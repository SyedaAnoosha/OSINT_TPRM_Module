# Migration Plan — from `scoring.yaml` v4.2.0 to the revised model

**Derived from:** [report.md](report.md) Parts VI–X, mapped onto the actual codebase.
**Baseline:** `scoring.yaml` v4.2.0 · `benchmarks.yaml` v1.0.0 · 417 tests passing, 15 pre-existing failures
**Date:** July 2026

---

## How to read this plan

Seven phases. **Phases 0–3 change published scores; Phases 4–6 add outputs beside them.** Each phase states its goal, the files it touches, its exit criteria, and what would make you stop and reconsider.

The ordering is not arbitrary. It follows one rule:

> **Relocate before you re-weight, and re-weight before you re-shape.**

Moving a signal out of Posture (Phase 1) is reversible and independently valuable. Changing the arithmetic (Phases 2–3) is neither, and is far easier to validate once the signals that shouldn't have been there are gone.

---

## The invariants — what must not change in any phase

These are the properties the report credits as *"better than most commercial security ratings"*. Every phase below is designed around them, and a change that breaks one is out of scope regardless of its other merits.

| Invariant | Where it lives | Why it is load-bearing |
|---|---|---|
| Posture and Confidence never collapse into one number | `engine.py`, `models.Score` | Structurally solves the observability bias that corrupts single-axis ratings |
| Missing data reduces Confidence, never Posture | Fixed divisor in `engine.py:187` | Arithmetic, not a promise — a silent source cannot move the denominator |
| Evidence stored before scoring | `pipeline.py` | The audit trail is what makes a score disputable |
| Every penalising band has a plain-English reason, enforced at load | `scoring_config.py` validation | 57 bands currently covered; the loader refuses to start otherwise |
| No natural-person data | `excluded_signals` | §4.2 bright line — APP 10, privacy tort, EU AI Act Art 6(3) |
| Ongoing findings never decay | `modifiers.age.never_decays` | Closes the "wait out the finding" loophole. **Rare and correct** |
| The frozen regression corpus stays green or moves deliberately | `backend/tests/fixtures`, `python -m tests.regolden` | The one artefact that makes every phase below falsifiable |

---

## Phase 0 · Instrument before changing anything

**Duration:** 1–2 weeks · **Risk:** none · **Changes scores:** no

You cannot demonstrate improvement without a baseline, and the report's single most important test is one you want to run *while the model is still broken* so the "after" has something to beat.

### Tasks

1. **Run the firmographics-only ablation.** Score every vendor in the corpus using only sector, revenue band, employee band and region — no posture signals at all. Compute AUC against whatever outcome labels you have. **Expect this to be uncomfortable**, given the missing denominator; that discomfort is the baseline.
2. **Run the mirror test** — posture-only vs full model. If firmographics add nothing measurable, that is a finding too.
3. **Record the current distribution.** Posture histogram, category-penalty shares, and the count of vendors floored at 0 or ceilinged at 49. Phase 3 is meant to move these; you need the "before".
4. **Measure how many vendors are actually affected by each planned change.** Specifically: how many have `industry_profiles` promotions firing, how many have ISO/SOC findings, how many would gain a denominator.
5. **Fix the 15 pre-existing test failures, or explicitly accept them.** They are drift between shipped config and tests, not regressions:
   - `min_cohort_n: 1` and the synthetic-peer fallback vs. tests expecting refusal (9 failures)
   - `_derive_cohort` defaulting sector → `technology` and employee_band → `medium` vs. tests expecting no cohort (5 failures)
   - `test_actions.py` asserting **54** penalising bands where there are now **57** (1 failure)

   **Do this first.** Migrating on top of a suite with 15 known-red tests means you cannot tell a new break from an old one.

### Exit criteria

- Ablation AUC recorded, both directions
- Test suite green, or each remaining failure has a written reason
- Baseline score distribution captured and stored

### Stop and reconsider if

Firmographics-only AUC is **within a few points of the full model**. That would mean the current score is largely a size-and-sector classifier, and Phase 2 becomes urgent rather than merely important.

---

## Phase 1 · Structural relocations

**Duration:** 2–3 weeks · **Risk:** low · **Changes scores:** yes, but only by removing things that should not have been there

No arithmetic changes. Signals move out of Posture, or change direction from penalty to bonus. This is the phase with the best ratio of noise removed to risk taken.

### 1a · Delete `industry_profiles` severity promotions

The report is unambiguous: this is **mechanism #10, *dynamic severity adjustment*, rejected** — the one adjustment every commercial platform declines to implement. It also puts `scoring.yaml` in direct contradiction with `benchmarks.yaml`, which states that interpretation lives in benchmarking and never in the arithmetic. **These two files currently disagree with each other.**

- Remove the `promote` blocks from `scoring.yaml:645+`
- Remove `promote_severity()` from `scoring_config.py:249` and its call in `normalize.py:93`
- Keep `NormalizedFinding.base_severity` / `promoted_by` fields for one release so stored receipts still deserialise
- Re-point the sector expectation at the **Compliance Gap** (Phase 5) — the sector obligation is real, it just is not a severity change

### 1b · Reclassify the low-base-rate signals from penalty to bonus

Roughly a third of the signal list. **The single highest-leverage change for noise reduction.**

| Signal | Now | After | Base-rate justification |
|---|---|---|---|
| `dnssec` | `absent: low` | **bonus** | 7–18% adoption — penalising absence penalises the norm |
| `caa` | `absent: low` | **bonus** | ~1.6% at early measurement; no published breach correlation |
| `security_txt` | `absent: low` | **bonus** | <0.25% of domains; 60% point at a platform's generic contact |
| `vd_program` | `none: medium` | **bonus + footprint-scaled penalty** | The one governance signal with a causal mechanism — scale by host count, not age |
| `program_disclosure` | `none: medium` | **bonus → Assurity** | Measures go-to-market motion; NIS2 Art. 20 requires governance, not a public page |
| `contactability` | `none_published: medium` | **merge into `security_txt`** | Same fact observed three ways, currently charged three times |
| `cert_posture` | `none_claimed: medium` | **bonus → Assurity** | Penalising absence is a tax on audit budget |
| `reporting_posture` | `none: medium` | **bonus → Assurity** | Private SMBs cannot produce this signal at all |

**Watch the confidence denominator.** `planned_signal_count()` is currently **27**. Moving signals to bonus must not silently shrink it, or every vendor's confidence jumps for no evidential reason. A bonus signal is still *planned and checked* — keep it in the denominator and only change what it does to posture.

### 1c · Merge `contactability` into `security_txt`

RFC 9116's `Contact:` field, a VDP page and a published security address are usually the same fact. Under flat accumulation that fact is charged three times, quietly making Governance heavier than any deliberate weighting decision would have made it.

### Exit criteria

- Corpus re-goldened with a **written justification per moved vendor** — `python -m tests.regolden`
- `planned_signal_count()` unchanged at 27, confirmed by test
- Confidence distribution unmoved (assert it)
- Every reclassified signal still appears in the receipt, marked as a bonus rather than silently dropped

### Stop and reconsider if

Confidence moves materially. That means the denominator changed, which was not the intent.

---

## Phase 2 · Exposure normalization — **the big one**

**Duration:** 3–4 weeks · **Risk:** high · **Changes scores:** substantially, and that is the point

This is defect #2 and the report's #1 recommendation. It removes an existing bias rather than adding a new one.

### The good news, verified

**The denominator already exists in the data.** `subdomain_estate` and `stale_hosts` both carry raw counts through `_count_of()` in `normalize.py:67`. Today they are banded *independently* — `stale_hosts` is `none/some/many` at thresholds 0 and 5, so **a 900-host vendor with 6 stale hosts scores `high`, identically to a 6-host vendor with 6 stale hosts.** That is defect #2 in one line, and `stale_hosts ÷ subdomain_estate` is computable today with no new collection.

### Tasks

1. **Introduce a denominator carrier.** Findings need `D_s` (hosts checked, certs observed, endpoints tested) alongside `f_s`. Most collectors already know this; they discard it.
2. **Implement the smoothed rate** in a new `backend/app/scoring/exposure.py`:

   ```
   r̂_s = (f_s + α_s) / (D_s + α_s + β_s)          # beta-binomial posterior mean
   g_s = λ_s·r̂_s + (1 − λ_s)·min(1, f_s/κ_s)      # blend rate with an absolute floor
   ```

   The `α/β` priors stop a 1-of-1 failure reading as 100%. The `κ_s` term preserves an absolute component so a large vendor cannot dilute a genuinely severe finding to nothing.
3. **Multi-tenant detection, before computing `D_s`.** Non-negotiable — without it your best-architected SaaS vendors bottom out. Detect naming regularity, shared wildcard certificates and uniform infrastructure fingerprints, and exclude those names from both the denominator and the finding counts.
4. **Apply to the 10 Class-P signals only:** `cert_validity`, `tls_version`, cipher findings, `hsts`, `csp`, `x_frame_opts`, `nvd_cve`, `kev_listed_cve`, `stale_hosts`, `subdomain_estate`. **Class-B signals keep binary treatment** — DMARC is one decision at the apex, not a rate.
5. **Retire `count_bands`** for `stale_hosts`; it becomes a rate. `subdomain_estate` stops being scored at all and becomes the denominator.

### The test that proves it worked

```
Vendor A:   4 hosts,   2 expired certs  →  50% failure rate
Vendor B: 900 hosts,   9 expired certs  →   1% failure rate

Before:  A −16,  B −72  (B scores worse, wrongly, by ~5×)
After:   A worse than B
```

**Write this as a regression test before writing the implementation.**

### Exit criteria

- The A/B inversion test passes
- Multi-tenant vendors in the corpus no longer floor
- Corpus re-goldened with per-vendor justification
- Ablation re-run — **firmographics-only AUC should now be materially worse than the full model.** That is the proof.

### Stop and reconsider if

`D_s` is unavailable or unreliable for a signal. Better to leave that signal un-normalized and say so than to divide by a denominator you cannot defend under dispute. **Attribution error is the dominant source of vendor disputes with external ratings.**

---

## Phase 3 · Aggregation

**Duration:** 2–3 weeks · **Risk:** medium · **Changes scores:** yes

Fixes defect #1 — hygiene trivia outranking active exploitation. [report.md VIII.2](report.md#viii2-aggregation--diminishing-returns-or-log-odds) records that the sources propose two incompatible fixes.

### 3a · Diminishing returns within category — do this now

```
CategoryPenalty(c) = Σᵢ pᵢ · λ^(rankᵢ − 1)      λ = 0.7, rank by descending pᵢ
```

Twelve hygiene failures (four Medium, eight Low) drop from **56** to **≈15.9**, against one Critical KEV at 50 — the vulnerability now dominates by better than 3:1. **Correct ordering restored without introducing category weights**, which preserves the emergence principle while killing the correlated-stacking bug.

### 3b · Widen the severity ladder

| Level | Now | After | Why |
|---|--:|--:|---|
| Critical | 40 | **50** | Should approach unrecoverable alone |
| High | 20 | **20** | Unchanged |
| Medium | 8 | **6** | Slight compression reduces mid-band stacking |
| Low | 3 | **1.5** | Should be a nudge, not a lever |
| Informational | 0 | **0 → routes to Confidence** | An informational observation *is* evidence of coverage |

Critical:Low moves from **13:1 to 33:1**. At 13:1, fourteen trivia outrank one actively-exploited vulnerability.

### 3c · Root-cause deduplication

> **One remediation ticket, one penalty.** If fixing one thing clears four findings, it was one finding.

| Cluster | Rule |
|---|---|
| KEV / CVE / CVSS / EPSS | Precedence **KEV > EPSS > CVSS**. One penalty; others are modifiers |
| TLS version / ciphers | Score the protocol finding; ciphers add an increment only beyond the version |
| CSP / X-Frame-Options | `frame-ancestors` satisfies XFO. Accept either, never penalise twice |
| Subdomains / shadow assets / CT | One footprint model, several views |

### Deferred to Phase 7 — bounded log-odds

The log-odds reshape (`L̃ = c^τ·L + (1−c^τ)·L_peer`, `Posture = 100·(1−σ(L̃))`) is statistically better and solves saturation properly. It is deferred because it **requires dense cohort medians to supply `L_peer`**, and those do not exist yet — `min_cohort_n` is currently **1**, with synthetic peers standing in.

### Exit criteria

- The §VI.2 inversion is gone: one Critical KEV outranks twelve hygiene failures, asserted by test
- **Monotonicity test passes** — a vendor that remediates a finding must *never* lose points. The diminishing-returns transform is a common place to introduce a violation
- Bottom-quartile discrimination measured; note it is improved but not solved until Phase 7

---

## Phase 4 · Gates

**Duration:** 1 week · **Risk:** low · **Changes scores:** no — changes outcomes

Everything in the model is currently arithmetic, so everything is fungible. A vendor at 100 with one actively-exploited internet-facing vulnerability publishes at 60 and clears a "≥50" threshold.

Extend the existing gate machinery (`sanctions`, `entity_ambiguous`) with:

- **KEV past its CISA due date** on an internet-facing authenticated or data-bearing asset
- **Legal entity dissolved / struck off** — already a `high` severity; promote to gate
- **No valid TLS** on a data-bearing endpoint
- **Ownership or attribution unresolvable**

The `critical_ceiling` (49) stays as-is for directly-observed criticals. A gate is stronger: it emits no score at all.

### Exit criteria

- Each gate has a named basis, as the sanctions gate does
- Gated vendors route to the adjudication queue, not to a low score
- The Tier matrix ([report.md VII.8](report.md#vii8-the-new-dimensions)) drives what a gate means per criticality tier

---

## Phase 5 · Context outputs

**Duration:** 3–4 weeks · **Risk:** low · **Changes scores:** no — adds dimensions beside them

Nothing here touches Posture. This is where every firmographic the research question asked about legitimately lives.

### 5a · Assurity

Partially built already — `targets.py` and the `target_maturity` block in `benchmarks.yaml` established the pattern of positive-only, instrument-cited controls with an attainability rule. Assurity extends it:

```
Assurity = 100 · σ( A₀ + Σ_j v_j · valid_j · scope_j − Σ_k γ_k · ComplianceGap_k )
```

**Absence never subtracts.** A vendor with no certifications has low Assurity, not bad Posture. This is the single most important structural fix for demographic fairness in the model, and it is where the Phase 1b relocations land.

### 5b · Compliance Gap

Where a vendor asserts (or is bound by) framework `F` and is observed failing control `c ∈ C(F)`, emit a cited finding. *"Vendor asserts PCI DSS compliance and negotiates TLS 1.0"* is **not a more severe TLS finding** — it is a distinct, high-signal finding about the reliability of the vendor's own attestations. This is where the deleted `industry_profiles` sector expectation goes.

Gaming it means dropping the claim, which is itself informative.

### 5c · Expectation Gap

```
EG = Posture − E[Posture | cohort]
```

The widening ladder in `benchmark.py` already computes the cohort and already discloses `n` and the rung reached. **This is the answer to the entire research question** and it needs no arithmetic change:

> *"Posture 68. Median for financial services, 1,000–10,000 staff, ANZ (n=14): 87. **This vendor sits 19 points below its peer group and in the bottom decile of it.** The gap is driven by absent DMARC (95% of Fortune 500 peers have it) and by TLS 1.0 on 8 of 340 checked hosts."*

**Prerequisite:** this is only honest once cohorts are real. See Phase 6.

### 5d · Impact / Inherent Risk Tier

`criticality` is already client-supplied and already reaches `recommend.py` — it just never reaches a tier. Formalise the Tier matrix and drive review cadence and gate consequences from it.

This is the **Inherent Risk** layer — who the vendor is and what you have exposed to them, assessed before looking at a single control. It updates rarely; Posture refreshes continuously. **Residual Risk** is the published combination of the two, and is a **derived matrix view, not a dimension**: a lookup over two already-published inputs. A vendor disputes its Posture or its Tier, never the cell.

### 5e · Continuity — flags, not a score

The destination for the Class-C signals that leave Posture. `business_financial_stability` (`entity_status`, `entity_existence`, `entity_maturity`, `domain_registration`) is a *Posture* category holding going-concern facts: Companies House `liquidation`, `receivership`, `administration` and `insolvency-proceedings` all map to `entity_inactive`, **costing 20 points of technical security posture**. `entity_maturity` penalises companies under ten years old, i.e. scores by founding date — which this plan's own "does not do" table forbids. `rdap_collector` already tags `domain_registration` with `subcategory="business_continuity"`.

**This is a relocation, not a build.** The signals and collectors exist; only the destination is new.

**Publish as registry-cited flags, never as a 0–100 axis:**

> *"In administration — Companies House company status, retrieved 2026-07-29."*

Three reasons, and they are the same three the report gives:

1. The sources establish that these signals must leave Posture; they do not specify an arithmetic to replace them.
2. Four registry bands cannot support hundred-point precision.
3. A cited register fact carries the same legal footing as any other published observation. A *derived* distress index — inferred runway, a bankruptcy-risk score — is closer to credit-rating territory and defamation-adjacent when wrong.

**Financial markers route by the same discipline:** going-concern facts → Continuity flags · public-vs-private status (Wikidata `listed_on`, already collected and unused) → Confidence multiplier ≈ 0.6 · revenue and headcount bands → cohort assignment · everything else → discard. Markers with no lawful free source (funding runway, cash burn, Altman Z-score, market share, layoffs) stay in `held_roadmap` — the position `gleif_collector` already records.

**One free gap worth scoping here:** service-outage / status-page history. No collector reads it, it is genuinely public, and it is the clearest operational-resilience signal available. It belongs in Continuity, not Posture.

---

## Phase 6 · Make the cohorts real

**Duration:** ongoing · **Risk:** low · **Changes scores:** no

Phases 5c and 7 both depend on cohort medians that can be trusted. Today they cannot be.

| Issue | Current state | Target |
|---|---|---|
| `min_cohort_n` | **1** — "set to 1 for live demo/interactive use" | 8, once the pool supports it |
| Synthetic fallback | 6 hard-coded postures `[65,72,78,83,89,94]`, reported as `n=6` | Removed, or labelled so `n` cannot read as six real companies |
| Peer pool | Whatever this deployment has scored | Seeded across all 10 sectors × 4 regions × size bands |

**The disclosure defect worth fixing first, independently of everything else:** a reference-baseline card currently reports `n=6` alongside the caveat *"Industry Reference Baseline"*. A reader sees `n=6` and thinks six real companies. Either suppress `n` for synthetic cohorts or state plainly on the card that these are not real peers.

Run `python -m app.seed_cohorts --all --concurrency 2` — 115 real vendors across 10 sectors, deliberately spread across ANZ / North America / UK-EU / APAC and across size bands. **Politeness is not optional**; every collector queries someone else's free service.

---

## Phase 7 · Bounded log-odds — the destination

**Duration:** 3–4 weeks · **Risk:** medium-high · **Changes scores:** substantially · **Blocked on Phase 6**

```
z_s = w_sev(s) · a(s) · φ(s) · m(s) · g_s · κ_cat(s)
L   = L₀ + Σ_s z_s
L̃   = c^τ·L + (1 − c^τ)·L_peer          τ ≈ 1.5
Posture = 100 · (1 − σ(L̃))
```

Solves what Phase 3 only partially addresses:

- **Never floors.** Three Criticals currently reach 120 points against a 100-point scale, so a vendor with three and a vendor with fifteen both publish as 0 — all discrimination lost exactly where triage matters most.
- **Never saturates at the top.** `L₀` replaces the unjustified "start at 100" prior.
- **Makes the Ghost cliff unnecessary.** At `c = 0.3`, roughly 84% of the estimate is the cohort prior, and the report says so. **A vendor who becomes unmeasurable gets their cohort's median, not a free pass** — which removes the gaming vector entirely, because hiding stops being better than being average.

### Ghost handling — do the cheap half in Phase 3, the rest here

The **ceiling ramp** can ship early and preserves the current axiom exactly (Confidence bounds what you assert, never the arithmetic):

```
< 40%    → no publish; "Insufficient Evidence" (explicitly ADVERSE); manual review required
40–60%   → publish, ceiling 80
60–75%   → publish, ceiling 90
75–90%   → publish, ceiling 97
≥ 90%    → publish, ceiling 100
```

Both proposals agree on the governance point, and it costs nothing to do immediately: **publish "Insufficient Evidence" as an explicitly adverse state, not a neutral absence.** Procurement must not be able to read a Ghost as a pass.

---

## Sequencing and dependencies

```
Phase 0  Instrument ────────────────────────────────────────┐
              │                                             │
              ▼                                             │
Phase 1  Relocations ──────────────────────┐                │
              │                            │                │
              ▼                            ▼                │
Phase 2  Exposure denominators        Phase 5a/b  Assurity, │
              │                       Compliance Gap        │
              ▼                            │                │
Phase 3  Aggregation + ceiling ramp        │                │
              │                            │                │
              ▼                            │                │
Phase 4  Gates                             │                │
              │                            │                │
              ▼                            ▼                ▼
Phase 6  Real cohorts ─────────────► Phase 5c Expectation Gap
              │
              ▼
Phase 7  Log-odds + shrinkage
```

**Two hard dependencies:** Phase 7 needs Phase 6 (no trustworthy `L_peer` without real cohorts), and Phase 5c needs Phase 6 for the same reason. **Everything else can be resequenced** if a phase proves harder than expected.

**Phases 1, 4, 5 and 6 do not change published posture** and can run in parallel with the others if you have the hands.

---

## Validation, running throughout

Applies from Phase 2 onward, not at the end.

| Test | What it catches |
|---|---|
| **Firmographics-only ablation** | Whether you have built a security rating or a size classifier. Re-run after Phase 2 — the AUC gap should have widened |
| **Within-cohort discrimination, never pooled** | Pooled AUC is inflated by the model's ability to detect size, which correlates with disclosure probability. You would be measuring your own selection bias and reporting it as accuracy |
| **Calibration, not just ranking** | A model that orders well but calibrates badly produces risk-acceptance decisions systematically wrong in magnitude |
| **Monotonicity** | A vendor that remediates must never lose points. Phase 3's transform is where this usually breaks |
| **Stability** | Re-cohorting must not silently move published scores. Version and diff |
| **Frozen corpus** | Every phase re-goldens deliberately, with a written justification per moved vendor |

---

## Governance obligations that attach as you go

Publishing scores about other companies carries duties, and several of these phases increase them.

| Trigger | Obligation |
|---|---|
| Phase 1 changes what signals cost | **Notice before the change**, not after |
| Phase 2 introduces a denominator | Publish it. Attribution and denominator disputes will be a top-two dispute category |
| Phase 3 changes the ladder | Version it. Label expert-set severities as **expert judgment until calibrated** — most are, and that is fine if declared |
| Phase 5c publishes cohort placement | **Make cohort assignment disputable.** Misclassification is the other top-two dispute category |
| Phase 6 changes `min_cohort_n` | A cohort redefinition can move many scores overnight with no change in any vendor's behaviour. Notice and diff |

**One scheduled change to record now rather than discover as drift:** CA/Browser Forum Ballot SC-081v3 compresses maximum certificate lifetimes to 100 days from **March 2027** and 47 days from **March 2029**. As lifetimes compress, an expired certificate stops meaning "someone forgot" and starts meaning "this vendor has no certificate lifecycle automation" — a materially stronger inference. **Schedule the weight increase at both boundaries and announce it in advance.**

---

## What this plan deliberately does not do

| Not doing | Why |
|---|---|
| Firmographic severity multipliers | Rejected on five independent grounds ([report.md VII.7](report.md#vii7-the-twelve-candidate-mechanisms-scored)) |
| Cohort-scaled severity tables | Contested 3–2 across the sources ([report.md VIII.1](report.md#viii1-may-severity-be-cohort-scaled--the-sources-split-32)). The Expectation Gap expresses the same insight and keeps the score comparable. **This is the correct second choice if the Expectation Gap proves insufficient — a bare multiplier never is** |
| Baseline maturity curves as f(company age) | No published evidence. Not one of Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA or CISA scores by founding date. **Note the shipped config currently violates this** — `entity_maturity` penalises vendors under ten years old. Phase 5e is the fix |
| A numeric Continuity / financial-distress score | Four registry bands cannot support 0–100 precision, and a derived distress index is credit-rating territory — different legal exposure from a security observation. Publish cited registry flags instead (Phase 5e) |
| Residual Risk as a fifth measured axis | It is a lookup over Posture × Tier. Presenting a derived view as a measurement implies a third thing was measured when nothing was |
| Any geography or nationality adjustment in Posture | Weakly predictive, ethically fraught, legally exposed. Surface jurisdiction as a disclosed attribute instead |
| Cross-tenant peer pooling | A contractual question before an engineering one |

---

## Effort summary

| Phase | Weeks | Changes scores | Risk | Blocked by |
|---|--:|:--:|:--:|---|
| 0 · Instrument | 1–2 | no | none | — |
| 1 · Relocations | 2–3 | yes | low | 0 |
| 2 · Exposure denominators | 3–4 | **substantially** | **high** | 1 |
| 3 · Aggregation + ceiling ramp | 2–3 | yes | medium | 2 |
| 4 · Gates | 1 | no | low | — |
| 5 · Context outputs (5a–5e) | 3–4 | no | low | 1 *(5c also needs 6)* |
| 5e · Continuity relocation | 1 | **yes** — removes ~20 pts of misplaced penalty | low | 1 |
| 6 · Real cohorts | ongoing | no | low | — |
| 7 · Log-odds + shrinkage | 3–4 | **substantially** | med-high | **6** |

**Critical path: 0 → 1 → 2 → 3, roughly 8–12 weeks**, and those four phases carry most of the value. Phases 4–6 can run alongside. Phase 7 is a second release.

---

## The one-line summary per phase

| Phase | In one line |
|---|---|
| **0** | Prove what is broken before fixing it |
| **1** | Take out what should never have been in Posture |
| **2** | Stop measuring host count and start measuring hygiene |
| **3** | Stop letting a dozen missing headers outrank an actively-exploited vulnerability |
| **4** | Make the unforgivable findings unaveraged |
| **5** | Give every firmographic a legitimate home outside the score |
| **6** | Make the peer group real enough to compare against |
| **7** | Stop the scale saturating at both ends |
