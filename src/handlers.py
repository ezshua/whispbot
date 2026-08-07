"""Telegram bot handlers."""

import logging
from pathlib import Path

from telegram import Message, Update
from telegram.ext import ContextTypes

from .config import AppConfig
from .utils import (
    convert_audio_to_wav,
    extract_audio_from_video,
    get_file_extension,
    temp_filename,
)
from .whisper_client import WhisperClient

logger = logging.getLogger(__name__)


class BotHandlers:
    """Handlers for Telegram bot messages."""

    def __init__(self, config: AppConfig, whisper_client: WhisperClient, temp_dir: Path):
        """Initialize bot handlers.

        Args:
            config: Application configuration
            whisper_client: Whisper API client
            temp_dir: Temporary files directory
        """
        self.config = config
        self.whisper_client = whisper_client
        self.temp_dir = temp_dir
        self.max_file_size = config.files.max_file_size_mb * 1024 * 1024
        self.keep_temp_files = config.files.keep_temp_files
        self.minimal_mode = False

    async def _respond(self, update: Update, listening_message, text: str) -> None:
        """Reply or edit depending on minimal_mode.

        Args:
            update: Telegram update object
            listening_message: Message to edit (None in minimal mode)
            text: Text to send
        """
        if self.minimal_mode:
            await update.message.reply_text(text)
        else:
            await listening_message.edit_text(text)

    async def _check_file_size(self, file_size: int | None, update: Update) -> bool:
        """Check if file size is within the allowed limit.

        Args:
            file_size: File size in bytes
            update: Telegram update object (for replying on error)

        Returns:
            bool: True if file size is acceptable
        """
        if file_size is None:
            return True
        if file_size > self.max_file_size:
            await update.message.reply_text(
                f"Файл слишком большой ({file_size / 1024 / 1024:.1f} MB). "
                f"Максимум: {self.config.files.max_file_size_mb} MB."
            )
            return False
        return True

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle audio file messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        message: Message = update.message
        user_id = message.from_user.id
        caption = message.caption

        if not await self._check_file_size(message.audio.file_size, update):
            return

        listening_message = (
            None if self.minimal_mode else await message.reply_text("Слушаю...")
        )

        audio_file = await message.audio.get_file()
        file_path = self.temp_dir / temp_filename(user_id, ".mp3")
        wav_path: Path | None = None

        try:
            await audio_file.download_to_drive(custom_path=str(file_path))

            if file_path.suffix.lower() != ".wav":
                wav_path = file_path.with_suffix(".wav")
                if not convert_audio_to_wav(file_path, wav_path):
                    await self._respond(update, listening_message, "Ошибка: не удалось конвертировать аудио")
                    return
                transcribe_path = wav_path
            else:
                transcribe_path = file_path

            transcription = await self.whisper_client.transcribe_audio(transcribe_path, prompt=caption)

            if transcription:
                await self._respond(update, listening_message, transcription)
            else:
                await self._respond(update, listening_message, "Ошибка: не удалось транскрибировать аудио")

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            await self._respond(update, listening_message, "Ошибка: не удалось обработать аудио")
        finally:
            if not self.keep_temp_files:
                for p in (file_path, wav_path):
                    if p and p.exists():
                        p.unlink()

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle video file messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        message: Message = update.message
        user_id = message.from_user.id
        caption = message.caption

        if not await self._check_file_size(message.video.file_size, update):
            return

        listening_message = (
            None if self.minimal_mode else await message.reply_text("Слушаю...")
        )

        video_file = await message.video.get_file()
        file_path = self.temp_dir / temp_filename(user_id, ".mp4")
        audio_path: Path | None = None

        try:
            await video_file.download_to_drive(custom_path=str(file_path))

            audio_path = file_path.with_suffix(".wav")
            if not extract_audio_from_video(file_path, audio_path):
                await self._respond(update, listening_message, "Ошибка: не удалось извлечь аудио из видео")
                return

            transcription = await self.whisper_client.transcribe_audio(audio_path, prompt=caption)

            if transcription:
                await self._respond(update, listening_message, transcription)
            else:
                await self._respond(update, listening_message, "Ошибка: не удалось транскрибировать видео")

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            await self._respond(update, listening_message, "Ошибка: не удалось обработать видео")
        finally:
            if not self.keep_temp_files:
                for p in (file_path, audio_path):
                    if p and p.exists():
                        p.unlink()

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        message: Message = update.message
        user_id = message.from_user.id
        caption = message.caption

        if not await self._check_file_size(message.voice.file_size, update):
            return

        listening_message = (
            None if self.minimal_mode else await message.reply_text("Слушаю...")
        )

        voice_file = await message.voice.get_file()
        file_path = self.temp_dir / temp_filename(user_id, ".ogg")
        wav_path: Path | None = None

        try:
            await voice_file.download_to_drive(custom_path=str(file_path))

            wav_path = file_path.with_suffix(".wav")
            if not convert_audio_to_wav(file_path, wav_path):
                await self._respond(
                    update, listening_message, "Ошибка: не удалось конвертировать аудиосообщение"
                )
                return

            transcription = await self.whisper_client.transcribe_audio(wav_path, prompt=caption)

            if transcription:
                await self._respond(update, listening_message, transcription)
            else:
                await self._respond(
                    update, listening_message, "Ошибка: не удалось транскрибировать аудиосообщение"
                )

        except Exception as e:
            logger.error(f"Error processing voice: {e}")
            await self._respond(update, listening_message, "Ошибка: не удалось обработать аудиосообщение")
        finally:
            if not self.keep_temp_files:
                for p in (file_path, wav_path):
                    if p and p.exists():
                        p.unlink()

    async def handle_video_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle video note (circle video) messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        message: Message = update.message
        user_id = message.from_user.id
        caption = message.caption

        if not await self._check_file_size(message.video_note.file_size, update):
            return

        listening_message = (
            None if self.minimal_mode else await message.reply_text("Слушаю...")
        )

        video_file = await message.video_note.get_file()
        file_path = self.temp_dir / temp_filename(user_id, ".mp4")
        audio_path: Path | None = None

        try:
            await video_file.download_to_drive(custom_path=str(file_path))

            audio_path = file_path.with_suffix(".wav")
            if not extract_audio_from_video(file_path, audio_path):
                await self._respond(update, listening_message, "Ошибка: не удалось извлечь аудио из кружочка")
                return

            transcription = await self.whisper_client.transcribe_audio(audio_path, prompt=caption)

            if transcription:
                await self._respond(update, listening_message, transcription)
            else:
                await self._respond(update, listening_message, "Ошибка: не удалось транскрибировать кружочек")

        except Exception as e:
            logger.error(f"Error processing video note: {e}")
            await self._respond(update, listening_message, "Ошибка: не удалось обработать кружочек")
        finally:
            if not self.keep_temp_files:
                for p in (file_path, audio_path):
                    if p and p.exists():
                        p.unlink()

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document file messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        message: Message = update.message
        user_id = message.from_user.id
        caption = message.caption

        document = message.document
        file_ext = get_file_extension(Path(document.file_name))

        if not file_ext:
            await message.reply_text("Ошибка: не удалось определить формат файла")
            return

        allowed_extensions = (
            self.config.files.allowed_audio_extensions + self.config.files.allowed_video_extensions
        )

        if file_ext.lower() not in allowed_extensions:
            await message.reply_text(
                f"Ошибка: формат {file_ext} не поддерживается. "
                f"Поддерживаемые форматы: {', '.join(allowed_extensions)}"
            )
            return

        if not await self._check_file_size(document.file_size, update):
            return

        listening_message = (
            None if self.minimal_mode else await message.reply_text("Слушаю...")
        )

        doc_file = await document.get_file()
        file_path = self.temp_dir / temp_filename(user_id, file_ext)

        audio_path = file_path.with_suffix(".wav")

        try:
            await doc_file.download_to_drive(custom_path=str(file_path))

            if file_ext.lower() in self.config.files.allowed_audio_extensions:
                if file_path.suffix.lower() != ".wav":
                    if not convert_audio_to_wav(file_path, audio_path):
                        await self._respond(update, listening_message, "Ошибка: не удалось конвертировать аудио")
                        return
                    transcribe_path = audio_path
                else:
                    transcribe_path = file_path

                transcription = await self.whisper_client.transcribe_audio(
                    transcribe_path, prompt=caption
                )

            elif file_ext.lower() in self.config.files.allowed_video_extensions:
                if not extract_audio_from_video(file_path, audio_path):
                    await self._respond(update, listening_message, "Ошибка: не удалось извлечь аудио из видео")
                    return

                transcription = await self.whisper_client.transcribe_audio(
                    audio_path, prompt=caption
                )

            else:
                transcription = None

            if transcription:
                await self._respond(update, listening_message, transcription)
            else:
                await self._respond(update, listening_message, "Ошибка: не удалось транскрибировать файл")

        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await self._respond(update, listening_message, "Ошибка: не удалось обработать файл")
        finally:
            if not self.keep_temp_files:
                for p in (file_path, audio_path):
                    if p and p.exists():
                        p.unlink()
