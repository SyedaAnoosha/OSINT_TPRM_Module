"""Profile assembly — collected results in, `VendorProfile` out.

WHY A DERIVATION AND NOT A COLLECTOR. The same shape as `entity_resolution.assess()`: several
sources each know part of the answer, and the useful artefact is the reconciliation, not any one
source's view. GLEIF knows the jurisdiction, Wikidata knows the industry and headcount, ABN knows
the Australian status, RDAP knows how old the domain is. A profile is what you get when you put
them beside each other and record which one said what.

PRECEDENCE IS EXPLICIT AND ORDERED BY AUTHORITY, not by convenience. An authoritative register
beats a community-edited one for the fields it actually holds; a community-edited source is used
where no register publishes the fact at all (headcount, industry). Every field carries the source
that produced it, so a reader disputing "employees: 230,000" can see it came from Wikidata P1128
and argue with that rather than with us.

THE INVARIANT: nothing in this module can change a score. It runs after scoring, reads `raw`
payloads only, and returns a value the engine never sees. `tests/test_profile.py` holds it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from . import industry as ind
from .benchmark import cohort_key, employee_band_for, revenue_band_for
from .models import (
    CollectorResult,
    Criticality,
    PeerCohort,
    ProfileField,
    SizeBand,
    Substitutability,
    Vendor,
    VendorProfile,
    utcnow,
    LifecycleStage,
)

from .lifecycle import lifecycle_stage_from_years

# Fields counted for `completeness`. Deliberately excludes `criticality` (a client input, not an
# observation) so completeness measures what WE managed to find out.
_COUNTED = (
    "legal_name", "country", "jurisdiction", "industry_label", "sector",
    "employees", "revenue", "ownership", "inception", "domain_age_days",
)


def build_profile(
    vendor: Vendor,
    results: list[CollectorResult],
    criticality: Criticality | None = None,
    size_band: SizeBand | None = None,
    sector: str | None = None,
    substitutability: Substitutability | None = None,
) -> VendorProfile:
    """Assemble the profile from whatever the collectors returned. Missing sources are normal.

    `size_band` and `sector` are OPTIONAL CLIENT OVERRIDES, and they exist because of a measured
    gap rather than a hypothetical one: public sources publish an industry for most vendors but a
    headcount or revenue for far fewer, and a sector without a size is not a peer group. Without an
    override, a large share of real vendors would carry an absolute grade and never a comparison.

    They are recorded with `source="client"`, so the scorecard shows a client-stated size as
    client-stated rather than dressing it as an observation. That is the same discipline
    `criticality` follows, and the reason neither is ever inferred: a buyer usually knows how big
    their supplier is, and it is more honest to let them say so than to guess from proxies. It is
    also why we do NOT derive size from anything we observe — subdomain counts and mail volume
    correlate with attack surface, which correlates with the score, and that circularity is exactly
    the size bias methodology §7.3 warns about.
    """
    by_source = {r.source: r for r in results if r.raw}
    # Remember the name this run resolved with, so a later domain-only re-score replays it rather
    # than the slug (see VendorProfile.search_name). Stored even for domain-only runs (None), which
    # is harmless; the pipeline only recovers a NON-empty prior name.
    profile = VendorProfile(vendor_ref=vendor.ref, criticality=criticality,
                            substitutability=substitutability, search_name=vendor.name)

    _from_gleif(profile, by_source.get("gleif"))
    _from_abn(profile, by_source.get("abn"))
    _from_firmographics(profile, by_source.get("firmographics"))
    _from_rdap(profile, by_source.get("rdap"))
    # LAST, and fallback-only: PDL fills industry/size/country the registers and Wikidata left blank
    # — the ~1-in-4 vendors nobody classified — and never overwrites what an authoritative source or
    # a domain-verified Wikidata entity already supplied.
    _from_pdl(profile, by_source.get("pdl"))

    _derive_sector(profile)
    if sector:
        profile.sector = ProfileField(value=sector, source="client", locator="client-supplied")
    profile.cohort = _derive_cohort(profile, size_override=size_band)
    profile.completeness = _completeness(profile)

    # Derive lifecycle stage from operating years — context only, see models.LifecycleStage.
    profile.lifecycle_stage = lifecycle_stage_from_years(operating_years(profile))

    return profile


# --------------------------------------------------------------------- per-source readers


def _field(result: CollectorResult, value: Any, locator: str | None = None,
           as_of: str | None = None) -> ProfileField | None:
    """Wrap a value with its provenance. `None` in, `None` out — an absent fact is absent, and is
    never represented as an empty string or a zero, both of which would read as data."""
    if value in (None, "", [], {}):
        return None
    return ProfileField(value=value, source=result.source, locator=locator,
                        fetched_at=result.fetched_at, as_of=as_of)


def _from_gleif(profile: VendorProfile, result: CollectorResult | None) -> None:
    """GLEIF is authoritative for legal name and jurisdiction — it goes first and is not overwritten."""
    if result is None or not result.raw:
        return
    best = result.raw.get("resolved") or {}
    profile.legal_name = _field(result, best.get("legalName"), f"GLEIF LEI {best.get('lei')}")
    jurisdiction = best.get("jurisdiction")
    profile.jurisdiction = _field(result, jurisdiction, f"GLEIF LEI {best.get('lei')}")
    # GLEIF jurisdictions are ISO-3166-2 ("US-DE", "AU"); the country is the leading part.
    if jurisdiction:
        profile.country = _field(result, str(jurisdiction).split("-")[0].upper(),
                                 f"GLEIF LEI {best.get('lei')}")


def _from_abn(profile: VendorProfile, result: CollectorResult | None) -> None:
    """The ABR is the authority for AU entities: its name and country override GLEIF's."""
    if result is None or not result.raw or not result.raw.get("abn"):
        return
    abn = result.raw["abn"]
    profile.legal_name = _field(result, result.raw.get("entity_name"), f"ABN {abn}") or profile.legal_name
    profile.country = _field(result, "AU", f"ABN {abn}")
    profile.jurisdiction = _field(result, "AU", f"ABN {abn}")


def _from_firmographics(profile: VendorProfile, result: CollectorResult | None) -> None:
    """Wikidata fills what no register publishes: industry, headcount, revenue, ownership, age.

    It never overwrites a register's legal name or country — those it also holds, less reliably.
    """
    if result is None or not result.raw:
        return
    raw = result.raw
    qid = raw.get("qid")
    loc = f"Wikidata {qid}" if qid else None

    industries = raw.get("industry") or []
    if industries:
        profile.industry_label = _field(result, ", ".join(industries), f"{loc} P452")

    # `as_of` matters more here than anywhere else on the profile: these are Wikidata TIME SERIES,
    # and an undated headcount can be a decade old (see `_wikidata.claim_amount`).
    if raw.get("employees") is not None:
        profile.employees = _field(result, int(raw["employees"]), f"{loc} P1128",
                                   as_of=raw.get("employees_as_of"))
    if raw.get("revenue") is not None:
        profile.revenue = _field(result, float(raw["revenue"]), f"{loc} P2139",
                                 as_of=raw.get("revenue_as_of"))
        profile.revenue_currency = _field(result, raw.get("revenue_currency"), f"{loc} P2139")
    if raw.get("inception"):
        profile.inception = _field(result, raw["inception"], f"{loc} P571")
    parents = raw.get("parent") or []
    if parents:
        profile.parent = _field(result, parents[0], f"{loc} P749")
    if raw.get("ownership") and raw["ownership"] != "unknown":
        profile.ownership = _field(result, raw["ownership"], f"{loc} P414")

    # Country shown on the profile is the OPERATIONAL headquarters, not the legal incorporation
    # domicile: that is what a reader means by "where is this vendor" and what its regulatory regime
    # (and therefore its peer region) tracks. So a resolved HQ country OVERRIDES the register's legal
    # country — for a re-domiciled firm they differ (Atlassian: HQ Australia, incorporated US). The
    # legal jurisdiction is untouched on `profile.jurisdiction`, so both facts remain available.
    hq_country = raw.get("hq_country") or []
    if hq_country and _country_code(hq_country[0]):
        profile.country = _field(result, _country_code(hq_country[0]),
                                 f"{loc} P159 (headquarters)")
    elif profile.country is None and (raw.get("country") or []):
        profile.country = _field(result, _country_code(raw["country"][0]), f"{loc} P17")


def _from_pdl(profile: VendorProfile, result: CollectorResult | None) -> None:
    """People Data Labs Free Company Dataset — a FALLBACK for the fields nobody else supplied.

    Fills ONLY what is still empty: legal name, industry (→ sector, → cohort), a representative
    headcount (→ size band, → cohort), and country (→ region). It never overwrites a register's or
    Wikidata's value — it runs last precisely so an authoritative source always wins. A static
    snapshot carries no per-figure date, so there is no `as_of` to attach; that is honest about what
    a quarterly dump is."""
    if result is None or not result.raw:
        return
    raw = result.raw
    loc = f"PDL {raw.get('dataset_version') or 'dump'}"

    if profile.legal_name is None and raw.get("name"):
        profile.legal_name = _field(result, raw["name"], loc)
    if profile.industry_label is None and raw.get("industry"):
        profile.industry_label = _field(result, raw["industry"], loc)
    if profile.employees is None and raw.get("employees") is not None:
        profile.employees = _field(result, int(raw["employees"]), loc)
    if profile.country is None and raw.get("country"):
        code = _country_code(raw["country"])
        if code:
            profile.country = _field(result, code, loc)


def _from_rdap(profile: VendorProfile, result: CollectorResult | None) -> None:
    """Domain age — already collected for entity standing, reused here at no extra cost.

    `created` is the RDAP registration event, which the collector stores as an ISO string. A young
    domain is context, not a penalty: the RDAP collector already scores that separately under
    `domain_registration`, and reading it twice would be double-counting.
    """
    if result is None or not result.raw:
        return
    age = _days_since(result.raw.get("created"))
    if age is not None:
        profile.domain_age_days = _field(result, age, "RDAP registration event 'created'")


# --------------------------------------------------------------------- derivations


def _derive_sector(profile: VendorProfile) -> None:
    """Classify into a working sector, or leave it unset.

    Order is by how much the source actually knows: a registry industry code beats a free-text
    label. An unmapped label leaves `sector` None, which means no cohort and no percentile — the
    honest outcome. We do not fall back to a default sector; a wrong peer group produces a
    confident comparison against the wrong population, which is worse than no comparison.
    """
    code_field = profile.industry_code
    if code_field:
        code = str(code_field.value)
        sector = ind.sector_from_anzsic(code) or ind.sector_from_sic(code)
        if sector:
            profile.sector = ProfileField(value=sector, source=code_field.source,
                                          locator=code_field.locator,
                                          fetched_at=code_field.fetched_at)
            return

    label_field = profile.industry_label
    if label_field:
        # Industries arrive most-specific-first; take the first that maps.
        for part in str(label_field.value).split(","):
            sector = ind.sector_from_label(part.strip())
            if sector:
                profile.sector = ProfileField(value=sector, source=label_field.source,
                                              locator=label_field.locator,
                                              fetched_at=label_field.fetched_at)
                return


def _derive_cohort(profile: VendorProfile,
                   size_override: SizeBand | None = None) -> PeerCohort | None:
    """Build the four-factor cohort: industry × revenue × headcount × region.

    THIS FUNCTION ALWAYS RETURNS A COHORT. It used to return None when the profile could not
    support one — "a sector without a size is not a peer group" — and the docstring said so long
    after the code had stopped doing it. Today an unknown sector falls to `technology` and an
    unknown headcount falls to `medium`, so every vendor gets a comparison. That is a deliberate
    product choice for live/demo use, not an accident, but it has two consequences worth naming:

      * The sector fallback IS traceable — `profile.sector` is rewritten with `source="default"`,
        so a reader can tell a guess from an observation.
      * The headcount fallback is NOT. `emp=medium` in a cohort key is indistinguishable from a
        vendor genuinely measured as medium. Cohort assignment is supposed to be disputable, and
        you cannot dispute a fabrication you cannot see. **Open item for E11** — either mark it
        the way the sector default is marked, or restore the refusal now that the synthetic-peer
        fallback already labels the downstream comparison as "NOT REAL PEERS".

    Revenue is NOT defaulted: an unknown revenue stays None and the widening ladder skips any rung
    that needs it, so the key writes `rev=?` rather than inventing a figure.

    A client-supplied `size_override` sets the headcount band, because that is the dimension a
    buyer can actually speak to. It wins over the observed figure: a buyer stating the band may be
    describing the local subsidiary they contract with rather than the global parent Wikidata
    describes. The observed values stay on the profile either way, so a reader can see both.
    """
    sector = profile.sector.value if profile.sector else "technology"
    if not profile.sector:
        profile.sector = ProfileField(value="technology", source="default", locator="fallback")

    employee_band = size_override or employee_band_for(
        profile.employees.value if profile.employees else None
    ) or "medium"
    revenue_band = revenue_band_for(
        profile.revenue.value if profile.revenue else None,
        profile.revenue_currency.value if profile.revenue_currency else None,
    )

    # `region_for` already falls to "other" for an unknown country, so it never returns falsy —
    # an `or` fallback here would be dead code, and the one that used to sit here named a region
    # ("us") that is not a member of the Region literal at all.
    region = ind.region_for(profile.country.value if profile.country else None)
    return PeerCohort(
        sector=sector,
        revenue_band=revenue_band,
        employee_band=employee_band,
        region=region,
        ownership=profile.ownership.value if profile.ownership else None,
        key=cohort_key(sector, revenue_band, employee_band, region),
    )


def refresh_cohort(profile: VendorProfile | None) -> VendorProfile | None:
    """Re-derive the cohort on READ, repairing profiles written under an older cohort model.

    WHY THIS IS NECESSARY, AND THE BUG THAT PROVED IT. Profiles are append-only, so a row written
    when a cohort was `sector|size|region` still deserialises today — and the two size fields that
    did not exist then default to None. The result rendered as a live cohort with "headcount
    unknown · revenue unknown", matched no peers at any width, and reported *"insufficient peers"*
    — blaming the population for what was actually a schema change. Silently wrong, and wrong in
    the direction that makes benchmarking quietly never work.

    WHY RE-DERIVING IS LEGITIMATE RATHER THAN A FUDGE. A cohort is not an observation; it is a
    grouping computed from observations the profile already stores (sector, employees, revenue,
    country). Re-deriving it from those frozen facts is the same discipline `PersistedFinding.reason`
    already follows — the band is stored, the sentence is regenerated at serve time — so improving
    the derivation improves old records instead of rewriting history. The stored row is untouched.

    A cohort that still cannot be formed becomes None, which reads as "no peer group" rather than
    as an empty one.
    """
    if profile is None or profile.cohort is None:
        return profile
    cohort = profile.cohort
    if cohort.employee_band or cohort.revenue_band:
        return profile   # current-model cohort, nothing to repair
    profile.cohort = _derive_cohort(profile)
    return profile


def apply_size_override(profile: VendorProfile, size_band: SizeBand) -> VendorProfile:
    """Re-derive the cohort with a CLIENT-supplied headcount band — for a vendor public sources
    gave no size, so no peer group could form. Returns a NEW profile (the store is append-only);
    the posture is untouched, because size never reaches the arithmetic. Only the cohort changes,
    and `size_client_supplied` is set so the card can badge the comparison as resting on a supplied
    size rather than an observed one."""
    updated = profile.model_copy(deep=True)
    updated.cohort = _derive_cohort(updated, size_override=size_band)
    updated.size_client_supplied = True
    updated.computed_at = utcnow()
    return updated


def operating_years(profile: VendorProfile | None) -> float | None:
    """Operating history in years, preferring the ENTITY's inception over its domain's age.

    The preference is the point, not a tie-break. A registered inception date says when the company
    began; a domain creation date says when somebody paid a registrar, and aged domains are bought
    at auction routinely. Where both exist the entity record wins; the domain is the fallback for
    the many private vendors no register describes, and `maturity.py` separately discounts what a
    domain-only claim is worth.

    Used to decide ATTAINABILITY in the target maturity model — whether a vendor has existed long
    enough to hold an artefact that attests to a period of operation. It reaches no penalty.
    """
    if profile is None:
        return None

    if profile.inception is not None:
        from .maturity import years_between
        from .models import utcnow

        raw = profile.inception.value
        when = raw if isinstance(raw, datetime) else None
        if when is None and isinstance(raw, str):
            try:
                when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                when = None
        if when is not None and when.tzinfo is not None:
            years = years_between(when, utcnow())
            if years is not None:
                return years

    if profile.domain_age_days is not None:
        try:
            return max(0.0, float(profile.domain_age_days.value) / 365.25)
        except (TypeError, ValueError):
            return None
    return None


def _completeness(profile: VendorProfile) -> float:
    filled = sum(1 for name in _COUNTED if getattr(profile, name) is not None)
    return round(filled / len(_COUNTED), 3)


# --------------------------------------------------------------------- small helpers


_COUNTRY_NAMES = {
    "australia": "AU", "new zealand": "NZ", "united states": "US",
    "united states of america": "US", "canada": "CA", "united kingdom": "GB",
    "ireland": "IE", "germany": "DE", "france": "FR", "netherlands": "NL",
    "singapore": "SG", "india": "IN", "japan": "JP", "china": "CN",
}


def _country_code(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    return _COUNTRY_NAMES.get(name.strip().lower())


def _days_since(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    from .models import utcnow

    if when.tzinfo is None:
        return None
    return max(0, (utcnow() - when).days)


def _lifecycle_stage(operating_years: float | None) -> "LifecycleStage | None":
    """Map operating years to an Adizes-derived stage label.

    Thresholds are approximate — the model does not publish hard boundaries. These are
    calibrated to the five bands already in scoring.yaml's `entity_maturity` signal:
    new_lt_1 / startup_lt_2 / young_2_5 / established_5_10 / mature_gt_10, widened at
    the top (>10 stays 'prime' until 15, beyond which institutional path-dependency
    typically dominates). Adjust here; there is no other place.
    """
    
    if operating_years is None:
        return "unknown"
    if operating_years < 1.0:
        return "infancy"
    if operating_years < 2.0:
        return "go_go"
    if operating_years < 5.0:
        return "adolescence"
    if operating_years < 15.0:
        return "prime"
    return "aging"