# Supplier Peer Benchmarking — design decisions of record

**Status:** locked 2026-07-30 · **Supersedes:** the cohort machinery in [benchmark.py](../backend/app/benchmark.py)
**Implements:** `backend/app/benchmarking/` · **Config:** `benchmarks.yaml` → `benchmarking:`

> This layer answers exactly one customer question: **"is this supplier's risk posture normal, good,
> or poor compared to similar suppliers?"**
>
> It is **not** a scoring engine. It reads posture, confidence and domain scores that already exist,
> and contextualises them. **If every line of this module were deleted, every published score would
> be byte-identical.** That property is asserted by test, not promised in prose.

---

## The five decisions

Locked before implementation, because each one changes the database schema or the published output.

| # | Decision | Chosen | Rejected alternative |
|--:|---|---|---|
| **1** | Cohort scoping | **Vendor-only cohorts.** Dimensions are `sector`, `size_band`, `delivery_model`. `data_access_scope` is an **interpretation filter**, never a cohort dimension | Relationship-scoped cohorts including `data_access_scope` — fragments the pool ~4×, makes cohorts tenant-dependent, re-opens cross-tenant pooling |
| **2** | Cold start | **Labelled external base rates as a reference line**, plus honest `Insufficient peer data (n=4)`. A reference line is a *population statistic*, never a peer median | Blank cards; or synthetic peers dressed as a cohort |
| **3** | Synthetic reference points | **Hard gate.** `is_synthetic = true` forbids *any* percentile or quartile at *any* n. Reference line + prose only | Label-only — thirty invented numbers still yield a screenshottable fake percentile |
| **4** | Member disclosure | **Aggregates only externally. Member refs stored internally**, for dispute and audit | Full member list to the supplier (cross-tenant confidentiality); or storing nothing (kills dispute) |
| **5** | Pool size assumption | **Hundreds in year one.** Design for quartile + rank-of-n first; percentiles switch on automatically at n≥30 | Assuming thousands and shipping a percentile-first UI that shows "insufficient data" everywhere |

### Decision 1, in full — why `data_access_scope` is not a cohort dimension

`sector`, `size_band` and `delivery_model` are properties **of the supplier**. `data_access_scope` is
a property **of the relationship** — it is what *this buyer* exposed to them, the same quantity
`criticality` already carries.

Putting it in the cohort key would mean the same supplier belongs to different cohorts for different
buyers. Three consequences, all bad: it breaks "exactly one cohort per supplier"; it fragments the
peer pool per tenant precisely where n≥30 is needed; and it silently re-introduces cross-tenant
pooling, which [complete_plan.md](complete_plan.md) records as *"a contractual question before an
engineering one."*

So scope routes to **interpretation**: it selects the procurement action template and it filters the
buyer's own book. It never selects the peers. This preserves the layering the platform already
insists on — **inherent risk (buyer-side) interprets the comparison; it never defines it.**

### Decision 4, in full — the member-ref visibility rule

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

## Cohort assignment

### Dimensions

| Dimension | Values | Source |
|---|---|---|
| `sector` | string, normalised | supplier record |
| `size_band` | `micro` · `small` · `mid` · `large` · `enterprise` | **derived** — see below |
| `delivery_model` | `saas` · `on_prem` · `managed` | supplier record |

`data_access_scope` (`low`/`medium`/`high`/`critical`) is carried on the placement for
interpretation, and is **absent from every cohort key**.

### `size_band` is derived, versioned and disputable

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

### The ladder — deepen, then widen, then refuse

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

## Placement thresholds — the hard rules

| Condition | Published |
|---|---|
| `is_synthetic` | **Reference line + prose only.** No percentile. No quartile. At any `n` |
| `n < 8` | `"Insufficient peer data"` + the actual `n`. No quartile, no percentile |
| `8 ≤ n < 30` | **Quartile + rank-of-n** + direction vs median. **No percentile** |
| `n ≥ 30` | Percentile (with resolution band) + quartile + rank-of-n + direction vs median |

`n` is **always** published alongside any output, and `n` counts **peers, excluding the subject** —
otherwise "n=30" is 29 peers and the boundary rule is wrong by one.

### Estimator choices, and why

| Choice | Decision | Reason |
|---|---|---|
| Ties | **Midrank**: `100·(below + 0.5·equal)/n` | *At-or-below* pushes a supplier tied with ten others at the median **above** the 50th percentile. Postures are integers 0–100; at n=40 collisions are certain |
| Rank | **`rank_of_n` is required, not optional** | *"17th of 34"* needs no estimator choice, cannot overstate precision, and survives one peer joining. At n=8–29 it is strictly more informative than a quartile letter |
| Percentile precision | Snapped to the achievable step, **step published** | At n=8 the step is 12.5, so an "83rd percentile" claims precision the sample cannot express |
| Median | **Nearest-rank, no interpolation** | *"An interpolated median between two real vendors is a company that does not exist"* |
| Outliers | **IQR fence (p25 − 1.5·IQR)**, never standard deviations | SD assumes normality and is destabilised by one extreme member — and at n=8–20 one member *is* a large share of the population |
| Quartile labelling | `quartile: 1..4` **plus** `quartile_label` **plus** `quartile_direction` | Q1 means "best" in finance and "worst" elsewhere. A bare `Q1` is a footgun. `1 = lowest posture`, stated in the payload |

### Per-domain `n` is not cohort `n`

A cohort of 40 may hold only 12 suppliers with an `email_auth` score. **Every domain row carries its
own `n` and its own resolution label, and the thresholds apply per domain independently.** One card
will legitimately show *overall: 62nd percentile (n=41)* beside *email_auth: bottom quartile (n=13)*
beside *breach_history: insufficient peer data (n=5)*. That reads as an inconsistency unless every
row is labelled — which is also why there is **no composite benchmark score**.

A peer never assessed for a domain is **not** a peer that failed it. It leaves that domain's
denominator.

---

## Two confidences, never merged

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

## Snapshots — reproducibility, and the feature that falls out of it

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

## Dispute — inputs only, and notated while open

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
  [report.md](report.md) records the US Chamber / FCRA principle that *"disputed ratings must be
  notated as such until resolved."* Silence during review is the exposure.

---

## The discrimination test

Automates, per cohort, the analysis [complete_plan.md](complete_plan.md) ran by hand — which found
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

## Narrative — versioned templates that refuse to render

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

## What is not built

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

## Migration from `benchmark.py`

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
