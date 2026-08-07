"""Tests for WhispBot."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.access_control import MAX_PENDING_MESSAGES, AccessManager
from src.bot import NonAllowedUserFilter, WhispBot, check_whisper_api, resolve_temp_dir
from src.config import load_config
from src.handlers import BotHandlers
from src.user_settings import UserSettings
from src.utils import FALLBACK_TEMP_DIR
from src.whisper_client import WhisperClient

# ── Existing tests ──────────────────────────────────────────────


def test_load_config():
    """Test configuration creates AppConfig with expected structure."""
    config = load_config()
    assert hasattr(config, "telegram_bot_token")
    assert hasattr(config, "whisper")
    assert hasattr(config, "files")
    assert hasattr(config.whisper, "api_base_url")
    assert hasattr(config.whisper, "api_key")
    assert hasattr(config.whisper, "model")
    assert hasattr(config.files, "max_file_size_mb")
    assert hasattr(config.files, "temp_dir_path")
    assert hasattr(config.files, "allowed_audio_extensions")
    assert hasattr(config.files, "allowed_video_extensions")


@pytest.mark.asyncio
async def test_whisper_client_transcribe(mock_config):
    """Test Whisper client transcription."""
    client = WhisperClient(mock_config.whisper)
    mock_http = MagicMock()
    mock_http.is_closed = False
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "test transcription"}
    mock_response.raise_for_status.return_value = None
    mock_http.post = AsyncMock(return_value=mock_response)
    client._client = mock_http

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value = MagicMock()
        result = await client.transcribe(Path("test.mp3"))
        assert result == "test transcription"


@pytest.mark.asyncio
async def test_bot_handlers_init(mock_config):
    """Test bot handlers initialization."""
    whisper_client = WhisperClient(mock_config.whisper)
    handlers = BotHandlers(mock_config, whisper_client, FALLBACK_TEMP_DIR)

    assert handlers.config == mock_config
    assert handlers.whisper_client == whisper_client
    assert handlers.temp_dir == FALLBACK_TEMP_DIR


@pytest.mark.asyncio
async def test_bot_handlers_audio(mock_config):
    """Test audio file handling."""
    whisper_client = WhisperClient(mock_config.whisper)
    handlers = BotHandlers(mock_config, whisper_client, FALLBACK_TEMP_DIR)

    mock_update = MagicMock()
    mock_context = MagicMock()
    mock_message = MagicMock()
    mock_message.from_user.id = 123
    mock_message.audio = MagicMock()
    mock_message.audio.file_id = "test_id"
    mock_message.audio.file_size = 1024
    mock_message.caption = None

    mock_file = MagicMock()
    mock_file.download_to_drive = AsyncMock()
    mock_message.audio.get_file = AsyncMock(return_value=mock_file)

    mock_listening_message = MagicMock()
    mock_listening_message.edit_text = AsyncMock()
    mock_message.reply_text = AsyncMock(return_value=mock_listening_message)
    mock_update.message = mock_message

    handlers.whisper_client.transcribe_audio = AsyncMock(return_value="test transcription")

    mock_context = MagicMock()
    mock_context.user_data = {}

    await handlers.handle_audio(mock_update, mock_context)

    mock_message.reply_text.assert_called_once_with("Слушаю...")


# ── WhispBot initialization ─────────────────────────────────────


class TestWhispBotInit:
    """Tests for WhispBot.__init__."""

    def test_creates_whisper_client_and_handlers(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        assert isinstance(bot.whisper_client, WhisperClient)
        assert isinstance(bot.handlers, BotHandlers)
        assert bot.handlers.temp_dir == FALLBACK_TEMP_DIR


# ── Bot commands ────────────────────────────────────────────────


class TestStartCommand:
    """Tests for _start_command."""

    @pytest.mark.asyncio
    async def test_switches_to_two_phase_and_replies(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}

        await bot._start_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].minimal_mode is False
        mock_update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shows_current_user_settings(self, mock_config):
        """/start must display the user's current individual settings."""
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {
            "settings": UserSettings(language="en", temperature=0.5, model="whisper-large-v3-turbo")
        }

        await bot._start_command(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "whisper-large-v3-turbo" in text
        assert "en" in text
        assert "0.5" in text

    @pytest.mark.asyncio
    async def test_shows_default_model_when_not_overridden(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}

        await bot._start_command(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "whisper-1" in text
        assert "auto" in text


class TestStartMinCommand:
    """Tests for _startmin_command."""

    @pytest.mark.asyncio
    async def test_sets_minimal_mode_true(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}

        await bot._startmin_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].minimal_mode is True
        mock_update.message.reply_text.assert_awaited_once()


class TestHelpCommand:
    """Tests for _help_command."""

    @pytest.mark.asyncio
    async def test_replies_with_help_text(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        await bot._help_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "/start" in text
        assert "/help" in text
        assert "/lang" in text


class TestLangCommand:
    """Tests for _lang_command."""

    @pytest.mark.asyncio
    async def test_sets_language_from_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["en"]

        await bot._lang_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].language == "en"
        mock_update.message.reply_text.assert_awaited_once_with("Язык: `en`")

    @pytest.mark.asyncio
    async def test_sets_language_to_none_for_auto(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {"settings": UserSettings(language="ru")}
        mock_context.args = ["auto"]

        await bot._lang_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].language is None
        mock_update.message.reply_text.assert_awaited_once_with("Язык: автораспознавание")

    @pytest.mark.asyncio
    async def test_replies_with_usage_when_no_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = []

        await bot._lang_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "Использование" in mock_update.message.reply_text.call_args[0][0]


class TestTempCommand:
    """Tests for _temp_command."""

    @pytest.mark.asyncio
    async def test_sets_temperature_from_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["0.5"]

        await bot._temp_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].temperature == 0.5
        mock_update.message.reply_text.assert_awaited_once_with("Температура: `0.5`")

    @pytest.mark.asyncio
    async def test_accepts_comma_as_decimal_separator(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["0,3"]

        await bot._temp_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].temperature == 0.3

    @pytest.mark.asyncio
    async def test_replies_with_usage_when_no_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = []

        await bot._temp_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "Использование" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_replies_error_for_invalid_number(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["abc"]

        await bot._temp_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "Ошибка" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_replies_error_for_out_of_range(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["2.5"]

        await bot._temp_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "0 до 1" in mock_update.message.reply_text.call_args[0][0]


class TestModelCommand:
    """Tests for _model_command."""

    @pytest.mark.asyncio
    async def test_switches_to_large_alias(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["large"]

        await bot._model_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].model == "whisper-large-v3"
        mock_update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_switches_to_turbo_alias(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["turbo"]

        await bot._model_command(mock_update, mock_context)

        assert mock_context.user_data["settings"].model == "whisper-large-v3-turbo"
        mock_update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_replies_usage_when_no_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = []

        await bot._model_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "Использование" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_replies_error_for_invalid_alias(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.args = ["invalid"]

        await bot._model_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "Ошибка" in mock_update.message.reply_text.call_args[0][0]


# ── check_whisper_api ───────────────────────────────────────────


class TestCheckWhisperApi:
    """Tests for check_whisper_api."""

    @patch("httpx.get")
    def test_ok_when_model_found(self, mock_get, mock_config):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": "whisper-1"}, {"id": "whisper-large-v3"}]
        }
        mock_get.return_value = mock_response

        check_whisper_api(mock_config)

        mock_get.assert_called_once_with(
            "http://test.com/models",
            headers={"Authorization": "Bearer test_key"},
            timeout=5.0,
        )

    @patch("httpx.get")
    def test_does_not_raise_when_model_not_in_list(self, mock_get, mock_config):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "other-model"}]}
        mock_get.return_value = mock_response

        check_whisper_api(mock_config)

    @patch("httpx.get")
    def test_does_not_raise_on_http_error(self, mock_get, mock_config):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        check_whisper_api(mock_config)

    @patch("httpx.get", side_effect=httpx.ConnectError("unreachable"))
    def test_does_not_raise_on_connection_error(self, mock_get, mock_config):
        check_whisper_api(mock_config)


# ── resolve_temp_dir ────────────────────────────────────────────


class TestResolveTempDir:
    """Tests for resolve_temp_dir."""

    @patch("src.bot.ensure_temp_dir", return_value=Path("temp"))
    @patch("src.bot.cleanup_temp_dir")
    def test_returns_temp_dir_path(self, mock_cleanup, mock_ensure, mock_config):
        result = resolve_temp_dir(mock_config)
        assert result == Path("temp")
        mock_ensure.assert_called_once_with(Path("temp"))
        mock_cleanup.assert_called_once_with(Path("temp"))


# ── Gatekeeper ──────────────────────────────────────────────────


def _make_access(tmp_path, allowed="1; Admin\n", ignored=""):
    """Create an AccessManager with a real admin from test files."""
    allowed_path = tmp_path / "allowed.txt"
    allowed_path.write_text(allowed, encoding="utf-8")
    ignored_path = tmp_path / "ignored.txt"
    ignored_path.write_text(ignored, encoding="utf-8")
    return AccessManager(allowed_path, ignored_path)


def _make_update(user_id, text=None, voice=None):
    message = MagicMock()
    message.text = text
    message.voice = voice
    message.forward = AsyncMock()
    message.reply_text = AsyncMock()
    user = MagicMock()
    user.id = user_id
    user.full_name = "Test User"
    update = MagicMock()
    update.effective_user = user
    update.message = message
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    return update, context


class TestNonAllowedUserFilter:
    """Tests for NonAllowedUserFilter."""

    def test_matches_non_allowed_user(self, tmp_path):
        access = _make_access(tmp_path)
        update, _ = _make_update(999)
        assert NonAllowedUserFilter(access).check_update(update) is True

    def test_does_not_match_allowed_user(self, tmp_path):
        access = _make_access(tmp_path)
        update, _ = _make_update(1)
        assert NonAllowedUserFilter(access).check_update(update) is False

    def test_matches_ignored_user(self, tmp_path):
        access = _make_access(tmp_path, allowed="1\n", ignored="999; Blocked\n")
        update, _ = _make_update(999)
        assert NonAllowedUserFilter(access).check_update(update) is True

    def test_returns_false_without_user(self, tmp_path):
        access = _make_access(tmp_path)
        update = MagicMock()
        update.effective_user = None
        assert NonAllowedUserFilter(access).check_update(update) is False

    def test_allows_admin_voice_message(self, tmp_path):
        """Admin's voice message must not be swallowed by the gatekeeper."""
        access = _make_access(tmp_path)
        update, _ = _make_update(1, voice=MagicMock())
        assert NonAllowedUserFilter(access).check_update(update) is False

    def test_allows_admin_audio_message(self, tmp_path):
        access = _make_access(tmp_path)
        update, _ = _make_update(1, voice=None)
        update.message.audio = MagicMock()
        assert NonAllowedUserFilter(access).check_update(update) is False


class TestGatekeeper:
    """Tests for the gatekeeper handler."""

    @pytest.mark.asyncio
    async def test_silently_ignores_ignored_users(self, tmp_path, mock_config):
        access = _make_access(tmp_path, allowed="1\n", ignored="777; Blocked\n")
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(777, text="hello")

        await bot._gatekeeper(update, context)

        update.message.reply_text.assert_not_called()
        update.message.forward.assert_not_called()

    @pytest.mark.asyncio
    async def test_forwards_text_to_admin_and_replies(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(999, text="user question")

        await bot._gatekeeper(update, context)

        update.message.forward.assert_awaited_once_with(chat_id=1)
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "передан администратору" in text
        remaining = MAX_PENDING_MESSAGES - 1
        assert str(remaining) in text

    @pytest.mark.asyncio
    async def test_notifies_admin_with_user_info_before_forward(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(999, text="user question")

        await bot._gatekeeper(update, context)

        context.bot.send_message.assert_awaited()
        notice = context.bot.send_message.call_args.kwargs
        assert notice["chat_id"] == 1
        assert "Test User" in notice["text"]
        assert "999" in notice["text"]
        assert "подключиться" in notice["text"]
        update.message.forward.assert_awaited_once_with(chat_id=1)

    @pytest.mark.asyncio
    async def test_forwards_voice_to_admin(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(999, voice=MagicMock())

        await bot._gatekeeper(update, context)

        update.message.forward.assert_awaited_once_with(chat_id=1)
        update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warns_wrong_type_without_forwarding(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(999, text=None, voice=None)
        update.message.audio = MagicMock()

        await bot._gatekeeper(update, context)

        update.message.forward.assert_not_called()
        update.message.reply_text.assert_awaited_once()
        assert "только текстовые и голосовые" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_adds_to_ignored_after_max_messages(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)

        for _ in range(MAX_PENDING_MESSAGES):
            update, context = _make_update(555, text="request")
            await bot._gatekeeper(update, context)

        assert access.is_ignored(555)
        last_reply = update.message.reply_text.call_args[0][0]
        assert "игнорируемых" in last_reply
        ignored_notice = [
            call.kwargs["text"]
            for call in context.bot.send_message.call_args_list
            if "игнорируемых" in call.kwargs["text"]
        ]
        assert len(ignored_notice) == 1

    @pytest.mark.asyncio
    async def test_replies_when_no_admin(self, tmp_path, mock_config):
        access = _make_access(tmp_path, allowed="")
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(999, text="question")

        await bot._gatekeeper(update, context)

        update.message.forward.assert_not_called()
        update.message.reply_text.assert_awaited_once()
        assert "не может быть отправлен" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_gatekeeper_skips_without_access_manager(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        update, context = _make_update(999, text="question")

        await bot._gatekeeper(update, context)

        update.message.reply_text.assert_not_called()
        update.message.forward.assert_not_called()


# ── /adduser command ────────────────────────────────────────────


class TestAddUserCommand:
    """Tests for the admin-only /adduser command."""

    @pytest.mark.asyncio
    async def test_silently_ignored_for_allowed_non_admin(self, tmp_path, mock_config):
        access = _make_access(tmp_path, allowed="1; Admin\n2; Regular\n")
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(2, text=None, voice=None)
        context.args = ["456", "Ivan"]

        await bot._adduser_command(update, context)

        update.message.reply_text.assert_not_called()
        assert access.is_allowed(456) is False

    @pytest.mark.asyncio
    async def test_silently_ignored_for_unknown_user(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(999, text=None, voice=None)
        context.args = ["456"]

        await bot._adduser_command(update, context)

        update.message.reply_text.assert_not_called()
        assert access.is_allowed(456) is False

    @pytest.mark.asyncio
    async def test_admin_adds_user_with_name(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["456", "Ivan"]

        await bot._adduser_command(update, context)

        assert access.is_allowed(456)
        assert access.allowed[456] == "Ivan"
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "456" in text and "Ivan" in text
        assert "добавлен" in text

    @pytest.mark.asyncio
    async def test_admin_adds_user_and_removes_from_ignored(self, tmp_path, mock_config):
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("1; Admin\n", encoding="utf-8")
        ignored = tmp_path / "ignored.txt"
        ignored.write_text("456; Spammer\n", encoding="utf-8")
        access = AccessManager(allowed, ignored)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["456", "Ivan"]

        await bot._adduser_command(update, context)

        assert access.is_ignored(456) is False
        assert "456" not in ignored.read_text(encoding="utf-8")
        text = update.message.reply_text.call_args[0][0]
        assert "игнорируемых" in text

    @pytest.mark.asyncio
    async def test_admin_accepts_name_and_id_in_any_order(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["Ivan;456"]

        await bot._adduser_command(update, context)

        assert access.allowed[456] == "Ivan"

    @pytest.mark.asyncio
    async def test_two_numbers_first_is_id(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["123", "456"]

        await bot._adduser_command(update, context)

        assert access.allowed[123] == "456"

    @pytest.mark.asyncio
    async def test_accepts_negative_id(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["-5", "Bob"]

        await bot._adduser_command(update, context)

        assert access.allowed[-5] == "Bob"

    @pytest.mark.asyncio
    async def test_replies_usage_when_no_id(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = []

        await bot._adduser_command(update, context)

        update.message.reply_text.assert_awaited_once()
        assert "Использование" in update.message.reply_text.call_args[0][0]


class TestDelUserCommand:
    """Tests for the admin-only /deluser command."""

    @pytest.mark.asyncio
    async def test_silently_ignored_for_non_admin(self, tmp_path, mock_config):
        access = _make_access(tmp_path, allowed="1; Admin\n2; Regular\n")
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(2, text=None, voice=None)
        context.args = ["1"]

        await bot._deluser_command(update, context)

        update.message.reply_text.assert_not_called()
        assert access.is_allowed(1)

    @pytest.mark.asyncio
    async def test_admin_moves_user_to_ignored(self, tmp_path, mock_config):
        access = _make_access(tmp_path, allowed="1; Admin\n456; Ivan\n")
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["456"]

        await bot._deluser_command(update, context)

        assert access.is_allowed(456) is False
        assert access.is_ignored(456)
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "456" in text and "игнорируемых" in text

    @pytest.mark.asyncio
    async def test_moved_user_is_removed_from_allowed_file(self, tmp_path, mock_config):
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("1; Admin\n456; Ivan\n", encoding="utf-8")
        ignored = tmp_path / "ignored.txt"
        ignored.write_text("", encoding="utf-8")
        access = AccessManager(allowed, ignored)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["456"]

        await bot._deluser_command(update, context)

        assert "456" not in allowed.read_text(encoding="utf-8")
        assert "456; Ivan" in ignored.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_replies_error_when_not_in_allowed(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["999"]

        await bot._deluser_command(update, context)

        update.message.reply_text.assert_awaited_once()
        assert "не в списке" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_refuses_to_delete_admin(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = ["1"]

        await bot._deluser_command(update, context)

        assert access.is_allowed(1)
        update.message.reply_text.assert_awaited_once()
        assert "нельзя удалить" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_replies_usage_when_no_id(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)
        context.args = []

        await bot._deluser_command(update, context)

        update.message.reply_text.assert_awaited_once()
        assert "Использование" in update.message.reply_text.call_args[0][0]


class TestListUserCommand:
    """Tests for the admin-only /listuser command."""

    @pytest.mark.asyncio
    async def test_silently_ignored_for_non_admin(self, tmp_path, mock_config):
        access = _make_access(tmp_path, allowed="1; Admin\n2; Regular\n")
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(2, text=None, voice=None)

        await bot._listuser_command(update, context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_two_messages_with_lists(self, tmp_path, mock_config):
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("1; Admin\n", encoding="utf-8")
        ignored = tmp_path / "ignored.txt"
        ignored.write_text("789; Spammer\n", encoding="utf-8")
        access = AccessManager(allowed, ignored)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)

        await bot._listuser_command(update, context)

        replies = [call.args[0] for call in update.message.reply_text.call_args_list]
        assert len(replies) == 2
        assert "Разрешённые" in replies[0]
        assert "Admin (1)" in replies[0]
        assert "Игнорируемые" in replies[1]
        assert "Spammer (789)" in replies[1]

    @pytest.mark.asyncio
    async def test_shows_empty_placeholder_for_empty_ignored(self, tmp_path, mock_config):
        access = _make_access(tmp_path)
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR, access)
        update, context = _make_update(1, text=None, voice=None)

        await bot._listuser_command(update, context)

        replies = [call.args[0] for call in update.message.reply_text.call_args_list]
        assert len(replies) == 2
        assert "Admin (1)" in replies[0]
        assert "Список пуст" in replies[1]
