"""Tests for Whisper API client."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.whisper_client import WhisperClient


class TestWhisperClientInit:
    """Tests for WhisperClient.__init__."""

    def test_initializes_from_config(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client.base_url == "http://test.com"
        assert client.api_key == "test_key"
        assert client._model == "whisper-1"
        assert client._temperature == 0.0
        assert client._language is None


class TestWhisperClientModel:
    """Tests for model property and set_model."""

    def test_model_property(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client.model == "whisper-1"

    def test_set_model_with_alias(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_model("turbo")
        assert client.model == "whisper-large-v3-turbo"

    def test_set_model_with_full_name(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_model("custom-model")
        assert client.model == "custom-model"


class TestWhisperClientTemperature:
    """Tests for temperature property and set_temperature."""

    def test_temperature_property_default(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client.temperature == 0.0

    def test_set_temperature_valid(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_temperature(0.5)
        assert client.temperature == 0.5

    def test_set_temperature_clamps_below_zero(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_temperature(-0.5)
        assert client.temperature == 0.0

    def test_set_temperature_clamps_above_one(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_temperature(1.5)
        assert client.temperature == 1.0


class TestWhisperClientLanguage:
    """Tests for language property and set_language."""

    def test_language_property_default(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client.language is None

    def test_set_language(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_language("ru")
        assert client.language == "ru"

    def test_set_language_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_language("ru")
        client.set_language(None)
        assert client.language is None


class TestWhisperClientTranscribe:
    """Tests for transcribe method."""

    @pytest.mark.asyncio
    async def test_success(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {"text": "transcribed text"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = await client.transcribe(Path("test.mp3"))
            assert result == "transcribed text"

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=MagicMock()
            )
            mock_post.return_value = mock_response

            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = await client.transcribe(Path("test.mp3"))
            assert result is None

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with (
            patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("connection failed")),
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = await client.transcribe(Path("test.mp3"))
            assert result is None

    @pytest.mark.asyncio
    async def test_generic_exception_returns_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with (
            patch("httpx.AsyncClient.post", side_effect=RuntimeError("unexpected")),
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = await client.transcribe(Path("test.mp3"))
            assert result is None

    @pytest.mark.asyncio
    async def test_sends_language_in_request_data(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_language("ru")
        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {"text": "text"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            await client.transcribe(Path("test.mp3"))
            call_data = mock_post.call_args[1]["data"]
            assert call_data["language"] == "ru"

    @pytest.mark.asyncio
    async def test_uses_per_request_prompt_over_system_prompt(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {"text": "text"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            await client.transcribe(Path("test.mp3"), prompt="per-request prompt")
            call_data = mock_post.call_args[1]["data"]
            assert call_data["prompt"] == "per-request prompt"


class TestWhisperClientTranscribeAudio:
    """Tests for transcribe_audio method."""

    @pytest.mark.asyncio
    async def test_delegates_to_transcribe(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with patch.object(client, "transcribe", AsyncMock(return_value="result")) as mock_transcribe:
            result = await client.transcribe_audio(Path("test.wav"), prompt="test")
            assert result == "result"
            mock_transcribe.assert_awaited_once_with(Path("test.wav"), prompt="test")
