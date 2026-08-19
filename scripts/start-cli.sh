#!/usr/bin/env bash
# Starts WhispBot in the foreground, occupying the current console.
# Performs same checks as start-bot.sh but runs the bot directly.

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

# Ensure no bot is running before starting
if test_bot_running; then
    existing=$(get_bot_process)
    echo "[Bot] Found running bot (PID ${existing}). Stopping it..."
    stop_bot
fi

mkdir -p "${rundir}"
echo "[Bot] Starting in foreground - the console is occupied. Ctrl+C to stop."
# Run bot directly; it will create its own pidfile etc.
"${python_exe}" -m src.bot
exit_code=$?
if (( exit_code != 0 )); then
    echo "[Bot] Exited with code ${exit_code}. Logs: ${outlog} / ${errlog}" >&2
    exit ${exit_code}
fi
echo "[Bot] Stopped."