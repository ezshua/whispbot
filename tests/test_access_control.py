"""Tests for user access control."""

from pathlib import Path

from src.access_control import (
    DEFAULT_ADMIN_ID,
    DEFAULT_ADMIN_NAME,
    MAX_PENDING_MESSAGES,
    AccessManager,
)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestLoadLists:
    """Tests for list loading and parsing."""

    def test_admin_is_first_entry(self, tmp_path):
        _write(tmp_path / "allowed.txt", "# allowed\n123; Admin Name\n456; Friend\n")
        _write(tmp_path / "ignored.txt", "789; Spammer\n")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.admin_id == 123
        assert access.allowed == {123: "Admin Name", 456: "Friend"}
        assert access.ignored == {789: "Spammer"}

    def test_skips_blank_and_comment_lines(self, tmp_path):
        _write(tmp_path / "allowed.txt", "\n# header\n\n123;\n456; Second user\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.allowed == {123: "", 456: "Second user"}
        assert access.admin_id == 123

    def test_skips_invalid_lines(self, tmp_path):
        _write(tmp_path / "allowed.txt", "not-a-number; bad\n123; Valid\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.allowed == {123: "Valid"}
        assert access.admin_id == 123

    def test_creates_missing_files_with_default_admin(self, tmp_path):
        allowed = tmp_path / "missing_allowed.txt"
        ignored = tmp_path / "missing_ignored.txt"

        access = AccessManager(allowed, ignored)

        assert allowed.exists()
        assert ignored.exists()
        assert access.allowed == {DEFAULT_ADMIN_ID: DEFAULT_ADMIN_NAME}
        assert access.ignored == {}
        assert access.admin_id == DEFAULT_ADMIN_ID

    def test_created_file_contains_default_admin_line(self, tmp_path):
        allowed = tmp_path / "missing_allowed.txt"
        ignored = tmp_path / "missing_ignored.txt"

        AccessManager(allowed, ignored)

        content = allowed.read_text(encoding="utf-8")
        assert f"{DEFAULT_ADMIN_ID}; {DEFAULT_ADMIN_NAME}" in content
        assert content.splitlines()[0].startswith("#")

    def test_empty_allowed_list_has_no_admin(self, tmp_path):
        _write(tmp_path / "allowed.txt", "")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.admin_id is None


class TestMembership:
    """Tests for is_allowed / is_ignored."""

    def test_membership_checks(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; One\n2; Two\n")
        _write(tmp_path / "ignored.txt", "3; Three\n")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.is_allowed(1)
        assert access.is_allowed(2)
        assert not access.is_allowed(3)
        assert not access.is_allowed(999)
        assert access.is_ignored(3)
        assert not access.is_ignored(1)
        assert not access.is_ignored(999)


class TestPendingCounter:
    """Tests for the pending messages counter."""

    def test_counter_is_in_memory_only(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")
        assert access.pending_count(555) == 0
        access.record_pending(555, "New User")
        assert access.pending_count(555) == 1

        restarted = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")
        assert restarted.pending_count(555) == 0

    def test_adds_to_ignored_after_max_messages(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        ignored = tmp_path / "ignored.txt"
        _write(ignored, "")

        access = AccessManager(tmp_path / "allowed.txt", ignored)
        for _ in range(MAX_PENDING_MESSAGES):
            count = access.record_pending(555, "New User")

        assert count == MAX_PENDING_MESSAGES
        assert access.is_ignored(555)
        assert "555; New User" in ignored.read_text(encoding="utf-8")

    def test_ignored_user_does_not_increment_counter(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(tmp_path / "ignored.txt", "555; Blocked\n")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")
        count = access.record_pending(555, "New User")

        assert count == 1
        assert access.pending_count(555) == 1


class TestAddIgnored:
    """Tests for add_ignored."""

    def test_appends_to_file_and_dict(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        ignored = tmp_path / "ignored.txt"
        _write(ignored, "7; Old\n")

        access = AccessManager(tmp_path / "allowed.txt", ignored)
        access.add_ignored(8, "New Blocked")

        assert access.is_ignored(8)
        assert "8; New Blocked" in ignored.read_text(encoding="utf-8")
        assert "7; Old" in ignored.read_text(encoding="utf-8")

    def test_does_not_duplicate_existing_user(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        ignored = tmp_path / "ignored.txt"
        _write(ignored, "7; Old\n")

        access = AccessManager(tmp_path / "allowed.txt", ignored)
        access.add_ignored(7, "Duplicate")

        assert ignored.read_text(encoding="utf-8").count("7;") == 1
