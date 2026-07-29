"""Main Telegram bot implementation."""

import logging
from pathlib import Path

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import load_config
from .handlers import BotHandlers
from .utils import FALLBACK_TEMP_DIR, cleanup_temp_dir, ensure_temp_dir
from .whisper_client import WhisperClient

logger = logging.getLogger("src.bot")


class WhispBot:
    """Main Telegram bot class."""

    def __init__(self, config, temp_dir: Path):
        """Initialize the bot.

        Args:
            config: Application configuration
            temp_dir: Temporary files directory
        """
        self.config = config
        self.whisper_client = WhisperClient(self.config.whisper)
        self.handlers = BotHandlers(self.config, self.whisper_client, temp_dir)

    def run(self) -> None:
        """Run the bot."""
        application = (
            Application.builder()
            .token(self.config.telegram_bot_token)
            .build()
        )

        application.add_handler(CommandHandler("start", self._start_command))
        application.add_handler(CommandHandler("help", self._help_command))
        application.add_handler(MessageHandler(filters.AUDIO, self.handlers.handle_audio))
        application.add_handler(MessageHandler(filters.VIDEO, self.handlers.handle_video))
        application.add_handler(MessageHandler(filters.VOICE, self.handlers.handle_voice))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handlers.handle_video_note))
        application.add_handler(MessageHandler(filters.Document.ALL, self.handlers.handle_document))

        logger.info("WhispBot started — awaiting messages")
        application.run_polling(allowed_updates=["message"])

    async def _start_command(self, update, context) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "🎤 Привет! Я WhispBot — бот для транскрибации аудио и видео."
            "\n\nПросто отправьте мне аудио или видео файл, "
            "и я верну текстовое содержимое."
        )

    async def _help_command(self, update, context) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "📝 Как использовать:"
            "\n1. Отправьте аудио файл (MP3, WAV, M4A)"
            "\n2. Или отправьте видео файл (MP4, WEBM)"
            "\n3. Или отправьте документ с поддерживаемым расширением"
            "\n\nПоддерживаемые форматы:"
            f"\nАудио: {', '.join(self.config.files.allowed_audio_extensions)}"
            f"\nВидео: {', '.join(self.config.files.allowed_video_extensions)}"
        )


def check_whisper_api(config) -> None:
    """Check Whisper API availability at startup."""
    import httpx

    url = config.whisper.api_base_url.rstrip("/")
    models_url = f"{url}/models"
    headers = {"Authorization": f"Bearer {config.whisper.api_key}"}

    try:
        resp = httpx.get(models_url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_ids = [m["id"] for m in models]
            model = config.whisper.model
            if model in model_ids:
                logger.info("Whisper API OK — model '%s' available", model)
            else:
                logger.warning("Whisper API reachable, but model '%s' not in list: %s", model, model_ids)
        else:
            logger.warning("Whisper API returned status %s", resp.status_code)
    except httpx.ConnectError:
        logger.warning("Whisper API unreachable at %s", url)
    except Exception as exc:
        logger.warning("Whisper API check failed: %s", exc)


def resolve_temp_dir(config) -> Path:
    """Resolve and prepare temp directory from config.

    Tries configured path first, falls back to local temp/.
    Always cleans both.

    Args:
        config: Application configuration

    Returns:
        Path: Usable temp directory
    """
    configured = Path(config.files.temp_dir_path)

    logger.info("Setting up temp dir: %s", configured)
    temp_dir = ensure_temp_dir(configured)

    # Always clean fallback as well
    cleanup_temp_dir(FALLBACK_TEMP_DIR)

    if temp_dir == configured:
        cleanup_temp_dir(temp_dir)
    else:
        logger.warning("Using fallback temp dir: %s", FALLBACK_TEMP_DIR)
        cleanup_temp_dir(temp_dir)

    logger.info("Temp dir ready: %s", temp_dir)
    return temp_dir


def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("src").setLevel(logging.INFO)

    config = load_config()
    temp_dir = resolve_temp_dir(config)
    check_whisper_api(config)

    bot = WhispBot(config, temp_dir)
    bot.run()


if __name__ == "__main__":
    main()
