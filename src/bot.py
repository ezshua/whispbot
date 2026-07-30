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
from .utils import cleanup_temp_dir, ensure_temp_dir
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
        application = Application.builder().token(self.config.telegram_bot_token).build()

        application.add_handler(CommandHandler("start", self._start_command))
        application.add_handler(CommandHandler("startmin", self._startmin_command))
        application.add_handler(CommandHandler("help", self._help_command))
        application.add_handler(CommandHandler("lang", self._lang_command))
        application.add_handler(CommandHandler("temp", self._temp_command))
        application.add_handler(CommandHandler("model", self._model_command))
        application.add_handler(MessageHandler(filters.AUDIO, self.handlers.handle_audio))
        application.add_handler(MessageHandler(filters.VIDEO, self.handlers.handle_video))
        application.add_handler(MessageHandler(filters.VOICE, self.handlers.handle_voice))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handlers.handle_video_note))
        application.add_handler(MessageHandler(filters.Document.ALL, self.handlers.handle_document))

        logger.info("WhispBot started — awaiting messages")
        application.run_polling(allowed_updates=["message"])

    async def _start_command(self, update, context) -> None:
        """Handle /start command — normal mode (two-phase)."""
        self.handlers.minimal_mode = False
        wc = self.whisper_client
        lang = wc.language or "auto"
        await update.message.reply_text(
            "🎤 Привет! Я WhispBot — бот для транскрибации аудио и видео."
            "\n\nПросто отправьте мне аудио или видео файл, "
            "и я верну текстовое содержимое."
            f"\n\n⚙ Текущие параметры:"
            f"\n• Модель: `{wc.model}`"
            f"\n• Язык: `{lang}`"
            f"\n• Температура: `{wc.temperature}`"
        )

    async def _startmin_command(self, update, context) -> None:
        """Handle /startmin command — minimal mode (single response)."""
        self.handlers.minimal_mode = True

    async def _help_command(self, update, context) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "📝 **Как использовать:**"
            "\n1. Отправьте аудио файл (MP3, WAV, M4A)"
            "\n2. Или отправьте видео файл (MP4, WEBM)"
            "\n3. Или отправьте документ с поддерживаемым расширением"
            "\n\nПоддерживаемые форматы:"
            f"\nАудио: {', '.join(self.config.files.allowed_audio_extensions)}"
            f"\nВидео: {', '.join(self.config.files.allowed_video_extensions)}"
            "\n\n**Команды:**"
            "\n`/start` — обычный режим (двухфазный: «Слушаю...» → текст)"
            "\n`/startmin` — минимальный режим (одно сообщение с результатом)"
            "\n`/help` — эта справка"
            "\n`/lang <код>` — установить язык (ISO-639-1, например `ru`, `en`)"
            "\n`/lang auto` — автораспознавание языка"
            "\n`/temp <0.0–1.0>` — установить температуру модели"
            "\n`/model large` — переключиться на whisper-large-v3"
            "\n`/model turbo` — переключиться на whisper-large-v3-turbo"
        )

    async def _lang_command(self, update, context) -> None:
        """Handle /lang command — set recognition language."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: `/lang <код>` или `/lang auto`\n"
                "Пример: `/lang ru`, `/lang en`, `/lang auto`"
            )
            return

        code = args[0].lower()
        if code == "auto":
            self.whisper_client.set_language(None)
            await update.message.reply_text("Язык: автораспознавание")
        else:
            self.whisper_client.set_language(code)
            await update.message.reply_text(f"Язык: `{code}`")

        logger.info("Language set to %s by user %s", code, update.effective_user.id)

    async def _temp_command(self, update, context) -> None:
        """Handle /temp command — set sampling temperature."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: `/temp <0.0–1.0>`\nПример: `/temp 0.5`"
            )
            return

        raw = args[0].replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            await update.message.reply_text("Ошибка: укажите число от 0 до 1")
            return

        if not 0.0 <= value <= 1.0:
            await update.message.reply_text("Ошибка: температура должна быть от 0 до 1")
            return

        self.whisper_client.set_temperature(value)
        await update.message.reply_text(f"Температура: `{value}`")
        logger.info("Temperature set to %s by user %s", value, update.effective_user.id)

    async def _model_command(self, update, context) -> None:
        """Handle /model command — switch model at runtime."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: `/model large` или `/model turbo`"
            )
            return

        alias = args[0].lower()
        if alias not in ("large", "turbo"):
            await update.message.reply_text(
                "Ошибка: доступные модели — `large` (whisper-large-v3), "
                "`turbo` (whisper-large-v3-turbo)"
            )
            return

        self.whisper_client.set_model(alias)
        await update.message.reply_text(f"Модель: `{self.whisper_client.model}`")
        logger.info("Model switched to %s by user %s", self.whisper_client.model, update.effective_user.id)


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
                logger.warning(
                    "Whisper API reachable, but model '%s' not in list: %s", model, model_ids
                )
        else:
            logger.warning("Whisper API returned status %s", resp.status_code)
    except httpx.ConnectError:
        logger.warning("Whisper API unreachable at %s", url)
    except Exception as exc:
        logger.warning("Whisper API check failed: %s", exc)


def resolve_temp_dir(config) -> Path:
    """Resolve and prepare temp directory from config.

    Tries configured path first, falls back to system TEMP/TMP, then local temp/.

    Args:
        config: Application configuration

    Returns:
        Path: Usable temp directory
    """
    configured = Path(config.files.temp_dir_path)
    logger.info("Setting up temp dir: %s", configured)

    temp_dir = ensure_temp_dir(configured)

    if temp_dir != configured:
        logger.warning(
            "Configured temp dir '%s' not usable, using '%s'", configured, temp_dir.resolve()
        )

    cleanup_temp_dir(temp_dir)
    logger.info("Temp dir ready: %s", temp_dir.resolve())
    return temp_dir


def main() -> None:
    """Main entry point."""
    config = load_config()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("src").setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    temp_dir = resolve_temp_dir(config)
    check_whisper_api(config)

    bot = WhispBot(config, temp_dir)
    bot.run()


if __name__ == "__main__":
    main()
