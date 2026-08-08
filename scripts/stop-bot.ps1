<#
.SYNOPSIS
Stops the running WhispBot and removes run/bot.pid.
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