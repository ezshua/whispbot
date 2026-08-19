"""Main Telegram bot implementation."""

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from .access_control import MAX_PENDING_MESSAGES, AccessManager, parse_user_args
from .config import load_config
from .handlers import BotHandlers
from .stats import DEFAULT_PID_FILE, DEFAULT_STATS_FILE, Stats, clear_pid_file, write_pid_file
from .user_settings import get_user_settings
from .utils import cleanup_temp_dir, ensure_temp_dir
from .whisper_client import MODEL_ALIASES, WhisperClient

logger = logging.getLogger("src.bot")

ACCESS_DENIED_TEXT = (
    "⚠️ Доступ ограничен: вас нет в списке разрешённых пользователей.\n"
    "Отправлять можно только текстовые и голосовые сообщения — "
    "они будут переданы администратору бота.\n"
    "Осталось сообщений администратору: {remaining}."
)


class NonAllowedUserFilter(filters.UpdateFilter):
    """Match messages from users not present in the allowed list.

    Subclasses UpdateFilter (not BaseFilter): BaseFilter.check_update only
    checks the update type and never calls filter(), which would make the
    gatekeeper consume every message including those from allowed users.
    """

    def __init__(self, access: AccessManager) -> None:
        """Initialize the filter.

        Args:
            access: User access manager
        """
        super().__init__()
        self.access = access

    def filter(self, update: Update) -> bool:
        user = update.effective_user
        if user is None:
            return False
        return not self.access.is_allowed(user.id)


class WhispBot:
    """Main Telegram bot class."""

    def __init__(
        self,
        config,
        temp_dir: Path,
        access: AccessManager | None = None,
        stats: Stats | None = None,
    ):
        """Initialize the bot.

        Args:
            config: Application configuration
            temp_dir: Temporary files directory
            access: Optional user access manager (enables the gatekeeper)
            stats: Optional runtime statistics collector (enables message counting)
        """
        self.config = config
        self.access = access
        self.stats = stats
        self.whisper_client = WhisperClient(self.config.whisper)
        self.handlers = BotHandlers(self.config, self.whisper_client, temp_dir)

    def run(self) -> None:
        """Run the bot."""
        application = Application.builder().token(self.config.telegram_bot_token).build()

        if self.access is not None:
            application.add_handler(CommandHandler("adduser", self._adduser_command))
            application.add_handler(CommandHandler("deluser", self._deluser_command))
            application.add_handler(CommandHandler("listuser", self._listuser_command))
            application.add_handler(
                MessageHandler(NonAllowedUserFilter(self.access), self._gatekeeper)
            )
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
        if self.stats is not None:
            application.add_handler(MessageHandler(filters.ALL, self._stats_collector), group=1)
        application.add_error_handler(self._error_handler)
        application.post_init = self._on_post_init
        application.post_shutdown = self._on_shutdown

        logger.info("WhispBot started — awaiting messages")
        application.run_polling(allowed_updates=["message"])

    async def _stats_collector(self, update: Update, context) -> None:
        """Record every incoming message for the status report.

        Registered in a separate handler group, so it runs after the main
        handler(s) regardless of which one processed the update.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        user = update.effective_user
        if user is not None:
            self.stats.record_message(user.id)

    async def _on_post_init(self, application) -> None:
        """Notify the admin that the bot is ready and awaiting messages.

        Sent once the Telegram Application is fully initialised and polling
        has started, so the admin can be sure the bot is reachable.

        Args:
            application: The Telegram Application instance
        """
        if self.access is None or self.access.admin_id is None:
            logger.warning("Admin ID is not set — startup notification skipped")
            return
        try:
            await application.bot.send_message(
                chat_id=self.access.admin_id,
                text=(
                    "🎙️ *WhispBot запущен и готов к работе!*\n\n"
                    "Бот успешно стартовал и слушает входящие сообщения. "
                    "Отправьте аудио или видео — и получите расшифровку."
                ),
                parse_mode="Markdown",
            )
            logger.info("Startup notification sent to admin %s", self.access.admin_id)
        except Exception as exc:
            logger.warning("Failed to send startup notification to admin: %s", exc)

    async def _on_shutdown(self, application) -> None:
        """Clean up resources on shutdown."""
        await self.whisper_client.close()
        clear_pid_file(DEFAULT_PID_FILE)

    async def _error_handler(self, update, context) -> None:
        """Log unhandled exceptions from handlers."""
        logger.error("Unhandled exception: %s", context.error, exc_info=context.error)

    async def _gatekeeper(self, update: Update, context) -> None:
        """Handle messages from users who are not in the allowed list.

        Forwards text and voice messages to the admin and counts pending
        requests. Users are silently ignored if they are in the ignored list.
        After MAX_PENDING_MESSAGES requests the user is added to the ignored
        list and the admin is notified.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        user = update.effective_user
        message = update.message
        if user is None or message is None or self.access is None:
            return
        if self.access.is_allowed(user.id) or self.access.is_ignored(user.id):
            return

        if message.text is None and message.voice is None:
            await message.reply_text(
                ACCESS_DENIED_TEXT.format(
                    remaining=MAX_PENDING_MESSAGES - self.access.pending_count(user.id)
                )
            )
            return

        if self.access.admin_id is None:
            await message.reply_text(
                "К сожалению, запрос не может быть отправлен администратору бота."
            )
            return

        await context.bot.send_message(
            chat_id=self.access.admin_id,
            text=f"👤 Пользователь {user.full_name} ({user.id}) хочет подключиться к боту:",
        )
        await message.forward(chat_id=self.access.admin_id)
        count = self.access.record_pending(user.id, user.full_name or "unknown")

        if count >= MAX_PENDING_MESSAGES:
            await message.reply_text(
                f"Ваш запрос передан администратору, но это было последнее "
                f"({MAX_PENDING_MESSAGES}) сообщение — вы добавлены в список игнорируемых."
            )
            await context.bot.send_message(
                chat_id=self.access.admin_id,
                text=f"Пользователь {user.full_name} ({user.id}) добавлен в список игнорируемых.",
            )
        else:
            await message.reply_text(
                f"✅ Запрос передан администратору. "
                f"Осталось сообщений администратору: {MAX_PENDING_MESSAGES - count}."
            )
        logger.info("Pending request forwarded from user %s", user.id)

    async def _adduser_command(self, update: Update, context) -> None:
        """Handle /adduser command — admin only.

        Adds a user to the allowed list and removes them from the ignored
        list. Invocations from non-admin users are silently ignored.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        user = update.effective_user
        if user is None or self.access is None or user.id != self.access.admin_id:
            return

        user_id, name = parse_user_args(" ".join(context.args))
        if user_id is None:
            await update.message.reply_text("Использование: `/adduser <идентификатор> [имя]`")
            return

        was_ignored = self.access.is_ignored(user_id)
        added = self.access.add_allowed(user_id, name)

        display = f"{name} ({user_id})" if name else f"{user_id}"
        if added:
            text = f"✅ Пользователь {display} добавлен в список разрешённых."
        else:
            text = f"ℹ️ Пользователь {display} уже в списке разрешённых."
        if was_ignored:
            text += " Удалён из списка игнорируемых."
        await update.message.reply_text(text)
        logger.info("adduser: user %s added by admin %s", user_id, user.id)

    async def _deluser_command(self, update: Update, context) -> None:
        """Handle /deluser command — admin only.

        Moves a user from the allowed list to the ignored list. Invocations
        from non-admin users are silently ignored.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        user = update.effective_user
        if user is None or self.access is None or user.id != self.access.admin_id:
            return

        user_id, _ = parse_user_args(" ".join(context.args))
        if user_id is None:
            await update.message.reply_text("Использование: `/deluser <идентификатор>`")
            return

        if user_id == self.access.admin_id:
            await update.message.reply_text("Ошибка: нельзя удалить администратора.")
            return

        if self.access.del_allowed(user_id):
            await update.message.reply_text(
                f"✅ Пользователь {user_id} перемещён в список игнорируемых."
            )
        else:
            await update.message.reply_text(
                f"Ошибка: пользователь {user_id} не в списке разрешённых."
            )
        logger.info("deluser: user %s moved by admin %s", user_id, user.id)

    async def _listuser_command(self, update: Update, context) -> None:
        """Handle /listuser command — admin only.

        Sends two separate messages to the admin: first the allowed users
        list, then the ignored users list. Invocations from non-admin users
        are silently ignored.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        user = update.effective_user
        if user is None or self.access is None or user.id != self.access.admin_id:
            return

        allowed_text = self.access.format_allowed() or "Список пуст"
        await update.message.reply_text(f"📋 Разрешённые пользователи:\n{allowed_text}")

        ignored_text = self.access.format_ignored() or "Список пуст"
        await update.message.reply_text(f"⛔ Игнорируемые пользователи:\n{ignored_text}")
        logger.info("listuser: lists sent to admin %s", user.id)

    async def _start_command(self, update, context) -> None:
        """Handle /start command — normal mode (two-phase).

        Switches the user to the two-phase response mode and shows their
        current individual settings, so they can recall them at any time.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        settings = get_user_settings(context)
        settings.minimal_mode = False

        model = settings.model or self.whisper_client.model
        lang = settings.language or "auto"
        await update.message.reply_text(
            "🎤 Привет! Я WhispBot — бот для транскрибации аудио и видео."
            "\n\nПросто отправьте мне аудио или видео файл, "
            "и я верну текстовое содержимое."
            "\n\n⚙ Ваши текущие параметры:"
            f"\n• Модель: `{model}`"
            f"\n• Язык: `{lang}`"
            f"\n• Температура: `{settings.temperature}`"
            "\n\nНастройки можно менять командами `/lang`, `/temp`, `/model`, "
            "`/startmin`. Индивидуальные настройки хранятся в памяти бота."
        )

    async def _startmin_command(self, update, context) -> None:
        """Handle /startmin command — minimal mode (single response).

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        get_user_settings(context).minimal_mode = True
        await update.message.reply_text(
            "⚡ Минимальный режим: результат придёт одним сообщением.\n"
            "Команда `/start` вернёт обычный режим и покажет ваши настройки."
        )

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
            " и показ ваших текущих настроек"
            "\n`/startmin` — минимальный режим (одно сообщение с результатом)"
            "\n`/help` — эта справка"
            "\n`/lang <код>` — установить язык (ISO-639-1, например `ru`, `en`)"
            "\n`/lang auto` — автораспознавание языка"
            "\n`/temp <0.0–1.0>` — установить температуру модели"
            "\n`/model large` — переключиться на whisper-large-v3"
            "\n`/model turbo` — переключиться на whisper-large-v3-turbo"
            "\n\nНастройки индивидуальны для каждого пользователя "
            "и действуют до перезапуска бота."
            "\n`/adduser <id> [имя]` — добавить пользователя в список разрешённых "
            "(только для администратора)"
            "\n`/deluser <id>` — переместить пользователя в список игнорируемых "
            "(только для администратора)"
            "\n`/listuser` — показать списки разрешённых и игнорируемых "
            "(только для администратора)"
        )

    async def _lang_command(self, update, context) -> None:
        """Handle /lang command — set the user's recognition language."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: `/lang <код>` или `/lang auto`\n"
                "Пример: `/lang ru`, `/lang en`, `/lang auto`"
            )
            return

        settings = get_user_settings(context)
        code = args[0].lower()
        if code == "auto":
            settings.language = None
            await update.message.reply_text("Язык: автораспознавание")
        else:
            settings.language = code
            await update.message.reply_text(f"Язык: `{code}`")

        logger.info("Language set to %s by user %s", code, update.effective_user.id)

    async def _temp_command(self, update, context) -> None:
        """Handle /temp command — set sampling temperature."""
        args = context.args
        if not args:
            await update.message.reply_text("Использование: `/temp <0.0–1.0>`\nПример: `/temp 0.5`")
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

        get_user_settings(context).temperature = value
        await update.message.reply_text(f"Температура: `{value}`")
        logger.info("Temperature set to %s by user %s", value, update.effective_user.id)

    async def _model_command(self, update, context) -> None:
        """Handle /model command — switch model at runtime."""
        args = context.args
        if not args:
            await update.message.reply_text("Использование: `/model large` или `/model turbo`")
            return

        alias = args[0].lower()
        if alias not in ("large", "turbo"):
            await update.message.reply_text(
                "Ошибка: доступные модели — `large` (whisper-large-v3), "
                "`turbo` (whisper-large-v3-turbo)"
            )
            return

        get_user_settings(context).model = MODEL_ALIASES.get(alias, alias)
        await update.message.reply_text(f"Модель: `{MODEL_ALIASES[alias]}`")
        logger.info(
            "Model switched to %s by user %s", MODEL_ALIASES[alias], update.effective_user.id
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

    stats = Stats(DEFAULT_STATS_FILE)
    stats.reset()
    pid = write_pid_file(DEFAULT_PID_FILE)
    logger.info("Runtime state: pid=%s stats=%s", pid, DEFAULT_STATS_FILE)

    access = AccessManager(
        Path(config.access_allowed_users_file),
        Path(config.access_ignored_users_file),
    )
    bot = WhispBot(config, temp_dir, access, stats=stats)
    bot.run()


if __name__ == "__main__":
    main()
