"""Runtime state of the bot.

The bot keeps its runtime counters in memory and mirrors them to a JSON file
so that external PowerShell scripts can produce a live status report (running
state, uptime, unique users, processed messages) without connecting to the
bot. It also registers its own PID in a pid file so the same scripts can
detect and manage the running instance regardless of how it was launched.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_RUN_DIR = Path(__file__).resolve().parent.parent / "run"
DEFAULT_STATS_FILE = DEFAULT_RUN_DIR / "stats.json"
DEFAULT_PID_FILE = DEFAULT_RUN_DIR / "bot.pid"


class Stats:
    """Track runtime counters and persist them to a JSON file.

    Attributes:
        stats_file: Path to the JSON file used for persistence
    """

    def __init__(self, stats_file: Path | None = None) -> None:
        """Initialise an empty counter state.

        Callers must invoke :meth:`reset` to mark the run start and persist
        the initial zero state.

        Args:
            stats_file: Path to the statistics JSON file; defaults to
                ``run/stats.json`` next to the project root
        """
        self.stats_file = stats_file or DEFAULT_STATS_FILE
        self._lock = threading.Lock()
        self._started_at: float | None = None
        self._messages: dict[int, int] = {}

    def reset(self) -> None:
        """Reset all counters and treat the current moment as the run start.

        Writes a fresh zero snapshot, so the next status report reflects only
        activity since this call began.
        """
        with self._lock:
            self._started_at = time.time()
            self._messages = {}
        self.persist()

    def record_message(self, user_id: int) -> None:
        """Record one incoming message from a user.

        Args:
            user_id: Telegram user ID that sent the message
        """
        with self._lock:
            self._messages[user_id] = self._messages.get(user_id, 0) + 1
        self.persist()

    def snapshot(self) -> dict:
        """Return a JSON-serialisable snapshot of the current state.

        Returns:
            dict: ``started_at`` (unix seconds), ``users_count``,
                ``messages_processed`` and per-user counts under ``users``
        """
        with self._lock:
            return self._snapshot_locked()

    def persist(self) -> None:
        """Atomically write the current state to the JSON file.

        The state is first written to a ``.tmp`` file and then renamed into
        place, so a reader never observes a partially written file.
        """
        with self._lock:
            payload = self._snapshot_locked()
        try:
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.stats_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp_file.replace(self.stats_file)
        except OSError as exc:
            logger.warning("Could not persist stats to %s: %s", self.stats_file, exc)

    def _snapshot_locked(self) -> dict:
        """Build a snapshot assuming the caller already holds the lock.

        Returns:
            dict: Serialisable counter state
        """
        return {
            "started_at": int(self._started_at or 0),
            "users_count": len(self._messages),
            "messages_processed": sum(self._messages.values()),
            "users": {str(user_id): count for user_id, count in self._messages.items()},
        }


def write_pid_file(pid_file: Path = DEFAULT_PID_FILE) -> int:
    """Persist the current process ID to the pid file.

    Args:
        pid_file: Path to the pid file; defaults to ``run/bot.pid``

    Returns:
        int: The recorded process ID
    """
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="ascii")
    return os.getpid()


def clear_pid_file(pid_file: Path = DEFAULT_PID_FILE) -> None:
    """Remove the pid file if it belongs to the current process.

    A foreign PID is left untouched so a newer instance is never disturbed by
    the shutdown of an older one.

    Args:
        pid_file: Path to the pid file; defaults to ``run/bot.pid``
    """
    try:
        recorded = int(pid_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return
    if recorded != os.getpid():
        return
    try:
        pid_file.unlink()
    except OSError as exc:
        logger.warning("Could not remove pid file %s: %s", pid_file, exc)
