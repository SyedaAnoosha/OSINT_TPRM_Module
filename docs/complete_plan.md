# Complete Plan — OSINT Third-Party Risk Assessment

**Supersedes as the integrating document:** [report.md](report.md) (research) · [migration-plan.md](migration-plan.md) + [step_by_step_mig_plan.md](step_by_step_mig_plan.md) (engine) · [tprm-module-plan.md](tprm-module-plan.md) (product) · [new_add.md](../new_add.md) (summary)
**Baseline verified against the working tree:** 2026-07-30 · `scoring.yaml` v4.2.0 · `benchmarks.yaml` v1.0.0 · **417 passed, 15 failed**

---

## How this document is organised, and why

The research asked *"how do we calculate a technically correct security posture score?"* and answered it well. But a posture score is **one component of a supplier decision**, not the decision itself.

This plan is therefore organised around the buyer, not the model:

| Part | Question it answers |
|---|---|
| **I** | What does the customer actually need to decide? |
| **II** | What outputs serve that decision, and what must never contaminate them? |
| **III** | What is built, what is measured, what is missing? |
| **IV** | Engine work — making the score correct |
| **V** | Product work — making the score *usable* |
| **VI** | Sequencing both workstreams |
| **VII** | Governance, anti-patterns, and the lines we do not cross |

The scoring engine appears in Part IV. It is important, but it arrives fourth for a reason.

---

# Part I · The customer decision

## I.1 Two audiences, one dataset

A supplier onboarding is a cross-functional decision. Two groups consume the output and they want different things.

| Audience | Mandate | What they need |
|---|---|---|
| **Security / Cyber Risk** | *"Will they lose our data?"* | Findings, evidence receipts, remediation asks, recheck cadence, per-signal peer comparison |
| **Procurement / Supply Chain** | *"Will they disrupt our business?"* | A decision, contract conditions, monitoring cadence, concentration exposure, exit position, and **what we could not see** |

The current system serves the first audience well and the second barely — **not because the data is missing, but because it was built as engine features and never assembled into an audience view.**

## I.2 The seven questions asked before signature

Mapped to what we can actually answer.

| # | Question | OSINT answer | Where it lands |
|---|---|:--|---|
| 1 | Who are we contracting with — is this the right legal entity? | **Full** | Entity resolution + gate |
| 2 | Are they sanctioned or otherwise barred? | **Full** | Sanctions gate |
| 3 | Will they still exist through the contract term? | **Partial** — registry facts only | Continuity flags |
| 4 | Can they protect our data? | **Partial** — external evidence only | Posture + Confidence |
| 5 | Do their claims match observed reality? | **Full** | Compliance Gap |
| 6 | Who do *they* depend on, and where is our concentration? | **Partial** — Tier-2 only | Fourth-party + portfolio |
| 7 | If they fail, what happens to us? | **Weak** | Inherent Tier + exit view |

## I.3 What OSINT cannot answer — and why publishing that is the product

Roughly **40%** of an onboarding decision is externally observable. *(This is a considered estimate from mapping collectors against TPRM domains, not a computed figure — use it for internal positioning, not as a published metric.)*

**Structurally unobservable, always:** internal access controls and MFA enforcement · BCP/DR testing evidence, RTO/RPO · insurance coverage and limits · contract history and DPA terms · Tier-3+ supply chain · employee security training.

**Unobservable today, source-limited:** litigation (no free authoritative source) · credential/dark-web exposure (HIBP domain API is paid) · ESG and modern slavery (pending data licence).

The honest positioning that follows:

> **"We tell you what is true from outside, we tell you what we could not see, and we generate the exact questions to ask about the rest."**

That is a *complete* contribution to the decision. A product covering 40% while implying 100% is not.

---

# Part II · The architecture

## II.1 The layered model

The mainstream TPRM design — and the one the research independently reached — separates who the vendor *is* from how well they *manage risk*, and combines them only at the end.

```
LAYER 1  INHERENT RISK  ── who they are, what we exposed to them
         (buyer-supplied: data held, integration depth, criticality, substitutability)
         updates rarely
                 │
LAYER 2  CONTROL POSTURE ── how well they manage it
         Posture 0-100 · Confidence 0-1 · Assurity 0-100 · Continuity flags
         refreshes continuously
                 │
         ── GATES bypass both entirely ──
                 │
LAYER 3  RESIDUAL RISK ── derived matrix view, the procurement decision
```

**Keeping the two layers on different clocks is half the reason for separating them.** Any design that multiplies posture penalties by firmographic bands has collapsed them back into one.

## II.2 Every published output

**Only one new 0–100 score is being added.** The distinction is load-bearing: calling a flag set or a lookup table a "score" implies a measurement that was never made.

| Output | Type | Audience | Status |
|---|---|---|---|
| **Posture** | 0–100 score | Security | Exists |
| **Confidence** | 0–1 + band | Both | Exists |
| **Assurity** | **0–100 score** | Both | **New** |
| **Expectation Gap** | Signed delta + narrative | Both | New — output, not score |
| **Compliance Gap** | Finding class | Security | New — findings, not a number |
| **Inherent Risk Tier** | Tier (Low → Critical) | Procurement | New — buyer-side |
| **Continuity** | Registry-cited flags | Procurement | New — deliberately *not* 0–100 |
| **Residual Risk** | Derived matrix view | Procurement | New — decision aid, not a measurement |
| **Coverage statement** | Prose | Procurement | New |
| **Concentration** | Portfolio view | Procurement | Half built |
| **Evidence Request Pack** | Generated questionnaire | Both | New |

### Residual Risk matrix

| Posture ↓ / Inherent → | Low | Medium | High | Critical |
|---|---|---|---|---|
| **Strong (80–100)** | Low | Low-Med | Medium | Med-High |
| **Moderate (60–79)** | Low-Med | Medium | High | High |
| **Weak (40–59)** | Medium | High | High | Critical |
| **Poor (< 40)** | Med-High | High | Critical | Critical |

High-Inherent + Strong-Posture still lands at Medium: inherent exposure does not disappear because the controls look good.

**The matrix is a deterministic lookup over two independently disputable inputs.** Publish it that way. A vendor or an internal stakeholder will still argue about the resulting cell — that is normal and healthy — but the argument resolves by re-examining the Posture evidence or the Tier assignment, each of which has its own dispute path. The cell itself carries no independent judgement to contest.

### Why Continuity is flags, not a score

1. The research establishes these signals must *leave* Posture; it does not specify an arithmetic to replace them. A score would be invention wearing the report's authority.
2. Four registry bands cannot support hundred-point precision.
3. A cited register fact carries the same legal footing as any other published observation. A **derived** distress index is credit-rating territory and defamation-adjacent when wrong.

> *"In administration — Companies House company status, retrieved 2026-07-29."*

## II.3 The research answer — where firmographics go

> **"Should external security signals be interpreted differently by company type, age, revenue, headcount, market cap?"**
> **No.**

Signal importance varies with **measured exposure** (a denominator), and consequence varies with the **buyer's engagement**. The intuition that *"a $5B bank with no DMARC is more negligent than a $500K startup"* is a statement about **culpability, not probability** — and mixing culpability into the arithmetic destroys cross-vendor comparability.

**The routing rule.** Every firmographic and financial marker passes this test, **in order**:

1. Does it change the technical probability of **compromise**? → stays in / affects **Posture**. *Almost nothing qualifies — this gate is meant to be near-empty.*
2. Does it change the probability the vendor **remains a viable counterparty**? → **Continuity flags**
3. Does it change how much we trust our **data**? → **Confidence multiplier**
4. Does it help compare against **fair peers**? → **Expectation Gap / cohort**
5. None of the above? → **Discard.** It is firmographic bias seeking a side door.

> **Why step 1 and step 2 are separate questions.** Going-concern signals — insolvency, administration, entity dissolution — do **not** change the probability of technical compromise. They change the probability the vendor is still there to operate the controls at all. Collapsing the two is exactly how continuity ended up inside Posture in the first place.

| Factor | Collected? | Touches Posture today? | Destination |
|---|:--|:--|---|
| Company type (sector) | Yes | **Yes** — `industry_profiles` | Compliance Gap + cohort |
| Age | Yes | **Yes** — 2 paths, 6 pts | **Primary:** Assurity `attainable_after_years` + cohort. **Secondary, narrow:** see below |
| Revenue | Yes | No | Cohort only |
| Headcount | Yes | No | Cohort only |
| Market cap | **No — not collected** | No | `listed_on` → Confidence ×0.6 |
| Public vs private | Yes — **collected, unused** | No | **Confidence** — the disclosure-regime effect |

**On age and Confidence.** The engine keys its assurance multiplier to `entity_maturity` (bounded 0.96–1.04). Retain it, but treat it as the **weakest** of age's three homes: "old company" is a soft proxy for "well-evidenced". The strong disclosure-regime effect comes from `listed_on` — a public company is bound by SEC Item 1.05 four-day breach disclosure and a private one is not, so *"no breach news"* is materially weaker evidence for a private firm. Prefer the regime signal over the age signal wherever both are available.

Revenue and headcount exclusion is **structurally enforced**: the `firmographics` and `pdl` collectors emit zero findings, and `test_profile_never_moves_a_score` requires a byte-identical `Score` with and without a full firmographic payload.

---

# Part III · What is built, measured, and missing

## III.1 Lifecycle coverage — the gap is assembly, not construction

Verified across 26 API endpoints.

| Stage | Status | Where |
|---|:--|---|
| Inherent risk tiering | ⚠️ Partial | `criticality` collected; sets only a `high_stakes` boolean |
| Screening / dealbreakers | ✅ | Sanctions + entity-ambiguity gates, adjudication queue |
| Due diligence | ✅ | Full pipeline, 27 signals, evidence-before-scoring |
| Decision | ✅ | `recommend.py` rule table + `POST /decisions` |
| **Contracting** | ❌ | No flow-down output |
| Ongoing monitoring | ✅ | `monitor.py`, `/benchmark-history` |
| Issue management | ✅ | Disputes + adjudication |
| **Offboarding / exit** | ❌ | Nothing |
| Portfolio view | ✅ | `/api/portfolio` |

**The "composite score fallacy" critique does not land here.** Gates already bypass arithmetic, Confidence is already separate, portfolio drill-down already exists.

## III.2 The measured baseline

```
version 4.2.0 · 27 signals · 57 penalising bands · penalty_divisor 4.0 (NOT 7)
severity: critical 40 · high 20 · medium 8 · low 3
ceiling 49 · refuse_below 0.4 · min_cohort_n 1 (yaml) / 8 (code default)
```

**The frozen corpus — 5 vendors, all large, all A/B:**

| Vendor | Posture | Grade | Conf | Footprint penalty |
|---|--:|:--:|--:|--:|
| atlassian | 82 | B | 0.963 | 26.0 |
| myob | 86 | A | 0.926 | 26.0 |
| onetrust | 86 | A | 0.963 | 26.0 |
| slack | 84 | B | 0.926 | 19.0 |
| snowflake | 76 | B | 0.926 | 31.0 |

## III.3 Signal discrimination — measured 2026-07-30, no labels required

A signal that does not vary across the population cannot rank anything.

**Six signals penalise 100% of the corpus** — every vendor, every run:

| Signal | Bands seen | Minimum charged |
|---|---|--:|
| `stale_hosts` | `many`×4 · `some`×1 | 8 |
| `contactability` | `none_published`×5 | 8 |
| `weak_issuance` | `wildcard_sprawl`×5 | 3 |
| `subdomain_estate` | `medium`×3 · `large`×2 | 3 |
| `cert_posture` | `claimed_unverified`×4 · `none_claimed`×1 | 3 |
| `vd_program` | `security_txt_only`×3 · `none`×2 | 3 |

That is **≥28 category-points every vendor pays regardless — about 7 posture points of pure flat tax.** It shifts the intercept; it does not measure risk.

**Twelve signals are constant-pass:** `tls_version` `cert_validity` `hsts` `x_frame_opts` `dmarc` `dkim` `breach_by_data_class` `domain_registration` `entity_existence` `regulator_action` `program_disclosure` `reporting_posture`.

**One signal never fires at all:** `entity_maturity` — which is *also* the Confidence assurance signal, so that mechanism is inert in practice.

**So 19 of 27 signals contribute nothing to ordering in this sample.** Only eight discriminate: `kev_listed_cve` `nvd_cve` `spf` `csp` `dnssec` `caa` `security_txt` `entity_status`.

> ⚠️ **Two consequences for Phase 1d.** `vd_program` and `cert_posture` both penalise everyone — so the Transparency category's only surviving penalising signal is a flat tax, and `cert_posture` leaves for Assurity anyway. Re-run this analysis on the seeded pool **before** fixing the category boundaries.

**Caveat: five large tech vendors is not a population.** The method scales directly to the 115-vendor seed list and should be run there first — it needs no outcome labels and is roughly a day's work.

## III.4 The honest domain coverage

| Domain | Coverage | Source |
|---|:--|---|
| External attack surface · breach history · KEV/CVE · email auth · sanctions · entity standing | **High** | Built |
| Certification claims · regulator actions · adverse media · fourth-party (Tier-2) | Moderate | Built |
| Internal controls · BCP/DR · insurance · contract terms · Tier-3+ | **None** | Requires vendor |
| Litigation · credential exposure · ESG | **None** | HELD — source-limited |

---

# Part IV · Engine work — making the score correct

Full runbook in [step_by_step_mig_plan.md](step_by_step_mig_plan.md). Summarised here.

## IV.1 The ordering rule

> **Relocate before you re-weight, and re-weight before you re-shape.**

## IV.2 Phases

| Phase | What | Weeks | Changes scores |
|---|---|--:|:--|
| **0** | Instrument: git, fix 15 red tests, build outcome labels, extend corpus, run discrimination analysis | 2–3 | no |
| **1a** | Delete `industry_profiles` severity promotions | 1 | ≈0 on corpus |
| **1b-i** | Stop penalising low-base-rate signals (park at `informational`) | 1–2 | yes |
| **1c** | Merge `contactability` into `security_txt` | 0.5 | yes |
| **5e** | **Continuity relocation** — move `business_financial_stability` out of Posture | 1 | yes |
| **1d** | **Category consolidation + divisor recalibration** | 1–2 | yes, everywhere |
| **2A** | `stale_hosts ÷ subdomain_estate` — the one denominator that already exists | 1 | yes |
| **2B** | Collector fan-out — TLS/headers probe **one host** today | 6–10 | substantially |
| **3** | Aggregation: λ=0.7 diminishing returns **+** widened ladder, shipped together | 2–3 | yes |
| **4** | Gates | 1 | no — changes outcomes |
| **5a/b** | Assurity, Compliance Gap | 3–4 | no |
| **1b-ii** | Positive credit (blocked on 5a) | 0.5 | no |
| **5c/d** | Expectation Gap, Impact Tier | 2 | no |
| **6** | Real cohorts | ongoing | no |
| **7** | Bounded log-odds | 3–4 | substantially |

## IV.3 The five corrections that matter most

1. **`penalty_divisor` is 4.0, not 7.** Every "N points" figure in the research is a *category* penalty. Divide by 4 for posture impact.
2. **The Phase 2 denominator exists for 1 of 10 signals, not "most".** TLS and headers collectors probe a single host. Hence the 2A/2B split — and 2B is a 6–10 week programme, not a 3-week phase.
3. **Phase 0's ablation is not executable.** No outcome labels exist anywhere. Label acquisition is the real prerequisite.
4. **There is no bonus mechanism in the engine.** Assurity must ship *before* reclassified signals can be credited — the dependency runs opposite to the original plan.
5. **3a and 3b must ship together.** Computed: 3a alone reaches 1.78:1 against one Critical; both together reach 3.06:1.

## IV.4 The divisor derivation (Phase 1d)

Category consolidation without this silently re-scores everyone:

```
divisor(n) = n × (4 / 7)     # holds max damage at 175 posture points
```

| Categories | Divisor | Floors at |
|--:|--:|--:|
| 7 (today) | 4.00 | 0 |
| 5 (target) | **2.86** | 0 |
| 3 with divisor left at 4.0 | 4.00 | **25** ✗ |

## IV.5 Target category set — all 27 signals accounted for

| Category | Signals | n |
|---|---|--:|
| Breach & Compromise | `breach_by_data_class` `kev_listed_cve` `nvd_cve` | 3 |
| Attack Surface & Hygiene | `tls_version` `cert_validity` `hsts` `csp` `x_frame_opts` `stale_hosts` `weak_issuance` | 7 |
| Identity & Email | `dmarc` `spf` `dkim` | 3 |
| Transparency | `vd_program` `security_txt` | 2 |
| Regulatory | `regulator_action` | 1 |

**16 scored · 1 denominator (`subdomain_estate`) · 2 informational (`dnssec`, `caa`) · 8 relocated = 27.** Verified: nothing unaccounted, nothing invented.

⚠️ **No signal may appear in two categories** — the engine keys on `(category, signal)` and would charge it twice.

⚠️ **Every category must retain at least one penalising band, or the divisor moves again.** Two are fragile:

| Category | Risk | Consequence |
|---|---|---|
| **Transparency** | `security_txt` goes `informational` in 1b-i, leaving only `vd_program` — which penalises **100% of the corpus** and is itself a reclassification candidate | If `vd_program` also relocates, Transparency has zero penalising bands and is a constant, not a category |
| **Regulatory** | `regulator_action` awaits the cyber / non-cyber decision. If it relocates, the category disappears | Posture drops to 4 categories |

**Assert the count at load and re-derive the divisor in the same commit.** Dropping silently from 5 → 4 → 3 while the divisor stays at 2.86 makes the model progressively more forgiving with no one noticing.

---

# Part V · Product work — making the score usable

Full detail in [tprm-module-plan.md](tprm-module-plan.md). **Nothing here touches Posture arithmetic, so this runs fully parallel to Part IV.**

| # | Gap | Effort | Why |
|---|---|--:|---|
| **1** | **Fourth-party concentration** | days | `/api/portfolio` and `fourth_party.py` both exist; **nothing joins them**. CPS 230 in force since 1 Jul 2026 |
| **2** | **Coverage statement** | days | "What we could not see" — increases credibility, protects legally |
| **3** | **Evidence Request Pack** | 1–2 wks | 58 `ask_of_vendor` + `accepts_as_refute` pairs already written and unused |
| **4** | Tier → assessment depth + cadence | 1–2 wks | Makes tiering operational; saves free-API budget |
| **5** | Contract flow-downs | 1–2 wks | Speaks procurement's language directly |
| **6** | Two audience views | 2 wks | Packaging, not new data |
| **7** | Status-page collector | 2–3 wks | Only free unread domain → Continuity |
| **8** | Exit / substitutability | 1 wk | Procurement always asks |

## V.1 The differentiator: Evidence Request Pack

`scoring.yaml` carries 58 `ask_of_vendor` + 58 `accepts_as_refute` + 58 `recheck_after` entries — one per penalising band.

| | SIG Lite | Evidence Request Pack |
|---|---|---|
| Questions | ~300, fixed | **Only what was observed failing** |
| Basis | Generic | Cited to a finding + evidence id |
| Resolution | Manual | Evidence standard stated up front |
| Closure | Email thread | Dispute → `nullify`/`mitigate` → re-score with reason recorded |

This is the **outside-in triggers inside-out** loop every framework describes, and it is ~80% built.

## V.2 The two views

**Security:** findings by effective penalty · evidence receipts · category drill-down · per-signal peer comparison · remediation asks · recheck cadence · dispute status.

**Procurement:** decision → Residual Risk → Continuity flags → concentration → contract conditions → monitoring cadence → coverage statement → Evidence Request Pack.

Same immutable score object underneath. `/export` and `/summary` are the rendering seam.

---

# Part VI · Sequencing both workstreams

```
ENGINE (Part IV)                          PRODUCT (Part V)
─────────────────────────────             ─────────────────────────────
Phase 0  Instrument + labels              Gap 1  4th-party concentration  ← START NOW
     │                                    Gap 2  Coverage statement       ← START NOW
     ▼                                    Gap 3  Evidence Request Pack    ← START NOW
Phase 1a delete industry_profiles              │
     ▼                                         ▼
Phase 1b-i stop penalising ─► 1c          Gap 5  Contract flow-downs
     ▼                                         │
Phase 5e Continuity relocation                 │
     ▼                                         │
Phase 1d Categories + divisor  ◄───────────────┤
     ▼                                    Gap 4  Tier → depth (needs 5d)
Phase 2A denominators                          │
     ▼                                    Gap 7  Status pages (needs 5e)
Phase 3  Aggregation 3a+3b                     │
     ▼                                         ▼
Phase 2B collector fan-out                Gap 6  Two audience views
     ▼
Phase 6 real cohorts ─► 5c Expectation Gap
     ▼
Phase 7 log-odds
```

### Hard dependencies — none of these are soft orderings

| Dependency | Why it is hard |
|---|---|
| **1a → 1b-i** | `_validate_industry_profiles` requires promoted bands to *be* penalising. Reverse the order and the loader refuses to start |
| **1b-i + 5e → 1d** | 1d consolidates categories that 1b-i and 5e empty. Running it first consolidates the wrong set — **treat as blocking, not preferred** |
| **1d → 2A and 3** | Both operate *inside* a category boundary. Landing boundaries first means one re-golden instead of three |
| **5a → 1b-ii** | No bonus mechanism exists until Assurity does |
| **6 → 5c and 7** | No trustworthy `L_peer` without real cohorts |
| **Phase 0 git → everything** | `regolden` diffs are the evidence for every later phase |

**Document drift is a live risk.** Phases 1d and 5e exist in [step_by_step_mig_plan.md](step_by_step_mig_plan.md) and here. Any change to their scope or dependencies must land in both, or the runbook and the governing plan disagree about execution order.

**Product items 1–3 are ~3 weeks and depend on nothing.** They should start immediately and in parallel — they move this from "security rating" to "TPRM module" faster than any engine phase.

**Engine critical path:** 0 → 1a → 1b-i → 5e → 1d → 2A → 3, roughly **10–14 weeks**.

## VI.1 Ship this sprint, regardless of everything else

1. **`git init`.** The repo is not under version control. Every phase's evidence is a `regolden` diff that cannot currently be read.
2. **The `n=6` disclosure defect.** Synthetic peers `[65,72,78,83,89,94]` are reported as `n=6` beside "Industry Reference Baseline". A reader sees six real companies. The `is_synthetic` flag already exists — consume it.
3. **The 15 red tests.** Migrating on a red suite means a new break is indistinguishable from an old one.

---

# Part VII · Governance and the lines we do not cross

## VII.1 Invariants — a change that breaks one is out of scope

| Invariant | Enforced at |
|---|---|
| Posture and Confidence never collapse into one number | `engine.py` — separate `Score` fields |
| Missing data reduces Confidence, never Posture | Fixed divisor, `engine.py:187` |
| Evidence stored before scoring | `pipeline.py:145` precedes scoring at 186 |
| Every penalising band has a reason + action + recheck date | Loader **refuses to start** otherwise |
| No natural-person data | `excluded_signals` — §4.2 bright line |
| Ongoing findings never decay | `modifiers.age.never_decays` |
| Disclosed-never-scored | Fourth parties, concentration, coverage gaps are context |
| Frozen corpus moves deliberately | `python -m tests.regolden` |

## VII.2 Anti-patterns — recorded so they are not re-proposed each quarter

1. **Ability-to-pay bias.** *Currently violated:* `cert_posture.none_claimed` costs 8 points and fires on 5 of 5 corpus vendors.
2. **Context multipliers on penalties** (*"×1.5 large, ×0.6 startup"*). Rejected on five grounds. The anomaly is real and belongs to the Expectation Gap.
3. **Suspending penalties after M&A.** Dynamic severity adjustment wearing a hat. Gameable.
4. **Reweighting absence-of-evidence for regulated firms.** A sector promotion entering through the confidence door.
5. **Financial distress as a cyber proxy.** Separate vectors, separate axes.
6. **Category weights** (*"Cyber 30–35%…"*). §5.6 deleted them. Percentages look principled and are unfalsifiable.
7. **Natural-person signals.** Employee sentiment, key-person dependency, leadership controversies, diversity data — §4.2, and observability-biased.
8. **Customer review corpora.** A reputation axis built on review volume is a size classifier wearing a halo.
9. **Numeric Continuity score.** Four registry bands cannot support 0–100 precision.
10. **Residual Risk as a measured axis.** It is a lookup over two published inputs.

## VII.3 Not building, and why

| Proposal | Why not |
|---|---|
| Firmographic severity multipliers | Rejected on five independent grounds |
| Baseline maturity curves as f(age) | No published evidence. **Currently violated** by `entity_maturity` — Phase 5e fixes it |
| Geography/nationality adjustment in Posture | Weakly predictive, ethically fraught, legally exposed |
| Cross-tenant peer pooling | Contractual question before an engineering one |
| Commercial benchmark import (Bitsight/SSC) | Imports their observability bias — the thing this model exists to remove |
| Homomorphic encryption / SMPC / differential privacy | `min_cohort_n` is 1 and the corpus is 5 vendors. Years premature |
| "Minimum n=30 for percentiles" | Unreachable across 120 cohort cells with 115 seeds. Keep 8, disclose `n` |
| Monte Carlo / Bayesian / ML anomaly detection | No outcome labels exist |
| 300-control framework mapping matrix | For questionnaire systems; we observe from outside |
| Snowflake / Databricks / Tableau | Cargo cult at this scale |
| "Supplier Trust Dossier" | A product for a company *being assessed* — different customer |
| Probing non-public endpoints | Spends the legal position the TLS collector depends on |

## VII.4 Obligations that attach as you go

| Trigger | Obligation |
|---|---|
| Phase 1 changes what signals cost | Notice **before** the change |
| Phase 1c / 5e move `planned_signal_count` | Confidence shifts for no evidential reason. Disclose, or ship per-axis confidence |
| Phase 2 introduces a denominator | **Publish it**, with sampling rule and multi-tenant exclusions |
| Phase 1d changes categories + divisor | The largest single re-score in the plan. Version and give notice |
| Phase 3 changes the ladder | Label expert-set severities *expert judgment until calibrated* |
| Phase 5c publishes cohort placement | Make cohort assignment **disputable** |
| Continuity publishes going-concern facts | Registry-cited only. A derived distress index is credit-rating territory |
| Phase 7 changes the scale's meaning | New version, notice period, side-by-side publication |

**Scheduled change to record now:** CA/Browser Forum Ballot SC-081v3 compresses certificate lifetimes to 100 days from **March 2027** and 47 days from **March 2029**. An expired certificate stops meaning "someone forgot" and starts meaning "no lifecycle automation." `cert_validity` is the only ceiling-arming signal, so this reaches further than it looks.

## VII.5 Validation

| Test | Needs labels? |
|---|:--|
| **Signal discrimination / variance** across the seeded pool | **No — run first** |
| Construct validity (does the signal measure its name?) | No |
| Measurement accuracy (spot-check, inter-source agreement) | No |
| Base-rate validation against own population | No |
| Negative controls (a signal that must not predict) | No |
| Gaming cost per signal | No |
| Monotonicity — remediation never loses points | No |
| Firmographics-only ablation | **Yes** |
| Within-cohort discrimination, never pooled | **Yes** |
| Calibration, not just ranking | **Yes** |

**The corpus is 5 vendors, all large, all A/B.** It cannot see a regression affecting small vendors, low scorers, or Ghosts. Extend it in Phase 0 with at least one Ghost, one gated vendor, one small vendor, one bottom-quartile scorer.

---

## The plan in one page

**For the customer:** a supplier decision needs identity, sanctions, viability, data protection, claim reliability, concentration, and failure consequence. We answer roughly 40% of that from public evidence, say so explicitly, and generate the questions for the rest.

**For the engine:** Posture measures observable technical security and nothing else. Firmographics route to cohort, confidence and tiering — never to a penalty. Fix the denominator, fix the aggregation, fix the categories, fix the divisor.

**For the product:** join the two halves of concentration, generate the evidence pack, publish the coverage statement. Three weeks, no engine dependency, and it is the difference between a security rating and a TPRM module.

**The one-line summary:** *the score is a component, not the product.*
