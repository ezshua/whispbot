"""Per-user bot settings.

Settings live in the python-telegram-bot ``context.user_data`` dictionary,
which is provided automatically by the Application. They are stored in memory
only, so they reset every time the bot is restarted.
"""

from dataclasses import dataclass

from telegram.ext import ContextTypes

USER_SETTINGS_KEY: str = "settings"


@dataclass
class UserSettings:
    """Individual transcription settings for a single user.

    Attributes:
        language: Recognition language code (ISO-639-1) or None for auto-detect.
        temperature: Sampling temperature (0.0-1.0).
        model: Model name or alias; None means the default from the config.
        minimal_mode: Reply with a single message instead of the two-phase flow.
    """

    language: str | None = None
    temperature: float = 0.0
    model: str | None = None
    minimal_mode: bool = False


def get_user_settings(context: ContextTypes.DEFAULT_TYPE) -> UserSettings:
    """Return the per-user settings, creating them lazily on first access.

    Args:
        context: Telegram context callback carrying ``user_data``.

    Returns:
        UserSettings: The stored settings object for the current user.
    """
    settings = context.user_data.get(USER_SETTINGS_KEY)
    if settings is None:
        settings = UserSettings()
        context.user_data[USER_SETTINGS_KEY] = settings
    return settings
