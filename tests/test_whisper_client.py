"""Tests for Whisper API client."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.whisper_client import WhisperClient


def _make_mock_http_client(response_text: str = "text") -> MagicMock:
    """Create a mock httpx.AsyncClient with a successful post response."""
    mock_client = MagicMock()
    mock_client.is_closed = False
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": response_text}
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


class TestWhisperClientInit:
    """Tests for WhisperClient.__init__."""

    def test_initializes_from_config(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client.base_url == "http://test.com"
        assert client.api_key == "test_key"
        assert client._model == "whisper-1"
        assert client._temperature == 0.0
        assert client._language is None
        assert client._client is None


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
        client._client = _make_mock_http_client("transcribed text")

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            result = await client.transcribe(Path("test.mp3"))
            assert result == "transcribed text"

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        mock_http.post = AsyncMock(return_value=mock_response)
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            result = await client.transcribe(Path("test.mp3"))
            assert result is None

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            result = await client.transcribe(Path("test.mp3"))
            assert result is None

    @pytest.mark.asyncio
    async def test_generic_exception_returns_none(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_http.post = AsyncMock(side_effect=RuntimeError("unexpected"))
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            result = await client.transcribe(Path("test.mp3"))
            assert result is None

    @pytest.mark.asyncio
    async def test_sends_language_in_request_data(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_language("ru")
        mock_http = _make_mock_http_client()
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            await client.transcribe(Path("test.mp3"))
            call_data = mock_http.post.call_args[1]["data"]
            assert call_data["language"] == "ru"

    @pytest.mark.asyncio
    async def test_uses_per_request_prompt_over_system_prompt(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = _make_mock_http_client()
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            await client.transcribe(Path("test.mp3"), prompt="per-request prompt")
            call_data = mock_http.post.call_args[1]["data"]
            assert call_data["prompt"] == "per-request prompt"


class TestWhisperClientTranscribeAudio:
    """Tests for transcribe_audio method."""

    @pytest.mark.asyncio
    async def test_delegates_to_transcribe(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        with patch.object(
            client, "transcribe", AsyncMock(return_value="result")
        ) as mock_transcribe:
            result = await client.transcribe_audio(Path("test.wav"), prompt="test")
            assert result == "result"
            mock_transcribe.assert_awaited_once_with(
                Path("test.wav"), prompt="test", model=None, temperature=None, language=None
            )


class TestTranscribeOverrides:
    """Tests for per-request overrides in transcribe."""

    @pytest.mark.asyncio
    async def test_uses_per_request_parameters(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = _make_mock_http_client()
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            await client.transcribe(
                Path("test.mp3"),
                model="whisper-large-v3-turbo",
                temperature=0.5,
                language="en",
            )
            call_data = mock_http.post.call_args[1]["data"]
            assert call_data["model"] == "whisper-large-v3-turbo"
            assert call_data["temperature"] == 0.5
            assert call_data["language"] == "en"

    @pytest.mark.asyncio
    async def test_falls_back_to_client_defaults(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client.model != "whisper-large-v3-turbo"
        mock_http = _make_mock_http_client()
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            await client.transcribe(Path("test.mp3"))
            call_data = mock_http.post.call_args[1]["data"]
            assert call_data["model"] == "whisper-1"
            assert call_data["temperature"] == 0.0
            assert "language" not in call_data

    @pytest.mark.asyncio
    async def test_override_model_resolves_back_to_default(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        client.set_language("ru")
        mock_http = _make_mock_http_client()
        client._client = mock_http

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            await client.transcribe(Path("test.mp3"), language=None)
            call_data = mock_http.post.call_args[1]["data"]
            assert call_data["language"] == "ru"


class TestWhisperClientClient:
    """Tests for lazy client property and close."""

    def test_client_creates_httpx_client_lazily(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        assert client._client is None
        http_client = client.client
        assert isinstance(http_client, httpx.AsyncClient)
        assert client._client is http_client

    def test_client_reuses_existing(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        first = client.client
        second = client.client
        assert first is second

    @pytest.mark.asyncio
    async def test_close_closes_client(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_http.aclose = AsyncMock()
        client._client = mock_http

        await client.close()
        mock_http.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        await client.close()

    @pytest.mark.asyncio
    async def test_close_noop_when_already_closed(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = MagicMock()
        mock_http.is_closed = True
        client._client = mock_http

        await client.close()

    def test_client_recreates_after_close(self, mock_config):
        client = WhisperClient(mock_config.whisper)
        mock_http = MagicMock()
        mock_http.is_closed = True
        client._client = mock_http

        new_client = client.client
        assert new_client is not mock_http
        assert isinstance(new_client, httpx.AsyncClient)
