# Vendor Risk Metrics — Complete Guide

This document explains the metrics the OSINT TPRM Module publishes, the theory each one rests on,
and the arithmetic actually implemented in the code. Every constant quoted here was read from
`scoring.yaml` or the module named beside it — where configuration and code disagree, that is
called out explicitly rather than smoothed over.

Model version: `scoring.yaml` `version: 5.4.0`, `model: penalty_subtractive`.

## Overview

The module deliberately reports several **separate axes** rather than one blended number, because
each answers a different question and blending them destroys the ability to act on any of them:

| Axis | Question it answers | Where it is computed |
|---|---|---|
| **Posture** | How exposed is this vendor to compromise? | `scoring/engine.py` |
| **Confidence** | How much of the evidence we would *expect* for a company like this did we find? | `confidence_calculator.py` |
| **Business Stability** | How likely is this vendor to still be trading? | `business_stability.py` |
| **Assurity** | How much *independent* assurance stands behind their claims? | `assurity.py` |
| **Longevity / Maturity** | How long have they operated, and how well is that evidenced? | `longevity.py`, `maturity.py` |
| **Lifecycle** | What organisational stage are they in? | `lifecycle.py` |

### The theoretical commitment behind separate axes

This is a **multi-attribute decision model with deliberately non-compensatory aggregation across
axes**. In MCDA terms, a fully compensatory model (weighted sum of everything) allows a strong
attribute to buy back a weak one. That is the wrong property here: a published trust page must
never offset an expired production certificate, and financial distress must never read as a
security failing. Each axis is therefore aggregated internally (partially compensatory, with
limits) and **never** across axes.

Two structural rules follow, and both are enforced in arithmetic rather than by convention:

1. **Missing data reduces Confidence, never Posture.** The posture divisor is fixed by the model,
   so a silent collector contributes no penalty *and* cannot move the denominator.
2. **Absence never subtracts on Assurity.** Not holding a certification is not a finding. The
   only thing that subtracts on that axis is a *compliance gap* — a vendor asserting a framework
   and being observed failing a control inside its scope.

---

## 1. Posture Score

### What it measures

The strength of a vendor's externally observable security posture — how exposed they are to
compromise, on public evidence only.

### Theoretical model

A **subtractive penalty model**, not a weighted-additive scorecard. Every vendor starts at 100 and
each observed issue subtracts. The property this buys is the important one: a signal that returned
nothing contributes nothing, so the model cannot reward opacity or punish a vendor for being
hard to observe. There are **no category weights at all** — influence emerges from what was found,
which is the point of a penalty model.

The severity ladder and the aggregation decay are **expert judgement, not calibrated values**, and
`scoring.yaml` requires them to be labelled as such wherever they are published. Calibration
requires outcome labels (see `docs/e0.4-outcome-labels-deferral.md`).

### Scale

- **0–100** (100 = strongest, 0 = weakest)
- **Grades** (`scoring.yaml grades`): **A ≥ 85 · B ≥ 70 · C ≥ 50 · D ≥ 30 · F ≥ 0**

### Severity ladder (`severity_penalties`)

| Severity | Penalty | Example |
|---|---:|---|
| Critical | **50** | expired production cert, unpatched KEV, CVSS 9–10 |
| High | **20** | no DMARC, TLS 1.0/1.1, confirmed breach of personal data |
| Medium | **6** | weak TLS, `p=none`, missing SPF, CVSS 4–6.9 |
| Low | **1.5** | missing security header, no DNSSEC, CVSS 0.1–3.9 |
| Informational | **0** | recorded but **not scored** — unverifiable observations |

Critical : Low is **33.3 : 1**. This ratio was widened deliberately (E7b). At the old ladder,
four Medium plus eight Low findings (56 points) outranked one Critical (40) — a dozen missing HTTP
headers beating an actively-exploited vulnerability at 0.71 : 1. Widening alone only reaches
1.39 : 1; it ships with rank decay (below) because neither half is sufficient. Together: **3.06 : 1**.

### Categories (`scoring.yaml categories`)

**Five scoring categories** — these can penalise:

1. **`breach_compromise_history`** — realized > exploited > theoretical
   (`breach_by_data_class`, `kev_listed_cve`, `nvd_cve`)
2. **`attack_surface_hygiene`** — the estate and how well it is kept
   (`tls_version`, `cert_validity`, `hsts`, `csp`, `x_frame_opts`, `dnssec`, `caa`,
   `subdomain_estate`, `stale_hosts`, `weak_issuance`, `estate_tls_legacy`, `estate_cert_expired`)
3. **`identity_email`** — can this vendor be impersonated? (`dmarc`, `spf`, `dkim`)
4. **`transparency`** — can this vendor be *told* about a vulnerability? (`vd_program`, `security_txt`)
5. **`compliance_regulatory`** — claim reliability, not audit budget (`cert_posture`, `regulator_action`)

**Two context categories** — they count toward coverage but contribute **exactly zero** to posture
by construction:

6. **`continuity_context`** — will this vendor still be trading? (`entity_status`, `entity_existence`,
   `entity_maturity`, `domain_registration`, `sec_filing`, `sec_going_concern`, `insolvency_notice`,
   `bankruptcy_petition`)
7. **`assurance_context`** — `contactability`, `program_disclosure`, `reporting_posture`

Context categories exist rather than the signals being deleted because `planned_signal_count` is
the coverage denominator (**27** signals). Deleting them would raise every vendor's confidence for
no evidential reason — the check still ran, we would simply have stopped recording it.

### Per-finding modifiers (`modifiers`)

Applied to each finding before aggregation:

- **Age decay** — `0.5 ^ (months / 36)`, floored at **0.15**. A three-year half-life on historic
  occurrences. `cert_validity` is in `never_decays`: a certificate's `notAfter` is a *state
  boundary*, not an event, so decaying it made a cert expired six years ago cheaper than one
  expiring next week.
- **Frequency** — `1 + 0.25 × (n − 1)`, capped at **2.0**. Three breaches are a pattern (×1.5),
  not one breach counted three times. `kev_listed_cve` and `nvd_cve` are exempt: a bag of
  keyword-matched CVEs is coarse-match noise, not distinct events.
- **Mitigation** — **×0.6**, applied only where remediation is *evidenced*, and applied once.

### Aggregation within a category (`aggregation.decay = 0.7`)

```
CategoryPenalty(c) = Σᵢ pᵢ × 0.7^(rankᵢ − 1)      # ranked by descending penalty
```

**Rationale.** The tenth missing header on a vendor already missing nine tells you almost nothing
new — you already know nobody is minding the headers. Charging it in full counts one organisational
fact ten times. Rank decay expresses diminishing informational return, and it is applied **within**
a category only: a cross-category discount would let a vendor's worst category be cheapened by
their second-worst, which is precisely the compensatory behaviour the critical ceiling exists to
prevent.

Two prior steps protect the ranking:
- **Worst-of collapse** — every `(category, signal)` group contributes one penalty, its worst
  member *after* decay. So a fresh High can outrank a long-decayed Critical.
- **Root-cause deduplication** — one remediation ticket, one penalty. Patching a KEV-listed CVE
  fixes the NVD finding in the same action. Suppression zeroes the *penalty*, never the *evidence*.

### Final posture

```
Posture = 100 − ( Σ_categories min(penalty, 100) ) / 2.86
```

**Why a fixed divisor.** It is *not* a mean over the categories that answered. Averaging only
answering categories made a clean trust page worth +23 posture, because each clean category entered
the average as a 100 and pulled it up — silence changing the score, which is exactly what
"missing data never changes posture" forbids.

**Why 2.86 specifically.** `divisor(n) = n × (4/7)` holds maximum damage constant at 175 posture
points regardless of how many scoring categories exist. Five scoring categories → **2.86**. Leaving
it at the old 4 would have cut maximum damage to 125 and made the model *quietly more forgiving*
without anything visibly failing. Asserted by `test_divisor_preserves_maximum_damage`.

Category-level posture shown in the breakdown is `100 − category_penalty` (undivided).

### Non-compensatory overrides

- **Gates (emit nothing).** Entity resolution confidence < **0.5**, a sanctions hit, or a
  configured finding gate (`entity_dissolved`) **BLOCKS**: no posture, no grade, routed to a human.
  A gate is not a low score — a vendor with a disqualifying finding publishing 60 clears a
  ">= 50" procurement threshold and gets onboarded by a rule nobody re-read.
- **Critical ceiling (caps, never sets).** A directly-observed current critical caps posture at
  **49** — the top of Grade D. Armed only by `cert_validity` on the **apex host**
  (`auto_signal_scope`); arming on any host in a fanned-out estate would cap every large vendor on
  one abandoned staging certificate, and a non-compensatory response that fires constantly is one
  nobody reads. `kev_listed_cve` and `breach_by_data_class` require human confirmation to arm.
- **Confidence ceiling ramp** — see §2.
- **Refusal (the Ghost).** Confidence < **0.40** → posture is **not published**. Per
  `insufficient_evidence_is_adverse: true`, this is an **adverse** result, not a neutral one, and
  the UI is required to render it that way.

### Log-odds preview (E13, not published as posture)

`max(0, …)` means a vendor at three times the cap and one at six times both publish 0, so the model
cannot rank the worst suppliers in a book. A bounded log-odds transform with shrinkage toward a
peer rate (`scoring/log_odds.py`) is computed **alongside** as a preview field. It refuses whenever
`L_peer` would come from fewer than eight real peers — shrinking an under-evidenced vendor toward
invented postures is worse than not shrinking at all.

---

## 2. Confidence Score

### What it measures

Not "how much data did we get" but: **what percentage of the evidence we would expect to exist for
a company like this did we actually find?**

### Theoretical model

The naïve formulation `found / all_possible` embeds a systematic bias: it penalises young and
small companies for lacking evidence they could not yet have produced. A two-month-old startup has
no five-year SOC 2 observation window, and no SEC filings, and cannot acquire either by trying
harder.

The implemented alternative is a **conditional expectation ratio** — the denominator is the
evidence set expected *given the vendor's profile*, so an unattainable signal never enters it:

```
Confidence = Σ weights(expected ∧ found) / Σ weights(expected)      # capped at 1.0
```

This is the same principle as `attainable_after_years` in `benchmarks.yaml`: measure vendors
against what is attainable for them, not against an absolute footprint.

### Scale

- **0.0–1.0**
- **Bands** (`confidence.bands`): **High ≥ 0.90 · Medium ≥ 0.70 · Low < 0.70**
- Below **0.40** (`refuse_below`) nothing is published.

### Signal expectations (`confidence_config.py`)

**Always expected — attainable day 1, total weight 108:**

| Signal | Weight | | Signal | Weight |
|---|---:|---|---|---:|
| `domain_registration` | 15 | | `dmarc` | 12 |
| `entity_status` | 15 | | `spf` | 8 |
| `cert_validity` | 12 | | `dkim` | 5 |
| `entity_existence` | 10 | | `hsts` | 5 |
| `tls_version` | 10 | | `csp` | 5 |
| `dnssec` | 5 | | `x_frame_opts` | 3 |
| `caa` | 3 | | | |

**Scales with age** — expected only past a minimum operating age:

| Signal | Weight | Expected after |
|---|---:|---|
| `insolvency_notice`, `bankruptcy_petition` | 15, 15 | 1 year |
| `kev_listed_cve`, `nvd_cve` | 15, 10 | 1 year |
| `security_txt`, `contactability` | 5, 8 | 1 year |
| `regulator_action` | 20 | 2 years |
| `breach_by_data_class` | 15 | 2 years |
| `vd_program`, `program_disclosure`, `reporting_posture` | 12, 10, 8 | 2 years (and ≥ small) |
| `sec_filing` | 20 | 2 years (and ≥ medium, US only) |
| `cert_posture` | 15 | 3 years (and ≥ small) |

**Scales with size** — `subdomain_estate` (8), `stale_hosts` (10), `estate_tls_legacy` (10),
`estate_cert_expired` (10) require ≥ medium; `weak_issuance` (8) requires ≥ small.

### Expected-weight denominators (computed from the code)

| Operating years | Band | Size unknown | Size small | Size medium+ |
|---|---|---:|---:|---:|
| 0.5 | startup | 108 | 116 | 154 |
| 1.5 | startup | 176 | 184 | 222 |
| 2.5 | young | 211 | 249 | 307 |
| 3.5+ | young → veteran | 211 | 264 | 322 |

The denominator **plateaus at three years** — past that, age adds no further expectations and only
size does. Note that an **unknown size band is treated as the smallest**, so every size-gated
signal drops out of the denominator; this is conservative but it means confidence for a vendor with
no size evidence is computed over a materially smaller expected set.

### Worked comparison

- **Startup, 0.5 years, size unknown, all 13 always-expected signals found** → 108/108 = **100%**.
- **Veteran, 15 years, size unknown, only the always-expected 13 found** → 108/211 = **51.2%** (Low).

A veteran missing financial filings is penalised; a startup missing the same filings is not,
because they are not yet expected. The differentiation is produced by the denominator, not by a
flat penalty table.

### Signal statuses

Only `FOUND` and `NOT_FOUND` move the number. `SEARCH_FAILED` (our collector broke),
`NOT_APPLICABLE` and `NOT_CHECKED` are excluded from **both** numerator and denominator — our
infrastructure failing is not the vendor's evidence gap. Signals the run *planned* and got nothing
for are reclassified as `NOT_FOUND`: planned means attempted, and attempted-and-absent is exactly
what a reader needs itemised.

### Confidence ceiling ramp (`confidence.ceiling_ramp`)

Thin evidence caps how good a vendor may **look** — a cap, never a deduction, so no category
penalty is touched:

| Coverage ≥ | Posture ceiling |
|---|---:|
| 0.90 | 100 (no cap) |
| 0.75 | 97 |
| 0.60 | 90 |
| 0.40 | 80 |
| < 0.40 | not published |

Before this ramp there was a single cliff at 40%: a vendor seen through four collectors could
publish 100 and read identically to one seen through fourteen, making *being hard to observe* the
cheapest route to a high score.

### Fallback path

If the age-based calculation raises, `scoring/engine.py` falls back to raw coverage
(`covered / planned`) multiplied by a bounded assurance multiplier derived from `entity_maturity`
(floor **0.40**, ceiling **1.04**). When multiple maturity observations exist, the **most
conservative** multiplier wins, so an old domain in front of a young company cannot buy assurance
the company has not earned.

### Deduction labels

Each gap carries a human-readable label and category — e.g. "DMARC email authentication missing"
(`email_security`, −12), "SEC regulatory filings missing" (`financial_transparency`, −20). Impact
is banded: high ≥ 15, medium ≥ 8, low otherwise.

> **Known defect.** `ConfidenceCalculator.calculate_from_profile` passes `profile.sector` into the
> `jurisdiction` parameter. For `sec_filing` (the only `jurisdiction_required` signal) any
> non-US-looking value drops it from the denominator. Harmless while size is unknown, since
> `sec_filing` is size-gated anyway, but wrong for medium+ vendors.

---

## 3. Business Stability Score

### What it measures

Financial health and continuity — will this vendor still be trading? Deliberately separate from
posture: **a bankrupt company can have excellent security controls, and a secure startup can run
out of cash.**

### Theoretical model

Age-anchored base score plus evidenced adjustments. The age anchor rests on the **liability of
newness** (Stinchcombe, 1965): young organisations face materially higher hazard rates because
they must build roles, routines and external trust from nothing while consuming scarce resources.

**Real-world survival base rates.** US Bureau of Labor Statistics Business Employment Dynamics
establishment survival data supports, approximately:

- ~**20%** of new establishments fail within the first year
- ~**50%** survive to five years
- ~**33%** survive to ten years
- surviving cohorts show a **declining hazard rate** — the longer a firm has traded, the lower its
  annual failure probability, which is what justifies survivorship credit

These are establishment-level US figures used as a **proxy** for entity survival, not a fitted
model of any specific vendor. They set the shape of the base curve; they are not a prediction.

**Explicitly out of scope:** Altman Z-score, cash burn, funding runway, D&B-style credit scoring
and any natural-person financial data. Computing an in-house distress index from scraped
fundamentals is credit-rating territory and defamation-adjacent when wrong. These sit on
`held_roadmap` (see `continuity.py`, `docs/tprm_feedback_redesign.md`).

### Scale

- **0–100**, or **None** when gated
- **Standing**: sound ≥ 80 · watch ≥ 60 · impaired ≥ 40 · ceased < 40 (or gated)

### Gate logic (checked first, blocks scoring)

- Any insolvency record with `status == "active"` → **BLOCK**
- Company status in {`liquidation`, `administration`, `receivership`, `dissolved`} → **BLOCK**

A gate returns `score: None` with a stated reason. Historical insolvency is a penalty, not a gate.

### Base score by age band (`longevity.py base_age_score`)

| Band | Years | Base | `base_adjustment` | **Effective base** |
|---|---|---:|---:|---:|
| startup | < 2 | 50 | −30 | **20** |
| young | 2–5 | 65 | −20 | **45** |
| established | 5–10 | 80 | 0 | **80** |
| mature | 10–20 | 90 | 0 | **90** |
| veteran | 20+ | 100 | 0 | **100** |
| unknown | — | 60 | not applied* | **60** |

\* `_apply_age_based_adjustments` returns early for `unknown`, so neither the −15 adjustment nor
any multiplier is applied.

### Financial penalties (`_apply_financial_penalties`)

| Signal | Penalty | Source |
|---|---:|---|
| Going-concern language | 25 | SEC EDGAR — the vendor's own auditor doubting continuity |
| Historical insolvency, ≤ 3 years ago | 20 | resolved but recent |
| Historical insolvency, > 3 years ago | 5 | minor |
| Revenue declining across recent periods | 15 | every consecutive period lower |
| Debt-to-equity > 3 | 10 | latest period |
| Debt-to-equity > 2 | 5 | latest period |
| Negative net income across last 2 periods | 15 | net income used as a cash-flow proxy |

Only one historical-insolvency penalty is charged. `scoring.yaml` additionally declares
`voluntary_arrangement` (15), `declining_profitability` (10), `high_customer_concentration` (10)
and `no_recent_funding_18_months` (5) — **these are declared but not yet wired** in
`business_stability.py`.

### Survivorship bonus and age multipliers

Bonus: mature **+5**, veteran **+10**, others 0 (a further +5 for surviving a known downturn is
implemented in `survivorship_bonus` but not currently invoked by the engine).

| Band | Penalty × | Bonus × |
|---|---:|---:|
| startup | 1.5 | 0.5 |
| young | 1.2 | 0.7 |
| established | 1.0 | 1.0 |
| mature | 0.9 | 1.2 |
| veteran | 0.8 | 1.5 |

The asymmetry is the theory made arithmetic: a young firm has less balance-sheet buffer, so the
same distress signal is worse; a veteran has demonstrated it can absorb shocks, so the same signal
is less predictive of exit.

```
Business Stability = clamp(0, 100, effective_base − Σ(penalties × mult) + Σ(bonuses × mult))
```

### Outcomes with no adverse financial evidence at all

| Band | Score | Standing |
|---|---:|---|
| startup | **20** | ceased |
| young | **45** | impaired |
| established | **80** | sound |
| mature | **96** | sound |
| veteran | **100** | sound |
| unknown | **60** | watch |

> **⚠️ Two divergences that need a decision.**
>
> 1. **Config and code disagree on the base curve.** `scoring.yaml`
>    `business_stability.age_base_scores` reads 70/75/80/85/100/60 and its
>    `confidence_adjustments` read −0.15/−0.10. The runtime path
>    (`business_stability.py` → `longevity.py`) reads 50/65/80/90/100/60 and −0.60/−0.50, and never
>    loads the YAML block. **The code wins at runtime; the YAML block is inert.** `docs/methodology.md`
>    documents the YAML numbers and is therefore describing values that never execute.
> 2. **A clean startup is labelled "ceased".** With zero adverse findings, a <2-year-old vendor
>    scores 20 and lands in the same standing as a company in liquidation. That is a base-rate
>    prior being reported in vocabulary reserved for an observed outcome, and it contradicts
>    `lifecycle.py`'s own caveat: *"A young company is not thereby an impaired counterparty — that
>    is the founding-date scoring this system refuses."* Either the base curve or the standing
>    thresholds should move.

### Age differentiation profile (`age_risk_factors.py`)

Alongside the score, six dimensions are banded for narrative context:

| Dimension | Bands |
|---|---|
| Historical depth | sparse · limited · moderate · rich · extensive |
| Financial transparency | opaque · limited · partial · transparent · comprehensive |
| Leadership risk | founder_dependent/high · moderate · low · stable |
| Operational maturity | immature · developing · mature · established · legacy |
| Media velocity | unknown · low · moderate · high · critical |
| Structural change | neutral · low · moderate · high_suspicion |

The same observation is read differently by age — a name change at 18 months is normal
repositioning; three name changes and two address changes at 20 years is a suspicion signal.
Several inputs (leadership history, media counts, structural changes) are **currently passed as
placeholders** from `business_stability.py` and are not yet collector-fed.

---

## 4. Assurity Score

### What it measures

**Independent assurance** — how much externally verifiable evidence exists that a security
programme is audited and operating. It is explicitly *not* a security score.

### Theoretical model

```
Assurity = 100 × σ( intercept + scale × Σ credits − γ × compliance_gaps )
```

where `σ(x) = 1 / (1 + e^(−x))`.

**Why this axis exists.** Before it, the model expressed assurance by *subtracting* for its
absence — `cert_posture.none_claimed` cost 8 points and fired on five of five corpus vendors. That
is a tax on audit budget, not a measure of risk, and it fell hardest on exactly the small suppliers
this product exists to assess fairly.

**Why a sigmoid rather than a sum.** The logistic function is bounded without a cliff at either
end and is monotone in the credit sum. The twentieth certification cannot buy what the second did
(saturation), and no vendor is ever pinned at exactly 0 or 100 — so the axis keeps resolving
differences at both extremes, which is precisely the defect the log-odds work exists to fix for
Posture. Credits are additive in **log-odds** space, which is the natural space for combining
independent pieces of evidence.

**Absence never subtracts — enforced, not intended.** `_validate` rejects a negative credit at load
time. A vendor with nothing observable sits at the intercept, which is deliberately **low rather
than zero**, because unevidenced is not disproved and a 0 would read as *"audited and failed"*.

### Parameters (`scoring.yaml assurity`)

- `enabled: true` · `intercept: −1.2` · `scale: 1.0` · `gamma: 0.8` · `min_observed_signals: 3`
- **Published range: 23 → 97.** Floor = σ(−1.2) ≈ 0.231. Ceiling = σ(−1.2 + 4.8) ≈ 0.973.

### Credit table

| Signal | Band | Credit |
|---|---|---:|
| `cert_posture` | `registry_corroborated` | **1.4** |
| `cert_posture` | `claimed_unverified` | 0.2 |
| `reporting_posture` | `substantive` | 0.9 |
| `reporting_posture` | `partial` | 0.3 |
| `vd_program` | `bug_bounty` | 0.8 |
| `vd_program` | `security_txt_only` | 0.3 |
| `program_disclosure` | `detailed_policies` | 0.6 |
| `program_disclosure` | `marketing_only` | 0.1 |
| `contactability` | `dpo_and_security_contact` | 0.4 |
| `contactability` | `partial` | 0.1 |
| `dnssec` | `valid` | 0.3 |
| `security_txt` | `present` | 0.2 |
| `caa` | `present` | 0.2 |

The gap between `registry_corroborated` (1.4) and `claimed_unverified` (0.2) is the axis's whole
thesis: an independently verifiable certification is worth seven times a marketing claim.

### The only subtraction

A **compliance gap** (γ = 0.8 each) — the vendor asserting a framework and being observed failing a
control within its scope. That is a statement about the reliability of their own claims, which is
exactly what this axis measures. A compliance gap **never touches Posture**. It is high-signal
precisely because the way to game it is to drop the claim, which is itself informative.

### Publication threshold

Below **3 observed signals**, nothing is published. "2 of 3" assembled from whichever checks
happened to return is the same false precision as a median over three peers.

Note that `observed` counts signals that were **checked**, whether or not they evidenced anything —
a checked-and-empty signal is a real observation, and is still not a subtraction.

### Age handling

Age does **not** adjust the credit sum or the score. It adjusts only the reported **confidence**,
via `longevity.confidence_adjustment` mapped from the `entity_maturity` band: startup −0.60,
young −0.50, established/mature/veteran 0.00, unknown −0.05.

> **Correction to earlier documentation.** There is no weighted-component model
> (25/20/20/15/10/10), no "attainability" band (Full/Partial/Minimal), and no age cap on the
> attainable score. Those described a design that was never implemented.

---

## 5. Longevity and Maturity

### What it measures

Operating history, and — separately — **how well that history is evidenced**.

### Age bands (`longevity.age_band_from_years`)

```
< 2 → startup   |   2–5 → young   |   5–10 → established   |   10–20 → mature   |   20+ → veteran
```

`maturity.py` carries a parallel band vocabulary used by `scoring.yaml` for narrative lookup:
`new_lt_1` · `startup_lt_2` · `young_2_5` · `established_5_10` · `mature_gt_10`.

### The maturity index — why it saturates

```
index(y) = min(1, ln(1 + y) / ln(1 + 25))          SATURATION_YEARS = 25
```

A step table could not tell an 11-year-old vendor from a 40-year-old one: everything past ten years
was one bucket. But a linear-in-years term would make "old" the single largest term in the model.
The **logarithmic, saturating** curve encodes the actual epistemics: year two of trading is
enormously informative, year forty is not. A vendor trading 25 years has demonstrated continuity
across at least two full economic cycles; one trading 40 has not demonstrated meaningfully more.

### Evidence strength — why age is discounted by source

**Age is purchasable.** An aged domain costs a few hundred dollars at an expiry auction; a company
inception date in a national register does not. Weighting every source equally would have made
"buy an old domain" the cheapest posture uplift in the product.

```
assurance_index(y, source) = min( index(y), index(y) × evidence_strength(source) )
```

| Source | Strength | |
|---|---:|---|
| `gleif`, `companies_house`, `abn` | 1.00 | authoritative entity registers |
| `wikidata` | 0.90 | curated inception date, community-maintained |
| `firmographics`, `pdl` | 0.80 | aggregated founding year |
| `rdap` | 0.60 | domain creation — a proxy, and a buyable one |
| unrecognised | 0.60 | a new collector earns its weight; it does not inherit it |

The discount is **one-directional**: a weak source can never buy assurance, and can never
manufacture youth that isn't there either.

### Source priority for the date itself

1. Incorporation date from entity registers (OpenCorporates, Companies House, ABR, GLEIF)
2. Wikidata P571 (legal inception)
3. RDAP domain creation date (discounted, free fallback)
4. `unknown`

### Where age is allowed to reach

Age reaches exactly three places, and **posture is not one of them**:

1. **Confidence** — the bounded assurance multiplier (floor 0.40, ceiling 1.04)
2. **Benchmarking** — cohort assignment and `attainable_after_years`
3. **Business Stability** — base score and penalty/bonus multipliers

`docs/context-aware-vendor-risk-scoring-study.md` §1.6 finds **no published evidence that founding
date predicts security posture**, which is why age is confined to Confidence and Benchmarking on
the security side. `scoring/engine.py` carries an explicit comment recording that a previous
revision added a table charging young vendors 6–15 posture points *where no finding had been
observed* — a deduction with no evidence behind it, levied on a company for being new — and why it
was removed. Two vendors with identical findings get an identical posture. That is deliberate.

### Contingency planning

`contingency_plan_required` returns True for **high** criticality with a startup or young vendor,
and for **medium** criticality with a startup — a control response to elevated base-rate exit risk,
rather than a score deduction.

---

## 6. Lifecycle

### What it measures

Organisational stage — and it is **context only**. It is not a score, it emits no finding, it
writes nothing to the store, and it cannot reach the scoring engine.

### Theoretical model: Adizes corporate lifecycle

`lifecycle.py` implements stages from the **Adizes corporate lifecycle** model (Adizes, 1979;
*Corporate Lifecycles*, 1988), which characterises organisations by the changing balance of
flexibility and control rather than by funding or headcount. Firms are most flexible and least
controlled at birth, most controlled and least flexible in old age, and best balanced at Prime.

```python
< 1  → infancy      # under 1 year
< 2  → go_go        # rapid growth, processes forming
< 5  → adolescence  # structure emerging, not yet stable
< 15 → prime        # peak balance of control and flexibility
≥ 15 → aging        # established, accumulating path-dependency
None → unknown
```

Derived solely from operating years (entity inception, or domain age as fallback).

### What each stage means for a buyer

| Stage | Buyer-relevant reading |
|---|---|
| **Infancy** | Financial fragility (no revenue history), compliance immaturity (no SOC 2 observation window yet), key-person dependency. DMARC/TLS gaps are greenfield misses — hygiene not embedded in founding habits. |
| **Go-Go** | Processes forming, financial model unproven. Gaps indicate security deprioritised during growth. SOC 2 Type 2 unlikely — insufficient observation window. |
| **Adolescence** | Structure emerging. Cohort benchmarking against similarly-aged peers is more meaningful than comparison with incumbents. Gaps here suggest deliberate inaction rather than resource constraint. |
| **Prime** | Established processes and governance. Watch for emerging path-dependency. Gaps are concerning — years have been available. SOC 2 absence is a choice or a programme failure. |
| **Aging** | Accumulating path-dependency; legacy systems constrain modernisation. Gaps suggest accepted obsolescence or under-investment. |
| **Unknown** | Cannot assess lifecycle risk. Request incorporation evidence directly. |

### Key-person risk

A **flag with a stated basis**, never a score: headcount ≤ **10** (observed via Wikidata) in a
**high-criticality** relationship. Deliberately weak — headcount is a *scale* proxy, not a
*concentration* measure, and internal dependency concentration is not externally observable.

### Technology obsolescence framing

Re-labels findings the engine **already charged for** (`tls_version`, `kev_listed_cve`) as
path-dependency context, adding no arithmetic. The same finding is described differently by age:
TLS 1.0 on a 2-year-old vendor is a configuration decision fixable by config change; on a
20-year-old vendor it is likely path-dependency that may require system replacement. Deduplicated
per unique `(signal, band_key)` so the UI does not repeat itself.

> **Correction to earlier documentation.** The funding-stage model (Seed / Series A/B / Series C+ /
> IPO), employee-count stages, product-maturity stages and market-presence tiers described
> previously are **not implemented** and have no collector behind them. `LifecycleStage` is the
> Adizes five-stage vocabulary above.

---

## Metric relationships

### Posture ↔ Confidence
Different questions: how strong are the controls, versus how much of the expected evidence we
found. High posture with low confidence means clean *observable* controls on thin evidence — common
for young vendors. **A bare posture is unrepresentable; never publish one without its confidence.**
Confidence acts on posture in one direction only: as a **ceiling**, never as a deduction.

### Posture ↔ Business Stability
Orthogonal by construction. Business Stability signals are excluded from **both sides** of the
posture coverage ratio, and the two context categories cannot penalise. A vendor can be sound and
exposed, or impaired and well-controlled.

### Posture ↔ Assurity
Complementary: implementation versus independent verification. Assurity credit can **never** buy
back posture lost to a real finding. Keeping them apart is what stops assurance theatre from
becoming a security score.

### Longevity → everything except Posture
Foundational context. It sets the Confidence denominator, the Business Stability base and
multipliers, the benchmark cohort, and the Assurity confidence adjustment. It reaches Posture
**nowhere**.

### Business Stability ↔ Lifecycle
Strongly correlated — both are age-anchored — but lifecycle is narrative and stability is scored.
Lifecycle is what lets a reader interpret a stability score in context rather than as a verdict.

---

## Key principles

1. **Never mix axes.** Each answers a different question; none may influence another's arithmetic.
2. **Missing data reduces Confidence, never Posture.** Enforced by the fixed divisor, not by
   convention.
3. **Absence of evidence is not evidence of failure.** Not holding a certification is not a
   finding. Only an *asserted-then-failed* control is.
4. **Age-appropriate expectations.** Confidence denominators and attainability rules scale with
   profile, so the maths handles fairness rather than a special case doing it.
5. **Separate gates from scores.** Some conditions must **block**, not merely reduce: sanctions,
   ambiguous entity resolution, active insolvency, dissolution. A low score clears a threshold; a
   gate does not.
6. **Insufficient evidence is adverse, not neutral.** A supplier nobody can see is a supplier
   nobody has checked.
7. **No vendor context reaches the posture arithmetic.** Sector, revenue, headcount, country,
   ownership and age are all out. The same evidence must score the same way for everyone, or
   comparability is gone.
8. **Judgement is labelled as judgement.** The severity ladder, the aggregation decay and the
   divisor are expert judgement. They are defensible and reviewable; they are not calibrated
   against outcomes, and nothing may present them as though they were.

---

## API endpoints

**Posture and confidence**
- `GET /api/vendors/{ref}` — the published Score (posture, grade, confidence, categories)
- `GET /api/vendors/{ref}/confidence` — confidence breakdown with deduction labels
- `GET /api/vendors/{ref}/coverage` — evidence coverage analysis
- `GET /api/vendors/{ref}/history` — prior scores
- `GET /api/vendors/{ref}/findings`, `/evidence`, `/evidence/{evidence_id}` — the receipts

**Business stability and continuity**
- `GET /api/vendors/{ref}/stability` — score, standing, penalties, bonuses, gate status
- `GET /api/vendors/{ref}/financial` — raw financial profile
- `GET /api/vendors/{ref}/continuity` — registry facts and going-concern status

**Assurity**
- `GET /api/vendors/{ref}/assurity` — score, inputs, gap penalty, caveats
- `GET /api/vendors/{ref}/evidence-request-pack` — what to ask the vendor for

**Longevity and lifecycle**
- `GET /api/vendors/{ref}/lifecycle` — stage, key-person flag, obsolescence framing
- `GET /api/vendors/{ref}/profile` — operating years, age band, size band

**Scoring**
- `POST /api/vendors/score` · `POST /api/vendors/{ref}/rescore` — 202 + job id
- `GET /api/jobs/{job_id}` · `GET /api/jobs/{job_id}/stream`

---

## Summary

| Metric | Range | Aggregation | Age's role |
|---|---|---|---|
| **Posture** | 0–100, A–F | `100 − Σ capped penalties / 2.86`, with rank decay 0.7 | **none** |
| **Confidence** | 0–1 | `Σ w(expected ∧ found) / Σ w(expected)` | sets the denominator |
| **Business Stability** | 0–100 or gated | base − penalties + bonuses, age-multiplied | base score + multipliers |
| **Assurity** | 23–97 | `100 × σ(−1.2 + Σ credits − 0.8·gaps)` | confidence only |
| **Longevity** | bands + 0–1 index | `ln(1+y)/ln(26)`, discounted by source | is the metric |
| **Lifecycle** | 5 Adizes stages | none — narrative only | is the metric |

Each axis is computed independently by a method appropriate to what it measures, and they are
reported side by side rather than blended. The age-based differentiation makes the treatment of
young and small vendors fair *by construction* — through what is expected of them, not through a
penalty applied and then apologised for.

### Open items flagged by this review

1. `business_stability.age_base_scores` / `confidence_adjustments` in `scoring.yaml` are **inert** —
   the runtime reads `longevity.py`. One of the two must be deleted or wired.
2. A clean startup scores **20 / "ceased"** on Business Stability. The standing vocabulary and the
   base curve need to be reconciled.
3. Four declared financial penalties (`voluntary_arrangement`, `declining_profitability`,
   `high_customer_concentration`, `no_recent_funding_18_months`) are **not wired**.
4. Several `age_risk_factors` inputs are passed as placeholders from `business_stability.py`
   (`finding_count=0`, leadership, media, structural-change fields) — the profile currently reports
   on defaults rather than observations.
5. `calculate_from_profile` passes `sector` as `jurisdiction`.
6. `docs/methodology.md` §"Age-based base scores" documents the inert YAML values (base 70) and
   should be corrected alongside this file.
