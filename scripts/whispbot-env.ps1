# Shared environment and helpers for the WhispBot control scripts.
#
# Dot-source this module from the other scripts in this folder:
#   . "$PSScriptRoot\whispbot-env.ps1"
#
# Run once if PowerShell refuses to execute scripts:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# ── Paths ──────────────────────────────────────────────────────────────
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:RunDir      = Join-Path $script:ProjectRoot "run"
$script:PidFile     = Join-Path $script:RunDir "bot.pid"
$script:OutLog      = Join-Path $script:RunDir "bot.out.log"
$script:ErrLog      = Join-Path $script:RunDir "bot.err.log"
$script:StatsFile   = Join-Path $script:RunDir "stats.json"
$script:PythonExe   = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"

# ── Helpers ────────────────────────────────────────────────────────────

<#
.SYNOPSIS
Returns the PID recorded in run/bot.pid, or $null when absent/invalid.
#>
function Get-RecordedBotPid {
    if (-not (Test-Path -LiteralPath $script:PidFile)) { return $null }
    $raw = Get-Content -LiteralPath $script:PidFile -Raw -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    $value = 0L
    if ([long]::TryParse($raw.Trim(), [ref]$value) -and $value -gt 0) { return $value }
    return $null
}

<#
.SYNOPSIS
Returns the running bot process object, or $null when it is not running.
#>
function Get-BotProcess {
    $botPid = Get-RecordedBotPid
    if ($null -eq $botPid) { return $null }
    return Get-Process -Id $botPid -ErrorAction SilentlyContinue
}

<#
.SYNOPSIS
Returns $true when a bot process is currently running.
#>
function Test-BotRunning {
    return $null -ne (Get-BotProcess)
}

<#
.SYNOPSIS
Starts the bot in the background and records its PID in run/bot.pid.
.DESCRIPTION
Uses Start-Process with a hidden window and redirects stdout/stderr to
run/bot.out.log and run/bot.err.log, so the current console returns at once.
Returns the Process object on success; throws otherwise.
#>
function Start-Bot {
    if (Test-BotRunning) {
        $existing = Get-BotProcess
        throw ("[Bot] Already running (PID {0})." -f $existing.Id)
    }
    if (-not (Test-Path -LiteralPath (Join-Path $script:ProjectRoot ".env"))) {
        throw "[Bot] '.env' not found. Copy .env.example to .env and fill it in."
    }
    if (-not (Test-Path -LiteralPath $script:PythonExe)) {
        throw "[Bot] Virtual environment not found (.venv). Run 'uv sync'."
    }

    New-Item -ItemType Directory -Force -Path $script:RunDir | Out-Null

    $proc = Start-Process -FilePath $script:PythonExe `
        -ArgumentList @("-m", "src.bot") `
        -WorkingDirectory $script:ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $script:OutLog `
        -RedirectStandardError $script:ErrLog `
        -PassThru

    Start-Sleep -Milliseconds 2000
    if ($proc.HasExited) {
        throw ("[Bot] Exited with code {0}. Check the log: {1}" -f $proc.ExitCode, $script:ErrLog)
    }

    Set-Content -LiteralPath $script:PidFile -Value $proc.Id -Encoding ascii
    return $proc
}

<#
.SYNOPSIS
Stops the running bot (if any) and removes run/bot.pid.
.DESCRIPTION
Returns $true once the process is gone.
#>
function Stop-Bot {
    $proc = Get-BotProcess
    if ($null -ne $proc) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $deadline = (Get-Date).AddSeconds(15)
        while ((Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 200
        }
        Write-Host ("[Bot] Stopped (PID {0})." -f $proc.Id)
    } else {
        Write-Host "[Bot] Not running."
    }
    if (Test-Path -LiteralPath $script:PidFile) {
        Remove-Item -LiteralPath $script:PidFile -Force
    }
    return $true
}