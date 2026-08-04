"""E6 — the exposure denominator. A failure RATE, not a failure count.

THE DEFECT, IN ONE COMPARISON. Before this phase `stale_hosts` banded on a raw count:

    Vendor A:   4 public hosts,  2 abandoned  ->  50%  -> band `some` ->  -8
    Vendor B: 900 public hosts,  9 abandoned  ->   1%  -> band `many` -> -20

B runs an estate fifty times tidier and paid two and a half times more, because the model was
measuring how BIG a vendor is and calling the answer risk. `docs/discrimination-analysis.md`
measured the consequence: `stale_hosts` and `subdomain_estate` penalise 100% of real corpus
vendors, and a penalty nobody escapes cannot rank anyone.

Arithmetic and parameter reasoning: `app/scoring/exposure.py`. Shipped values: `scoring.yaml`
-> `exposure:`.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from app.models import CollectorResult, Finding, Vendor
from app.scoring import ScoringEngine
from app.scoring.exposure import exposure_index, posterior_rate
from app.scoring_config import ScoringConfig, get_scoring_config

_YAML = Path(__file__).resolve().parents[2] / "scoring.yaml"


def _vendor() -> Vendor:
    return Vendor(ref="acme", name="Acme", domain="acme.example",
                  resolved=True, resolution_confidence=1.0)


def _estate(stale: int, total: int) -> list[CollectorResult]:
    """The two findings `ct_collector` emits, as the engine receives them."""
    return [CollectorResult(
        source="ct", vendor_ref="acme", status="ok", source_version="t", raw={"t": 1},
        reliability=0.9,
        findings=[
            Finding(source="ct", signal="subdomain_estate", category="attack_surface_hygiene",
                    observed=f"{total} subdomains", value={"count": total}),
            Finding(source="ct", signal="stale_hosts", category="attack_surface_hygiene",
                    observed=f"{stale} of {total}", value={"count": stale}),
        ],
    )]


def _stale(stale: int, total: int):  # noqa: ANN201
    out = ScoringEngine().score(_vendor(), _estate(stale, total))
    return next(n for n in out.normalized if n.signal == "stale_hosts")


def _cfg_with(overrides: dict) -> ScoringConfig:
    """The shipped config with `exposure:` patched — used to test the revert switch."""
    data = copy.deepcopy(yaml.safe_load(_YAML.read_text(encoding="utf-8")))
    data["exposure"].update(overrides)
    return ScoringConfig(data, _YAML)


# --------------------------------------------------------------- the three the plan named


def test_large_estate_with_low_stale_rate_beats_small_estate_with_high_rate():
    """THE test. It failed against v5.0.0 and every version before it.

    Before E6: A banded `some` (-8), B banded `many` (-20) — B worse by 2.5x, exactly backwards.
    After: A is worse than B, which is what half an estate rotting ought to mean.
    """
    a = _stale(2, 4)      # 50% of a tiny estate
    b = _stale(9, 900)    # 1% of a large one

    assert a.penalty > b.penalty, (
        f"A (2 of 4 stale) charged {a.penalty}, B (9 of 900) charged {b.penalty}. The vendor with "
        f"half their estate abandoned must not score better than one with 1% abandoned."
    )
    assert a.band_key == "many" and b.band_key == "some"


def test_one_of_one_failure_is_not_scored_as_one_hundred_percent():
    """A single observation is not a rate. `f/D` cannot tell 1-of-1 from 900-of-900 and would
    hand the smallest vendors the worst possible score on the thinnest possible evidence — the
    ability-to-pay bias this model is supposed to be removing, re-entering through the maths."""
    one = _stale(1, 1)
    assert one.exposure_index < 0.15, (
        f"1 of 1 scored an exposure index of {one.exposure_index:.3f}. The prior is supposed to "
        f"shrink a single observation toward the base rate, not report it as total failure."
    )
    assert one.band_key != "many"
    # ...and the raw ratio it is protecting against really is 1.0.
    assert posterior_rate(1, 1) < 0.2


def test_a_single_severe_finding_is_not_diluted_by_a_large_estate():
    """The mirror failure, and the reason `kappa` exists.

    A pure rate lets scale buy forgiveness: 60 abandoned hosts out of 900 is 6.6%, which reads
    fine, and 60 abandoned hosts is 60 ways in. Rate-normalising without an absolute floor would
    simply invert the original defect in favour of large vendors.
    """
    big = _stale(60, 900)
    assert big.band_key == "many", (
        f"60 abandoned hosts banded {big.band_key!r} because the estate is large. The absolute "
        f"term (kappa) exists to stop exactly this."
    )
    # The rate alone would not have got there — proving kappa is what did the work.
    assert posterior_rate(60, 900) < 0.12


# --------------------------------------------------------------- properties that must hold


def test_zero_failures_is_never_charged():
    """With a prior, zero observed failures still yields a small positive rate — for a 4-host
    vendor, 0.5/14 = 3.6%. Banding on that would charge a vendor with a spotless estate for a
    finding of ZERO, which is the fastest way to lose their trust in every other number."""
    for total in (1, 4, 20, 900, 5000):
        clean = _stale(0, total)
        assert clean.exposure_index == 0.0
        assert clean.band_key == "none"
        assert clean.penalty == 0.0, f"charged {clean.penalty} for zero stale hosts of {total}"


def test_the_rate_is_monotonic_in_both_directions():
    """More failures is never better; a larger clean estate is never worse. Generated rather than
    spot-checked, because monotonicity breaks silently and a handful of cases will not catch it."""
    for total in (10, 50, 200, 1000):
        rates = [exposure_index(f, total) for f in range(0, min(total, 40))]
        assert rates == sorted(rates), f"non-monotonic in failures at D={total}"
    for failures in (1, 5, 20):
        rates = [exposure_index(failures, d) for d in range(failures, failures + 200)]
        assert rates == sorted(rates, reverse=True), f"non-monotonic in denominator at f={failures}"


def test_the_denominator_is_published_on_the_finding():
    """E6's exit criterion, as arithmetic rather than intention. Attribution disagreements —
    *'you counted 340 hosts, we operate 40'* — are a top-two dispute category, and a rate whose
    denominator is not shown cannot be argued with."""
    n = _stale(9, 900)
    assert n.denominator == 900
    assert n.exposure_index is not None
    assert get_scoring_config().action_for("stale_hosts", n.band_key)["accepts_as_refute"]
    # The refute text must invite the denominator challenge, not only the host-list one.
    for band in ("negligible", "some", "many"):
        refute = get_scoring_config().action_for("stale_hosts", band)["accepts_as_refute"]
        assert "count of your public estate" in refute, f"{band}: no way to dispute the denominator"


def test_a_corrected_denominator_changes_the_band():
    """What makes the dispute meaningful. If challenging the estate size could not move the
    outcome, inviting the challenge would be theatre."""
    assert _stale(9, 900).band_key == "some"
    assert _stale(9, 40).band_key == "many"      # same 9 hosts, honest denominator, worse verdict


def test_band_keys_stay_stable_strings_for_the_dispute_machinery():
    """`_apply_dispute` keys on `(signal, band_key)`. A rate-derived band that was a formatted
    number would make every dispute unmatchable the moment a count changed by one."""
    bands = {_stale(f, d).band_key for f, d in
             [(0, 6), (1, 900), (5, 4326), (9, 99), (13, 41), (119, 211), (61, 340)]}
    assert bands <= {"none", "negligible", "some", "many"}


def test_the_collector_emits_the_denominator_itself():
    """Belt and braces. The engine pairs the two findings, but a receipt read in five years should
    not need its sibling to be interpretable."""
    from app.collectors.ct_collector import CtCollector

    findings = CtCollector()._findings(
        "acme.example", ["a.acme.example", "dev.acme.example"], ["dev.acme.example"], False, "crtsh")
    stale = next(f for f in findings if f.signal == "stale_hosts")
    assert stale.value["denominator"] == 2
    assert "of 2" in stale.observed


# --------------------------------------------------------------- the revert switch


def test_disabling_exposure_restores_the_pre_e6_bands():
    """E6's exit criterion: *keep behind `exposure.enabled` so a revert is one config line*.

    The subtle failure this guards: `stale_hosts` left `count_bands:`, so switching the feature off
    without a fallback would send it down the plain-band path, where its observed string matches no
    band and it would silently stop scoring — a revert that looks like a revert and is a deletion.
    """
    off = _cfg_with({"enabled": False})
    assert off.exposure_spec("stale_hosts") is None
    # Every exposure signal stays KNOWN when the feature is off, which is what makes the revert a
    # revert rather than a deletion. E12 added two more (`estate_*`), so this asserts membership
    # rather than equality — pinning the exact set would make every future exposure signal look
    # like a regression in a test about something else.
    assert "stale_hosts" in off.exposure_signals(), "the signal must still be KNOWN when off"
    assert {"estate_tls_legacy", "estate_cert_expired"} <= off.exposure_signals()
    assert off.count_band("stale_hosts", 9) == "many"     # the pre-E6 verdict, restored
    assert off.count_band("stale_hosts", 3) == "some"
    assert off.count_band("stale_hosts", 0) == "none"

    n = next(x for x in ScoringEngine(cfg=off).score(_vendor(), _estate(9, 900)).normalized
             if x.signal == "stale_hosts")
    assert n.band_key == "many", "reverting must reproduce the pre-E6 band exactly"
    assert n.penalty == 20.0
    assert n.exposure_index is None, "no rate should be computed when the feature is off"
    assert n.denominator is None

    # ...and with it ON, the same estate is read completely differently. Stated here so the two
    # halves of the switch are visible in one place.
    on = _stale(9, 900)
    assert on.band_key == "some" and on.penalty == 6.0   # medium, widened to 6 at E7b


# --------------------------------------------------------------- config discipline


def test_exposure_is_registered_as_engine_read():
    """The trap E6 shares with every phase that adds a top-level key: config nothing reads is how
    this model drifted from its own documentation three times. `_ENGINE_READS` is the guard."""
    from app.scoring_config import _ENGINE_READS

    assert "exposure" in _ENGINE_READS


def test_subdomain_estate_is_a_denominator_and_no_longer_a_penalty():
    """It stays in the signal list — deleting it would drop planned_signal_count to 26 and lift
    every vendor's confidence for no evidential reason — but charging a vendor for the SIZE of
    their estate was the defect, so every band is informational now."""
    cfg = get_scoring_config()
    bands = cfg.signals_of("attack_surface_hygiene")["subdomain_estate"]
    assert all(cfg.penalty_for(sev) == 0 for sev in bands.values()), bands
    assert cfg.exposure_denominator_signal("stale_hosts") == "subdomain_estate"
    assert cfg.planned_signal_count() == 27


def test_every_exposure_band_still_carries_a_reason_and_an_action():
    """The loader enforces this globally; asserted here too because E6 ADDED a band
    (`negligible`), and a new band without a sentence ships an unexplained deduction."""
    cfg = get_scoring_config()
    for band in ("negligible", "some", "many"):
        assert cfg.reason_for("stale_hosts", band), f"{band} has no plain-English reason"
        assert (cfg.action_for("stale_hosts", band) or {}).get("action"), f"{band} has no action"


@pytest.mark.parametrize("stale,total,expected", [
    (13, 41, "many"),        # atlassian  — a third of a small estate
    (11, 84, "many"),        # myob
    (9, 99, "some"),         # onetrust   — was `many` before E6
    (5, 4326, "negligible"), # slack      — was `some`; 0.1% of a very large estate
    (119, 211, "many"),      # snowflake  — 56%, and it stays `many`
])
def test_the_corpus_estates_band_where_the_change_notice_says_they_do(stale, total, expected):
    """Pins the per-vendor movement E6 publishes, so a parameter tweak that quietly re-bands a
    real vendor fails here rather than showing up as an unexplained golden diff."""
    assert _stale(stale, total).band_key == expected
