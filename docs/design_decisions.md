# Design Decisions of Record

Three subsystems whose design was settled before implementation, recorded here so the reasoning
survives the people who made it. Each part states what was chosen, what was rejected, and why.

| Part | Subsystem |
|---|---|
| **1 · Peer benchmarking** | Cohort scoping, placement thresholds, the refusal-to-compare gate |
| **2 · Financial data integration** | Collector chains, API surface, schema, and the Business Stability axis |
| **3 · Vendor comparison scenarios** | Nine acceptance scenarios in plain English, executable as a test file |

*The model itself is [`scoring_model.md`](scoring_model.md) Part 1; the research behind it is
[`methodology.md`](methodology.md) Part 1.*

## Part 1 · Peer benchmarking

*This layer answers one question — is this supplier's posture normal, good or poor versus similar suppliers? It is **not** a scoring engine: if every line of it were deleted, every published score would be byte-identical. That property is asserted by test, not promised in prose.*

**Status:** locked 2026-07-30 · **Supersedes:** the cohort machinery in [benchmark.py](../backend/app/benchmark.py)
**Implements:** `backend/app/benchmarking/` · **Config:** `benchmarks.yaml` → `benchmarking:`

> This layer answers exactly one customer question: **"is this supplier's risk posture normal, good,
> or poor compared to similar suppliers?"**
>
> It is **not** a scoring engine. It reads posture, confidence and domain scores that already exist,
> and contextualises them. **If every line of this module were deleted, every published score would
> be byte-identical.** That property is asserted by test, not promised in prose.

---

### The five decisions

Locked before implementation, because each one changes the database schema or the published output.

| # | Decision | Chosen | Rejected alternative |
|--:|---|---|---|
| **1** | Cohort scoping | **Vendor-only cohorts.** Dimensions are `sector`, `size_band`, `delivery_model`. `data_access_scope` is an **interpretation filter**, never a cohort dimension | Relationship-scoped cohorts including `data_access_scope` — fragments the pool ~4×, makes cohorts tenant-dependent, re-opens cross-tenant pooling |
| **2** | Cold start | **Labelled external base rates as a reference line**, plus honest `Insufficient peer data (n=4)`. A reference line is a *population statistic*, never a peer median | Blank cards; or synthetic peers dressed as a cohort |
| **3** | Synthetic reference points | **Hard gate.** `is_synthetic = true` forbids *any* percentile or quartile at *any* n. Reference line + prose only | Label-only — thirty invented numbers still yield a screenshottable fake percentile |
| **4** | Member disclosure | **Aggregates only externally. Member refs stored internally**, for dispute and audit | Full member list to the supplier (cross-tenant confidentiality); or storing nothing (kills dispute) |
| **5** | Pool size assumption | **Hundreds in year one.** Design for quartile + rank-of-n first; percentiles switch on automatically at n≥30 | Assuming thousands and shipping a percentile-first UI that shows "insufficient data" everywhere |

#### Decision 1, in full — why `data_access_scope` is not a cohort dimension

`sector`, `size_band` and `delivery_model` are properties **of the supplier**. `data_access_scope` is
a property **of the relationship** — it is what *this buyer* exposed to them, the same quantity
`criticality` already carries.

Putting it in the cohort key would mean the same supplier belongs to different cohorts for different
buyers. Three consequences, all bad: it breaks "exactly one cohort per supplier"; it fragments the
peer pool per tenant precisely where n≥30 is needed; and it silently re-introduces cross-tenant
pooling, which prior design review recorded as *"a contractual question before an
engineering one."*

So scope routes to **interpretation**: it selects the procurement action template and it filters the
buyer's own book. It never selects the peers. This preserves the layering the platform already
insists on — **inherent risk (buyer-side) interprets the comparison; it never defines it.**

#### Decision 4, in full — the member-ref visibility rule

| Audience | May see |
|---|---|
| Internal (platform operator, auditor, dispute reviewer) | **Full member refs** of any snapshot |
| The assessed supplier, on dispute | **The cohort definition and n**, and the aggregate distribution. **Not** the member list |
| The buyer (tenant) | **Aggregates only** — n, `data_sources` composition, distribution, per-domain n |
| Any export (CSV/JSON) | **Aggregates only.** Member refs are never serialised into an export path |

Rationale: a dispute needs *"who was I compared against?"* to be **answerable by a human reviewer**,
which requires storage. It does not require **publication**, and publishing one tenant's supplier
list to another tenant's supplier is a confidentiality breach dressed as transparency. The API
therefore has two shapes for a snapshot, and the member-bearing one is not reachable from a
tenant-scoped route.

---

### Cohort assignment

#### Dimensions

| Dimension | Values | Source |
|---|---|---|
| `sector` | string, normalised | supplier record |
| `size_band` | `micro` · `small` · `mid` · `large` · `enterprise` | **derived** — see below |
| `delivery_model` | `saas` · `on_prem` · `managed` | supplier record |

`data_access_scope` (`low`/`medium`/`high`/`critical`) is carried on the placement for
interpretation, and is **absent from every cohort key**.

#### `size_band` is derived, versioned and disputable

The superseded model kept revenue and headcount as **separate** cohort dimensions, and
[models.py:310-315](../backend/app/models.py#L310-L315) argues why: *"a 40-person firm turning over
$400M is a different risk proposition from a 4,000-person firm turning over the same amount."* That
is true, and it costs 5× the cohort cells — which is unaffordable when the threshold is n≥30.

Resolution: collapse to one band **for cohorting only**, by a published rule, and keep both raw
inputs on the record so the derivation is what a supplier disputes.

```
size_band = max(band(headcount), band(revenue_aud))     # rule v1, `resolve: max`
```

`max` rather than headcount-primary because leverage (revenue) and attack surface (headcount) each
independently raise what a competent operator is expected to run. The result carries
`size_band_basis` naming which input determined it and whether the two disagreed. **Neither input
known → no `size_band`**, and the supplier falls to a sector rung rather than being guessed into a
band.

#### The ladder — deepen, then widen, then refuse

```
  ── deepen while density allows ──────────────────────────────
  D2   sector + size_band + delivery_model      most specific
  D1   sector + size_band                       ← FLOOR
  ── widen only below the floor ───────────────────────────────
  W1   sector
  W2   sector_group                             published rollup
  ── ────────────────────────────────────────────────────────── ──
       REFUSE: "Insufficient peer data (n=<actual>)"
```

Evaluate **most specific first**; assign the first rung reaching `min_quartile_n`. Below the floor,
keep widening. Below `sector_group`, assign the widest rung attempted and publish **no placement**.

Three rules this encodes:

1. **Never widen to the global "all suppliers" set.** Comparing a bank against every supplier ever
   assessed is the meaningless comparison the whole feature exists to refuse — the same floor
   [benchmark.py:23-26](../backend/app/benchmark.py#L23-L26) already defends.
2. **Deterministic.** Fixed precedence, so two rungs of equal `n` never flip between rebuilds.
3. **Every rung tried is recorded with its `n`.** That list *is* the assignment rationale —
   *"wanted sector+size+delivery (n=6), assigned sector+size (n=34)"*.

Assignment and placement are **separate**: every supplier gets exactly one cohort assignment, even
when the cohort is too thin to place them in.

---

### Placement thresholds — the hard rules

| Condition | Published |
|---|---|
| `is_synthetic` | **Reference line + prose only.** No percentile. No quartile. At any `n` |
| `n < 8` | `"Insufficient peer data"` + the actual `n`. No quartile, no percentile |
| `8 ≤ n < 30` | **Quartile + rank-of-n** + direction vs median. **No percentile** |
| `n ≥ 30` | Percentile (with resolution band) + quartile + rank-of-n + direction vs median |

`n` is **always** published alongside any output, and `n` counts **peers, excluding the subject** —
otherwise "n=30" is 29 peers and the boundary rule is wrong by one.

#### Estimator choices, and why

| Choice | Decision | Reason |
|---|---|---|
| Ties | **Midrank**: `100·(below + 0.5·equal)/n` | *At-or-below* pushes a supplier tied with ten others at the median **above** the 50th percentile. Postures are integers 0–100; at n=40 collisions are certain |
| Rank | **`rank_of_n` is required, not optional** | *"17th of 34"* needs no estimator choice, cannot overstate precision, and survives one peer joining. At n=8–29 it is strictly more informative than a quartile letter |
| Percentile precision | Snapped to the achievable step, **step published** | At n=8 the step is 12.5, so an "83rd percentile" claims precision the sample cannot express |
| Median | **Nearest-rank, no interpolation** | *"An interpolated median between two real vendors is a company that does not exist"* |
| Outliers | **IQR fence (p25 − 1.5·IQR)**, never standard deviations | SD assumes normality and is destabilised by one extreme member — and at n=8–20 one member *is* a large share of the population |
| Quartile labelling | `quartile: 1..4` **plus** `quartile_label` **plus** `quartile_direction` | Q1 means "best" in finance and "worst" elsewhere. A bare `Q1` is a footgun. `1 = lowest posture`, stated in the payload |

#### Per-domain `n` is not cohort `n`

A cohort of 40 may hold only 12 suppliers with an `email_auth` score. **Every domain row carries its
own `n` and its own resolution label, and the thresholds apply per domain independently.** One card
will legitimately show *overall: 62nd percentile (n=41)* beside *email_auth: bottom quartile (n=13)*
beside *breach_history: insufficient peer data (n=5)*. That reads as an inconsistency unless every
row is labelled — which is also why there is **no composite benchmark score**.

A peer never assessed for a domain is **not** a peer that failed it. It leaves that domain's
denominator.

---

### Two confidences, never merged

| Field | Meaning | Origin |
|---|---|---|
| `supplier_confidence` | Coverage of *this supplier's* observable data | **Input, passed through unchanged** |
| `placement_reliability` | How much weight the *comparison* deserves | Derived from `n`, rung reached, peer confidence composition, freshness — **itemised, not opaque** |

`supplier_confidence < 0.6` → placement is **flagged unreliable and still published**. Labelled,
never suppressed.

**Disclose peer confidence; do not filter on it.** Excluding thinly-evidenced peers biases the
cohort toward the observable, i.e. toward large companies — which is the observability bias the
platform exists to remove. So the cohort publishes its confidence composition and keeps its members.

And per the spec's own rule: **cohort quality is not inferable from cohort size.** `data_sources` is
therefore a **composition with counts** — `{osint_only: 12, osint_plus_questionnaire: 8, attested: 3}` —
not a list of strings. *"n=23, of which 3 attested"* is a different claim from *"n=23"*.

---

### Snapshots — reproducibility, and the feature that falls out of it

Every placement stores the cohort snapshot it was computed from. Snapshots are **append-only**;
a rebuild mints a new one; nothing is ever mutated.

Snapshot contents: `cohort_key` · content hash of sorted member refs · `n` · distribution
(median, p25, p75, min, max) · per-domain medians and per-domain `n` · `data_sources` composition ·
`is_synthetic` · `non_discriminating` · `last_refreshed` · rung reached + rationale.

**The feature:** *"why did my quartile change?"* becomes mechanically answerable. Diff two snapshots
and it is either **your posture moved** or **the cohort moved**. So the delta is promoted to a
first-class output rather than left as an implementation detail:

```
placement_delta:
  posture_change:        +3
  cohort_median_change:  +7
  net_effect:            "-1 quartile — the cohort improved faster than you did"
```

Nobody in this market answers that question today.

**Cohorts are rebuildable from raw data; the tables are a materialisation, not a source of truth.**
Which is exactly why an upheld dispute cannot be a database edit — see below.

---

### Dispute — inputs only, and notated while open

Extends the existing append-only dispute machinery
([storage.py:65-68](../backend/app/storage.py#L65-L68)) with a **target discriminator**, rather than
building a parallel system.

- **Disputable:** the *inputs* — `sector`, `size_band` (and its two raw values), `delivery_model`.
- **Not disputable:** the cohort, the snapshot, or the resulting cell. Same discipline the platform
  already applies to Residual Risk: *a vendor disputes its Posture or its Tier, never the cell.*
- **States:** `submitted` → `under_review` → `upheld` / `partially_upheld` / `rejected`, each an
  appended event carrying actor, evidence and timestamp.
- **Effect of upheld:** the attribute changes → rebuild → new snapshot → new placement. **Historical
  placements are never rewritten** — that is the whole point of storing the snapshot.
- **While a dispute is open, the placement is notated `disputed`.** This is not optional politeness:
  the governing research recorded the US Chamber / FCRA principle that *"disputed ratings must be
  notated as such until resolved."* Silence during review is the exposure.

---

### The discrimination test

Automates, per cohort, the analysis prior design review ran by hand — which found
six signals penalising **100%** of the corpus and twelve constant-pass, i.e. *"19 of 27 signals
contribute nothing to ordering."*

| Data shape | Statistic | Non-discriminating when |
|---|---|---|
| Continuous domain score | IQR + coefficient of variation | `IQR == 0` or `CV < 0.02` |
| Categorical signal band | **Modal-band share** (variance is undefined for strings) | modal share `≥ 0.95` |

Two rules that are easy to get wrong:

1. **Flag both directions.** 100%-fail and 100%-pass are equally useless for ranking. It is the same
   test, and a flat tax is not a comparison.
2. **Per cohort, not global.** DMARC may be non-discriminating among enterprise financials and
   highly discriminating among small manufacturers. Compute per cohort; aggregate separately for the
   model team.

Where the flag lands: stored on the snapshot; **suppressed from the "you are behind your peers"
list** (that line would tell the reader nothing); **shown in a labelled "no peer discrimination in
this cohort" section**; and exposed for the model team. Logged and labelled — never silently
included, never silently dropped.

---

### Narrative — versioned templates that refuse to render

Same discipline `scoring.yaml` already enforces, where the loader **refuses to start** if a
penalising band has no plain-English reason.

- Templates live in config, are versioned, and each declares the placement fields it consumes.
- A template whose required field is absent **refuses to render** — so a missing `n` can never
  produce a confident sentence.
- Procurement's `Recommend: [action]` is a deterministic lookup on
  `(placement × data_access_scope)` — a table, not a model — and is marked **"suggested, not
  advice."**
- The **self-selection caveat is permanent** and appears on every rendering, including the ones that
  publish no placement.

---

### What is not built

| Not building | Why |
|---|---|
| A composite "benchmark score" blending domains | Per-domain comparison only. A blend hides the one domain a given buyer cares about |
| Firmographic multipliers on posture | Firmographics determine **cohort membership only**. The module cannot write to a score |
| ML anomaly detection | No outcome labels exist anywhere in the platform |
| Differential privacy / homomorphic encryption / SMPC | Premature at hundreds of suppliers. Fix the pool first |
| Tableau / BI integration | Flat REST + CSV export |
| Inferring cohort quality from `n` alone | `data_sources` composition travels with every `n` |
| Widening past `sector_group` | A peer group spanning all industries is not a peer group |

---

### Migration from `benchmark.py`

The superseded module stays in the tree for one release so stored `BenchmarkSnapshot` rows keep
deserialising, and is marked deprecated. Two pieces of it are **deleted outright** rather than
carried:

| Deleted | Why |
|---|---|
| `_synthetic_baseline_peers` — six hard-coded postures `[65,72,78,83,89,94]` published as `n=6` ([benchmark.py:369](../backend/app/benchmark.py#L369)) | A reader sees `n=6` and thinks six real companies. Decision 3 forbids it |
| The `cohort is None → technology / medium / other` fallback ([benchmark.py:414-421](../backend/app/benchmark.py#L414-L421)) | Inventing a cohort to avoid a blank card is the exact defect these rules exist to kill |

Carried over unchanged, because they were already right: nearest-rank percentile with no
interpolation · resolution disclosure · the IQR outlier fence · checked-vs-failed prevalence
discipline · per-category independent `n` · the caveat machinery · load-time config validation that
fails at startup rather than at serve time · and the `PeerLookup` callable seam, which keeps
persistence out of the statistics and makes every rung testable without a database.

---

## Part 2 · Financial data integration

*Integration points for the financial collectors: collector mapping, priority chains, API endpoints and schema. Scoring mechanics live in [`scoring_model.md`](scoring_model.md) Part 1; this is the wiring.*

### Overview
This document defines the integration points for financial data collectors into the existing TPRM pipeline, including collector mapping, priority chains, API endpoints, and database schema considerations.

### Collector Mapping: Domain → Registry Number

#### Existing Collectors for Entity Resolution
The following existing collectors already provide registry numbers that financial collectors can leverage:

| Existing Collector | Provides | Target Financial Collectors |
|-------------------|----------|----------------------------|
| `gleif_collector` | LEI, registration numbers | OpenCorporates, SEC EDGAR |
| `abn_collector` | Australian Business Number (ABN) | ASIC insolvency |
| `companies_house_collector` | UK company number | Companies House insolvency |
| `wikidata_collector` | Various registry IDs | Regional registries |

#### New Financial Collectors and Their Inputs

| Collector | Primary Input | Fallback Input | Priority |
|-----------|--------------|----------------|----------|
| `companies_house_collector` | UK company number | Company name + domain | 1 (UK) |
| `sec_edgar_collector` | CIK (from LEI or ticker) | Company name + domain | 1 (US public) |
| `open_corporates_collector` | Company name + domain | LEI | 2 (global) |
| `registry_lookup_collector` | Company name + domain | Registry number | 3 (global backup) |
| `eu_insolvency_collector` | Company name + jurisdiction | Registry number | 1 (EU) |
| `german_insolvency_collector` | Company name + HRB | Registry number | 1 (Germany) |
| `canada_bankruptcy_collector` | Company name | Business number | 1 (Canada) |
| `asic_insolvency_collector` | ACN/ABN | Company name | 1 (Australia) |

### Collector Priority and Fallback Chain

#### Primary Strategy: Jurisdiction-Based Routing
1. Determine vendor jurisdiction from existing `VendorProfile.country`
2. Route to primary collector for that jurisdiction
3. If primary fails, fall back to global collectors
4. If all fail, return `empty` (lowers confidence, never posture)

#### Fallback Chain by Jurisdiction

##### United Kingdom
1. `companies_house_collector` (authoritative UK registry)
2. `open_corporates_collector` (global aggregator)
3. `registry_lookup_collector` (backup global)

##### United States (Public Companies)
1. `sec_edgar_collector` (SEC EDGAR - authoritative for public companies)
2. `open_corporates_collector` (for private company data)
3. `registry_lookup_collector` (backup)

##### European Union
1. `eu_insolvency_collector` (official EU insolvency register)
2. National registry collector (if available for specific country)
3. `open_corporates_collector` (global aggregator)

##### Germany
1. `german_insolvency_collector` (official German insolvency register)
2. `open_corporates_collector` (global aggregator)

##### Canada
1. `canada_bankruptcy_collector` (OSB official bankruptcy records)
2. `open_corporates_collector` (global aggregator)

##### Australia
1. `asic_insolvency_collector` (ASIC official records)
2. `open_corporates_collector` (global aggregator)

##### Global/Unknown Jurisdiction
1. `open_corporates_collector` (primary global source)
2. `registry_lookup_collector` (backup global)

#### Collector Configuration
Add to `config.py`:

```python
# Financial collector configuration
financial_collector_priority: dict[str, list[str]] = {
    "uk": ["companies_house", "open_corporates", "registry_lookup"],
    "us": ["sec_edgar", "open_corporates", "registry_lookup"],
    "eu": ["eu_insolvency", "open_corporates", "registry_lookup"],
    "de": ["german_insolvency", "open_corporates", "registry_lookup"],
    "ca": ["canada_bankruptcy", "open_corporates", "registry_lookup"],
    "au": ["asic_insolvency", "open_corporates", "registry_lookup"],
    "global": ["open_corporates", "registry_lookup"],
}
```

### API Endpoints Design

#### New Endpoints

##### GET /api/vendors/{ref}/financial
Retrieve the financial profile for a vendor.

**Response Schema:**
```json
{
  "vendor_ref": "atlassian",
  "incorporation_date": {
    "value": "2002-06-27",
    "source": "open_corporates",
    "locator": "https://opencorporates.com/companies/au/...",
    "fetched_at": "2026-08-05T14:00:00Z",
    "as_of": "2002-06-27"
  },
  "company_status": {
    "value": "active",
    "source": "companies_house",
    "locator": "https://find-and-update.company-information.service.gov.uk/company/...",
    "fetched_at": "2026-08-05T14:00:00Z"
  },
  "registry_number": {
    "value": "123456789",
    "source": "companies_house",
    "locator": "https://find-and-update.company-information.service.gov.uk/company/123456789",
    "fetched_at": "2026-08-05T14:00:00Z"
  },
  "insolvency_status": {
    "value": "none",
    "source": "companies_house",
    "fetched_at": "2026-08-05T14:00:00Z"
  },
  "insolvency_records": [],
  "financial_metrics": [
    {
      "period_end": "2024-06-30",
      "period_type": "annual",
      "revenue": 4000000000,
      "revenue_currency": "USD",
      "net_income": 800000000,
      "total_assets": 10000000000,
      "total_liabilities": 3000000000,
      "long_term_debt": 1000000000,
      "cash_and_equivalents": 2000000000,
      "equity": 7000000000,
      "source": "sec_edgar",
      "source_version": "0001193125-24-123456",
      "locator": "https://www.sec.gov/Archives/edgar/data/...",
      "fetched_at": "2026-08-05T14:00:00Z"
    }
  ],
  "operating_years": 24.1,
  "age_band": "veteran",
  "debt_to_equity": 0.14,
  "revenue_trend": "growing",
  "cash_flow_trend": "positive",
  "insolvency_gate": false,
  "insolvency_gate_reason": null,
  "computed_at": "2026-08-05T14:00:00Z"
}
```

##### GET /api/vendors/{ref}/stability
Retrieve the Business Stability score for a vendor.

**Response Schema:**
```json
{
  "vendor_ref": "atlassian",
  "score": 95,
  "base_score": 100,
  "age_band": "veteran",
  "penalties": {},
  "bonuses": {
    "survivorship": 10.0
  },
  "gate_triggered": false,
  "gate_reason": null,
  "confidence_adjusted": 0.95,
  "contingency_plan_required": false,
  "computed_at": "2026-08-05T14:00:00Z"
}
```

**Gate Response (if insolvency active):**
```json
{
  "vendor_ref": "blocked-vendor",
  "score": null,
  "base_score": null,
  "age_band": "mature",
  "penalties": {},
  "bonuses": {},
  "gate_triggered": true,
  "gate_reason": "Active insolvency proceeding: liquidation (CASE-12345) in United Kingdom",
  "confidence_adjusted": null,
  "contingency_plan_required": true,
  "computed_at": "2026-08-05T14:00:00Z"
}
```

#### Extended Existing Endpoints

##### GET /api/vendors/{ref}
Add `business_stability` field to existing vendor response:

```json
{
  "vendor_ref": "atlassian",
  "name": "Atlassian",
  "domain": "atlassian.com",
  "score": {
    "posture": 88,
    "grade": "A",
    "overall_confidence": 0.92,
    "confidence_band": "High",
    "blocked": false,
    "refused": false
  },
  "business_stability": {
    "score": 95,
    "age_band": "veteran",
    "gate_triggered": false,
    "confidence_adjusted": 0.95
  },
  // ... existing fields
}
```

### Database Schema Changes

#### New Tables

##### financial_profiles
Stores the financial profile for each vendor (similar to vendor_profiles).

```sql
CREATE TABLE financial_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_ref VARCHAR(255) NOT NULL,
    incorporation_date JSONB,
    company_status JSONB,
    registry_number JSONB,
    registry_jurisdiction JSONB,
    insolvency_status JSONB,
    insolvency_records JSONB,
    financial_metrics JSONB,
    operating_years FLOAT,
    age_band VARCHAR(50),
    debt_to_equity FLOAT,
    revenue_trend VARCHAR(50),
    cash_flow_trend VARCHAR(50),
    insolvency_gate BOOLEAN DEFAULT FALSE,
    insolvency_gate_reason TEXT,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (vendor_ref)
);

CREATE INDEX idx_financial_profiles_vendor_ref ON financial_profiles(vendor_ref);
CREATE INDEX idx_financial_profiles_computed_at ON financial_profiles(computed_at DESC);
```

##### business_stability_scores
Stores the Business Stability score history (similar to scores table).

```sql
CREATE TABLE business_stability_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_ref VARCHAR(255) NOT NULL,
    score INTEGER,
    base_score INTEGER,
    age_band VARCHAR(50),
    penalties JSONB,
    bonuses JSONB,
    gate_triggered BOOLEAN DEFAULT FALSE,
    gate_reason TEXT,
    confidence_adjusted FLOAT,
    contingency_plan_required BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_business_stability_scores_vendor_ref ON business_stability_scores(vendor_ref);
CREATE INDEX idx_business_stability_scores_computed_at ON business_stability_scores(computed_at DESC);
```

#### No Changes to Existing Tables
The existing tables (scores, vendor_profiles, evidence, findings) remain unchanged to maintain backward compatibility. Business Stability is a separate axis that does not modify the cybersecurity scoring data.

### Pipeline Integration

#### Pipeline Order Extension
Add financial collection phase after existing collectors but before scoring:

```
entity-resolution → collect (existing + financial) → EVIDENCE STORE
→ normalize → score (cybersecurity) → business_stability_score
→ persist Score → persist BusinessStabilityScore
```

#### Progress Events
Add SSE progress events for financial collectors:

```python
await _emit(progress, "financial_collecting", {
    "total": len(financial_collectors),
    "sources": [c.source for c in financial_collectors]
})

await _emit(progress, "financial_collector_done", {
    "source": result.source,
    "status": result.status,
    "evidence_id": evidence.id,
})

await _emit(progress, "business_stability_scoring", {})

await _emit(progress, "business_stability_done", {
    "score": result.score,
    "gate_triggered": result.gate_triggered,
})
```

### Error Handling

#### Collector Failure Strategy
- Individual collector failure: Log warning, continue to next in fallback chain
- All collectors in chain fail: Return `empty` status, lower confidence
- Gate triggered: Return early with gate status, do not compute score

#### Data Quality Validation
- Validate required fields (e.g., incorporation_date must be valid date)
- Handle missing data gracefully (set to None, don't fail)
- Validate financial metrics (e.g., revenue must be positive number)
- Log data quality issues for monitoring

### Rate Limiting

#### Per-Collector Rate Limits
Add to `config.py`:

```python
# Financial collector rate limits (requests per minute)
financial_rate_limits: dict[str, int] = {
    "companies_house": 600,  # Companies House API limit
    "sec_edgar": 10,  # SEC EDGAR fair access rule
    "open_corporates": 300,  # OpenCorporates free tier
    "registry_lookup": 60,  # Registry Lookup free tier
    "eu_insolvency": 60,  # EU e-Justice Portal
    "german_insolvency": 60,  # German insolvency register
    "canada_bankruptcy": 30,  # OSB search limit
    "asic_insolvency": 60,  # ASIC registry
}
```

#### Global Rate Limiting
Use existing `RateLimiter` class with per-collector limits.

### Monitoring

#### Collector Success Metrics
Track per-collector success rates and latency:

```python
financial_collector_metrics = {
    "companies_house": {"success_rate": 0.95, "avg_latency_ms": 250},
    "sec_edgar": {"success_rate": 0.98, "avg_latency_ms": 500},
    # ...
}
```

#### Gate Trigger Monitoring
Alert on gate triggers (active insolvency):

```python
if gate_triggered:
    log.warning("Insolvency gate triggered for %s: %s", vendor_ref, gate_reason)
    # Send alert to procurement team
```

### Backward Compatibility

#### Existing API Behavior
- Existing endpoints unchanged by default
- Business Stability data only added when explicitly requested via new endpoints
- Cybersecurity scoring logic completely unaffected
- Existing tests continue to pass without modification

#### Feature Flag
Add feature flag to enable/disable Business Stability:

```python
business_stability_enabled: bool = True
```

When disabled, financial collectors are skipped and Business Stability endpoints return 503.

---

### Implementation record (v5.3.0 — shipped)

This design was implemented as specified above. What follows is the as-built detail this design
doc doesn't otherwise cover — scoring mechanics are documented in
[`methodology.md`](methodology.md) Part 1 §5.2.1 and [`scoring_model.md`](scoring_model.md) Part 1 §6.1; this is
the wiring.

**Scoring/longevity logic:** `app/business_stability.py` (`compute_business_stability`),
`app/longevity.py` (`age_band_from_years`, `base_age_score`, `confidence_adjustment`,
`survivorship_bonus`, `contingency_plan_required`).

**Frontend:**
- `BusinessStabilityCard.jsx` — financial health score, gate status, age band, metrics, contingency flags, registry facts
- `BusinessStabilityPair` (in `primitives.jsx`) — Business Stability as a second axis alongside posture, same confidence-pairing rule
- `FinancialDetailModal.jsx` — drill-down tabs: Overview, Trends, Ratios, Insolvency

**Tests:**
- `test_business_stability.py` — age bands, base/confidence/bonus scoring, gate logic, penalties
- `test_financial_integration.py` — collector fallback chains, SSE streaming, API structure, missing-key/timeout handling, rate limits
- `test_regression_cybersecurity.py` — confirms cybersecurity scoring and collector separation are unaffected
- `tests/fixtures/financial_validation_corpus.py` — five fixtures (active insolvency block, 2-year startup, 40-year veteran, declining mature company, historical insolvency)

**Deployment:** no schema changes beyond §"Database Schema Changes" above; findings land in the
existing evidence store under category `business_financial_stability`. Required env vars:
`OPENCORPORATES_KEY`, `REGISTRY_LOOKUP_KEY`, `CANADA_BANKRUPTCY_KEY` (see `backend/.env.example`).

---

## Part 3 · Vendor comparison scenarios

*The plain-English version of the acceptance criteria encoded in [`backend/tests/test_vendor_comparison_scenarios.py`](../backend/tests/test_vendor_comparison_scenarios.py). Read this for *what the model should do*; read the test file to see *that it does*.*

**Status:** Implemented — phase 2 of the stakeholder feedback response (financial data integration, scoring-model test coverage, scorecard UX)
**Executable as:** [`backend/tests/test_vendor_comparison_scenarios.py`](../backend/tests/test_vendor_comparison_scenarios.py) — 9 numbered scenarios, 11 test functions, all passing against the real `scoring.yaml`

This is the plain-English version of the acceptance criteria the test file encodes. Each scenario compares two synthetic vendors that differ in exactly one respect, states what the platform must show, and explains why. Read this to review *what the model should do*; read the test file to see *that it does*.

Two scenarios deliberately depart from a literal reading of the original request, for reasons explained inline — the platform can only be tested against signals it actually scores.

---

### Scenario 1 — Severe breach history vs. no known breach

**Setup:** Two otherwise-identical, fully-evidenced vendors. Vendor A has a confirmed breach exposing passwords or payment card data. Vendor B has no known breach.

**Expected:** A's `breach_compromise_history` category takes a real penalty; B's does not. A's overall posture is materially lower than B's.

**Why it matters:** This is the most basic discrimination test — a real, severe security event must move the score, and move it in a category a reader can trace directly to the finding.

**Note on "adverse media":** the original request framed this as "severe adverse media vs. none," implying GDELT-sourced news coverage. Today, GDELT adverse-media findings are **enrichment/review-queue only** — they are not declared anywhere in `scoring.yaml`, so a collector emitting one is silently excluded from scoring rather than penalising posture (confirmed directly against the shipped config, `test_scenario_1b`). This is worth stating to stakeholders plainly rather than leaving it implied: **adverse media does not move the score today.** If that's a gap worth closing, it's a `scoring.yaml` design decision (what band structure, what corroboration bar) — a separate piece of work from this test suite, and one the model's own "no invented derived index" discipline argues should be approached carefully. Confirmed breach history (`breach_by_data_class`) is the real, already-scored analogue used for this scenario instead.

---

### Scenario 2 — Bankrupt vs. financially healthy vendor

**Setup:** Two vendors with byte-identical cybersecurity evidence. The only difference: one's company registry record shows liquidation/administration (`entity_status: entity_inactive`); the other shows active good standing.

**Expected:** Posture, confidence, and grade are **identical** between the two. The Business Stability / Continuity standing differs — one reads `ceased`, the other `sound` — and is visible to a reader, just not blended into the security number.

**Why it matters:** This is the single most important scenario in the whole feedback response. It's the direct regression guard for a real historical defect (E4): a vendor entering administration used to lose 20 points of *technical security posture*, even though going into administration says nothing about their TLS configuration. Financial distress is real, serious, and must be surfaced — just never mixed into the axis that answers "how exposed is this vendor to compromise."

**Companion scenario (2b):** the same invariant, proven specifically for the *new* collectors this feedback item added (The Gazette, SEC EDGAR, CourtListener) rather than the pre-existing Companies House signal. A `bankruptcy_petition` finding from CourtListener changes neither posture nor confidence versus not having collected it at all — see "A note on how this nearly went wrong" below.

---

### Scenario 3 — Multiple historical breaches vs. none

**Setup:** Vendor A has both a confirmed breach *and* a KEV-listed (actively-exploited) vulnerability — two separate findings in `breach_compromise_history`. Vendor B is clean on both.

**Expected:** A's category penalty reflects **both** findings, not just the worse one — but not their full arithmetic sum either (see Scenario 9). A's posture is materially lower than B's.

**Why it matters:** A vendor with a pattern of security failures should read as worse than one with a single incident, without the model becoming a simple penalty-adding machine that a large enough vendor can never recover from.

---

### Scenario 4 — Poor email security vs. strong email security

**Setup:** Vendor A publishes no DMARC, SPF, or DKIM records. Vendor B publishes DMARC at `p=reject`, a hard-fail SPF record, and DKIM.

**Expected:** A's `identity_email` category takes a real penalty; B's does not. A's posture is lower.

**Why it matters:** Domain-impersonation risk (can someone send email pretending to be this vendor?) is one of the clearest, most binary signals in the model, and the most intuitive one for a non-technical reader to verify themselves.

---

### Scenario 5 — Expired certificate vs. valid certificate

**Setup:** Vendor A is serving an expired production TLS certificate. Vendor B is fully clean, including a valid certificate. Both are otherwise identically well-evidenced.

**Expected:** Vendor A is **capped at posture 49** (the top of Grade D) — not merely penalised proportionally. Vendor B publishes well above that.

**Why it matters:** `cert_validity` is the *only* signal wired to the model's "critical ceiling" — a non-compensatory knockout that says no amount of cleanliness elsewhere can outweigh serving an expired certificate live, in production, right now. This is qualitatively different from every other finding in the model, and the dashboard needs to show it differently (a hard cap, not a deduction) — see Phase 3.

---

### Scenario 6 — Low evidence coverage vs. high evidence coverage (the Ghost)

**Setup:** Vendor A has only 11 of 27 signals answered, all clean. Vendor B has all 27 of 27, also all clean.

**Expected:** A bands **Low confidence** and is flagged as a **Ghost** — a vendor that *looks* clean only because so little was checked. B bands **High confidence** and is not a Ghost.

**Why it matters:** This is the scenario that most directly explains why the executive dashboard (Phase 3) must show Confidence as its own tile, never folded into Posture. A clean-looking score on thin evidence is not the same claim as a clean-looking score on thorough evidence, and conflating them is exactly how a barely-evidenced vendor could look identical to a thoroughly-vetted one.

---

### Scenario 7 — Independent, corroborated assurance vs. a disclosure-only claim

**Setup:** Vendor A claims a security certification that is **not** corroborated against any registry (`cert_posture: claimed_unverified`). Vendor B publishes a detailed trust/security page with no verifiable certification claim at all (`program_disclosure: detailed_policies`).

**Expected:** A's claim reaches `compliance_regulatory` and takes a real penalty (an unverified claim is worse than no claim — see below). B's disclosure lands in `assurance_context`, a context-only category that **never** penalises posture.

**Why it matters:** This is a deliberately drawn distinction from the model's own history (E5): a certification claim that can be checked against a registry is *evidence*; a marketing trust page is not. Note the asymmetry is not "corroborated beats disclosed" in the simple sense — an *unverified* claim actively costs points (asserting something that doesn't check out), while a vendor with no certification claim at all pays nothing for it. A vendor with genuine, registry-corroborated certification (`cert_posture: registry_corroborated`) scores a clean pass, which is the intended positive case this scenario's mirror image demonstrates.

---

### Scenario 8 — Regulatory enforcement action vs. a sanctions-list match

**Setup:** Vendor A has a formal regulatory enforcement action on record. Vendor B has a possible match against a sanctions list.

**Expected:** A **publishes** a score, penalised in `compliance_regulatory`. B receives **no score at all** — blocked pending human adjudication, not a Grade F.

**Why it matters:** These are two fundamentally different mechanisms the platform uses for "this is bad," and conflating them on a dashboard would misrepresent both. A regulatory action is a fact the model can weigh; a sanctions match is a legal question (dealing with a sanctioned entity can be a criminal offence) that a number must never appear to answer. The dashboard (Phase 3) needs a visibly different treatment for "scored and penalised" versus "blocked, needs a human."

---

### Scenario 9 — Compounding findings: diminishing returns within a category

**Setup:** A vendor is missing three security headers (HSTS, CSP, X-Frame-Options) — three separate low-severity findings, all in `attack_surface_hygiene`.

**Expected:** The combined penalty is **less than** the sum of three individual penalties (1.5 points each) — specifically ≈3.29 points, not 4.5.

**Why it matters:** The tenth missing header on a vendor already missing nine tells a reader almost nothing new — it's the same underlying organisational fact ("nobody is minding the headers") counted repeatedly. Without this diminishing-returns rule, a vendor with many small, correlated gaps could rank worse than one with a single serious vulnerability, which inverts what actually matters. **This only applies within one category, never across categories** — a vendor with an expired certificate (`attack_surface_hygiene`) *and* no DMARC (`identity_email`) pays for both in full, because those are two independent facts about the vendor, not one fact restated.

---

### A note on how this nearly went wrong

While wiring the new financial-data collectors (The Gazette, SEC EDGAR, CourtListener), the first working version declared their signals in the same evidence-coverage denominator that gates every vendor's Posture confidence. That passed every unit test but **failed the frozen regression corpus**: replaying five real vendors' already-stored evidence against a denominator that grew by three (because that historical evidence naturally has no record for collectors that didn't exist yet) silently dropped every one of their confidence bands — Atlassian fell out of "High" confidence entirely, for no evidential reason.

The fix — and the reason Scenario 2b exists as its own test — was to give Business Stability its own, separate coverage count (`ScoringConfig.business_stability_signals`, `continuity.business_stability_coverage`), excluded from the Posture-confidence axis by construction. This is the same principle Scenario 2 demonstrates at the model-design level, caught here at the implementation level: **a new axis must never leak into an existing one's arithmetic, even by accident.**
