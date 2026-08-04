"""Entity-resolution confidence — the input the ambiguity gate reads.

These encode the asymmetry that makes the gate safe to switch on: it must block AMBIGUITY
("which of these companies did you mean?") and must not block OBSCURITY ("this vendor is too
small to be on a register"). Blocking the second would be the invisible-vendor failure the
methodology exists to prevent, wearing a different hat.
"""

from __future__ import annotations

from app.entity_resolution import (
    AMBIGUOUS_REGISTER,
    DOMAIN_ONLY,
    DOMAIN_VERIFIED,
    INFERRED_DOMAIN,
    REGISTER_MATCH,
    UNVERIFIED,
    WEAK_ATTRIBUTION,
    assess,
)
from app.models import CollectorResult, Finding, Vendor
from app.scoring import ScoringEngine
from app.scoring_config import get_scoring_config

BLOCK_BELOW = get_scoring_config().entity_block_below()


def _v(name="Acme Corp", domain="acme.example"):  # noqa: ANN001
    """A caller-supplied domain — the normal path. `domain_source` defaults to 'supplied'."""
    return Vendor(ref="acme", name=name, domain=domain, resolved=True)


def _r(source, status="ok", findings=None, raw=None):  # noqa: ANN001
    return CollectorResult(source=source, vendor_ref="acme", status=status, source_version="t",
                           raw=raw or {}, findings=findings or [], reliability=0.9)


def _f(signal, category):  # noqa: ANN001
    return Finding(source="t", signal=signal, subcategory=signal, category=category,
                   observed="x", value={"band": "x"})


_GLEIF_F = [_f("entity_status", "business_financial_stability")]
_WIKI_F = [_f("entity_existence", "business_financial_stability")]


def _gleif(name_match=3, strong=1, exact=1, status="ok", findings=_GLEIF_F):  # noqa: ANN001
    return _r("gleif", status, findings,
              {"name_match": name_match, "strong_matches": strong, "exact_matches": exact})


# ---------------------------------------------------------------- what must NOT block

def test_domain_only_has_nothing_to_confuse():
    """No name given: the caller pointed at a domain and we scored that domain. There is no
    name-to-entity mapping that could be wrong, so there is nothing to be ambiguous about."""
    res = assess(Vendor(ref="a", name=None, domain="acme.example", resolved=True), [])
    assert res.confidence == DOMAIN_ONLY
    assert res.confidence >= BLOCK_BELOW


def test_an_obscure_vendor_is_unverified_not_ambiguous():
    """THE asymmetry. A vendor absent from every register is small, not misidentified. Blocking
    it would punish obscurity — the same failure as letting a vendor look strong by being
    invisible, which the methodology forbids outright."""
    res = assess(_v(), [_r("gleif", "empty"), _r("wikidata", "empty")])
    assert res.confidence == UNVERIFIED
    assert res.confidence >= BLOCK_BELOW, "obscurity must never block"
    assert "not ambiguous" in res.summary()


def test_domain_verification_is_the_strongest_evidence():
    """Wikidata emits only when P856 matches the vendor's domain — a hard identifier tying the
    name to the thing we scored."""
    res = assess(_v(), [_r("wikidata", "ok", _WIKI_F), _gleif()])
    assert res.confidence >= DOMAIN_VERIFIED
    assert "official website matches" in res.summary()


def test_a_single_close_register_match_is_enough():
    res = assess(_v(), [_gleif(), _r("wikidata", "empty")])
    assert res.confidence >= REGISTER_MATCH


def test_register_ambiguity_lowers_confidence_but_does_not_block():
    """MEASURED, not assumed. Four separate legal entities are registered as 'Snowflake'; GLEIF
    alone cannot say which owns snowflake.com. An earlier draft blocked on exactly this and
    refused a benchmark vendor.

    Two different questions were being conflated: WHICH LEGAL ENTITY is this (uncertain) and
    WHAT DID WE ASSESS (certain — the domain the caller supplied). Register ambiguity makes the
    Business Stability finding unreliable; it says nothing about the TLS handshake."""
    res = assess(_v(name="Snowflake"), [_gleif(exact=4, strong=15), _r("wikidata", "empty")])
    assert res.confidence == AMBIGUOUS_REGISTER
    assert res.confidence >= BLOCK_BELOW, "register ambiguity must not refuse the whole vendor"
    assert res.confidence < 0.70, "...but it must not read as confidently resolved either"
    assert "may belong to another" in res.summary()


def test_strong_matches_alone_are_not_ambiguity():
    """'Snowflake' strong-matches 15 records (Snowflake Capital, Snowflake Holdings...) while
    exactly one IS Snowflake. Counting strong matches would refuse a household name for having a
    common word in it — the false positive that this distinction exists to prevent."""
    res = assess(_v(name="Snowflake"), [_gleif(exact=1, strong=15), _r("wikidata", "empty")])
    assert res.confidence >= REGISTER_MATCH


def test_a_barely_matching_entity_is_flagged():
    """A register answered, but the winning legal name hardly resembles what was asked for."""
    res = assess(_v(), [_gleif(name_match=0, exact=0), _r("wikidata", "empty")])
    assert res.confidence == WEAK_ATTRIBUTION


def test_missing_attribution_metadata_does_not_penalise():
    """Absent metadata is not bad metadata. A result captured before attribution quality was
    recorded must not be marked down for the collector's history rather than for the vendor."""
    stale = _r("gleif", "ok", _GLEIF_F, {"query": "Acme Corp", "candidates": 1})
    res = assess(_v(), [stale, _r("wikidata", "empty")])
    assert res.confidence >= REGISTER_MATCH


# ---------------------------------------------------------------- what MUST block

def test_a_guessed_domain_blocks():
    """THE blocking case. If the domain was inferred from a name and never confirmed, we cannot
    say what we assessed — scoring it is the one shortcut this system refuses."""
    v = Vendor(ref="acme", name="Acme Corp", domain="acme.example", resolved=True,
               domain_source="inferred")
    res = assess(v, [_gleif()])
    assert res.confidence == INFERRED_DOMAIN
    assert res.confidence < BLOCK_BELOW
    assert "guessed from the name" in res.summary()


def test_a_guessed_domain_is_blocked_by_the_engine_and_says_why():
    """End to end: no score emitted, and the human adjudicator is told the reason in words."""
    v = Vendor(ref="acme", name="Acme Corp", domain="acme.example", resolved=True,
               domain_source="inferred")
    resolution = assess(v, [_gleif()])
    v.resolution_confidence = resolution.confidence
    v.resolution_basis = resolution.summary()

    score = ScoringEngine().score(v, [_gleif()]).score
    assert score.blocked is True
    assert score.posture is None and score.grade is None
    assert "guessed from the name" in (score.blocked_reason or "")


# ---------------------------------------------------------------- end to end through the engine

def test_a_resolved_entity_is_scored_normally():
    vendor = _v()
    results = [_r("wikidata", "ok", _WIKI_F), _gleif()]
    resolution = assess(vendor, results)
    vendor.resolution_confidence = resolution.confidence
    score = ScoringEngine().score(vendor, results).score
    assert score.blocked is False


def test_confidence_is_never_a_bare_number():
    """Every assessment carries its reasoning — a blocked vendor is an accusation of sorts."""
    for results in ([_gleif(exact=4, strong=9)], [_r("gleif", "empty")], [_gleif()]):
        assert assess(_v(), results).summary().strip()
