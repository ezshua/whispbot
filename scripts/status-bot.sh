#!/usr/bin/env bash
# Shows the current WhispBot status: process state, uptime, unique users
# connected and the number of processed messages since the last start.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/whispbot-env.sh"

pid=$(get_bot_process)
stats=()
if [[ -f "${statsfile}" ]]; then
    # Read JSON with jq if available, else fallback to python
    if command -v jq &> /dev/null; then
        stats=$(jq -c . "${statsfile}" 2>/dev/null) || true
    elif python3 -c "import json,sys; print(json.load(open('${statsfile}')))" 2>/dev/null; then
        stats=$(python3 -c "import json,sys; print(json.load(open('${statsfile}')))" 2>/dev/null) || true
    fi
fi

if [[ -n "${pid}" ]]; then
    # Get start time of process (ps -o lstart=)
    start_raw=$(ps -p "${pid}" -o lstart= 2>/dev/null) || start_raw=""
    echo "[Bot] Status     : RUNNING (PID ${pid})"
    if [[ -n "${start_raw}" ]]; then
        echo "[Bot] Started    : ${start_raw}"
    fi
    if [[ -n "${stats}" ]]; then
        # Extract fields using jq or python
        if command -v jq &> /dev/null; then
            started_at=$(echo "${stats}" | jq -r '.started_at // empty')
            users_count=$(echo "${stats}" | jq -r '.users_count // empty')
            messages_processed=$(echo "${stats}" | jq -r '.messages_processed // empty')
        else
            started_at=$(python3 -c "import json,sys; d=json.load(open('${statsfile}')); print(d.get('started_at',''))" 2>/dev/null)
            users_count=$(python3 -c "import json,sys; d=json.load(open('${statsfile}')); print(d.get('users_count',''))" 2>/dev/null)
            messages_processed=$(python3 -c "import json,sys; d=json.load(open('${statsfile}')); print(d.get('messages_processed',''))" 2>/dev/null)
        fi
        if [[ -n "${started_at}" && "${started_at}" != "null" ]]; then
            # Convert started_at (likely Unix timestamp) to date
            start_date=$(date -d @"${started_at}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null) || start_date="${started_at}"
            now=$(date +%s)
            elapsed=$(( now - started_at ))
            if (( elapsed < 0 )); then elapsed=0; fi
            days=$(( elapsed / 86400 ))
            hours=$(( (elapsed % 86400) / 3600 ))
            minutes=$(( (elapsed % 3600) / 60 ))
            seconds=$(( elapsed % 60 ))
            printf '[Bot] Uptime     : %02d:%02d:%02d:%02d\n' "$days" "$hours" "$minutes" "$seconds"
        fi
        if [[ -n "${users_count}" && "${users_count}" != "null" ]]; then
            echo "[Bot] Users since: ${users_count}"
        fi
        if [[ -n "${messages_processed}" && "${messages_processed}" != "null" ]]; then
            echo "[Bot] Messages   : ${messages_processed}"
        fi
    else
        echo "[Bot] Stats      : unavailable (stats.json not created yet)"
    fi
else
    recorded=$(get_recorded_bot_pid)
    if [[ -z "${recorded}" ]]; then
        echo "[Bot] Status     : NOT RUNNING (no PID recorded)"
    else
        echo "[Bot] Status     : NOT RUNNING (PID ${recorded} is gone)"
    fi
    if [[ -n "${stats}" ]]; then
        if command -v jq &> /dev/null; then
            started_at=$(echo "${stats}" | jq -r '.started_at // empty')
            users_count=$(echo "${stats}" | jq -r '.users_count // empty')
            messages_processed=$(echo "${stats}" | jq -r '.messages_processed // empty')
        else
            started_at=$(python3 -c "import json,sys; d=json.load(open('${statsfile}')); print(d.get('started_at',''))" 2>/dev/null)
            users_count=$(python3 -c "import json,sys; d=json.load(open('${statsfile}')); print(d.get('users_count',''))" 2>/dev/null)
            messages_processed=$(python3 -c "import json,sys; d=json.load(open('${statsfile}')); print(d.get('messages_processed',''))" 2>/dev/null)
        fi
        if [[ -n "${started_at}" && "${started_at}" != "null" ]]; then
            start_date=$(date -d @"${started_at}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null) || start_date="${started_at}"
            echo "[Bot] Last start : ${start_date}"
        fi
        if [[ -n "${users_count}" && "${users_count}" != "null" ]]; then
            echo "[Bot] Last users : ${users_count}"
        fi
        if [[ -n "${messages_processed}" && "${messages_processed}" != "null" ]]; then
            echo "[Bot] Last msgs  : ${messages_processed}"
        fi
    fi
fi