<#
.SYNOPSIS
Shows the current WhispBot status: process state, uptime, unique users
connected and the number of processed messages since the last start.
.DESCRIPTION
Reads run/bot.pid to detect the running process and run/stats.json to show
runtime counters written by the bot itself.
#>
[CmdletBinding()]
param()

. "$PSScriptRoot\whispbot-env.ps1"

$proc = Get-BotProcess

$stats = $null
if (Test-Path -LiteralPath $script:StatsFile) {
    try {
        $raw = Get-Content -LiteralPath $script:StatsFile -Raw -Encoding UTF8
        $stats = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
    }
    catch {
        Write-Warning "Could not parse $($script:StatsFile): $($_.Exception.Message)"
    }
}

if ($null -ne $proc) {
    Write-Host ("[Bot] Status     : RUNNING (PID {0})" -f $proc.Id)
    Write-Host ("[Bot] Started    : {0:yyyy-MM-dd HH:mm:ss}" -f $proc.StartTime.ToLocalTime())

    if ($null -ne $stats) {
        $start = [DateTimeOffset]::FromUnixTimeSeconds([int64]$stats.started_at).LocalDateTime
        $elapsed = (Get-Date) - $start
        if ($elapsed.TotalSeconds -lt 0) { $elapsed = New-TimeSpan 0 }

        $uptime = "{0}d {1:00}:{2:00}:{3:00}" -f `
            $elapsed.Days, $elapsed.Hours, $elapsed.Minutes, $elapsed.Seconds

        Write-Host ("[Bot] Uptime     : {0}" -f $uptime)
        Write-Host ("[Bot] Users since: {0}" -f $stats.users_count)
        Write-Host ("[Bot] Messages   : {0}" -f $stats.messages_processed)
    }
    else {
        Write-Host "[Bot] Stats      : unavailable (stats.json not created yet)"
    }
}
else {
    $recorded = Get-RecordedBotPid
    if ($null -eq $recorded) {
        Write-Host "[Bot] Status     : NOT RUNNING (no PID recorded)"
    }
    else {
        Write-Host ("[Bot] Status     : NOT RUNNING (PID {0} is gone)" -f $recorded)
    }

    if ($null -ne $stats) {
        $lastStart = [DateTimeOffset]::FromUnixTimeSeconds([int64]$stats.started_at).LocalDateTime
        Write-Host ("[Bot] Last start : {0:yyyy-MM-dd HH:mm:ss}" -f $lastStart)
        Write-Host ("[Bot] Last users : {0}" -f $stats.users_count)
        Write-Host ("[Bot] Last msgs  : {0}" -f $stats.messages_processed)
    }
}