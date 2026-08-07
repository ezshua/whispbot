"""Tests for bot message handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.handlers import BotHandlers
from src.user_settings import UserSettings
from src.utils import FALLBACK_TEMP_DIR
from src.whisper_client import WhisperClient


@pytest.fixture
def handlers(mock_config):
    """Create BotHandlers instance with mock config."""
    whisper_client = WhisperClient(mock_config.whisper)
    return BotHandlers(mock_config, whisper_client, FALLBACK_TEMP_DIR)


@pytest.fixture
def mock_audio_message():
    """Create a mock Telegram message with audio."""
    mock = MagicMock()
    mock.from_user.id = 123
    mock.audio = MagicMock()
    mock.audio.file_id = "audio_id"
    mock.audio.file_size = 1024
    mock.caption = None
    return mock


@pytest.fixture
def mock_update(mock_audio_message):
    """Create a mock Telegram update with audio message."""
    mock = MagicMock()
    mock.message = mock_audio_message
    return mock


@pytest.fixture
def mock_context():
    """Create a mock Telegram context with a real user_data dict."""
    mock = MagicMock()
    mock.user_data = {}
    return mock


class TestCheckFileSize:
    """Tests for _check_file_size."""

    @pytest.mark.asyncio
    async def test_accepts_file_within_limit(self, handlers, mock_update):
        result = await handlers._check_file_size(1024, mock_update)
        assert result is True
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_file_exceeding_limit(self, handlers, mock_update):
        oversized = 30 * 1024 * 1024
        mock_update.message.reply_text = AsyncMock()
        result = await handlers._check_file_size(oversized, mock_update)
        assert result is False
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_none_file_size(self, handlers, mock_update):
        result = await handlers._check_file_size(None, mock_update)
        assert result is True
        mock_update.message.reply_text.assert_not_called()


class TestRespond:
    """Tests for _respond."""

    @pytest.mark.asyncio
    async def test_minimal_mode_replies_to_message(self, handlers, mock_update, mock_context):
        mock_update.message.reply_text = AsyncMock()

        await handlers._respond(mock_update, None, "result", minimal_mode=True)

        mock_update.message.reply_text.assert_called_once_with("result")

    @pytest.mark.asyncio
    async def test_normal_mode_edits_listening_message(self, handlers, mock_update, mock_context):
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()

        await handlers._respond(mock_update, mock_listening, "result", minimal_mode=False)

        mock_listening.edit_text.assert_called_once_with("result")


class TestHandleVideo:
    """Tests for handle_video."""

    @pytest.mark.asyncio
    async def test_processes_video_successfully(self, handlers, mock_context, mock_config):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.video = MagicMock()
        mock_message.video.file_id = "video_id"
        mock_message.video.file_size = 2048
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.video.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message
        handlers.whisper_client.transcribe_audio = AsyncMock(return_value="video transcription")

        with patch("src.handlers.extract_audio_from_video", return_value=True):
            await handlers.handle_video(mock_update, mock_context)

        mock_message.reply_text.assert_called_once_with("Слушаю...")
        mock_listening.edit_text.assert_called_once_with("video transcription")

    @pytest.mark.asyncio
    async def test_reports_extraction_error(self, handlers, mock_context, mock_config):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.video = MagicMock()
        mock_message.video.file_id = "video_id"
        mock_message.video.file_size = 2048
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.video.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message

        with patch("src.handlers.extract_audio_from_video", return_value=False):
            await handlers.handle_video(mock_update, mock_context)

        mock_listening.edit_text.assert_called_once()
        assert "не удалось извлечь аудио" in mock_listening.edit_text.call_args[0][0]


class TestHandleVoice:
    """Tests for handle_voice."""

    @pytest.mark.asyncio
    async def test_processes_voice_successfully(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 456
        mock_message.voice = MagicMock()
        mock_message.voice.file_id = "voice_id"
        mock_message.voice.file_size = 512
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.voice.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message
        handlers.whisper_client.transcribe_audio = AsyncMock(return_value="voice transcription")

        with patch("src.handlers.convert_audio_to_wav", return_value=True):
            await handlers.handle_voice(mock_update, mock_context)

        mock_message.reply_text.assert_called_once_with("Слушаю...")
        mock_listening.edit_text.assert_called_once_with("voice transcription")


class TestHandleVideoNote:
    """Tests for handle_video_note."""

    @pytest.mark.asyncio
    async def test_processes_video_note_successfully(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 789
        mock_message.video_note = MagicMock()
        mock_message.video_note.file_id = "note_id"
        mock_message.video_note.file_size = 1024
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.video_note.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message
        handlers.whisper_client.transcribe_audio = AsyncMock(return_value="note transcription")

        with patch("src.handlers.extract_audio_from_video", return_value=True):
            await handlers.handle_video_note(mock_update, mock_context)

        mock_message.reply_text.assert_called_once_with("Слушаю...")
        mock_listening.edit_text.assert_called_once_with("note transcription")


class TestHandleDocument:
    """Tests for handle_document."""

    @pytest.mark.asyncio
    async def test_processes_audio_document(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 111
        mock_message.document = MagicMock()
        mock_message.document.file_id = "doc_id"
        mock_message.document.file_size = 1024
        mock_message.document.file_name = "song.mp3"
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.document.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message
        handlers.whisper_client.transcribe_audio = AsyncMock(return_value="doc transcription")

        with patch("src.handlers.convert_audio_to_wav", return_value=True):
            await handlers.handle_document(mock_update, mock_context)

        mock_message.reply_text.assert_called_once_with("Слушаю...")
        mock_listening.edit_text.assert_called_once_with("doc transcription")

    @pytest.mark.asyncio
    async def test_processes_video_document(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 222
        mock_message.document = MagicMock()
        mock_message.document.file_id = "doc_video_id"
        mock_message.document.file_size = 2048
        mock_message.document.file_name = "clip.mp4"
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.document.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message
        handlers.whisper_client.transcribe_audio = AsyncMock(return_value="video doc transcription")

        with patch("src.handlers.extract_audio_from_video", return_value=True):
            await handlers.handle_document(mock_update, mock_context)

        mock_message.reply_text.assert_called_once_with("Слушаю...")
        mock_listening.edit_text.assert_called_once_with("video doc transcription")

    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.document = MagicMock()
        mock_message.document.file_name = "data.bin"
        mock_message.reply_text = AsyncMock()
        mock_update.message = mock_message

        await handlers.handle_document(mock_update, mock_context)

        mock_message.reply_text.assert_called_once()
        assert "не поддерживается" in mock_message.reply_text.call_args[0][0]


class TestHandlerEdgeCases:
    """Tests for error handling edge cases."""

    @pytest.mark.asyncio
    async def test_file_size_exceeded_returns_early(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.audio = MagicMock()
        mock_message.audio.file_id = "audio_id"
        mock_message.audio.file_size = 50 * 1024 * 1024
        mock_message.reply_text = AsyncMock()
        mock_update.message = mock_message

        await handlers.handle_audio(mock_update, mock_context)

        mock_message.reply_text.assert_called_once()
        assert "слишком большой" in mock_message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_conversion_error_reports_message(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.audio = MagicMock()
        mock_message.audio.file_id = "audio_id"
        mock_message.audio.file_size = 1024
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.audio.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message

        with patch("src.handlers.convert_audio_to_wav", return_value=False):
            await handlers.handle_audio(mock_update, mock_context)

        mock_listening.edit_text.assert_called_once()
        assert "не удалось конвертировать" in mock_listening.edit_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_transcription_error_reports_message(self, handlers, mock_context):
        mock_update = MagicMock()
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.audio = MagicMock()
        mock_message.audio.file_id = "audio_id"
        mock_message.audio.file_size = 1024
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.audio.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        mock_update.message = mock_message

        with patch("src.handlers.convert_audio_to_wav", return_value=True):
            handlers.whisper_client.transcribe_audio = AsyncMock(return_value=None)
            await handlers.handle_audio(mock_update, mock_context)

        mock_listening.edit_text.assert_called_once()
        assert "не удалось транскрибировать" in mock_listening.edit_text.call_args[0][0]


class TestHandlerPerUserSettings:
    """Tests for per-user settings in handlers."""

    def _make_mock_update(self, minimal=False):
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.audio = MagicMock()
        mock_message.audio.file_id = "audio_id"
        mock_message.audio.file_size = 1024
        mock_message.caption = None
        mock_file = MagicMock()
        mock_file.download_to_drive = AsyncMock()
        mock_message.audio.get_file = AsyncMock(return_value=mock_file)
        mock_listening = MagicMock()
        mock_listening.edit_text = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_listening)
        update = MagicMock()
        update.message = mock_message
        return update

    @pytest.mark.asyncio
    async def test_minimal_mode_replies_directly_without_listening(self, handlers, mock_config):
        update = self._make_mock_update()
        context = MagicMock()
        context.user_data = {"settings": UserSettings(minimal_mode=True)}
        handlers.whisper_client.transcribe_audio = AsyncMock(return_value="result")

        with patch("src.handlers.convert_audio_to_wav", return_value=True):
            await handlers.handle_audio(update, context)

        replies = [call.args[0] for call in update.message.reply_text.call_args_list]
        assert replies == ["result"]
        update.message.reply_text.assert_awaited_once_with("result")

    @pytest.mark.asyncio
    async def test_passes_user_settings_to_transcribe(self, handlers, mock_config):
        update = self._make_mock_update()
        context = MagicMock()
        context.user_data = {
            "settings": UserSettings(language="en", temperature=0.3, model="whisper-large-v3-turbo")
        }
        mock_transcribe = AsyncMock(return_value="transcribed")
        handlers.whisper_client.transcribe_audio = mock_transcribe
        handlers.keep_temp_files = True

        with patch("src.handlers.convert_audio_to_wav", return_value=True):
            await handlers.handle_audio(update, context)

        call_kwargs = mock_transcribe.call_args.kwargs
        assert call_kwargs["language"] == "en"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["model"] == "whisper-large-v3-turbo"
