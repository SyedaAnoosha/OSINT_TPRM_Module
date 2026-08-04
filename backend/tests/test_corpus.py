"""Regression corpus — the baseline that makes every scoring change legible.

TWO HALVES, AND THE DIFFERENCE BETWEEN THEM IS THE POINT
--------------------------------------------------------
`VENDOR_REFS` — five REAL vendors (methodology §2.3), collector output captured live once and
frozen. This half is EVIDENCE. It is what makes a claim about the model's behaviour on real
companies checkable.

`ARCHETYPE_REFS` — five SYNTHETIC vendors, constructed by `tests/build_archetypes.py` and added
at E0.2. This half is not evidence and never pretends to be: reserved `.example` domains,
`synthetic_` refs, `(synthetic)` in every name, and a `synthetic` block in every fixture.

The split exists because the real five are all large, all well-run, all confidence 0.93-0.96 and
all grade A/B. They cannot observe a Ghost, a gated vendor, a small supplier, a ceiling case or
the bottom of the scale — **so E1 through E5 each re-goldened against a corpus that structurally
could not disagree with them about small vendors.** The archetypes close that hole for the ENGINE
paths. They close nothing about whether the model's ordering is correct; only E0.4's outcome
labels can, and those do not exist.

Tests assert against whichever half the property belongs to. `test_confidence_bands_are_reachable_
on_real_collection` stays on the real five, because "a fully-collected vendor bands High" is a
claim about real collection — asserting it over a deliberate Ghost would be nonsense. Properties
that must hold for ANY input (receipts add up, no orphan signals, sector never moves a score) run
over `ALL_REFS`.

Each fixture is replayed through the REAL engine and compared against `fixtures/golden_scores.json`.
A model change that moves a number fails here and the diff names the vendor and the category that
moved — an intended re-grade and a regression look different.

Determinism matters more than freshness: the fixtures never change, and the clock is pinned to
`AS_AT` so age decay cannot drift the expected numbers by the day.

To re-baseline after an INTENDED model change:
    python -m tests.regolden          (from backend/, with the venv active)
then read the git diff of golden_scores.json before committing it. That diff is the change.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models import CollectorResult, Vendor
from app.scoring import ScoringEngine
from app.scoring_config import get_scoring_config

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden_scores.json"

# The clock every corpus run is measured against. Pinned to the capture date so a breach's age
# decay is identical today and in a year. Bump it only when re-capturing the fixtures.
AS_AT = datetime(2026, 7, 23, tzinfo=UTC)

VENDOR_REFS = ["atlassian", "myob", "onetrust", "slack", "snowflake"]

# E0.2. Constructed, not captured — see tests/build_archetypes.py for the spec and the reasoning.
# Kept as a SEPARATE list, deliberately: a test that says "on real collection" must be able to say
# so, and merging the two lists would quietly weaken every such assertion to "on some fixture".
ARCHETYPE_REFS = [
    "synthetic_ghost",     # thin coverage, looks clean -> refused, never published
    "synthetic_gated",     # sanctions hit -> blocked, no score at all
    "synthetic_smallco",   # small supplier doing the free things right -> the E2 fairness proof
    "synthetic_weak",      # expired cert -> the critical ceiling actually biting
    "synthetic_floor",     # comprehensively bad -> the bottom of the scale
]

ALL_REFS = VENDOR_REFS + ARCHETYPE_REFS


def load_fixture(ref: str) -> tuple[Vendor, list[CollectorResult]]:
    payload = json.loads((FIXTURES / f"{ref}.json").read_text(encoding="utf-8"))
    v = payload["vendor"]
    vendor = Vendor(ref=v["ref"], name=v["name"], domain=v["domain"],
                    resolved=True, resolution_confidence=1.0)
    return vendor, [CollectorResult.model_validate(r) for r in payload["results"]]


def score_fixture(ref: str) -> dict:
    """Score one fixture down to the numbers we hold stable. Shared with tests/regolden.py."""
    vendor, results = load_fixture(ref)
    score = ScoringEngine().score(vendor, results, now=AS_AT).score
    return {
        "posture": score.posture,
        "grade": score.grade,
        "confidence": round(score.overall_confidence, 3),
        "confidence_band": score.confidence_band,
        "refused": score.refused,
        "ghost": score.ghost,
        "blocked": score.blocked,
        "critical_ceiling_applied": score.critical_ceiling_applied,
        "categories": {
            c.category: {"posture": c.posture, "penalty": round(c.penalty, 2),
                         "coverage": round(c.coverage, 3), "findings": c.findings}
            for c in score.categories
        },
    }


@pytest.fixture(scope="module")
def golden() -> dict:
    if not GOLDEN.exists():
        pytest.fail(f"{GOLDEN.name} missing — run `python -m tests.regolden` to create it")
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("ref", ALL_REFS)
def test_vendor_scores_match_the_baseline(ref: str, golden: dict) -> None:
    """The headline numbers for a real vendor must not move unnoticed."""
    actual, expected = score_fixture(ref), golden[ref]
    for key in ("posture", "grade", "confidence", "confidence_band",
                "refused", "ghost", "blocked", "critical_ceiling_applied"):
        assert actual[key] == expected[key], (
            f"{ref}: {key} moved {expected[key]!r} -> {actual[key]!r}. "
            "If intended, re-baseline with `python -m tests.regolden`."
        )


@pytest.mark.parametrize("ref", ALL_REFS)
def test_category_penalties_match_the_baseline(ref: str, golden: dict) -> None:
    """Per-category penalties too — this is what localises a change to one category."""
    actual, expected = score_fixture(ref)["categories"], golden[ref]["categories"]
    assert set(actual) == set(expected), f"{ref}: category set changed"
    for cat, exp in expected.items():
        assert actual[cat] == exp, (
            f"{ref} / {cat}: {exp} -> {actual[cat]}. "
            "If intended, re-baseline with `python -m tests.regolden`."
        )


def test_scoring_is_deterministic_for_a_fixed_clock() -> None:
    """Same fixture + same `now` must give the same score, or the corpus proves nothing."""
    assert score_fixture("atlassian") == score_fixture("atlassian")


@pytest.mark.parametrize("ref", ALL_REFS)
def test_stored_findings_reconstruct_the_category_penalties(ref: str) -> None:
    """Finding A, as arithmetic: the receipts must ADD UP to the published score.

    `effective_penalty` is what was actually charged after the NIST modifiers and after the
    (category, signal) group collapsed to its worst member. Summing it per category must equal
    that category's penalty exactly. The base `penalty` cannot do this — a decayed breach carries
    a -40 base against a category that lost -16 — which is why it is stored alongside, not instead.
    """
    vendor, results = load_fixture(ref)
    out = ScoringEngine().score(vendor, results, now=AS_AT)
    published = {c.category: round(c.penalty, 2) for c in out.score.categories}

    rebuilt: dict[str, float] = {}
    for nf in out.normalized:
        if not nf.is_sanctions:
            rebuilt[nf.category] = rebuilt.get(nf.category, 0.0) + nf.effective_penalty

    for cat, expected in published.items():
        assert round(rebuilt.get(cat, 0.0), 2) == expected, (
            f"{ref} / {cat}: receipts sum to {rebuilt.get(cat, 0.0):.2f} but the category "
            f"published {expected:.2f} — the stored record cannot reproduce the score"
        )


def test_confidence_bands_are_reachable_on_real_collection() -> None:
    """The confidence bands must be CALIBRATED, not decorative.

    `coverage = covered_signals / 26 planned`. If the denominator ever grows past what a real
    collection run can return, `High` becomes unreachable, every vendor bands `Low`, and the
    Ghost — the product's strongest honesty claim — fires on everything and means nothing.

    Measured on the frozen corpus: real vendors return 0.96-1.00 and band High, so the bands work
    as designed. This test fails if a future signal is added to scoring.yaml with no collector to
    feed it, which is exactly how that denominator would silently rot.
    """
    for ref in VENDOR_REFS:
        s = score_fixture(ref)
        assert s["confidence"] >= 0.90, (
            f"{ref}: coverage {s['confidence']} — a fully-collected vendor no longer reaches High. "
            "A signal was likely added to scoring.yaml with nothing to collect it."
        )
        assert s["confidence_band"] == "High"
        assert s["ghost"] is False, f"{ref}: a fully-collected vendor must not be a Ghost"
        assert s["refused"] is False


@pytest.mark.parametrize("ref", ALL_REFS)
def test_every_emitted_signal_has_a_home_in_the_model(ref: str) -> None:
    """The drift guard, pointing the other way.

    `ScoringConfig` refuses config the engine never reads. This is its mirror: a COLLECTOR
    emitting a signal the model has no band for. That failure is quieter — the normaliser logs a
    warning and drops the finding — so it survived a whole release: GDELT emitted `tone_volume`,
    scoring.yaml had no home for it, and "held, not scored" was achieved by the model failing to
    recognise the signal rather than by the collector declining to score it.

    A held source must emit NO findings (its candidates live in `raw`, captured but unscoreable).
    A scoring source must emit only signals the model bands. There is no third option.

    The check is on the SIGNAL, not on the collector's declared category. Since E5 the model
    decides where a signal lives (`ScoringConfig.category_of`), so a finding whose `_CAT` constant
    predates a recategorisation is scored correctly and is not drift. What still IS drift, and
    what this guard exists to catch, is a signal the model has no band for anywhere.
    """
    cfg = get_scoring_config()
    _, results = load_fixture(ref)
    unknown = [
        f"{r.source}.{f.signal}"
        for r in results for f in r.findings
        if f.category and f.category != "regulatory_legal_sanctions"
        and cfg.category_of(f.signal) is None
    ]
    assert not unknown, (
        f"{ref}: collector(s) emit signals the model cannot score: {sorted(set(unknown))}. "
        "Either add the band to scoring.yaml, or stop emitting the finding and keep the "
        "observation in `raw` — silently dropping it is how a source ends up 'held' by accident."
    )


def test_mitigation_is_still_dormant_across_every_real_vendor() -> None:
    """The mitigation factor (x0.6) is LIVE in the engine but has no data to feed it.

    Nothing we lawfully collect evidences that a vendor fixed a given issue: KEV says a product
    line is known-exploited, NVD says a CVE exists. Neither observes whether THIS vendor patched.
    The two bands that used to imply otherwise were removed in v4.1.0 — one was dead config no
    collector emitted, the other was `remediated`, which only ever meant "below CVSS HIGH".

    This test is the guard on that story. If a collector later sets `remediation_evidenced`, it
    fails — forcing the docs and the Methodology page to be corrected in the SAME change, instead
    of the claim quietly becoming false again. That silent drift is how two NIST variables sat
    inert for a whole release while the documentation advertised them as applied.

    To retire it: wire a source that CORROBORATES a fix (not a vendor's own claim — mitigation
    exists precisely to reward corroboration over assertion), then update this test, methodology
    §5.3 and the MethodologyPage wording together.
    """
    for ref in VENDOR_REFS:
        _, results = load_fixture(ref)
        claimed = [f"{r.source}.{f.signal}" for r in results for f in r.findings
                   if f.remediation_evidenced]
        assert not claimed, (
            f"{ref}: {claimed} now claims evidenced remediation. Mitigation is no longer dormant — "
            "update methodology.md §5.3 and the MethodologyPage NIST card in this same change."
        )


def test_no_fixture_has_quietly_disappeared() -> None:
    """A deleted fixture must fail loudly, not shrink the corpus in silence."""
    for ref in ALL_REFS:
        assert (FIXTURES / f"{ref}.json").exists(), f"fixture {ref}.json is missing"
        _, results = load_fixture(ref)
        assert len(results) >= 10, f"{ref}: only {len(results)} collector results captured"


# --------------------------------------------------------------------- E0.2: the archetypes


def test_the_corpus_actually_covers_the_archetypes() -> None:
    """The test whose NAME was already this, and whose body checked something else.

    Before E0.2 this asserted only that five fixtures existed with >=10 results each. It passed
    for a year against a corpus containing no Ghost, no gated vendor, no small vendor and no bad
    vendor — the exact four E0.2 was written to add. A test named for a property it does not check
    is worse than no test, because the status table reads green.

    Now it checks the archetypes are actually PRESENT AND DISTINCT, by behaviour rather than by
    filename. Deleting a fixture, or neutering one until it no longer exercises its path, fails.
    """
    scored = {ref: score_fixture(ref) for ref in ALL_REFS}

    ghosts = [r for r, s in scored.items() if s["ghost"] and s["refused"]]
    blocked = [r for r, s in scored.items() if s["blocked"]]
    ceilinged = [r for r, s in scored.items() if s["critical_ceiling_applied"]]
    published = [s["posture"] for s in scored.values() if s["posture"] is not None]

    assert ghosts, "no Ghost in the corpus — the refusal path is unpinned"
    assert blocked, "no gated vendor — the sanctions gate is unpinned"
    assert ceilinged, "no ceiling case — the knockout is unpinned"
    assert max(published) >= 90, "nothing exercises the top of the scale"

    # E7 MOVED THIS THRESHOLD AND THAT IS A FINDING, NOT A TEST BEING LOOSENED.
    # `synthetic_floor` published 16 at v5.1.0 and publishes 39 at v5.2.0. Nothing about the
    # vendor changed: diminishing returns (E7a) stopped its many findings from stacking linearly,
    # so a comprehensively badly-run vendor — credential breach, KEV listing, TLS 1.0, no email
    # authentication, abandoned estate, regulator enforcement — now lands in grade D rather than F.
    #
    # That is the compression E13's bounded log-odds exists to fix, and E7 has made it worse
    # before it makes it better. The threshold is 45 rather than 30 to record where the bottom
    # actually is; if it climbs again, E13 has become urgent rather than scheduled.
    assert min(published) < 45, (
        f"lowest published posture is {min(published)}. The scale is compressing at the bottom — "
        f"see E13. If this keeps rising, triage stops working precisely where it matters most."
    )
    assert max(published) - min(published) >= 50, "the corpus no longer spans a usable range"


def test_synthetic_archetypes_are_unmistakably_synthetic() -> None:
    """The discipline that makes constructed fixtures safe to keep in the tree.

    Sprint 0 (`ebc1dc5`, `18dd4f6`) exists because six invented postures were published as a real
    peer cohort of n=6. The lesson was never "do not construct data" — it was **never let
    constructed data pass as observed**. Four independent markers, so no single edit can strip the
    labelling: the ref, the domain, the name, and the in-fixture block.

    `.example` is reserved by RFC 2606 §3 and cannot be registered by anyone, so these can never
    collide with a real company even by accident.
    """
    for ref in ARCHETYPE_REFS:
        payload = json.loads((FIXTURES / f"{ref}.json").read_text(encoding="utf-8"))
        vendor, block = payload["vendor"], payload.get("synthetic")

        assert ref.startswith("synthetic_"), f"{ref}: ref does not announce itself"
        assert vendor["domain"].endswith(".example"), (
            f"{ref}: domain {vendor['domain']!r} is not under the reserved .example TLD — a "
            "constructed fixture must not name a domain anyone could register"
        )
        assert "(synthetic)" in vendor["name"], f"{ref}: name would read as a real company"
        assert block and block.get("constructed") is True, f"{ref}: no synthetic block"
        assert block.get("builder") == "tests/build_archetypes.py"
        assert block.get("why_this_one"), f"{ref}: constructed with no stated reason"
        assert "not_a_real_company" in block

    for ref in VENDOR_REFS:
        payload = json.loads((FIXTURES / f"{ref}.json").read_text(encoding="utf-8"))
        assert "synthetic" not in payload, (
            f"{ref} is one of the five REAL captured fixtures and must never carry a synthetic "
            "marker — the marker is what separates evidence from construction"
        )


def test_a_ghost_is_never_published_however_clean_it_looks() -> None:
    """The single most important row in the archetype set.

    `synthetic_ghost` observes five signals and every one of them is CLEAN. A model that read
    coverage as quality would publish it as a perfect score. Approving a supplier because nothing
    is publicly visible about them is the worst call this system could make.
    """
    s = score_fixture("synthetic_ghost")
    assert s["posture"] is None and s["grade"] is None, "a Ghost must not publish a number"
    assert s["refused"] is True and s["ghost"] is True
    assert s["confidence"] < 0.4, "the Ghost stopped being thin — rebuild it"


def test_a_gated_vendor_produces_no_score_rather_than_a_low_one() -> None:
    """Blocked is not Grade F. A sanctions hit is a legal adjudication routed to a human, and a
    number next to it would invite someone to weigh it against other numbers."""
    s = score_fixture("synthetic_gated")
    assert s["blocked"] is True
    assert s["posture"] is None and s["grade"] is None


def test_the_small_supplier_is_not_taxed_for_being_small() -> None:
    """E2's fairness claim, made checkable.

    `synthetic_smallco` has no DNSSEC, no CAA, no security.txt, no certification, no trust page
    and no formal reporting — the profile of most small suppliers. Under v4.2.0 that cost it 41
    category points before anything about its security was considered. Under v5.0.0 those bands
    are informational and it keeps only what it genuinely fails: a missing CSP and no disclosure
    path.

    This is the assertion the real corpus could not make, because it contains no small vendor.
    """
    s = score_fixture("synthetic_smallco")
    free_now = {"dnssec", "caa", "security_txt", "cert_posture",
                "program_disclosure", "contactability", "reporting_posture"}

    vendor, results = load_fixture("synthetic_smallco")
    out = ScoringEngine().score(vendor, results, now=AS_AT)
    charged = {nf.signal: nf.effective_penalty for nf in out.normalized
               if nf.signal in free_now and nf.effective_penalty > 0}
    assert charged == {}, f"small-supplier profile is being taxed again: {charged}"

    assert s["grade"] == "A", (
        f"a small supplier doing everything free correctly scores {s['posture']}/{s['grade']}. "
        "If this drops, check whether a base-rate control started penalising again."
    )
    # ...and its lack of independent assurance shows up on the axis that is FOR that, not posture.
    assert s["confidence"] < 1.0, (
        "entity_maturity=startup_lt_2 must pull the assurance multiplier below 1. This is the "
        "only fixture in the corpus that fires entity_maturity at all"
    )


def test_the_ceiling_actually_bites_on_a_vendor_that_would_otherwise_pass() -> None:
    """The knockout, on a vendor where it CHANGES the outcome.

    `synthetic_weak` accumulates 63 category points, which is posture 78 — a grade B that clears
    any ">= 50" procurement threshold. It is also serving an expired production certificate. The
    ceiling caps it at 49. No real corpus vendor arms the ceiling, so until E0.2 this path was
    exercised only by synthetic unit tests and never end-to-end through a fixture.
    """
    s = score_fixture("synthetic_weak")
    assert s["critical_ceiling_applied"] is True
    assert s["posture"] == 49, "the ceiling is 49 — the top of grade D"

    cfg = get_scoring_config()
    uncapped = 100 - sum(c["penalty"] for c in s["categories"].values()) / cfg.penalty_divisor()
    assert uncapped > 70, (
        f"without the ceiling this vendor would publish {uncapped:.0f}. If that falls below the "
        "ceiling the fixture no longer demonstrates anything — make it milder."
    )


def test_no_new_signal_taxes_every_real_vendor_uniformly() -> None:
    """E0.3, as a tripwire rather than an occasional investigation.

    A signal that penalises 100% of vendors ranks nobody. It lowers the whole population together
    and separates none of it — a flat tax wearing the clothes of a comparison, and it looks
    perfectly fine on a per-vendor report, which is how six of them survived to v4.2.0 costing
    roughly 7 posture points between them.

    At v5.0.0 exactly one remains, recorded below. If that set grows, either a reclassification
    regressed or a new band was added that charges the base rate — decide which, then update this
    list in the same commit and say why.

    Real vendors only. The archetypes were built to vary, so including them would mask exactly the
    condition this guards against. Full analysis: `python -m tests.analyse_discrimination`.
    """
    # The three that survive at E6, each with a reason and a destination.
    #
    #   stale_hosts    ) still charges all five, but no longer UNIFORMLY: E6 bands it on a rate,
    #                    so slack (5 of 4,326) now pays 3 where atlassian (13 of 41) pays 20.
    #                    A flat tax that has become proportional is most of the way fixed, and
    #                    it stays listed because "everyone pays something" is still true.
    #   weak_issuance  ) every real vendor uses wildcard certificates — a base-rate case of
    #                    exactly E2's kind, parked for E9b where a control can earn positive
    #                    credit rather than merely stop costing points.
    #   vd_program     ) no real vendor runs an observable bug bounty. Also E9b, not E6.
    #
    # `subdomain_estate` LEFT this list at E6 and that is the phase's headline: charging a vendor
    # for the size of their public estate was measuring how big they are and calling it risk.
    # E2/E3 removed `contactability` and `cert_posture` earlier. Of the six the by-hand E0.3 pass
    # found at v4.2.0, three are gone. Full working: `python -m tests.analyse_discrimination`.
    RECORDED_FLAT_TAXES = {"stale_hosts", "weak_issuance", "vd_program"}

    charged_by: dict[str, set[str]] = {}
    for ref in VENDOR_REFS:
        vendor, results = load_fixture(ref)
        out = ScoringEngine().score(vendor, results, now=AS_AT)
        for nf in out.normalized:
            if not nf.is_sanctions and nf.penalty > 0:
                charged_by.setdefault(nf.signal, set()).add(ref)

    universal = {s for s, refs in charged_by.items() if refs == set(VENDOR_REFS)}
    assert universal <= RECORDED_FLAT_TAXES, (
        f"{sorted(universal - RECORDED_FLAT_TAXES)} now penalises every real vendor. A signal "
        f"nobody passes cannot rank anyone — it is a flat tax. Either reclassify it (E2's "
        f"argument) or record it here with the reason, in this commit."
    )
    # ...and the list must not go stale in the other direction. A signal recorded as a known flat
    # tax that has stopped being one is a comment asserting something untrue.
    assert RECORDED_FLAT_TAXES <= universal, (
        f"{sorted(RECORDED_FLAT_TAXES - universal)} is recorded as a known flat tax but no longer "
        f"penalises every real vendor. Remove it from the list — a stale exemption hides the next "
        f"real one."
    )


def test_the_expired_cert_in_the_corpus_has_not_decayed_with_age() -> None:
    """`cert_validity` is the only `never_decays` signal, and `synthetic_weak`'s notAfter is 2020.

    A current-state finding's event_date is a boundary, not an occurrence. If decay ever reached
    it, a certificate that expired six years ago would cost less than one expiring next week — the
    longer it stays broken, the cheaper. This is the end-to-end guard on that.
    """
    vendor, results = load_fixture("synthetic_weak")
    out = ScoringEngine().score(vendor, results, now=AS_AT)
    cert = next(n for n in out.normalized if n.signal == "cert_validity")
    assert cert.event_date is not None and cert.event_date.year == 2020
    # 50, not 40, since E7b widened the ladder. Full severity either way — that is the point.
    assert cert.effective_penalty == 50.0, (
        f"a cert expired in 2020 charged {cert.effective_penalty}, not the full critical 40 — "
        "age decay has reached a current-state signal"
    )
