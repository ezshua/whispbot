<#
.SYNOPSIS
Starts WhispBot in the foreground, occupying the current console (like the
former start.bat).
.DESCRIPTION
Performs the same guards as start-bot.ps1 ('.env', '.venv', duplicate
instance check) but runs "python -m src.bot" directly in this console:
the console is occupied until the bot stops (Ctrl+C) or is killed by
scripts\stop-bot.ps1 / scripts\restart-bot.ps1. The bot registers its own
PID in run/bot.pid and writes runtime statistics, so the other control
scripts see and manage this instance as usual.
#>
[CmdletBinding()]
param()

. "$PSScriptRoot\whispbot-env.ps1"

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath (Join-Path $script:ProjectRoot ".env"))) {
    Write-Host "[Bot] ERROR: '.env' not found. Copy .env.example to .env and fill it in."
    exit 1
}

if (-not (Test-Path -LiteralPath $script:PythonExe)) {
    Write-Host "[Bot] ERROR: virtual environment not found (.venv). Run 'uv sync'."
    exit 1
}

if (Test-BotRunning) {
    $existing = Get-BotProcess
    Write-Host ("[Bot] ERROR: the bot is already running (PID {0})." -f $existing.Id)
    Write-Host "[Bot] Use scripts\status-bot.ps1 to check, scripts\restart-bot.ps1 or scripts\stop-bot.ps1 to manage it."
    exit 1
}

New-Item -ItemType Directory -Force -Path $script:RunDir | Out-Null

Write-Host "[Bot] Starting in foreground - the console is occupied. Ctrl+C to stop."

& $script:PythonExe -m src.bot
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ("[Bot] Exited with code {0}. Logs: {1} / {2}" -f $exitCode, $script:OutLog, $script:ErrLog)
    exit $exitCode
}

Write-Host "[Bot] Stopped."