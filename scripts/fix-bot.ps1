<#
.SYNOPSIS
Fixes the PowerShell execution policy so the WhispBot control scripts can run.
.DESCRIPTION
Sets the execution policy to RemoteSigned for the current user only (no
admin rights needed). Idempotent: when the policy is already correct, the
script reports that and exits. Run it once if PowerShell refuses to execute
the scripts in scripts\ (e.g. "running scripts is disabled on this system").
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$current = Get-ExecutionPolicy -Scope CurrentUser

if ($current -eq "RemoteSigned") {
    Write-Host "[Bot] Execution policy is already RemoteSigned for the current user."
    Write-Host "[Bot] Nothing to do - you can run scripts\start-bot.ps1 and friends."
    exit 0
}

try {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    Write-Host ("[Bot] Execution policy changed from {0} to RemoteSigned for the current user." -f $current)
    Write-Host "[Bot] You can now run scripts\start-bot.ps1, scripts\status-bot.ps1, ..."
    exit 0
}
catch {
    Write-Host "[Bot] ERROR: could not change the execution policy in this session."
    Write-Host "[Bot]   - If PowerShell was started with an '-ExecutionPolicy' switch (e.g. by another tool),"
    Write-Host "[Bot]     the policy cannot be changed in-session. Open a plain PowerShell window and run this script again."
    Write-Host "[Bot]   - Otherwise run the command manually in this console:"
    Write-Host "[Bot]       Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
    exit 1
}