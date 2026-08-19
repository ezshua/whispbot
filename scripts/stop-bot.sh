#!/usr/bin/env bash
# Stops the running WhispBot and removes run/bot.pid.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/whispbot-env.sh"

# Stop bot if running
stop_bot

# Remove PID file if it exists
if [[ -f "${pidfile}" ]]; then
    rm -f "${pidfile}"
    echo "[Bot] Removed PID file."
fi