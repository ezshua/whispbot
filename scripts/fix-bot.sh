#!/usr/bin/env bash
# Fixes permissions and checks dependencies for WhispBot control scripts.
# Makes all *.sh scripts in this directory executable.
# Checks for required tools: ffmpeg, uv (or python3-pip), and that .env exists or can be created.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$script_dir")"

echo "[Bot] Making control scripts executable..."
chmod +x "${script_dir}"/*.sh

echo "[Bot] Checking for ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "[Bot] ERROR: ffmpeg not found. Please install ffmpeg (e.g., sudo apt install ffmpeg)." >&2
    exit 1
else
    echo "[Bot] ffmpeg found."
fi

echo "[Bot] Checking for uv (or python3 + pip)..."
if command -v uv &> /dev/null; then
    echo "[Bot] uv found."
elif command -v python3 &> /dev/null && python3 -m pip --version &> /dev/null; then
    echo "[Bot] python3 and pip found (uv not installed, but can use pip)."
else
    echo "[Bot] WARNING: Neither uv nor pip found. You may need to install dependencies manually." >&2
    # Not exiting; maybe user will use system packages
fi

echo "[Bot] Checking for .env file..."
if [[ ! -f "${project_root}/.env" ]]; then
    echo "[Bot] '.env' not found. Please copy .env.example to .env and fill it in."
    echo "[Bot]   cp ${project_root}/.env.example ${project_root}/.env"
else
    echo "[Bot] .env file present."
fi

echo "[Bot] All checks passed."