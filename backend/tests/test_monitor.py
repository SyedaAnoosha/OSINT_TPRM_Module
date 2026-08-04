"""P5's join — the scheduled sweep stops running one clock over the whole book.

A depth-and-cadence table that nothing schedules against is a table, and the budget saving it
claims never arrives. These tests are about the SWEEP, not the table: that a passive relationship
is genuinely skipped, that an urgent finding still pulls it forward, and that an undeclared tier is
never quietly demoted to the cheapest treatment by the thing that spends the budget.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.models import utcnow
from app.monitor import monitor, plan_of


class _Row:
    def __init__(self, signal: str, band_key: str, penalty: float) -> None:
        self.signal, self.band_key, self.effective_penalty = signal, band_key, penalty


class _FakeStore:
    """Only the six reads the by-tier sweep performs. Anything else is a bug in the sweep."""

    def __init__(self, vendors: dict[str, dict]) -> None:
        self.vendors = vendors
        self.closed = False

    def latest_scores_all(self):
        now = utcnow()
        return [
            SimpleNamespace(vendor_ref=ref, posture=70, grade="C",
                            computed_at=now - timedelta(days=v["age_days"]))
            for ref, v in self.vendors.items()
        ]

    def latest_score(self, ref):
        return next((s for s in self.latest_scores_all() if s.vendor_ref == ref), None)

    def latest_profile(self, ref):
        crit = self.vendors[ref].get("criticality")
        # `inherent_provisional` is present because a real `VendorProfile` always carries it —
        # pydantic defaults it to False, so even a row written before the field existed
        # deserialises with it. A fake that omitted it would be testing a shape the store cannot
        # actually return.
        return SimpleNamespace(
            criticality=crit,
            inherent_provisional=self.vendors[ref].get("provisional", False),
        ) if crit else None

    def latest_supplier_attributes(self, ref):
        scope = self.vendors[ref].get("data_access_scope")
        return {"data_access_scope": scope} if scope else None

    def findings_for_vendor(self, ref):
        return self.vendors[ref].get("findings", [])

    def for_vendor(self, ref):
        return [SimpleNamespace(raw={"domain": f"{ref}.com"})]

    def close(self):
        self.closed = True


def _sweep(monkeypatch, vendors) -> list:
    store = _FakeStore(vendors)
    monkeypatch.setattr("app.monitor.get_store", lambda: store)
    return asyncio.run(monitor(stale_days=7, only_ref=None, dry_run=True, by_tier=True))


# ============================================================ the tier drives the interval


def test_a_passive_relationship_long_past_the_old_clock_is_skipped(monkeypatch):
    """THE BUDGET WIN, stated as the behaviour it actually is. Under `--stale-days 7` this vendor
    would be re-scored for the fortieth time this year; under `--by-tier` it is not scored at all,
    because nobody depends on it and nothing is outstanding."""
    drifts = _sweep(monkeypatch, {
        "stationery": {"age_days": 300, "criticality": "low", "data_access_scope": "low"},
    })
    assert len(drifts) == 1
    assert drifts[0].note.startswith("skipped —")
    assert "passive" in drifts[0].note
    assert drifts[0].tier == "T4 Low"


def test_a_critical_relationship_inside_its_quarter_is_also_skipped(monkeypatch):
    drifts = _sweep(monkeypatch, {
        "core-db": {"age_days": 40, "criticality": "high", "data_access_scope": "critical"},
    })
    assert drifts[0].tier == "T1 Critical"
    assert "40 of 90" in drifts[0].note


def test_a_critical_relationship_past_its_quarter_is_due(monkeypatch):
    drifts = _sweep(monkeypatch, {
        "core-db": {"age_days": 95, "criticality": "high", "data_access_scope": "critical"},
    })
    assert drifts[0].note.startswith("would re-score")
    assert "full depth" in drifts[0].note


# ============================================================ the second clock still bites


def test_an_urgent_finding_pulls_a_passive_vendor_forward(monkeypatch):
    """`--by-tier` must never park a real problem. `cert_validity.expired_serving_prod` carries a
    7-day re-check in `scoring.yaml`; the relationship being unimportant does not make an expired
    certificate serving production a next-year item."""
    drifts = _sweep(monkeypatch, {
        "stationery": {
            "age_days": 30, "criticality": "low", "data_access_scope": "low",
            "findings": [_Row("cert_validity", "expired_serving_prod", 20.0)],
        },
    })
    assert drifts[0].note.startswith("would re-score")
    assert drifts[0].tier == "T4 Low"


def test_a_finding_that_cost_nothing_does_not_pull_anyone_forward(monkeypatch):
    """A passing control has no re-check date to inherit — the same rule P3 applies when deciding
    what to ask a vendor about."""
    drifts = _sweep(monkeypatch, {
        "stationery": {
            "age_days": 30, "criticality": "low", "data_access_scope": "low",
            "findings": [_Row("cert_validity", "expired_serving_prod", 0.0)],
        },
    })
    assert drifts[0].note.startswith("skipped —")


# ============================================================ undeclared is not cheap


def test_an_undeclared_relationship_runs_at_full_depth(monkeypatch):
    """The sweep is where a "sensible default" would do the most damage: it is the thing that
    spends the budget, so demoting unclassified vendors here would silently under-assess exactly
    the relationships nobody has looked at."""
    drifts = _sweep(monkeypatch, {"mystery": {"age_days": 400}})
    assert drifts[0].tier == "Unclassified"
    assert drifts[0].depth == "full"
    assert "full depth" in drifts[0].note


def test_the_screening_depth_note_warns_before_the_run_not_after(monkeypatch):
    """A reader meeting a Ghost refusal with no warning reads it as a finding about the vendor."""
    drifts = _sweep(monkeypatch, {
        "stationery": {
            "age_days": 900, "criticality": "low", "data_access_scope": "low",
            "findings": [_Row("cert_validity", "expired_serving_prod", 20.0)],
        },
    })
    assert "publishes no posture" in drifts[0].note


# ============================================================ the plan itself


def test_plan_of_reads_both_declared_inputs_and_neither_is_inferred(monkeypatch):
    store = _FakeStore({
        "a": {"age_days": 1, "criticality": "high"},                 # criticality only
        "b": {"age_days": 1, "data_access_scope": "critical"},       # scope only
        "c": {"age_days": 1},                                        # neither
    })
    assert plan_of(store, "a").tier == "high"
    assert plan_of(store, "b").tier == "critical"
    assert plan_of(store, "c").tier is None
    assert plan_of(store, "c").depth == "full"


def test_the_ordinary_sweep_is_completely_unchanged(monkeypatch):
    """`--by-tier` is opt-in. Without it the sweep behaves exactly as it did, tier fields unset, so
    an existing cron entry does not silently change what it spends."""
    store = _FakeStore({"acme": {"age_days": 30, "criticality": "low",
                                 "data_access_scope": "low"}})
    monkeypatch.setattr("app.monitor.get_store", lambda: store)
    drifts = asyncio.run(monitor(stale_days=7, only_ref=None, dry_run=True))
    assert len(drifts) == 1
    assert drifts[0].note == "would re-score"
    assert drifts[0].tier is None and drifts[0].depth is None


def test_by_tier_does_not_pre_filter_on_the_staleness_cutoff(monkeypatch):
    """The cutoff being replaced must not also gate the replacement. If `--stale-days` still
    filtered first, every tier interval longer than it would be unreachable and every shorter one
    decorative — the table would look principled and do nothing."""
    store = _FakeStore({"fresh": {"age_days": 1, "criticality": "low",
                                  "data_access_scope": "low"}})
    monkeypatch.setattr("app.monitor.get_store", lambda: store)
    drifts = asyncio.run(monitor(stale_days=7, only_ref=None, dry_run=True, by_tier=True))
    assert len(drifts) == 1, "a vendor inside the old cutoff was dropped before its tier was read"
