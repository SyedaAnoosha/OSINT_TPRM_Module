"""Cohort persistence and the comparison API — including the refusals.

The cohort query has three exclusions that each look like an optimisation and are actually
correctness: a vendor is not its own peer, a blocked/refused score is not a low score, and a
re-scored vendor is one data point rather than one per run. Each has a test, because each would
silently skew a published percentile if it regressed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import app, store_dep
from app.benchmark import cohort_key
from app.models import PeerCohort, ProfileField, Score, VendorProfile, utcnow

# The four factors, as a tuple: (sector, revenue_band, employee_band, region).
TECH = ("technology", "large", "large", "anz")
BAKERY = ("food_agriculture", "micro", "micro", "anz")

# Every dimension of the exact cohort — what the ladder's top rung asks for.
EXACT = {"sector": "technology", "revenue_band": "large",
         "employee_band": "large", "region": "anz"}


@pytest.fixture
def client(store):
    """`store` comes from conftest — a fresh, disposable Postgres schema per test."""
    app.dependency_overrides[store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _profile(ref: str, dims: tuple | None = TECH, **kw) -> VendorProfile:
    cohort = None
    if dims:
        sector, rev, emp, region = dims
        cohort = PeerCohort(sector=sector, revenue_band=rev, employee_band=emp, region=region,
                            key=cohort_key(sector, rev, emp, region))
    return VendorProfile(
        vendor_ref=ref, cohort=cohort, completeness=0.8,
        sector=ProfileField(value=cohort.sector, source="firmographics") if cohort else None,
        **kw,
    )


def _score(ref: str, posture: int | None = 80, **kw) -> Score:
    return Score(vendor_ref=ref, posture=posture, grade="B", overall_confidence=0.9,
                 confidence_band="High", computed_at=utcnow(), **kw)


def _seed(store, ref: str, posture: int | None = 80, dims=TECH, **score_kw):
    store.put_profile(_profile(ref, dims))
    store.put_score(_score(ref, posture, **score_kw))


def _postures(store, dims: dict, exclude_ref: str | None = None) -> list[int]:
    return sorted(int(r["posture"]) for r in store.cohort_peers(dims, exclude_ref=exclude_ref))


# --------------------------------------------------------------------- the query


def test_cohort_peers_excludes_the_vendor_itself(store):
    """A vendor is not its own peer. Leaving it in guarantees a flattering percentile at small n."""
    for ref, posture in [("alpha", 90), ("beta", 70), ("gamma", 60)]:
        _seed(store, ref, posture)
    assert _postures(store, EXACT, exclude_ref="alpha") == [60, 70]
    assert _postures(store, EXACT) == [60, 70, 90]


def test_partial_dimensions_widen_the_population(store):
    """The widening ladder is a WHERE clause over fewer columns. Fewer dimensions means a broader
    population — that is exactly what 'compared against all regions' has to mean."""
    _seed(store, "anz_peer", 80, dims=("technology", "large", "large", "anz"))
    _seed(store, "us_peer", 70, dims=("technology", "large", "large", "north_america"))
    _seed(store, "us_smaller", 60, dims=("technology", "small", "medium", "north_america"))

    assert _postures(store, EXACT) == [80]
    assert _postures(store, {"sector": "technology", "revenue_band": "large",
                             "employee_band": "large"}) == [70, 80]
    assert _postures(store, {"sector": "technology"}) == [60, 70, 80]


def test_widening_never_crosses_industries(store):
    """Even at the widest rung the population stays inside one sector."""
    _seed(store, "tech", 80)
    _seed(store, "bakery", 55, dims=BAKERY)
    assert _postures(store, {"sector": "technology"}) == [80]


def test_blocked_and_refused_scores_are_not_peers(store):
    """"We could not assess this" is not "this is bad". Counting a sanctions block or a Ghost as a
    low posture would drag every cohort median down with absences of evidence."""
    _seed(store, "clean", 90)
    store.put_profile(_profile("blocked"))
    store.put_score(Score(vendor_ref="blocked", blocked=True, blocked_reason="sanctions",
                          posture=None, overall_confidence=0.0, confidence_band="Low"))
    store.put_profile(_profile("ghost"))
    store.put_score(Score(vendor_ref="ghost", posture=None, refused=True, ghost=True,
                          overall_confidence=0.2, confidence_band="Low"))

    assert _postures(store, EXACT) == [90]


def test_rescored_vendor_counts_once(store):
    """Scores are append-only, so a re-scored vendor has several rows. Only the latest is a peer —
    otherwise a frequently-re-scored vendor would dominate its own cohort's median."""
    _seed(store, "alpha", 60)
    store.put_score(_score("alpha", 85))
    assert _postures(store, EXACT) == [85]


def test_reprofiled_vendor_uses_its_current_cohort(store):
    """Profiles are append-only too: a company that grows moves cohort, and only the current
    profile decides which population it belongs to now."""
    _seed(store, "alpha", 75, dims=("technology", "medium", "medium", "anz"))
    assert _postures(store, EXACT) == []

    store.put_profile(_profile("alpha", TECH))
    assert _postures(store, EXACT) == [75]
    assert _postures(store, {"sector": "technology", "employee_band": "medium"}) == []


def test_unclassified_vendors_are_in_no_cohort(store):
    store.put_profile(_profile("alpha", dims=None))
    store.put_score(_score("alpha", 75))
    assert _postures(store, {"sector": "technology"}) == []


def test_unknown_dimension_is_rejected(store):
    with pytest.raises(ValueError, match="unknown cohort dimension"):
        store.cohort_peers({"turnover": "large"})


def test_profiles_are_append_only(store):
    store.put_profile(_profile("alpha"))
    with pytest.raises(Exception, match="append-only"):
        store._conn.execute("UPDATE vendor_profiles SET sector='x'")
    with pytest.raises(Exception, match="append-only"):
        store._conn.execute("DELETE FROM vendor_profiles")


def test_latest_profile_round_trips(store):
    store.put_profile(_profile("alpha"))
    got = store.latest_profile("alpha")
    assert got.vendor_ref == "alpha"
    assert got.cohort.key == cohort_key(*TECH)
    assert got.cohort.revenue_band == "large" and got.cohort.employee_band == "large"


# --------------------------------------------------------------------- the API


def test_profile_endpoint_404s_before_a_score(client):
    assert client.get("/api/vendors/nobody/profile").status_code == 404


def test_a_three_peer_cohort_publishes_no_placement(client, store):
    """RESTORED AT E11, as the version of this test written under `min_cohort_n: 1` said it should
    be.

    That version recorded a deliberate behaviour change: at a threshold of 1, three peers cleared
    the bar and nothing was refused, so the honest property available at that setting was
    DISCLOSURE rather than refusal. It ended with "E11 raises the threshold and refusal becomes
    reachable again — at which point this test should be restored." This is that.

    Three real peers is now below the floor of 8, so the cohort falls through to the labelled
    reference baseline — which publishes NO ordinal placement at all. A percentile over three
    companies and a percentile over six invented ones are the same error, and neither is
    recoverable by a caption.
    """
    for i in range(3):
        _seed(store, f"peer{i}", 70 + i)
    _seed(store, "subject", 80)

    body = client.get("/api/vendors/subject/benchmark").json()
    assert body["available"] is True, "the card still renders — with context instead of a rank"
    assert body["synthetic"] is True
    assert body["percentile"] is None, "a placement over three peers is noise in a costume"
    assert body["quartile"] is None
    assert body["variance_from_median"] is None
    assert any("NOT REAL PEERS" in c for c in body["caveats"])


def test_benchmark_publishes_once_the_cohort_is_deep_enough(client, store):
    for i in range(10):
        _seed(store, f"peer{i}", 60 + i)
    _seed(store, "subject", 80)

    body = client.get("/api/vendors/subject/benchmark").json()
    assert body["available"] is True
    assert body["stats"]["n"] == 10
    assert body["percentile"] == 100          # 80 beats every peer (60-69)
    assert body["quartile"] == 4
    assert body["variance_from_median"] > 0
    assert body["widened"] is False
    # The cohort travels with the number: a percentile whose population is hidden is a black box.
    assert body["stats"]["cohort"]["key"] == cohort_key(*TECH)
    # And the standing limitation is never omitted.
    assert any("random sample" in c for c in body["caveats"])


def test_benchmark_widens_and_says_so(client, store):
    """The exact four-factor cohort rarely fills — 1,500 of them exist. Widening is what makes the
    feature work, and disclosure is what keeps it honest."""
    # No peer shares the exact four-factor cohort — the subject is excluded from its own lookup,
    # so the exact rung returns nothing and the ladder MUST drop region to find anyone. Seeding a
    # same-cohort peer here would satisfy the exact rung at the shipped `min_cohort_n: 1` and the
    # widening this test exists to observe would never run.
    _seed(store, "subject", 80)
    for i in range(9):   # same industry + sizes, different region
        _seed(store, f"us{i}", 60 + i, dims=("technology", "large", "large", "north_america"))

    body = client.get("/api/vendors/subject/benchmark").json()
    assert body["available"] is True
    assert body["widened"] is True
    assert "all regions" in body["level"]
    assert any("wider population" in c for c in body["caveats"])


def test_peers_endpoint_returns_only_the_cohort(client, store):
    _seed(store, "subject", 80)
    _seed(store, "same_cohort", 70)
    _seed(store, "other_cohort", 95, dims=("food_agriculture", "small", "small", "anz"))

    body = client.get("/api/vendors/subject/peers").json()
    refs = {p["vendor_ref"] for p in body["peers"]}
    assert refs == {"subject", "same_cohort"}
    assert "other_cohort" not in refs
    # RAISED AT E11 and now floored in code, not only in YAML — see
    # test_benchmark.test_the_peer_floor_cannot_be_lowered_by_a_config_edit. The endpoint
    # publishes it because a reader comparing two vendors needs to know what bar each cleared.
    assert body["min_cohort_n"] == 8


def test_compare_refuses_across_cohorts(client, store):
    """Google vs the local bakery, as an API contract rather than a documentation note."""
    _seed(store, "big_tech", 88)
    _seed(store, "local_bakery", 55, dims=BAKERY)

    r = client.post("/api/compare", json={"refs": ["big_tech", "local_bakery"]})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "not_comparable"
    assert "different peer cohorts" in detail["reason"]
    # Both cohorts are named, so the caller can see exactly why rather than being told "no".
    assert set(detail["cohorts"]) == {"big_tech", "local_bakery"}


def test_compare_refuses_unclassified_vendors(client, store):
    _seed(store, "known", 80)
    store.put_profile(_profile("unknown", dims=None))
    store.put_score(_score("unknown", 90))

    r = client.post("/api/compare", json={"refs": ["known", "unknown"]})
    assert r.status_code == 409
    assert r.json()["detail"]["vendors"] == ["unknown"]


def test_compare_within_a_cohort_ranks_by_posture(client, store):
    _seed(store, "strong", 92)
    _seed(store, "middling", 74)
    _seed(store, "weak", 51)

    body = client.post("/api/compare",
                       json={"refs": ["middling", "weak", "strong"]}).json()
    assert body["comparable"] is True
    assert [v["vendor_ref"] for v in body["vendors"]] == ["strong", "middling", "weak"]
    assert body["cohort"] == cohort_key(*TECH)
    assert body["cohort_median"] == 74


def test_compare_needs_two_vendors(client, store):
    _seed(store, "alpha", 80)
    assert client.post("/api/compare", json={"refs": ["alpha"]}).status_code == 422
