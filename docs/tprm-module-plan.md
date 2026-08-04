# TPRM Module Plan — from security rating to third-party risk decision support

**Companion to:** [step_by_step_mig_plan.md](step_by_step_mig_plan.md) · **Verified against the tree on 2026-07-30**

> The migration plan fixes the **scoring engine**. This plan builds the **product around it**.
> They are independent workstreams: nothing here changes Posture arithmetic, so both can run in parallel.

---

## The reframing

Everything in the migration plan answers *"is this number right?"*. This plan answers a different question:

> **"If I were onboarding this company as a supplier, what would I want to know?"**

That question has two askers, and they want different things.

| Audience | Their mandate | What they need |
|---|---|---|
| **Security / Cyber Risk** | Will they lose our data? | Findings, evidence, remediation asks, recheck cadence, peer comparison per signal |
| **Procurement / Supply Chain** | Will they disrupt our business? | A decision, contract conditions, monitoring cadence, concentration exposure, exit position, and **what we could not see** |

The engine currently serves the first audience well and the second barely — not because the data is missing, but because it was built as engine features and never assembled into an audience view.

---

## What already exists — the inventory nobody wrote down

Verified across 26 API endpoints. **The gap is assembly, not construction.**

| TPRM lifecycle stage | Status | Where |
|---|:--|---|
| Inherent risk tiering | ⚠️ Partial | `criticality` collected, client-supplied — sets only a `high_stakes` boolean ([recommend.py:76](../backend/app/scoring/recommend.py#L76)) |
| Screening / dealbreakers | ✅ Built | Sanctions gate, entity-ambiguity gate, adjudication queue |
| Due diligence | ✅ Built | Full pipeline, 27 signals, evidence-stored-before-scoring |
| Decision | ✅ Built | `recommend.py` deterministic rule table + `POST /api/vendors/{ref}/decisions` |
| **Contracting** | ❌ **Missing** | No flow-down or clause output |
| Ongoing monitoring | ✅ Built | `monitor.py`, `/api/vendors/{ref}/benchmark-history` percentile trend |
| Issue management | ✅ Built | Disputes + `POST /api/disputes/{id}/adjudicate` |
| **Offboarding / exit** | ❌ **Missing** | No substitutability or exit output |
| Portfolio view | ✅ Built | `GET /api/portfolio` — grade + criticality distribution, blocked/refused/ghost counts, concentration |

Plus: `/dependencies` (fourth-party), `/evidence`, `/findings`, `/export`, `/compare`, `/disclosures`, `/summary`.

**Consequence:** the "composite score fallacy" critique does not land here. You already have gates that bypass arithmetic, a separate Confidence axis, and portfolio drill-down. You are closer to the mature pattern than the critique assumes.

---

## The honest coverage statement

OSINT answers roughly **40%** of an onboarding decision. Publishing that number is a feature, not an admission.

| TPRM domain | Coverage | Where it lives |
|---|:--|---|
| External attack surface | **High** | `dns` `tls` `headers` `ct` |
| Breach history | **High** | `hibp` |
| Vulnerability / KEV exposure | **High** | `nvd` `kev` |
| Email authentication | **High** | `dns` |
| Sanctions | **High** | Gate |
| Entity existence / insolvency | **High** | `gleif` `companies_house` `abn` |
| Certification claims | Moderate | `trust` — claims, not audit reports |
| Regulator actions | Moderate | `regulatory` |
| Adverse media | Moderate | `gdelt` |
| Fourth-party dependencies | Moderate | `fourth_party.py` — Tier-2 only |
| **Internal controls (MFA, access mgmt, training)** | **None** | Requires questionnaire |
| **BCP/DR testing, RTO/RPO** | **None** | Requires questionnaire |
| **Insurance coverage** | **None** | Requires disclosure |
| **Contract history, DPAs, subprocessor terms** | **None** | Requires the vendor |
| **Tier-3+ supply chain** | **None** | Requires flow-down |
| Litigation | **None** | HELD — no free authoritative source (`gleif_collector`) |
| Credential / dark-web exposure | **None** | HELD — `data_privacy_leakage`, HIBP domain API is paid |
| ESG / modern slavery | **None** | HELD — pending Modern Slavery data licence |

**The positioning that follows:**

> *"We tell you what is true from outside, we tell you what we could not see, and we generate the exact questions to ask about the rest."*

That is a **complete** TPRM contribution — it covers the whole decision honestly — rather than 40% presented as 100%.

---

## Gap 1 · Fourth-party concentration — two built halves, never joined

**Effort: days · Value: highest in the system**

[fourth_party.py](../backend/app/fourth_party.py) already names this gap in its own docstring:

> *"The finding that actually matters — 'six of your fourteen vendors share one identity provider' — is a PORTFOLIO statement, and that half needs the platform."*

Meanwhile `/api/portfolio`'s `concentration` field is only *high-criticality vendors scoring below 60*. **It never calls `fourth_party`.** Both halves exist; nothing joins them.

### The output

> *"Nine of your twenty-three vendors authenticate through Okta. Four are Tier-1. A single Okta outage removes 17% of your supplier book simultaneously."*

No per-vendor score can express this, and no commercial rating publishes it from free data.

### Why now

**APRA CPS 230 came into force 1 July 2026.** `fourth_party.py` already cites ¶48. APRA-regulated entities must now identify material service providers and assess concentration. For ANZ buyers this is a live regulatory obligation, four weeks old.

### Steps

1. Extend `GET /api/portfolio` to resolve `fourth_party` per vendor from stored evidence (no new collection — it re-reads DNS/CT/trust/header evidence already banked)
2. Invert to a provider → vendors index
3. Rank by `(vendor_count, max_criticality)`
4. **Disclose, never score.** Same discipline as the per-vendor view: a shared dependency is concentration context, not a penalty on any single vendor

### The metric, defined precisely

Vague concentration reporting is worse than none. Publish exactly these, per provider:

| Metric | Definition | Why it is the one that matters |
|---|---|---|
| **Dependent vendor count** | Vendors in the book with this provider in their fourth-party map | The raw exposure |
| **Book share** | `dependent / total scored vendors` | Makes 9-of-23 legible as 39% |
| **Critical share** | `dependent where criticality=high / total high-criticality vendors` | **The board number.** Concentration on low-criticality vendors is not exposure |
| **Category** | email · CDN · identity · hosting · payments | Identity and hosting concentration are not equivalent risks |
| **Single point of failure** | Critical share ≥ 50% in one category | The trigger for a named finding |

Rank by **critical share**, not raw count — a provider under 90% of your stationery suppliers is not a finding.

### Exit criteria

- [ ] Provider concentration ranked by **critical share**, with all five metrics published
- [ ] No fourth-party finding enters any score — asserted by test
- [ ] Caveat carried: Tier-2 visibility only; Tier-3+ requires vendor disclosure
- [ ] Vendors without a client-supplied `criticality` are counted in the book but excluded from critical share, and that exclusion is stated

---

## Gap 2 · The Evidence Request Pack — the real differentiator

**Effort: 1–2 weeks · Value: very high**

`scoring.yaml` carries **58 `ask_of_vendor` + 58 `accepts_as_refute` + 58 `recheck_after`** entries — one per penalising band. That is a complete, evidence-driven questionnaire generator sitting unused as a product feature.

### Why this beats SIG Lite

| | SIG Lite | Evidence Request Pack |
|---|---|---|
| Questions | ~300, fixed | **Only what was actually observed failing** |
| Basis | Generic | Cited to a specific finding + evidence id |
| Resolution | Manual review | `accepts_as_refute` states the evidence standard up front |
| Closure | Email thread | Dispute workflow → `nullify` / `mitigate` → score updates with reason recorded |

This is the **outside-in triggers inside-out** pattern every TPRM framework describes, and the loop is already ~80% built — the dispute adjudication half exists and is tested.

### Steps

1. `GET /api/vendors/{ref}/evidence-request` — render the pack from the vendor's penalising bands
2. Group by category, order by `effective_penalty` descending
3. Per item: the finding, its evidence id, the `ask_of_vendor` question, the `accepts_as_refute` evidence standard, the `recheck_after` date
4. Export as PDF/DOCX for sending
5. Inbound: link a vendor response to `POST /api/vendors/{ref}/disputes`

### What each audience sees — the same 58 pairs, two renderings

The pack is one dataset. Procurement and security need it cut differently.

**Procurement rendering — an outbound request, ordered by decision impact**

```
EVIDENCE REQUEST · <Vendor> · generated 2026-07-30 · 6 items
Blocking for onboarding: 2      Recheck by: 14 days

1. [BLOCKING] Certificate expiry on a production host
   We observed:  expired certificate, api.example.com, 2026-07-11
   We are asking: "When was this renewed, and what monitors expiry?"
   Resolves with: current certificate chain + monitoring evidence
   Evidence ref:  ev_8f21c...

2. [CONDITION] No published vulnerability-disclosure path
   ...
```

Each item carries **blocking / condition / informational** derived from severity × Inherent Tier — that is the field procurement acts on, and it is the only element not already in `scoring.yaml`.

**Security rendering — an inbound worklist, ordered by effective penalty**

Finding · evidence receipt · category · effective penalty · `recheck_after` · dispute status · what refutes it. Grouped by category so a remediation owner sees their whole queue at once.

**Per-domain confidence appears in both.** A pack built from five collectors that returned data is not the same artefact as one built from twelve. State the coverage per domain at the top, not just the global Confidence number.

### Exit criteria

- [ ] Pack generated from live findings, never a fixed template
- [ ] Every item cites its evidence id
- [ ] Blocking / condition / informational derived from severity × Tier, not hand-set
- [ ] Per-domain coverage stated on the pack
- [ ] Round-trip works: pack → vendor response → dispute → adjudication → re-score

---

## Gap 3 · Coverage statement as a first-class output

**Effort: days · Value: trust + legal protection**

Confidence is currently a number. Procurement needs it as a sentence:

> *"This assessment covers externally observable evidence only. We could not observe: internal access controls, BCP/DR testing, subprocessor contracts, insurance coverage, or Tier-3 supply chain. It does not replace internal due diligence."*

Derive it mechanically from which collectors returned data plus the fixed HELD list — never hand-written per vendor.

Counter-intuitively this **increases** credibility with mature buyers, and it is the honest counterpart to the Ghost being adverse rather than neutral.

---

## Gap 4 · Tiering must drive assessment depth

**Effort: 1–2 weeks**

Today every vendor gets the same 27-signal treatment whether they hold production data or sell stationery. Mature TPRM varies depth by inherent tier — and it saves collector volume, which matters when *"politeness is not optional"*.

| Tier | Collection depth | Outputs | Cadence |
|---|---|---|---|
| **T1 Critical** | Full + fourth-party map + evidence pack | Everything | Quarterly |
| **T2 Important** | Full | Standard card | Semi-annual |
| **T3 Standard** | Core signals only | Summary | Annual |
| **T4 Low** | Screening only (sanctions + entity) | Pass/fail | Passive monitoring |

Two wins: tiering becomes operational rather than cosmetic, and low-tier vendors stop consuming free-API budget.

**Interaction:** this is Phase 5d in the migration plan. Build them together.

---

## Gap 5 · Contract flow-downs — speaks procurement's language

**Effort: 1–2 weeks**

Converts a security finding into something procurement can act on. A lookup table, not a model — same discipline as `reasons`/`actions`.

| Observed | Suggested contractual protection |
|---|---|
| No published incident-response path | 24–72h breach notification clause |
| No independent audit evidence | Right-to-audit, or annual SOC 2 delivery obligation |
| Concentrated fourth-party dependency | Subprocessor change notification + approval right |
| Going-concern flag | Termination for convenience · source-code escrow · exit assistance |
| Thin coverage / Ghost | Security questionnaire as condition precedent |
| Overdue KEV | Remediation SLA with contractual milestone |

**Discipline:** each entry cited, marked as *suggested drafting points, not legal advice*, and versioned. Never generated.

---

## Gap 6 · Operational resilience — the one collector worth building

**Effort: 2–3 weeks**

Status-page and outage history is the **only** major TPRM domain that is lawfully free, genuinely public, and currently unread. BCP/resilience is the second procurement question after "will they still exist."

**Route to Continuity, not Posture** — frequent outages are a delivery problem, not a security problem.

Caveat to carry: a vendor with no status page is not more reliable than one publishing incidents. Absence of a status page is absence of evidence — a Confidence effect, not a Continuity finding.

---

## Gap 7 · Exit and substitutability

**Effort: 1 week**

Mostly not OSINT, but the tier drives it and procurement always asks. What is derivable:

- Fourth-party dependency map → what breaks if they fail
- Sector + cohort → whether substitutes plausibly exist
- Going-concern flags → urgency

What is not: switching cost, contract lock-in, data portability. Ask via the Evidence Request Pack.

### Close the loop cheaply: one buyer-supplied flag

Do not attempt to derive substitutability from public data — it is not there. Take it the same way `criticality` is taken: **client-supplied, never inferred.**

| `substitutability` | Meaning | Effect |
|---|---|---|
| `sole_source` | No viable alternative | Escalates Residual Risk one band · mandates exit-clause flow-downs |
| `low` | Alternatives exist, migration is months | Exit-assistance clause recommended |
| `medium` | Alternatives exist, migration is weeks | Standard terms |
| `high` | Commodity, swap at will | No exit conditions needed |

Four values, one field, alongside `criticality` on the same client-supplied path. It turns Gap 7 from a research problem into a form field — and `sole_source × poor Posture` is the single most useful procurement alert the system could emit.

---

## What NOT to build

The benchmarking material circulating alongside this proposes several things that are wrong for this system, not merely premature.

| Proposal | Why not |
|---|---|
| **Peer consortium / commercial benchmark purchase** (BitSight, SecurityScorecard datasets) | Cross-tenant pooling is already recorded as *"a contractual question before an engineering one"*. And importing a commercial rating imports its biases — including the observability bias this model exists to remove |
| **Homomorphic encryption / SMPC / differential privacy** | For a system where `min_cohort_n` is currently **1** and the corpus is **5 vendors**, this is years premature. Fix the pool first |
| **"Minimum n=30 for reliable percentiles"** | Your target is 8. 30 is unreachable across 120 cohort cells with 115 seeds. Adopt 30 and you publish nothing. Note the tension, keep 8, disclose `n` |
| **Monte Carlo / Bayesian updating / ML anomaly detection** | You have no outcome labels. These techniques need ground truth you have not built yet |
| **300-control taxonomy / framework mapping matrix** | That is for questionnaire-based systems. You observe from outside; there is no control attestation to map |
| **Snowflake / Databricks / Tableau stack** | You have FastAPI + a store abstraction and 27 signals. Enterprise data-lake tooling would be cargo cult |
| **"Supplier Trust Dossier"** | This is a product for a company *being assessed*, not one *doing* assessment. Different customer entirely — note it and move on |
| **Category weights (Cyber 30–35%, Financial 15–20%…)** | §5.6 deleted category weights deliberately. Percentages look principled and are unfalsifiable |

**The benchmarking work you actually need is already scheduled** — migration plan Phase 6: fix the `n=6` synthetic disclosure, enforce `min_cohort_n`, seed the pool. Nothing beyond that is reachable until the pool is real.

---

## Build order

| # | Item | Effort | Depends on |
|---|---|--:|---|
| 1 | **Fourth-party concentration** | days | — (both halves built) |
| 2 | **Coverage statement** | days | — |
| 3 | **Evidence Request Pack** | 1–2 wks | — (58 pairs written) |
| 4 | **Tier → depth + cadence** | 1–2 wks | Migration 5d |
| 5 | **Contract flow-downs** | 1–2 wks | 3 |
| 6 | **Two audience views** | 2 wks | 1–5 |
| 7 | **Status-page collector** | 2–3 wks | Continuity (migration 5e) |
| 8 | **Exit / substitutability** | 1 wk | 1, 4 |

**Items 1–3 are roughly three weeks** and move this from "security rating" to "TPRM module" more than anything currently in the migration plan.

---

## The two audience views — one dataset, two renderings

### Security view
Findings ranked by effective penalty · evidence receipts · category drill-down · per-signal peer comparison · remediation asks · recheck cadence · dispute status

### Procurement view
1. **Decision** — proceed / conditions / do not proceed / escalate (`recommend.py`)
2. **Residual Risk** — Posture × Inherent Tier matrix
3. **Continuity flags** — registry-cited, with retrieval dates
4. **Concentration** — shared fourth parties across the book
5. **Contract conditions** — flow-downs to negotiate
6. **Monitoring cadence** — from tier
7. **What we could not see** — the coverage statement
8. **Evidence Request Pack** — the questions to ask

Same immutable score object underneath. `/export` and `/summary` already exist as the rendering seam.

---

## What this plan does not change

- **Posture arithmetic.** Nothing here touches it
- **The firmographic rule.** Type, age, revenue, headcount and market cap stay out of the score — they inform tiering, cohorting and confidence only
- **Evidence-before-scoring.** Every new output reads stored evidence; none introduces a new scoring path
- **Disclosed-never-scored.** Fourth parties, concentration and coverage gaps are context, never penalties
