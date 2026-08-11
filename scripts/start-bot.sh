#!/usr/bin/env bash
# Starts WhispBot in the background without occupying the console.
# Sources helper functions and starts the bot.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/whispbot-env.sh"

if [[ ! -f "${project_root}/.env" ]]; then
    echo "[Bot] ERROR: '.env' not found. Copy .env.example to .env and fill it in." >&2
    exit 1
fi

if [[ ! -x "${python_exe}" ]]; then
    echo "[Bot] ERROR: Python executable not found at ${python_exe}. Run 'uv sync' or ensure python3 is available." >&2
    exit 1
fi

if test_bot_running; then
    existing=$(get_bot_process)
    echo "[Bot] ERROR: the bot is already running (PID ${existing})." >&2
    echo "[Bot] Use ./status-bot.sh to check, ./restart-bot.sh or ./stop-bot.sh to manage it." >&2
    exit 1
fi

mkdir -p "${rundir}"
start_bot