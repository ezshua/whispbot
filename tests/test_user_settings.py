"""Tests for per-user settings."""

from unittest.mock import MagicMock

from src.user_settings import USER_SETTINGS_KEY, UserSettings, get_user_settings


class TestUserSettingsDefaults:
    """Tests for UserSettings default values."""

    def test_defaults(self):
        settings = UserSettings()
        assert settings.language is None
        assert settings.temperature == 0.0
        assert settings.model is None
        assert settings.minimal_mode is False


class TestGetUserSettings:
    """Tests for get_user_settings."""

    def test_creates_settings_lazily(self):
        context = MagicMock()
        context.user_data = {}
        settings = get_user_settings(context)
        assert isinstance(settings, UserSettings)
        assert context.user_data[USER_SETTINGS_KEY] is settings

    def test_returns_existing_settings(self):
        existing = UserSettings(language="ru", temperature=0.4)
        context = MagicMock()
        context.user_data = {USER_SETTINGS_KEY: existing}
        assert get_user_settings(context) is existing

    def test_two_contexts_have_isolated_settings(self):
        first = MagicMock()
        first.user_data = {}
        second = MagicMock()
        second.user_data = {}
        first_settings = get_user_settings(first)
        second_settings = get_user_settings(second)
        assert first_settings is not second_settings
