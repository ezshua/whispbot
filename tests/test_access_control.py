"""Tests for user access control."""

from pathlib import Path

from src.access_control import (
    DEFAULT_ADMIN_ID,
    DEFAULT_ADMIN_NAME,
    MAX_PENDING_MESSAGES,
    AccessManager,
    parse_user_args,
)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestParseUserArgs:
    """Tests for parse_user_args."""

    def test_id_only(self):
        assert parse_user_args("123") == (123, "")

    def test_id_and_name(self):
        assert parse_user_args("123 Ivan") == (123, "Ivan")

    def test_name_and_id(self):
        assert parse_user_args("Ivan 123") == (123, "Ivan")

    def test_semicolon_separator(self):
        assert parse_user_args("123;Ivan") == (123, "Ivan")

    def test_comma_separator(self):
        assert parse_user_args("Ivan,123") == (123, "Ivan")

    def test_colon_and_pipe_separators(self):
        assert parse_user_args("123:Petrov|Sidorov") == (123, "Petrov Sidorov")

    def test_negative_id(self):
        assert parse_user_args("-123 Ivan") == (-123, "Ivan")

    def test_two_numbers_first_is_id(self):
        assert parse_user_args("123 456") == (123, "456")

    def test_multiple_word_name(self):
        assert parse_user_args("Ivan Petrov 123") == (123, "Ivan Petrov")

    def test_no_id_returns_none(self):
        assert parse_user_args("Ivan") == (None, "")

    def test_empty_returns_none(self):
        assert parse_user_args("") == (None, "")


class TestAddAllowed:
    """Tests for add_allowed."""

    def test_appends_to_allowed_file(self, tmp_path):
        allowed = tmp_path / "allowed.txt"
        _write(allowed, "1; Admin\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(allowed, tmp_path / "ignored.txt")
        added = access.add_allowed(456, "Ivan")

        assert added is True
        assert access.is_allowed(456)
        assert "456; Ivan" in allowed.read_text(encoding="utf-8")

    def test_removes_user_from_ignored(self, tmp_path):
        ignored = tmp_path / "ignored.txt"
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(ignored, "456; Spammer\n")

        access = AccessManager(tmp_path / "allowed.txt", ignored)
        access.add_allowed(456, "Ivan")

        assert access.is_ignored(456) is False
        content = ignored.read_text(encoding="utf-8")
        assert "456" not in content

    def test_preserves_other_ignored_entries(self, tmp_path):
        ignored = tmp_path / "ignored.txt"
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(ignored, "# comment\n456; Spammer\n789; Bot\n")

        access = AccessManager(tmp_path / "allowed.txt", ignored)
        access.add_allowed(456, "Ivan")

        content = ignored.read_text(encoding="utf-8")
        assert "456" not in content
        assert "789; Bot" in content
        assert "# comment" in content

    def test_returns_false_when_already_allowed(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")
        added = access.add_allowed(1, "New Name")

        assert added is False
        assert access.allowed[1] == "Admin"

    def test_accepts_negative_id(self, tmp_path):
        allowed = tmp_path / "allowed.txt"
        _write(allowed, "1; Admin\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(allowed, tmp_path / "ignored.txt")
        added = access.add_allowed(-5, "Test")

        assert added is True
        assert "-5; Test" in allowed.read_text(encoding="utf-8")


class TestDelAllowed:
    """Tests for del_allowed."""

    def test_moves_user_to_ignored_keeping_comment(self, tmp_path):
        allowed = tmp_path / "allowed.txt"
        ignored = tmp_path / "ignored.txt"
        _write(allowed, "1; Admin\n456; Ivan\n")
        _write(ignored, "")

        access = AccessManager(allowed, ignored)
        moved = access.del_allowed(456)

        assert moved is True
        assert access.is_allowed(456) is False
        assert access.is_ignored(456)
        assert access.ignored[456] == "Ivan"
        assert "456" not in allowed.read_text(encoding="utf-8")
        assert "456; Ivan" in ignored.read_text(encoding="utf-8")

    def test_preserves_other_allowed_entries(self, tmp_path):
        allowed = tmp_path / "allowed.txt"
        _write(allowed, "1; Admin\n456; Ivan\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(allowed, tmp_path / "ignored.txt")
        access.del_allowed(456)

        content = allowed.read_text(encoding="utf-8")
        assert "1; Admin" in content
        assert "456" not in content

    def test_returns_false_when_not_allowed(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")
        moved = access.del_allowed(999)

        assert moved is False
        assert access.is_ignored(999) is False

    def test_clears_pending_counter(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n456; Ivan\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")
        access.record_pending(456, "Ivan")
        assert access.pending_count(456) == 1

        access.del_allowed(456)

        assert access.pending_count(456) == 0


class TestFormatLists:
    """Tests for format_allowed / format_ignored."""

    def test_formats_allowed_with_names_and_ids(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n456; Ivan\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.format_allowed() == "Admin (1)\nIvan (456)"
        assert access.format_ignored() == ""

    def test_formats_ignored_without_names(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n")
        _write(tmp_path / "ignored.txt", "789\n")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.format_ignored() == "789"

    def test_lists_ordered_by_user_id(self, tmp_path):
        _write(tmp_path / "allowed.txt", "1; Admin\n100; Zed\n50; Mid\n")
        _write(tmp_path / "ignored.txt", "")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.format_allowed() == "Admin (1)\nMid (50)\nZed (100)"

    def test_empty_lists_return_empty_string(self, tmp_path):
        _write(tmp_path / "allowed.txt", "# header\n")
        _write(tmp_path / "ignored.txt", "# header\n")

        access = AccessManager(tmp_path / "allowed.txt", tmp_path / "ignored.txt")

        assert access.format_allowed() == ""
        assert access.format_ignored() == ""


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
