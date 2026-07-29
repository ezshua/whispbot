@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".env" (
    echo [ERROR] .env not found.
    echo Copy .env.example to .env and fill in your settings.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run: uv sync
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m src.bot
if errorlevel 1 pause
