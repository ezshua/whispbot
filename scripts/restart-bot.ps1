<#
.SYNOPSIS
Restarts WhispBot: stops the running instance (if any) and starts a fresh
one in the background. The console is not occupied.
.DESCRIPTION
Runtime counters in run/stats.json are reset by the new process, so after a
restart the status script reports only the new run.
#>
[CmdletBinding()]
param()

. "$PSScriptRoot\whispbot-env.ps1"

$ErrorActionPreference = "Stop"

try {
    Stop-Bot | Out-Null
}
catch {
    Write-Host "[Bot] ERROR: $($_.Exception.Message)"
    exit 1
}

try {
    Start-Bot | Out-Null
    Write-Host ("[Bot] Restarted (PID {0})." -f (Get-RecordedBotPid))
}
catch {
    Write-Host "[Bot] ERROR: $($_.Exception.Message)"
    exit 1
}