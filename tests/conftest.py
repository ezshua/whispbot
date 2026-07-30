"""Shared fixtures and configuration for tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.config import AppConfig


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return AppConfig(
        telegram_bot_token="test_token",
        whisper_api_base_url="http://test.com",
        whisper_api_key="test_key",
        whisper_model="whisper-1",
        files_max_file_size_mb=25,
        files_temp_dir_path="temp",
        files_allowed_audio_extensions=".mp3,.wav,.m4a",
        files_allowed_video_extensions=".mp4,.webm",
    )
