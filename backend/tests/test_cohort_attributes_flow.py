"""How a supplier gets INTO a peer group — the write path behind `bm_cohort_peers`.

`supplier_attributes` is the source of truth the v2 cohort tables materialise, and it is the only
table `bm_cohort_peers` reads. Until this was fixed there were exactly two writers — the
`/api/v2/suppliers/{ref}/attributes` route and the inherent register — and **being scored did not
put a supplier into a peer group at all**.

The live book showed what that costs: 144 profiles, 128 of them carrying a sector resolved from
Wikidata or GLEIF, against 23 attribute rows of which 4 had a sector. A technology cohort of 4 in a
book holding 37 profiled technology vendors, so every placement refused for want of peers that had
already been assessed.

Two defects, two fixes, both covered here:

  1. `pipeline` now appends cohort attributes from the profile it just built.
  2. `inherent_register.apply_entry` MERGES the profile's firmographics into the stored row instead
     of inheriting the stored row wholesale. A relationship declared before the vendor was ever
     scored has no profile, so an empty row was written — and because `firmographics_of` then
     returned that empty row, re-running the register after the vendor WAS scored rewrote the same
     emptiness. The blank was sticky.
"""

from __future__ import annotations

import pytest

from app.benchmarking.models import SupplierFirmographics
from app.benchmarking.service import firmographics_of, record_attributes
from app.inherent_register import Entry, apply_entry
from app.models import ProfileField, Score, VendorProfile
from app.pipeline import _record_cohort_attributes


def _profile(ref: str, *, sector: str | None = "technology",
             employees: int | None = 8179) -> VendorProfile:
    """A profile shaped like one `build_profile` produces — provenance-wrapped fields.

    `ProfileField`, not a bare dict: a firmographic value that cannot be traced to a source is an
    assertion rather than evidence, and the read path unwraps `.value`.
    """
    p = VendorProfile(vendor_ref=ref)
    if sector is not None:
        p.sector = ProfileField(value=sector, source="firmographics", locator="Wikidata P452")
    if employees is not None:
        p.employees = ProfileField(value=employees, source="firmographics",
                                   locator="Wikidata P1128")
    return p


# ── 1. the pipeline path ──────────────────────────────────────────────────────────────────────

def test_scoring_a_vendor_puts_it_in_the_cohort_table(store):
    """The defect in one assertion: a profiled vendor must become a findable peer."""
    assert store.latest_supplier_attributes("acme") is None

    _record_cohort_attributes(store, "acme", _profile("acme"))

    attrs = store.latest_supplier_attributes("acme")
    assert attrs is not None, "a scored, profiled vendor must be recorded as a cohort member"
    assert attrs["sector"] == "technology"
    assert attrs["employees"] == 8179
    assert attrs["source"] == "derived", "observed from public evidence, not supplied by the client"
    # The size band is DERIVED from the headcount and stored with its own basis, so a reviewer
    # never has to re-run the code to find out why a supplier is `large`.
    assert attrs["size_band"] == "large"
    assert "8179" in (attrs["size_band_basis"] or "")


def test_the_vendor_is_then_actually_returned_as_a_peer(store):
    """Through the real query, not just the row — the whole point is cohort membership."""
    store.put_score(Score(vendor_ref="acme", posture=80, grade="B", overall_confidence=0.9,
                          confidence_band="High", categories=[]))
    _record_cohort_attributes(store, "acme", _profile("acme"))

    peers = store.bm_cohort_peers({"sector": "technology"}, exclude_ref="subject")
    assert [p["vendor_ref"] for p in peers] == ["acme"]


def test_re_scoring_never_drops_a_buyer_side_declaration(store):
    """`data_access_scope` and `delivery_model` are facts NO collector can observe.

    The table is append-only, so a fresh row written without them makes the newest row — the one
    every read takes — the one that lost the declaration. That is the defect
    `_carry_forward_declaration` fixes for criticality, one table across.
    """
    record_attributes(store, SupplierFirmographics(
        supplier_ref="acme", sector="technology", delivery_model="saas",
        data_access_scope="critical"), source="client_supplied")

    _record_cohort_attributes(store, "acme", _profile("acme", employees=25))

    attrs = store.latest_supplier_attributes("acme")
    assert attrs["data_access_scope"] == "critical", "a re-score must not drop the declaration"
    assert attrs["delivery_model"] == "saas"
    assert attrs["employees"] == 25, "...while the observed firmographics DO refresh"


def test_a_profile_with_no_sector_still_records_a_row(store):
    """An unknown sector is a supplier with no cohort, not a supplier to leave unrecorded.

    The row still carries the size band and the declaration, and it is what a later run merges
    into once the sector becomes resolvable.
    """
    _record_cohort_attributes(store, "acme", _profile("acme", sector=None))

    attrs = store.latest_supplier_attributes("acme")
    assert attrs is not None and attrs["sector"] is None
    assert attrs["size_band"] == "large"


def test_a_benchmarking_failure_never_costs_a_score(store):
    """Isolated like every other post-score step. A profile that cannot be read must not raise."""
    class Unreadable:
        def __getattr__(self, name: str):  # noqa: ANN204
            raise RuntimeError("profile is malformed")

    _record_cohort_attributes(store, "acme", Unreadable())   # must not raise
    assert store.latest_supplier_attributes("acme") is None


# ── 2. the inherent-register path ─────────────────────────────────────────────────────────────

def _entry(ref: str, **kw) -> Entry:
    kw.setdefault("criticality", "high")
    kw.setdefault("data_access_scope", "high")
    return Entry(ref, "relationship", basis="declared for the test",
                 declared_by="tester", declared_on="2026-08-04", **kw)


def test_declaring_before_the_vendor_is_scored_records_the_exposure_and_no_firmographics(store):
    """The starting condition, asserted so the fix below is visibly a change in behaviour."""
    applied = apply_entry(store, _entry("acme"))

    assert applied.wrote_attributes
    attrs = store.latest_supplier_attributes("acme")
    assert attrs["data_access_scope"] == "high", "the exposure is declarable without a profile"
    assert attrs["sector"] is None, "nothing has been observed about this vendor yet"


def test_the_blank_is_not_sticky_once_the_vendor_is_scored(store):
    """THE REGRESSION TEST. Declare first, score second, re-apply — the sector must arrive.

    Before the fix `firmographics_of` returned the empty row and `apply_entry` took it wholesale,
    so the profile was never consulted again and the blank survived every subsequent run.
    """
    apply_entry(store, _entry("acme"))
    assert store.latest_supplier_attributes("acme")["sector"] is None

    store.put_profile(_profile("acme"))          # the vendor is assessed
    apply_entry(store, _entry("acme"))           # the register runs again

    attrs = store.latest_supplier_attributes("acme")
    assert attrs["sector"] == "technology", "the profile must fill what the stored row lacks"
    assert attrs["employees"] == 8179
    assert attrs["size_band"] == "large", "and the derived band follows the headcount"
    assert attrs["data_access_scope"] == "high", "without losing the declaration"


def test_a_stored_value_wins_over_the_profile(store):
    """MERGE, not overwrite. The stored row may carry a client correction or an upheld dispute, and
    a firmographic collector must not silently restate it."""
    record_attributes(store, SupplierFirmographics(
        supplier_ref="acme", sector="financial_services", delivery_model="on_prem"),
        source="dispute_upheld")

    store.put_profile(_profile("acme", sector="technology"))
    apply_entry(store, _entry("acme"))

    attrs = store.latest_supplier_attributes("acme")
    assert attrs["sector"] == "financial_services", "an upheld correction is not re-derived away"
    assert attrs["delivery_model"] == "on_prem", "and a field the profile cannot see survives"
    assert attrs["employees"] == 8179, "while a field neither had is filled from the profile"


def test_a_non_relationship_is_still_never_declared(store):
    """Unchanged by the merge: a seeded corpus vendor has no commercial relationship, so it has no
    exposure to declare and inventing one to move a metric is the failure the register prevents."""
    applied = apply_entry(store, Entry("seeded", "corpus", note="peer population only"))

    assert not applied.wrote_attributes
    assert store.latest_supplier_attributes("seeded") is None


@pytest.mark.parametrize("dry", [True, False])
def test_dry_run_writes_nothing(store, dry):
    apply_entry(store, _entry("acme"), dry_run=dry)
    assert (store.latest_supplier_attributes("acme") is None) is dry
