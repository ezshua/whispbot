#!/usr/bin/env bash
# Shared environment and helpers for the WhispBot control scripts.
#
# Source this file from the other scripts in this folder:
#   source "$(dirname "${BASH_SOURCE[0]}")/whispbot-env.sh"

# Exit on error, treat unset variables as errors
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$script_dir")"
rundir="${project_root}/run"
pidfile="${rundir}/bot.pid"
outlog="${rundir}/bot.out.log"
errlog="${rundir}/bot.err.log"
statsfile="${rundir}/stats.json"
# Prefer venv python, else fallback to python3
if [[ -x "${project_root}/.venv/bin/python" ]]; then
    python_exe="${project_root}/.venv/bin/python"
else
    python_exe="python3"
fi

# ── Helpers ────────────────────────────────────────────────────────────

# Returns the PID recorded in run/bot.pid, or empty string if absent/invalid.
get_recorded_bot_pid() {
    if [[ ! -f "${pidfile}" ]]; then
        return
    fi
    local pid
    pid=$(< "${pidfile}")
    # Ensure it's a positive integer
    if [[ "${pid}" =~ ^[0-9]+$ ]] && (( pid > 0 )); then
        echo "${pid}"
    fi
}

# Returns the running bot process PID (via ps), or empty string if not running.
get_bot_process() {
    local pid
    pid=$(get_recorded_bot_pid)
    if [[ -z "${pid}" ]]; then
        return
    fi
    # Check if process with this PID exists and its command looks like our bot
    if ps -p "${pid}" -o cmd= 2>/dev/null | grep -q "\-m src\.bot"; then
        echo "${pid}"
    fi
}

# Returns true (0) when a bot process is currently running.
test_bot_running() {
    get_bot_process >/dev/null 2>&1
}

# Starts the bot in the background and records its PID in run/bot.pid.
# Redirects stdout/stderr to logs.
start_bot() {
    if test_bot_running; then
        local existing
        existing=$(get_bot_process)
        echo "[Bot] Already running (PID ${existing})." >&2
        return 1
    fi
    if [[ ! -f "${project_root}/.env" ]]; then
        echo "[Bot] '.env' not found. Copy .env.example to .env and fill it in." >&2
        return 1
    fi
    if [[ ! -x "${python_exe}" ]]; then
        echo "[Bot] Virtual environment not found (.venv). Run 'uv sync' or ensure python3 is available." >&2
        return 1
    fi
    mkdir -p "${rundir}"
    # Start bot in background, redirect output
    nohup "${python_exe}" -m src.bot >"${outlog}" 2>"${errlog}" &
    local bot_pid=$!
    # Give it a moment to start
    sleep 2
    # Verify it's still running
    if ! ps -p "${bot_pid}" >/dev/null 2>&1; then
        echo "[Bot] Failed to start (exited quickly). Check logs: ${outlog} / ${errlog}" >&2
        return 1
    fi
    echo "${bot_pid}" > "${pidfile}"
    echo "[Bot] Started in background (PID ${bot_pid})."
}

# Stops the running bot (if any) and removes run/bot.pid.
stop_bot() {
    local pid
    pid=$(get_bot_process)
    if [[ -n "${pid}" ]]; then
        echo "[Bot] Stopping bot (PID ${pid})..."
        kill "${pid}" 2>/dev/null || true
        # Wait up to 15 seconds for process to exit
        local deadline=$(( SECONDS + 15 ))
        while (( SECONDS < deadline )) && ps -p "${pid}" >/dev/null 2>&1; do
            sleep 0.2
        done
        if ps -p "${pid}" >/dev/null 2>&1; then
            echo "[Bot] Bot did not exit gracefully, sending SIGKILL..."
            kill -9 "${pid}" 2>/dev/null || true
        fi
        echo "[Bot] Stopped (PID ${pid})."
    else
        echo "[Bot] Not running."
    fi
    rm -f "${pidfile}"
}