"""Target maturity — measurement against a published baseline rather than against the peer pool.

The three things this feature is for, asserted rather than assumed: it works with no peers at all,
it never counts an unobserved control as a failure, and every control it publishes names the
instrument that requires it.
"""

from __future__ import annotations

import pytest

from app.benchmark import BenchmarkConfig, build_benchmark, get_benchmark_config
from app.models import PeerCohort
from app.targets import TargetConfig, TargetConfigError, build_maturity_gap

WEAK = {
    "dmarc": "absent", "spf": "softfail_all", "tls_version": "tls_10_or_11",
    "cert_validity": "valid", "hsts": "absent", "kev_listed_cve": "no_kev_match",
    "vd_program": "none", "security_txt": "absent", "cert_posture": "none_claimed",
}
STRONG = {
    "dmarc": "p_reject", "spf": "hardfail_all", "tls_version": "tls_13",
    "cert_validity": "valid", "hsts": "present", "kev_listed_cve": "no_kev_match",
    "vd_program": "bug_bounty", "security_txt": "present",
    "cert_posture": "registry_corroborated",
}


def _targets() -> TargetConfig:
    return get_benchmark_config().targets()


# --------------------------------------------------------------------- the shipped file

def test_every_shipped_control_names_an_instrument():
    """The rule that keeps this from becoming a list of professional opinions. A plausible baseline
    with an official-sounding citation would pass any check that only tests for a non-empty
    string, so the shipped file is asserted directly."""
    for profile in _targets().profiles:
        for control in profile.controls:
            assert control.basis.strip(), f"{profile.id}/{control.signal} has no basis"
            # A basis must name something checkable, not gesture at "industry standard".
            assert any(token in control.basis
                       for token in ("BOD", "NIST", "RFC", "PCI DSS", "ISO/IEC", "SOC 2")), \
                f"{profile.id}/{control.signal} basis names no identifiable instrument"


def test_shipped_bands_exist_in_the_scoring_model():
    """A target that expects a band the collectors never emit can never be met, and would show as a
    permanent gap on every vendor."""
    from app.scoring_config import get_scoring_config

    cfg = get_scoring_config()
    known: dict[str, set[str]] = {}
    for category in cfg.category_names():
        for signal, bands in cfg.signals_of(category).items():
            known.setdefault(signal, set()).update(bands.keys())

    for profile in _targets().profiles:
        for control in profile.controls:
            assert control.signal in known, f"unknown signal {control.signal!r}"
            for band in (*control.meets, *control.partial):
                assert band in known[control.signal], \
                    f"{control.signal}: band {band!r} is not in scoring.yaml"


def test_day_one_controls_are_not_age_gated():
    """Attainability is for artefacts that need elapsed time, NOT a grace period for controls a
    startup could ship on day one. Email auth and TLS cost engineering hours, not years."""
    for profile in _targets().profiles:
        for control in profile.controls:
            if control.signal in {"dmarc", "spf", "tls_version", "cert_validity", "hsts"}:
                assert control.attainable_after_years == 0


# --------------------------------------------------------------------- evaluation

def test_a_strong_vendor_meets_the_baseline_and_a_weak_one_does_not():
    strong = build_maturity_gap(STRONG, "technology", _targets(), 20.0)
    weak = build_maturity_gap(WEAK, "technology", _targets(), 20.0)
    assert strong.attainment == 1.0
    assert weak.attainment is not None and weak.attainment < 0.4
    assert weak.gaps > strong.gaps


def test_it_works_with_no_peers_at_all():
    """THE POINT OF THE FEATURE. A cohort needs peers; a published baseline does not, so the
    reading survives exactly the situation where the percentile cannot be published."""
    gap = build_maturity_gap(STRONG, "technology", _targets(), 10.0)
    assert gap.available is True
    assert gap.attainment == 1.0


def test_an_unobserved_control_is_not_a_failure():
    """Absence of evidence is not evidence of absence — the same discipline the scoring engine
    applies one level up. An unchecked signal leaves the denominator."""
    partial_view = {"dmarc": "p_reject", "spf": "hardfail_all", "tls_version": "tls_13"}
    gap = build_maturity_gap(partial_view, "technology", _targets(), 20.0)
    assert gap.applicable == 3
    assert gap.gaps == 0
    assert gap.unchecked > 0
    assert gap.attainment == 1.0          # not punished for what we could not see


def test_too_few_observations_publishes_nothing():
    """'2 of 3' assembled from whichever signals happened to return is the same false precision as
    a median over three vendors."""
    gap = build_maturity_gap({"dmarc": "absent"}, "technology", _targets(), 10.0)
    assert gap.available is False
    assert gap.attainment is None
    assert "below the minimum" in (gap.reason or "")


def test_partial_credit_sits_between_meeting_and_failing():
    """p=quarantine is not p=reject, and it is also not the same as publishing nothing."""
    base = {"spf": "hardfail_all", "tls_version": "tls_13", "cert_validity": "valid"}
    met = build_maturity_gap({**base, "dmarc": "p_reject"}, "technology", _targets(), 20.0)
    part = build_maturity_gap({**base, "dmarc": "p_quarantine"}, "technology", _targets(), 20.0)
    none = build_maturity_gap({**base, "dmarc": "absent"}, "technology", _targets(), 20.0)
    assert met.attainment > part.attainment > none.attainment


# --------------------------------------------------------------------- age, handled honestly

def test_an_unattainable_artefact_is_excluded_and_disclosed():
    """A SOC 2 Type II attests across an observation window, so a 1-year-old entity cannot hold
    one. Counting that as a gap would measure the calendar, not the vendor."""
    young = build_maturity_gap(WEAK, "technology", _targets(), 1.0)
    old = build_maturity_gap(WEAK, "technology", _targets(), 20.0)
    assert young.not_yet_attainable == 1
    assert old.not_yet_attainable == 0
    assert young.applicable == old.applicable - 1
    assert "not yet attainable" in (young.summary or "")


def test_age_never_excuses_a_day_one_control():
    """The leniency this feature must NOT have. A 1-year-old with no DMARC still fails DMARC."""
    young = build_maturity_gap(WEAK, "technology", _targets(), 1.0)
    dmarc = next(c for c in young.controls if c.signal == "dmarc")
    assert dmarc.status == "gap"


def test_unknown_age_is_held_to_the_full_baseline():
    """Erring the other way would make 'we could not determine your founding date' a way to shed
    controls — a gaming vector, and a cheap one."""
    unknown = build_maturity_gap(WEAK, "technology", _targets(), None)
    old = build_maturity_gap(WEAK, "technology", _targets(), 20.0)
    assert unknown.applicable == old.applicable
    assert unknown.not_yet_attainable == 0


# --------------------------------------------------------------------- config validation

def test_a_control_without_a_basis_is_refused_at_load():
    with pytest.raises(TargetConfigError, match="no `basis`"):
        TargetConfig({"target_maturity": {"profiles": [
            {"id": "p", "controls": [{"signal": "dmarc", "meets": ["p_reject"]}]},
        ]}})


def test_a_control_nothing_could_satisfy_is_refused():
    with pytest.raises(TargetConfigError, match="no `meets`"):
        TargetConfig({"target_maturity": {"profiles": [
            {"id": "p", "controls": [{"signal": "dmarc", "basis": "RFC 7489"}]},
        ]}})


def test_a_band_cannot_be_both_met_and_partial():
    with pytest.raises(TargetConfigError, match="both"):
        TargetConfig({"target_maturity": {"profiles": [
            {"id": "p", "controls": [{"signal": "dmarc", "basis": "RFC 7489",
                                      "meets": ["p_reject"], "partial": ["p_reject"]}]},
        ]}})


def test_a_signal_in_two_profiles_is_counted_once():
    """Otherwise the SHAPE of the config file moves a vendor's attainment with no observation
    having changed."""
    cfg = TargetConfig({"target_maturity": {"min_controls": 1, "profiles": [
        {"id": "a", "controls": [{"signal": "dmarc", "basis": "BOD 18-01", "meets": ["p_reject"]}]},
        {"id": "b", "controls": [{"signal": "dmarc", "basis": "BOD 18-01", "meets": ["p_reject"]}]},
    ]}})
    gap = build_maturity_gap({"dmarc": "absent"}, "technology", cfg, 10.0)
    assert gap.applicable == 1
    assert len(gap.controls) == 1


# --------------------------------------------------------------------- integration

def test_benchmark_carries_the_gap_even_with_no_posture():
    """A blocked or refused vendor still gets the baseline reading — it is the one measure that
    does not depend on a published number or on a peer group."""
    bm = build_benchmark(None, None, lookup=lambda _dims: [], signals=STRONG, vendor_age_years=20.0)
    assert bm.available is False
    assert bm.maturity_gap is not None
    assert bm.maturity_gap.attainment == 1.0


def test_benchmark_carries_the_gap_alongside_a_percentile():
    cohort = PeerCohort(sector="technology", employee_band="large", region="anz",
                        key="technology|rev=?|emp=large|anz")
    bm = build_benchmark(78, cohort, lookup=lambda _dims: [], signals=WEAK, vendor_age_years=20.0)
    assert bm.maturity_gap is not None
    assert bm.maturity_gap.gaps > 0
    # The two readings are independent: a percentile exists AND the baseline is missed.
    assert bm.posture == 78


def test_a_broken_target_block_does_not_sink_the_percentile():
    """Each reading degrades alone. A malformed profile must not cost a reader their comparison."""
    from pathlib import Path

    cfg = BenchmarkConfig({"cohort": {"min_cohort_n": 1}}, Path("t"))
    cohort = PeerCohort(sector="technology", employee_band="large", region="anz",
                        key="technology|rev=?|emp=large|anz")
    bm = build_benchmark(78, cohort, lookup=lambda _dims: [], cfg=cfg, signals=WEAK)
    assert bm.available is True
    # No target_maturity block configured -> no gap, but the comparison still published.
    assert bm.maturity_gap is None or bm.maturity_gap.available is False
