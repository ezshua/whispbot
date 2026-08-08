"""Tests for runtime statistics tracking."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.bot import WhispBot
from src.stats import Stats, clear_pid_file, write_pid_file
from src.utils import FALLBACK_TEMP_DIR


class TestStats:
    """Tests for the Stats counter store."""

    def _make(self, tmp_path) -> Stats:
        return Stats(tmp_path / "stats.json")

    def test_reset_writes_zero_state(self, tmp_path):
        stats = self._make(tmp_path)
        stats.reset()
        data = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
        assert data["started_at"] > 0
        assert data["users_count"] == 0
        assert data["messages_processed"] == 0
        assert data["users"] == {}

    def test_record_message_persists_per_user_counts(self, tmp_path):
        stats = self._make(tmp_path)
        stats.record_message(111)
        stats.record_message(222)
        stats.record_message(111)

        data = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
        assert data["users_count"] == 2
        assert data["messages_processed"] == 3
        assert data["users"]["111"] == 2
        assert data["users"]["222"] == 1

    def test_snapshot_matches_persisted_file(self, tmp_path):
        stats = self._make(tmp_path)
        stats.record_message(111)
        assert stats.snapshot() == json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))

    def test_reset_clears_accumulated_counters(self, tmp_path):
        stats = self._make(tmp_path)
        stats.record_message(111)
        stats.reset()

        data = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
        assert data["users_count"] == 0
        assert data["messages_processed"] == 0
        assert data["users"] == {}

    def test_persist_is_atomic_and_leaves_no_temp_file(self, tmp_path):
        stats = self._make(tmp_path)
        stats.record_message(111)
        assert not (tmp_path / "stats.json.tmp").exists()


@pytest.mark.asyncio
async def test_bot_tracks_messages_through_collector(mock_config, tmp_path):
    """The stats collector must record each message, including unknown users."""
    stats = Stats(tmp_path / "stats.json")
    bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, stats=stats)

    update = MagicMock()
    user = MagicMock()
    user.id = 999
    update.effective_user = user

    await bot._stats_collector(update, MagicMock())
    await bot._stats_collector(update, MagicMock())

    snapshot = stats.snapshot()
    assert snapshot["users_count"] == 1
    assert snapshot["messages_processed"] == 2

    update.effective_user = None
    await bot._stats_collector(update, MagicMock())
    assert stats.snapshot()["messages_processed"] == 2


@patch("src.bot.Application.builder")
def test_run_registers_stats_collector_in_separate_group(mock_builder, mock_config, tmp_path):
    """With stats enabled, run() must add a collector handler in group 1."""
    app = MagicMock()
    mock_builder.return_value.token.return_value.build.return_value = app

    stats = Stats(tmp_path / "stats.json")
    bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, stats=stats)
    bot.run()

    collectors = [call for call in app.add_handler.call_args_list if call.kwargs.get("group") == 1]
    assert len(collectors) == 1
    handler = collectors[0].args[0]
    assert handler.callback == bot._stats_collector


@patch("src.bot.Application.builder")
def test_run_without_stats_has_no_group_one_handler(mock_builder, mock_config):
    """Without stats, run() must not register the group-1 collector."""
    app = MagicMock()
    mock_builder.return_value.token.return_value.build.return_value = app

    bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
    bot.run()

    assert not any(call.kwargs.get("group") == 1 for call in app.add_handler.call_args_list)


class TestPidFile:
    """Tests for the pid file helpers."""

    def test_write_pid_file_records_current_pid(self, tmp_path):
        pid_file = tmp_path / "bot.pid"
        assert write_pid_file(pid_file) == os.getpid()
        assert pid_file.read_text(encoding="ascii").strip() == str(os.getpid())

    def test_clear_pid_file_removes_own_pid(self, tmp_path):
        pid_file = tmp_path / "bot.pid"
        write_pid_file(pid_file)
        clear_pid_file(pid_file)
        assert not pid_file.exists()

    def test_clear_pid_file_keeps_foreign_pid(self, tmp_path):
        pid_file = tmp_path / "bot.pid"
        pid_file.write_text("123456789", encoding="ascii")
        clear_pid_file(pid_file)
        assert pid_file.exists()

    def test_clear_pid_file_ignores_missing_file(self, tmp_path):
        pid_file = tmp_path / "bot.pid"
        clear_pid_file(pid_file)
        assert not pid_file.exists()
