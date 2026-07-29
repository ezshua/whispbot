# WhispBot

Telegram-бот для транскрибации аудио и видео в текст через Whisper API (OpenAI-совместимый).

## Требования

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) (менеджер пакетов)
- [ffmpeg](https://ffmpeg.org/) (конвертация аудио)

## Установка

```bash
git clone <repo>
cd whispbot
uv sync
```

## Настройка

Скопировать `.env.example` в `.env` и заполнить (в редакторе, не через консоль):

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `WHISPER_API_BASE_URL` | Адрес Whisper API (напр. `http://localhost:8000/v1`) |
| `WHISPER_API_KEY` | API-ключ |
| `WHISPER_MODEL` | Модель (напр. `whisper-1`) |
| `FILES_MAX_FILE_SIZE_MB` | Максимальный размер файла (по умолч. 25) |
| `FILES_ALLOWED_AUDIO_EXTENSIONS` | Разрешённые аудиоформаты |
| `FILES_ALLOWED_VIDEO_EXTENSIONS` | Разрешённые видеоформаты |

## Запуск

```bash
.venv\Scripts\activate
python -m src.bot
```

Либо двойным кликом на `start.bat`.

Остановка: `Ctrl+C`.

## Использование

Отправьте боту аудио (MP3, WAV, M4A) или видео (MP4, WEBM) — он ответит текстовой расшифровкой.

Команды:
- `/start` — приветствие
- `/help` — справка
