"""The scheduled entrypoint and the ledger that makes "we monitor continuously" checkable.

THE CLAIM THIS FILE DEFENDS. P9 held Continuous Monitoring at Reactive because `monitor --by-tier`
exists and nothing schedules it. Adding a cron entry closes the letter of that and none of its
substance, because **the failure mode of a scheduled job is not that it errors — it is that it
silently stops**, and every downstream currency figure keeps rendering as though it had not. So the
tests here are mostly about the ways a dead schedule must NOT look alive:

  * a run that dies leaves an orphan `started` and is never overwritten by the next success
  * a dry run is recorded but is not a live run
  * silence past the tolerance is unhealthy even though nothing errored
  * a failure after the last success is unhealthy even though a run once completed

Plus the counting bug the first live sweep produced: `monitor` returns a Drift for every vendor it
CONSIDERED, and the ledger reported 126 re-scores against a true figure of 20.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app import scheduler
from app.models import utcnow
from app.monitor import Drift


class _Ledger:
    """An append-only ledger. UPDATE and DELETE raise, exactly as the Postgres triggers do — an
    operator who can edit run history can make a monitoring practice look continuous after the
    fact, and the whole value of the ledger is that they cannot."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def put_monitor_run(self, event):
        self.rows.append({
            "id": event.id, "run_id": event.run_id, "event": event.event,
            "trigger": event.trigger, "mode": event.mode, "considered": event.considered,
            "rescored": event.rescored, "drifted": event.drifted, "failed": event.failed,
            "duration_secs": event.duration_secs, "error": event.error,
            "detail_json": __import__("json").dumps(event.detail), "created_at": event.created_at,
        })
        return event.id

    def monitor_runs(self, limit=50):
        return sorted(self.rows, key=lambda r: r["created_at"], reverse=True)[:limit]


def _row(event, *, trigger="scheduled", hours_ago=0.0, run_id="r1", error=None, **kw):
    base = {"id": f"{run_id}-{event}", "run_id": run_id, "event": event, "trigger": trigger,
            "mode": "by_tier", "considered": 0, "rescored": 0, "drifted": 0, "failed": 0,
            "duration_secs": 1.0, "error": error, "detail_json": "{}",
            "created_at": utcnow() - timedelta(hours=hours_ago)}
    base.update(kw)
    return base


# ════════════════════════════════════════════════════ this is not a daemon


def test_the_scheduler_contains_no_event_loop_of_its_own():
    """`monitor.py`'s argument stands and this module must not quietly overturn it: a long-lived
    scheduler is a deployment concern, and encoding one here would bury an operational decision in
    code. The schedule lives in `ops/schedule/`."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("app/scheduler.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            assert not (isinstance(node.test, ast.Constant) and node.test.value is True), \
                "a `while True` in the scheduler is a daemon, which is the thing this is not"
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "sleep" not in called, "a scheduler that sleeps is keeping its own time"


def test_the_schedule_artefacts_exist_outside_the_application():
    from pathlib import Path

    ops = Path("../ops/schedule")
    for name in ("README.md", "crontab", "osint-tprm-monitor.service",
                 "osint-tprm-monitor.timer", "Register-MonitorTask.ps1", "run-monitor.sh"):
        assert (ops / name).exists(), f"ops/schedule/{name} is missing — the schedule is the artefact"


def test_the_cron_entry_does_not_fire_on_the_hour():
    """Every scheduled job on every host lands on :00, and this sweep queries a dozen free public
    services that are all being hit hardest at exactly that minute. Politeness is how free-source
    access is kept."""
    from pathlib import Path

    lines = [ln for ln in Path("../ops/schedule/crontab").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert lines
    for line in lines:
        minute = line.split()[0]
        assert minute not in ("0", "00", "30"), f"{minute!r} is the minute everyone else picked"


# ════════════════════════════════════════════════════ the ledger


def test_a_healthy_run_writes_exactly_two_events(monkeypatch):
    ledger = _Ledger()
    monkeypatch.setattr("app.monitor.monitor",
                        lambda **kw: asyncio.sleep(0, result=[]))
    asyncio.run(scheduler.run_once(ledger, trigger="scheduled"))
    assert [r["event"] for r in sorted(ledger.rows, key=lambda r: r["created_at"])] == \
        ["started", "finished"]


def test_a_run_that_raises_is_ledgered_and_then_re_raised(monkeypatch):
    """AN EXCEPTION THAT GOES UNRECORDED IS A RUN THAT NEVER HAPPENED to every reader afterwards,
    and a monitoring practice whose failures are invisible is worse than one honestly absent —
    because it is believed. Re-raised so the OS scheduler's own alerting fires."""
    ledger = _Ledger()

    async def _boom(**kw):
        raise RuntimeError("database went away")

    monkeypatch.setattr("app.monitor.monitor", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(scheduler.run_once(ledger))

    events = [r["event"] for r in sorted(ledger.rows, key=lambda r: r["created_at"])]
    assert events == ["started", "failed"]
    assert "database went away" in ledger.rows[-1]["error"]


def test_counts_come_from_the_stated_action_and_never_from_the_postures(monkeypatch):
    """THE BUG THE FIRST LIVE SWEEP PRODUCED. `monitor` returns a Drift for every vendor it
    CONSIDERED, including the ones its tier interval said to skip — and a skipped vendor carries
    its previous posture in both slots, so it is arithmetically identical to one re-scored to the
    same number. The ledger read 126 re-scores against a true figure of 20."""
    drifts = [
        Drift("a", 80, 80, "B", "B", note="skipped — not due", action="skipped"),
        Drift("b", 80, 80, "B", "B", note="", action="rescored"),          # same number, real run
        Drift("c", 80, 61, "B", "C", note="", action="rescored"),
        Drift("d", 80, None, "B", None, note="ERROR", action="error"),
    ]
    ledger = _Ledger()
    monkeypatch.setattr("app.monitor.monitor", lambda **kw: asyncio.sleep(0, result=drifts))
    out = asyncio.run(scheduler.run_once(ledger))

    assert out["considered"] == 4
    assert out["rescored"] == 2, "the skipped vendor is not a re-score"
    assert out["skipped"] == 1
    assert out["drifted"] == 1, "an unchanged posture is not drift"
    assert out["failed"] == 1


def test_drift_is_retained_on_the_run_rather_than_only_logged(monkeypatch):
    """P9's Continuous Monitoring dimension asks for "drift reports retained". A log line that
    rotates is not a retained report."""
    drifts = [Drift("a", 90, 40, "A", "F", action="rescored")]
    ledger = _Ledger()
    monkeypatch.setattr("app.monitor.monitor", lambda **kw: asyncio.sleep(0, result=drifts))
    asyncio.run(scheduler.run_once(ledger))

    runs = scheduler.recent_runs(ledger)
    assert runs[0]["drift"][0] == {"ref": "a", "old": 90, "new": 40, "delta": -50,
                                   "tier": None, "depth": None, "note": ""}


# ════════════════════════════════════════════════════ health: silence is the alarm


def test_a_book_with_no_runs_at_all_is_unhealthy_and_says_what_to_install():
    h = scheduler.monitoring_health(_Ledger())
    assert h["healthy"] is False
    assert "NEVER completed" in h["reason"] and "ops/schedule" in h["reason"]


def test_silence_past_the_tolerance_is_unhealthy_even_though_nothing_errored():
    """THE FAILURE THIS WHOLE MODULE EXISTS FOR. Nothing errors when a timer dies, and
    `monitoring_currency` does not fall — it decays slowly and plausibly, which is
    indistinguishable from a book that happens to be current."""
    ledger = _Ledger([_row("started", hours_ago=100), _row("finished", hours_ago=100)])
    h = scheduler.monitoring_health(ledger)
    assert h["healthy"] is False
    assert "NO COMPLETED RUN" in h["reason"]
    assert h["silence_hours"] > scheduler.HEALTHY_SILENCE_HOURS


def test_a_recent_run_is_healthy():
    ledger = _Ledger([_row("started", hours_ago=2), _row("finished", hours_ago=2)])
    assert scheduler.monitoring_health(ledger)["healthy"] is True


def test_a_failure_after_the_last_success_is_unhealthy():
    """A schedule that fires and breaks is a different problem from silence, and it must not read
    as healthy just because a run completed once."""
    ledger = _Ledger([
        _row("finished", hours_ago=10, run_id="ok"),
        _row("failed", hours_ago=1, run_id="bad", error="psycopg.OperationalError"),
    ])
    h = scheduler.monitoring_health(ledger)
    assert h["healthy"] is False
    assert "most recent run FAILED" in h["reason"]


def test_a_dry_run_is_recorded_but_does_not_count_as_a_live_run():
    """A habit of checking what would happen is not the same as anything happening."""
    ledger = _Ledger([_row("started", trigger="dry_run", hours_ago=1),
                      _row("finished", trigger="dry_run", hours_ago=1)])
    h = scheduler.monitoring_health(ledger)
    assert h["healthy"] is False and h["runs_recorded"] == 2
    assert "NEVER completed" in h["reason"]


def test_a_run_that_died_leaves_a_visible_orphan():
    """A status column would have overwritten this on the next success and lost the fact that
    anything died at all. That is the reason the ledger is an event log."""
    ledger = _Ledger([
        _row("started", hours_ago=30, run_id="died"),
        _row("started", hours_ago=1, run_id="ok"),
        _row("finished", hours_ago=1, run_id="ok"),
    ])
    h = scheduler.monitoring_health(ledger)
    assert h["healthy"] is True
    assert h["incomplete_runs"] == ["died"], "a run that died must not vanish on the next success"


def test_the_run_ledger_is_append_only_in_the_schema():
    """Protected for a reason that is not about legal artefacts: an operator who can edit run
    history can make a monitoring practice look continuous after the fact."""
    from app.pg_store import _TRIGGERS

    ops = {op for table, _, op in _TRIGGERS if table == "monitor_runs"}
    assert ops == {"UPDATE", "DELETE"}
