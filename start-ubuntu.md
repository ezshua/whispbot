# Запуск WhispBot на Ubuntu

Инструкция по развертыванию бота от имени обычного пользователя (без root-прав).

---

## 1. Подготовка сервера (только один раз, от root)

Зайдите на сервер под пользователем с правами sudo, установите необходимые пакеты, создайте пользователя `skuch` и разрешите ему запускать службы в фоне:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git ffmpeg
sudo adduser skuch
sudo loginctl enable-linger skuch
```

*(`enable-linger` гарантирует, что системные службы пользователя `skuch` будут запускаться при старте сервера, даже если пользователь не авторизован).*

---

## 2. Переключение на пользователя `skuch`

```bash
sudo su - skuch
```

---

## 3. Клонирование проекта и настройка окружения

```bash
git clone <repository-url> ~/whispbot
cd ~/whispbot
python3 -m venv .venv
source .venv/bin/activate
pip install python-telegram-bot python-dotenv httpx pydantic pydantic-settings
```

*Если на сервере установлен `uv`, можно использовать его вместо pip:*

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

---

## 4. Создание конфигурационного файла `.env`

Скопируйте шаблон и заполните недостающие значения:

```bash
cp .env.example .env
nano .env
```

**Обязательные переменные для заполнения:**

| Переменная | Описание | Пример |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather | `1234567890:ABC...` |
| `WHISPER_API_BASE_URL` | Базовый URL Whisper API | `http://localhost:8000/v1` |
| `WHISPER_API_KEY` | API-ключ | `your_api_key_here` |
| `WHISPER_MODEL` | Модель | `whisper-1` |

**Опциональные переменные** (можно оставить значения по умолчанию):

| Переменная | По умолчание | Описание |
|---|---|---|
| `WHISPER_PROMPT` | `""` | Системный промпт для модели |
| `FILES_MAX_FILE_SIZE_MB` | `25` | Максимальный размер файла |
| `FILES_TEMP_DIR_PATH` | `temp` | Путь к временной папке |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

---

## 5. Настройка списков пользователей

Создайте файлы разрешённых и игнорируемых пользователей:

```bash
nano ~/whispbot/allowed_users.txt
nano ~/whispbot/ignored_users.txt
```

**Формат строки:** `<user_id>; <имя или комментарий>`

**Важно:** Первая строка в `allowed_users.txt` — администратор бота. Ему будут приходить запросы от незарегистрированных пользователей.

Пример `allowed_users.txt`:
```
123456789; Алексей (администратор)
987654321; Иван Иванов
```

---

## 6. Создание systemd-службы

Создайте директорию для пользовательских служб и файл service:

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/whispbot.service
```

**Содержимое файла:**

```ini
[Unit]
Description=WhispBot Telegram Bot (User skuch)
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/whispbot
EnvironmentFile=%h/whispbot/.env
ExecStart=%h/whispbot/.venv/bin/python -m src.bot
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=default.target
```

**Пояснение параметров:**

| Параметр | Значение | Почему |
|---|---|---|
| `WorkingDirectory` | `%h/whispbot` | `%h` = домашняя директория `skuch`, бот найдёт `temp/`, `run/`, `.env` по относительным путям |
| `EnvironmentFile` | `%h/whispbot/.env` | Явно указываем путь к `.env`, так как `pydantic-settings` сам не ищет его в рабочей директории при запуске через systemd |
| `ExecStart` | `-m src.bot` | Точка входа — модуль `src/bot.py` с функцией `main()` |
| `Restart=always` | Всегда | Перезапускать бота при любом выходе (краш, ошибка, плановая остановка) |
| `RestartSec=10` | 10 секунд | Пауза перед перезапуском |
| `StartLimitIntervalSec` / `StartLimitBurst` | 300с / 5 | Ограничение на частые перезапуски — если бот падает больше 5 раз за 5 минут, systemd остановит его и не будет бесконечно перезагружать |

---

## 7. Запуск бота

```bash
systemctl --user daemon-reload
systemctl --user enable whispbot
systemctl --user start whispbot
```

- **`enable`** — включает автозапуск при старте сервера (работает только при включённом `linger`).
- **`start`** — запускает бота здесь и сейчас.

---

## 8. Проверка статуса

```bash
systemctl --user status whispbot
```

Полезные команды управления:

```bash
systemctl --user stop whispbot     # остановить
systemctl --user restart whispbot  # перезапуск
systemctl --user disable whispbot  # отключить автозапуск
journalctl --user -u whispbot -f  # следить за логами в реальном времени
```

---

## 9. Логи бота

Бот пишет логи в консоль, systemd перехватывает их. Для просмотра:

```bash
journalctl --user -u whispbot --since "1 hour ago"
```

Дополнительно бот создаёт файлы в папке `run/`:
- `run/bot.pid` — PID процесса
- `run/stats.json` — статистика (количество пользователей, обработанных сообщений)
- `run/bot.out.log` / `run/bot.err.log` — stdout/stderr (только при запуске через скрипты, не через systemd)

---

## Итоговая таблица

| Действие | Команда |
|---|---|
| Установить зависимости | `pip install python-telegram-bot python-dotenv httpx pydantic pydantic-settings` |
| Создать `.env` | `cp .env.example .env && nano .env` |
| Создать списки пользователей | `nano allowed_users.txt` |
| Создать службу | `nano ~/.config/systemd/user/whispbot.service` |
| Запустить | `systemctl --user start whispbot` |
| Проверить | `systemctl --user status whispbot` |
| Автозапуск | `systemctl --user enable whispbot` |