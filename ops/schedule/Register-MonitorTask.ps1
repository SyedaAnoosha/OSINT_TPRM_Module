<#
.SYNOPSIS
    Registers the OSINT TPRM monitoring sweep with Windows Task Scheduler.

.DESCRIPTION
    The Windows equivalent of the crontab / systemd timer beside this file. Same command, same
    cadence, same argument: `app/scheduler.py` runs once and exits, and the schedule belongs to the
    operating system rather than to the application.

    Registers TWO tasks, and the second is not optional:

      OSINT-TPRM-Monitor        the daily sweep at 03:17
      OSINT-TPRM-MonitorHealth  a check every 6 hours that the sweep is still happening

    The health task exists because the failure mode of a scheduled job is that it silently stops.
    Without it, a dead sweep leaves every currency metric on the dashboard rendering exactly as
    though monitoring were healthy.

.PARAMETER RepoRoot
    Path to the repository root. Defaults to two directories above this script.

.PARAMETER User
    The account to run as. Defaults to the current user. A service account with "Log on as a batch
    job" is the right answer for a server; its profile must hold DATABASE_URL and the collector keys.

.EXAMPLE
    .\Register-MonitorTask.ps1
    python -m app.scheduler --health     # verify: exits 0 when the schedule is alive
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$User = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = "Stop"

$backend = Join-Path $RepoRoot "backend"
$python  = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "No virtualenv at $python. Create it before registering the task — a scheduled task that cannot find its interpreter fails silently every night."
}

# 03:17, not 03:00. Every scheduled task on every host fires on the hour, and this sweep queries a
# dozen free public services that are busiest at exactly that minute. Politeness is how free-source
# access is kept.
$sweepTrigger = New-ScheduledTaskTrigger -Daily -At "03:17"

$sweepAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m app.scheduler --run" `
    -WorkingDirectory $backend

# NO automatic restart on failure. A failed sweep must stay failed and be visible in the ledger. An
# automatic retry against someone else's free service turns one polite failure into a rate-limit ban.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -RestartCount 0 `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "OSINT-TPRM-Monitor" `
    -Description "Daily continuous-monitoring sweep. Each relationship is re-scored on its own P5 interval; vendors not due cost no collector traffic." `
    -Trigger $sweepTrigger `
    -Action $sweepAction `
    -Settings $settings `
    -User $User `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host "Registered OSINT-TPRM-Monitor (daily 03:17)."

# ── the health check ────────────────────────────────────────────────────────────────────────────
# Exits 1 when no run has completed inside the tolerance. SILENCE IS THE ALARM CONDITION: nothing
# errors when a timer dies, which is exactly why a sweep task on its own is not a monitoring practice.
$healthTrigger = New-ScheduledTaskTrigger -Once -At "00:41" `
    -RepetitionInterval (New-TimeSpan -Hours 6) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$healthAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m app.scheduler --health" `
    -WorkingDirectory $backend

Register-ScheduledTask `
    -TaskName "OSINT-TPRM-MonitorHealth" `
    -Description "Is the monitoring sweep still running? Exits 1 on silence. Point host alerting at this task's last result." `
    -Trigger $healthTrigger `
    -Action $healthAction `
    -Settings $settings `
    -User $User `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host "Registered OSINT-TPRM-MonitorHealth (every 6 hours)."
Write-Host ""
Write-Host "Point your host alerting at the LastTaskResult of OSINT-TPRM-MonitorHealth."
Write-Host "A non-zero result means the sweep has stopped, and no other signal will tell you."
