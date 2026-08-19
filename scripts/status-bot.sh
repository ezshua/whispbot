#!/usr/bin/env bash
# Shows the current WhispBot status: process state, uptime, unique users
# connected and the number of processed messages since the last start.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/whispbot-env.sh"

pid=$(get_bot_process)
stats_fields=""
if stats_fields=$(read_stats_fields); then
    read -r started_at users_count messages_processed <<< "${stats_fields}"
else
    started_at=""
    users_count=""
    messages_processed=""
fi

if [[ -n "${pid}" ]]; then
    # Get start time of process (ps -o lstart=)
    start_raw=$(ps -p "${pid}" -o lstart= 2>/dev/null) || start_raw=""
    echo "[Bot] Status     : RUNNING (PID ${pid})"
    if [[ -n "${start_raw}" ]]; then
        echo "[Bot] Started    : ${start_raw}"
    fi
    if [[ -n "${started_at}" && "${started_at}" != "0" ]]; then
        start_date=$(date -d "@${started_at}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null) || start_date="${started_at}"
        now=$(date +%s)
        elapsed=$(( now - started_at ))
        if (( elapsed < 0 )); then elapsed=0; fi
        days=$(( elapsed / 86400 ))
        hours=$(( (elapsed % 86400) / 3600 ))
        minutes=$(( (elapsed % 3600) / 60 ))
        seconds=$(( elapsed % 60 ))
        printf '[Bot] Uptime     : %02d:%02d:%02d:%02d\n' "$days" "$hours" "$minutes" "$seconds"
    fi
    if [[ -n "${users_count}" && "${users_count}" != "0" ]]; then
        echo "[Bot] Users since: ${users_count}"
    fi
    if [[ -n "${messages_processed}" && "${messages_processed}" != "0" ]]; then
        echo "[Bot] Messages   : ${messages_processed}"
    fi
else
    recorded=$(get_recorded_bot_pid)
    if [[ -z "${recorded}" ]]; then
        echo "[Bot] Status     : NOT RUNNING (no PID recorded)"
    else
        echo "[Bot] Status     : NOT RUNNING (PID ${recorded} is gone)"
    fi
    if [[ -n "${started_at}" && "${started_at}" != "0" ]]; then
        start_date=$(date -d "@${started_at}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null) || start_date="${started_at}"
        echo "[Bot] Last start : ${start_date}"
    fi
    if [[ -n "${users_count}" && "${users_count}" != "0" ]]; then
        echo "[Bot] Last users : ${users_count}"
    fi
    if [[ -n "${messages_processed}" && "${messages_processed}" != "0" ]]; then
        echo "[Bot] Last msgs  : ${messages_processed}"
    fi
fi