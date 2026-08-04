"""The inventory of record, and the denominator it exists to fix.

P9 reported `inherent_tier_declaration_rate: 0.0%` across 146 vendors. Two things were wrong, and
only one of them was a habit:

  * There was no route that accepted a declaration without re-running the whole pipeline, so
    declaring an exposure cost a full scan of a dozen free services. A rate of zero was a missing
    route wearing the costume of a missing habit.
  * 146 scored rows were never 146 relationships. The denominator counted a seeded benchmarking
    corpus and a handful of typos as suppliers nobody had classified.

These tests hold both, plus the refusal that keeps the fix honest: **a non-relationship may never
carry a declaration**, because an exposure declared against a typo counts toward the rate
indistinguishably from a real one.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import inherent_register as reg
from app.models import VendorProfile, utcnow
from app.residual_risk import inherent_tier, residual_risk

# ════════════════════════════════════════════════════ the register holds together


def test_every_relationship_carries_a_declaration_a_basis_an_author_and_a_date():
    """`_validate` runs at import, so this is really asserting that it still has teeth."""
    for e in reg.relationships():
        assert e.declared, f"{e.ref}: a relationship with no exposure declared"
        assert len(e.basis) >= 80, f"{e.ref}: a label, not a basis"
        assert e.declared_by and e.declared_on


@pytest.mark.parametrize("e", [e for e in reg.entries() if not e.declarable],
                         ids=lambda e: e.ref)
def test_a_non_relationship_may_never_carry_a_declaration(e):
    """THE REFUSAL THAT KEEPS THE FIX HONEST. A seeded corpus vendor has no commercial relationship
    and a typo has no entity at all; declaring an exposure against either fabricates the
    relationship, and it would count toward the declaration rate exactly like a real one."""
    assert not e.declared
    assert e.substitutability is None
    assert e.note, "an unexplained exclusion is how a denominator gets quietly trimmed"


def test_a_declaration_on_a_non_relationship_is_refused_at_validation():
    with pytest.raises(reg.RegisterError, match="fabricate"):
        reg._validate((reg.Entry("x", "corpus", criticality="high", note="n"),))


def test_a_relationship_with_no_declaration_is_refused():
    with pytest.raises(reg.RegisterError, match="neither criticality nor data access scope"):
        reg._validate((reg.Entry("x", "relationship", basis="b" * 100,
                                 declared_by="a", declared_on="2026-01-01"),))


def test_a_declaration_with_a_one_line_basis_is_refused():
    with pytest.raises(reg.RegisterError, match="not a basis"):
        reg._validate((reg.Entry("x", "relationship", criticality="high", basis="important",
                                 declared_by="a", declared_on="2026-01-01"),))


def test_a_duplicate_ref_is_refused():
    a = reg.Entry("x", "corpus", note="n")
    with pytest.raises(reg.RegisterError, match="listed twice"):
        reg._validate((a, a))


def test_every_declaration_ships_provisional():
    """NOT A DEFAULT THAT DRIFTED — the whole seeded set is one person's judgement written on one
    day, and `confirmed` is what a relationship owner sets, one row at a time. A bulk-confirmed
    register would be the laundering this design exists to prevent."""
    assert all(not e.confirmed for e in reg.relationships())
    assert all(e.provisional for e in reg.relationships())


def test_the_corpus_is_derived_from_the_seed_list_and_never_hand_listed():
    """A second hand-maintained copy of the seed list would drift, and the failure would be silent:
    a corpus vendor quietly counted as an undeclared relationship, which is the exact denominator
    error this module exists to fix."""
    src = Path("app/inherent_register.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_corpus_refs")
    imported = {a.name for n in ast.walk(fn) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "SEED_SETS" in imported
    assert not any(e.classification == "corpus" for e in reg.entries())


def test_a_seeded_vendor_classifies_as_corpus_without_being_listed():
    corpus = next(iter(reg._corpus_refs()))
    entry = reg.entry_for(corpus)
    assert entry is not None and entry.classification == "corpus"
    assert not entry.declared


def test_an_unknown_ref_is_none_rather_than_a_default_classification():
    """A vendor on nobody's inventory is a FINDING. Defaulting it either way is a guess, and only
    one of the two guesses is visible."""
    assert reg.entry_for("nobody-has-ever-heard-of-this") is None
    assert reg.classify("nobody-has-ever-heard-of-this") is None


# ════════════════════════════════════════════════════ the denominator


class _Store:
    """Enough store for `coverage`. Declarations live in `profiles`/`attrs`, NOT in the register —
    which is the distinction the fixture exists to make testable."""

    def __init__(self, refs, profiles=None, attrs=None):
        self._refs = list(refs)
        self._profiles = profiles or {}
        self._attrs = attrs or {}

    def latest_scores_all(self):
        return [SimpleNamespace(vendor_ref=r, posture=70, blocked=False, refused=False,
                                computed_at=utcnow()) for r in self._refs]

    def latest_profile(self, ref):
        return self._profiles.get(ref)

    def latest_supplier_attributes(self, ref):
        return self._attrs.get(ref)

    # The book-wide reads `coverage` actually uses. Deliberately backed by the same two dicts as
    # the per-vendor methods above: if the bulk and single reads could disagree here, the fixture
    # would be testing a store no real store behaves like.
    def latest_profiles_all(self):
        return dict(self._profiles)

    def latest_supplier_attributes_all(self):
        return dict(self._attrs)


def test_the_denominator_is_relationships_and_not_every_scored_row():
    """THE FINDING THAT WAS BIGGER THAN THE NUMERATOR. Counting seeded corpus vendors as undeclared
    makes the programme look negligent about a question that does not apply to them, and buries the
    relationships that genuinely are undeclared in a number too large to act on."""
    corpus = sorted(reg._corpus_refs())[:40]
    rel = [e.ref for e in reg.relationships()]
    store = _Store(corpus + rel + ["jira"])

    cov = reg.coverage(store)
    assert cov["in_book"] == len(corpus) + len(rel) + 1
    assert cov["relationships"] == len(rel)
    assert cov["corpus"] == len(corpus)
    assert cov["not_a_relationship"] == 1
    # No declaration has been APPLIED, so the rate is zero even though the register declares them.
    assert cov["declaration_rate"] == 0.0


def test_declared_means_the_store_has_it_not_that_the_register_claims_it():
    """THE FIRST THING THIS FUNCTION GOT WRONG. Counting the register's own rows made it report
    100% the moment the file was written and before a single declaration was applied — a metric
    measuring its own input. `unapplied` is how that state stays visible instead of reading as
    success."""
    e = reg.relationships()[0]
    store = _Store([e.ref])
    assert reg.coverage(store)["declared"] == 0
    assert reg.coverage(store)["unapplied"] == [e.ref]

    applied = _Store([e.ref],
                     profiles={e.ref: VendorProfile(vendor_ref=e.ref, criticality="high",
                                                    inherent_provisional=True)})
    cov = reg.coverage(applied)
    assert cov["declared"] == 1 and cov["unapplied"] == []
    assert cov["provisional"] == 1 and cov["confirmed"] == 0


def test_an_unregistered_vendor_is_reported_separately_and_never_folded_in():
    store = _Store(["a-vendor-nobody-classified"])
    cov = reg.coverage(store)
    assert cov["unregistered"] == ["a-vendor-nobody-classified"]
    assert cov["relationships"] == 0


# ════════════════════════════════════════════════════ applying it


def test_applying_a_declaration_writes_a_profile_and_an_attribute_row_and_no_score():
    """NOTHING HERE TOUCHES A POSTURE — the E10b invariant, not an optimisation. Inherent exposure
    and observed posture run on different clocks, and a contract change must never look like a
    security event."""
    written = {"profiles": [], "attrs": []}

    class _W(_Store):
        def put_profile(self, p):
            written["profiles"].append(p)
            return "id"

        def put_supplier_attributes(self, a):
            written["attrs"].append(a)
            return "id"

        def put_score(self, *a, **k):  # pragma: no cover - must never be called
            raise AssertionError("applying a declaration must not write a score")

    e = reg.relationships()[0]
    store = _W([e.ref])
    out = reg.apply_entry(store, e)

    assert out.wrote_profile and out.wrote_attributes
    assert written["profiles"][0].criticality == e.criticality
    assert written["profiles"][0].inherent_provisional is True
    assert written["attrs"][0].data_access_scope == e.data_access_scope
    assert out.tier == inherent_tier(e.criticality, e.data_access_scope).tier


def test_a_dry_run_writes_nothing_but_still_reports_the_tier():
    class _W(_Store):
        def put_profile(self, p):  # pragma: no cover
            raise AssertionError("dry run wrote a profile")

    e = reg.relationships()[0]
    out = reg.apply_entry(_W([e.ref]), e, dry_run=True)
    assert not out.wrote_profile and out.tier is not None


def test_applying_a_non_relationship_is_a_no_op_rather_than_an_error():
    """It has to be safe to run `--apply` over the whole register, and a defect row must neither
    write nor raise — raising would make the safe operation the one nobody runs."""
    e = next(e for e in reg.entries() if not e.declarable)
    out = reg.apply_entry(_Store([e.ref]), e)
    assert not out.wrote_profile and out.tier is None


def test_a_blocked_vendor_with_no_profile_can_still_be_declared():
    """Exposure is a fact about the RELATIONSHIP and does not need the vendor to have been
    successfully observed. A blocked record with no declared tier tells an adjudicator nothing
    about how much hangs on their decision."""
    class _W(_Store):
        def put_profile(self, p):
            self.saved = p
            return "id"

        def put_supplier_attributes(self, a):
            return "id"

    e = reg.relationships()[0]
    store = _W([e.ref])          # no profile, no attributes
    out = reg.apply_entry(store, e)
    assert out.wrote_profile and "minimal" in out.note


# ════════════════════════════════════════════════════ provisionality travels


def test_a_provisional_tier_still_publishes_a_residual_and_says_it_is_provisional():
    """A PROVISIONAL ANSWER ROUTES BETTER THAN NO ANSWER. Refusing to publish against an unconfirmed
    declaration would put every relationship back in the undeclared state the register exists to
    leave — so it publishes, and every page that shows it says so."""
    out = residual_risk(85, "high", "high", provisional=True)
    assert out.published and out.residual == "medium"
    assert out.inherent.provisional
    assert "(provisional)" in out.inherent.label
    assert any("PROVISIONAL" in c for c in out.caveats)


def test_a_confirmed_tier_carries_no_provisional_caveat():
    out = residual_risk(85, "high", "high")
    assert not out.inherent.provisional
    assert "(provisional)" not in out.inherent.label
    assert not any("PROVISIONAL" in c for c in out.caveats)


def test_provisionality_never_changes_the_published_cell():
    """It changes what the page SAYS, never what the lookup RETURNS. A flag that quietly moved the
    tier would make the matrix unreconstructible, which is the whole reason it is a table."""
    for posture in (95, 75, 55, 20):
        for crit in ("low", "medium", "high"):
            a = residual_risk(posture, crit, "medium")
            b = residual_risk(posture, crit, "medium", provisional=True)
            assert a.residual == b.residual


def test_an_absent_declaration_is_never_marked_provisional():
    """There is nothing provisional about an absence, and a flag saying 'this missing declaration
    is unconfirmed' would read as though something had been declared."""
    out = inherent_tier(None, None, provisional=True)
    assert not out.published and not out.provisional


# ════════════════════════════════════════════════════ a re-score must not lose the declaration


def test_a_rescore_that_is_not_told_the_exposure_replays_it_rather_than_blanking_it():
    """THE BUG THE UI FOUND, 2026-08-01, and it failed in the worst possible direction.

    A profile is rebuilt from scratch on every run and `criticality` arrives as a call argument, so
    a re-score that does not re-supply it — the scheduled monitor, a dispute re-score, a
    blocked-record retry — wrote a new profile with `criticality=None`. Two vendors on the live
    book had already lost theirs.

    Nothing broke visibly, which is why it survived. `data_access_scope` lives on a different table
    and was untouched, so `inherent_tier` kept publishing — one input lighter. A vendor declared
    high criticality / medium scope silently re-published as MEDIUM inherent after a routine
    re-scan, with nothing on the page to say a declared input had gone.
    """
    from app.pipeline import _carry_forward_declaration

    class _Store:
        def latest_profile(self, ref):
            return VendorProfile(vendor_ref=ref, criticality="high", substitutability="sole_source",
                                 inherent_provisional=True)

    fresh = VendorProfile(vendor_ref="acme")          # as `build_profile` returns it: no declaration
    _carry_forward_declaration(_Store(), "acme", fresh, supplied=(None, None))

    assert fresh.criticality == "high"
    assert fresh.substitutability == "sole_source"
    assert fresh.inherent_provisional is True, "provisionality must travel with the value it qualifies"


def test_an_explicitly_supplied_declaration_supersedes_the_prior_one():
    """A caller passing a criticality is stating the exposure NOW. Restoring the old value over the
    top would make the declaration route unable to lower a tier, which is the failure in the
    opposite direction."""
    from app.pipeline import _carry_forward_declaration

    class _Store:
        def latest_profile(self, ref):
            return VendorProfile(vendor_ref=ref, criticality="high", inherent_provisional=True)

    fresh = VendorProfile(vendor_ref="acme", criticality="low")
    _carry_forward_declaration(_Store(), "acme", fresh, supplied=("low", None))
    assert fresh.criticality == "low"


def test_a_vendor_with_no_prior_profile_is_left_alone():
    from app.pipeline import _carry_forward_declaration

    class _Store:
        def latest_profile(self, ref):
            return None

    fresh = VendorProfile(vendor_ref="acme")
    _carry_forward_declaration(_Store(), "acme", fresh, supplied=(None, None))
    assert fresh.criticality is None and fresh.inherent_provisional is False
