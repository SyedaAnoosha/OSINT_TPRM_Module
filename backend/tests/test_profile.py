"""Profile, industry classification and size banding.

THE FIRST TEST IN THIS FILE IS THE POINT OF THE FILE. `test_profile_never_moves_a_score` replays
every corpus vendor with and without firmographics and requires a byte-identical Score. Everything
else here is ordinary coverage; that one is the guard on methodology §7.3 — coverage already
tracks company size rather than company risk, and letting revenue or headcount touch the arithmetic
would let that bias in one level up, where it would be much harder to see.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app import industry as ind
from app.benchmark import employee_band_for, revenue_band_for
from app.collectors import _wikidata as wd
from app.models import CollectorResult, PeerCohort, Vendor
from app.profile import build_profile, refresh_cohort
from app.scoring import ScoringEngine
from tests.test_corpus import AS_AT, VENDOR_REFS, load_fixture

FETCHED = datetime(2026, 7, 24, tzinfo=UTC)


def _result(source: str, raw: dict) -> CollectorResult:
    return CollectorResult(source=source, vendor_ref="acme", status="ok", fetched_at=FETCHED,
                           raw=raw, reliability=0.8)


def _firmographics(**over) -> CollectorResult:
    raw = {"qid": "Q42", "label": "Acme", "industry": ["enterprise software"],
           "country": ["Australia"], "employees": 500, "revenue": 50_000_000,
           "revenue_currency": "AUD", "ownership": "unknown", "parent": [], "listed_on": []}
    raw.update(over)
    return _result("firmographics", raw)


def test_search_name_is_persisted_for_replay():
    """The name a run resolved WITH is stored on the profile, so a later domain-only re-score (the
    continuous monitor, a dispute re-score) can replay it instead of the domain slug. Proven live on
    Archer: 'Archer Technologies' resolves the US parent where the slug 'archerirm' matched the
    Indian subsidiary — and `pipeline.run_pipeline` recovers this value before collection."""
    named = build_profile(Vendor(ref="archer", name="Archer Technologies", domain="archerirm.com"),
                          [_firmographics()])
    assert named.search_name == "Archer Technologies"

    # A genuinely domain-only run stores no search name — there is nothing from that run to replay.
    anon = build_profile(Vendor(ref="archer", domain="archerirm.com"), [_firmographics()])
    assert anon.search_name is None


# --------------------------------------------------------------------- THE GUARD


@pytest.mark.parametrize("ref", VENDOR_REFS)
def test_profile_never_moves_a_score(ref):
    """A firmographic must never change a penalty, a posture, a grade or the confidence axis.

    The firmographics collector emits NO findings, so adding it to a run cannot reach the engine.
    This asserts that structurally rather than trusting it: score each corpus vendor, then score
    it again with a full firmographic payload appended, and require the two Scores to be identical
    — including `overall_confidence`, since a collector that emitted findings would move coverage
    even if every band happened to be a `pass`.
    """
    vendor, results = load_fixture(ref)
    baseline = ScoringEngine().score(vendor, results, now=AS_AT).score

    enriched = [*results, _firmographics(), _result("abn", {"abn": "11111111111"})]
    with_profile = ScoringEngine().score(vendor, enriched, now=AS_AT).score

    # `computed_at` is wall-clock and differs between any two runs; everything else — posture,
    # grade, confidence, ceiling, and every per-category penalty — must be identical.
    drop = {"computed_at"}
    assert {k: v for k, v in with_profile.model_dump().items() if k not in drop} == \
           {k: v for k, v in baseline.model_dump().items() if k not in drop}, (
        f"{ref}: profile context changed the score — a firmographic reached the engine"
    )


def test_firmographics_collector_emits_no_findings():
    """The structural reason the guard above holds. If this ever fails, the guard is load-bearing
    rather than belt-and-braces, and the collector has become a scorer by accident."""
    from app.collectors import get_collector

    collector = get_collector("firmographics")
    assert collector is not None
    # A collector that emits nothing also cannot move the confidence axis: coverage counts
    # normalized findings, so zero findings means zero effect on either axis.
    assert collector.result(Vendor(ref="acme"), "ok", raw={"qid": "Q1"}).findings == []


# --------------------------------------------------------------------- stale-source handling


def _entity(claims: list[tuple[float, str | None, str]]) -> dict:
    """A Wikidata entity with a P1128 time series: (amount, point-in-time, rank)."""
    return {"claims": {"P1128": [
        {"rank": rank,
         "mainsnak": {"datavalue": {"value": {"amount": f"+{amount}", "unit": "1"}}},
         **({"qualifiers": {"P585": [{"datavalue": {"value": {"time": f"+{when}T00:00:00Z"}}}]}}
            if when else {})}
        for amount, when, rank in claims
    ]}}


def test_latest_dated_claim_wins():
    """Found live on Atlassian: P1128 carries TEN claims spanning 2012-2022, and reading the first
    returned 1,100 — a March 2015 figure shown as current, and used to pick a peer group."""
    entity = _entity([(1100, "2015-03-00", "normal"),
                      (8179, "2022-04-28", "normal"),
                      (4907, "2020-00-00", "preferred")])
    amount, _unit, as_of = wd.claim_amount(entity, wd.P_EMPLOYEES)
    assert amount == 8179
    assert as_of == "2022-04-28"


def test_deprecated_claims_are_skipped():
    entity = _entity([(999999, "2025-01-01", "deprecated"), (8179, "2022-04-28", "normal")])
    assert wd.claim_amount(entity, wd.P_EMPLOYEES)[0] == 8179


def test_undated_claim_loses_to_a_dated_one():
    """A figure someone bothered to date is the figure they meant to be read as current."""
    entity = _entity([(500, None, "normal"), (8179, "2022-04-28", "normal")])
    assert wd.claim_amount(entity, wd.P_EMPLOYEES)[0] == 8179


def test_as_of_reaches_the_profile():
    """The date must travel with the number all the way to the card. `fetched_at` says when we read
    Wikidata; `as_of` says how old the fact is, and only the second one tells a reader to doubt it."""
    profile = build_profile(Vendor(ref="acme", name="Acme", domain="acme.com"),
                            [_firmographics(employees=8179, employees_as_of="2022-04-28")])
    assert profile.employees.value == 8179
    assert profile.employees.as_of == "2022-04-28"


# --------------------------------------------------------------------- assembly


def test_build_profile_reconciles_sources_by_authority():
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    results = [
        _result("gleif", {"resolved": {"legalName": "ACME PTY LTD", "lei": "X" * 20,
                                       "jurisdiction": "AU"}}),
        _firmographics(),
    ]
    profile = build_profile(vendor, results, criticality="high", substitutability="sole_source")

    assert profile.legal_name.value == "ACME PTY LTD"
    assert profile.legal_name.source == "gleif"      # a register beats a community wiki
    assert profile.country.value == "AU"
    assert profile.employees.value == 500
    assert profile.employees.source == "firmographics"  # ...where the register holds nothing
    assert profile.criticality == "high"
    # P8 — same client-supplied, never-inferred path as criticality.
    assert profile.substitutability == "sole_source"
    assert profile.sector.value == "technology"
    assert profile.cohort.key == "technology|rev=medium|emp=medium|anz"


def test_substitutability_defaults_to_undeclared():
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    profile = build_profile(vendor, [])
    assert profile.substitutability is None


def test_abn_overrides_gleif_for_australian_entities():
    """The ABR is the Commonwealth's own register: for an AU entity its name and country win."""
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com.au")
    results = [
        _result("gleif", {"resolved": {"legalName": "ACME INTERNATIONAL", "lei": "Y" * 20,
                                       "jurisdiction": "US-DE"}}),
        _result("abn", {"abn": "51824753556", "entity_name": "ACME AUSTRALIA PTY LTD"}),
    ]
    profile = build_profile(vendor, results)
    assert profile.legal_name.value == "ACME AUSTRALIA PTY LTD"
    assert profile.country.value == "AU"


def test_unclassifiable_vendor_gets_a_defaulted_sector_that_is_marked_as_defaulted():
    """BEHAVIOUR CHANGE, recorded deliberately (E0.1).

    This required `sector is None` and `cohort is None` — the argument being that a guessed sector
    produces a confident comparison against the wrong population. The shipped code now falls back
    to `technology` so every vendor gets a comparison.

    That argument was right, and the mitigation is that the guess is LABELLED: the fallback writes
    `source="default"` onto the sector field, and downstream the synthetic-peer path adds a
    "NOT REAL PEERS" caveat. So the property worth pinning is traceability of the guess.
    E11 decides whether to keep the fallback or restore the refusal.
    """
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    profile = build_profile(vendor, [_firmographics(industry=["unclassifiable widgetry"])])
    assert profile.sector.value == "technology"
    assert profile.sector.source == "default", (
        "a guessed sector MUST be distinguishable from an observed one, or the cohort key asserts "
        "a fact nobody established"
    )
    assert profile.cohort is not None


def test_missing_size_falls_back_to_a_medium_headcount_band():
    """BEHAVIOUR CHANGE, recorded deliberately (E0.1) — and the weaker half of it.

    Unlike the sector fallback, the headcount fallback leaves NO mark: `emp=medium` in the cohort
    key reads identically whether it was measured or invented. Pinned here so the gap is visible
    and E11 has a failing test to change when it either marks or removes the default.
    """
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    profile = build_profile(vendor, [_firmographics(employees=None, revenue=None)])
    assert profile.sector.value == "technology"
    assert profile.cohort is not None
    assert profile.cohort.employee_band == "medium"
    assert profile.employees is None, (
        "the FALLBACK must not write itself back as an observation — the cohort may say medium, "
        "but the profile must still show that no headcount was ever observed"
    )
    # Revenue, by contrast, is not invented.
    assert profile.cohort.revenue_band is None
    assert "rev=?" in profile.cohort.key


def test_client_size_override_forms_a_cohort_that_public_data_could_not():
    """The measured gap: Wikidata publishes an industry far more often than a headcount, so many
    real vendors have a sector and no size. Without an override they would never get a comparison.
    """
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    no_size = _firmographics(employees=None, revenue=None)

    # Without an override the headcount band is FABRICATED as medium (E0.1 — see
    # test_missing_size_falls_back_to_a_medium_headcount_band). The override replaces a guess with
    # something a buyer actually asserted, which is the whole point of the feature.
    assert build_profile(vendor, [no_size]).cohort.employee_band == "medium"
    profile = build_profile(vendor, [no_size], size_band="large")
    # The override sets headcount — the dimension a buyer can actually speak to. Revenue stays
    # unknown and is written as `?`, so the key never pretends to a figure nobody supplied.
    assert profile.cohort.key == "technology|rev=?|emp=large|anz"


def test_client_size_override_wins_over_observed():
    """A buyer stating the band may be describing the local subsidiary they actually contract with
    rather than the global parent Wikidata describes. The observed figures stay on the profile so a
    reader can see both and disagree."""
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    profile = build_profile(vendor, [_firmographics(employees=500)], size_band="micro")
    assert profile.cohort.employee_band == "micro"
    assert profile.employees.value == 500, "the observed figure must remain visible"


def test_client_sector_override_is_recorded_as_client_supplied():
    """An override must never masquerade as an observation."""
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    profile = build_profile(vendor, [_firmographics(industry=["unmappable"])],
                            sector="healthcare", size_band="small")
    assert profile.sector.value == "healthcare"
    assert profile.sector.source == "client"
    assert profile.cohort.key == "healthcare|rev=medium|emp=small|anz"


def test_completeness_reports_what_was_actually_found():
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    thin = build_profile(vendor, [_firmographics(employees=None, revenue=None, country=[])])
    full = build_profile(vendor, [
        _result("gleif", {"resolved": {"legalName": "ACME", "lei": "Z" * 20, "jurisdiction": "AU"}}),
        _firmographics(listed_on=["Australian Securities Exchange"], ownership="listed"),
    ])
    assert 0.0 < thin.completeness < full.completeness <= 1.0


# --------------------------------------------------------------------- classification


@pytest.mark.parametrize("label,expected", [
    ("enterprise software", "technology"),
    ("cloud computing", "technology"),
    ("banking", "financial_services"),
    ("health care", "healthcare"),
    ("food manufacturing", "food_agriculture"),
    ("telecommunications", "telecommunications"),
    ("management consulting", "professional_services"),
    ("something entirely unmapped", None),
])
def test_sector_from_label(label, expected):
    assert ind.sector_from_label(label) == expected


def test_accounting_software_is_technology_not_financial_services():
    """A vendor's own industry, not its customers'. MYOB sells software to accountants; it is a
    software company, and filing it with banks would put it in the wrong peer group AND, later,
    under the wrong industry severity profile."""
    assert ind.sector_from_label("accounting software") == "technology"


def test_anzsic_class_beats_division():
    """ANZSIC division M is 'Professional, Scientific and Technical Services' — where most AU
    software companies are registered. Without the class, every AU SaaS vendor would be filed as
    professional services and benchmarked against law firms."""
    assert ind.sector_from_anzsic("M") == "professional_services"
    assert ind.sector_from_anzsic("7000") == "technology"


@pytest.mark.parametrize("country,region", [
    ("AU", "anz"), ("NZ", "anz"), ("US", "north_america"),
    ("GB", "uk_eu"), ("DE", "uk_eu"), ("SG", "apac"),
    ("ZW", "other"), (None, "other"),
])
def test_region_is_regulatory_not_geographic(country, region):
    assert ind.region_for(country) == region


# --------------------------------------------------------------------- size bands


@pytest.mark.parametrize("employees,band", [
    (5, "micro"), (50, "small"), (500, "medium"), (5000, "large"), (230000, "mega"),
])
def test_employee_band(employees, band):
    assert employee_band_for(employees) == band


def test_revenue_and_headcount_stay_separate_dimensions():
    """The two disagree often, and the disagreement is informative: a 40-person firm at $400M is a
    high-leverage money mover; a 4,000-person firm at $400M is a large employer with a large attack
    surface. An earlier design collapsed them to one band and lost that distinction."""
    profile = build_profile(
        Vendor(ref="acme", name="Acme", domain="acme.com"),
        [_firmographics(employees=40, revenue=400_000_000, revenue_currency="AUD")],
    )
    assert profile.cohort.employee_band == "small"
    assert profile.cohort.revenue_band == "large"
    assert profile.cohort.key == "technology|rev=large|emp=small|anz"


def test_cohort_forms_with_only_one_size_dimension():
    """Requiring both would rarely form a cohort — public sources publish headcount far more often
    than private-company revenue."""
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com")
    headcount_only = build_profile(vendor, [_firmographics(revenue=None)])
    assert headcount_only.cohort.employee_band == "medium"
    assert headcount_only.cohort.revenue_band is None
    assert headcount_only.cohort.key == "technology|rev=?|emp=medium|anz"

    revenue_only = build_profile(vendor, [_firmographics(employees=None)])
    assert revenue_only.cohort.revenue_band is not None
    # E0.1: was `is None`. An absent headcount now falls back to `medium` rather than staying
    # unknown, so a revenue-only profile still carries an invented headcount band.
    assert revenue_only.cohort.employee_band == "medium"
    assert revenue_only.employees is None, "the fallback must not masquerade as an observation"


def test_stale_schema_cohort_is_repaired_on_read():
    """A profile written under the three-factor cohort model deserialises with both size bands
    None. It rendered as a LIVE cohort reading 'headcount unknown · revenue unknown', matched no
    peers at any width, and blamed the population — *'insufficient peers'* — for a schema change.
    `refresh_cohort` re-derives it from the observations the profile already holds."""
    profile = build_profile(Vendor(ref="acme", name="Acme", domain="acme.com"), [_firmographics()])
    # Simulate the legacy row: a cohort with a sector and region but neither size dimension.
    profile.cohort = PeerCohort(sector="technology", revenue_band=None, employee_band=None,
                                region="anz", key="technology|medium|anz")

    repaired = refresh_cohort(profile)
    assert repaired.cohort.employee_band == "medium"
    assert repaired.cohort.key == "technology|rev=medium|emp=medium|anz"


def test_repair_rewrites_a_legacy_cohort_into_the_current_four_factor_shape():
    """E0.1: was `cohort is None`. Repair no longer yields nothing — it re-derives, which under
    the current fallbacks always produces a cohort. What it must still do is stop a legacy
    three-factor key surviving as though it were current."""
    profile = build_profile(Vendor(ref="acme", name="Acme", domain="acme.com"),
                            [_firmographics(employees=None, revenue=None)])
    profile.cohort = PeerCohort(sector="technology", region="anz", key="technology|medium|anz")
    repaired = refresh_cohort(profile).cohort
    assert repaired is not None
    assert repaired.key != "technology|medium|anz", "the legacy key must not survive repair"
    assert "rev=?" in repaired.key, "repair must write the current four-factor shape"


def test_repair_leaves_a_current_cohort_untouched():
    profile = build_profile(Vendor(ref="acme", name="Acme", domain="acme.com"), [_firmographics()])
    before = profile.cohort.model_dump()
    assert refresh_cohort(profile).cohort.model_dump() == before


def test_no_size_signal_at_all_still_forms_a_cohort_on_an_invented_band():
    """E0.1 — the sharpest statement of the open item.

    The original argument stands on its merits: an industry with no size is not a peer group, and
    pooling a two-person consultancy with a global bank on a shared sector label is exactly what
    a cohort is supposed to prevent. The shipped code does it anyway, on a `medium` band nobody
    observed.

    Downstream this is partly caught — with no real peers the comparison goes synthetic and is
    labelled "NOT REAL PEERS". But the COHORT KEY still asserts a size. Recorded here so E11
    resolves it deliberately rather than inheriting it.
    """
    profile = build_profile(Vendor(ref="acme", name="Acme", domain="acme.com"),
                            [_firmographics(employees=None, revenue=None)])
    assert profile.sector.value == "technology"
    assert profile.cohort is not None
    assert profile.cohort.employee_band == "medium"
    assert profile.employees is None and profile.revenue is None, (
        "no size was observed — the cohort asserts one anyway, and that is the open item"
    )


def test_revenue_converts_for_banding_only():
    # US$50M ~ A$77M: medium under the AUD bands, and it must be banded on the converted figure
    # rather than on the raw number, or every US vendor lands a band too low.
    assert revenue_band_for(50_000_000, "USD") == "medium"


def test_unknown_currency_does_not_guess():
    """An unconvertible revenue yields no band rather than being treated as AUD."""
    assert revenue_band_for(50_000_000, "XBT") is None
