"""The v2 benchmarking store reads, exercised against a REAL Postgres store.

WHY THIS FILE EXISTS. `test_benchmarking.py` covers the placement arithmetic against fabricated peer
lists, and says so in its own comments — the store-backed paths were assumed to be covered by
`test_api.py`, and they were not. Nothing in the suite ever executed `bm_cohort_peers` against
Postgres.

What that let through: the exclude clause was built as `p.vendor_ref <> %s`, but `p` is the
`current_attrs` CTE, whose column is `supplier_ref`. `vendor_ref` is only the SELECT alias, and a
SELECT alias is not in scope in WHERE — so every call raised `UndefinedColumn`. The service passes
`exclude_ref` on every call, because a cohort must never count the subject. **The entire v2 surface
500'd**, and the arithmetic tests above it all passed.

The lesson generalises past the one typo: a query built by string concatenation is only tested by
running it. So these tests assert on real SQL, and the first one would have caught it.
"""

from __future__ import annotations

import pytest

from app.benchmarking.models import SupplierAttributes
from app.models import Score


def _score(ref: str, posture: int = 80) -> Score:
    """A publishable score — `bm_cohort_peers` filters out blocked, refused and null-posture rows."""
    return Score(vendor_ref=ref, posture=posture, grade="B", overall_confidence=0.9,
                 confidence_band="High", categories=[])


def _attrs(ref: str, *, sector: str = "technology", size_band: str = "large",
           delivery_model: str | None = None) -> SupplierAttributes:
    return SupplierAttributes(supplier_ref=ref, sector=sector, size_band=size_band,
                              delivery_model=delivery_model, source="client_supplied")


@pytest.fixture
def cohort(store):
    """Four technology suppliers, one of which is the subject of every query below."""
    for ref, posture in (("subject", 70), ("peer_a", 80), ("peer_b", 90), ("peer_c", 60)):
        store.put_supplier_attributes(_attrs(ref))
        store.put_score(_score(ref, posture))
    return store


def test_the_subject_is_excluded_from_its_own_cohort(cohort):
    """The regression test for the defect above — and the rule it protects.

    A cohort of one is not a peer group, and at the threshold boundary self-inclusion is worse than
    merely flattering: an "n=30" that counts the subject is 29 peers, so the percentile rule is
    wrong by one on the exact case it exists to govern.
    """
    peers = cohort.bm_cohort_peers({"sector": "technology"}, exclude_ref="subject")

    refs = {p["vendor_ref"] for p in peers}
    assert "subject" not in refs, "the subject must never appear in its own peer group"
    assert refs == {"peer_a", "peer_b", "peer_c"}


def test_every_supported_dimension_filters_without_error(cohort):
    """Each dimension goes into the same concatenated WHERE clause, so each needs executing once."""
    cohort.put_supplier_attributes(_attrs("saas_peer", delivery_model="saas"))
    cohort.put_score(_score("saas_peer"))

    assert cohort.bm_cohort_peers({"sector": "technology"}, exclude_ref="subject")
    assert cohort.bm_cohort_peers({"sector": "technology", "size_band": "large"},
                                  exclude_ref="subject")
    assert cohort.bm_cohort_peers({"delivery_model": "saas"}, exclude_ref="subject") == [
        p for p in cohort.bm_cohort_peers({"delivery_model": "saas"}, exclude_ref="subject")
    ]
    # `sector_group` is the pseudo-dimension: it arrives as a resolved LIST and becomes `= ANY(...)`,
    # a different SQL construction from the scalar comparisons above.
    grouped = cohort.bm_cohort_peers({"sector_group": ["technology", "finance"]},
                                     exclude_ref="subject")
    assert {p["vendor_ref"] for p in grouped} == {"peer_a", "peer_b", "peer_c", "saas_peer"}


def test_an_unknown_dimension_is_refused_rather_than_ignored(cohort):
    """Silently dropping an unrecognised dimension would widen the cohort without saying so —
    the supplier would be compared against a population nobody asked for."""
    with pytest.raises(ValueError, match="unknown v2 cohort dimension"):
        cohort.bm_cohort_peers({"data_access_scope": "high"}, exclude_ref="subject")


def test_an_empty_sector_group_returns_no_peers(cohort):
    """`= ANY('{}')` matches nothing, and an empty group means the rollup resolved to no sectors.
    Returning everyone would be the widest possible cohort produced by an absence of information."""
    assert cohort.bm_cohort_peers({"sector_group": []}, exclude_ref="subject") == []


def test_only_the_latest_attributes_and_the_latest_score_are_used(cohort):
    """Both tables are append-only, so a supplier reassessed twice has two rows in each.

    Without the `ROW_NUMBER() ... = 1` filters a re-scored peer would be counted twice, and a
    supplier that moved sector would be counted under both. Either one silently changes an `n`,
    which is the number every published figure is qualified by.
    """
    cohort.put_score(_score("peer_a", 95))
    cohort.put_supplier_attributes(_attrs("peer_a", size_band="mid"))

    peers = cohort.bm_cohort_peers({"sector": "technology"}, exclude_ref="subject")
    assert len(peers) == 3, "a re-scored, re-attributed peer must still be exactly one peer"
    assert next(p for p in peers if p["vendor_ref"] == "peer_a")["posture"] == 95

    # And the superseded attributes must not still match their old band.
    large = cohort.bm_cohort_peers({"sector": "technology", "size_band": "large"},
                                  exclude_ref="subject")
    assert "peer_a" not in {p["vendor_ref"] for p in large}


def test_unscorable_suppliers_are_not_peers(cohort):
    """A blocked or refused record has no posture to compare, and a null posture in a distribution
    is not a low score — it is an absent one. They must not enter the population at all."""
    cohort.put_supplier_attributes(_attrs("blocked_peer"))
    cohort.put_score(Score(vendor_ref="blocked_peer", blocked=True,
                           blocked_reason="sanctions hit — adjudication required",
                           overall_confidence=0.0, categories=[]))
    cohort.put_supplier_attributes(_attrs("ghost_peer"))
    cohort.put_score(Score(vendor_ref="ghost_peer", refused=True, overall_confidence=0.2,
                           confidence_band="Low", categories=[]))

    refs = {p["vendor_ref"] for p in cohort.bm_cohort_peers({"sector": "technology"},
                                                            exclude_ref="subject")}
    assert refs == {"peer_a", "peer_b", "peer_c"}


def test_peer_signals_reads_the_latest_run_only(store):
    """`bm_peer_signals` feeds prevalence ("12 of 14 peers publish DMARC"), so counting a re-scored
    peer's old bands alongside its new ones would count the same company twice in a rate."""
    from app.scoring.normalize import NormalizedFinding

    def _finding(signal: str, band: str) -> NormalizedFinding:
        return NormalizedFinding(
            evidence_id=None, source="dns", category="identity_email", signal=signal,
            band_key=band, severity="high", penalty=20.0, event_date=None,
            is_critical=False, is_sanctions=False, observed=f"{signal}={band}",
        )

    store.put_findings("peer_a", [_finding("dmarc", "absent")], run_id="run-1")
    store.put_findings("peer_a", [_finding("dmarc", "p_reject")], run_id="run-2")

    bands = store.bm_peer_signals(["peer_a"])
    assert bands["peer_a"]["dmarc"] == "p_reject", "the superseded run must not win"


def test_no_refs_is_an_empty_answer_not_a_query(store):
    """The empty peer set is reachable (a cohort below the floor) and must not build SQL with an
    empty IN-list, which is a syntax error in Postgres rather than an empty result."""
    assert store.bm_peer_signals([]) == {}
