"""E10a — the Expectation Gap and its drivers.

THE SENTENCE THE PHASE EXISTS TO PRODUCE, which is the answer to the whole research question:

    "Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group.
     The gap is driven by dmarc (absent) — 12 of 14 peers are not in this band."

The first half was delivered by EB as `delta_from_median`. The second half is what E10a owes, and
it is the half that turns a fact into a remediation: a buyer handed `-19` knows they have a
problem, a buyer handed `-19, driven by DMARC, which 12 of 14 peers publish` knows what to ask for,
and can ask for it citing a count of the vendor's own peer group rather than an opinion of ours.
"""

from __future__ import annotations

import pytest

from app.benchmarking.expectation_gap import expectation_gap
from app.benchmarking.models import PeerRecord


def _peer(ref: str, posture: int, **signals: str) -> PeerRecord:
    return PeerRecord(supplier_ref=ref, posture=posture, signals=signals)


def _cohort(n: int = 14, *, posture: int = 87, **signals: str) -> list[PeerRecord]:
    """A cohort of `n` peers all sitting at `posture`, with whatever bands are given."""
    return [_peer(f"peer-{i}", posture, **signals) for i in range(n)]


# --------------------------------------------------------------------- the signed gap


def test_the_gap_is_signed_named_and_states_its_estimator():
    """`EG = Posture − E[Posture | cohort]`. The estimator is part of the CLAIM, not a footnote to
    it: "19 points below the median" and "19 points below the mean" are different findings, and a
    reader must be able to tell which one they were handed."""
    report = expectation_gap("acme", 68, _cohort(14, posture=87))

    assert report.published is True
    assert report.expected_posture == 87
    assert report.gap == -19
    assert report.direction == "below"
    assert "median" in report.estimator


def test_a_supplier_above_its_peers_gets_a_positive_gap():
    """Signed, not an absolute distance. "19 above" and "19 below" are opposite findings and a
    magnitude cannot express the difference."""
    report = expectation_gap("acme", 95, _cohort(14, posture=80))
    assert report.gap == 15
    assert report.direction == "above"
    assert any("ABOVE its peer median" in c for c in report.caveats)


def test_the_expectation_uses_the_same_median_the_placement_does():
    """A second definition of the middle of a distribution is a second answer to the same question,
    and the two drift within a release. This calls `_percentile_value` rather than reimplementing
    a median, so an expectation quoted here and a median quoted in a placement CANNOT disagree."""
    from app.benchmarking.placement import place

    values = [40, 55, 61, 61, 70, 72, 79, 84, 90, 91]
    peers = [_peer(f"p{i}", v) for i, v in enumerate(values)]
    placed = place(68, values)
    report = expectation_gap("acme", 68, peers)

    assert report.expected_posture == placed.median
    assert report.gap == placed.delta_from_median


# --------------------------------------------------------------------- the refusals


def test_no_expectation_below_the_quartile_floor():
    """The same floor the placement applies, for the same reason. A gap against a median of four
    companies is a comparison with a handful of businesses, and calling it a peer expectation gives
    it a confidence it has not earned."""
    report = expectation_gap("acme", 68, _cohort(4, posture=87))
    assert report.published is False
    assert report.gap is None and report.expected_posture is None
    assert "Insufficient peer data: 4" in report.reason
    assert report.headline() is None, "a caller must not be able to compose a sentence from a refusal"


def test_synthetic_peers_yield_no_expectation_at_any_n():
    """The hard gate, checked FIRST, before anything is computed. Thirty invented numbers still make
    a screenshottable expectation, and the caption under it does not travel with the screenshot."""
    report = expectation_gap("acme", 68, _cohort(40, posture=87), is_synthetic=True)
    assert report.published is False
    assert "synthetic peers at any sample size" in report.reason


def test_a_vendor_with_no_posture_is_not_compared():
    """Blocked, gated and refused vendors have no number to place. Substituting one — a zero, a
    cohort median — would be the Ghost cliff by another route."""
    report = expectation_gap("acme", None, _cohort(14))
    assert report.published is False
    assert "No published posture" in report.reason


# --------------------------------------------------------------------- driver attribution


def test_the_driver_is_what_peers_do_not_share():
    """The definition, and the whole point of the phase:

        attribution(s) = charged_posture_points(s) × (1 − peer_failure_rate(s))

    A vendor failing DMARC in a cohort where every peer also fails DMARC is not BEHIND on DMARC. It
    cost them points, and it cost their peers the same points, so it explains none of their
    POSITION. Without this, a "driver" is just the vendor's biggest penalty relabelled as a
    comparison — which is precisely what a peer benchmark is supposed to replace.
    """
    peers = ([_peer(f"clean-{i}", 87, dmarc="p_reject", hsts="absent") for i in range(12)]
             + [_peer(f"same-{i}", 87, dmarc="absent", hsts="absent") for i in range(2)])
    report = expectation_gap(
        "acme", 68, peers,
        subject_signals={"dmarc": "absent", "hsts": "absent"},
        charged_points={"dmarc": 7.0, "hsts": 7.0},
    )

    by_signal = {d.signal: d for d in report.drivers}
    # Identical cost, opposite verdicts — because 12 of 14 peers publish DMARC and 0 of 14 publish
    # HSTS. `hsts` drops out entirely: every peer shares it, so it explains none of the gap.
    assert "hsts" not in by_signal
    dmarc = by_signal["dmarc"]
    assert dmarc.charged_posture_points == 7.0
    assert dmarc.peers_sharing_band == 2 and dmarc.peers_observed == 14
    assert dmarc.attribution == pytest.approx(7.0 * (12 / 14), abs=0.01)


def test_the_headline_names_the_driver_and_counts_the_peer_group():
    """The published sentence. It leads with the peer COUNT because that is the part the vendor
    cannot argue is our opinion — it is a fact about their own peer group."""
    peers = ([_peer(f"clean-{i}", 87, dmarc="p_reject") for i in range(12)]
             + [_peer(f"same-{i}", 87, dmarc="absent") for i in range(2)])
    report = expectation_gap("acme", 68, peers,
                             subject_signals={"dmarc": "absent"},
                             charged_points={"dmarc": 7.0})

    headline = report.headline()
    assert "Posture 68" in headline
    assert "(n=14): 87" in headline
    assert "19 points below" in headline
    assert "dmarc" in headline and "12 of 14 peers" in headline


def test_drivers_are_ranked_and_the_report_says_they_do_not_sum():
    """THE MISREADING THIS GUARDS AGAINST. Since E7a, what a finding costs depends on what else was
    charged alongside it (`λ^(rank−1)` within a category), so per-signal attributions do not add up
    to the gap and no arrangement of them can be made to. Presenting them as a decomposition —
    "here is where your 19 points went" — would be arithmetically false, so they are ranked and the
    caveat is emitted mechanically rather than left to whoever writes the report."""
    peers = _cohort(14, posture=87, dmarc="p_reject", tls_version="tls_13", hsts="present")
    report = expectation_gap(
        "acme", 68, peers,
        subject_signals={"dmarc": "absent", "tls_version": "tls_10_or_11", "hsts": "absent"},
        charged_points={"dmarc": 2.0, "tls_version": 17.5, "hsts": 0.5},
    )

    assert [d.signal for d in report.drivers] == ["tls_version", "dmarc", "hsts"]
    assert sum(d.attribution for d in report.drivers) != abs(report.gap)
    assert any("NOT A DECOMPOSITION" in c for c in report.caveats)


def test_the_lone_failure_in_a_clean_cohort_is_the_strongest_driver_not_a_suppressed_one():
    """A DESIGN ERROR CAUGHT BY THIS TEST, worth keeping the reasoning for.

    The discrimination verdict was first computed over the peers alone — which is right everywhere
    else in this package, because an "n=30" that counts the subject is 29 peers and the percentile
    rule would be wrong by one. It is exactly wrong here.

    A discrimination verdict asks whether a signal separates the companies being compared, and the
    subject is one of them. Fourteen peers all publishing DMARC is 14/14 in one band, which the
    modal-share test calls flat — so the vendor who is the ONLY ONE in the cohort without DMARC had
    their single clearest driver suppressed for being unanimous among everyone except them. The
    stronger the finding, the more certainly it was discarded.

    With the subject included it is 14/15, discriminating, and it ranks first. A signal is now
    suppressed only when the subject and its peers ALL sit in the same band — the case the
    suppression was written for.
    """
    peers = _cohort(14, posture=87, dmarc="p_reject")
    report = expectation_gap("acme", 68, peers,
                             subject_signals={"dmarc": "absent"},
                             charged_points={"dmarc": 7.0})

    assert report.suppressed_signals == [], "the only failing vendor had its driver suppressed"
    assert [d.signal for d in report.drivers] == ["dmarc"]
    assert report.drivers[0].attribution == pytest.approx(7.0), (
        "no peer shares the band, so the finding explains the whole of its own cost"
    )


def test_a_non_discriminating_signal_is_suppressed_by_name_not_dropped():
    """Agreement with the discrimination test, reached from the other direction. A signal every peer
    sits on cannot explain a POSITION — but "every supplier in your cohort fails this" is a finding
    in its own right, so it is named rather than silently removed. Never silently included, never
    silently dropped, which is the rule EB already applies to the peer-gap list."""
    peers = _cohort(14, posture=87, cert_posture="none_claimed")
    report = expectation_gap("acme", 68, peers,
                             subject_signals={"cert_posture": "none_claimed"},
                             charged_points={"cert_posture": 3.0})

    assert report.drivers == []
    assert report.suppressed_signals == ["cert_posture"]
    assert any("do not vary across this cohort" in c for c in report.caveats)


def test_a_signal_no_peer_was_checked_for_forms_no_rate():
    """A prevalence rate over zero observations is not a small rate, it is no rate. Treating an
    unchecked signal as "no peer fails it" would attribute the entire gap to whichever signal the
    cohort happens to have the least coverage of."""
    report = expectation_gap("acme", 68, _cohort(14, posture=87),
                             subject_signals={"dnssec": "absent"},
                             charged_points={"dnssec": 5.0})
    assert report.drivers == []


def test_a_signal_that_cost_nothing_is_never_a_driver():
    """A passing signal explains no gap. Including it would put "tls_version = tls_13" on a list of
    reasons a vendor is behind, which reads as a criticism of a control that is working."""
    peers = _cohort(14, posture=87, tls_version="tls_10_or_11")
    report = expectation_gap("acme", 68, peers,
                             subject_signals={"tls_version": "tls_13"},
                             charged_points={})
    assert report.drivers == []


# --------------------------------------------------------------------- the invariant


def test_the_expectation_gap_never_alters_a_score():
    """The package contract, restated for the new module. If every line of `benchmarking/` were
    deleted, every published score would be byte-identical."""
    import ast
    import inspect
    from pathlib import Path

    from app.benchmarking import expectation_gap as module

    # Parsed, not grepped: the module docstring *names* `scoring.yaml` in the course of explaining
    # why it must never read it, and a substring check would fail on the very comment that states
    # the rule. Imports are the thing that can actually create the coupling.
    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    imported = {
        n.module or ""
        for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
    } | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    for name in imported:
        assert "scoring" not in name, (
            f"{name!r} reaches the benchmarking layer — the divisor is passed IN as a number "
            f"precisely so this import never happens"
        )


# ------------------------------------------------- model-risk controls (bias monitoring)


def test_firmographics_alone_cannot_move_a_posture_ablation():
    """THE ABLATION TEST industry guidance names as a bias-monitoring control.

    The question it asks is not "does the cohort look reasonable" but "does knowing a supplier's
    SECTOR AND SIZE, and nothing else about them, predict their posture in this system?" If it
    does, the firmographics have become a scoring factor by some indirect route — which is exactly
    what E1 deleted `industry_profiles` to stop, and exactly the failure a benchmark makes easy to
    reintroduce, because a benchmark is the one component that legitimately handles firmographics.

    Asserted STRUCTURALLY rather than statistically, because a statistical version needs a seeded
    pool (E11) and would be `untested` until then — and an untested control is not a control. The
    structural form holds now and holds at any pool size: the engine's inputs are findings and
    config, and no firmographic reaches them. If that ever stops being true, no amount of
    downstream statistics will make it safe.
    """
    import ast
    import inspect
    from pathlib import Path

    from app.scoring import engine, normalize

    firmographic = {"sector", "size_band", "employee_band", "revenue_band", "region",
                    "delivery_model", "criticality", "data_access_scope"}
    for module in (engine, normalize):
        tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
        assigned = {
            t.id
            for n in ast.walk(tree) if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)
        }
        # `sector` is a PARAMETER of `normalize_one` and is deliberately ignored (E1). Accepting it
        # and dropping it is the documented behaviour; assigning it to something is not.
        assert not (assigned & firmographic), (
            f"{module.__name__} assigns a firmographic ({assigned & firmographic}) — a supplier's "
            f"size or industry must never become an input to what an observation is worth"
        )


def test_the_same_finding_scores_identically_in_every_cohort():
    """The comparability principle, stated as an outcome rather than as an import check.

    Two suppliers with byte-identical evidence must publish byte-identical postures no matter which
    peer group they land in. This is the property that makes a cross-sector portfolio view mean
    anything, and it is the one a benchmark silently breaks if a placement is ever allowed to
    adjust a score.
    """
    from app.benchmarking.expectation_gap import expectation_gap

    subject = {"dmarc": "absent"}
    charged = {"dmarc": 7.0}
    strong = _cohort(14, posture=95, dmarc="p_reject")
    weak = _cohort(14, posture=40, dmarc="absent")

    in_strong = expectation_gap("acme", 68, strong, subject_signals=subject, charged_points=charged)
    in_weak = expectation_gap("acme", 68, weak, subject_signals=subject, charged_points=charged)

    # The POSTURE is the same number in both — it is an input, passed through untouched.
    assert in_strong.posture == in_weak.posture == 68
    # Only the CONTEXT differs, which is the entire job of this layer.
    assert in_strong.gap == -27 and in_weak.gap == 28
    assert in_strong.direction == "below" and in_weak.direction == "above"
