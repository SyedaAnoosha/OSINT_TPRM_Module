# The monitoring schedule

`app/monitor.py` is the unit of work. `app/scheduler.py` is the entrypoint. **This directory is the
schedule**, and it is deliberately here rather than in the application: which host runs the sweep,
at what hour, under which credentials, and who gets paged when it stops, are operational decisions,
and burying them in Python would make them invisible to the people who own them.

Pick the one that matches your deployment. All three run the same command.

```
python -m app.scheduler --run
```

## What "installed" means

Adding a timer is half of it. P9 holds **Continuous Monitoring at Reactive** until the *ledger* shows
runs, not until a crontab has a line in it — because the failure mode of a scheduled job is that it
silently stops, and every currency metric on the dashboard keeps rendering as though nothing were
wrong. Verify with:

```
python -m app.scheduler --health      # exits 0 when the schedule is alive, 1 when it is not
```

That command is the one to point your existing host monitoring at. It reads the append-only
`monitor_runs` ledger, and it treats **silence as the alarm condition**: no completed run inside
`HEALTHY_SILENCE_HOURS` (48h) is unhealthy even though nothing has errored.

## Cadence

**Daily**, and the reason is not that vendors change daily.

Under `--by-tier` each relationship carries its own interval from `app/assessment_depth.py`
(quarterly for T1 Critical down to passive for T4 Low), and a finding's own `recheck_after` can pull
any vendor forward to 7 days. The sweep must therefore run far more often than any single vendor's
interval, so that *whichever* relationships come due that day are picked up. A vendor is re-scored
when its own clock says so; the schedule just has to be there when it does.

Vendors that are not due cost nothing — `is_due` is a timestamp comparison, and no collector runs.

## Politeness

Every collector queries someone else's free service. `--by-tier` exists so that budget goes to the
relationships that warrant it: T4 Low is `passive` and is never swept on a cadence at all. Do not
replace this with `--stale-days 1`; that re-scores the whole book daily and is the fastest way to
lose access to a free source.

## Files

| File | Platform |
|---|---|
| `crontab` | Any Unix with cron |
| `osint-tprm-monitor.service` / `.timer` | systemd |
| `Register-MonitorTask.ps1` | Windows Task Scheduler |
| `run-monitor.sh` | Wrapper: activates the venv, loads `.env`, runs the sweep |

`run-monitor.sh` is what all of them invoke, so the environment setup exists in one place.

## Credentials

The sweep needs `DATABASE_URL` and whatever collector keys are configured. `.env` is gitignored and
must stay that way. Under systemd prefer `EnvironmentFile=`; under Windows Task Scheduler the task
runs as a service account whose profile holds the variables. **Do not put a connection string in a
crontab line** — crontabs are world-readable on most hosts.
