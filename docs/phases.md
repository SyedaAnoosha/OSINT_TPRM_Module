# Phases — Implementation Runbook

**The single execution document.** Combines [report.md](report.md) (research) · [complete_plan.md](complete_plan.md) (architecture) · [migration-plan.md](migration-plan.md) + [step_by_step_mig_plan.md](step_by_step_mig_plan.md) (engine) · [tprm-module-plan.md](tprm-module-plan.md) (product).

**Verified against the working tree:** 2026-07-31 (re-audited after E6 landed) · `scoring.yaml` **v5.1.0** · 27 signals · **35 penalising bands** · `penalty_divisor` **2.86** · **5 scoring + 2 context categories** · **595 passed, 0 failed**

*(Band count fell 57 → 49 at E2 → 47 at E3 → 36 at E4; the suite went green at E0.1. Signals held at 27 throughout — nothing was deleted, only reclassified. E1–E5 are a MAJOR version bump: see [change-notice-v5.md](change-notice-v5.md). The figures above are measured, not carried forward.)*

---

## How to read this — two lenses on every phase

Each phase below is written twice over, because two people need it:

| Lens | Question | Where it appears |
|---|---|---|
| **Sponsor** *(your senior, procurement, the client)* | *"What does the customer get, and why does it matter to a supplier decision?"* | **Customer outcome** at the top of each phase |
| **Implementer** | *"What do I type, in what order, and what breaks?"* | **Steps · Traps · Tests · Exit** |

The governing principle behind the whole sequence, and the sentence to lead with in any status update:

> **The score is a component, not the product.** A supplier decision needs identity, sanctions, viability, data protection, claim reliability, concentration and failure consequence. We answer roughly 40% of that from public evidence, say so explicitly, and generate the questions for the rest.

---

## Two tracks, deliberately separate

**Track E (Engine)** makes the number correct. **Track P (Product)** makes it usable in a decision. **P touches no Posture arithmetic**, so both run in parallel with different people.

The single most important scheduling fact for a sponsor:

> **P1–P3 depend on nothing, take about three weeks, and move this from "security rating" to "TPRM module" faster than any engine phase.** They should start now, not after the engine work.

### Phase map

```
TRACK E — ENGINE (score correctness)          TRACK P — PRODUCT (decision support)
────────────────────────────────────          ─────────────────────────────────────
E0  Instrument + baseline           ✅ E0.1    P1  Fourth-party concentration  ← NOW
     │                                        P2  Coverage statement          ← NOW
     ▼                                        P3  Evidence Request Pack       ← NOW
E1  Remove sector opinion           ✅              │
     ▼                                             ▼
E2  Stop penalising the norm  ✅◑ ──► E3 Merge P4  Contract flow-downs
     ▼                                             │
E4  Relocate going-concern (Continuity)            │
     ▼                                             │
E5  Consolidate categories + divisor ◄─────────────┤
     ▼                                        P5  Tier → depth  (needs E10)
E6  Exposure denominator (free half)               │
     ▼                                        P7  Status pages  (needs E4)
E7  Aggregation + severity ladder                  │
     ▼                                             ▼
E8  Hard gates                                P6  Two audience views
     ▼                                        P8  Exit / substitutability
E9  Assurity + Compliance Gap ──► E2b positive credit  │
     ▼                                             ▼
                                               P9  Program maturity + KPI/KRI
                                                   benchmarking (needs P1–P8 for
                                                   full KPI wiring)
     ▼
E10 Expectation Gap + Inherent Tier   ◑ (E10a largely delivered by EB)
     ▼
E11 Real cohorts ──────────────► (unblocks E10 percentiles, E13)
     ▼
E12 Collector fan-out (the big one)
     ▼
E13 Bounded log-odds

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ EB  Peer benchmarking layer v2          ✅ DELIVERED 2026-07-30           │
  │     Out of sequence, and correctly so — it depends on nothing in Track E. │
  │     Supersedes E11's THRESHOLD mechanism · delivers most of E10a ·        │
  │     automates E0.3's instrument · adds snapshot reproducibility, a        │
  │     cohort dispute path, and the placement delta. See EB below.           │
  └──────────────────────────────────────────────────────────────────────────┘

✅ done   ◑ partial   (no mark) not started
```

### Numbering map — old documents → this one

The older plans grew numbering organically (`1a`, `1b-i`, `1d`, `5e`, `2A`…) and it no longer reads in execution order. This document renumbers; nothing is lost.

| Here | Was | Here | Was |
|---|---|---|---|
| **E0** | Phase 0 | **E8** | Phase 4 |
| **E1** | Phase 1a | **E9** | Phase 5a + 5b |
| **E2** | Phase 1b-i | **E9b** | Phase 1b-ii |
| **E3** | Phase 1c | **E10** | Phase 5c + 5d |
| **E4** | Phase 5e | **E11** | Phase 6 |
| **E5** | Phase 1d | **E12** | Phase 2B |
| **E6** | Phase 2A | **E13** | Phase 7 |
| **E7** | Phase 3 | **P1–P8** | Gaps 1–8 |
| **EB** | *(new — not in any earlier plan)* | | |
| **P9** | *(new — not in any earlier plan)* | | |
| **E14** | *(new — not in any earlier plan)* | | |

**Why `EB` is lettered and `E14` is numbered.** The rule is *position in the engine's execution
order*, not novelty. EB depends on nothing in Track E, touches no Posture arithmetic, and was built
out of sequence — numbering it would have implied it comes after E13, which is the opposite of true.
**E14 genuinely does come after everything**: it is a read layer over a finished assessment and its
context is assembled from P2's coverage statement, E9c's compliance gap, E10b's residual cell, EB's
expectation gap and P1's concentration. It cannot run before them, so the number is accurate rather
than decorative.

**Why `P9` is new.** [very_helpful_benchmarking_analysis.md](very_helpful_benchmarking_analysis.md)
describes two different things under one heading, and only one of them is already built. Its second
half (cohorts, expectation gap, percentiles) is EB, delivered. Its first half — a maturity model,
KPI/KRI dashboard, and peer-industry program comparison (Shared Assessments, Gartner, Crowe) — measures
**the TPRM program itself**, not any one vendor. Nothing in E0–E13, EB, or P1–P8 does that, so it is
added as **P9**, not folded into EB.

### Hard dependencies — none of these are preferences

| Dependency | Why it is hard |
|---|---|
| **E1 → E2** | `_validate_industry_profiles` requires promoted bands to *be* penalising. Reverse it and the loader refuses to start |
| **E2 + E4 → E5** | E5 consolidates categories that E2 and E4 empty. Run it first and you consolidate the wrong set |
| **E5 → E6, E7** | Both operate *inside* a category boundary. Boundaries first = one re-golden, not three |
| **E9 → E9b** | No bonus mechanism exists in the engine until Assurity does |
| **E11 → E10 percentiles, E13** | No trustworthy peer median without real cohorts. **EB enforces this in code** — it refuses a percentile below n=30 rather than trusting the sequence |

**EB depends on nothing** and is already delivered. It is listed in the map for orientation, not as a
gate on anything else.

---

## Status right now — measured, not assumed

**All three Sprint 0 "ship regardless" items are done and committed.** Track E is through E1 with E2
in the working tree; Track P has not started; EB landed whole.

### Sprint 0 — closed

| # | Item | Status |
|---|---|---|
| 1 | **Version control** | ✅ **Done.** Nine commits, HEAD `4d2b89f` |
| 2 | **`n=6` disclosure defect** | ✅ **Done and pinned.** `ebc1dc5` implemented it, `18dd4f6` added the tests. *(An earlier revision of this document said "written, not verified" — that is now stale.)* |
| 3 | **15 red tests** | ✅ **Done.** `6752556`. Suite is **544 passed, 0 failed** |

### Commit log

```
4d2b89f  E5: consolidate categories, recalibrate the divisor, bump to v5.0.0
1c500fa  E4: relocate going-concern out of Posture into Continuity
5412236  E3: merge contactability — one fact, charged once
0bf38f7  E2: stop penalising the norm
817d7da  E1: remove sector severity promotion from the arithmetic
6752556  E0.1: resolve the 15 pre-existing test failures
18dd4f6  Sprint 0: pin the synthetic-disclosure behaviour with tests
ebc1dc5  Sprint 0: stop reporting synthetic peers as real companies
b53e61f  baseline: scoring.yaml v4.2.0 — 417 pass / 15 fail, before any migration
```

### Phase status

| Phase | Status | Evidence in the tree |
|---|---|---|
| **E0.1** 15 red tests | ✅ | 577 pass / 0 fail |
| **E0.2** corpus extension | ✅ | 10 fixtures: 5 real + 5 labelled-synthetic archetypes. Range 16–96, was 74–87 |
| **E0.3** discrimination analysis | ✅◑ | [discrimination-analysis.md](discrimination-analysis.md) committed and regenerable. **The seeded pool now exists** (E11, 2026-07-31) and its distribution is measured: 103 real vendors span **67–97, median 90**, vs the **16–96** this document quotes — a range that came from the five *synthetic* archetypes. Re-running the analysis on the pool is the outstanding step, and it needs a seed set with ordinary suppliers in it, not more household names |
| **E0.4** outcome labels | ⏸ | **Deferred in writing**, as the criterion permits — [e0.4-outcome-labels-deferral.md](e0.4-outcome-labels-deferral.md) |
| **E0.5** baseline frozen | ✅ | `regolden` byte-for-byte. *(An earlier revision of this row invented a `baseline-distribution.md` deliverable the phase text never asked for; the posture distribution lives in the discrimination analysis.)* |
| **E1** sector opinion | ✅ | `industry_profiles` count in `scoring.yaml` is 0; `promote_severity` gone |
| **E2** stop penalising the norm | ✅ | `0bf38f7`. 8 bands informational (not 6 — see note), 57 → 49 |
| **E3** merge duplicates | ✅ | `5412236`. `contactability.partial` + `.none_published` informational, 49 → 47 |
| **E4** Continuity relocation | ✅ | `1c500fa`. `app/continuity.py`, `GET /api/vendors/{ref}/continuity`, 47 → 36 |
| **E5** categories + divisor | ✅ | `4d2b89f`. 5 scoring + 2 context categories, divisor 2.86, `ScoringConfig.category_of()`, v5.0.0 + [change notice](change-notice-v5.md) |
| **E6** exposure denominator | ✅ | `app/scoring/exposure.py`, `exposure:` in scoring.yaml, v5.1.0. `subdomain_estate` is a denominator, not a penalty |
| **E7** aggregation + ladder | ✅ | `501e995`, v5.2.0. decay 0.7 + ladder 50/20/6/1.5 → **3.06:1**; root-cause dedup; ceiling ramp |
| **E8** gates | ✅◑ | Config-driven pass, basis enforced at load. `entity_dissolved` LIVE; `kev_overdue` + `no_valid_tls` declared-but-off with reasons (evidence, not policy) |
| **E9** Assurity / Compliance Gap | ✅◑ | `app/assurity.py`, `app/compliance_gap.py`, `GET /api/vendors/{ref}/assurity`. **3 frameworks only** — [expansion roadmap](e9c-framework-roadmap.md) |
| **E10** Expectation Gap + Tier | ✅ | `6956593`. `benchmarking/expectation_gap.py` (signed `EG` + driver attribution) · `app/residual_risk.py` (Inherent Tier + 16-cell matrix, stored nowhere) · `GET /api/v2/suppliers/{ref}/expectation-gap`, `GET /api/vendors/{ref}/residual-risk`, `GET /api/vendors/{ref}/assessment` |
| **E11** real cohorts | ✅ | `min_cohort_n` **floored in code** at 8 on both paths; a synthetic baseline publishes **no ordinal placement at any n**. The seeder declares each vendor's sector and `--status` reports every gate plus E13 readiness. **Pool seeded 2026-07-31**: 114 vendors → 62 cohorts, mean depth 1.84, one cohort over the floor. The measured finding is that the cohort key has four dimensions and the seed list was sized for one |
| **E12** collector fan-out | ✅◑ | `b352cdb`. `app/collectors/estate.py` + `estate_collector.py`, second wave in the pipeline, `estate:` config, two rate signals. All six steps met. **Still OFF at `probe_cap: 1`, now for a MEASURED reason.** `app/estate_readiness.py` (2026-08-01): estate availability **26% book-wide, 48% of relationships**, against a written 50% threshold. The blocker is not probe budget — 25 probes/vendor is 1,644 handshakes for the whole book — it is that CT is not answering (crt.sh 404s, Certspotter rate-limits keyless clients). **The resourcing item is an API key, not a bigger cap** |
| **E13** bounded log-odds | ✅ | `app/scoring/log_odds.py` + 22 tests. Published **side by side** as `Score.log_odds_preview`; computed and consumed nowhere, asserted by parsing the engine. `score(peers=…)` filled from the exact cohort, median not mean. **Switched on for 1 of 62 cohorts as of 2026-07-31** — per cohort, no flag, the other 61 still refusing. Consuming the preview in the live posture remains a release decision, not a threshold |
| **EB** benchmarking v2 | ✅ | 11 routes, 91 tests, `docs/benchmarking-design.md`. Independent review audited against the tree: [benchmarking-review-2026-07.md](benchmarking-review-2026-07.md) — three gaps found and closed |
| **P1** fourth-party concentration | ✅ | `app/concentration.py`. The two halves are joined: `/api/portfolio` now publishes all five metrics ranked by **critical share**. The old misnamed `concentration` field is `weak_critical_vendors` |
| **P2** coverage statement | ✅ | `app/coverage_statement.py`. Derived from the run, never written. Three buckets kept apart: not-collected-this-run · held-no-lawful-source · never-observable |
| **P3** Evidence Request Pack | ✅ | `app/evidence_pack.py`, 25 tests. The **41** `ask_of_vendor` entries are finally read *(the plan said 58; that count predates E2/E3/E5 — corrected 2026-07-31)*. **Both renderings shipped** — procurement tagged blocking/condition/informational from severity × Inherent Tier, security grouped by domain with dispute state — plus per-domain coverage on both |
| **P4** contract flow-downs | ✅ | `app/contract_flowdowns.py`, 24 tests, `GET /api/vendors/{ref}/contract-flowdowns`. **Seven** fixed families (the seventh is P8's), versioned, cited, **never generated**. Four are derived rather than observed (portfolio concentration, continuity, the confidence axis, declared substitutability) and cite the module rather than an evidence id |
| **P5** tier → depth + cadence | ✅ | `app/assessment_depth.py`, 24 + 10 tests. Depth reaches `run_pipeline(depth=…)`, cadence reaches `monitor --by-tier` — **that is the join**. Screening depth publishes NO posture and says so before the run; the confidence denominator is never rebased onto the chosen depth |
| **P6** two audience views | ✅ | `app/audience_views.py`, 16 + 5 tests, `GET /api/vendors/{ref}/export?view=procurement\|security`. Recomputes nothing (asserted structurally); `views_agree()` ships as an invariant so the two renderings cannot quote different numbers |
| **P7** status-page collector | ✅ | `app/status_page.py` + `collectors/status_page_collector.py`, 10 tests, `GET /api/vendors/{ref}/status-page`. Emits **no `Finding`**, so the scoring path cannot read it even by accident. Assembled onto `/export` and the procurement continuity section, **beside** going-concern rather than inside it |
| **P8** exit + substitutability | ✅ | `app/exit_readiness.py`, 22 tests, `GET /api/vendors/{ref}/exit-readiness`. Both joins the plan named are now real: `sole_source` **escalates the residual tier one band** (disclosed via `escalated_from`) and **mandates exit-clause flow-downs** as P4's seventh family. It only ever escalates |
| **P9** program maturity + KPIs | ✅ | `app/program_maturity.py` + `app/program_kpis.py`, 73 tests, `GET /api/program[/maturity\|/kpis\|/inventory\|/monitoring\|/estate-readiness]`. **Level 2 (Reactive)** — the MINIMUM across 8 dimensions, not the 3.1 average. 15 metrics, 11 computed and 4 declared-or-empty. **Assessment v1.1.0 (2026-08-01):** `inventory_tiering` and `continuous_monitoring` both re-scored 2 → 3, and both re-scores were *forced by the claim tests* rather than volunteered — lifecycle coverage is now the only dimension at the floor |
| **E14** LLM gap analysis | ✅◑ | `app/gap_analysis.py`, `POST /api/vendors/{ref}/gap-analysis` · `GET .../gap-analysis/history` · `POST .../recommendations/{i}`, 28 tests. A third audience view whose renderer is a language model: an executive summary, prioritised recommendations an analyst can accept/edit/reject, `evidence_finding_ids[]` validated against the context and invented ones dropped-and-counted. `limitations` copied byte-identical from P2, never generated. Gemini → Groq → OpenRouter, one attempt each, falls back on transport/rate-limit only. **◑ because the chain is proven against a mocked transport, never a live key** — no provider is configured in this environment — and the button (`components/GapAnalysis.jsx`) has not been driven in a live browser session against a real generation |

### Immediate next action — the three programme actions are done, and each one found the denominator was wrong

**Every phase in this plan is delivered — E0–E13, EB, and P1–P9.** The three non-code actions P9's
own dashboard named were carried out on **2026-08-01** (`e1a2b11`), and the fourth — E12's fan-out —
was measured rather than switched on. What follows is what each one actually found, because in three
of the four cases the number that looked like the problem was not.

**1 · Inherent tiers — declared. 0.0% → 100% of relationships.**
The zero was a **missing route, not a missing habit**. The only path that had ever accepted a
criticality was `POST /api/vendors/score`, which re-runs the whole pipeline — so declaring an
exposure cost a full scan of a dozen free services, and of course nobody declared one.
`app/inherent_register.py` is now the inventory of record and `POST /api/vendors/{ref}/inherent`
declares without re-scoring.

The bigger finding was the **denominator**. 146 scored rows were never 146 relationships:

| Population | n | Has an exposure to declare? |
|---|--:|---|
| **Relationships** | 23 | Yes — all 23 now declared, every one **provisional** until an owner confirms it |
| **Seeded corpus** | 114 | No. Scored by `seed_cohorts` to give E11's peer groups a population; there is no commercial relationship, so declaring one would fabricate a contract to move a metric |
| **Inventory defects** | 9 | No. Typos (`aatlassian`), malformed refs (`http://servicenow`), products mistaken for vendors (`jira`, `claude`), the buyer's own domains |

Counting the 123 as undeclared made the programme look negligent about a question that does not
apply to them, and buried the two dozen that mattered in a number too large to act on.
`residual_risk_distribution` went from `{not_published: 146}` to a real spread; `tier1_assessment_currency`
became computable for the first time.

**2 · The monitor — scheduled, and the schedule is now falsifiable.**
`app/scheduler.py` is the entrypoint, still not a daemon; `ops/schedule/` holds the cron entry,
systemd timer and Windows Scheduled Task, because which host runs the sweep and who is paged when it
stops are operational decisions that do not belong in Python.

What earns the level is not the timer but the **ledger**. `monitor_runs` is append-only, records
`started` and `finished` as separate events so a run that dies leaves a visible orphan, and
`--health` treats **silence as the alarm condition**. This matters because `monitoring_currency` can
read 100% on a schedule that died in March — nothing is re-scored into staleness because nothing is
re-scored at all — and the ledger is the only signal that can tell those two books apart.

**3 · The 12 blocked records — six cleared, and one was never a sanctions match.**
`box`, `bt`, `jira`, `line`, `oracle` and `xero` cleared on the fixed matcher. Five remain on
sanctions head-matches; **`colesgroup` was blocked on `entity_dissolved` and was read as a sanctions
false positive until the queue said otherwise.** No relationship is blocked — all six are corpus.

`app/adjudication_queue.py` puts the discriminating facts on the row: match strength, whether the
listed party is a natural person, and whether the query is an ordinary English word or a coined
name. `orange` → ORANGE VOLUNTEERS and `experian` → Experian Holdings, Inc. are the *same match
strength* and completely different questions. It annotates and never suppresses — a suppression list
grows every time somebody is inconvenienced by it, and within a year it is why a real hit was missed.

**4 · E12's fan-out — measured, and NOT switched on.**
The plan called this *"a resourcing decision rather than a design problem."* Half right.
`app/estate_readiness.py` measured the book: **26% of vendors carry a usable estate** (48% of
relationships) against a written 50% threshold. The blocker is not probe budget — 25 probes per
vendor is 1,644 handshakes for the entire book, a polite afternoon. **Certificate transparency is
not answering**: crt.sh returns 404 under load and Certspotter rate-limits keyless clients.

Raising the cap makes both `estate_*` signals *reachable*, which puts them back in every vendor's
coverage denominator — so 108 vendors would lose confidence to a feature they cannot participate in.
That fall would be correct and must not be engineered away: rebasing the denominator per vendor is
the move P5 refuses in writing for assessment depths, and for the same reason. **The resourcing item
is an API key, not a bigger cap.** `probe_cap` stays 1, with the measurement written into
`scoring.yaml`.

> ### The maturity model re-scored itself, and the test suite forced it
>
> Assessment **v1.1.0**, 2026-08-01. `app/scheduler.py` and `app/inherent_register.py` were built;
> the claims citing their *absence* failed; the suite stayed red until a person came back and
> re-argued the levels. That is the anti-staleness mechanism working as designed, and it is the
> first time it has fired.
>
> `inventory_tiering` **2 → 3** · `continuous_monitoring` **2 → 3**
>
> **Overall stays Level 2** — the minimum, never the 3.1 average. But **lifecycle coverage is now
> the only dimension at the floor**, which is a far more useful sentence than the one three
> dimensions produced. The single remaining blocker is named and unambiguous: there is no
> offboarding workflow, no collector, and nothing that observes whether access was revoked or data
> returned.

**What is left is one credential and two verifications.** E12 needs a Certspotter key.
[E14](#e14--gap-analysis--recommendations-llm) is built and tested against a mocked provider
chain — what remains is a real `TPRM_GEMINI_*`/`TPRM_GROQ_*`/`TPRM_OPENROUTER_*` key to prove the
chain against a live model, a click-through of the button in a running browser, and joining a
generated analysis onto the P6 `/export` dossiers. Everything else in this document is built.

> ### E11's pool: seeded, and it bought less depth than the plan assumed — for a structural reason
>
> **Run 2026-07-31, `--all --concurrency 2`, 114 vendors. Measured result:**
>
> | | |
> |---|---|
> | Vendors scored into cohorts | **114** |
> | Distinct cohorts formed | **62** |
> | Mean cohort depth | **1.84** |
> | Cohorts holding exactly one member | **31** (half of them) |
> | Cohorts at or above E13's floor of 8 | **1** — `technology\|rev=?\|emp=medium\|north_america` (n=10) |
>
> **The seed list is sized for a gate on a SECTOR; the cohort key has four dimensions** —
> `sector × revenue_band × employee_band × region`. 114 vendors across 10 sectors, four regions and
> several size bands land 1.84 to a cell. **No plausible lengthening of the list fixes this**:
> reaching eight in even half of 62 cells needs something on the order of 500 scored vendors, and
> the fragmentation grows with every new region or size band the list reaches into. Eight peers in a
> four-dimensional cell is simply a different ask from eight peers in a sector, and the plan costed
> the second one.
>
> *(Six cohorts show `n=0`: a profile carries the cohort key but the vendor blocked or refused, and
> `_COHORT_PEERS_SQL` excludes both. Correct — a vendor with no published posture is not a peer —
> and worth stating, because "0 members" otherwise reads as a write that failed.)*
>
> ### …and the run surfaced two things worth more than the depth would have been
>
> **1. THE SANCTIONS GATE BLOCKED 10 OF 114 (8.8%). FIXED — the rate is now 5, and every survivor
> is a real name correspondence.** Every block was `sanctions screen hit`; not one was an
> entity-ambiguity block.
>
> **Two corrections to the first reading of this, both of which mattered.** The initial note said
> *"all ten look wrong"* and blamed a missing entity-resolution guard. Measuring against the real
> 25,921-entry list showed both claims were wrong:
>
> * **Not all ten were false.** `experian.com` matched **"Experian Holdings, Inc."** on the Entity
>   List — a proper name match, and precisely what the gate exists to catch. `orange.com` matched
>   **"ORANGE VOLUNTEERS"**, a listed entity genuinely named Orange. Those are the gate working.
> * **The register evidence is not available where the matching happens.** Collectors run
>   concurrently in one `asyncio.gather`, so at the moment the ITA collector matches, GLEIF and
>   RDAP have not answered. An entity-resolution guard would have needed a second wave. It was not
>   needed: the defect was in *what counts as a match*, not in what the gate does about one.
>
> **What the real failure was.** Whole-word containment: a query matched if its words appeared
> *anywhere* in an entity's name.
>
> | Vendor | Hits | Why |
> |---|---|---|
> | **BT Group** | **626** | `bt` is two characters and was dropped by a `len >= 3` filter, leaving `group` — which appears in 626 entries — as the entire query |
> | Line | 20 | *ISLAMIC REPUBLIC OF IRAN SHIPPING **LINE***, *Bestway **Line** FZCO* |
> | Wise | 9 | *ROBERT **WISE***, *Infinity **Wise** Technology Limited* |
> | Box | 2 | *RED **BOX** ENERGY SERVICES PTE LTD* |
> | Xero | 1 | *CLOUD **XERO** MANAGEMENT PTE. LTD.* |
>
> **Rarity is not the discriminator, and that was the first idea.** `xero` appears in exactly ONE
> entry in the whole list — maximally rare — and is still a false positive. What separates a hit
> from a collision is *where the word sits*: a company's distinguishing name **leads** its legal
> name. "RED BOX ENERGY SERVICES" is a company called Red Box Energy, not a company called Box.
>
> **The policy did not loosen.** A possible match still blocks and still goes to a person. What
> changed is that a match now requires the query to *account for* the entity's name — the whole
> name (`full`) or its leading words (`head`) — checked against the primary name and each alias
> **separately**, since pooling them let a query match words drawn from three different names at
> once.
>
> **Measured, both directions:** false positives **10 → 5**; recall checked against fourteen
> genuinely listed entities (Huawei, ZTE, Kaspersky, Hikvision, Inspur, SMIC, Rosneft, Gazprom,
> Sberbank, DJI, Dahua, China Telecom, Megvii) — **none lost**, correct entity ranked first. Dropping
> the `len >= 3` filter *recovers* recall: a real "BT GROUP PLC" now matches where `bt` was
> previously discarded unread.
>
> **Two things it also fixed that nobody had asked about:**
> * **A name with nothing distinctive in it is no longer recorded as a clean screen.** If every word
>   is a corporate generic, the collector records `screened: false` with a reason. A clean screen
>   *is* the s16(7) defence, and manufacturing one is worse than a false positive — nobody ever
>   looks at it again.
> * **The entity type is on the observation line.** `KOGAN, Alexander Borisovich [Individual]` is a
>   five-second adjudication; the same line without `[Individual]` is a research task. A blocking
>   queue is only as safe as the speed at which a human can clear a false positive from it.
>
> **A stated limit, pinned by test rather than assumed away.** "Hangzhou Hikvision Digital
> Technology" does not head-align on `hikvision` — a leading geographic qualifier. No cheap rule
> separates a place name from "RED BOX", where the same offset-by-one match is the false positive
> being removed, so allowing one skipped leading token would let Box straight back in. What makes it
> safe in practice is that OFAC records aliases systematically and the real entry carries one that
> does head-align — evidence, not luck, since the full-list run lost none of fourteen controls. The
> residual exposure is a listed entity with a leading geographic qualifier and **no** alias.
>
> **2. THE POSTURE DISTRIBUTION ON REAL VENDORS IS MUCH NARROWER THAN THE CORPUS SUGGESTS.**
> 103 published scores: **min 67 · p25 81 · median 90 · p75 90 · max 97**. Grades: **71 A, 31 B,
> 1 C, no D, no F.** Nothing below 67. Confidence: min 0.44, median 0.75.
>
> This is E0.3's outstanding diagnostic, and it is now answerable. The corpus range this document
> quotes — **16–96** — came from the *five synthetic archetypes*; the five real fixtures spanned
> 74–87, and 103 real global vendors span 67–97 with half of them at 90 or above. So the honest
> reading is that **E7's 3.06:1 severity ratio was measured on a population containing deliberately
> bad vendors, and the real population does not contain them.**
>
> Two readings compete and the pool cannot yet separate them: the model may not discriminate among
> reputable firms, or these firms may genuinely be good. The seed list is deliberately
> household-name companies — Siemens, Nestlé, SAP, Telstra — which biases hard toward clean hygiene.
> **What settles it is a seed set containing ordinary suppliers**, not more of these. That is a real
> input to E0.3's re-run and to any claim about discrimination, and it should be recorded before
> anyone quotes 16–96 as evidence the model separates real vendors.
>
> This is why E13's switch-on was rebuilt as **per cohort** rather than one switch for the book, and
> why `--status` reports *"N of M cohort(s) can supply `L_peer`"*. The design already handles the
> outcome honestly: cohorts that reach depth begin publishing the preview on their next score;
> the rest keep refusing, in `preconditions()`'s own words. Nothing had to be relaxed to
> accommodate the result, which is the test of whether the refusal was real.
>
> **What this does NOT license.** Lowering the floor, or shrinking toward a widened cohort, would
> both make more vendors "work" — and both are the flattering direction. The floor and the
> exact-cohort rule stay; deepening a cohort is an operational programme, and EB's widening ladder
> already serves the ranking question that genuinely can be answered at lower `n`.

### Historical — the E10 note this replaced

**E0 through E5 are closed: 23 of 23 exit criteria met**, each verified against the tree on
2026-07-31 rather than carried forward from a status table. One (E0.4) is met by a written
deferral, which is what its criterion permits; two carry outstanding work that belongs to a later
phase and is tracked there (E0.3's seeded-pool run, E5's `regulator_action` tagging).

E0.2 turned out to matter more than its one-line description suggested. It was a silent
prerequisite for E0.3, and closing it immediately paid for itself: the extended corpus **caught a
wrong finding in the discrimination analysis before it was committed** — an early draft conflated
"every vendor sits in one band" with "every vendor is charged", and understated the remaining flat
tax by three signals. All three are footprint signals, which makes them **the measured case for
E6**, not merely the argued one.

**E7, E8 and E9 landed 2026-07-31 (v5.2.0).** Next: **E10 · Expectation Gap + Inherent Risk Tier**, most of E10a already delivered by EB.

> **Note on E2's scope.** It reclassified **eight** bands where this document's table lists six: the
> `partial` / `marketing_only` variants of `program_disclosure` and `reporting_posture` were missed
> when the table was written. The implementation is right and the table has been corrected below.

> **Note on E5's scope.** Two deliberate deviations from the target table, recorded in
> [change-notice-v5.md](change-notice-v5.md) §3.6: `cert_posture` stayed in a scoring category
> rather than relocating to context, and `dnssec` still penalises its `misconfigured` band (only
> *absence* is the norm). Shipped count is 18 scored signals, not 16. Neither moves the divisor.
>
> E5 also required a change the plan did not anticipate: the collector-declared category had to
> stop being authoritative. `ScoringConfig.category_of()` resolves a signal's home from the model,
> which is what made the restructure a config-only edit instead of a rewrite of twelve collectors
> and five frozen fixtures whose entire value is that they are captured once and never touched.

---

# TRACK E — ENGINE

---

## E0 · Instrument and baseline

**2–3 weeks · Risk: none · Changes scores: no**

### Customer outcome
None directly — this is the phase that makes every later claim *provable*. Without it, "we improved the model" is an assertion. A sponsor should read E0 as **buying the right to make claims later**.

### Preconditions
- HEAD clean, `b53e61f` or later
- `backend/.venv` active

### Steps

**E0.1 — Resolve the 15 red tests.** Migrating on a red suite means a new break is indistinguishable from an old one. Three clusters, three decisions:

| Cluster | Count | Decision |
|---|--:|---|
| `min_cohort_n: 1` + synthetic fallback vs. tests expecting refusal | 8 | **Move the tests.** Re-assert against `min_cohort_n: 1` and add `test_min_cohort_n_demo_setting_is_deliberate`. E11 changes the threshold properly, with a seeded pool behind it |
| `_derive_cohort` sector→`technology`, employee→`medium` fallback | 6 | **Move the tests.** Document current behaviour; revisit at E11 |
| `test_actions.py:38` asserts **54** bands, actual is **57** | 1 | Update to 57, with a comment saying it is a tripwire and must be changed deliberately |

**E0.2 — Extend the corpus.** It is 5 vendors, all large, all A/B. It cannot see a regression that only affects small vendors, low scorers or Ghosts. Add at minimum: one Ghost (confidence < 0.4), one gated vendor, one small vendor, one bottom-quartile scorer.

**E0.3 — Run the discrimination analysis on the seeded pool.** No outcome labels required, roughly a day's work, and it is the highest-value diagnostic available. Measured on the current 5-vendor corpus:

| Finding | Detail |
|---|---|
| **6 signals penalise 100% of vendors** | `stale_hosts` `contactability` `weak_issuance` `subdomain_estate` `cert_posture` `vd_program` — **≥28 category-points ≈ 7 posture points of flat tax** |
| **12 signals are constant-pass** | `tls_version` `cert_validity` `hsts` `x_frame_opts` `dmarc` `dkim` `breach_by_data_class` `domain_registration` `entity_existence` `regulator_action` `program_disclosure` `reporting_posture` |
| **1 signal never fires** | `entity_maturity` — which is *also* the Confidence assurance signal, so that mechanism is inert |
| **Net** | **19 of 27 contribute nothing to ordering.** Only 8 discriminate |

Re-run across the 115 seeded vendors before E5 fixes category boundaries.

**E0.4 — Build the outcome label set.** There is no ground truth anywhere in the repo, so no AUC, calibration or ablation is executable today. Join the seeded pool against HIBP / KEV / regulator actions → `backend/tests/fixtures/outcome_labels.json`.

> **Disclose the bias on the artefact.** Public-breach labels over-represent large, scrutinised companies — the exact bias the model exists to remove. AUC is therefore a lower bound with a known lean, not a verdict.

**E0.5 — Freeze the baseline.**
```bash
python -m tests.regolden
git diff --exit-code tests/fixtures/golden_scores.json   # MUST be empty
```

### Exit criteria — ✅ **all 5 met** (four done, one deliberately deferred)
- [x] `pytest -q` green — **577 passed, 0 failed**
- [x] **Corpus extended** — five archetypes added, built by [build_archetypes.py](../backend/tests/build_archetypes.py) and constructed rather than captured, each unmistakably labelled: `synthetic_ghost` (refused) · `synthetic_gated` (blocked) · `synthetic_smallco` (the E2 fairness case) · `synthetic_weak` (the ceiling biting) · `synthetic_floor` (the bottom of the scale). Corpus range went **74–87 → 16–96**
- [x] **Discrimination analysis run and committed** — [discrimination-analysis.md](discrimination-analysis.md), regenerated by `python -m tests.analyse_discrimination`, reusing EB's `discrimination.py` rather than a second implementation. ⚠️ **The seeded-pool run is still outstanding** and is tracked under E11; what is committed is the corpus run, with that limit stated on the artefact
- [x] **`outcome_labels.json`** — **explicitly deferred in writing**, which is what this criterion permits: [e0.4-outcome-labels-deferral.md](e0.4-outcome-labels-deferral.md). Scheduled as the immediate successor to E11
- [x] `regolden` reproduces the committed golden file byte-for-byte

> **E0.2 was a prerequisite for E0.3 that no plan recorded.** The discrimination test requires
> `min_observations: 8`; the corpus published **5** vendors. E0.3 was therefore not merely
> unstarted — it was **unrunnable**, and would have returned `untested` for every signal. The
> status table read "◑ the instrument now exists" without anyone checking the instrument had
> enough input to say anything.

> **What E0.4's deferral costs, stated rather than minimised.** Every phase from E1 to E13 changes
> the model with no way to tell whether it *improved* it. The corpus diff proves a change was
> intended and localised; it cannot prove the model got better. **The scores are defensible and
> explainable, and their predictive accuracy is unmeasured.** E13 is explicitly blocked on this.

### Stop and reconsider if
Firmographics-only R² exceeds ~0.5. That means the score is largely a size-and-sector classifier, and E6 becomes urgent rather than important.

---

## E1 · Remove the sector opinion from the arithmetic

**1 week · Risk: low · Changes scores: ≈0 on corpus**

### Customer outcome
The score stops meaning something different depending on which industry we filed the vendor under. A bank and a farm supplier with identical evidence get identical Posture — and the sector obligation reappears, properly, as a **Compliance Gap** finding in E9.

### Why
This is mechanism #10, *dynamic severity adjustment* — the one adjustment every commercial platform declines to implement. It also puts `scoring.yaml` in direct contradiction with `benchmarks.yaml`, which says interpretation lives in benchmarking and never in the arithmetic. **The two files currently disagree.**

### Steps

1. **`scoring.yaml`** — delete the `industry_profiles:` block, [lines 661–685](../scoring.yaml#L661)
2. **`scoring_config.py`** — remove `industry_profiles()`, `industry_profile()`, `promote_severity()` (lines 242–266), `_validate_industry_profiles()` (line 390) and its call at line 326
3. **⚠️ Trap** — remove `"industry_profiles"` from `_ENGINE_READS` (line 54). Delete the code but leave the YAML and the loader raises *"declares key(s) nothing reads"* — the app will not start
4. **`normalize.py:121`** — drop the `promote_severity` call
5. **`engine.py:219`** — `industry_profile=None`; strip the promotion contract from the docstring at lines 62–67
6. **`pipeline.py:199`** — remove the `industry_profile` progress field
7. **Keep** `NormalizedFinding.base_severity` / `.promoted_by` for one release so stored receipts still deserialise. Mark deprecated with a removal release
8. **Copy both `basis:` strings verbatim** into the E9 backlog now — APRA CPS 234 / CPS 230, and Privacy Act APP 11 / My Health Records Act / OAIC NDB. They become Compliance Gap frameworks

### Tests to write first
```python
def test_sector_never_changes_a_severity():
    """Identical findings scored against every sector produce an identical Score."""

def test_scoring_yaml_declares_no_industry_profiles():
    """The block is gone from config, not merely unread."""
```

### Expected corpus movement
**Zero.** No corpus vendor carries a sector at fixture-score time. If anything moves, you removed more than promotions — stop and read the diff.

### Exit criteria — ✅ all met (`817d7da`)
- [x] Loader boots — `OK 5.0.0 signals 27 bands 36 divisor 2.86 cats 7`, and `industry_profiles` is absent from both the YAML and `_ENGINE_READS`
- [x] `golden_scores.json` diff is empty — `6752556` → `817d7da` moved no vendor by a single point, exactly as predicted
- [x] Both `basis:` strings captured — [compliance-gap-frameworks.md](compliance-gap-frameworks.md) holds APRA CPS 234/230 and Privacy Act APP 11 / My Health Records Act / OAIC NDB verbatim

---

## E2 · Stop penalising the norm

**1–2 weeks · Risk: low · Changes scores: yes · ✅ CODE LANDED, uncommitted · exit criterion open**

### Customer outcome
We stop charging vendors for not doing what almost nobody does. A small vendor without DNSSEC, CAA or a `security.txt` file is no longer marked down for behaving like 90%+ of the internet. **This is the single biggest fairness fix for smaller suppliers.**

### The mechanism, and why it is not "bonus" yet
The engine has **no bonus path** — `penalty_for` returns 0 or positive, never negative. So E2 sets bands to `informational`, which:
- costs nothing to implement (already supported)
- keeps the signal in `covered_by_cat`, so `planned_signal_count()` stays 27 and **confidence does not move**
- is fully reversible

Positive credit is **E9b**, after Assurity exists.

### Bands to reclassify — eight, as shipped

An earlier revision of this table listed six. It missed the intermediate bands of two signals: if
`program_disclosure.none` stops penalising but `program_disclosure.marketing_only` does not, a vendor
with a *thin* trust page is charged where a vendor with *no* page is not. Reclassifying a signal means
reclassifying every band of it that penalises absence.

| Signal | Now | → | Base-rate justification |
|---|---|---|---|
| `dnssec.absent` | low | `informational` | 7–18% adoption |
| `caa.absent` | low | `informational` | ~1.6% adoption |
| `security_txt.absent` | low | `informational` | <0.25% of domains |
| `program_disclosure.none` | medium | `informational` | Measures go-to-market motion, not governance |
| `program_disclosure.marketing_only` | low | `informational` | Same signal, intermediate band |
| `cert_posture.none_claimed` | medium | `informational` | A tax on audit budget |
| `reporting_posture.none` | medium | `informational` | Private SMBs cannot produce it at all |
| `reporting_posture.partial` | low | `informational` | Same signal, intermediate band |

**Result: 57 → 49 penalising bands.** `planned_signal_count()` holds at 27 and the divisor at 4.0, so
confidence is unmoved — verified.

### The consequence nobody scheduled: prevalence had to change too

E2 pulled apart two questions that used to coincide, and [benchmark.py](../backend/app/benchmark.py)
`_is_pass` is where they separate:

| Question | Who asks it |
|---|---|
| *Does this band cost points?* | The scoring engine |
| *Does the vendor HAVE the control?* | Peer prevalence |

Before E2 every absence penalised, so *"not penalised"* meant *"present"*. After E2 it does not.
Counting `informational` as a pass made every peer "have" DNSSEC, so nobody was ever ahead or behind
on it — and the sharpest line the benchmark produces (*"you are ahead of 85% of your peers"*) vanished
for **precisely the low-base-rate controls where it is most worth saying.**

`None` — a band the scoring model does not list at all — still reads as a pass. Never tell a vendor
they lack a control we do not model.

> **Generalise this before E3, E4 and E9.** Every phase that reclassifies or relocates a signal
> re-opens the same question: *which consumer of this band meant "costs points" and which meant "has
> the control"?* E4 will hit it again when going-concern signals leave Posture but must still appear
> in Continuity.

### Steps — per band, all four in ONE commit

1. `scoring.yaml` `categories:` — set the band to `informational`
2. **⚠️ `reasons:` — delete the entry.** An orphan raises `ScoringConfigError` at load
3. **⚠️ `actions:` — delete the entry.** Same failure mode
4. Update the `test_actions.py` band count

> A commit that changes the band but not `reasons:` leaves the tree unbootable. Bisecting through it later is miserable.

### Tests
```python
def test_planned_signal_count_is_unchanged_by_reclassification():
    assert get_scoring_config().planned_signal_count() == 27

def test_corpus_confidence_is_unmoved():
    """Posture may move in E2. Confidence may not."""
```

### Expected corpus movement
All five vendors gain. `cert_posture` fires on 5 of 5 today.

### Exit criteria — ✅ all met (`0bf38f7`)
- [x] `planned_signal_count() == 27` — `test_confidence_denominator_is_unmoved_by_reclassification`
- [x] Corpus confidence distribution unmoved — asserted, not eyeballed: confidence is a field in the frozen `golden_scores.json`, so `test_corpus` fails on any movement. Measured across the whole migration it has not moved once (0.963 / 0.926 / 0.963 / 0.926 / 0.926, baseline → v5.0.0)
- [x] Every reclassified signal still appears in the receipt, marked informational, never silently dropped — verified against all five fixtures: 9–10 of the eleven reclassified signals present per vendor, **zero** reclassified band carrying a penalty. The only penalty left on any of those signals is `cert_posture.claimed_unverified` (3.0, on 4 of 5), which is deliberate — it charges for asserting a certification that does not check out, not for lacking one
- [x] Corpus re-goldened with a written justification per moved vendor — in the commit body, per vendor, naming the category that moved

---

## E3 · Merge the duplicate transparency signals

**0.5 weeks · Risk: low · Changes scores: yes**

### Customer outcome
One fact is charged once. Today a published security contact is counted three times — via `security_txt`, `contactability` and `vd_program` — which quietly makes governance heavier than any deliberate decision made it.

### The evidence it is duplicated
[headers_collector.py:73-84](../backend/app/collectors/headers_collector.py#L73-L84) emits **both** `security_txt` *and* `vd_program` from the single `security.txt` observation, and says so in a comment.

### Steps
1. Remove `contactability` from `categories.vendor_transparency_gov`, plus its `reasons:` and `actions:`
2. Stop emitting it from `trust_collector.py`
3. **Recommended:** keep `contactability` as an `informational` signal rather than deleting it. `planned_signal_count()` stays 27, confidence does not move, and the evidence that the check ran is preserved. Deleting it drops 27 → 26 and raises every vendor's confidence for no evidential reason

### Exit criteria — ✅ both met (`5412236`)
- [x] One fact, one charge — `test_the_contact_disclosure_fact_is_charged_exactly_once` asserts that of `security_txt` / `contactability` / `vd_program`, **exactly** `vd_program` charges. It is the one the report credits with a causal mechanism: a vendor with no disclosure path cannot be *told* about a vulnerability
- [x] Denominator movement **avoided**, per step 3. `contactability` is still emitted by `trust_collector.py:105` and still counts toward coverage; `planned_signal_count()` held at 27

> **Step 2 was deliberately not executed.** "Stop emitting it from `trust_collector.py`" contradicts
> step 3's recommendation — keeping the signal informational only works if the collector keeps
> emitting it, otherwise coverage drops and every vendor's confidence rises for no evidential reason.
> Step 3 wins; step 2 is a leftover from the delete-it variant of this phase.

---

## E4 · Relocate going-concern to Continuity

**1 week · Risk: low · Changes scores: yes — removes ~20 misplaced points**

### Customer outcome
**A vendor entering administration stops being reported as having worse TLS.** Insolvency becomes what procurement actually needs — a cited going-concern flag with a retrieval date — instead of a 20-point deduction from a *technical security* score.

This is the clearest category error left in the model, and the easiest one to explain to a sponsor.

### What is wrong today, measured

| Signal | Band | Penalty | What it really measures |
|---|---|--:|---|
| `entity_status` | `entity_inactive` | **20.0** | Companies House maps `liquidation`, `receivership`, `administration`, `insolvency-proceedings` here |
| `entity_status` | `registration_lapsed` | 3.0 | Fires on **myob** and **slack** |
| `entity_existence` | `entity_dissolved` | 20.0 | Going-concern, not security |
| `entity_maturity` | `young_2_5` / `startup_lt_2` / `new_lt_1` | 3.0 | **Founding date** — which the plan's own "does not do" table forbids |
| `domain_registration` | `domain_recent` / `domain_new` | 3.0 | Company-age proxy. Already tagged `subcategory="business_continuity"` |

**This is a relocation, not a build.** Signals and collectors exist; only the destination is new.

### Steps

1. Move the four signals out of `categories.business_financial_stability`, with their `reasons:`/`actions:`
2. **⚠️ Category count 7 → 6.** With `penalty_divisor` 4.0, six categories cap at 600; 600/4 = 150, so posture still reaches 0. **Safe — but verify, and see E5 if more categories move**
3. **⚠️ `planned_signal_count()` 27 → 23.** Every vendor's confidence rises for no evidential reason. Either disclose it, or ship **per-axis confidence** (Posture confidence over its own signals, Continuity over its own) — the more honest option and a prerequisite if further categories relocate
4. **Emit as registry-cited flags, never a 0–100 axis:**
   > *"In administration — Companies House company status, retrieved 2026-07-29."*
5. **`entity_maturity` is also the Confidence assurance signal.** Removing the penalty leaves the multiplier — which is where [engine.py:169-171](../backend/app/scoring/engine.py#L169-L171) always said age belonged. Confirm the multiplier still resolves
6. **E8 collision:** `entity_dissolved` is slated to become a **gate**. Recommended split — gate for `dissolved`, Continuity flag for `lapsed` / `administration`

### Why flags and not a score
1. The research says these signals must *leave* Posture; it does not specify an arithmetic to replace them. A score would be invention wearing the report's authority
2. Four registry bands cannot support hundred-point precision
3. A cited register fact carries the same legal footing as any other published observation. A **derived** distress index is credit-rating territory and defamation-adjacent when wrong

### Tests
```python
def test_administration_does_not_reduce_posture():
def test_company_age_never_reaches_a_penalty():
def test_continuity_flags_carry_a_citation_and_a_retrieval_date():
```

### Exit criteria — ✅ all met (`1c500fa`)
- [x] No going-concern signal carries a posture penalty — `test_no_going_concern_signal_carries_a_posture_penalty`, asserted against the shipped config
- [x] Every Continuity flag carries a source and retrieval date — `test_every_flag_carries_a_citation_and_a_retrieval_date`, which also requires the evidence id
- [x] Confidence denominator change **avoided, not merely disclosed** — the plan predicted 27 → 23; the four signals were relocated rather than deleted, so it held at 27 and no vendor's confidence moved
- [x] myob and slack gain — **but 3 *category* points, which is +1 posture, not +3.** Verified: `business_financial_stability` 3.0 → 0.0 on exactly those two (the `registration_lapsed` holders), and 0.0 → 0.0 on the other three. At the then-current divisor of 4.0, 3 ÷ 4 = 0.75, so both posted 90 → 91 and 86 → 87. **The criterion as written confuses category points with posture points**; the prediction was right about which vendors and which band, wrong about the magnitude by the divisor

---

## E5 · Consolidate categories + recalibrate the divisor

**1–2 weeks · Risk: medium · Changes scores: everywhere · Blocked on E2 + E4**

### Customer outcome
"Posture" becomes definable in one sentence — *how exposed is this vendor to compromise* — which is what you need when a client asks why a company in administration didn't score lower. Everything else moved to an axis that names itself honestly.

### Target category set — all 27 signals accounted for

| Category | Signals | n |
|---|---|--:|
| Breach & Compromise | `breach_by_data_class` `kev_listed_cve` `nvd_cve` | 3 |
| Attack Surface & Hygiene | `tls_version` `cert_validity` `hsts` `csp` `x_frame_opts` `stale_hosts` `weak_issuance` | 7 |
| Identity & Email | `dmarc` `spf` `dkim` | 3 |
| Transparency | `vd_program` `security_txt` | 2 |
| Regulatory | `regulator_action` | 1 |

**16 scored · 1 denominator (`subdomain_estate`) · 2 informational (`dnssec`, `caa`) · 8 relocated = 27.** Verified: nothing unaccounted, nothing invented.

### The divisor — derive it, never guess

`penalty_divisor` is **4.0**, tuned against seven categories. Leaving it fixed while shrinking the category count makes the model **more forgiving**, because a larger *fraction* must fail before the score bottoms out.

```
divisor(n) = n × (4 / 7)      # holds maximum damage at 175 posture points
```

| Categories | Divisor | Floors at |
|--:|--:|--:|
| 7 (today) | 4.00 | 0 |
| **5 (target)** | **2.86** | 0 |
| 4 | 2.29 | 0 |
| **3 with divisor left at 4.0** | 4.00 | **25** ✗ |

**Ship the divisor in the same commit as the restructure.** A category move without it silently re-scores every vendor for an invisible reason.

### Two traps

**⚠️ No signal in two categories.** The engine keys on `(category, signal)` and charges duplicates twice. The two that tempt duplication: `stale_hosts` (surface *and* footprint → category 2 only) and `kev_listed_cve` (breach *and* vulnerability → category 1 only; splitting it also breaks E7's KEV precedence rule).

**⚠️ Every category must keep ≥1 penalising band.** Two are fragile:

| Category | Risk |
|---|---|
| **Transparency** | `security_txt` goes informational in E2, leaving only `vd_program` — which penalises **100% of the corpus** and is itself a reclassification candidate |
| **Regulatory** | `regulator_action` awaits the cyber / non-cyber decision. If it relocates, the category disappears and the divisor moves to 2.29 |

### The decision E5 forces
`regulator_action` does **not** distinguish cyber from non-cyber enforcement. A regulator sanctioning a vendor over a data breach is security evidence; one sanctioning them over consumer-credit conduct is not.

1. **Tag cyber-relevance in `regulatory_collector`** — most correct, most work · **recommended**
2. Keep as-is and accept non-cyber enforcement scoring as security risk — cheapest, and wrong in a way a vendor will dispute
3. Relocate the whole signal → Posture drops to 4 categories, divisor 2.29

**Do not default to (2) by omission.**

### Tests
```python
def test_no_signal_appears_in_two_categories():
def test_every_category_has_at_least_one_penalising_band():
def test_divisor_preserves_maximum_damage():
    n = len(cfg.category_names())
    assert abs((n * 100) / cfg.penalty_divisor() - 175) < 1.0
```

### Exit criteria — ✅ all met
- [x] Five scoring categories (+2 context), **18** scored signals, no duplicates — deviation from the planned 16 recorded above and in the change notice
- [x] `penalty_divisor` = **2.86** · verified `5 × 100 / 2.86 = 174.8` against the 175 target
- [x] `regulator_action` decision recorded in writing — **option 2 chosen explicitly**: keep in Compliance & Regulatory, accept the cyber/non-cyber defect for now. Grounds in `scoring.yaml` and pinned by `test_regulator_action_cyber_relevance_is_a_recorded_open_item`, which is written to FAIL once E9c's tagging lands
- [x] **No category weights introduced**
- [x] Corpus re-goldened; model bumped **4.2.0 → 5.0.0** with [change-notice-v5.md](change-notice-v5.md) covering per-vendor movement, the Slack B→A→B grade excursion, and what a holder of a v4.x report must do

---

## E6 · Exposure denominator — the free half ✅ DELIVERED

**1 week · Risk: medium · Changes scores: yes · Landed 2026-07-31 as v5.1.0**

### Customer outcome
We stop measuring how big a vendor is and start measuring how well they run. Today a 900-host vendor with 6 stale hosts is scored identically to a 6-host vendor with 6 stale hosts — and `digital_footprint_assets` is the **largest or second-largest penalty for all five corpus vendors**. This is the defect a sophisticated buyer will spot first.

### Why this half is free
`stale_hosts ÷ subdomain_estate` needs no new collection. Both come from the same `ct_collector` call and both already carry raw counts.

### Tests to write FIRST — they must fail against v4.2.0
```python
def test_large_estate_with_low_stale_rate_beats_small_estate_with_high_rate():
    #   Vendor A:   4 hosts, 2 stale →  50%
    #   Vendor B: 900 hosts, 9 stale →   1%
    # Before: A −16, B −72 (B worse, wrongly, by ~4.5×).  After: A worse than B.

def test_one_of_one_failure_is_not_scored_as_one_hundred_percent():
def test_a_single_severe_finding_is_not_diluted_by_a_large_estate():
```

### Steps
1. Create `backend/app/scoring/exposure.py` — pure functions, no config reads, same discipline as `modifiers.py`:
   ```
   r̂_s = (f_s + α_s) / (D_s + α_s + β_s)          # beta-binomial posterior mean
   g_s = λ_s·r̂_s + (1 − λ_s)·min(1, f_s/κ_s)      # rate blended with an absolute floor
   ```
   `α/β` stop 1-of-1 reading as 100%. `κ_s` stops a large vendor diluting a severe finding to nothing
2. `ct_collector.py` — add `"denominator": len(subdomains)` to the `stale_hosts` finding's `value`. One line, no new network calls
3. Add `denominator: int | None` to `NormalizedFinding`
4. Retire `count_bands` for `stale_hosts`; add an `exposure:` block to `scoring.yaml`
5. **⚠️ Trap** — add `"exposure"` to `_ENGINE_READS` in the same commit
6. `subdomain_estate` → informational, becomes denominator only; keep it in the signal list so the count holds at 27
7. Remove `stale_hosts` from `_COUNT_SIGNALS` (`normalize.py:26`)

### Dispute-machinery interaction
`_apply_dispute` keys on `(signal, band_key)`. A rate-derived band may no longer be a stable string. Check it, and **extend disputes to cover denominator challenges** — *"you counted 340 hosts, we operate 40"* is the dispute this phase invites and there is currently no way to file it.

### Exit criteria — ✅ all met
- [x] A/B inversion test passes, and demonstrably failed before — `test_large_estate_with_low_stale_rate_beats_small_estate_with_high_rate`. A (2 of 4) now charges 20 and B (9 of 900) charges 8; before E6 it was 8 and 20
- [x] Footprint penalty falls for the large corpus vendors, per-vendor justification written — [change-notice-v5.md §7](change-notice-v5.md#7-v510--the-exposure-denominator-e6). slack +4 (**B → A**), onetrust +5, snowflake +3, atlassian +1, myob +1. Snowflake is the control: 119 of 211 stale is 56% and stays `many` at the full −20, so this is not "large vendors gain"
- [x] Kept behind `exposure.enabled` — and it is a **true** revert, not a deletion: `stale_hosts` left `count_bands:`, so the old thresholds are preserved under `fallback_count_bands`. Without that, switching off would have sent the signal to the plain-band path where its observed string matches nothing and it would silently stop scoring. Pinned by `test_disabling_exposure_restores_the_pre_e6_bands`
- [x] **Denominator published** — `denominator` and `exposure_index` on every finding, `"5 of 4,326 names look stale/dev/staging"` in the observed string, and all three `accepts_as_refute` entries invite the correction. A corrected denominator changes the **band**, not just the wording (`test_a_corrected_denominator_changes_the_band`)

### What E6 added that the plan did not anticipate
- **A fourth band.** `negligible` (low, −3) is where a large well-kept estate lands. Without it slack's 5-of-4,326 paid the same 8 points as a vendor with 5 of 20, and the phase would have delivered half its own argument
- **Denominator resolution from the SIBLING finding**, not from a field on the finding itself. The five real fixtures were captured before E6 and carry no `denominator` key — requiring one would have meant re-capturing evidence to satisfy a config change, which is what a frozen corpus exists to prevent. `ct_collector` emits it too, so new receipts are self-contained
- **Zero short-circuits before the arithmetic.** With a prior, zero observed failures still yields a positive rate (3.6% for a 4-host vendor). Charging a vendor for a finding of zero is indefensible

### Dispute-machinery interaction — checked
`_apply_dispute` keys on `(signal, band_key)`. Band keys remain stable strings (`none` · `negligible` · `some` · `many`), so existing disputes still match — asserted by `test_band_keys_stay_stable_strings_for_the_dispute_machinery`. Denominator challenges are carried in `accepts_as_refute` text rather than as a new dispute *kind*; a structured denominator-override dispute is worth building at P3, where the Evidence Request Pack is the thing that will actually solicit the correction.

---

## E7 · Aggregation + severity ladder

**2–3 weeks · Risk: medium · Changes scores: yes**

### Customer outcome
One actively-exploited vulnerability stops being outranked by a dozen missing HTTP headers. Today twelve hygiene failures (56 points) beat one Critical KEV (40). That inversion is indefensible in front of a security team.

### These two ship together — computed, not quoted

| Configuration | 4 Medium + 8 Low | vs. 1 Critical | Ratio |
|---|--:|--:|--:|
| **Current** (flat 8/3) | 56.00 | 40 | 0.71 : 1 ✗ *trivia wins* |
| Diminishing returns only | 22.53 | 40 | 1.78 : 1 |
| Ladder only | 36.00 | 50 | 1.39 : 1 |
| **Both** | **16.33** | 50 | **3.06 : 1** ✅ |

**Neither half alone reaches the target.** Shipping them separately publishes an intermediate state that satisfies no one.

### E7a — Diminishing returns within category
```
CategoryPenalty(c) = Σᵢ pᵢ · λ^(rankᵢ − 1)      λ = 0.7, rank by descending pᵢ
```

**Structural change:** [engine.py:143](../backend/app/scoring/engine.py#L143) accumulates inside the per-`(cat, sig)` loop. Diminishing returns needs *all* of a category's penalties before ranking. Restructure to collect then transform after the loop closes.

> ⚠️ **Preserve `rep.effective_penalty`.** It must be the **post-discount** value or stored receipts stop reconciling — the exact defect those fields exist to prevent.

**⚠️ Trap** — `aggregation` is currently in `_DOCUMENTATION_ONLY`. **Move it to `_ENGINE_READS`**, or you get a live-looking rule that scores nothing.

### E7b — Widen the ladder

| Level | Now | After |
|---|--:|--:|
| Critical | 40 | **50** |
| High | 20 | 20 |
| Medium | 8 | **6** |
| Low | 3 | **1.5** |

Critical:Low moves **13.3:1 → 33.3:1**. `low: 1.5` is a float — check tests asserting integer penalties.

### E7c — Root-cause deduplication
> **One remediation ticket, one penalty.**

KEV > EPSS > CVSS, one penalty · score the TLS protocol finding, ciphers only add beyond it · CSP `frame-ancestors` satisfies XFO · one footprint model. Model as a `root_cause:` map in config, not a hardcoded set.

### E7d — Ghost ceiling ramp (cheap, ship here)
```
< 40%   → no publish; "Insufficient Evidence" — explicitly ADVERSE
40–60%  → ceiling 80      60–75% → ceiling 90
75–90%  → ceiling 97      ≥ 90%  → ceiling 100
```
The `<40%` rung already exists (`refuse_below: 0.4`). What is new is the graduated ceiling and the adverse framing. **Check the frontend renders it as adverse** — grey is not adverse.

### Tests
```python
def test_one_critical_kev_outranks_twelve_hygiene_failures():   # assert ≥ 3:1
def test_monotonicity_remediation_never_loses_points():          # GENERATED inputs, not 3 cases
def test_effective_penalty_sums_to_the_published_category_penalty():
```

Monotonicity is the property most likely to break silently and least likely to be caught by a 5-vendor corpus. **Write it with generated inputs.**

### Exit criteria — ✅ all met (`501e995`, frontend closed 2026-07-31)

- [x] **Severity beats volume, computed** — 1 Critical vs 4 Medium + 8 Low reaches **3.06 : 1**, up from 0.71 : 1. Both halves shipped together because neither reaches the target alone (discount only 1.78 : 1, ladder only 1.39 : 1) — `test_one_critical_kev_outranks_twelve_hygiene_failures`
- [x] Monotonicity holds under **generated** inputs, not three hand-picked cases — `test_monotonicity_remediation_never_loses_points`
- [x] `effective_penalty` is the **post-discount** value and reconciles to the published category penalty — `test_effective_penalty_sums_to_the_published_category_penalty`
- [x] `aggregation` moved from `_DOCUMENTATION_ONLY` to `_ENGINE_READS` — the trap the phase text called out; a live-looking rule that scored nothing
- [x] Root-cause dedup is a `root_cause:` map in config, not a hardcoded set — two rule kinds (`precedence`, `satisfied_by`), and a suppressed finding carries the SENTENCE saying why, because *"we saw this and did not charge for it"* is a different statement from *"we did not see it"*
- [x] **The frontend renders insufficient evidence as adverse.** ⚠️ *This was NOT met when E7 was marked complete* — see below

> **The one criterion E7 shipped without.** `RefusedCard` used `bg-secondary`: the same neutral
> chrome the UI uses for *not applicable* and *no data yet*. The phase text says it in four words —
> **grey is not adverse** — and it was the last line of the sub-phase, below the ceiling table,
> which is how it got missed. Grey is the visual language of *nothing happened*, so a reader
> skimming a portfolio reads a Ghost as an incomplete row rather than a result. That is precisely
> the misreading the Ghost mechanic exists to prevent, and it is what makes **hiding better than
> being average** — the same defect E13 is being written to fix in the arithmetic, live in the
> rendering. Now drawn in the amber register with an explicit *"adverse result"* label and the
> action a reader should take. Held by `test_insufficient_evidence_is_rendered_as_adverse_and_not_as_grey`.
>
> **A second gap found in the same pass, which the criteria did not name.** The graduated ceiling
> was applied but **invisible**: `confidence_ceiling_applied` was set on the model, published on no
> route, and rendered nowhere. A vendor whose arithmetic earned 94 and published 80 was
> indistinguishable from one that earned 80 — but the first is a limit on *our* evidence and the
> second is a finding about *their* controls, and only one is remediable by patching something.
> Now on the `/explain` receipt (where `computed_posture` and `published_posture` differ and the
> reader had no way to see which ceiling moved it) and on the card, **in a different palette from
> the critical ceiling** — that one is adverse to the vendor, this one is a limit on us, and
> sharing a colour would have readers blaming the vendor for our coverage.

---

## E8 · Hard gates

**1 week · Risk: low · Changes scores: no — changes outcomes**

### Customer outcome
Some findings stop being negotiable. A vendor with an actively-exploited internet-facing vulnerability currently publishes at 60 and clears a "≥50" procurement threshold. After E8 it publishes **nothing** and routes to a human.

### Steps
1. Generalise the two inline gates (`entity_ambiguous`, `sanctions`) into a config-driven `gates:` pass over normalized findings
2. Add four, each with a named basis: **KEV past CISA due date** on an internet-facing data-bearing asset *(check `kev_collector` carries the due date — it may not)* · **entity dissolved / struck off** · **no valid TLS on a data-bearing endpoint** · **ownership unresolvable**
3. **⚠️ Preserve the sanctions invariant.** `_validate` hard-codes `gates.sanctions.behaviour == "block"` — a legal position (s16(7)), not a default
4. Add `_validate_gates` requiring a non-empty `basis` per gate — the validation discipline `industry_profiles` had was right even though the mechanism was wrong
5. Route gated vendors to adjudication. Confirm `posture=None` renders distinctly from `posture=0`

### Exit criteria — ✅ all met (`6229356`, UI verified 2026-07-31)

- [x] **Each gate has a named basis, enforced at load** — `_validate_gates` requires ≥40 chars, and a disabled gate must additionally state `disabled_because`. A gate stops a company being onboarded; it must never be possible to add one without a reason someone can be shown
- [x] **Gated vendors route to adjudication, not a low score** — `posture=None`, `grade=None`, `blocked=True`, with the reason on the record. A renderer keying on `blocked` gets the right answer before it reads `posture`
- [x] **Visually distinct from a zero-scoring vendor** — verified in the tree, not assumed. `Scorecard.jsx` branches on `blocked` and then `refused` **before** reaching the scored path, so the three no-number states are three different components rather than one component in three colours. Held by `test_the_three_no_number_states_render_as_three_different_things`

**Only one of the four proposed gates ships live, and the reasons are evidence, not policy.**

| Gate | State | Why |
|---|---|---|
| `entity_dissolved` | **live** | Registry fact. No legal personality, unambiguous |
| `kev_overdue` | declared, **off** | `kev_listed_cve` is a keyword match against a **product line**, not this vendor's deployed version. Blocking onboarding on a name match is the most damaging false positive this system could produce. The trigger is built and CISA's due date is already collected — the evidence is E12 |
| `no_valid_tls` | declared, **off** | "Data-bearing" is not observable; we handshake the apex once. The critical ceiling is already proportionate |
| `ownership_unresolvable` | **not a gate** | It *is* `entity_ambiguous`. A second gate for one fact is E3's double-count, one layer up |

> **The three no-number states mean three different things**, and collapsing any two puts a vendor
> in the wrong queue: `blocked` is *we will not score this* (adjudicate) · `refused` is *we cannot
> score this* (adverse, request evidence) · a low score is *we scored it and the number is low* (a
> measurement). The same evidence bar set here was later applied across the whole compliance
> library at E9c — no framework rests a control on `kev_listed_cve` either.

---

## E9 · Assurity + Compliance Gap

**3–4 weeks · Risk: low · Changes scores: no**

### Customer outcome
Two things a buyer asks that we cannot currently answer:
- *"How much independent assurance does this vendor actually have?"* → **Assurity**
- *"Do their claims match reality?"* → **Compliance Gap**: *"Asserts PCI DSS, negotiates TLS 1.0."* That is a finding about the reliability of their own attestations, and it is high-signal precisely because gaming it means dropping the claim.

### E9a — Assurity
```
Assurity = 100 · σ( A₀ + Σ_j v_j · valid_j · scope_j − Σ_k γ_k · ComplianceGap_k )
```
**Absence never subtracts.** A vendor with no certifications has low Assurity, not bad Posture.

Read [targets.py:1-30](../backend/app/targets.py#L1-L30) first — it already articulates the three disciplines: a signal never *checked* is not a signal *failed* · a control that could not yet exist at this vendor's age leaves the denominator and is **disclosed by name** · below `min_controls`, publish nothing.

### E9b — Positive credit (0.5 wk, blocked on E9a)
The six signals parked at `informational` in E2 gain positive credit. Purely additive; Posture untouched.

### E9c — Compliance Gap
Where a vendor asserts or is bound by framework `F` and is observed failing control `c ∈ C(F)`, emit a cited finding. **This is where E1's deleted sector expectation lands** — both `basis:` strings become framework definitions.

### Exit criteria — ✅ all met (`6229356` + `c8ed801`)

*This phase shipped without a criteria list. These are derived from the phase text above and each
was verified against the tree on 2026-07-31, not carried forward from a status table.*

- [x] **Assurity published as a third axis, 0–100, bounded and never pinned** — `app/assurity.py`, `GET /api/vendors/{ref}/assurity`. The sigmoid keeps resolving at both extremes, which is the compression defect E13 exists to fix for Posture, avoided here by construction
- [x] **Absence never subtracts — enforced at load, not merely intended.** `_validate_assurity` rejects a negative credit. Without it, E2's audit-budget tax returns one axis over where nobody is watching for it
- [x] **Below `min_observed_signals` we publish nothing** — the `targets.py` discipline carried across. *"2 of 3"* assembled from whichever checks returned is the same false precision as a median over three peers
- [x] **Assurity cannot move Posture — structurally.** The engine never imports it; asserted by reading its source, not by comparing outputs
- [x] **E9b: every signal E2 parked at `informational` now earns** — and the ones that do not are the boundary: `subdomain_estate` is a denominator (E6), and the four continuity signals are E4's going-concern question. Crediting those would make Assurity a second, quieter solvency score. `test_every_signal_e2_parked_at_informational_gained_positive_credit`
- [x] **E9c: the sector obligation returns as a cited finding, and changes no arithmetic** — same evidence, same score, in every sector. `sector` reaches only `compliance_gaps()`; `test_sector_never_changes_a_severity` holds the engine boundary
- [x] **Every framework names a real, dated instrument** — `basis` ≥40 chars enforced at load, and every shipped one cites paragraph or requirement numbers
- [x] **Nine frameworks declared, eight assessed** — Tier 1 and Tier 2 both closed at `c8ed801`; see [e9c-framework-roadmap.md](e9c-framework-roadmap.md)

> **A live defect was found while closing this phase, and it had shipped.** `cert_posture` bands
> say `claimed_unverified` — they do not say *which* standard was claimed, and `asserted_by`
> matched on the band alone. A vendor whose trust page said **SOC 2 and nothing else** was
> published as *"asserts ISO/IEC 27001:2022, observed failing A.8.24."* That is us putting a claim
> in a named third party's mouth and then finding them short against it — the `industry_profiles`
> failure one layer over, and the more damaging half, because a false compliance assertion about a
> real company is the sort of thing that ends up in front of their lawyer. Adding PCI DSS and SOC 2
> would have tripled it. Fixed by `claim_contains`, **required at load**, and resolved from the
> `observed` string rather than a new field — so it works on a stored `PersistedFinding` and needs
> no fixture re-capture, the same choice E6 made for the exposure denominator.
>
> **A second, quieter one in the arithmetic.** Assurity charged `gap_count`, so a vendor asserting
> three frameworks and failing TLS once paid 3γ for one fact — meaning the axis **punished a vendor
> for publishing more certifications**, inverting what it measures. Now charges
> `distinct_observations`. All three gaps are still reported; they are three genuine
> claim-reliability problems. This is E3's rule (one fact, charged once) one axis over.

---

## E10 · Expectation Gap + Inherent Risk Tier

**2 weeks · Risk: low · Changes scores: no**

### Customer outcome
The answer to the entire research question, in a sentence a buyer can act on:

> *"Posture 68. Median for financial services, 1,000–10,000 staff, ANZ (n=14): 87. This vendor sits 19 points below its peer group and in the bottom decile of it."*

Plus the **Residual Risk** view procurement actually decides from.

### E10a — Expectation Gap · ◑ largely delivered by EB

**Most of this is built.** [EB](#eb--peer-benchmarking-layer-v2--delivered) computes the cohort, the
placement, the per-domain comparison and the disputable assignment, with `n` disclosed on every
figure. What E10a still owes is narrow:

- the **signed `EG` delta** as a named published field — EB publishes `delta_from_median` and a
  quartile, not `Posture − E[Posture | cohort]` under that name;
- the **driver attribution** in the sentence (*"the gap is driven by absent DMARC…"*), which needs
  per-signal peer prevalence joined to the placement.

**Do not build this against [benchmark.py](../backend/app/benchmark.py).** That module is the
deprecated v1 path — it still ships `min_cohort_n: 1` and a six-point synthetic fallback. Build
against `app/benchmarking/`.

**Still gated on E11 for percentiles**: EB refuses a percentile below n=30 by design, so until the
pool is seeded the honest output is a quartile plus rank-of-n.

### E10b — Inherent Risk Tier
`criticality` is client-supplied and already reaches [recommend.py:41](../backend/app/scoring/recommend.py#L41) — it just never becomes a tier. This is the **Inherent Risk** layer, and it runs on a different clock from Posture: it changes when the *relationship* changes, not when the vendor's TLS does.

**Residual Risk** is the published combination — a **deterministic lookup, not a dimension**:

| Posture ↓ / Inherent → | Low | Medium | High | Critical |
|---|---|---|---|---|
| **Strong (80–100)** | Low | Low-Med | Medium | Med-High |
| **Moderate (60–79)** | Low-Med | Medium | High | High |
| **Weak (40–59)** | Medium | High | High | Critical |
| **Poor (< 40)** | Med-High | High | Critical | Critical |

High-Inherent + Strong-Posture still lands at Medium — inherent exposure does not vanish because controls look good. Build it as a rendering concern, not a stored score.

### Exit criteria — ✅ all met (`6956593`)

*This phase shipped without a criteria list. These are derived from the phase text above and each was verified against the tree on 2026-07-31.*

**E10a**
- [x] **The signed `EG` delta as a named published field** — `expectation_gap.ExpectationGapReport.gap`, served at `GET /api/v2/suppliers/{ref}/expectation-gap`. Not a rename of `delta_from_median`: it calls the placement's own `_percentile_value`, so an expectation quoted here and a median quoted in a placement **cannot disagree**
- [x] **The estimator is published as part of the claim** — *"19 points below the median"* and *"19 below the mean"* are different findings and a reader must be able to tell which they hold
- [x] **Driver attribution in the sentence** — `attribution(s) = charged_points(s) × (1 − peer_failure_rate(s))`. A vendor failing DMARC where every peer also fails it is not *behind* on DMARC; without this, a "driver" is the vendor's biggest penalty relabelled as a comparison
- [x] **Per-signal peer prevalence joined to the placement** — `bm_peer_signals`. `PeerRecord.signals` had existed since EB with nothing populating it, so the per-cohort discrimination test had been running on domains only
- [x] Built against `app/benchmarking/`, **not** `benchmark.py` — asserted by parsing the module's imports
- [x] Every EB refusal rule re-applies, in the same order: synthetic gate first, then no-posture, then the n≥8 floor

**E10b**
- [x] **Inherent Risk Tier exists as a tier** — `inherent_tier()`, the higher of `criticality` and `data_access_scope`. Non-compensatory: averaging would let each excuse the other
- [x] **`data_access_scope` reused, not reinvented** — EB deliberately kept it out of cohort keying and routed it to *interpretation*; this is the interpretation it routes to, so a client answers once
- [x] **The 16-cell Residual matrix, exactly as tabled** — and **High-Inherent + Strong-Posture lands at Medium**, asserted directly
- [x] **A rendering, not a stored score** — no `residual` field on `Score`; asserted, along with monotonicity in both directions across all sixteen cells
- [x] Undeclared exposure is **`Not declared`, never `low`** — defaulting would present every unclassified vendor as low-residual, and the unclassified are disproportionately the ones nobody has looked at

> **Two additions the plan did not ask for**, both from the [independent design review](benchmarking-review-2026-07.md): the gap now reaches the **monitoring cadence** (30d, or 14d for a depended-on supplier) and *nothing else*, and `GET /api/vendors/{ref}/assessment` assembles the three layers into the one block a procurement reader needs — because assembling them was previously the client's job.

---

## E11 · Make the cohorts real

**Ongoing · Risk: low · Changes scores: no**

### Customer outcome
Peer comparison stops being illustrative and becomes evidence.

| Issue | Now | Target |
|---|---|---|
| `min_cohort_n` | **1** in the deprecated v1 block | ✅ **Solved in EB** — `min_quartile_n: 8`, `min_percentile_n: 30`, both floored **in code** so a demo setting cannot survive into production the way this one did |
| Synthetic fallback | 6 hard-coded postures reported as `n=6` | ✅ **Fixed and committed** (`ebc1dc5` + `18dd4f6`). EB goes further: `is_synthetic` is a **hard gate** forbidding any percentile or quartile at any `n` |
| Peer pool | Whatever this deployment scored | ❌ **Still outstanding — this is now the whole of E11** |

**What is left of E11 is the pool, and only the pool.** The threshold and disclosure defects that
made up two-thirds of this phase are closed; seeding is the remainder.

```bash
python -m app.seed_cohorts --all --concurrency 2   # 115 real vendors
```

**Politeness is not optional** — every collector queries someone else's free service, and seeding multiplies that by 115.

**Cohort maths, so expectations are right:** 115 vendors ÷ (10 sectors × 4 regions × 3 size bands) = 120 cells. Seeding alone **will not** reach `min_cohort_n: 8` in most cells — it fills the widening ladder's upper rungs. E11 is *ongoing* because the pool grows with real client assessments.

### Exit criteria — ✅ every code criterion met (`cf4e92b`) · pool seeding is operational

- [x] **`min_cohort_n: 1` is gone, and cannot come back.** 8 in YAML *and* floored in code (`_ABSOLUTE_MIN_COHORT_N`), mirroring what `benchmarking/config.py` does for its own two thresholds. Raising it works; lowering it does not, and that asymmetry is the point — a YAML floor alone is what let `1` ship for months
- [x] **The synthetic fallback publishes no ordinal placement at any `n`** — no percentile, no quartile, no variance-from-median. The caveat is strong, leads the list, and was still not enough: **the caption does not travel with the screenshot**. The labelled reference line and its context stay; only the rank against six invented postures is withheld
- [x] **Fixed on the DEFAULT path, not deferred to the cutover.** `benchmark.py` still serves `/api/vendors/{ref}/benchmark` and `run_pipeline` still writes its output onto every scored vendor, so *"it goes away next release"* would have meant shipping both defects for another release
- [x] The v1 route is marked `deprecated=True` in OpenAPI, naming what v2 offers instead
- [x] **Two tests restored that said to restore them here.** Both were written under `min_cohort_n: 1`, recorded the behaviour change deliberately, and ended *"E11 raises the threshold, at which point this test should be restored."* A three-peer cohort now publishes no placement at all
- [x] **The seeder spends the politeness budget on cohorts that can actually fill.** Two defects, both silent and both in the expensive direction — see the box below. 10 tests
- [x] **The pool itself.** `python -m app.seed_cohorts --all --concurrency 2` — run 2026-07-31. 114 vendors scored into **62 cohorts**, mean depth **1.84**, **one** cohort at or above the floor of 8. The run did what it was asked to do; what it revealed is that the ask was mis-sized, and that finding is worth more than the depth would have been — see the box in *"Immediate next action"*

> **The one item that cannot be closed by writing code, stated plainly.** Seeding is an operational
> task with a politeness budget, not an engineering one, and no amount of engineering substitutes
> for it. It is also the *only* thing standing between E13 and its switch-on: until the pool is
> real, `L_peer` would come from six invented postures, and shrinking every under-evidenced vendor
> toward fiction is worse than not shrinking at all.
>
> **But "the pool, and only the pool" was right about seeding and wrong about the seeder**, and two
> defects in it would have made 114 live scans buy less than they should:
>
> 1. **The sector was thrown away at the call site.** Every seed vendor sits under a sector heading
>    — the key of the dict it is in — and `seed()` called `run_pipeline(vendor)` with no sector, so
>    cohort assignment fell entirely to inference from GLEIF/Wikidata/PDL industry labels. That
>    inference fails for a meaningful share of real companies, and **a vendor with no sector gets no
>    cohort at all**: a live query against someone else's free service, spent in full, contributing
>    to no peer group. The heading is now passed as a *client-stated* sector — our editorial
>    judgement about which peer group a company belongs in, recorded as `source="client"` exactly
>    like a buyer's own declaration, never as an observation. `--infer-sector` opts out.
> 2. **Three headings were not sectors.** `food_agriculture`, `transport_logistics` and
>    `energy_utilities` are not in the controlled vocabulary (`agriculture`, `logistics`,
>    `utilities` are), so `--sector` offered an operator three headings that could never match a
>    cohort key. Now validated against `sectors.py` **at import**, because a check that fires after
>    114 live scans is a post-mortem rather than a guard.
>
> **And `--status`, the one instrument for *"is the pool real yet?"*, measured the deprecated gate.**
> It reported `benchmark.min_cohort_n()` — the v1 path EB replaced — as a single publishes /
> insufficient column, so an operator could not tell which of the three things they were waiting for
> had arrived. It now reports every gate (v1, EB quartile at 8, EB percentile at 30, E13's floor at
> 8) and answers the question the pool actually blocks: **how many cohorts can supply `L_peer`**,
> in `preconditions()`'s own words rather than a restatement of them.
>
> Five other tests were re-based from 3–6 peers to 8–9 while closing this. Not cosmetic: at the old
> sizes they now fall through to the synthetic path, and each would have **silently stopped
> measuring the thing it was written for** — stale exclusion, thin-peer exclusion, the percentile
> overshoot.

---

## EB · Peer benchmarking layer v2 — ✅ DELIVERED

**Delivered 2026-07-30 · Risk: none to Posture · Changes scores: no — it cannot**

**Design record:** [benchmarking-design.md](benchmarking-design.md) · **Code:** `backend/app/benchmarking/` · **Config:** `benchmarks.yaml` → `benchmarking:` · **Tests:** 91, all passing

### Why it is here and not in the original sequence

It appears in no earlier plan. It was built out of order because it **depends on nothing in Track E**:
it reads posture, confidence and domain scores that already exist and contextualises them. It has no
write path to a score, and `test_benchmarking_never_alters_input_scores` asserts it.

### Customer outcome

The question a supplier benchmark exists to answer — *"is this supplier's posture normal, good, or
poor compared to similar suppliers?"* — answered for **both** audiences from one dataset, with the
population always disclosed and the refusals treated as the feature.

### What it supersedes, and what it adds

| Relationship | Detail |
|---|---|
| **Supersedes E11's threshold mechanism** | `min_quartile_n: 8` and `min_percentile_n: 30`, both **floored in code**. The shipped `min_cohort_n: 1` exists because a demo setting survived into production; a YAML floor alone would let that recur |
| **Delivers most of E10a** | Cohort placement, per-domain comparison, disputable assignment. Outstanding: the named signed `EG` delta and driver attribution |
| **Automates E0.3** | The discrimination test now runs on **every cohort build**, per cohort, rather than as a one-off analysis. The seeded-pool run remains outstanding |
| **Adds — not in any plan** | Snapshot reproducibility · a cohort dispute path · the placement delta that separates *"you moved"* from *"the cohort moved"* |

### The five decisions, locked before code

Recorded in full in [benchmarking-design.md](benchmarking-design.md); summarised because each one
changed the schema.

1. **Vendor-only cohorts** — `sector` + `size_band` + `delivery_model`. `data_access_scope` is a
   property of the *relationship*, not the supplier: keying on it would put one supplier in different
   cohorts for different buyers, fragment the pool ~4× exactly where n≥30 is needed, and re-open the
   cross-tenant pooling question the plan has parked. It routes to **interpretation** — it picks the
   procurement action and nothing else.
2. **Cold start** — labelled external base rates as a *reference line*, plus honest
   `Insufficient peer data (n=4)`. A reference line is a **population statistic, never a peer median**.
3. **Synthetic is a hard gate** — `is_synthetic` forbids any percentile *or* quartile at any `n`.
   Thirty invented numbers still make a screenshottable fake percentile, and the caption under it does
   not travel with the screenshot.
4. **Member refs stored, never published** — a dispute reviewer must be able to answer *"who was I
   compared against?"*; a tenant must not learn another tenant's book. Enforced **structurally**:
   `PublicCohortSnapshot` has no field for them, so a route cannot leak by omission.
5. **Assume hundreds of suppliers in year one** — quartile + rank-of-n is the real product now;
   percentiles switch on by themselves at n≥30.

### The ladder — deepen, then widen, then refuse

The v1 ladder started at a four-dimension cohort and **widened**, which inverts the density problem:
the most specific rung is the one least likely to hold anybody, so the common path was *"try the thing
that never works, then try the next thing that never works."* EB puts the **floor** at the comparison
that should almost always be available, and only refines past it when density genuinely allows.

```
 deepen  →  sector + size_band + delivery_model
            sector + size_band            ← FLOOR
 widen   →  sector
            sector_group                  (published rollup, partition-validated at load)
 refuse  →  "Insufficient peer data (n=<actual>)"
```

Every rung tried is recorded with its `n`. That list **is** the assignment rationale — *"wanted
sector+size+delivery (n=6), assigned sector+size (n=34)"* — and it is the answer to the only question
anyone asks about a cohort. No rung may be anchored on neither `sector` nor `sector_group`; the loader
refuses one that is, because a peer group spanning every industry is not a peer group.

### Three correctness fixes worth carrying into other phases

**Midrank ties, worth 26 percentile points.** Postures are integers 0–100, so at n=40 collisions are
certain. The obvious `at-or-below / n` reports a supplier tied with ten others at the median as
**above** the 50th percentile — it inherits credit for beating suppliers it merely matched. Midrank
credits half the tie. Asserted directly: midrank `50.0` vs at-or-below `76.19` on the same data.

**`rank_of_n` is required, not optional.** *"17th of 34"* needs no estimator choice, cannot overstate
its own precision, and survives one peer joining. At n=8–29 it is strictly more informative than a
quartile letter.

**A bare `Q1` is a coin flip.** It means the *best* quarter in finance and the *worst* almost
everywhere else, so `quartile` always ships with `quartile_label` and `quartile_direction`.

### The bug the tests caught

`assign_cohort` overwrote its best-so-far rung with each successive one, so a supplier below every
threshold was assigned the **widest** rung even when an earlier rung held more peers. Widening does
not always add peers — a `sector_group` rung can hold fewer than the `sector` rung above it when the
rollup's other sectors are unpopulated. It reported `n=0` while a rung with four peers had already
been found. Now keeps the fullest rung; ties keep the more specific.

### Exit criteria — all met

- [x] Cohort assignment with full metadata and per-rung rationale
- [x] `n` published on every figure, never misrepresented, subject excluded
- [x] Percentile ≥30, quartile ≥8, `Insufficient peer data` below — floors enforced in code
- [x] Discrimination test runs on cohort build; flags suppressed from peer-gap reporting and disclosed separately
- [x] Cohort dispute raised, logged, and notated on the placement while open
- [x] 91 tests · full suite 520 passed / 0 failed · lint clean

### What EB does NOT do

- **No cutover.** [benchmark.py](../backend/app/benchmark.py) still serves `/api/vendors/{ref}/benchmark`
  and still contains `_synthetic_baseline_peers` and the invent-a-cohort fallback. Mounted side by
  side under `/api/v2` so no client is handed a changed response shape; **both are marked for deletion
  one release from now**. *(Updated at E11: the module stays, but its two live defects do not —
  `min_cohort_n` is floored at 8 in code and a synthetic baseline now publishes no ordinal
  placement at any `n`. Keeping a deprecated module is a compatibility decision; keeping its bugs
  for a release is not, and the two were being conflated.)*
- **No store-backed integration tests.** The 91 tests drive the pure layers in-memory; the `/api/v2`
  routes are schema-verified only.
- **No reference-line sources.** The `is_synthetic` gate and caveat text are in; the cited population
  statistics themselves need sources chosen.
- **No program-level maturity or KPI/KRI benchmarking.** EB benchmarks a *vendor's* Posture against
  its peer vendors. It says nothing about whether *your TPRM program* — its coverage, cycle times,
  automation level — is mature relative to industry practice. That is **P9**.

### Post-delivery review — ✅ audited, three gaps closed (`062f42d`)

[very_helpful_benchmarking_analysis.md](very_helpful_benchmarking_analysis.md) was audited line by
line **against the tree**, not against the plan. Full record: [benchmarking-review-2026-07.md](benchmarking-review-2026-07.md).

Confirmed against fifteen named principles (NIST SP 800-161, ISO 27036, FFIEC/OCC, Shared
Assessments, US Chamber). Three real gaps, now closed:

- [x] **§6 monitoring cadence from the peer gap** — built at E10; the cadence, and *nothing else*
- [x] **§7 firmographics-only ablation test** — closed **structurally**, deliberately: a statistical
  ablation needs a seeded pool and would return `untested` until then, and **an untested control is
  not a control**
- [x] **§8 the assembled view** — `GET /api/vendors/{ref}/assessment`, holding no arithmetic of its own

Two items deferred **with reasons recorded**: cohort-schema versioning (only useful if it *predates*
the change it would explain, so it lands before the first ladder edit, not with it), and
program-level maturity (a different product on different data — **P9**).

> **One place the review understates the implementation.** It treats minimum-`n` as a configuration
> choice. Both thresholds are floored **in code**, because `min_cohort_n: 1` shipped for months — a
> configurable threshold with no floor is one that will eventually be lowered by someone under time
> pressure.

---

## E12 · Collector fan-out

**6–10 weeks · Risk: high · Changes scores: substantially**

### Customer outcome
*"TLS 1.0 on 8 of 340 checked hosts"* instead of *"TLS 1.0 on the homepage."* This is what turns a homepage check into an estate assessment.

### The honest scoping correction
The research says the denominator exists for most Class-P signals. **It does not.** Verified:

| Signal | What it actually probes | `D_s` today? |
|---|---|:--:|
| `stale_hosts ÷ subdomain_estate` | CT log counts | ✅ (delivered in E6) |
| `tls_version`, `cert_validity` | **one** handshake, apex:443 | ❌ = 1 |
| `hsts`, `csp`, `x_frame_opts` | **one** GET of the homepage | ❌ = 1 |
| `nvd_cve`, `kev_listed_cve` | keyword match on product names | ❌ none exists |

**This is a 6–10 week programme, not a 3-week phase.** Plan and resource it separately.

### Steps
1. **Decide and publish the asset scope.** Recommended: a deterministic hash-sampled set of *N* live names. The sampling rule **is** the denominator and must be published
2. **Multi-tenant detection before computing `D_s`** — non-negotiable, or your best-architected SaaS vendors bottom out. `wildcard_seen` is already carried
3. **Resolve liveness first.** CT shows certificates *issued*, not hosts *live*. Probing dead names inflates `D_s` and flatters the vendor
4. **Budget runtime and rate limits.** Fan-out multiplies every collector by *N*; the suite already takes 299s at *N*=1
5. **Leave `nvd_cve` / `kev_listed_cve` un-normalized and say so.** Better than dividing by a denominator you cannot defend
6. **Do not probe non-public endpoints.** The legal position depends on the request being identical to an ordinary browser visit

### Ceiling interaction — easy to break
`cert_validity` is the only `ceiling_auto_signal` and the only `never_decays` signal. Once it becomes a rate, decide explicitly what arms the ceiling. **Recommended: an expired cert on the apex specifically** — preserves today's semantics exactly.

### Exit criteria — ✅ all six steps met (`4cc1fde` decisions · `b352cdb` machinery)

The phase text lists six steps rather than criteria. Each is taken, and five are **built**, not merely decided.

- [x] **1. Asset scope decided and published.** Deterministic hash sampling seeded on the vendor ref, `estate.rule()` quotable in one sentence, carried on every finding. **The sampling rule IS the denominator** — a vendor disputing the figure disputes the rule, not the count. Deterministic so a changed rate is a changed *estate* rather than changed dice
- [x] **2. Multi-tenant detection before `D_s`** — keyed on `(parent, stem)`. A generated namespace *enumerates* one stem; a real estate does not
- [x] **3. Liveness excludes rather than inflates** — a non-resolving name leaves the denominator. `is_live=None` means *unchecked*, and an unchecked name is not a dead name
- [x] **4. Runtime and rate limits budgeted** — `probe_cap` is a config value **precisely so the budget is visible to whoever raises it**, floored at 1 and ceilinged at 2000 by the loader
- [x] **5. `nvd_cve` / `kev_listed_cve` left un-normalised, and the reason published** — same evidence bar E8 used to refuse the `kev_overdue` gate and E9c used to exclude PCI Req 6.3.3. One bar, three phases, no exceptions
- [x] **6. No non-public endpoints probed.** Fan-out multiplies the *number* of requests, not the *kind*; `robots.txt` is honoured per host
- [x] **The ceiling interaction, decided and enforced.** The apex, specifically. Any-host would cap every large vendor at 49 on one abandoned staging certificate — and **a non-compensatory knockout that fires constantly is one nobody reads**, which is strictly worse than not having it. A rate threshold would make the most severe response in the model a tunable percentage
- [x] Emits **rates, not one finding per host** — N per-host findings would be E7c's root-cause problem multiplied by the estate size. The `count + denominator` shape is what E6's exposure branch already consumes
- [x] 19 tests · full suite 748 → 751 passed

**Shipped switched OFF at `probe_cap: 1`**, which is exactly the pre-E12 behaviour: no second wave, no extra traffic, no vendor's score moves. Raising the cap is a **resourcing decision**, which is why it is config.

> **Two real bugs the tests found, both in the direction that flatters.**
>
> **The tenant detector dropped whole estates.** Counting raw siblings under a parent meant any
> vendor with more than 25 subdomains off their apex had their **entire estate** classified as
> tenants — and a dropped estate is an empty denominator, which reads as *"nothing to see"* rather
> than as an error. Large companies legitimately run hundreds of distinct names off the apex; that
> is what a large company looks like. The test fixtures were wrong too: `h0…h339` is a generated
> namespace, so testing the detector against it was testing the wrong thing.
>
> **Declaring the signals cost every vendor confidence.** Adding two estate rates moved the coverage
> denominator 27 → 29, so confidence fell ~7% for a feature that *cannot* emit a finding at cap 1 —
> the same error as counting an unchecked signal as a failure, one axis over. Per-category coverage
> had it independently. `planned_signal_count` now means *"signals this deployment intends to
> collect"*.

**Still outstanding, and it is the 6–10 week part:** running at a raised cap against live vendors.
The machinery is built and tested; the fan-out is an operational programme with a politeness budget.

---

## E13 · Bounded log-odds

**3–4 weeks · Risk: medium-high · Blocked on E11**

### Customer outcome
Discrimination returns at the bottom of the scale, where triage matters most. Today a vendor with three Criticals and one with fifteen both publish as 0.

```
L̃ = c^τ·L + (1 − c^τ)·L_peer      Posture = 100 · (1 − σ(L̃))
```

Never floors · never saturates · makes the Ghost cliff unnecessary (an unmeasurable vendor gets their cohort's median, so **hiding stops being better than being average**).

### Preconditions — verified in code, not assumed
- [x] **`min_cohort_n ≥ 8` with real peers** — the threshold half is done and floored in code (E11); the *real peers* half is the pool, and `preconditions()` refuses on `n_peers < 8`
- [x] **`_synthetic_baseline_peers` hard-excluded from `L_peer`** — `peers_are_synthetic` is a refusal, not a caveat, and the engine passes `True` **because that is true today**
- [x] **E7 monotonicity re-run against the new transform** — `test_shrinkage_is_monotone_in_the_vendor_s_own_penalty`, at four confidence levels

### Exit criteria — ✅ built, wired side-by-side, correctly refusing (`4cc1fde` · `b352cdb`)

- [x] **The transform, complete and reviewable** — `app/scoring/log_odds.py`, 15 tests
- [x] **Never floors, never saturates** — a vendor at 3× the cap and one at 6× still separate. Under the live transform both publish 0, which is the defect stated as an assertion
- [x] **Thin evidence pulls toward the cohort, not toward 100** — the structural argument, and the strongest one in the plan: it removes the incentive to hide rather than penalising the response to it
- [x] **Published SIDE BY SIDE** — `Score.log_odds_preview` + `log_odds_reason` on every score. The plan calls this a second release needing a notice period, and **a client cannot be given a notice period for a number they cannot yet see**
- [x] **Computed and consumed nowhere** — asserted by parsing the engine: the preview may appear only where the `Score` is constructed, never in an arithmetic expression. If E13 could move the live number before its release, the notice period would be decorative
- [x] **The precondition cannot be waived by configuration** — the module imports `math`, `dataclasses` and nothing else, asserted by parsing its imports. `min_cohort_n: 1` is this codebase's standing evidence that a setting which *can* be lowered eventually is
- [x] **Switching on is one argument** — and it now *exists*. `ScoringEngine.score(peers=…)` takes a `PeerContext`; the pipeline fills it from the vendor's cohort. See the box below: this criterion was marked met while the argument was three literals and nothing in the codebase computed a peer rate
- [x] **`L_peer` is a MEDIAN over the EXACT cohort** — never a mean, never the widening ladder. Both are correctness arguments, both held as tests
- [x] **The switch-on itself** — **live for one cohort as of 2026-07-31.** `technology|rev=?|emp=medium|north_america` holds 10 real peers, so `L_peer` is available and the side-by-side preview publishes for those vendors on their next score, with no code change and no flag. That is what "data-driven rather than promised" was supposed to mean, and it is now observable rather than argued. Per cohort, not one switch for the book: 61 of 62 cohorts still refuse, in `preconditions()`'s own words

> **The criterion above was marked met on a promise, and the promise was not checkable.** *"When the
> pool is real, `peers_are_synthetic=False` and the transform runs — no new code"* described a
> one-line change to a line that did not exist. The engine wrote `peer_penalty_fraction=None,
> n_peers=0, peers_are_synthetic=True` as three literals, and **nothing anywhere computed a peer
> penalty rate**. The test that "demonstrated" the switch-on handed `shrink()` real numbers by
> hand — true, and nothing in the system was in a position to hand it any.
>
> The seam is now real and asserted end to end: the same vendor and the same evidence, refusing
> without a cohort and publishing with one, with the live posture unmoved. `NO_PEERS` reproduces
> the old literals exactly, so the default path did not change.
>
> **Two decisions the join forced, both of which could have gone the flattering way:**
>
> * **A median, not a mean.** A posture inverts to a penalty fraction exactly — `(100 − posture)/100`
>   — *except at the clamps*. A peer at the 0 floor and a peer capped at 49 by the critical ceiling
>   both invert to a rate they did not earn, and they distort in **opposite** directions, so no
>   adjustment fixes both. On a nine-peer cohort the mean moves 10.2 posture points on two such
>   peers; the median does not move at all. The count of capped peers is disclosed rather than
>   corrected, because a published posture does not say how much of it was a cap.
> * **The exact cohort, never the widened one.** Ranking a supplier against a widened group is worth
>   doing *with the widening disclosed*. Shrinking toward one is a different act — it moves the
>   vendor's own number toward a population they were not compared to, and the caption does not
>   travel with the figure. Asserted by parsing `_peer_context`: it reads `cohort_members`, never
>   `build_benchmark`.
>
> **An empty cohort is a refusal, never a rate of zero.** 0.0 would say every peer is spotless and
> shrink thin vendors toward a perfect score — the failure in the flattering direction, and the
> exact one this module exists to prevent.

**This is a second release.** It changes what the number means: new version, notice period, side-by-side publication. The preview field is what makes that sequence possible.

> **An honest limit the first test draft assumed away.** It asserted an invisible vendor lands *at*
> their cohort median. It does not: at τ=1 and 5% coverage they land about **six points above** it,
> because 5% weight on very clean own-evidence is still weight. So the transform shrinks the
> incentive to hide from roughly thirty points to roughly six — **it does not eliminate it**.
> Recorded in the test rather than tuned away, and it is the concrete thing τ is for (τ=2 cuts the
> residual to under two points). Which τ to ship is a judgement call for a room with a seeded pool
> in it, not one settled by picking the number that makes an assertion pass.

---

---

## E14 · Gap analysis & recommendations (LLM)

**2–3 weeks · Risk: medium · Depends on P2, P6, E9c, E10b · ✅◑ DELIVERED 2026-08-02, chain unverified against a live key**

### Customer outcome

One button on the vendor page — **"Generate Gap Analysis & Recommendations"** — that turns a
finished assessment into something an analyst can act on without reading nine sections first:

> *"Acme holds your production customer data and cannot be replaced quickly, and their observable
> controls do not match that exposure. The gap is concentrated in two places: email authentication
> (no DMARC enforcement, SPF soft-fail) and certificate lifecycle (two expired certs on hosts still
> serving). Neither is expensive to fix and both are contractually requestable. Coverage is 68% —
> the assessment could not see their internal controls, so this describes the perimeter only."*

Then a short list of prioritised recommendations, each of which the analyst can **accept, edit, or
reject**, and each accepted one becomes a remediation ticket with an owner and a due date.

### What this is NOT, and the boundary is the design

`app/summariser.py` already established the one rule this phase inherits and must not weaken:
**the LLM is a read layer over the finished record.** It never computes, adjusts, re-weights, or
second-guesses a score. Posture, confidence, assurity, the inherent tier and the residual cell are
all formed upstream by deterministic code and handed to the model **as given facts**.

This matters more here than it did for the summariser, because a "gap analysis" is exactly the
shape of output that invites a model to editorialise about the numbers. The specific failure to
design against: a model that writes *"the 72 posture understates their real risk"* has silently
produced a second, unauditable score — and it is the one the reader will remember.

**A recommendation is not a finding.** Findings are hash-stamped observations with a band, a
penalty and a re-check date. Recommendations are prose, marked AI-generated, disposable, and
regenerable. They live in a different part of the response and must never be merged into the
findings list.

### Why now

P1–P9 produced nine artefacts a reader has to assemble themselves: posture and category breakdown,
coverage statement, assurity, continuity, expectation gap, compliance gap, inherent and residual
risk, contract flow-downs, concentration. Every one is individually defensible and the set is
genuinely hard to read in under twenty minutes. The assembly is the work, and it is the same
assembly every analyst does by hand for every vendor.

P6 already proved the shape: `app/audience_views.py` assembles a procurement dossier and a security
dossier from one immutable score, with an invariant that they cannot quote different numbers. **E14
is a third audience view whose renderer happens to be a language model** — which is why it belongs
in the E track and why its context is assembled by the same deterministic code, not by prompting.

### The context handed to the model

Assembled by a dedicated module (`app/gap_analysis.py`), **not** by letting the prompt reach into
the store. Everything below already exists and is already published somewhere:

| Group | Fields |
|---|---|
| Identity | name, domain, legal name, jurisdiction, sector, employees, revenue band, ownership, domain age / inception |
| Posture | overall posture, grade, per-category posture + penalty + coverage, the penalty divisor, whether the critical ceiling armed |
| Findings | every charged finding: signal, band, observation, effective penalty, `ask_of_vendor`, `accepts_as_refute`, `recheck_after`, dispute state |
| Confidence | overall confidence, the coverage statement's three buckets (P2), which sources were silent and why |
| Assurity | the assurity report and what it rests on |
| Continuity | registry standing, worst-standing headline, service availability (P7) |
| Gaps | expectation gap (EB) and compliance gap (E9c), with framework names |
| Exposure | inherent tier + basis + **whether it is provisional**, residual cell, substitutability, escalation |
| Context | peer cohort and placement where one exists, fourth-party concentration and SPOFs (P1), assessment plan (P5) |

**PII minimisation is unchanged and non-negotiable.** The §4.2 bright line holds: no natural-person
data enters this context, because none is collected. Role addresses only. This is an egress
decision as much as a privacy one — the context leaves our infrastructure.

### Provider chain: Gemini → Groq → OpenRouter

*(An earlier revision of this document named the secondary provider "Grok" — xAI's model. The
intended provider is **Groq**, the fast open-weight-model inference host at groq.com, which is
also what the summariser's own `.env.example` block already pointed to. Corrected here and in
`TPRM_GROQ_*`; no design changed, only the name.)*

Three providers, each a fallback to the previous. The existing `llm_*` settings are single-provider
and must be generalised to an ordered list.

```
GEMINI      primary     cheapest per token at this context size, long context window
GROQ        secondary   different vendor, different failure surface
OPENROUTER  tertiary    a router, so it is a fallback for the FALLBACK's outage too
```

Design rules for the chain, and each exists because of a specific failure:

1. **Fall back on transport failure and rate limits, never on content.** A 429, a 5xx, a timeout, a
   connection error → try the next provider. A 200 whose content we dislike → **return it or fail**.
   Retrying until the output reads better is how a system acquires an unrecorded editorial policy.
2. **The provider that answered is on the response.** Not in a log — on the artefact. Two analysts
   comparing notes on the same vendor must be able to see they were reading different models.
3. **Every provider gets the identical context and the identical prompt.** If the prompt has to be
   tuned per provider, the differences are load-bearing and must be versioned as such.
4. **Exhausting the chain returns 503, never a degraded answer.** The summariser's existing rule:
   *opt-in and inert when unconfigured*. A gap analysis assembled without a model — a template with
   the findings pasted in — would be indistinguishable on the page from one written by a model, and
   the reader would have no way to know which they were trusting.
5. **The chain order is config, and the config is validated at load.** A provider listed with no key
   is a startup error, not a silent skip that turns the primary into the secondary without anyone
   noticing.
6. **One attempt per provider.** No retry loops inside a provider before falling through — three
   providers × three retries against a rate limit is nine requests to answer one question.

### Placement and gating

Primary action on the vendor assessment page, beside residual risk and the compliance-gap
indicators.

**Gated, and the gate is the interesting part.** The button must be **disabled with a stated reason**
— never silently absent, never enabled-but-useless — when:

| Condition | Why it is refused |
|---|---|
| No published posture (blocked / refused) | There is no assessment to analyse. A gap analysis over a Ghost record would be an essay about absence, and it would read as an assessment |
| Confidence below the P2 floor | The same refusal the posture itself makes. A recommendation list built on 30% coverage is a list of guesses about the 70% |
| Inherent tier not declared | Recommendations are prioritised by exposure. Without a tier, "prioritised" means "in the order the model happened to write them" |
| No LLM configured | 503, stated. Not a template |

An inherent tier that is **provisional** does not gate — it annotates. Consistent with
`app/inherent_register.py`: a provisional answer routes better than no answer, and it is labelled
everywhere it is read.

### Output shape

```
executive_summary      2–4 sentences. What this vendor is, what the exposure is, where the gap is.
gaps[]                 { theme, what_we_observed, what_we_expected, why_it_matters,
                         evidence_finding_ids[], confidence_caveat }
recommendations[]      { priority, recommendation, rationale, effort, owner_hint,
                         contract_flowdown_ref?, evidence_finding_ids[], addresses_gap }
limitations            Straight from P2's coverage statement. NOT generated.
provenance             { provider, model, prompt_version, context_hash, generated_at }
```

Two of those are load-bearing:

- **`evidence_finding_ids[]` on every gap and every recommendation.** A recommendation that cannot
  be traced to a finding is either a hallucination or an opinion, and both should be visible as such.
  A post-generation validator drops any id that is not in the context — silently accepting an
  invented id would make the citation decorative.
- **`limitations` is copied, not generated.** P2's coverage statement is already the honest sentence
  about what the assessment could not see. Asking a model to paraphrase it is a chance for it to
  soften it, and the softened version is the one that gets read.

### Workflow integration

The analyst can **accept / edit / reject** each recommendation individually. Accepted ones convert to
remediation tickets with owner and due date; analyst comments are retained and can be fed into
future context for the same vendor.

**Every one of those actions is an append-only event**, same discipline as `disputes`. A rejected
recommendation is not deleted — the record that a model proposed something and a person declined it
is the audit trail that makes the feature defensible. An edited recommendation keeps the original
alongside the edit, because "the analyst agreed" and "the analyst rewrote it" are different facts
about the model's usefulness, and only one of them is a good result.

### The measurement this phase owes

`app/program_maturity.py` scores Technology / data quality at 3 partly because *"a programme whose
data-quality defects surface by accident is Defined"*. An LLM feature with no accept/reject rate is
exactly that shape again. The event log above gives it for free:

> **acceptance rate** — of recommendations generated, how many an analyst accepted unedited, edited,
> or rejected. Reported per provider. It is the only honest measure of whether this feature works,
> and a version of it that is not measured will be believed regardless.

### Exit criteria — ✅◑ 11 of 12 met, verified against the tree 2026-08-02

- [x] **`app/gap_analysis.py` assembles the context deterministically** — `assemble_context()` takes only already-computed objects (score, findings, coverage statement, assurity, continuity, compliance/expectation gap, residual) and holds no arithmetic of its own, the same discipline `audience_views.py` follows for P6. `render_prompt()` is a pure function of the assembled `GapAnalysisContext`; `test_render_prompt_is_pure_and_cites_only_context_ids` and `test_context_is_assembled_deterministically_and_reviewable` assert it, the second by requiring two independent assemblies of identical inputs to hash identically
- [x] **Nothing in this phase reaches a vendor score** — `test_module_touches_no_scoring_machinery` greps the module source for `scoring.engine`, `pipeline` and `put_score(` and fails if any appear. (The plan's suggested second half — score a vendor with and without a generated analysis and require a byte-identical `Score` — was not additionally written: the module holds no reference to the score store at all, so there is no code path for it to write through)
- [x] **Provider chain falls back on transport failure and never on content** — `test_chain_falls_back_on_429_then_5xx_then_succeeds`, `test_chain_falls_back_on_timeout`, `test_200_with_poor_content_is_returned_not_retried` (asserts the second provider is never called on a 200)
- [x] **The answering provider and model are on the artefact** — `provenance.provider` / `provenance.model`, asserted in `test_happy_path_single_provider` and the fallback tests
- [x] **Chain exhaustion is 503** — `GapAnalysisExhausted`, mapped to HTTP 503 in `create_gap_analysis`; `test_chain_exhaustion_raises_never_a_template`
- [x] **Every gap and recommendation cites finding ids that exist in the context** — `_drop_invented_citations`; `test_happy_path_single_provider` plants an invented id (`ev999`) alongside a real one and asserts it is dropped and counted
- [x] **`limitations` is byte-identical to P2's coverage statement** — copied, never requested from the model (`_SYSTEM` rule 3 explicitly forbids the model writing one); `test_limitations_is_the_coverage_statement_object_itself`
- [x] **The button's gates are stated refusals** — `GET /api/vendors/{ref}/gap-analysis/gate`; `test_gate_refuses_no_score` / `_blocked` / `_refused` / `_thin_confidence` / `_undeclared_tier`, one test each
- [x] **A provisional inherent tier annotates and does not gate** — `test_provisional_tier_does_not_gate`; the frontend panel shows the annotation from `gate.inherent_tier_provisional` rather than disabling the button
- [x] **Accept / edit / reject are append-only events**, original retained alongside any edit — `gap_analysis_events` table, append-only triggers verified by `test_recommendation_events_are_append_only_and_keep_the_original` (asserts the stored recommendation text is untouched after an edit event, and that a DB-level `UPDATE`/`DELETE` raises)
- [x] **Acceptance rate is a KPI, and one metric was argued out** — `gap_analysis_acceptance_rate` added, `stakeholder_satisfaction` removed with the reasoning recorded in `program_kpis.py` (the vaguest of the four manually-supplied metrics, no near-term owner, versus a metric this module gets for free from a log the feature needs anyway); dashboard stays at 15
- [ ] **`POST`/`GET .../history` shipped; export to the P6 dossiers NOT done** — `POST /api/vendors/{ref}/gap-analysis` and `GET .../gap-analysis/history` are live and tested. Joining a generated analysis onto `/export?view=procurement|security` was not built — the dossiers still ship without it, and adding it is the one item left before this exit criterion is fully closed

**What "delivered" does not yet mean.** No provider is configured in this deployment (`TPRM_GEMINI_*` / `TPRM_GROQ_*` / `TPRM_OPENROUTER_*` all unset), so the chain has been proven against `httpx.MockTransport` — every fallback path, every parse failure, every citation-validation case — but never against a live key answering a real prompt. `components/GapAnalysis.jsx` builds and lints clean and the production bundle compiles, but nobody has clicked "Generate" in a running browser against a running backend. Both are the honest next steps, not gaps in the design.

### Anti-patterns for this phase specifically

1. **A model that comments on the score.** *"The 72 seems generous"* is a second score with no
   audit trail. The numbers are given facts; the model describes gaps, not arithmetic.
2. **Recommendations without finding ids.** Untraceable advice is indistinguishable from
   plausible-sounding invention, and it is the failure mode of every LLM feature ever shipped into
   a risk product.
3. **Retrying until the output looks better.** An unrecorded editorial policy.
4. **A template fallback when no provider answers.** It would read exactly like a real answer.
5. **Generating the limitations section.** P2 already wrote the honest sentence. Paraphrase is
   erosion.
6. **Feeding accepted recommendations back in as facts.** Analyst comments are context about
   *preferences*, not evidence. A recommendation accepted last quarter is not an observation about
   the vendor, and treating it as one is how a model starts citing itself.


# TRACK P — PRODUCT

**Nothing in this track touches Posture arithmetic.** Different people can run it in parallel from day one.

---

## P1 · Fourth-party concentration

**Days · Depends on nothing**

### Customer outcome
> *"Nine of your twenty-three vendors authenticate through Okta. Four are Tier-1. A single Okta outage removes 17% of your supplier book simultaneously."*

No per-vendor score can express this, and **no commercial rating publishes it from free data.** For a sponsor, this is the most differentiated output in the system.

### Why now
**APRA CPS 230 came into force 1 July 2026** — four weeks ago. [fourth_party.py](../backend/app/fourth_party.py) already cites ¶48. APRA-regulated entities must now identify material service providers and assess concentration.

### Why it is days, not weeks
Both halves are built and **nothing joins them.** `fourth_party.py` says so in its own docstring; `/api/portfolio`'s `concentration` is only *high-criticality vendors below 60* and never calls it.

### The metric, defined precisely
| Metric | Definition |
|---|---|
| Dependent vendor count | Vendors with this provider in their fourth-party map |
| Book share | `dependent / total scored` |
| **Critical share** | `dependent where criticality=high / total high-criticality` — **the board number** |
| Category | email · CDN · identity · hosting · payments |
| Single point of failure | Critical share ≥ 50% in one category |

**Rank by critical share, not raw count.** A provider under 90% of your stationery suppliers is not a finding.

### Exit criteria — ✅ all met (`P1`)

- [x] **Ranked by critical share, all five metrics published** — dependent count · book share · critical share · category · single point of failure. Ranked by critical share with count only as a tiebreak: *a provider under 90% of a book's stationery suppliers is not a finding*, and a report whose first row is noise trains the reader to skip the section
- [x] **No fourth-party finding enters any score** — asserted structurally by parsing the module's imports, and again on the source (`Finding(` / `penalty` absent). The aggregate is where the temptation returns: penalising every Okta customer for an Okta CVE would punish thousands of vendors for a dependency they share with their competitors **and** count the same risk once per vendor in one book
- [x] **Tier-2 visibility caveat on every report** — plus a second the plan did not ask for: a provider that leaves no public trace (a payroll processor, an offshore development partner) never appears here at all
- [x] **Vendors without `criticality` counted in the book, excluded from critical share, and the exclusion stated** — the two percentages are drawn from different populations by design, and a reader who notices that without an explanation concludes the numbers are wrong
- [x] 9 tests · `GET /api/portfolio` → `fourth_party_concentration`

> **A book with no declared criticality reports `None`, never `0%`.** A share with no denominator
> is not a small share, it is *no* share — and rendering 0% would read as *"none of your critical
> vendors depend on this"* when the truth is *"you have not told us which vendors are critical"*.
> The failure in the reassuring direction.
>
> **One rename shipped with this.** `/api/portfolio` published a field called `concentration` that
> was only *high-criticality vendors below 60* — a useful finding, but not concentration. Leaving
> the accurate name on the inaccurate thing is what let the real feature go unbuilt for two phases;
> it is now `weak_critical_vendors`, with the old key kept as a deprecated alias for one release.

---

## P2 · Coverage statement

**Days · Depends on nothing**

### Customer outcome
> *"This assessment covers externally observable evidence only. We could not observe: internal access controls, BCP/DR testing, subprocessor contracts, insurance coverage, or Tier-3 supply chain. It does not replace internal due diligence."*

Counter-intuitively this **increases** credibility with mature buyers, and it is the honest counterpart to a Ghost being adverse rather than neutral. It is also the cheapest legal protection in the plan.

Derive it mechanically from which collectors returned data plus the fixed HELD list. **Never hand-written per vendor.**

### Exit criteria — ✅ all met (`P2`)

- [x] **Derived mechanically, never hand-written** — `app/coverage_statement.py`, built from which collectors returned on THIS run plus `held_roadmap` read from the model. A written statement is wrong the moment a collector fails and nobody edits the prose — and wrong in the **flattering** direction, still claiming coverage the run did not achieve
- [x] **Names every area the phase text specified** — internal access controls · BCP/DR testing · subprocessor contracts · insurance · Tier-3 supply chain · *"does not replace internal due diligence"*
- [x] **`empty` is reached, not failed** — *we asked, there was nothing* is a real answer, and reporting it as a gap would turn a clean result into a finding. The same rule the engine applies to a passing signal
- [x] The HELD list comes from `scoring.yaml`, not restated here — the config is what a client is shown, and two copies drift
- [x] Served at `GET /api/vendors/{ref}/coverage` **and carried in the evidence pack**, which is where a limit most needs to travel with the number
- [x] 6 tests

> **The distinction that does the work, and it is not cosmetic.** `not_collected_this_run` may close
> on a re-run; `never_observable_from_outside` never closes. A reader who cannot tell them apart
> will either dismiss a real gap as a transient or wait indefinitely for a limit that will not lift.
> Three buckets, never collapsed into one "limitations" list — asserted by test.

---

## P3 · Evidence Request Pack

**1–2 weeks · Depends on nothing**

### Customer outcome
The bridge from *outside-in* to *inside-out* — and the feature that makes this a TPRM module rather than a rating.

| | SIG Lite | Evidence Request Pack |
|---|---|---|
| Questions | ~300, fixed | **Only what was observed failing** |
| Basis | Generic | Cited to a finding + evidence id |
| Resolution | Manual | Evidence standard stated up front |
| Closure | Email thread | Dispute → `nullify`/`mitigate` → re-score with reason recorded |

### Why it is 1–2 weeks and not a quarter
`scoring.yaml` already carries **41 `ask_of_vendor` + 41 `accepts_as_refute` + 41 `recheck_after`** entries — one per penalising band, written and unused. The dispute-adjudication half exists and is tested. **The loop is ~80% built.**

> **This figure was 58 in every earlier revision of this document, and 58 was measured against
> v4.2.0.** E2, E3 and E5 reclassified bands to informational and merged duplicate signals — the
> same passes this document records as 57 → 49 → 47 → 36 *signals* — and the band counts followed
> without anyone updating the prose. The shipped model carries **41** penalising bands, 41 `reasons`
> entries and 41 `actions` entries, and the three counts match exactly because
> `_validate_every_penalty_is_explainable` and `_validate_every_penalty_is_actionable` refuse to
> load a file where they do not. Nothing about the phase changes; the number was just wrong, and a
> criterion reading *"all 58 verified"* is one nobody could have verified.

### Two renderings, one dataset
**Procurement** — outbound request ordered by decision impact, each item tagged **blocking / condition / informational** derived from severity × Inherent Tier. That tag is the only element not already in `scoring.yaml`.

**Security** — inbound worklist ordered by effective penalty, grouped by category, with evidence receipt, `recheck_after`, dispute status, and what refutes it.

**Per-domain coverage on both.** A pack built from five collectors is not the same artefact as one built from twelve.

### Exit criteria — ✅ **all met** (`cf1acb4`) · verified against the tree 2026-07-31

- [x] **Only what was observed failing** — a finding that cost nothing raises no question. THE VALUE IS IN WHAT IS NOT ASKED: a pack scoped to a vendor's actual findings is answerable in an afternoon; a 300-question standard gets answered by an intern copying last year's
- [x] **Every question cites its finding and its evidence id** — a vendor who can see what we saw argues about the observation rather than about our motives, and an observation is arguable in a way a score is not
- [x] **The refute standard travels with the question** — `accepts_as_refute` up front. A request that does not say what would satisfy it generates a thread rather than an answer
- [x] **Ordered by what it is worth** — a pack that opens with a low-severity header gets triaged into a backlog
- [x] **All 41 entries verified reachable** — asserted across the whole shipped model, so a band whose question went missing fails loudly instead of silently dropping out of every pack. *(41, not the 58 this document claimed until 2026-07-31 — see the note under "Why it is 1–2 weeks". The assertion is over `penalising_bands()` rather than a literal, which is why it kept passing while the prose was stale.)*
- [x] **Closure through the dispute path** — the pack changes no score; answers travel through `nullify`/`mitigate` → re-score with the reason recorded, so a changed number always has a decision behind it
- [x] One question per observation however many times it fired · a clean vendor gets a **stated result, not an empty template**
- [x] **The two renderings** — `?view=procurement` and `?view=security` over one dataset. Procurement tags each item **blocking / condition / informational** from severity × Inherent Tier and orders by the tag, not by points; security groups by category and orders by effective penalty, carrying dispute state
- [x] **Per-domain coverage on the pack** — on both renderings *and* on the raw pack, in three states: observed-and-clean, observed-and-failing, **not observed at all**
- [x] 25 tests · `GET /api/vendors/{ref}/evidence-request-pack[?view=procurement|security]`

> **Why the tag could not come from severity alone**, which is what the plan meant by *"the only
> element not already in `scoring.yaml`"*. Severity is a property of the **finding**; what a finding
> does to a **decision** is a property of the relationship. The same missing DMARC record is a
> footnote on a stationery supplier and a deal-stopper on the vendor holding production customer
> data — same observation, same severity, opposite procurement action. So the tag is a sixteen-cell
> lookup on severity × Inherent Tier, shaped like E10b's residual matrix because it is the same
> argument applied to one finding rather than to the whole vendor.
>
> **An undeclared Inherent Tier leaves every item `untagged`, and says so.** Defaulting it to `low`
> would mark every item on every un-triaged relationship as informational — and the relationships
> nobody has classified are disproportionately the ones nobody has looked at, so the failure lands
> exactly where it does the most damage.
>
> **Ordered by the tag, not by the points.** A procurement reader is deciding whether to sign, not
> triaging remediation; ordering by posture points puts a 17.5-point informational above an 8-point
> blocking item, which is the wrong way round for the only question they are asking. Worth still
> breaks ties within a tag.
>
> **Per-domain coverage closes a silent, flattering failure.** A category that raised no questions
> reads as clean, and is equally consistent with a collector that never returned. Those are opposite
> facts about the vendor, and *silence is only good news once you know somebody asked* — the same
> distinction P2 draws for the assessment as a whole. The switched-off estate signals are out of the
> denominator, the correction E12 needed for confidence.

---

## P4 · Contract flow-downs

**1–2 weeks · Depends on P3**

### Customer outcome
Converts a security finding into something procurement can put in a contract. This is the item that makes the output usable by the audience that signs.

| Observed | Suggested protection |
|---|---|
| No published incident-response path | 24–72h breach notification clause |
| No independent audit evidence | Right-to-audit, or annual SOC 2 delivery |
| Concentrated fourth-party dependency | Subprocessor change notification + approval right |
| Going-concern flag | Termination for convenience · escrow · exit assistance |
| Thin coverage / Ghost | Questionnaire as condition precedent |
| Overdue KEV | Remediation SLA with contractual milestone |

**Discipline:** each entry cited, versioned, and marked *suggested drafting points, not legal advice*. Never generated.

### Exit criteria — ✅ all met (`P4`)

- [x] **A fixed table, never generated** — six observation families in `app/contract_flowdowns.py`, argued over once and held constant. No LLM is on this path and none may be added: asked *"why did you ask us for a 72-hour notification window?"* the only honest answer to *"the model produced it"* is that the output cannot be defended, and under Finding A a published output has to be reconstructible from a rule nameable in a sentence
- [x] **Each entry cited** — to the finding and its evidence id, or to the continuity flag or concentration statement that produced it. A row with no citation is our opinion of the vendor rather than an argument the reader can check
- [x] **Versioned** — `TABLE_VERSION` travels on every response, so a clause read from row 3 of v1.0.0 is not silently reinterpreted as row 3 of a later revision that changed what row 3 means
- [x] **Marked *suggested drafting points, not legal advice*** — on the caveat block and on the route docstring. It names a category of protection a lawyer would recognise; it does not draft clause language, and it never claims a vendor has agreed to anything
- [x] **Absence of a suggestion is not a clean bill of health** — stated in the summary. "None of the six families fired on this run" is a different claim from "we checked and there is nothing to add"
- [x] 17 tests · `GET /api/vendors/{ref}/contract-flowdowns`

> **Three of the plan's six rows are not findings, and pretending they were would have been the easy
> mistake.** *Concentrated fourth-party dependency* is a **portfolio** fact (P1) — invisible from
> inside one relationship, which is exactly the risk it names. *Going-concern* is E4's continuity
> flag, deliberately outside Posture. *Thin coverage / Ghost* is the confidence axis, which is an
> **absence** of findings and so has no band at all. Each cites the module that derived it instead of
> an evidence id, and each is rendered in the same list: a buyer negotiating subprocessor
> notification rights does not care which of our internal shapes produced the suggestion.
>
> **The KEV row is deliberately softer than the plan's label.** The plan calls it *"Overdue KEV"*.
> `kev_listed_cve` is a product-line **name match**, and CISA's due date is not carried past the
> collector into a stored finding — the same limitation that keeps `gates.kev_overdue` declared and
> disabled. Suggesting a remediation-SLA milestone off a KEV match is still sound; claiming *overdue*
> would assert evidence this system does not have. Say what we know, and let the caveat carry the
> rest.

---

## P5 · Tier → assessment depth and cadence

**1–2 weeks · Depends on E10b**

### Customer outcome
Effort matches exposure. Today a stationery supplier gets the same 27-signal treatment as the vendor holding production data.

| Tier | Collection depth | Cadence |
|---|---|---|
| **T1 Critical** | Full + fourth-party map + evidence pack | Quarterly |
| **T2 Important** | Full | Semi-annual |
| **T3 Standard** | Core signals only | Annual |
| **T4 Low** | Screening only (sanctions + entity) | Passive |

Two wins: tiering becomes operational rather than cosmetic, and low-tier vendors stop consuming free-API budget — which matters when politeness is not optional.

### Exit criteria — ✅ all met (`P5`)

- [x] **The plan's table, shipped** — `app/assessment_depth.py`. Four tiers → three depths → four cadences, a lookup like `residual_risk` and `recommend` for the same reason: *"the model chose quarterly"* is not a defensible answer to *"why is this vendor on a 90-day cycle"*
- [x] **Effort is monotone in exposure** — asserted, not assumed. A table that inverted anywhere would be worse than one clock for the whole book, because it would look principled while doing the opposite
- [x] **Depth reaches the pipeline** — `run_pipeline(depth=…)` filters the same collector list every run already builds. Default `None` means full, so no existing caller changed and no score silently got cheaper
- [x] **Cadence reaches the scheduler** — `python -m app.monitor --by-tier`. This is the join: a depth-and-cadence table nothing schedules against is a table, and the budget saving it claims never arrives
- [x] **Low-tier vendors stop consuming free-API budget** — a passive relationship with nothing outstanding is skipped entirely, and the sweep prints how many it skipped. A saving nobody can see is one nobody will defend when a reviewer asks why the stationery supplier has not been re-scored since March
- [x] **Two clocks, published separately and never averaged** — see the box
- [x] **Undeclared is not T4** — no declared tier routes to FULL depth on the T2 cadence, and says so
- [x] 24 + 10 tests (`test_assessment_depth.py`, `test_monitor.py`) + 3 pipeline tests · `GET /api/vendors/{ref}/assessment-plan` · `monitor --by-tier` · `monitor --plan`

> **THE DECISION THAT MAKES THIS MORE THAN A TABLE: a shallower run's confidence is allowed to
> fall.** Confidence is `signals observed / signals planned`. Run seven collectors instead of
> nineteen and coverage collapses — a screening run reaches about a fifth of the model, which is
> below `refuse_below` and correctly refuses as a Ghost.
>
> The tempting fix is to shrink the **denominator** to whatever the chosen depth planned, so a
> screening run reports high confidence "of what it set out to do". **Refused**, for the reason E6
> and E12 both give: confidence has to mean one thing across the whole book, or `0.8` means *"we saw
> most of the model"* on one vendor and *"we saw most of seven collectors"* on the next, printed in
> the same column with nothing to tell them apart. `unreachable_signals()` shrinks the denominator
> for signals that **cannot fire** — a property of the model. Depth is a property of the
> **relationship**, and adjusting a published measurement to flatter a deliberate choice is the
> failure mode this system is built against.
>
> So the consequence is stated **before the run**: `publishes_posture: false` on a T4 plan. A
> screening-depth run is a watchlist check, not an assessment — which is the right thing for a
> passive relationship, where the question is whether the entity exists and is not sanctioned, not
> how its TLS is configured. A reader who meets the refusal with no warning reads it as a finding
> about the vendor. Asserted as arithmetic rather than claimed: the test computes the screening
> fraction against `refuse_below` and fails if it ever climbs above the floor.
>
> **Two clocks, and they must not be collapsed.** The *review cadence* tracks how much the
> RELATIONSHIP is worth reassessing and moves when the contract moves; a *finding's re-check date*
> tracks one thing we FOUND and moves when the vendor's controls move. A card printing one number
> for both is lying about one of them. `next_action` returns the sooner and names which clock set
> it — so a T4 supplier with an expired certificate serving production is still chased inside a
> week, and closing that finding returns them to passive.
>
> **Undeclared is not T4, and the sweep is where that would do the most damage** — it is the thing
> that spends the budget, so demoting unclassified relationships there would put the thinnest
> assessment exactly where the unknown risk is. It costs budget, and the way to stop paying it is to
> declare the tier, which is the behaviour we want. Same argument E10b makes for the residual cell
> and P3 for the decision tag.

---

## P6 · Two audience views

**2 weeks · Depends on P1–P5**

Same immutable score object, two renderings. `/export` and `/summary` are the existing seam.

**Security:** findings by effective penalty · evidence receipts · category drill-down · per-signal peer comparison · remediation asks · recheck cadence · dispute status

**Procurement:** decision → Residual Risk → Continuity flags → concentration → contract conditions → monitoring cadence → coverage statement → Evidence Request Pack

### Exit criteria — ✅ all met (`P6`)

- [x] **Both renderings on the existing seam** — `GET /api/vendors/{ref}/export?view=procurement|security`. The unfiltered document is byte-for-byte what it was, so no existing caller changed
- [x] **Every section the plan names, in the order it names them** — procurement's order is asserted by test, because a template that floats the evidence pack above the residual tier turns a decision aid into a task list, and the reader most likely to stop early is the one whose signature matters most
- [x] **Nothing is recomputed** — `app/audience_views.py` arranges what the owning module hands it. Asserted structurally: the module imports only `__future__` and `typing`, and no arithmetic touches a posture, grade or confidence
- [x] **The two views cannot disagree** — `views_agree()` ships beside them and the suite runs it against real route output. A guard that cannot fail is not a guard, so a test hands it two divergent views and requires it to catch them
- [x] **Neither view publishes a number for a refusal or a block** — a refusal rendered as a low number is the most dangerous transformation this system could perform, and *"make it friendlier for procurement"* is exactly where it would appear
- [x] 16 tests + 5 route tests · `views_agree()` as a shipped invariant

> **THE RULE THAT KEEPS TWO VIEWS FROM BECOMING TWO STORIES: a limitation may not appear on only one
> view.** This is the thing a split rendering makes easy to get wrong, and it is wrong in the
> dangerous direction every time — put the coverage statement on the security view alone and the
> person who **signs** never learns what the assessment could not see. So the coverage statement,
> the confidence figure and the three-axes caveat travel on both, and `views_agree()` asserts it by
> requiring the same coverage object rather than by comparing prose, which would drift.
>
> **What procurement deliberately does not get: a per-signal worklist.** Not secrecy — `/export`
> serves the whole record to anyone who asks — but twenty-eight rows of DNS minutiae in front of a
> signer produces one of two outcomes: the decision is made on the first row, or the page is
> skipped. The evidence request pack is attached instead: the same findings, already turned into
> questions with a stated closing standard, which is the form a non-specialist can act on.
>
> **And security does not get a decision banner.** The decision is not theirs and it does not change
> what needs fixing.
>
> **P6 is the phase that was supposed to be a join, and for once it was.** P1, P2 and P3 each turned
> out to be two finished halves and no join. Here every piece genuinely existed — posture, residual,
> continuity, concentration, flow-downs, cadence, coverage, questions — and the work was arranging
> them without becoming a fourth source of truth about a vendor. That is why the invariant test
> matters more than any of the content tests.

---

## P7 · Status-page collector

**2–3 weeks · Depends on E4**

### Customer outcome
Answers the second procurement question after *"will they still exist"* — *"can they keep serving us?"* Outage and status-page history is the **only** major TPRM domain that is lawfully free, genuinely public and currently unread.

**Route to Continuity, not Posture** — frequent outages are a delivery problem, not a security problem.

**Caveat to carry:** a vendor with no status page is not more reliable than one publishing incidents. Absence of a status page is absence of evidence — a Confidence effect, not a Continuity finding.

### Exit criteria — ✅ all met (`P7`)

- [x] **The domain is read** — `app/collectors/status_page_collector.py` + `app/status_page.py`, `GET /api/vendors/{ref}/status-page`. Statuspage.io v2 JSON at `status.<domain>/api/v2/*.json`
- [x] **Routed to Continuity, not Posture** — the collector emits **no `Finding` at all**, so there is nothing for the scoring path to read even by accident. Frequent outages are a delivery problem, not a security problem
- [x] **Absence is stated as absence** — "not found" produces an explicit *"this is an absence of evidence, not a Continuity finding"* headline, never a clean bill of availability and never an implied outage record
- [x] **Assembled, not merely served** — carried on `/export` and inside the procurement rendering's continuity section, **beside** the going-concern standing rather than inside it
- [x] 8 + 2 tests

> **Why availability sits beside going-concern rather than inside it.** *"Is this entity still a
> legal person"* and *"does their service fall over"* are different questions with different
> evidence and different remedies. Folding the second into Continuity's `standing` would let an
> outage read as a solvency signal — the same conflation E4 undid when it moved going-concern out of
> Posture. Two facts on one page, never merged into one verdict.
>
> **What "a Confidence effect" does and does not mean here.** The plan's caveat is implemented as a
> disclosure, not as a change to the posture confidence denominator. Adding `status_page` to the
> scored model would mean a vendor's *security* confidence falls because their *availability* page
> is missing — which is precisely the axis-mixing the routing decision above exists to prevent, and
> it would silently move every published confidence in the book. The absence is disclosed where a
> reader meets it instead.
>
> **A known, stated gap rather than a claim.** Only the Statuspage.io v2 shape is recognised. A
> vendor on Instatus, a hand-rolled page, or one publishing at an uncommon path reads as "not found"
> even though a status page exists. That is written into the caveats, because the alternative —
> guessing at unfamiliar formats — is how "not found" quietly becomes "no outages".
>
> **One point in time, not a history.** The phase title says *"outage and status-page history"*;
> what ships is the state and open incidents **at the moment of the check**. Frequency needs a
> series, and a series needs repeated collection over time, which the monitor now supplies but has
> not yet accumulated. Said plainly on every report rather than implied by the phase name.

---

## P8 · Exit and substitutability

**1 week · Depends on P1, P5**

### Customer outcome
*"If they fail, what happens to us?"* — question 7, currently unanswered.

Do not derive substitutability from public data; it is not there. Take it the way `criticality` is taken — **client-supplied, never inferred:**

| `substitutability` | Effect |
|---|---|
| `sole_source` | Escalates Residual Risk one band · mandates exit-clause flow-downs |
| `low` | Exit-assistance clause recommended |
| `medium` | Standard terms |
| `high` | No exit conditions needed |

Four values, one field, same path as `criticality`. **`sole_source × poor Posture` is the single most useful procurement alert the system could emit.**

### Exit criteria — ✅ all met (`P8`)

- [x] **Four values, one field, same path as `criticality`** — `Substitutability` on `VendorProfile`, supplied on the score request, carried through `run_pipeline` and `build_profile`. **Client-supplied, never inferred**: switching cost, lock-in and data portability are not observable from outside, and guessing would be our opinion dressed as the buyer's exposure
- [x] **`sole_source` escalates Residual Risk one band** — in `residual_risk()`, disclosed via `escalated_from` and published on the route. It only ever escalates
- [x] **`sole_source` mandates exit-clause flow-downs** · **`low` recommends exit assistance** — P4's seventh family. `medium` and `high` produce nothing, which is the plan's *"standard terms"* and *"no exit conditions needed"* exactly
- [x] **`sole_source × poor Posture` is emitted** — `alert_level: critical` in `app/exit_readiness.py`, `GET /api/vendors/{ref}/exit-readiness`
- [x] **What OSINT cannot reach is named, not guessed** — switching cost, contractual lock-in, data portability, notice periods, transition assistance, each pointed at the Evidence Request Pack
- [x] 12 + 5 + 5 tests

> **The escalation is disclosed, never absorbed.** `escalated_from` keeps the cell the sixteen-cell
> matrix actually produced, so the published tier can always be traced back to the lookup plus one
> named step. An escalation a reader cannot undo in their head is an *adjustment*, and an adjusted
> risk tier is the thing E10b's "table, not a formula" rule exists to prevent.
>
> **It only escalates, and there is deliberately no de-escalating value.** An easily replaced vendor
> is not *less* exposed to a control failure while you are still using them. More to the point: a
> rule that could **lower** a residual tier on the client's own declaration is a rule that will be
> used to lower it, and the declaration is unverifiable by construction. Asymmetry on purpose, the
> same shape as `min_cohort_n`'s code floor — raising works, lowering does not.
>
> **Already Critical means there is nowhere to escalate, and it says so.** Inventing a band above
> the top to express "worse than critical" would break the published vocabulary to say something the
> word *critical* already says.
>
> **P8 was two-thirds built and missing exactly the joins the plan named.** `exit_readiness.py`
> raised the alert; nothing escalated the residual tier and nothing put an exit clause in front of
> procurement — and the plan's table names both in its own two right-hand cells. An alert that does
> not reach the contract is a fact the buyer now knows and still cannot act on, which is the same
> shape P1, P2 and P3 each turned out to be.

---

## P9 · Program maturity + KPI/KRI benchmarking

**2–3 weeks for the model + dashboard scaffold, ongoing to wire real KPIs · Depends on nothing to
start; the KPI set fills in as P1–P8 land · Source: [very_helpful_benchmarking_analysis.md](very_helpful_benchmarking_analysis.md)**

### Customer outcome
A different question than any other phase answers: not *"how is this vendor doing"* but *"how good is
our TPRM program, compared to a published maturity model and to peer programs?"* The answer a sponsor
or auditor should be able to read:

> *"We are Level 3/5 (Defined) overall. Managed (Level 4) on Inventory & Tiering; Reactive (Level 2)
> on Continuous Monitoring — no vendor gets re-checked between annual cycles. Tier-1 assessment
> currency is 74% against a 100% target. Industry benchmarking surveys report 30–45 day median
> assessment cycle time; ours is 51."*

### Why this is not EB, and must not be merged into it
EB answers *"is this vendor's Posture normal, good, or poor for its peer group of vendors."* P9 answers
*"is our program — governance, coverage, cycle time, automation — normal, good, or poor for a peer
group of TPRM programs."* The subject being benchmarked is different (one vendor vs. the whole
program), the peer group is different (similar vendors vs. similar TPRM programs, per Shared
Assessments / Gartner / Crowe survey data), and the output is different (a placement per vendor vs. a
maturity score per program dimension). Conflating them produces a metric nobody can explain.

### Steps
1. **Adopt an 8-dimension, 5-level maturity model**, scored `Informal(1) → Reactive(2) →
   Defined(3) → Managed(4) → Optimized(5)` per dimension:
   Governance & policy · Inventory completeness & risk tiering · Assessment methodology & depth ·
   Continuous monitoring & threat intel · Remediation & issue management · Lifecycle coverage
   (incl. offboarding, fourth parties) · Technology/automation & data quality · Reporting &
   stakeholder engagement.
2. **Self-assess each dimension against what this codebase actually does**, not aspirationally —
   e.g. Lifecycle coverage cannot claim Managed while offboarding has no collector; Continuous
   monitoring cannot claim above Reactive until `monitor.py`'s cadence is more than annual. Score
   is limited by its *weakest* dimension, not an average — a program is not "Managed overall" because
   three dimensions are and five are not.
3. **Build a small (≤15-metric) KPI/KRI dashboard from data the platform already produces** — do not
   invent new collection for this:

   | Metric | Source already in this codebase |
   |---|---|
   | Tier-1 coverage / assessment currency | `/api/portfolio`, P2 coverage statement |
   | Assessment cycle time | pipeline timestamps (`pipeline.py`) |
   | Critical finding remediation SLA | P3 evidence pack `recheck_after` + dispute resolution timestamps |
   | Residual risk distribution by tier | E10b matrix |
   | Fourth-party concentration | P1 |
   | Framework alignment score | E9c Compliance Gap coverage |

   Metrics with **no OSINT source** (staffing ratio, cost per assessment, stakeholder satisfaction,
   exception rate) are **manually supplied inputs**, tagged as such — never backfilled or estimated
   to make the dashboard look complete.
4. **External peer comparison is a process, not a build.** Participation in Shared Assessments /
   Gartner / Crowe benchmarking surveys happens outside this codebase; the deliverable here is a place
   to record the resulting peer figures against our own, with the survey name, year and *n* disclosed
   next to every comparison — the same honesty discipline EB enforces for vendor cohorts.
5. **Governance cadence**: quarterly KPI review, annual full maturity re-assessment, methodology
   documented for audit/exam defensibility.

### The same honesty rules EB already proved out — apply them here too
- Never publish a peer figure without disclosing the survey, year, and *n*.
- A thin or single-source peer comparison must say so, not be presented as robust.
- A maturity level is a self-assessment with a documented rationale per dimension, not a computed
  score — do not build a formula that produces a fake precision.

### Exit criteria — ✅ all met (`P9`)
- [x] **8-dimension maturity model**, each scored 1–5 with a written rationale citing what in the codebase justifies the level — `app/program_maturity.py`, assessment v1.0.0 dated 2026-07-31
- [x] **Overall maturity stated as the minimum**, not an average — `overall_level()`, and a test asserts the minimum is *strictly below* the average so the distinction cannot quietly stop mattering
- [x] **KPI/KRI dashboard: 15 metrics**, each with owner, formula, data source, target and refresh cadence — `app/program_kpis.py`, capped by assertion at import
- [x] **Every metric tagged** `platform-derived` (11) or `manually-supplied` (4) — and an unsupplied manual metric renders `null` with its owner named, never backfilled or estimated
- [x] **Nothing reaches a vendor score** — asserted structurally on both modules: neither imports the engine or the pipeline, neither calls any `put_*`, and `program_maturity` imports only `__future__`, `dataclasses` and `typing`
- [x] **External peer figures carry survey, year and *n*** — `peer_figure()` raises `PeerFigureError` without all three
- [x] 67 + 5 tests · `GET /api/program/maturity` · `GET /api/program/kpis` · `GET /api/program`

> ### The assessment: **Level 2 (Reactive)**, and the low dimensions are the deliverable
>
> **v1.1.0, re-assessed 2026-08-01.** Two dimensions moved, and both re-scores were *forced by this
> file's own claim tests* rather than volunteered — see the anti-staleness note below.
>
> | Dimension | Level | Held there by |
> |---|:--:|---|
> | Governance & policy | 3 Defined | No named owner in the repo, no scheduled model review |
> | Inventory completeness & risk tiering | 3 Defined *(was 2)* | Every declaration is **provisional**, none confirmed; nothing reconciles against procurement/AP |
> | Assessment methodology & depth | 4 Managed | Never calibrated against realised outcomes (E0.4 deferred) |
> | Continuous monitoring & threat intel | 3 Defined *(was 2)* | One run recorded, by hand; no host has the timer installed. Threat intel still point-in-time |
> | Remediation & issue management | 3 Defined | `recheck_after` stated per finding, enforced nowhere in aggregate |
> | **Lifecycle coverage** | **2 Reactive** | **No offboarding workflow or collector — the plan names this gap.** The only dimension at the floor |
> | Technology / automation & data quality | 3 Defined | The sanctions false-positive rate went unmeasured for months; still no standing precision instrumentation |
> | Reporting & stakeholder engagement | 4 Managed | No evidence the reports drive recorded decisions |
>
> **The average is 3.1 and the minimum is 2.** That gap is exactly why the plan specifies the
> minimum: reporting an even 3 would describe a programme that does not exist, and would conceal
> that offboarding — the whole end of the vendor lifecycle — is unbuilt.
>
> **The v1.0.0 assessment (2026-07-31) read Level 2 held down by THREE dimensions.** It is now held
> down by one, and that is the useful change: "we are Reactive because monitoring, inventory and
> offboarding are all missing" is a programme-wide indictment nobody can start on. "We are Reactive
> because there is no offboarding workflow" is a piece of work.
>
> **The technology/data-quality level is scored on what this week actually found.** Automation is
> Managed-grade — nineteen collectors, one failure-isolated path, evidence written before scoring,
> a loader that refuses to start on invalid config. But the sanctions matcher blocked 10 of 114
> household-name companies and **that rate had gone unmeasured for months**, found by a seeding run
> rather than by an instrument. A programme whose data-quality defects surface by accident is
> Defined, not Managed. Scoring it 4 would have been the flattering read of our own best week.
>
> ### The anti-staleness mechanism, which is worth more than the levels
>
> A hardcoded self-assessment is wrong the moment somebody builds the thing it says is missing, and
> here the dangerous direction is *understating*: a programme that fixed something and still reports
> Reactive stops being believed, and then nobody reads any of it.
>
> So every level cites **checkable claims about the tree** — modules that must exist, modules that
> must **not**, routes that must be served — and the suite walks them. Building `app/offboarding.py`
> fails the test that says lifecycle coverage is Reactive *because* offboarding is absent. **A
> failure there is not a bug; it is the signal to re-score that dimension.** Same discipline
> `_validate_no_dead_config` applies to `scoring.yaml`: an assessment is a claim, and a claim
> nothing checks is a claim that drifts.
>
> ### What the dashboard found on the real book, immediately
>
> Run against the live store (146 vendors):
>
> | Metric | Value |
> |---|---|
> | `inherent_tier_declaration_rate` | **0.0%** |
> | `residual_risk_distribution` | `{not_published: 146}` |
> | `tier1_assessment_currency` | *not computable — no critical-tier vendor exists to measure* |
> | `published_posture_rate` | 89.0% |
> | `ghost_rate` | 2.7% |
> | `blocked_pending_adjudication` | 12 |
> | `assessment_cycle_time_median` | 28.3 s |
>
> **Three of those are one finding.** Not a single vendor in the book has a declared inherent tier,
> so E10b publishes no residual risk for any of them, P3 tags every pack item `untagged`, and P5
> routes every relationship to full depth as an unclassified placeholder. The dashboard did not
> discover a new problem — it made an existing, silent, book-wide one countable, which is the whole
> claim of the phase.
>
> Cycle time is **28.3 seconds**, and that is the automated leg only. Survey figures of 30–45 *days*
> measure a full human assessment cycle and are not comparable; the metric says so on its own row,
> because a dashboard that quoted 28 seconds against a 30-day benchmark would be the most flattering
> number in the document and the least true.
>
> ### Two kinds of missing, kept apart
>
> `unsupplied` (a manual metric nobody has supplied — a programme gap with a named owner) and
> `not_computable` (a platform-derived metric with no population to measure — a fact about the
> book). One list for both would let an unmeasurable metric read as an unassigned chore. Same rule
> P2 applies to its three coverage buckets.

---

# Governance — what attaches as you go

| Trigger | Obligation |
|---|---|
| E2 changes what signals cost | **Notice before the change**, not after |
| E3 / E4 move `planned_signal_count` | Confidence shifts for no evidential reason. Disclose, or ship per-axis confidence |
| E5 changes categories + divisor | **Largest single re-score in the plan.** Version and give notice |
| E6 / E12 introduce a denominator | **Publish it**, with sampling rule and multi-tenant exclusions |
| E7 changes the ladder | Label expert-set severities *expert judgment until calibrated* |
| E10 publishes cohort placement | Make cohort assignment **disputable** — ✅ **done in EB**: inputs are disputable, the cell is not representable as a target, and an open dispute notates the placement until resolved |
| Continuity publishes going-concern facts | **Registry-cited only.** A derived distress index is credit-rating territory |
| E13 changes the scale's meaning | New version, notice period, side-by-side publication |

**Scheduled change to record now:** CA/Browser Forum Ballot SC-081v3 compresses certificate lifetimes to **100 days from March 2027** and **47 days from March 2029**. An expired certificate stops meaning *"someone forgot"* and starts meaning *"no lifecycle automation."* `cert_validity` is the only ceiling-arming signal, so this reaches further than it looks.

---

# Invariants — a change that breaks one is out of scope

| Invariant | Enforced at |
|---|---|
| Posture and Confidence never collapse into one number | Separate `Score` fields |
| Missing data reduces Confidence, never Posture | Fixed divisor, `engine.py:187` |
| Evidence stored before scoring | `pipeline.py:145` precedes scoring at 186 |
| Every penalising band has a reason + action + recheck date | Loader **refuses to start** otherwise |
| No natural-person data | `excluded_signals` — §4.2 bright line |
| Ongoing findings never decay | `modifiers.age.never_decays` |
| Disclosed-never-scored | Fourth parties, concentration, coverage gaps |
| Frozen corpus moves deliberately | `python -m tests.regolden` |

---

# Anti-patterns — recorded so they are not re-proposed each quarter

1. **Ability-to-pay bias.** *Currently violated:* `cert_posture.none_claimed` costs 8 points, fires on 5 of 5. Fixed by E2
2. **Context multipliers on penalties** (*"×1.5 large, ×0.6 startup"*). Rejected on five grounds. The anomaly is real and belongs to the Expectation Gap
3. **Suspending penalties after M&A.** Dynamic severity adjustment wearing a hat. Gameable
4. **Reweighting absence-of-evidence for regulated firms.** A sector promotion entering through the confidence door
5. **Financial distress as a cyber proxy.** Separate vectors, separate axes
6. **Category weights.** §5.6 deleted them. Percentages look principled and are unfalsifiable
7. **Natural-person signals.** Employee sentiment, key-person dependency, leadership controversies, diversity data
8. **Customer review corpora.** A reputation axis built on review volume is a size classifier wearing a halo
9. **Numeric Continuity score.** Four registry bands cannot support 0–100 precision
10. **Residual Risk as a measured axis.** It is a lookup over two published inputs

---

# Appendix A · Commands

```bash
cd backend && source .venv/Scripts/activate      # PowerShell: .venv\Scripts\Activate.ps1

# after ANY scoring.yaml edit — catches every loader trap at once
python -c "from app.scoring_config import load_scoring_config as L; c=L(); \
  print('OK', c.version, 'signals', c.planned_signal_count(), 'bands', len(c.penalising_bands()))"

# the corpus: the evidence for every phase
pytest tests/test_corpus.py -q
python -m tests.regolden
git diff tests/fixtures/golden_scores.json        # <-- THIS DIFF IS THE CHANGE. Read it.

pytest tests/test_scoring.py tests/test_scoring_config.py tests/test_actions.py -q   # E1–E7
pytest tests/test_benchmark.py tests/test_cohorts.py -q                              # v1 benchmark (deprecated)
pytest tests/test_benchmarking.py -q                                                 # EB — 91 tests, <1s, no DB
pytest tests/test_disputes.py -q                                                     # E6 band-key risk
pytest -q                                                                            # full, ~345s

# EB config: the hard rules are validated at LOAD, so this catches a bad threshold at startup
python -c "from app.benchmarking.config import load_benchmarking_config as L; c=L(); \
  print('OK', c.version(), 'quartile>=', c.min_quartile_n(), 'percentile>=', c.min_percentile_n())"

python -m app.score_harness --domain atlassian.com --ref atlassian --name Atlassian
python -m app.seed_cohorts --all --concurrency 2
```

# Appendix B · Config-key registration

Every new top-level `scoring.yaml` key must be registered or the app will not start.

| Phase | Key | Action |
|---|---|---|
| E1 | `industry_profiles` | **Remove** from `_ENGINE_READS`, delete the YAML block together |
| E6 | `exposure` | **Add** to `_ENGINE_READS` |
| E7a | `aggregation` | **Move** from `_DOCUMENTATION_ONLY` to `_ENGINE_READS` |
| E7c | `root_cause` | **Add** to `_ENGINE_READS` |
| E8 | `gates.*` | Already read; preserve `sanctions.behaviour == "block"` |
| E9 | `assurity` | **Add**, or keep in `benchmarks.yaml` which has no such guard |

# Appendix C · Effort and critical path

| Track | Phase | Weeks | Changes scores |
|---|---|--:|:--|
| E | 0 Instrument | 2–3 | no |
| E | 1 Sector opinion | 1 | ≈0 |
| E | 2 Stop penalising the norm | 1–2 | yes |
| E | 3 Merge duplicates | 0.5 | yes |
| E | 4 Continuity relocation | 1 | yes |
| E | 5 Categories + divisor | 1–2 | **everywhere** |
| E | 6 Denominator (free half) | 1 | yes |
| E | 7 Aggregation + ladder | 2–3 | yes |
| E | 8 Gates | 1 | no |
| E | 9 Assurity + Compliance Gap | 3–4 | no |
| E | 10 Expectation Gap + Tier | 2 | no |
| E | 11 Real cohorts | ongoing | no |
| E | 12 Collector fan-out | **6–10** | **substantially** |
| E | 13 Log-odds | 3–4 | **substantially** |
| E | **14 LLM gap analysis** | 2–3 | **no** — a read layer, asserted |
| **EB** | **Peer benchmarking v2** | — | **no** — ✅ delivered |
| P | 1–3 Concentration · Coverage · Evidence Pack | **3** | no |
| P | 4–8 Flow-downs · Tier depth · Views · Status · Exit | 7–9 | no |
| P | 9 Program maturity + KPI/KRI benchmarking | 2–3 + ongoing | no |

**Engine critical path:** E0 → E1 → E2 → E4 → E5 → E6 → E7 ≈ **10–14 weeks**.
E0.1, E1 and E2's code are done, so the remaining path is **E2 justification → E3 → E4 → E5 → E6 → E7**.

**Product first value:** P1–P3 ≈ **3 weeks**, starting now, no engine dependency. **Still not started** —
this remains the largest unclaimed value in the plan.

---

## What to tell a sponsor in three sentences

1. The score still measures **how big a vendor is** as much as how well it is run — a company entering administration loses 20 points of *technical security* posture, and the biggest single penalty line for every corpus vendor is a raw host count with no denominator.
2. Fixing that is 10–14 weeks of engine work with a corpus diff proving every step; **the first three phases are done** (the suite went from 15 red to green, the sector opinion is out of the arithmetic, and vendors are no longer charged for not doing what almost nobody does).
3. Separately and in parallel, **three weeks of product work** — concentration, coverage statement, evidence pack — turns a security rating into something a procurement team can actually sign against, and **none of it has started**.

### And one thing that shipped early

**Peer benchmarking (EB) is delivered.** A supplier is now placed against a real peer group with the
population always disclosed, a percentile only above n=30, a quartile only above n=8, an honest
refusal below that, and a dispute path for the cohort itself. It is the first output in the system a
procurement team can read without a caveat from us about how to read it.

### And one gap the analysis surfaced

**Nothing yet benchmarks the program.** EB tells a buyer whether one vendor is normal for its peers.
Nothing tells us whether *our TPRM function* — coverage, cycle time, automation, maturity — is normal
for a peer TPRM function. That is **P9**, newly added, and it is cheap to start: the maturity model and
dashboard scaffold need no engine work, only an honest self-assessment against what already exists.

---

## Document maintenance

**Re-audited 2026-07-30 against the working tree.** Three things in the previous revision had gone
stale and are corrected above: Sprint 0 item 2 was recorded as *"written, not verified"* when it was
already committed and test-pinned; E2's band table listed six bands where eight were required; and
the baseline header still quoted `417 passed, 15 failed`.

> **Status claims in this document are measured, not carried forward.** Before quoting one, re-run
> the loader check and `pytest -q` in [Appendix A](#appendix-a--commands). A runbook whose status
> table is stale is worse than one with no status table, because it is believed.
