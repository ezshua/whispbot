"""User access control for WhispBot.

Allowed and ignored user lists are stored in plain text files, one user per
line: ``<user_id>; <name or comment>``. Lines starting with ``#`` and blank
lines are skipped. The first entry of the allowed list is treated as the bot
admin, who receives forwarded requests and technical messages. Both lists are
read once at startup.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_PENDING_MESSAGES: int = 3

DEFAULT_ADMIN_ID: int = 962767424
DEFAULT_ADMIN_NAME: str = "alexx-rc1"

_FILE_HEADER = "# user_id; name or comment"

_ARGUMENT_DELIMITERS = re.compile(r"[\s,;:|]+")


def parse_user_args(raw: str) -> tuple[int | None, str]:
    """Parse a user ID and optional name from command arguments.

    The ID and name may appear in any order and be separated by whitespace,
    commas, semicolons, colons or pipes. The first numeric token is treated as
    the user ID (negative values are allowed); all other tokens joined with
    spaces form the name. If both parameters are numeric, the first is the ID
    and the second becomes the name.

    Args:
        raw: Raw command arguments (everything after the command)

    Returns:
        tuple[Optional[int], str]: User ID (or None if no numeric token found)
            and the name
    """
    tokens = [token for token in _ARGUMENT_DELIMITERS.split(raw) if token]
    for index, token in enumerate(tokens):
        try:
            user_id = int(token)
        except ValueError:
            continue
        name = " ".join(tokens[:index] + tokens[index + 1 :])
        return user_id, name
    return None, ""


@dataclass(frozen=True)
class AccessEntry:
    """A single entry of an access list file.

    Attributes:
        user_id: Telegram user ID
        comment: Name or comment from the file line after the semicolon
    """

    user_id: int
    comment: str = ""


def _format_user_list(users: dict[int, str]) -> str:
    """Render a user list as a display string.

    One user per line as ``<name> (<id>)``; users without a name are shown by
    their ID alone. Lines are ordered by user ID.

    Args:
        users: User IDs mapped to their comments

    Returns:
        str: One user per line, or an empty string if the list is empty
    """
    lines: list[str] = []
    for user_id in sorted(users):
        comment = users[user_id]
        lines.append(f"{comment} ({user_id})" if comment else str(user_id))
    return "\n".join(lines)


class AccessManager:
    """Manage allowed and ignored user lists.

    Attributes:
        allowed: Allowed user IDs mapped to their comments
        ignored: Ignored user IDs mapped to their comments
        pending: In-memory counter of request messages per pending user ID
        admin_id: ID of the bot admin (first allowed list entry) or None
    """

    def __init__(self, allowed_file: Path, ignored_file: Path) -> None:
        """Initialize the manager and load both lists.

        Args:
            allowed_file: Path to the allowed users list file
            ignored_file: Path to the ignored users list file
        """
        self.allowed_file = allowed_file
        self.ignored_file = ignored_file
        self.allowed: dict[int, str] = {}
        self.ignored: dict[int, str] = {}
        self.pending: dict[int, int] = {}
        self.admin_id: int | None = None
        self._load()

    def _load(self) -> None:
        """Read both lists and detect the admin."""
        allowed_entries = self._read_entries(
            self.allowed_file,
            seed_entries=[AccessEntry(DEFAULT_ADMIN_ID, DEFAULT_ADMIN_NAME)],
        )
        self.allowed = {entry.user_id: entry.comment for entry in allowed_entries}
        self.admin_id = allowed_entries[0].user_id if allowed_entries else None

        ignored_entries = self._read_entries(self.ignored_file)
        self.ignored = {entry.user_id: entry.comment for entry in ignored_entries}

        logger.info(
            "Access lists loaded: %d allowed, %d ignored, admin=%s",
            len(self.allowed),
            len(self.ignored),
            self.admin_id,
        )
        if self.admin_id is None:
            logger.warning(
                "Allowed users list '%s' is empty — admin is not set, requests cannot be forwarded",
                self.allowed_file,
            )

    def _read_entries(
        self, path: Path, seed_entries: list[AccessEntry] | None = None
    ) -> list[AccessEntry]:
        """Read and parse a user list file.

        Creates the file with a header comment if it does not exist, seeding it
        with the given entries. Invalid lines are skipped with a warning.

        Args:
            path: Path to the list file
            seed_entries: Entries written to the file when it is created

        Returns:
            list[AccessEntry]: Parsed entries
        """
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = [_FILE_HEADER + "\n"]
            for entry in seed_entries or []:
                lines.append(f"{entry.user_id}; {entry.comment}\n")
            path.write_text("".join(lines), encoding="utf-8")
            logger.info("Created empty user list file: %s", path)
            return list(seed_entries or [])

        entries: list[AccessEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            raw_id, _, comment = line.partition(";")
            try:
                user_id = int(raw_id.strip())
            except ValueError:
                logger.warning("Skipping invalid line in '%s': %r", path, line)
                continue
            entries.append(AccessEntry(user_id, comment.strip()))
        return entries

    def is_allowed(self, user_id: int) -> bool:
        """Check whether the user is in the allowed list.

        Args:
            user_id: Telegram user ID

        Returns:
            bool: True if the user is allowed
        """
        return user_id in self.allowed

    def format_allowed(self) -> str:
        """Render the allowed users list for display.

        Returns:
            str: One user per line, or an empty string if the list is empty
        """
        return _format_user_list(self.allowed)

    def format_ignored(self) -> str:
        """Render the ignored users list for display.

        Returns:
            str: One user per line, or an empty string if the list is empty
        """
        return _format_user_list(self.ignored)

    def is_ignored(self, user_id: int) -> bool:
        """Check whether the user is in the ignored list.

        Args:
            user_id: Telegram user ID

        Returns:
            bool: True if the user is ignored
        """
        return user_id in self.ignored

    def pending_count(self, user_id: int) -> int:
        """Return the number of request messages sent by a pending user.

        Args:
            user_id: Telegram user ID

        Returns:
            int: Number of recorded messages (0 if none)
        """
        return self.pending.get(user_id, 0)

    def record_pending(self, user_id: int, comment: str = "") -> int:
        """Record one request message from a pending user.

        Once the user reaches MAX_PENDING_MESSAGES, they are added to the
        ignored list.

        Args:
            user_id: Telegram user ID
            comment: Name or comment used for the ignored list entry

        Returns:
            int: New message count for the user
        """
        count = self.pending.get(user_id, 0) + 1
        self.pending[user_id] = count
        if count >= MAX_PENDING_MESSAGES:
            self.add_ignored(
                user_id, comment or f"auto-added after {MAX_PENDING_MESSAGES} messages"
            )
        return count

    def add_allowed(self, user_id: int, comment: str = "") -> bool:
        """Add a user to the allowed list and remove them from the ignored list.

        The user is appended to the allowed file. If present in the ignored
        list, the entry is removed from memory and from the ignored file.

        Args:
            user_id: Telegram user ID
            comment: Name or comment for the file line

        Returns:
            bool: True if the user was newly added, False if already allowed
        """
        was_allowed = user_id in self.allowed
        if user_id in self.ignored:
            del self.ignored[user_id]
            self._remove_line_from_file(self.ignored_file, user_id)
        if not was_allowed:
            self.allowed[user_id] = comment
            with self.allowed_file.open("a", encoding="utf-8") as file:
                file.write(f"{user_id}; {comment}\n")
            logger.info("User %s added to allowed list", user_id)
        return not was_allowed

    def del_allowed(self, user_id: int) -> bool:
        """Move a user from the allowed list to the ignored list.

        Removes the user from the allowed list (memory and file) and adds them
        to the ignored list (memory and file), keeping the original comment.
        The pending message counter for the user is cleared.

        Args:
            user_id: Telegram user ID

        Returns:
            bool: True if the user was allowed and got moved, False otherwise
        """
        comment = self.allowed.pop(user_id, None)
        if comment is None:
            return False
        self._remove_line_from_file(self.allowed_file, user_id)
        self.pending.pop(user_id, None)
        self.add_ignored(user_id, comment)
        logger.info("User %s moved from allowed to ignored list", user_id)
        return True

    def add_ignored(self, user_id: int, comment: str = "") -> None:
        """Add a user to the ignored list and append them to the file.

        Args:
            user_id: Telegram user ID
            comment: Name or comment for the file line
        """
        if user_id in self.ignored:
            return
        self.ignored[user_id] = comment
        with self.ignored_file.open("a", encoding="utf-8") as file:
            file.write(f"{user_id}; {comment}\n")
        logger.info("User %s added to ignored list", user_id)

    def _remove_line_from_file(self, path: Path, user_id: int) -> None:
        """Remove the line matching a user ID from a list file.

        Non-matching lines (including comments and invalid ones) are preserved
        in their original order.

        Args:
            path: Path to the list file
            user_id: Telegram user ID whose line is removed
        """
        lines = path.read_text(encoding="utf-8").splitlines()
        kept: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                raw_id, _, _ = stripped.partition(";")
                try:
                    if int(raw_id.strip()) == user_id:
                        continue
                except ValueError:
                    pass
            kept.append(line)
        path.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
