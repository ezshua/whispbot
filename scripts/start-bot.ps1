<#
.SYNOPSIS
Starts WhispBot in the background without occupying the console.
.DESCRIPTION
Launches "python -m src.bot" in a hidden window, redirects output to
run/bot.out.log (stdout) and run/bot.err.log (stderr), and stores the PID in
run/bot.pid. The current console returns immediately.

If PowerShell blocks execution, allow it once:
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#>
[CmdletBinding()]
param()

. "$PSScriptRoot\whispbot-env.ps1"

$ErrorActionPreference = "Stop"

try {
    Start-Bot | Out-Null
    Write-Host ("[Bot] Started in background (PID {0})." -f (Get-RecordedBotPid))
    Write-Host "[Bot] Logs: $script:RunDir"
    Write-Host "[Bot] Status: run the script status-bot.ps1"
}
catch {
    Write-Host "[Bot] ERROR: $($_.Exception.Message)"
    exit 1
}