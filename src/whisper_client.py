"""Whisper API client for transcription."""

import logging
from pathlib import Path

import httpx

from .config import WhisperConfig

logger = logging.getLogger(__name__)


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
        self.model = config.model

    async def transcribe(self, file_path: Path) -> str | None:
        """Transcribe audio file using Whisper API.

        Args:
            file_path: Path to audio file

        Returns:
            Optional[str]: Transcribed text or None if failed
        """
        url = f"{self.base_url}/audio/transcriptions"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(file_path, "rb") as audio_file:
                    files = {"file": (file_path.name, audio_file, "application/octet-stream")}
                    data = {"model": self.model}
                    headers = {"Authorization": f"Bearer {self.api_key}"}

                    response = await client.post(
                        url, files=files, data=data, headers=headers
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

    async def transcribe_audio(self, audio_path: Path) -> str | None:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Optional[str]: Transcribed text or None if failed
        """
        return await self.transcribe(audio_path)
