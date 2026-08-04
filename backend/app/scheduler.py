"""The scheduled entrypoint — what an OS timer invokes, and the ledger proving it did.

WHAT THIS IS NOT, AND THE ARGUMENT IS STILL `monitor.py`'S. This is **not a daemon**. There is no
event loop, no `while True`, no in-process timer. `monitor.py` is right that a long-lived scheduler
is a deployment concern and that encoding one in the app would bury an operational decision in code
— so the schedule itself lives in `ops/schedule/`, as a cron entry, a systemd timer and a Windows
Scheduled Task, and this module is what those invoke. It runs once and exits.

═══ WHY A NEW MODULE AT ALL, RATHER THAN JUST A CRON LINE ═══

P9 held Continuous Monitoring at **Reactive** on the grounds that `monitor --by-tier` exists and
nothing schedules it. Adding a cron entry alone would close the letter of that and none of its
substance, because **the failure mode of a scheduled job is not that it errors — it is that it
silently stops**. A crashed timer, a rotated credential, a container that stopped being deployed:
all of them leave every downstream number rendering exactly as though monitoring were healthy, and
`monitoring_currency` would keep reporting 100% precisely because nothing was being re-scored into
staleness. "We monitor continuously" then becomes the most confident false claim in the programme.

So this module does three things a cron line cannot:

  1. **Writes a run ledger.** Two append-only events per run — `started`, then `finished` or
     `failed`. A run that dies leaves an orphan `started`, which is a visible state rather than a
     forgotten one.
  2. **Reports monitoring HEALTH separately from vendor currency.** `monitoring_health()` answers
     "is the schedule alive", which no vendor-level metric can. Silence is the alarm condition.
  3. **Exits non-zero on failure**, so the OS scheduler's own alerting — the one already watching
     every other timer on the host — fires without a second notification path to maintain.

═══ WHAT IT DOES NOT DECIDE ═══

Which vendors are due, at what depth, and how often is entirely P5's answer, read through
`monitor.monitor(by_tier=True)`. This module chooses nothing about risk. If it did, there would be
two places that decide a cadence and they would drift.

USAGE
    python -m app.scheduler --run                 # the scheduled unit of work (by tier)
    python -m app.scheduler --run --dry-run       # what would re-score, spending nothing
    python -m app.scheduler --health              # is the schedule alive? exits 1 if not
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from .logging_config import get_logger, setup_logging
from .models import utcnow

log = get_logger("scheduler")

Trigger = Literal["scheduled", "manual", "dry_run"]
RunEvent = Literal["started", "finished", "failed"]

#: How long the ledger may be silent before monitoring is considered UNHEALTHY.
#:
#: Derived from P5's shortest interval rather than picked: the tightest cadence any relationship can
#: carry is quarterly (90 days) for T1 Critical, but the finding clock can pull a vendor forward to
#: 7 days, so the SCHEDULE has to run far more often than any single vendor's interval. A daily
#: timer with a two-day tolerance means one missed run is a hiccup and two is an alarm — short
#: enough to catch a dead timer within a working day, long enough not to page somebody over a
#: reboot.
HEALTHY_SILENCE_HOURS = 48


@dataclass
class MonitorRunEvent:
    """One append-only row in the run ledger."""

    run_id: str
    event: RunEvent
    trigger: Trigger
    mode: str
    considered: int = 0
    rescored: int = 0
    drifted: int = 0
    failed: int = 0
    duration_secs: float | None = None
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: Any = field(default_factory=utcnow)


async def run_once(store: Any, *, trigger: Trigger = "scheduled", by_tier: bool = True,
                   stale_days: int = 7, dry_run: bool = False) -> dict[str, Any]:
    """One scheduled sweep, bracketed by ledger events. Returns the run summary.

    THE LEDGER IS WRITTEN EVEN WHEN THE SWEEP RAISES. That is the point of the try/finally: an
    exception that goes unrecorded is a run that, to every reader afterwards, simply never happened
    — and a monitoring practice whose failures are invisible is worse than one that is honestly
    absent, because it is believed.

    A DRY RUN IS LEDGERED TOO, tagged `dry_run`, and `monitoring_health` does not count it as a
    live run. Recording it keeps "somebody checked what would happen" in the history; excluding it
    from health stops a habit of dry runs from reading as a working schedule.
    """
    from .monitor import monitor

    run_id = str(uuid.uuid4())
    mode = "by_tier" if by_tier else f"stale_days={stale_days}"
    effective_trigger: Trigger = "dry_run" if dry_run else trigger
    started = utcnow()

    store.put_monitor_run(MonitorRunEvent(
        run_id=run_id, event="started", trigger=effective_trigger, mode=mode,
        detail={"stale_days": stale_days, "by_tier": by_tier, "dry_run": dry_run},
    ))

    try:
        drifts = await monitor(stale_days=stale_days, only_ref=None, dry_run=dry_run,
                              by_tier=by_tier)
    except Exception as exc:  # noqa: BLE001 — recorded, then re-raised for the OS scheduler
        store.put_monitor_run(MonitorRunEvent(
            run_id=run_id, event="failed", trigger=effective_trigger, mode=mode,
            duration_secs=(utcnow() - started).total_seconds(),
            error=f"{type(exc).__name__}: {exc}", detail={},
        ))
        log.exception("scheduled monitor run failed")
        raise

    # COUNTED FROM THE STATED ACTION, never inferred from the postures. `monitor` returns a Drift
    # for every vendor it CONSIDERED, including the ones its tier interval said to skip — and a
    # skipped vendor carries its previous posture in both slots, so it is arithmetically identical
    # to one re-scored to the same number. The first sweep ledgered 126 re-scores against a true
    # figure of 20 before `Drift.action` existed.
    rescored = [d for d in drifts if d.action in ("rescored", "would_rescore")]
    skipped = [d for d in drifts if d.action == "skipped"]
    drifted = [d for d in drifts if d.action == "rescored" and d.delta not in (None, 0)]
    failed = [d for d in drifts if d.action == "error"]
    summary = {
        "run_id": run_id,
        "trigger": effective_trigger,
        "mode": mode,
        "considered": len(drifts),
        "rescored": len(rescored),
        "skipped": len(skipped),
        "drifted": len(drifted),
        "failed": len(failed),
        "duration_secs": round((utcnow() - started).total_seconds(), 1),
        # The drift is the reason anyone reads this. Kept on the run rather than only in a log line,
        # because P9's Continuous Monitoring dimension asks for "drift reports retained" and a log
        # that rotates is not a retained report.
        "drift": [
            {"ref": d.ref, "old": d.old_posture, "new": d.new_posture, "delta": d.delta,
             "tier": d.tier, "depth": d.depth, "note": d.note}
            for d in sorted(drifted, key=lambda x: abs(x.delta or 0), reverse=True)[:50]
        ],
    }
    store.put_monitor_run(MonitorRunEvent(
        run_id=run_id, event="finished", trigger=effective_trigger, mode=mode,
        considered=len(drifts), rescored=len(rescored), drifted=len(drifted), failed=len(failed),
        duration_secs=summary["duration_secs"], detail=summary,
    ))
    return summary


def monitoring_health(store: Any) -> dict[str, Any]:
    """Is the schedule alive? A question no vendor-level metric can answer.

    THE ALARM CONDITION IS SILENCE, not error. `monitoring_currency` reports the share of vendors
    inside their P5 interval, and if the monitor stops running that number does not fall — it stays
    wherever it was and then slowly, plausibly decays, which is indistinguishable from a book that
    happens to be current. Reading the LEDGER instead makes a dead timer look like a dead timer.

    Dry runs are recorded but do not count as live runs: a habit of checking what would happen is
    not the same as anything happening.
    """
    rows = store.monitor_runs(limit=200)
    live = [r for r in rows if r["trigger"] != "dry_run"]
    finished = [r for r in live if r["event"] == "finished"]
    failures = [r for r in live if r["event"] == "failed"]

    if not finished:
        return {
            "healthy": False,
            "reason": ("The monitor has NEVER completed a scheduled run. `--by-tier` and the P5 "
                       "cadence table both exist; nothing has invoked them. Install the schedule "
                       "from `ops/schedule/` — until then this programme's monitoring is "
                       "on-demand, whatever the cadence table says."),
            "last_run_at": None, "runs_recorded": len(rows), "failures": len(failures),
        }

    last = finished[0]
    silent = utcnow() - last["created_at"]
    healthy = silent <= timedelta(hours=HEALTHY_SILENCE_HOURS)
    started_ids = {r["run_id"] for r in live if r["event"] == "started"}
    closed_ids = {r["run_id"] for r in live if r["event"] in ("finished", "failed")}
    orphans = started_ids - closed_ids
    # A failure AFTER the last success means the schedule is firing and breaking, which is a
    # different problem from silence and must not read as healthy just because a run completed once.
    failed_since_success = bool(failures) and failures[0]["created_at"] > last["created_at"]

    return {
        "healthy": healthy and not failed_since_success,
        "reason": (
            f"The most recent run FAILED: {failures[0]['error']}. A schedule that fires and breaks "
            f"is not a monitoring practice."
            if failed_since_success else
            f"Last completed run {round(silent.total_seconds() / 3600, 1)}h ago, within the "
            f"{HEALTHY_SILENCE_HOURS}h tolerance."
            if healthy else
            f"NO COMPLETED RUN IN {round(silent.total_seconds() / 3600, 1)}h — the tolerance is "
            f"{HEALTHY_SILENCE_HOURS}h. The schedule is not firing, and every currency metric on "
            f"this dashboard is describing a book nothing is refreshing."
        ),
        "last_run_at": last["created_at"].isoformat(),
        "last_run": {"considered": last["considered"], "rescored": last["rescored"],
                     "drifted": last["drifted"], "failed": last["failed"],
                     "duration_secs": last["duration_secs"]},
        "silence_hours": round(silent.total_seconds() / 3600, 1),
        "tolerance_hours": HEALTHY_SILENCE_HOURS,
        "runs_recorded": len(rows),
        "completed_runs": len(finished),
        "failures": len(failures),
        # A run that started and never closed. Reported because a status column would have
        # overwritten it on the next success and lost the fact that anything died at all.
        "incomplete_runs": sorted(orphans),
    }


def recent_runs(store: Any, limit: int = 10) -> list[dict[str, Any]]:
    """Completed runs, newest first, with their drift — the retained report P9 asks for."""
    out = []
    for row in store.monitor_runs(limit=limit * 4):
        if row["event"] != "finished":
            continue
        detail = json.loads(row["detail_json"]) if row["detail_json"] else {}
        out.append({
            "run_id": row["run_id"], "at": row["created_at"].isoformat(),
            "trigger": row["trigger"], "mode": row["mode"],
            "considered": row["considered"], "rescored": row["rescored"],
            "drifted": row["drifted"], "failed": row["failed"],
            "duration_secs": row["duration_secs"], "drift": detail.get("drift", []),
        })
        if len(out) >= limit:
            break
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="The scheduled monitor entrypoint. Runs once.")
    parser.add_argument("--run", action="store_true", help="perform the scheduled sweep")
    parser.add_argument("--health", action="store_true",
                        help="is the schedule alive? exits 1 when it is not")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would re-score without spending any collector budget")
    parser.add_argument("--stale-days", type=int, default=7,
                        help="fallback cutoff when --no-by-tier is used")
    parser.add_argument("--no-by-tier", action="store_true",
                        help="use one staleness cutoff for the whole book instead of P5's "
                             "per-relationship intervals. Not recommended: it is the behaviour "
                             "P5 replaced.")
    parser.add_argument("--trigger", choices=["scheduled", "manual"], default="scheduled")
    args = parser.parse_args()
    setup_logging()

    from .storage import get_store

    store = get_store()

    if args.health:
        health = monitoring_health(store)
        print(json.dumps(health, indent=2, default=str))
        sys.exit(0 if health["healthy"] else 1)

    if not args.run:
        parser.error("nothing to do — pass --run or --health")

    summary = asyncio.run(run_once(
        store, trigger=args.trigger, by_tier=not args.no_by_tier,
        stale_days=args.stale_days, dry_run=args.dry_run,
    ))
    print(json.dumps(summary, indent=2, default=str))
    # Non-zero when the sweep completed but individual vendors failed to re-score, so the OS
    # scheduler's existing alerting is the notification path and there is not a second one to
    # maintain. A partial failure is not a healthy run.
    sys.exit(1 if summary["failed"] else 0)


if __name__ == "__main__":
    main()
