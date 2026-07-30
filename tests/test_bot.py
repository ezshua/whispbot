"""Tests for WhispBot."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import AppConfig, load_config
from src.handlers import BotHandlers
from src.utils import FALLBACK_TEMP_DIR
from src.whisper_client import WhisperClient


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return AppConfig(
        telegram_bot_token="test_token",
        whisper={"api_base_url": "http://test.com", "api_key": "test_key", "model": "whisper-1"},
        files={
            "max_file_size_mb": 25,
            "temp_dir_path": "temp",
            "allowed_audio_extensions": [".mp3", ".wav", ".m4a"],
            "allowed_video_extensions": [".mp4", ".webm"],
        },
    )


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

    # Mock httpx response and file operations
    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch("builtins.open", create=True) as mock_open,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "test transcription"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Mock file object
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

    # Mock update and context
    mock_update = MagicMock()
    mock_context = MagicMock()

    # Mock message with audio
    mock_message = MagicMock()
    mock_message.from_user.id = 123
    mock_message.audio = MagicMock()
    mock_message.audio.file_id = "test_id"
    mock_message.audio.file_size = 1024

    # Mock get_file to return an async mock
    mock_file = MagicMock()
    mock_file.download_to_drive = AsyncMock()
    mock_message.audio.get_file = AsyncMock(return_value=mock_file)

    # Mock reply_text to return a mock with edit_text
    mock_listening_message = MagicMock()
    mock_listening_message.edit_text = AsyncMock()
    mock_message.reply_text = AsyncMock(return_value=mock_listening_message)
    mock_update.message = mock_message

    # Mock whisper client
    handlers.whisper_client.transcribe_audio = AsyncMock(return_value="test transcription")

    # Call handler
    await handlers.handle_audio(mock_update, mock_context)

    # Verify reply was called
    mock_message.reply_text.assert_called_once_with("Слушаю...")
