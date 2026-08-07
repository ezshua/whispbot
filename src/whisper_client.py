"""Whisper API client for transcription."""

import logging
from pathlib import Path

import httpx

from .config import WhisperConfig

logger = logging.getLogger(__name__)

# Default model parameters — can be overridden for fine-tuning
TEMPERATURE: float = 0.0
LANGUAGE: str | None = None
RESPONSE_FORMAT: str = "json"
TIMESTAMP_GRANULARITIES: list[str] | None = None

MODEL_ALIASES: dict[str, str] = {
    "large": "whisper-large-v3",
    "turbo": "whisper-large-v3-turbo",
}


class WhisperClient:
    """Client for interacting with Whisper API."""

    def __init__(self, config: WhisperConfig):
        """Initialize Whisper client.

        Args:
            config: Whisper configuration
        """
        self.config = config
        self.base_url = config.api_base_url.rstrip("/")
        self.api_key = config.api_key
        self.prompt = config.prompt
        self._model = config.model
        self._temperature = TEMPERATURE
        self._language = LANGUAGE
        self._client: httpx.AsyncClient | None = None

    @property
    def model(self) -> str:
        """Current model name."""
        return self._model

    def set_model(self, name: str) -> None:
        """Switch model at runtime. Accepts alias ('large', 'turbo') or full name.

        Args:
            name: Model name or alias
        """
        self._model = MODEL_ALIASES.get(name, name)

    @property
    def temperature(self) -> float:
        """Current temperature value."""
        return self._temperature

    def set_temperature(self, value: float) -> None:
        """Set sampling temperature (0.0–1.0).

        Args:
            value: Temperature value
        """
        self._temperature = max(0.0, min(1.0, value))

    @property
    def language(self) -> str | None:
        """Current language code or None for auto-detect."""
        return self._language

    def set_language(self, code: str | None) -> None:
        """Set language (ISO-639-1) or None for auto-detect.

        Args:
            code: Language code (e.g. 'ru', 'en') or None
        """
        self._language = code

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client, reused across requests."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client if open."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def transcribe(self, file_path: Path, prompt: str | None = None) -> str | None:
        """Transcribe audio file using Whisper API.

        Args:
            file_path: Path to audio file
            prompt: Optional per-request prompt; falls back to system prompt if not set

        Returns:
            Optional[str]: Transcribed text or None if failed
        """
        url = f"{self.base_url}/audio/transcriptions"
        active_prompt = prompt or self.prompt

        data: dict = {
            "model": self._model,
            "temperature": self._temperature,
            "response_format": RESPONSE_FORMAT,
        }
        if self._language:
            data["language"] = self._language
        if TIMESTAMP_GRANULARITIES:
            data["timestamp_granularities"] = TIMESTAMP_GRANULARITIES
        if active_prompt:
            data["prompt"] = active_prompt

        logger.debug(
            "Whisper request: url=%s model=%s file=%s prompt=%s temperature=%s "
            "language=%s timestamp_granularities=%s",
            url, self._model, file_path.name, active_prompt,
            self._temperature, self._language, TIMESTAMP_GRANULARITIES,
        )

        try:
            with open(file_path, "rb") as audio_file:
                files = {"file": (file_path.name, audio_file, "application/octet-stream")}
                headers = {"Authorization": f"Bearer {self.api_key}"}

                response = await self.client.post(url, files=files, data=data, headers=headers)

                logger.debug(
                    "Whisper response: status=%s body=%s", response.status_code, response.text
                )

                response.raise_for_status()

                result = response.json()
                return result.get("text")

        except httpx.HTTPStatusError as e:
            logger.error(f"Whisper API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return None

    async def transcribe_audio(self, audio_path: Path, prompt: str | None = None) -> str | None:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file
            prompt: Optional per-request prompt; falls back to system prompt if not set

        Returns:
            Optional[str]: Transcribed text or None if failed
        """
        return await self.transcribe(audio_path, prompt=prompt)
