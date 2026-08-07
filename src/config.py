"""Configuration management for Whispbot."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WhisperConfig:
    """Configuration for Whisper API."""

    def __init__(self, api_base_url: str, api_key: str, model: str, prompt: str = ""):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.model = model
        self.prompt = prompt


class FileConfig:
    """Configuration for file processing."""

    def __init__(
        self,
        max_file_size_mb: int,
        allowed_audio_extensions: list[str],
        allowed_video_extensions: list[str],
        temp_dir_path: str,
        keep_temp_files: bool = False,
    ):
        self.max_file_size_mb = max_file_size_mb
        self.allowed_audio_extensions = allowed_audio_extensions
        self.allowed_video_extensions = allowed_video_extensions
        self.temp_dir_path = temp_dir_path
        self.keep_temp_files = keep_temp_files


class AppConfig(BaseSettings):
    """Main application configuration."""

    telegram_bot_token: str = Field(..., description="Telegram bot token")
    whisper_api_base_url: str = Field(..., description="Base URL for Whisper API")
    whisper_api_key: str = Field(..., description="API key for Whisper service")
    whisper_model: str = Field(..., description="Whisper model identifier")
    whisper_prompt: str = Field("", description="Optional system prompt for Whisper model")
    files_max_file_size_mb: int = Field(25, description="Maximum file size in MB")
    files_temp_dir_path: str = Field("temp", description="Path to temporary files directory")
    files_allowed_audio_extensions: str = Field(
        ".mp3,.wav,.m4a,.flac,.aac,.opus,.ogg,.wma,.aiff",
        description="Allowed audio file extensions (comma-separated)",
    )
    files_allowed_video_extensions: str = Field(
        ".mp4,.webm,.mkv,.mov,.avi,.flv,.m4v,.3gp,.ts",
        description="Allowed video file extensions (comma-separated)",
    )
    files_keep_temp_files: bool = Field(False, description="Keep temp files after transcription")
    access_allowed_users_file: str = Field(
        "allowed_users.txt",
        description="Path to allowed users list file (first line = admin)",
    )
    access_ignored_users_file: str = Field(
        "ignored_users.txt",
        description="Path to ignored users list file",
    )
    log_level: str = Field("INFO", description="Logging level for the app (DEBUG, INFO, WARNING, ERROR)")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def whisper(self) -> WhisperConfig:
        """Get Whisper configuration."""
        return WhisperConfig(
            api_base_url=self.whisper_api_base_url,
            api_key=self.whisper_api_key,
            model=self.whisper_model,
            prompt=self.whisper_prompt,
        )

    @property
    def files(self) -> FileConfig:
        """Get file processing configuration."""
        return FileConfig(
            max_file_size_mb=self.files_max_file_size_mb,
            temp_dir_path=self.files_temp_dir_path,
            keep_temp_files=self.files_keep_temp_files,
            allowed_audio_extensions=[
                ext.strip() for ext in self.files_allowed_audio_extensions.split(",")
            ],
            allowed_video_extensions=[
                ext.strip() for ext in self.files_allowed_video_extensions.split(",")
            ],
        )


def load_config() -> AppConfig:
    """Load configuration from environment variables.

    Returns:
        AppConfig: Loaded application configuration
    """
    return AppConfig()
