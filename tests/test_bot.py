"""Tests for WhispBot."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.bot import WhispBot, check_whisper_api, resolve_temp_dir
from src.config import load_config
from src.handlers import BotHandlers
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

    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch("builtins.open", create=True) as mock_open,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "test transcription"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

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
    async def test_sets_minimal_mode_false_and_replies(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        await bot._start_command(mock_update, mock_context)

        assert bot.handlers.minimal_mode is False
        mock_update.message.reply_text.assert_awaited_once()


class TestStartMinCommand:
    """Tests for _startmin_command."""

    @pytest.mark.asyncio
    async def test_sets_minimal_mode_true(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_context = MagicMock()

        await bot._startmin_command(mock_update, mock_context)

        assert bot.handlers.minimal_mode is True


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
        mock_context.args = ["en"]

        await bot._lang_command(mock_update, mock_context)

        assert bot.whisper_client.language == "en"
        mock_update.message.reply_text.assert_awaited_once_with("Язык: `en`")

    @pytest.mark.asyncio
    async def test_sets_language_to_none_for_auto(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        bot.whisper_client.set_language("ru")
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["auto"]

        await bot._lang_command(mock_update, mock_context)

        assert bot.whisper_client.language is None
        mock_update.message.reply_text.assert_awaited_once_with("Язык: автораспознавание")

    @pytest.mark.asyncio
    async def test_replies_with_usage_when_no_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
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
        mock_context.args = ["0.5"]

        await bot._temp_command(mock_update, mock_context)

        assert bot.whisper_client.temperature == 0.5
        mock_update.message.reply_text.assert_awaited_once_with("Температура: `0.5`")

    @pytest.mark.asyncio
    async def test_accepts_comma_as_decimal_separator(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["0,3"]

        await bot._temp_command(mock_update, mock_context)

        assert bot.whisper_client.temperature == 0.3

    @pytest.mark.asyncio
    async def test_replies_with_usage_when_no_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
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
        mock_context.args = ["large"]

        await bot._model_command(mock_update, mock_context)

        assert bot.whisper_client.model == "whisper-large-v3"
        mock_update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_switches_to_turbo_alias(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["turbo"]

        await bot._model_command(mock_update, mock_context)

        assert bot.whisper_client.model == "whisper-large-v3-turbo"
        mock_update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_replies_usage_when_no_args(self, mock_config):
        bot = WhispBot(mock_config, FALLBACK_TEMP_DIR)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
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
