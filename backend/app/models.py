"""Pydantic contracts shared across the pipeline.

These models ARE the schema of the evidence store and the API simultaneously —
one definition, no drift. That matters here because the evidence store is a legal
artefact (methodology Finding A): every score must be reconstructible from what was
retained, so the shapes below are deliberately explicit about provenance
(`source`, `fetched_at`, `source_version`, `locator`).

Pipeline order (scoring.yaml PIPELINE ORDER; not negotiable):
    entity-resolution -> collect -> EVIDENCE STORE (first) -> normalize
    -> finding modifiers -> signal -> subcategory mean -> category mean
    -> GATE -> overall mean -> KNOCKOUT FLOOR -> confidence + quadrant
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CollectorStatus = Literal["ok", "empty", "error", "timeout", "skipped_tos"]
"""Outcome of a single collector run.

`empty` is a FIRST-CLASS result, not an error: it means the source was reached and
returned nothing for this vendor (e.g. no SEC filing for a private company). Per
methodology §5.4 it must reduce *confidence*, never *risk* — so it is persisted and
scored as absence-of-evidence, never dropped and never treated as a 0-risk signal.
"""

# Derived from operating years (entity inception or domain age). Context only — never scored.
# Age's two legitimate homes in this system are already taken: confidence (scoring.yaml
# assurance_multiplier) and attainability (benchmarks.yaml attainable_after_years).
# This label is a third home: the UI display layer, so a reader understands WHAT they are
# looking at when benchmarking a 2-year-old vendor against a 40-year-old one.
LifecycleStage = Literal["infancy", "go_go", "adolescence", "prime", "aging", "unknown"]


def utcnow() -> datetime:
    """Timezone-aware UTC now. All timestamps in this system are tz-aware UTC."""
    return datetime.now(UTC)


class Vendor(BaseModel):
    """The subject of an assessment, after entity resolution.

    `ref` is the canonical internal id (a slug) that ties every Evidence, Finding and
    Score row back to one resolved identity. `resolution_confidence` below 0.5 must
    gate the whole assessment to BLOCKED (never silently score the wrong company —
    scoring.yaml gates.entity_ambiguous).
    """

    ref: str = Field(..., description="Canonical internal id (slug), e.g. 'atlassian'")
    name: str | None = None
    domain: str | None = None
    aliases: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolution_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "How sure we are this is the company the caller meant. None until derived from the "
            "registries after collection (app.entity_resolution) — a caller-supplied value is an "
            "explicit override, not the normal path."
        ),
    )
    resolution_basis: str | None = Field(
        default=None,
        description="Plain-English reason for the confidence — a blocked record must say WHY.",
    )
    domain_source: str = Field(
        default="supplied",
        description=(
            "'supplied' — the caller named or confirmed this domain. 'inferred' — it was guessed "
            "from a company name and never confirmed, which BLOCKS: scoring a guessed domain is "
            "the shortcut this system refuses (see app.entity_resolution)."
        ),
    )
    operating_years: float | None = Field(
        default=None,
        description="Years since incorporation (computed from incorporation_date or fallback sources)"
    )

    @field_validator("domain")
    @classmethod
    def _normalise_domain(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        for prefix in ("https://", "http://", "www."):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v.rstrip("/") or None


class Finding(BaseModel):
    """One observation from a collector, normalized enough to be scored later.

    A collector emits Findings carrying WHAT was observed and WHERE (`locator`); the
    scoring engine (Phase 2) maps `signal`/`observed` onto a band in scoring.yaml and
    fills `severity_base`, then applies the NIST SP 1326 modifiers. Keeping severity
    off the collector keeps the model — not the collector — the single source of truth
    for how an observation becomes a number.
    """

    source: str = Field(..., description="Collector id, e.g. 'dns'")
    signal: str = Field(..., description="scoring.yaml signal key, e.g. 'dmarc'")
    subcategory: str | None = Field(default=None, description="scoring.yaml subcategory key")
    category: str | None = Field(default=None, description="scoring.yaml category key")

    observed: str = Field(..., description="Human-readable observed value, e.g. 'p=none'")
    value: Any | None = Field(default=None, description="Structured value for scoring")
    event_date: datetime | None = Field(
        default=None,
        description="Date the evidence PERTAINS to (cert notAfter, breach date) — drives age decay",
    )
    locator: str | None = Field(
        default=None, description="Where in raw this came from (URL, record id, key path)"
    )
    remediation_evidenced: bool = Field(
        default=False,
        description=(
            "Remediation CORROBORATED by the source, not merely claimed — drives the NIST SP 1326 "
            "mitigation factor (x0.6). Default False: a collector must positively evidence a fix. "
            "No current free source evidences remediation, so nothing sets this True yet."
        ),
    )

    # Filled by the normalizer/scoring engine, not the collector:
    severity_base: float | None = Field(default=None, ge=0.0, le=100.0)
    notes: str | None = None


class CollectorResult(BaseModel):
    """The uniform envelope every collector returns.

    The scoring engine never knows or cares which source produced a result — it reads
    this shape only. `raw` is persisted verbatim to the evidence store BEFORE any
    scoring; `source_version` (e.g. the KEV catalogVersion, an ETag, a list date) is
    what lets a screen be reconstructed "as it stood at the time" — load-bearing for
    the sanctions defence (Finding B).
    """

    source: str = Field(..., description="Collector id, e.g. 'dns'")
    vendor_ref: str
    status: CollectorStatus
    fetched_at: datetime = Field(default_factory=utcnow)
    source_version: str | None = Field(
        default=None, description="Version/date/etag of the source data — kept for reconstruction"
    )
    raw: dict[str, Any] | None = Field(default=None, description="Verbatim response -> evidence")
    findings: list[Finding] = Field(default_factory=list)
    reliability: float = Field(
        ..., ge=0.0, le=1.0, description="Source reliability (source_assessment.md), not invented"
    )
    notes: str | None = None

    @field_validator("fetched_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware (UTC)")
        return v.astimezone(UTC)


class Evidence(BaseModel):
    """A persisted, immutable record of one CollectorResult.

    `content_hash` is a sha256 over the canonical JSON of the stored payload; it is what
    the Phase 0 exit criterion checks ("written and read back byte-identical") and what
    proves at audit time that a stored record was not altered.
    """

    id: str = Field(..., description="UUID assigned at write time")
    vendor_ref: str
    source: str
    status: CollectorStatus
    fetched_at: datetime
    source_version: str | None
    raw: dict[str, Any] | None
    reliability: float
    notes: str | None
    content_hash: str = Field(..., description="sha256 of the canonical stored payload")
    stored_at: datetime = Field(default_factory=utcnow)


class PersistedFinding(BaseModel):
    """A stored, immutable, signal-level finding — what a source actually observed, mapped to a
    severity and penalty by the model.

    This is the *interpreted* evidence, persisted alongside the raw `Evidence` it was derived
    from (`evidence_id`), so a score's deductions are auditable per SIGNAL, not just per source:
    "DMARC was `p=none` -> Medium -> -8, from evidence <hash>". Like `Evidence` it is append-only
    and `content_hash`-stamped, so the interpretation that stood behind a published score cannot
    be silently re-derived differently after a `scoring.yaml` change (methodology Finding A).
    """

    id: str = Field(..., description="UUID assigned at write time")
    vendor_ref: str
    evidence_id: str | None = Field(default=None, description="the raw Evidence row this came from")
    source: str
    category: str
    signal: str = Field(..., description="scoring.yaml signal key, e.g. 'dmarc'")
    band_key: str = Field(..., description="the observed band looked up in scoring.yaml")
    severity: str | None = Field(default=None, description="pass/low/medium/high/critical; None for sanctions")
    penalty: float = Field(..., ge=0.0, description="base points subtracted (0 for pass/informational)")
    effective_penalty: float = Field(
        default=0.0, ge=0.0,
        description=(
            "What was ACTUALLY subtracted after the NIST modifiers (age x frequency x mitigation) "
            "and after the group collapsed to its worst member. This is the number that adds up to "
            "the category penalty — `penalty` is the pre-adjustment base and will not."
        ),
    )
    occurrences: int = Field(
        default=1, ge=1,
        description="How many times this signal fired for this vendor — 3 breaches, 40 CVE matches",
    )
    run_id: str | None = Field(
        default=None,
        description=(
            "The scoring run (published Score id) this finding belongs to. Findings are "
            "append-only, so reads default to the current run — otherwise a re-scored vendor "
            "shows every deduction once per run."
        ),
    )
    frequency_amplified: bool = Field(
        default=False,
        description=(
            "Whether those occurrences were read as a PATTERN (penalty x frequency factor) or as a "
            "coarse-match BAG (worst one counted, no amplification). Derived at serve time from "
            "modifiers.frequency.exempt_signals — the UI must not claim a pattern treatment that "
            "a frequency-exempt signal like a keyword-matched CVE list never received."
        ),
    )
    observed: str = Field(..., description="human-readable observed value, e.g. 'p=none'")
    reason: str | None = Field(
        default=None,
        description=(
            "Plain-English explanation of this deduction, read from scoring.yaml `reasons` at "
            "SERVE time rather than stored. The frozen fact is `band_key`; the sentence is "
            "presentation, so re-wording it for clarity improves old scores instead of rewriting "
            "history. None for passing bands — nothing was deducted, nothing to explain."
        ),
    )
    action: str | None = Field(
        default=None,
        description=(
            "What to DO about this deduction. Read from scoring.yaml `actions` at SERVE time, not "
            "stored — same discipline as `reason`: the frozen fact is `band_key`, the advice is "
            "presentation, so improving the wording improves old records instead of rewriting them."
        ),
    )
    ask_of_vendor: str | None = Field(default=None, description="The exact question, copy-pasteable")
    recheck_after: str | None = Field(default=None, description="7d | 30d | 90d")
    accepts_as_refute: str | None = Field(
        default=None, description="What evidence would close this finding — the dispute path's input"
    )
    promoted_by: str | None = Field(
        default=None,
        description=(
            "Sector whose industry profile raised this severity, if any. Published so a reader can "
            "see WHICH rule fired: a promotion nobody can see is indistinguishable from a model "
            "that scores inconsistently."
        ),
    )
    base_severity: str | None = Field(
        default=None, description="Severity before any sector promotion"
    )
    dispute: str | None = Field(
        default=None,
        description=(
            "Set when an accepted refute changed this finding: 'nullified' (penalty removed) or "
            "'mitigated' (×0.6). Shown on the receipt so a discounted deduction says WHY."
        ),
    )
    event_date: datetime | None = Field(default=None, description="date the evidence pertains to")
    is_critical: bool = Field(default=False, description="directly-observed current critical -> ceiling")
    is_sanctions: bool = Field(default=False, description="gate input, never scored")
    note: str | None = None
    content_hash: str = Field(..., description="sha256 of the canonical stored finding")
    stored_at: datetime = Field(default_factory=utcnow)
    value_snapshot: Any = Field(default=None, description="structured data snapshot (e.g., years from entity_maturity)")


SizeBand = Literal["micro", "small", "medium", "large", "mega"]
Region = Literal["anz", "north_america", "uk_eu", "apac", "other"]
Ownership = Literal["listed", "private", "government", "not_for_profit", "unknown"]
Criticality = Literal["low", "medium", "high"]
# P8. How easily this vendor could be replaced if the relationship ended — CLIENT-SUPPLIED, same
# discipline as `Criticality`: switching cost and lock-in are not observable from outside, and
# guessing would be our opinion dressed as the buyer's exposure.
Substitutability = Literal["sole_source", "low", "medium", "high"]


class ProfileField(BaseModel):
    """One firmographic fact plus the provenance that makes it checkable.

    Firmographics obey the same rule as every other observation: a value a reader cannot trace
    to a source is not evidence, it is an assertion. So the value never travels alone.
    """

    value: Any
    source: str = Field(..., description="Collector id that produced it, e.g. 'firmographics'")
    locator: str | None = Field(default=None, description="URL / record id / property path")
    fetched_at: datetime | None = Field(
        default=None, description="When WE read it — not when the fact was true"
    )
    as_of: str | None = Field(
        default=None,
        description=(
            "When the FACT was reported, where the source dates it. `fetched_at` and `as_of` answer "
            "different questions, and conflating them is how a 2015 headcount gets presented as "
            "today's: we read Wikidata this morning, and the figure in it is eleven years old."
        ),
    )


class PeerCohort(BaseModel):
    """The population a vendor may lawfully be compared against — on FOUR factors.

    Comparing a mega-cap US technology vendor with a small Australian food manufacturer is not a
    harsh comparison, it is a meaningless one — different observable surface area, different
    regulatory pressure, different expected posture. The cohort is what makes a comparison mean
    something, so it is computed explicitly and DISCLOSED with every benchmark (including `n`).

    **Revenue and headcount are separate dimensions, not one blended "size".** They disagree often
    and the disagreement is informative: a 40-person firm turning over $400M is a different risk
    proposition from a 4,000-person firm turning over the same amount — one is a high-leverage
    money mover, the other a large employer with a large attack surface. Collapsing them to a
    single band threw that away. Keeping them apart costs cohort density, which is precisely why
    the widening ladder in `benchmark.py` exists.

    Either size dimension may be None: public sources publish headcount far more often than
    private-company revenue, and a cohort that required both would almost never form. The widening
    ladder simply skips any level that needs a dimension this vendor does not have.
    """

    sector: str = Field(..., description="Working sector, e.g. 'technology', 'financial_services'")
    revenue_band: SizeBand | None = Field(default=None, description="Band by reported revenue")
    employee_band: SizeBand | None = Field(default=None, description="Band by headcount")
    region: Region
    ownership: Ownership | None = Field(
        default=None, description="Collected but not keyed by default — see benchmarks.yaml"
    )
    key: str = Field(
        ...,
        description="Canonical key, e.g. 'technology|rev=mega|emp=large|north_america'",
    )


class VendorProfile(BaseModel):
    """Who the vendor is — the context a score is read against, and NEVER an input to it.

    THE RULE THIS TYPE EXISTS TO HOLD (methodology §7.3): a profile field must never move a
    penalty. Coverage already tracks company size rather than company risk; letting revenue or
    headcount touch the arithmetic would let that bias in through the front door, one level up.
    A profile therefore selects the PEER COHORT and the INDUSTRY PROFILE, and does nothing else.
    `tests/test_profile.py` asserts this by scoring each corpus vendor with and without a profile
    and requiring an identical Score.

    Entity-level only (§4.2). `parent` is a corporate parent; directors, officers and beneficial
    owners who are natural persons are excluded here exactly as they are everywhere else — even
    where a source would happily supply them.
    """

    vendor_ref: str
    # The name resolution actually SEARCHED WITH — persisted so a later domain-only re-score (the
    # continuous monitor, a dispute re-score) replays it instead of falling back to the domain slug.
    # The registers have no domain index, so `archerirm.com` → slug "archerirm" matches an Indian
    # subsidiary, while "Archer Technologies" matches the US parent. Remembering the winning name
    # keeps that correction durable across unattended runs; the domain and evidence chain are kept.
    search_name: str | None = None
    legal_name: ProfileField | None = None
    country: ProfileField | None = Field(default=None, description="ISO-2 country of the legal entity")
    jurisdiction: ProfileField | None = None
    industry_label: ProfileField | None = Field(default=None, description="As published by the source")
    industry_code: ProfileField | None = Field(default=None, description="ANZSIC / SIC / NAICS code")
    sector: ProfileField | None = Field(default=None, description="Normalised working sector")
    employees: ProfileField | None = None
    revenue: ProfileField | None = Field(default=None, description="Reported revenue, native units")
    revenue_currency: ProfileField | None = None
    ownership: ProfileField | None = None
    inception: ProfileField | None = Field(default=None, description="Entity inception date")
    parent: ProfileField | None = Field(default=None, description="Corporate parent — never a person")
    domain_age_days: ProfileField | None = None

    # Derived from `operating_years()` in profile.py — never scored, never reaches the engine.
    # Present so the API and UI have a named, typed field rather than re-deriving the same
    # threshold logic in three places. None until `build_profile` runs and `inception` or
    # `domain_age_days` is populated.
    lifecycle_stage: LifecycleStage | None = Field(
        default=None,
        description=(
            "Organisational lifecycle stage — context only. infancy (<1yr) | go_go (1–2yr) | "
            "adolescence (2–5yr) | prime (5–15yr) | aging (>15yr) | unknown. Never scored."
        ),
    )
    # Client-supplied, never inferred: how badly this vendor's failure hurts THIS buyer is not
    # observable from outside, and guessing it would be the least defensible number on the card.
    criticality: Criticality | None = None

    # P8. Client-supplied, never inferred, same discipline as `criticality`: how easily this vendor
    # could be REPLACED if the relationship ended. `sole_source` paired with a poor posture is the
    # single most useful procurement alert this system can raise — a critical dependency with no
    # fallback and weak observable controls — and it cannot be derived, only declared.
    substitutability: Substitutability | None = None

    # True when the declaration above came from `app/inherent_register.py` and NO RELATIONSHIP OWNER
    # HAS CONFIRMED IT YET. A provisional declaration is a real one — it routes P5's depth and
    # publishes an E10b residual tier — but it travels with a caveat saying so, and the programme
    # dashboard counts confirmed and provisional separately rather than as one green number.
    #
    # The same shape as `size_client_supplied` below and as `_derive_cohort`'s `source="default"`
    # sector: a fallback that unblocks a feature is legitimate only where a reader can see it is a
    # fallback. Defaults False, so every profile written before the register existed reads as
    # "not provisional" — correct, because those carried no declaration at all.
    inherent_provisional: bool = False

    # True when the cohort's headcount band came from the CLIENT (added after the score to form a
    # peer group public sources could not), not from an observed figure. Surfaced as a badge so a
    # reader knows the comparison rests on a supplied size — the posture is unaffected either way.
    size_client_supplied: bool = False

    cohort: PeerCohort | None = Field(
        default=None,
        description="None when the profile lacks sector or size — an unclassified vendor gets an "
                    "absolute grade and NO peer percentile, never a guessed one.",
    )
    completeness: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Fraction of profile fields populated. Reported alongside the comparison it "
                    "supports — thin firmographics weaken the COMPARISON, never the posture.",
    )
    computed_at: datetime = Field(default_factory=utcnow)


class CohortStats(BaseModel):
    """The peer distribution behind a benchmark. `n` is published — a percentile whose population
    is hidden is a bought black-box score with extra steps."""

    cohort: PeerCohort
    n: int = Field(..., ge=0, description="Vendors scored in this cohort")
    median: int | None = None
    p25: int | None = None
    p75: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    median_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "Median evidence coverage across the peers. A cohort of thinly-evidenced vendors "
            "produces a thinly-evidenced median, and a reader is entitled to know that before "
            "reading anything into a variance from it."
        ),
    )
    oldest_peer_days: int | None = Field(
        default=None, description="Age of the stalest peer score included, in days"
    )
    excluded_stale: int = Field(
        default=0, description="Peers dropped for exceeding the freshness window — disclosed, not silent"
    )


class SignalPrevalence(BaseModel):
    """How common a control is among this vendor's peers — the sharpest line on the whole card.

    A penalty says a vendor fell short of OUR model. A prevalence says it fell short of its own
    industry: *"79% of your peers publish a DMARC record; you do not."* That is harder to argue
    with and easier to act on, and it is the one figure a vendor can take to their own board.

    Computed only where enough peers were actually CHECKED for the signal — a control nobody was
    assessed on has no prevalence, and inventing one from three observations would be the false
    precision this whole feature is built to refuse.
    """

    signal: str
    band: str = Field(..., description="This vendor's observed band")
    passing: bool = Field(..., description="Whether this vendor passes the signal")
    peers_checked: int = Field(..., ge=0)
    peers_passing: int = Field(..., ge=0)
    peer_pass_rate: float = Field(..., ge=0.0, le=1.0)
    standing: Literal["ahead", "typical", "behind"] = Field(
        ..., description="Where this vendor sits relative to the peer pass rate"
    )


class CategoryBenchmark(BaseModel):
    """One category read against the same peers. 'Your cyber hygiene is below peers but your
    business stability is above' is a far more actionable sentence than a single overall variance,
    and the per-category postures are already stored on every peer's Score."""

    category: str
    posture: int | None = None
    median: int | None = None
    variance_from_median: int | None = None
    percentile: int | None = Field(
        default=None, ge=0, le=100,
        description="Rank within the cohort for THIS category — a vendor can be top-quartile "
                    "overall and bottom-quartile on the one category that matters to you.",
    )
    n: int = Field(default=0, description="Peers that actually covered this category")
    gap_drivers: list[str] = Field(
        default_factory=list,
        description="The findings that account for most of a negative gap, largest first. A gap "
                    "with no named cause is a number; a gap with three named causes is a to-do list.",
    )


ControlStatus = Literal["meets", "partial", "gap", "not_yet_attainable", "unchecked"]


class TargetControl(BaseModel):
    """One control from the target maturity model, evaluated against this vendor.

    `basis` travels with the RESULT, not just the config, because the sentence a reader needs is
    "you are missing X, which BOD 18-01 requires" — a gap without its instrument is an opinion,
    and an opinion is what this whole file refuses to publish.
    """

    signal: str
    observed: str | None = Field(default=None, description="The band actually observed, or None")
    status: ControlStatus
    basis: str = Field(..., description="The named instrument requiring this control")
    attainable_after_years: float = Field(
        default=0.0,
        description=(
            "Years of operating history before this control could exist at all. Non-zero ONLY "
            "where the artefact is arithmetically impossible sooner (an audit observation window), "
            "never as a grace period for something a startup could do on day one."
        ),
    )


class MaturityGap(BaseModel):
    """How this vendor measures against a PUBLISHED baseline — not against its peers.

    THE POINT OF HAVING BOTH. A percentile says whether a vendor is typical; this says whether it
    is adequate. They disagree often and the disagreement is the finding: a vendor at the 60th
    percentile of a weak cohort can still be missing controls a named instrument requires. This
    reading has no dependence on how many vendors the deployment happens to have scored, so it
    works at n=0 peers and cannot inherit the cohort's self-selection skew.
    """

    available: bool = Field(..., description="False when too few controls could be observed")
    reason: str | None = Field(default=None, description="Why not, in words")
    profile_ids: list[str] = Field(default_factory=list, description="Target profiles applied")
    controls: list[TargetControl] = Field(default_factory=list)
    met: int = Field(default=0, description="Controls fully satisfied")
    partial: int = Field(default=0, description="Controls partially satisfied")
    gaps: int = Field(default=0, description="Controls the vendor observably fails")
    applicable: int = Field(
        default=0,
        description=(
            "Controls actually counted — excludes unchecked ones (absence of evidence is not a "
            "failure) and ones not yet attainable at this vendor's age."
        ),
    )
    not_yet_attainable: int = Field(
        default=0, description="Excluded as impossible at this vendor's operating age — disclosed, not silent"
    )
    unchecked: int = Field(default=0, description="No observation for this signal this run")
    attainment: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="(met + 0.5 × partial) / applicable. None when below the publication minimum.",
    )
    summary: str | None = Field(
        default=None, description="The plain sentence a reader gets, e.g. '4 of 6 baseline controls met'"
    )
    vendor_age_years: float | None = Field(
        default=None, description="Operating history used to decide attainability, when known"
    )


class Benchmark(BaseModel):
    """A vendor's posture read against its peers — INTERPRETATION, never arithmetic.

    The published posture is unchanged by anything here. What the benchmark adds is the reading:
    78 is below par for a regulated financial vendor and comfortably above it for a small
    agricultural supplier, and the same 78 is the honest number in both cases.
    """

    available: bool = Field(..., description="False when the cohort is too thin to publish")
    reason: str | None = Field(
        default=None, description="Why not, in words — e.g. 'insufficient peers (3 of 8)'"
    )
    stats: CohortStats | None = None
    posture: int | None = Field(default=None, description="This vendor's posture, for convenience")
    percentile: int | None = Field(default=None, ge=0, le=100)
    percentile_resolution: int | None = Field(
        default=None,
        description=(
            "The finest percentile step this sample can actually express (100/n). With 8 peers "
            "that is 13 points, so a percentile quoted to the unit would be false precision — the "
            "value above is rounded to this step."
        ),
    )
    quartile: int | None = Field(
        default=None, ge=1, le=4,
        description="1 = bottom quarter … 4 = top quarter. Honest at small n, where a percentile is not.",
    )
    variance_from_median: int | None = Field(
        default=None, description="posture − cohort median; negative means below peers"
    )
    categories: list[CategoryBenchmark] = Field(
        default_factory=list, description="Per-category comparison against the same peers"
    )
    signals: list[SignalPrevalence] = Field(
        default_factory=list,
        description="Per-control prevalence — how many peers pass each signal this vendor fails",
    )
    outlier: bool = Field(
        default=False,
        description=(
            "True when this vendor sits below the cohort's lower fence (p25 − 1.5×IQR). Flagged "
            "even at a moderate absolute score: being far below one's own industry is a finding "
            "in itself."
        ),
    )
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "How much weight this COMPARISON bears — distinct from the score's evidence coverage. "
            "A benchmark can be computed from a thin, widened, stale cohort and still print a "
            "number; this says how much to trust it. Same discipline as the score's second axis."
        ),
    )
    confidence_band: str | None = Field(default=None, description="High | Medium | Low")
    level: str | None = Field(
        default=None,
        description=(
            "Which cohort definition actually produced the peers — 'sector+size+region' when the "
            "exact cohort was deep enough, or a widened one when it was not."
        ),
    )
    widened: bool = Field(
        default=False,
        description="True when the exact cohort was too thin and a broader population was used.",
    )
    synthetic: bool = Field(
        default=False,
        description=(
            "True when NO real peer was available and a hard-coded industry reference baseline "
            "stood in. `stats.n` then counts REFERENCE POINTS, NOT COMPANIES — and a reader who "
            "sees 'n=6' beside the word 'peers' will believe six real companies were assessed. "
            "That misreading is the reason this flag exists as a field rather than as a sentence "
            "buried in `caveats`: a renderer must be able to badge it without string-matching "
            "prose. Never publish `stats.n` from a synthetic cohort without showing this."
        ),
    )
    provisional: bool = Field(
        default=False,
        description=(
            "True when the cohort only just cleared the minimum — one peer joining or leaving could "
            "still move the percentile or drop it below the gate. A published-but-fragile signal, "
            "badged so a reader does not treat a barely-populated cohort as a settled one."
        ),
    )
    caveats: list[str] = Field(
        default_factory=list,
        description=(
            "Everything a reader must know to read this comparison correctly — widening, small "
            "samples, stale or thinly-evidenced peers, and the standing self-selection limit. "
            "These are UI requirements, not footnotes."
        ),
    )
    expected_posture: int | None = Field(
        default=None, description="Cited sector expectation, when one is configured with a basis"
    )
    expected_basis: str | None = Field(
        default=None, description="The named source behind `expected_posture`. No basis, no number."
    )
    maturity_gap: MaturityGap | None = Field(
        default=None,
        description=(
            "Measurement against a PUBLISHED baseline rather than against peers. Independent of "
            "cohort size — it survives a thin or absent peer group, which is exactly when the "
            "percentile cannot be published and a reader still needs an answer."
        ),
    )


class Recommendation(BaseModel):
    """What to do about a score — derived deterministically, published as ADVISORY.

    Computed at serve time from published fields by a rule table (`scoring/recommend.py`), never
    stored and never generated. Under Finding A the reasonable-grounds representation attaches to
    what we publish, and a recommendation is published: it has to be reconstructible, and the rule
    behind it nameable. *"The model said do not sign"* is not reasonable grounds.
    """

    decision: Literal[
        "approve", "approve_with_conditions", "approve_pending_questionnaire",
        "request_remediation", "full_due_diligence", "reject",
        "blocked", "insufficient_evidence",
    ]
    headline: str = Field(..., description="One line, in the reader's language")
    detail: str = Field(..., description="Why this, and what to do next")
    recheck_after: str | None = Field(
        default=None, description="Soonest cadence any finding asks for — 7d | 30d | 90d"
    )
    urgency: Literal["stop", "act", "assess", "routine"] = "routine"
    criticality: Criticality | None = Field(
        default=None, description="The client-supplied input this was derived with, echoed back"
    )
    advisory: bool = Field(
        default=True,
        description="Always true. The client makes the risk decision; this states what the "
                    "evidence supports.",
    )


DisputeEvent = Literal["submitted", "accepted", "rejected"]
DisputeKind = Literal["mitigate", "nullify"]


class Dispute(BaseModel):
    """One event in the life of a dispute — append-only, like everything else in the store.

    WHY A DISPUTE PATH EXISTS. Outside-in scoring SYSTEMATICALLY over-penalises, because it cannot
    see the compensating controls a vendor runs behind the perimeter (methodology §7, open item 12).
    Publishing a score with no way to contest it — while knowing the method scores too harshly — is
    a live Finding A exposure, and both benchmarked commercial platforms accept evidenced refutes
    for exactly this reason. This is that route.

    WHY EVENTS, NOT A MUTABLE ROW. The store is append-only (Finding A/B). A dispute is not edited
    from `submitted` to `accepted`; a NEW event row is appended, and the current state of a dispute
    is its latest event. So the whole history — who submitted what evidence, who decided, when — is
    frozen and auditable, and a resolution can never be silently rewritten.

    THE TWO OUTCOMES, and why they are different:
      * `nullify`  — the finding does not apply here at all (an attribution error: "that IP is our
        CDN, not us", or a compensating control that removes the risk). The penalty goes to zero.
      * `mitigate` — the finding is real but remediated with evidence. This drives the NIST
        `mitigation` factor (×0.6), the one modifier that was wired end-to-end but DORMANT because
        no free source evidences a fix. A human-adjudicated refute is that evidence.

    SELF-EXPIRING BY DESIGN. A dispute is keyed to a specific `(signal, band_key)` — a specific
    observation. When the next scan shows a different band (the cert renewed, the record appeared),
    the dispute no longer matches and simply stops applying. A refute cannot outlive the finding it
    refutes, so nobody has to remember to withdraw it.
    """

    id: str = Field(..., description="UUID of THIS event")
    dispute_id: str = Field(..., description="Groups the events of one dispute; current = latest")
    vendor_ref: str
    event: DisputeEvent
    signal: str = Field(..., description="scoring.yaml signal the dispute targets")
    band_key: str = Field(..., description="the specific observed band being disputed")
    kind: DisputeKind
    evidence: str = Field(..., description="what the vendor submitted — a SOC 2 ref, a patch log, "
                                          "an attribution correction. Retained verbatim.")
    actor: str | None = Field(default=None, description="who submitted or adjudicated")
    note: str | None = Field(default=None, description="adjudicator reasoning, on accept/reject")
    content_hash: str = Field(..., description="sha256 of the canonical event")
    created_at: datetime = Field(default_factory=utcnow)


DecisionKind = Literal["approve", "conditional", "reject"]


class Decision(BaseModel):
    """A buyer's decision on a vendor — recorded ALONGSIDE the score, never inside it.

    WHY THIS EXISTS. A score answers "how does this vendor look?"; procurement and executives also
    have to answer "so are we buying, and on what terms?" — the *action*, which the score itself
    deliberately never takes (the model advises; the client decides). Without a place to record it,
    that decision lives in an email thread, unlinked to the evidence it was made on.

    WHY IT CANNOT MOVE THE SCORE. A decision is an output of reading the score, not an input to
    computing it. It emits no finding and touches no penalty — recording "approved" on a vendor
    changes its posture by exactly nothing. This keeps the single-source rule intact: the score is
    reconstructible from evidence alone, and the decision is a separate, auditable fact beside it.

    WHY IT SNAPSHOTS posture_at / grade_at. Append-only, and stamped with the number that was on the
    card at the moment of the call. A vendor re-scored next quarter must not make a past approval
    look better- or worse-founded than it was: "we approved at 72 (C)" stays true forever, even
    after the vendor moves to 40. A change of mind is a NEW decision row, not an edit.
    """

    id: str = Field(..., description="UUID of this decision")
    vendor_ref: str
    decision: DecisionKind
    conditions: str | None = Field(
        default=None, description="the terms, when decision = conditional (e.g. 'remediate KEV "
                                  "before go-live'). Required for a conditional; ignored otherwise.")
    actor: str | None = Field(default=None, description="who recorded it — role or name, client-supplied")
    posture_at: int | None = Field(default=None, description="the posture on the card at decision time")
    grade_at: str | None = Field(default=None, description="the grade on the card at decision time")
    content_hash: str = Field(default="", description="sha256 of the canonical decision")
    created_at: datetime = Field(default_factory=utcnow)


GapAnalysisEventKind = Literal["accepted", "edited", "rejected"]


class GapAnalysisRecord(BaseModel):
    """One generated gap analysis (E14) — a third audience view whose renderer is a language
    model, over a finished record it never adjusts.

    APPEND-ONLY, LIKE EVERYTHING ELSE HERE. A vendor is re-analysed by generating a NEW record,
    never by editing an old one — the same discipline `BenchmarkSnapshot` and `Decision` follow,
    and for the same reason: a past analysis is a claim about what the model said against a
    SPECIFIC finished record, and it must stay exactly what it was even after the vendor is
    rescored next quarter.

    `gaps` and `recommendations` are stored as the JSON shapes `app/gap_analysis.py` defines
    (`{theme, what_we_observed, ...}` / `{priority, recommendation, ...}`) rather than typed
    further here — they are LLM output, disposable and regenerable, and belong nowhere near the
    hash-stamped `Finding` shape that IS the legal artefact.

    `limitations` is COPIED from P2's coverage statement at generation time, never generated by
    the model — see the module docstring on why a paraphrase is a softening.
    """

    id: str = Field(..., description="UUID of this analysis")
    vendor_ref: str
    provider: str = Field(..., description="which provider in the chain actually answered")
    model: str = Field(..., description="the model name the provider reported back")
    prompt_version: str
    context_hash: str = Field(..., description="sha256 of the exact context object the model saw")
    executive_summary: str
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    limitations: dict[str, Any] = Field(
        default_factory=dict, description="byte-identical copy of the coverage statement"
    )
    dropped_evidence_ids: int = Field(
        default=0, description="citations the model invented, dropped by the post-generation validator"
    )
    content_hash: str = Field(default="", description="sha256 of the canonical record")
    created_at: datetime = Field(default_factory=utcnow)


class GapAnalysisRecommendationEvent(BaseModel):
    """One event in an analyst's accept / edit / reject of ONE recommendation — append-only.

    WHY EVENTS, NOT A MUTABLE FLAG ON THE RECOMMENDATION. Same reasoning as `Dispute`: a rejected
    recommendation is not deleted, and an edited one keeps the model's original alongside the
    analyst's rewrite, because "the analyst agreed" and "the analyst rewrote it" are different
    facts about whether the feature is actually useful — see `acceptance rate` in
    `app/program_kpis.py`, which this log feeds.

    `rec_index` is the recommendation's position in the analysis's `recommendations[]` at
    generation time — the record is immutable, so the position is a stable key.
    """

    id: str = Field(..., description="UUID of THIS event")
    analysis_id: str = Field(..., description="the GapAnalysisRecord this recommendation came from")
    vendor_ref: str
    rec_index: int = Field(..., ge=0, description="position within recommendations[] on that analysis")
    event: GapAnalysisEventKind
    edited_text: str | None = Field(
        default=None, description="the analyst's rewrite — present only when event = 'edited'"
    )
    actor: str | None = Field(default=None, description="who recorded it — role or name, client-supplied")
    note: str | None = None
    content_hash: str = Field(default="", description="sha256 of the canonical event")
    created_at: datetime = Field(default_factory=utcnow)


class BenchmarkSnapshot(BaseModel):
    """Where a vendor stood among its peers AS AT one score run — the percentile trend's raw point.

    WHY STORE IT. The overall percentile is a read-time quantity: it is computed against whatever
    peers happen to be in the cohort right now. That makes it perfect for "how do I read today's
    number" and useless for "has this vendor been slipping" — because a percentile recomputed today
    would compare an old posture against today's cohort. A trend needs the percentile as it WAS,
    against the peers that existed THEN. So a light benchmark is computed at score time and its
    scalar result frozen here: "bottom quartile three quarters running" is the risk-manager signal a
    single point cannot give, and it is only honest if each point was frozen when it was true.

    NOT A SECOND SCORE. Like the profile and the decision, this is context beside the score, not an
    input to it — it holds no finding and moves no penalty. `available: false` (a thin or missing
    cohort) is a first-class, expected value, recorded rather than dropped.
    """

    id: str = Field(..., description="UUID of this snapshot")
    vendor_ref: str
    cohort_key: str | None = Field(default=None, description="the cohort compared against, as at then")
    level: str | None = Field(default=None, description="the widening rung actually used")
    available: bool = Field(default=False, description="False when the cohort was too thin to publish")
    percentile: int | None = None
    percentile_resolution: int | None = Field(default=None, description="the step the sample could express")
    quartile: int | None = None
    peer_n: int = Field(default=0, description="peers in the cohort at this run")
    posture: int | None = Field(default=None, description="the posture this percentile was for")
    content_hash: str = Field(default="", description="sha256 of the canonical snapshot")
    created_at: datetime = Field(default_factory=utcnow)


class CategoryScore(BaseModel):
    """One category's posture roll-up: 100 minus the penalties found in it (for the breakdown).

    `posture` is None when the category was not covered this run (no signals returned) — absent,
    not zero. `penalty` is the total severity penalty subtracted; `coverage` is how many of the
    category's planned signals returned data (the confidence axis, per category).
    """

    category: str
    posture: int | None = Field(default=None, ge=0, le=100)
    grade: str | None = None
    penalty: float = Field(default=0.0, ge=0.0)
    coverage: float = Field(..., ge=0.0, le=1.0)
    findings: int = Field(default=0, description="scored issues found in this category")
    contributing_finding_ids: list[str] = Field(default_factory=list)


class Score(BaseModel):
    """The published result — a penalty-based POSTURE score (100 = strongest). A bare number is
    unrepresentable: a confidence (coverage) axis rides with every score, or it is refused as a
    Ghost (methodology §5.7). Higher posture = better."""

    vendor_ref: str
    blocked: bool = False
    blocked_reason: str | None = Field(
        default=None, description="e.g. 'sanctions hit — adjudication required', 'entity ambiguous'"
    )
    posture: int | None = Field(
        default=None, ge=0, le=100, description="0-100 posture (100 best); None when blocked/refused"
    )
    grade: str | None = Field(default=None, description="A–F headline; None when blocked/refused")
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="coverage-derived assurance 0-1 (coverage first, optional maturity adjustment)",
    )
    confidence_band: str = Field(default="Low", description="High | Medium | Low")
    refused: bool = Field(default=False, description="coverage < refuse_below — a Ghost, no posture")
    ghost: bool = Field(default=False, description="low-confidence: looks clean only for lack of evidence")
    critical_ceiling_applied: bool = Field(
        default=False, description="a directly-observed current critical capped the posture (knockout)"
    )
    ceiling_cause: str | None = None
    # E7d. Two DIFFERENT ceilings, kept apart deliberately. The critical ceiling is a statement
    # about the VENDOR — we observed something disqualifying. This one is a statement about US —
    # we did not see enough to publish a number this high. Merging them would let a reader blame
    # the vendor for our coverage, and a vendor dispute the wrong thing.
    confidence_ceiling_applied: bool = Field(
        default=False,
        description="thin evidence capped the published posture (E7d) — about OUR coverage, not the vendor",
    )
    confidence_ceiling: float | None = Field(
        default=None, description="the cap this coverage level allows, whether or not it bound"
    )
    # E13, SIDE BY SIDE. The plan calls the bounded log-odds transform a second release because it
    # changes what the number MEANS — same evidence, different published figure — so it needs a
    # version bump, a notice period and both numbers visible at once. This field is what makes the
    # notice period possible: a client sees the preview beside the live posture for a release
    # before either moves.
    #
    # None wherever the vendor's exact cohort holds fewer than eight real peers, which is every
    # vendor until E11's pool is seeded — shrinking toward six invented postures is worse than not
    # shrinking. It fills in PER VENDOR as their cohort reaches depth, so this is not one switch for
    # the whole book. `log_odds_reason` says which precondition is unmet, or where L_peer came from.
    log_odds_preview: float | None = Field(
        default=None,
        description=(
            "E13 PREVIEW, not the published posture. Bounded log-odds: never floors, never "
            "saturates, so a vendor with three Criticals and one with fifteen still separate. "
            "None until this vendor's own cohort holds eight real peers."
        ),
    )
    log_odds_reason: str | None = Field(
        default=None,
        description=(
            "Why the E13 preview is unavailable — or, when it IS available, the cohort and median "
            "posture L_peer was taken from, because a shrunk number whose target is not stated is "
            "not reviewable"
        ),
    )
    categories: list[CategoryScore] = Field(default_factory=list)
    industry_profile: str | None = Field(
        default=None,
        description=(
            "DEPRECATED at E1, removal scheduled for the following release. Recorded which sector "
            "profile promoted a severity during scoring. That mechanism is gone — no vendor "
            "context reaches the arithmetic — so this is now ALWAYS None and a renderer must not "
            "show it. Retained only so Scores stored before E1 still deserialise. The sector "
            "obligation survives as a Compliance Gap finding; see "
            "the design notes."
        ),
    )
    recommendation: Recommendation | None = Field(
        default=None,
        description="Filled at SERVE time from the rule table; never stored, never generated.",
    )
    computed_at: datetime = Field(default_factory=utcnow)


# =============================================================================
# FINANCIAL & BUSINESS STABILITY MODELS (Phase 1.1)
# =============================================================================
# These models support the Business Stability axis — a separate score from
# cybersecurity posture, measuring financial health and longevity. Financial
# distress ≠ poor security, so these models are kept distinct from the security
# scoring models above.
# =============================================================================

InsolvencyStatus = Literal[
    "active",           # Insolvency proceedings currently active
    "resolved",         # Proceedings completed (e.g. discharged, dissolved)
    "historical",       # Past insolvency, now closed
    "none",             # No insolvency record found
    "unknown",          # Unable to determine
]

CompanyStatus = Literal[
    "active",
    "dissolved",
    "liquidation",
    "receivership",
    "administration",
    "voluntary_arrangement",
    "insolvency_proceedings",
    "converted_closed",
    "registered",
    "removed",
    "closed",
    "unknown",
]


class InsolvencyRecord(BaseModel):
    """One insolvency proceeding against a vendor.

    Insolvency is a GATE signal: active proceedings BLOCK scoring (the vendor
    cannot be assessed while in administration/liquidation). Historical records
    are scored as financial distress signals but do not block.
    """

    proceeding_type: str = Field(
        ...,
        description="Type of proceeding: liquidation, administration, receivership, etc."
    )
    status: InsolvencyStatus = Field(
        ...,
        description="Current status of the proceeding"
    )
    date: datetime | None = Field(
        default=None,
        description="Date the proceeding was opened or filed"
    )
    jurisdiction: str | None = Field(
        default=None,
        description="Country/court jurisdiction where proceeding was filed"
    )
    case_number: str | None = Field(
        default=None,
        description="Official case/reference number from the court or registry"
    )
    court: str | None = Field(
        default=None,
        description="Court or tribunal handling the proceeding"
    )
    practitioner: str | None = Field(
        default=None,
        description="Name of insolvency practitioner or administrator"
    )
    notes: str | None = Field(
        default=None,
        description="Additional context from the source"
    )
    source: str = Field(
        ...,
        description="Collector id that produced this record"
    )
    locator: str | None = Field(
        default=None,
        description="URL or record id in the source system"
    )
    fetched_at: datetime = Field(
        default_factory=utcnow,
        description="When we retrieved this record"
    )


class FinancialMetrics(BaseModel):
    """Time-series financial metrics for a vendor.

    These are structured financial data points (revenue, debt, etc.) that can
    be trended over time. Each metric carries a reporting period and currency
    where applicable.
    """

    period_end: datetime = Field(
        ...,
        description="End date of the reporting period (fiscal quarter/year)"
    )
    period_type: Literal["quarterly", "annual", "trailing_twelve_months"] = Field(
        ...,
        description="Type of reporting period"
    )
    revenue: float | None = Field(
        default=None,
        description="Total revenue in native currency"
    )
    revenue_currency: str | None = Field(
        default=None,
        description="ISO-4217 currency code (USD, GBP, EUR, etc.)"
    )
    net_income: float | None = Field(
        default=None,
        description="Net income/profit in native currency"
    )
    total_assets: float | None = Field(
        default=None,
        description="Total assets in native currency"
    )
    total_liabilities: float | None = Field(
        default=None,
        description="Total liabilities in native currency"
    )
    long_term_debt: float | None = Field(
        default=None,
        description="Long-term debt in native currency"
    )
    cash_and_equivalents: float | None = Field(
        default=None,
        description="Cash and cash equivalents in native currency"
    )
    equity: float | None = Field(
        default=None,
        description="Shareholders' equity in native currency"
    )
    source: str = Field(
        ...,
        description="Collector id that produced this metric"
    )
    source_version: str | None = Field(
        default=None,
        description="Version/date of the source data (e.g. SEC filing accession number)"
    )
    locator: str | None = Field(
        default=None,
        description="URL or filing reference"
    )
    fetched_at: datetime = Field(
        default_factory=utcnow,
        description="When we retrieved this metric"
    )


class FinancialProfile(BaseModel):
    """The financial and business stability profile of a vendor.

    This is CONTEXT for the Business Stability score, similar to how
    VendorProfile provides context for cybersecurity benchmarking. It
    contains the raw financial observations; the scoring logic in
    business_stability.py converts these to a 0-100 score.

    THE RULE THIS TYPE EXISTS TO HOLD: financial data must never directly
    affect the cybersecurity posture score. Business stability is a separate
    axis for a reason — a bankrupt company can have excellent security, and
    a secure startup can run out of cash.
    """

    vendor_ref: str
    # Basic company information from registries
    incorporation_date: ProfileField | None = Field(
        default=None,
        description="Date the company was legally incorporated"
    )
    company_status: ProfileField | None = Field(
        default=None,
        description="Current legal status from the registry (active, dissolved, etc.)"
    )
    registry_number: ProfileField | None = Field(
        default=None,
        description="Company registration number from the official registry"
    )
    registry_jurisdiction: ProfileField | None = Field(
        default=None,
        description="Jurisdiction of incorporation (country/state/province)"
    )

    # Insolvency information
    insolvency_status: ProfileField | None = Field(
        default=None,
        description="Current insolvency status (none, active, historical)"
    )
    insolvency_records: list[InsolvencyRecord] = Field(
        default_factory=list,
        description="All insolvency proceedings found for this vendor"
    )

    # Financial metrics ( time-series from filings)
    financial_metrics: list[FinancialMetrics] = Field(
        default_factory=list,
        description="Financial metrics over time (most recent first)"
    )

    # Derived fields (computed from the above, not stored)
    operating_years: float | None = Field(
        default=None,
        description="Years since incorporation (computed from incorporation_date or fallback sources)"
    )
    # Fallback age sources when entity registers are unavailable (free alternatives)
    wikidata_years: float | None = Field(
        default=None,
        description="Years since legal inception from Wikidata (P571) - free fallback source"
    )
    rdap_years: float | None = Field(
        default=None,
        description="Years since domain registration from RDAP - free fallback source (discounted)"
    )
    age_band: Literal["startup", "young", "established", "mature", "veteran", "unknown"] | None = Field(
        default=None,
        description="Age band for scoring: startup (<2yr), young (2-5yr), established (5-10yr), mature (10-20yr), veteran (20+yr)"
    )

    # Computed financial ratios (for scoring logic)
    debt_to_equity: float | None = Field(
        default=None,
        description="Most recent debt-to-equity ratio (computed from financial_metrics)"
    )
    revenue_trend: Literal["growing", "stable", "declining", "unknown"] | None = Field(
        default=None,
        description="Revenue trend over available periods (computed from financial_metrics)"
    )
    cash_flow_trend: Literal["positive", "negative", "unknown"] | None = Field(
        default=None,
        description="Cash flow trend (computed from financial_metrics)"
    )

    # Gate status (whether this vendor should be BLOCKED from scoring)
    insolvency_gate: bool = Field(
        default=False,
        description="True if active insolvency proceedings should BLOCK assessment"
    )
    insolvency_gate_reason: str | None = Field(
        default=None,
        description="Why the gate was triggered (e.g. 'active administration proceeding')"
    )
    
    # Going-concern flag (critical financial distress signal)
    going_concern_flagged: bool = Field(
        default=False,
        description="True if SEC EDGAR going-concern language detected in company's own filings"
    )
    going_concern_detected: bool = Field(
        default=False,
        description="True if going-concern penalty was applied in Business Stability scoring"
    )

    computed_at: datetime = Field(default_factory=utcnow)
