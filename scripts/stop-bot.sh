#!/usr/bin/env bash
# Stops the running WhispBot and removes run/bot.pid.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/whispbot-env.sh"

stop_bot