"""User access control for WhispBot.

Allowed and ignored user lists are stored in plain text files, one user per
line: ``<user_id>; <name or comment>``. Lines starting with ``#`` and blank
lines are skipped. The first entry of the allowed list is treated as the bot
admin, who receives forwarded requests and technical messages. Both lists are
read once at startup.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_PENDING_MESSAGES: int = 3

DEFAULT_ADMIN_ID: int = 962767424
DEFAULT_ADMIN_NAME: str = "alexx-rc1"

_FILE_HEADER = "# user_id; name or comment"


@dataclass(frozen=True)
class AccessEntry:
    """A single entry of an access list file.

    Attributes:
        user_id: Telegram user ID
        comment: Name or comment from the file line after the semicolon
    """

    user_id: int
    comment: str = ""


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
