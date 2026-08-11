#!/usr/bin/env bash
# Restarts WhispBot: stops the running instance (if any) and starts a fresh
# one in the background. The console is not occupied.
# Runtime counters in run/stats.json are reset by the new process.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/whispbot-env.sh"

# Stop bot if running
if test_bot_running; then
    stop_bot
fi

# Start bot
start_bot
echo "[Bot] Restarted (PID $(get_recorded_bot_pid))."