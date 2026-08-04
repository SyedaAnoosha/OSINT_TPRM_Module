"""The published shapes of the benchmarking layer.

These live in the package rather than in the top-level `models.py` because they are a self-contained
subsystem with one entry point, and because the split makes decision 4 STRUCTURAL rather than
procedural: `CohortSnapshot` carries member refs, `PublicCohortSnapshot` cannot, and the only way to
get from one to the other is `.public()`. A route that serialises the wrong one is a type error at
review time instead of a confidentiality incident at run time.

NOTHING HERE IS A SCORE. Every numeric field is either an input passed through unchanged, a
statistic over peers, or a rank. There is deliberately no field that blends posture with confidence,
and deliberately no composite "benchmark score" across domains — a blend hides the one domain a
given buyer actually cares about, which is the whole reason per-domain comparison exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..models import utcnow

# --------------------------------------------------------------------------- vocabulary

SizeBand = Literal["micro", "small", "mid", "large", "enterprise"]
DeliveryModel = Literal["saas", "on_prem", "managed"]
DataAccessScope = Literal["low", "medium", "high", "critical"]

#: Where a peer's data came from. Published as a COMPOSITION beside every `n`, because cohort
#: quality is not inferable from cohort size — twelve assessed suppliers can be a better basis than
#: forty OSINT-only signals, and a reader cannot tell which they are looking at from `n` alone.
PeerSourceClass = Literal["osint_only", "osint_plus_questionnaire", "attested"]

#: The placement bucket that drives the procurement action lookup. Deliberately coarser than a
#: quartile number so the action table stays legible.
PlacementBucket = Literal[
    "bottom_quartile", "lower_mid", "upper_mid", "top_quartile", "insufficient_peers"
]

Direction = Literal["above", "at", "below"]

#: `untested` is a first-class verdict, not an error: below `min_observations` the discrimination
#: test itself is not meaningful, and saying so beats guessing in either direction.
Discrimination = Literal["discriminating", "non_discriminating", "untested"]

DisputeState = Literal["submitted", "under_review", "upheld", "partially_upheld", "rejected"]

#: What a supplier may contest. The INPUTS only — never the cohort, the snapshot, or the resulting
#: cell. Same discipline the platform applies to Residual Risk: a supplier disputes its posture or
#: its tier, never the cell they land in, because the cell carries no independent judgement.
DisputeTarget = Literal["sector", "size_band", "delivery_model", "headcount", "revenue"]


# --------------------------------------------------------------------------- inputs


class SizeBandDerivation(BaseModel):
    """How one `size_band` was arrived at — the object a supplier actually disputes.

    Both raw inputs and both intermediate bands are retained, because the interesting case is
    DISAGREEMENT: a 240-person firm turning over A$310M bands `small` on headcount and `large` on
    revenue, and a reader who sees only `large` cannot tell whether that was a judgement or a
    typo. `resolved_by` names which input won.
    """

    band: SizeBand | None = Field(default=None, description="None when neither input was known")
    rule_version: int
    resolve: str = Field(..., description="max | headcount | revenue")
    employees: int | None = None
    employee_band: SizeBand | None = None
    revenue_aud: float | None = Field(default=None, description="Converted for BANDING ONLY")
    revenue_band: SizeBand | None = None
    resolved_by: Literal["headcount", "revenue", "agreement", "none"] = "none"
    disagreed: bool = Field(
        default=False,
        description="True when the two inputs banded differently — informative, not an error",
    )

    def basis(self) -> str:
        """One sentence a dispute reviewer can read without opening the code."""
        if self.band is None:
            return "No size band: neither headcount nor revenue was available."
        # ASCII arrows deliberately: this string reaches logs and CSV exports as well as JSON, and a
        # Windows console at cp1252 raises UnicodeEncodeError on U+2192 rather than degrading.
        parts = []
        if self.employee_band:
            parts.append(f"headcount {self.employees} -> {self.employee_band}")
        if self.revenue_band:
            parts.append(f"revenue A${self.revenue_aud:,.0f} -> {self.revenue_band}")
        joined = "; ".join(parts) or "no inputs"
        note = " (inputs disagreed)" if self.disagreed else ""
        return (
            f"{joined}. Resolved `{self.band}` by rule v{self.rule_version} "
            f"(`{self.resolve}`, decided on {self.resolved_by}){note}."
        )


class SupplierFirmographics(BaseModel):
    """What the cohort is computed from — plus the one attribute that is deliberately NOT.

    `data_access_scope` sits on this object because it travels with the supplier record, but it is
    absent from every cohort key: it is a property of the RELATIONSHIP, not of the supplier, and
    keying on it would put the same supplier in different cohorts for different buyers. It routes to
    interpretation — it picks the procurement action — and nowhere else. Decision 1.
    """

    supplier_ref: str
    supplier_name: str | None = None
    sector: str | None = None
    delivery_model: DeliveryModel | None = None
    employees: int | None = None
    revenue: float | None = Field(default=None, description="Native units, as reported")
    revenue_currency: str | None = None
    data_access_scope: DataAccessScope | None = Field(
        default=None,
        description="Buyer-side. Selects the procurement action; NEVER a cohort dimension.",
    )


class SupplierAttributes(BaseModel):
    """The raw inputs a cohort is derived from, as one stored, append-only row.

    THIS IS THE SOURCE OF TRUTH; the cohort tables are a materialisation of it. That is what makes
    "cohorts are rebuildable from raw data, no manual overrides baked into the DB" true rather than
    aspirational — and it is why an upheld dispute appends a corrected row here instead of editing a
    cohort: the derivation is then re-run over the correction and the result is diffable.

    `size_band` is stored alongside its own `size_band_basis` because a derived value with no record
    of its derivation is exactly what a supplier cannot argue with.
    """

    supplier_ref: str
    sector: str | None = None
    size_band: SizeBand | None = None
    delivery_model: DeliveryModel | None = None
    data_access_scope: DataAccessScope | None = Field(
        default=None, description="Interpretation only. Never a cohort dimension."
    )
    employees: int | None = None
    revenue: float | None = None
    revenue_currency: str | None = None
    size_band_basis: str | None = None
    source: Literal["derived", "client_supplied", "dispute_upheld"] = "derived"


class PeerRecord(BaseModel):
    """One comparable supplier, as the benchmarking layer sees it.

    `domains` and `signals` are separate because they are different kinds of measurement and get
    different statistics: a domain score is continuous and gets an IQR, a signal band is a string
    and gets a modal share. Conflating them is how a discrimination test ends up computing the
    variance of a set of words.

    A domain absent from `domains` means the peer was never assessed for it — which is NOT the same
    as scoring zero, and it leaves that domain's denominator rather than dragging its median down.
    """

    supplier_ref: str
    posture: int = Field(..., ge=0, le=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    domains: dict[str, int] = Field(default_factory=dict)
    signals: dict[str, str] = Field(default_factory=dict)
    computed_at: datetime | None = None
    source_class: PeerSourceClass = "osint_only"


# --------------------------------------------------------------------------- cohort


class LadderRungResult(BaseModel):
    """One rung tried, and what it held. The list of these IS the assignment rationale.

    Recorded for every rung including the ones that failed, because *"we wanted
    sector+size+delivery, that held 6, so you are in sector+size at 34"* is the answer to the only
    question a supplier asks about their cohort, and reconstructing it after the fact is guesswork.
    """

    rung: tuple[str, ...]
    label: str
    n: int
    satisfied: bool
    skipped_reason: str | None = Field(
        default=None,
        description="Set when the rung could not be evaluated at all, e.g. the supplier has no "
                    "size_band, so the rung was skipped rather than failed",
    )


class CohortAssignment(BaseModel):
    """The peer group this supplier belongs to — exactly one, always.

    ASSIGNMENT AND PLACEMENT ARE SEPARATE. Every supplier gets an assignment even when the cohort is
    far too thin to place them in; `placeable` records which case this is. Collapsing the two would
    mean a supplier in a sparse sector has no cohort at all, and then there is nothing to show them,
    nothing to dispute, and nothing to fill.
    """

    cohort_key: str = Field(..., description="Canonical, e.g. 'sector=technology|size_band=large'")
    rung: tuple[str, ...]
    rung_label: str
    dimensions: dict[str, str] = Field(
        default_factory=dict, description="The resolved dimension values this cohort matched on"
    )
    n: int = Field(..., ge=0, description="Peers, EXCLUDING the subject")
    placeable: bool = Field(
        ..., description="False when n is below min_quartile_n — assigned but not comparable"
    )
    widened: bool = Field(
        ..., description="True when the ladder had to walk below the configured floor"
    )
    size_band: SizeBandDerivation
    sector_group: str | None = None
    rationale: list[LadderRungResult] = Field(default_factory=list)

    def rationale_text(self) -> str:
        """The assignment in one sentence, for the card and for a dispute reviewer."""
        tried = ", ".join(
            f"{r.label} (n={r.n}{', skipped' if r.skipped_reason else ''})"
            for r in self.rationale
            if not r.satisfied
        )
        head = f"Assigned {self.rung_label}, n={self.n}."
        return f"{head} Tried first: {tried}." if tried else head


class Distribution(BaseModel):
    """A peer distribution. Nearest-rank throughout, never interpolated — an interpolated median
    between two real suppliers is a company that does not exist."""

    n: int = Field(..., ge=0)
    median: int | None = None
    p25: int | None = None
    p75: int | None = None
    minimum: int | None = None
    maximum: int | None = None

    def iqr(self) -> int | None:
        if self.p25 is None or self.p75 is None:
            return None
        return self.p75 - self.p25


class DomainStats(BaseModel):
    """One domain's distribution across the cohort, with ITS OWN n.

    The separate `n` is load-bearing. A cohort of 40 may hold only 12 suppliers with an `email_auth`
    score, so a card legitimately shows an overall percentile beside a domain quartile beside a
    domain refusal — and that reads as an inconsistency unless every row carries its own population.
    """

    domain: str
    distribution: Distribution
    discrimination: Discrimination = "untested"


class DiscriminationVerdict(BaseModel):
    """Whether a signal or domain varies enough across this cohort to rank anything.

    A signal that does not vary cannot order suppliers; it shifts the intercept. Reported rather
    than dropped, because *"every supplier in your cohort fails this"* is itself worth knowing — it
    is just not a comparison, and it must never appear in a "you are behind your peers" list.
    """

    key: str
    kind: Literal["domain", "signal"]
    verdict: Discrimination
    statistic: str = Field(..., description="Which test was applied, e.g. 'modal_share'")
    value: float | None = None
    observations: int = 0
    detail: str | None = Field(
        default=None, description="Plain-English reading, e.g. '38 of 38 peers in band `many`'"
    )


class CohortSnapshot(BaseModel):
    """The cohort AS AT one build — the artefact a placement stays reproducible against.

    APPEND-ONLY. A rebuild mints a new snapshot; nothing is ever mutated. That is what makes the
    single most useful question in the product answerable: *"why did my quartile change?"* Diff two
    snapshots and it is either the supplier's posture that moved or the cohort's median — and the
    placement delta says which.

    ⚠️ CARRIES `member_refs`. Decision 4: member refs are stored so a dispute reviewer can answer
    "who was I compared against?", and are NEVER published — publishing one tenant's supplier list
    to another tenant's supplier is a confidentiality breach dressed as transparency. Use
    `.public()` on every outbound path. There is no route that serialises this type directly.
    """

    snapshot_id: str
    cohort_key: str
    rung: tuple[str, ...]
    rung_label: str
    dimensions: dict[str, str] = Field(default_factory=dict)
    distribution: Distribution
    domains: list[DomainStats] = Field(default_factory=list)
    data_sources: dict[str, int] = Field(
        default_factory=dict,
        description="Composition by PeerSourceClass — 'n=23, of which 3 attested' is a different "
                    "claim from 'n=23', and cohort quality is not inferable from n alone",
    )
    peer_confidence_median: float | None = Field(
        default=None,
        description="DISCLOSED, never filtered on. Excluding thinly-evidenced peers would bias the "
                    "cohort toward the observable, i.e. toward large companies.",
    )
    stale_peers: int = Field(default=0, description="Peers older than the freshness window — counted "
                                                   "and disclosed, not dropped")
    is_synthetic: bool = Field(
        default=False,
        description="HARD GATE. When true no percentile and no quartile is published at any n.",
    )
    non_discriminating: list[DiscriminationVerdict] = Field(default_factory=list)
    member_refs: list[str] = Field(
        default_factory=list, description="INTERNAL ONLY — never serialised to a tenant route"
    )
    member_postures: list[int] = Field(
        default_factory=list,
        description="INTERNAL ONLY. Sorted, ref-stripped peer postures — what a rank and a quartile "
                    "are actually computed from. Stored because REPRODUCIBILITY REQUIRES IT: five "
                    "order statistics can rebuild a median but not a rank, so a historical placement "
                    "re-derived from summary stats alone would not reproduce. Sorted and detached "
                    "from refs so it carries a distribution and not an identifiable peer.",
    )
    domain_values: dict[str, list[int]] = Field(
        default_factory=dict,
        description="INTERNAL ONLY. Per-domain sorted peer values, over only the peers that covered "
                    "each domain — so a domain's population is its own, never the cohort's.",
    )
    member_hash: str = Field(
        default="", description="sha256 over the sorted member refs; identifies the exact population"
    )
    last_refreshed: datetime = Field(default_factory=utcnow)

    def public(self) -> PublicCohortSnapshot:
        """The tenant-safe projection. The one way member refs leave this object: they don't."""
        return PublicCohortSnapshot(
            snapshot_id=self.snapshot_id,
            cohort_key=self.cohort_key,
            rung_label=self.rung_label,
            dimensions=self.dimensions,
            n=self.distribution.n,
            distribution=self.distribution,
            domains=self.domains,
            data_sources=self.data_sources,
            peer_confidence_median=self.peer_confidence_median,
            stale_peers=self.stale_peers,
            is_synthetic=self.is_synthetic,
            non_discriminating=self.non_discriminating,
            member_hash=self.member_hash,
            last_refreshed=self.last_refreshed,
        )


class PublicCohortSnapshot(BaseModel):
    """What a tenant, a supplier or an export may see: aggregates, and the hash that pins them.

    `member_hash` is included deliberately. It lets an auditor confirm two placements were computed
    against the identical population without ever learning who that population was — which is the
    whole of what transparency requires here.
    """

    snapshot_id: str
    cohort_key: str
    rung_label: str
    dimensions: dict[str, str] = Field(default_factory=dict)
    n: int
    distribution: Distribution
    domains: list[DomainStats] = Field(default_factory=list)
    data_sources: dict[str, int] = Field(default_factory=dict)
    peer_confidence_median: float | None = None
    stale_peers: int = 0
    is_synthetic: bool = False
    non_discriminating: list[DiscriminationVerdict] = Field(default_factory=list)
    member_hash: str = ""
    last_refreshed: datetime


# --------------------------------------------------------------------------- placement


class Placement(BaseModel):
    """Where one value sits in one distribution, at the resolution the sample can actually express.

    THE THRESHOLDS ARE THE PRODUCT:
      * `n < min_quartile_n`   -> nothing but `n` and a refusal. No quartile, no percentile.
      * `n < min_percentile_n` -> quartile + rank. NO percentile.
      * otherwise              -> percentile, with its resolution published beside it.
      * `is_synthetic`         -> nothing, at ANY n.

    `rank_of_n` is REQUIRED rather than optional. "17th of 34" needs no estimator choice, cannot
    overstate its own precision, and survives one peer joining — all three of which a quartile
    letter fails at small n.
    """

    subject: int | None = Field(default=None, description="The input value, passed through unchanged")
    n: int = Field(..., ge=0)
    sufficient: bool = Field(..., description="False -> 'Insufficient peer data', with n")
    quartile: int | None = Field(default=None, ge=1, le=4)
    quartile_label: str | None = Field(
        default=None, description="e.g. 'bottom quartile' — always sent, because a bare Q1 is "
                                 "ambiguous: it means 'best' in finance and 'worst' elsewhere"
    )
    quartile_direction: str = Field(
        default="1 = lowest posture, 4 = highest posture",
        description="Stated in the payload so a client cannot invert it",
    )
    percentile: int | None = Field(default=None, ge=0, le=100)
    percentile_resolution: int | None = Field(
        default=None, description="The finest step this sample can express, in percentile points"
    )
    rank_of_n: int | None = Field(default=None, ge=1, description="1 = highest posture in cohort")
    tied_with: int = Field(default=0, description="Peers sharing the subject's exact value")
    median: int | None = None
    direction: Direction | None = None
    delta_from_median: int | None = None
    outlier_low: bool = Field(
        default=False,
        description="Below the cohort's lower IQR fence. IQR rather than standard deviations: SD "
                    "assumes normality and one extreme member is a large share of an n=12 cohort.",
    )
    bucket: PlacementBucket = "insufficient_peers"
    reason: str | None = Field(default=None, description="Why nothing was published, when nothing was")


class DomainPlacement(BaseModel):
    """One domain's placement, with its own population and its own resolution."""

    domain: str
    label: str
    placement: Placement
    discrimination: Discrimination = "untested"
    suppressed: bool = Field(
        default=False,
        description="True when the domain does not discriminate in this cohort, so it is disclosed "
                    "in its own section rather than listed as a peer gap",
    )


class ReliabilityFactors(BaseModel):
    """How much weight the COMPARISON deserves — itemised, never a single opaque number.

    A reader shown `0.42` learns nothing. One shown *"n=9 (thin) × widened to sector-only × peer
    median confidence 0.55"* knows what to fix, and knows it is a fact about our coverage rather
    than about the supplier.

    This is NOT the supplier's confidence and never merges with it — see `BenchmarkPlacement`.
    """

    sample_adequacy: float = Field(..., ge=0.0, le=1.0)
    rung_exactness: float = Field(..., ge=0.0, le=1.0)
    peer_evidence: float = Field(..., ge=0.0, le=1.0)
    freshness: float = Field(..., ge=0.0, le=1.0)
    value: float = Field(..., ge=0.0, le=1.0, description="Roll-up of the four factors above")
    band: Literal["High", "Medium", "Low"]
    notes: list[str] = Field(default_factory=list, description="One line per factor worth reading")


class PlacementDelta(BaseModel):
    """Movement since a previous placement, attributed.

    THE POINT: separate "you moved" from "the cohort moved". A supplier that improved three points
    while its cohort improved seven has lost ground without doing anything wrong, and no other
    output in the system can say so.
    """

    previous_snapshot_id: str | None = None
    posture_change: int | None = None
    cohort_median_change: int | None = None
    quartile_change: int | None = None
    net_effect: str | None = Field(default=None, description="Plain-English attribution")


class BenchmarkPlacement(BaseModel):
    """The published artefact: one supplier, one cohort, two audiences.

    THE TWO CONFIDENCES STAY APART. `supplier_confidence` is an input, passed through untouched.
    `reliability` is a property of the comparison. They are never multiplied together and never
    blended into posture — a benchmark that folded coverage into the number would be the
    single-axis rating this platform exists to refuse.

    THERE IS NO COMPOSITE BENCHMARK SCORE. `overall` places the posture; `domains` place each domain
    independently. Blending the domains into one figure would hide the single domain a given buyer
    cares about, which is the entire reason per-domain comparison exists.
    """

    supplier_ref: str
    supplier_name: str | None = None
    assessed_at: datetime = Field(default_factory=utcnow)

    assignment: CohortAssignment
    snapshot: PublicCohortSnapshot

    overall: Placement
    domains: list[DomainPlacement] = Field(default_factory=list)

    supplier_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="INPUT, unchanged. Never blended with posture."
    )
    confidence_flagged: bool = Field(
        default=False,
        description="Supplier confidence below the configured floor. The placement is LABELLED and "
                    "still published — suppressing it would hide a fact about our own coverage.",
    )
    reliability: ReliabilityFactors

    data_access_scope: DataAccessScope | None = None
    delta: PlacementDelta | None = None

    disputed: bool = Field(
        default=False,
        description="An open cohort dispute exists. Notated on the placement until resolved — the "
                    "US Chamber / FCRA principle the platform already accepts for scores.",
    )
    open_dispute_ids: list[str] = Field(default_factory=list)

    security_narrative: list[str] = Field(default_factory=list)
    procurement_narrative: list[str] = Field(default_factory=list)
    action: str | None = None
    action_disclaimer: str | None = None
    caveats: list[str] = Field(default_factory=list)

    config_version: str = ""
    narrative_version: int = 0


# --------------------------------------------------------------------------- dispute


class CohortDispute(BaseModel):
    """One append-only event in the life of a cohort dispute.

    EXTENDS the existing dispute machinery with a target discriminator rather than duplicating it:
    same append-only-events shape, same "current state is the latest event" rule, same audit
    guarantee. What differs is what is being contested.

    WHAT IS DISPUTABLE: the INPUTS — sector, size_band and its two raw values, delivery_model.
    WHAT IS NOT: the cohort, the snapshot, or the resulting cell. A cell is a deterministic lookup
    over disputable inputs and carries no independent judgement, so there is nothing in it to
    contest; the argument resolves by re-examining an input, each of which has its own path.

    AN UPHELD DISPUTE IS NOT A DATABASE EDIT. Cohorts are rebuildable from raw data by definition,
    so the resolution changes the supplier's ATTRIBUTE, a rebuild mints a new snapshot, and a new
    placement follows. Historical placements keep pointing at the snapshot they were computed
    against — which is precisely why the snapshot is stored.
    """

    id: str = Field(..., description="UUID of THIS event")
    dispute_id: str = Field(..., description="Groups the events of one dispute; current = latest")
    supplier_ref: str
    state: DisputeState
    target: DisputeTarget
    asserted_value: str | None = Field(
        default=None, description="What the supplier says it should be"
    )
    observed_value: str | None = Field(default=None, description="What we assigned")
    cohort_key_at: str | None = Field(
        default=None, description="The cohort in force when the dispute was raised"
    )
    snapshot_id_at: str | None = None
    evidence: str = Field(..., description="What the supplier submitted. Retained verbatim.")
    actor: str | None = None
    note: str | None = Field(default=None, description="Reviewer reasoning, on resolution")
    content_hash: str = ""
    created_at: datetime = Field(default_factory=utcnow)


OPEN_DISPUTE_STATES: frozenset[str] = frozenset({"submitted", "under_review"})
