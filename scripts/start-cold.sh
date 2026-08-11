#!/usr/bin/env bash
# Cold start for WhispBot on Ubuntu/Linux: checks/Installs prerequisites, then launches the bot in the foreground.
# Steps:
#   1. Ensure .env exists (copy from .env.example if missing).
#   2. Make all *.sh scripts executable.
#   3. Check Python >=3.10.
#   4. Install uv via pip if not present.
#   5. Run uv sync to set up venv and install dependencies.
#   6. Verify ffmpeg is installed.
#   7. Launch the bot in foreground via start-cli.sh.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$script_dir")"

# Helper functions for output
info() { echo -e "[Bot] \e[36m$*\e[0m"; }
warn() { echo -e "[Bot] \e[33mWARNING: $*\e[0m"; }
error() { echo -e "[Bot] \e[31mERROR: $*\e[0m"; exit 1; }

# 1. .env file
info "Checking for .env file..."
env_path="${project_root}/.env"
env_example="${project_root}/.env.example"
if [[ ! -f "${env_path}" ]]; then
    if [[ -f "${env_example}" ]]; then
        cp "${env_example}" "${env_path}"
        info ".env created from .env.example. Please edit it with your settings before proceeding."
    else
        error ".env.example not found. Cannot create .env."
    fi
else
    info ".env file found."
fi

# 2. Make all helper scripts executable
info "Ensuring all script files are executable..."
chmod +x "${script_dir}"/*.sh

# 3. Python version
info "Checking Python availability..."
# Prefer python3, fallback to python
if command -v python3 >/dev/null 2>&1; then
    py_cmd="python3"
elif command -v python >/dev/null 2>&1; then
    py_cmd="python"
else
    error "Neither python nor python3 found. Please install Python 3.10+."
fi

# Get version
version=$(${py_cmd} --version 2>&1 | grep -oP '(?<=Python )\d+\.\d+' || true)
if [[ -z "${version}" ]]; then
    error "Unable to determine Python version."
fi
# Compare versions (simple lexicographic works for major.minor)
if [[ "$(printf '%s\n' "3.10" "${version}" | sort -V | head -n1)" != "3.10" ]]; then
    error "Python version ${version} is less than required 3.10. Please install Python 3.10 or newer."
fi
info "Found Python ${version} via ${py_cmd}."

# 4. uv installation
info "Checking for uv..."
if command -v uv >/dev/null 2>&1; then
    info "uv is already installed."
else
    info "uv not found. Installing uv via pip..."
    ${py_cmd} -m pip install --upgrade pip
    ${py_cmd} -m pip install uv
    if ! command -v uv >/dev/null 2>&1; then
        error "Failed to install uv. Please install it manually (e.g., pip install uv)."
    fi
    info "uv installed successfully."
fi

# 5. uv sync (install dependencies)
info "Synchronizing dependencies with uv sync..."
uv sync
if [[ $? -ne 0 ]]; then
    error "uv sync failed. See output above."
fi
info "Dependencies synchronized."

# 6. ffmpeg check
info "Checking for ffmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
    error "ffmpeg not found. Please install ffmpeg (e.g., sudo apt install ffmpeg)."
fi
info "ffmpeg found."

# 7. Launch bot in foreground
info "All checks passed. Launching bot in foreground..."
# Use the start-cli script (foreground)
"${script_dir}/start-cli.sh"
exit_code=$?
if [[ ${exit_code} -ne 0 ]]; then
    warn "Bot exited with code ${exit_code}."
fi
exit ${exit_code}