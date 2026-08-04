# TPRM Feedback Redesign — Implementation Plan

**Status:** Draft for review · **Prepared:** 2026-08-04 · **Owner:** engineering
**Responds to:** stakeholder feedback on financial data integration, scoring-model test coverage, and the scorecard UX
**Governing precedent:** [`change-notice-v5.md`](change-notice-v5.md), [`continuity.py`](../backend/app/continuity.py), [`source_assessment.md`](source_assessment.md), [`roadmap.md`](roadmap.md), [`frontend_redesign_plan.md`](frontend_redesign_plan.md)

---

## 0. Constraints this plan inherits — read before implementing

The platform already made, and documented, three decisions that every recommendation below must respect. Re-deriving them would repeat work the codebase has already paid for, in blood (E4 shipped *because* mixing these axes cost a vendor 20 posture points for entering administration).

1. **Posture is security-only, and financial/going-concern facts do not touch it.** `scoring.yaml` v5.x has five *scoring* categories (`breach_compromise_history`, `attack_surface_hygiene`, `identity_email`, `transparency`, `compliance_regulatory`) and two *context* categories (`continuity_context`, `assurance_context`) that are asserted, by a shipped test, to never carry a penalty. This is not a gap to close — it is the fix for a real defect (E4, `change-notice-v5.md` §3.4). Any new financial signal is a **context** signal by default; it needs an explicit, argued exception to become a scoring one.
2. **No invented numeric financial score.** `continuity.py`'s docstring gives the reasoning directly: four-to-five registry bands can't support hundred-point precision, and a derived distress index is credit-rating territory — defamation-adjacent when wrong. The existing `Continuity` module publishes a **qualitative standing** (`ceased` / `impaired` / `watch` / `sound` / `unknown`) with a cited, dated fact per flag, never a blended number. This plan extends that module; it does not replace it with a score.
3. **Sources must clear the same legality bar as everything already shipped**: free (or free key), commercial-and-automated use permitted, no ToS trap, reachable and parseable (`roadmap.md` §0, `source_assessment.md`). D&B-style credit scoring, Altman Z-score inputs, cash-burn/funding-runway data, and any natural-person financial data (personal bankruptcy, director credit files) are explicitly out of scope — held on `held_roadmap`, not silently dropped.

Where the stakeholder feedback below asks for something that would violate one of these three, the recommendation is adapted to fit the constraint rather than the constraint being relaxed — with the reasoning stated inline so it can be argued with.

---

## Phase 1 — Financial & Business Stability Data Integration

### 1.1 Source register (deliverable: new rows in [`source_assessment.md`](source_assessment.md))

| Source | Coverage | Cost | What it provides | Status |
|---|---|---|---|---|
| **Companies House (UK)** | UK-registered entities | Free, keyed (600 req/5min), OGL | Company status incl. `liquidation`/`receivership`/`administration`/`insolvency-proceedings`; **insolvency practitioner filings** (not yet wired); **charges register** (secured-lending load — a leverage signal); filing-history gaps | **Already built** (`companies_house_collector.py`) — extend to insolvency + charges endpoints |
| **ABN Lookup (AU)** | AU-registered entities | Free, keyed GUID | Registration status incl. `Cancelled` | **Already built** (`abn_collector.py`) — extend cancellation-reason parsing |
| **GLEIF (LEI)** | Any LEI-holding entity, global | Free, no key | Registration status incl. `Lapsed`/`Merged`/`Retired`/`Duplicate`/`Annulled` | **Already built** (`gleif_collector.py`) — extend mapping for irregular statuses |
| **The Gazette (UK)** | UK entities | Free, Crown copyright/OGL, no ToS trap | Official notices: winding-up petitions, liquidator/receiver/administrator appointments, insolvency notices | **New** — `gazette_collector.py`. Cleanest signal on the table: it is the primary legal record, not a downstream aggregation |
| **SEC EDGAR (US)** | US SEC-registered/public companies only | Free, no key | Full-Text Search API for XBRL `goingConcern` flag in filed statements; **8-K Item 1.03 (bankruptcy)** filed within 4 business days of the event — timely and structured | **New** — `edgar_collector.py`. Narrow coverage (public companies only) but very high signal quality where it applies |
| **CourtListener / RECAP (US)** | US federal court filings | Free, documented API | Bankruptcy case dockets (Ch. 7/11 petitions) by party name | **New, narrow scope** — bankruptcy-petition search only, not general litigation (litigation search is a separate, larger roadmap item already flagged in `roadmap.md` §6) |
| **OpenCorporates** | 140+ registries, global aggregation | Free tier (rate-limited); bulk data is paid | Corroborating dissolution/liquidation status codes across jurisdictions Companies House/ABN/GLEIF don't cover | **Held pending ToS confirmation** — treat like DFAT/Modern Slavery in `roadmap.md` §2.4: ask before you collect |
| ~~D&B Paydex / credit score~~ | — | Paid, proprietary methodology | Credit rating | **Excluded** — no lawful free source; opaque methodology we can't cite a fact against |
| ~~Altman Z-score, cash burn, funding runway~~ | — | Requires financial statements not publicly filed (private cos.) | Solvency prediction | **Excluded** — `continuity.py` already names this as `held_roadmap`: no lawful free source |
| ~~AFSA personal bankruptcy / director credit files~~ | — | — | Individual insolvency | **Excluded on principle**, not just availability — natural-person data is out of scope per the existing §4.2 bright line (no natural-person data enters the model) |

### 1.1a Equities/market-data APIs — evaluated separately, verified 2026-08

A stakeholder also asked about eight equities/market-data providers (Alpha Vantage, Finnhub, Yahoo Finance, Marketstack, IEX Cloud, Twelve Data, Financial Modeling Prep). These are a different category from the registries above — market-data vendors, not company registers — and share one capping limitation: **they only have data for publicly-traded companies**, a minority of typical TPRM vendors. Status verified against each provider's current (2026) terms:

| Source | Free tier (verified 2026) | Data type | ToS / commercial-use status | Verdict |
|---|---|---|---|---|
| **Financial Modeling Prep** | 250 req/day, permanent, no card | Full fundamentals (balance sheet/income/cash-flow) **and** precomputed Altman Z-Score / Piotroski Score | Free tier usable for real testing; redistribution/commercial terms need direct confirmation before building | **Best fit — adopt, pending ToS confirmation** |
| **Twelve Data** | 800 credits/day | Price + fundamentals (balance sheet gated harder on free tier) | Standard "internal use" license; redistribution unclear | **Secondary candidate** — mainly for delisting/price-decline flags |
| **Alpha Vantage** | 25 req/day | Fundamentals + price | Commercial/redistribution requires separate paid licensing | **Hold** — free tier too thin for portfolio-scale scanning |
| **Finnhub** | Free dev tier, ~60 calls/min | Fundamentals, insider transactions, IPO calendar | Must purge proprietary data at subscription end; commercial license required for production | **Hold** — same licensing gate as Alpha Vantage |
| **Yahoo Finance API / yfinance** | No official API — retired by Yahoo in 2017 | yfinance scrapes Yahoo's internal endpoints | ToS explicitly prohibits automated access without written permission; documented "personal use only" | **Reject** — the exact ToS trap the source-legality bar (§0.3) exists to catch |
| **Marketstack** | 100 requests/**month** | EOD price only — no fundamentals | Standard commercial terms | **Reject** — too thin to cover a portfolio; wrong data type (price, not balance-sheet facts) |
| **IEX Cloud** | — | — | **Shut down permanently 31 Aug 2024** | **Dead — drop from consideration** |

**How this plugs into the model, if adopted:** same rule as everything else in §0 — `continuity_context`, informational bands, never posture, never a new numeric score. The only genuinely new facts these add beyond `edgar_collector.py` (§1.1, which already covers the authoritative going-concern signal for US public companies) are **delisting/exchange non-compliance notices** and **sustained stock-price decline** (e.g. >50% over 6 months) — both dated, citable observations, same treatment as a Companies House filing. **Do not** pull raw fundamentals and compute an in-house Altman Z-score from them — that repeats exactly the "derived distress index is credit-rating territory, defamation-adjacent when wrong" reasoning already used to exclude this in `continuity.py` (lawful source access does not relax that rule). If FMP's own precomputed Financial Health Score is ever surfaced, it must be shown as an attributed citation ("FMP's calculated score") — never blended into the Business Stability standing, which stays qualitative per §1.3.

### 1.2 Collector work

- Build `gazette_collector.py`, `edgar_collector.py`, `courtlistener_bankruptcy_collector.py` following the existing collector contract (failure-isolated, emits `Finding`s with `source`, `observed`, `evidence_id`, retrieval timestamp — see any existing collector for the pattern).
- Extend `companies_house_collector.py` (insolvency + charges endpoints), `abn_collector.py`, `gleif_collector.py` (irregular-status mapping).
- **All new signals land in `continuity_context` in `scoring.yaml`, at `informational` bands only** — mirroring the existing `entity_status`/`entity_existence`/`domain_registration` pattern exactly. This is enforced today by a shipped test that asserts context categories never carry a penalty; extend that test's parametrization to cover the new signals rather than writing a new one from scratch.
- Extend `continuity.py`'s `_FLAGS` mapping with the new `(signal, band) → (standing, statement)` tuples, e.g. `("insolvency_notice", "winding_up_petition") → ("ceased", "The Gazette records a winding-up petition against this entity — …")`. Every new entry must carry a `cited()`-compatible source + retrieval date; this is the non-negotiable guardrail that keeps the module publishable without defamation exposure (`continuity.py` lines 15–26).

### 1.3 Where does it score? — answering the feedback's central question directly

**Recommendation: not the cybersecurity posture score, and not a new numeric "Business Stability score" either — a qualitative standing axis plus a rule-based procurement layer.**

- **Not posture.** Re-mixing financial distress into the cyber score reintroduces the exact defect E4 removed (`change-notice-v5.md` §3.4): a vendor's TLS configuration does not change when they enter administration, and a security reader needs posture to mean *only* security or it stops being comparable across vendors.
- **Not a new 0–100 "Business Stability score".** The reasoning in `continuity.py` (lines 15–26) already rules this out for exactly the same evidentiary reason the posture score itself is defensible: 5–6 registry bands cannot support hundred-point precision, and a derived distress index is a different *kind* of claim than a cited fact — one the platform can't stand behind if it's wrong. This is the load-bearing reason for the whole recommendation, so it is worth restating to whoever raised the "or a Business Stability score" option in the feedback.
- **Instead:** surface the **existing `Continuity.standing`** (`ceased`/`impaired`/`watch`/`sound`/`unknown`) under the user-facing label **"Business Stability"** — same data, same architecture, a label stakeholders asked for. This is a display change, not a scoring change.
- **New: a deterministic procurement-rules layer** (`backend/app/procurement_rules.py`), separate from both posture and standing, so the financial signal still drives a concrete action without becoming a number:

| Standing | Trigger examples | Procurement rule (advisory text, legal review required before ship) |
|---|---|---|
| `ceased` | Liquidation, dissolution, winding-up petition | "Do not proceed to contract without evidence of a successor entity or novation." (blocking flag) |
| `impaired` | Domain suspended, administrator appointed | "Immediate continuity risk — escalate to security and legal before renewal." |
| `watch` | Registration lapsed, domain expiring, new high secured-charge filing | "Request an updated register extract before signing." |
| `sound` | No adverse filings in lookback window | "No continuity concerns identified from public registers." |
| `unknown` | No coverage for this vendor's jurisdiction | "Business Stability could not be evidenced — treat as unknown, not as clean." (mirrors the existing Ghost-vendor principle: absence of data is never presented as health) |

- **Coverage, not a score, for the confidence-adjacent question.** Report "Business Stability evidence: N of M available checks returned data for this jurisdiction" — the same style of denominator the posture confidence axis already uses, applied to this axis instead of blended into it.

### 1.4 Legal/compliance guardrails

- Every new flag must carry source + retrieval date — no exceptions (matches `continuity.py`'s existing non-negotiable).
- No natural-person data, ever — bright line already established, applies unchanged to any new financial source.
- Ambiguous-ToS sources (OpenCorporates bulk) go through the same "ask licence first, `held` until confirmed" gate as DFAT/Modern Slavery in `roadmap.md` §2.4 — not "collect first, check later."
- Procurement-rule *wording* needs legal/compliance sign-off before shipping — it's advisory language a procurement team will act on, not an internal engineering string.

---

## Phase 2 — Vendor Comparison Test Cases

**Approach:** follow the existing convention in `backend/tests/test_scoring.py` — build synthetic `Finding`/`CollectorResult` objects and score them against the **real** `scoring.yaml` (never a mock), so a scenario breaks the moment the config drifts from the stated behaviour. New file: `backend/tests/test_vendor_comparison_scenarios.py`. Each scenario is also written up in plain English in a companion doc, `docs/vendor_comparison_scenarios.md`, so procurement/security/exec stakeholders can review it as acceptance criteria, not just as unit tests.

| # | Scenario | Vendor A vs Vendor B | Expected Δ Posture | Expected Δ Confidence | Expected Δ Business Stability | Reasoning / what it guards |
|---|---|---|---|---|---|---|
| 1 | Adverse media | Severe, substantiated GDELT-adjudicated hit vs none | A scores lower (breach/compliance category penalty) | Roughly equal if coverage is equal | Unaffected | Confirms adverse media reaches the score through a scored category, not through Continuity |
| 2 | **Bankrupt vs healthy** | `ceased` (Gazette winding-up petition) vs `sound`, **all cyber signals held identical** | **Zero** — postures must be byte-identical | Zero | A shows `ceased`, B shows `sound` | The direct regression guard for the E4 defect (`change-notice-v5.md` §3.4) and the single most important scenario to demonstrate to whoever gave this feedback: financial distress is real and visible, but it cannot move the security number |
| 3 | Breach history | Multiple recent `breach_by_data_class` entries vs none | A scores lower, proportional to the aggregation-decay math | Equal (breach category scores either way; coverage unaffected) | Unaffected | Exercises `breach_compromise_history` and the diminishing-returns aggregation together |
| 4 | Email security | DMARC `none`/SPF `none` vs DMARC `reject`/SPF strict | A scores lower on `identity_email` | Equal | Unaffected | Straightforward category-swing case, good smoke test for `normalize.py` band mapping |
| 5 | **Certificate posture** | `cert_validity: expired_serving_prod` vs `valid` | A is **capped by the critical ceiling**, not merely penalised — `cert_validity` is the sole entry in `critical_ceiling.auto_signals` and is flagged `never_decays` | Equal | Unaffected | Distinguishes a normal category penalty from a knockout — worth its own assertion since it's the only signal wired to the ceiling |
| 6 | **Evidence coverage** | Thin coverage ("Ghost" — most collectors return no data) vs broad coverage, both otherwise clean | Raw posture may look similar or better for the Ghost | **Confidence collapses for the thin-coverage vendor**, capping the effective grade via the confidence-ceiling ramp | Report "unknown" coverage note if jurisdiction unsupported | Demonstrates why posture and confidence are reported as a pair, never one number — this is the scenario that most directly answers "how do strengths/weaknesses read at a glance" for the dashboard work in Phase 3 |
| 7 | **Assurance: claimed vs corroborated** | `cert_posture: registry_corroborated` vs `program_disclosure: detailed_policies` only (no registry match) | Only the corroborated case scores (in `compliance_regulatory`); the disclosure-only case is `informational` (`assurance_context`) | Coverage differs slightly by category composition | Unaffected | Tests the exact E5 distinction the codebase draws (`change-notice-v5.md` §3.6): a certification claim corroborated against a registry is evidence; a marketing trust page is not |
| 8 | **Regulatory action vs sanctions match** | `regulator_action` finding (soft penalty in `compliance_regulatory`) vs a sanctions-list match (hard **gate** — blocks scoring, routes to human adjudication) | A scores lower; B **does not receive a published score at all** until adjudicated | N/A for B until released from the gate | Unaffected | Distinguishes the two very different mechanisms the platform uses for "this is bad" — a penalty vs a stop — which the dashboard must render differently (Phase 3) |
| 9 *(stretch)* | Compounding findings | Expired cert **and** no DMARC on the same vendor vs either alone | Combined penalty is **less than the arithmetic sum** of the two individually | Equal | Unaffected | Exercises `aggregation_decay` / diminishing-returns directly — useful regression coverage, not required by the feedback but cheap to add alongside #5 and #4 |

Scenarios 1, 3, 4, 5, 6, 7, 8, 9 need no new collectors and can be built immediately against the current model. Scenario 2 can be built today using the existing `continuity.py`/Companies House data and re-run once the Phase 1 sources land, to confirm the invariant still holds with the larger evidence set.

---

## Phase 3 — Executive Dashboard Redesign

### 3.1 Starting point

`docs/frontend_redesign_plan.md` already specified and largely shipped a "What / So what / Now what" structure (`Scorecard.jsx`, `VendorProfile.jsx`, components like `<PostureConfidencePair>`, `<GhostState>`). **This phase extends that plan — it does not replace it.** The gap between what's built and what the feedback asks for is: no single glanceable hero row, no explicit Business Stability treatment, no consolidated recommendations panel, and the detailed sections (`BenchmarkCharts.jsx`, `GapAnalysis.jsx`, `Dependencies.jsx`, `Assurance.jsx`) aren't yet organized as a clear "drill-down" tier under a summary.

### 3.2 Information hierarchy

**Tier 1 — glance, under 15 seconds.** Everything a stakeholder needs without scrolling or clicking:

- Vendor name/domain, last scored date
- Overall status/grade badge
- Posture score (with trend arrow if history exists)
- Confidence badge — with the existing Ghost-state treatment if coverage is thin, since scenario 6 shows this is where a clean-looking score can mislead
- Assurity badge
- **Business Stability** badge (the `Continuity.standing` value, relabeled per §1.3)
- Inherent vs Residual risk, shown as a pair (not two disconnected numbers) so the delta — what controls/mitigations actually bought — is visible at a glance

**Tier 2 — scan, 30–60 seconds.**

- Top 3 strengths and top 3 weaknesses, ranked by penalty magnitude (weaknesses) and by category headroom (strengths)
- Key recommendations — merges existing remediation guidance with the new Phase 1 procurement-rule output, so a `ceased`/`impaired` Business Stability flag surfaces here, not buried in a sub-tab
- Evidence coverage bar — overall fraction plus a per-category breakdown (X of 27 signals), including the new Business Stability coverage fraction from §1.3

**Tier 3 — drill-down, on demand.** Existing components, reorganized under tabs/accordion rather than a single long scroll: category-by-category breakdown (`VendorProfile.jsx`), peer benchmarking (`BenchmarkCharts.jsx`, `PeerBenchmark.jsx`), gap analysis (`GapAnalysis.jsx`), dependencies (`Dependencies.jsx`), full assurance detail (`Assurance.jsx`), and the full cited Continuity/Business Stability flag list with sources and retrieval dates.

### 3.3 Wireframe

```
┌─────────────────────────────────────────────────────────────────────┐
│  Acme Vendor Co.   acme.com          Last scored: 2026-08-01         │
├─────────────────────────────────────────────────────────────────────┤
│  OVERALL   POSTURE   CONFIDENCE   ASSURITY   BUS. STABILITY   INH/RES│
│   B         78/100      Ghost⚠      Partial      Watch          H→M  │
│  (grade)   (trend ↓2)  (thin cov.) (badge)     (standing badge) (pair)│
├─────────────────────────────────────────────────── TIER 1 ───────────┤
│  ▲ Top strengths            ▼ Top weaknesses      ⚑ Recommendations  │
│  • Strong TLS/HSTS           • DMARC absent          • Renew domain  │
│  • DMARC reject policy       • Domain expiring soon    before <date> │
│  • No known breaches         • Thin evidence cov.    • Confirm SOC2  │
│                                                        claim (unverif)│
├─────────────────────────────────────────────────── TIER 2 ───────────┤
│  Evidence coverage:  ████████░░  21/27 signals · Bus.Stability 3/4   │
├────────────────────────────────────────────────────── TIER 3 ────────┤
│  [ Category Detail ][ Peer Benchmark ][ Gap Analysis ][ Dependencies]│
│  [ Assurance Detail ][ Business Stability — full citations ]         │
│  (tab content renders below, existing components, unchanged)         │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.4 Component work

- `<ExecutiveSummaryHero>` — new, composes the existing `<PostureConfidencePair>` plus new `<AssurityBadge>`, `<BusinessStabilityBadge>` (wraps `Continuity.standing`), `<InherentResidualPair>`.
- `<TopFindings>` — new, ranks weaknesses by penalty magnitude and strengths by category headroom; reuses existing finding-formatting utilities already in `Scorecard.jsx`/`VendorProfile.jsx`.
- `<RecommendationsPanel>` — new, merges existing remediation text with `procurement_rules.py` output from Phase 1.
- `<EvidenceCoverageBar>` — new, per-category + Business Stability coverage; links straight into the relevant Tier-3 tab.
- `<VendorDetailTabs>` — new wrapper, reorganizes the *existing* `BenchmarkCharts`, `GapAnalysis`, `Dependencies`, `Assurance` components under tabs/accordion; no changes to those components' internals required.
- **Load the `dataviz` skill before implementing any new badge, tile, or coverage bar** — it governs the color system (avoid a plain traffic-light palette) and accessibility rules; this is a build-time step, not part of this planning document.
- Reuse the existing `<GhostState>` component for any Tier-1 element with thin coverage, rather than inventing a new empty-state treatment.

### 3.5 UX notes and industry precedent

- Sticky hero row on scroll — stakeholders reference it while reading Tier 3 detail (pattern used by BitSight and SecurityScorecard's letter-grade header).
- Single "headline risk" callout in the Recommendations panel when one finding dominates — precedent: Black Kite's ransomware-susceptibility highlight, UpGuard's single risk score with category breakdown underneath.
- Progressive disclosure via tabs, not infinite scroll — precedent: OneTrust/ProcessUnity's workflow-and-recommendation-first layout, which the feedback's "too detailed to grasp at a glance" complaint is describing the absence of.
- Responsive layout — executives frequently review scorecards on tablets/phones between meetings; the hero row must reflow to a stacked layout below ~768px.

---

## Phase 4 — Testing, Rollout, Documentation

- **Backend:** pytest coverage for new collectors, `procurement_rules.py`, and the Phase 2 comparison scenarios. Confirm the frozen regression corpus (`backend/tests/regolden.py`) is **unchanged** by the new context-only signals — add a guard test asserting posture/confidence for the five corpus vendors are byte-identical before and after Phase 1 lands, the same style of proof `change-notice-v5.md` used for E1–E6.
- **Frontend:** no automated frontend test framework currently exists (confirmed — only `npm run lint`/`npm run build`). Manual QA pass rendering each of the 9 Phase 2 scenarios through the new dashboard is the practical substitute; recommend adding Vitest smoke tests as a follow-up, not a blocker for this rollout.
- **Docs to update:** `source_assessment.md` (new source rows), `methodology.md` and `roadmap.md` (mark the relevant "Business Stability" roadmap line as unlocked, per the existing `held_roadmap` bookkeeping pattern), new `docs/vendor_comparison_scenarios.md`, and a new `docs/business_stability.md` written in the same style as `change-notice-v5.md` — stating plainly, for future readers and auditors, that "Business Stability" is a relabeled, extended `Continuity` axis that has never affected and will never affect Posture. This preempts exactly the confusion E4 was written to fix, before it has a chance to recur under a new name.

---

## Sequencing and effort estimate

| Phase | Work | Estimate | Notes |
|---|---|---|---|
| 1 | Collectors + procurement rules + docs | 2–3 weeks | Companies House/ABN/GLEIF extensions are near-zero net-new (collectors exist); Gazette/EDGAR/CourtListener are new builds; OpenCorporates blocked on ToS confirmation |
| 2 | Test scenarios | 3–5 days | Runs largely in parallel with Phase 1 — 8 of 9 scenarios need no new collector |
| 3 | Dashboard components | 1–2 weeks | Mostly composition of existing components; genuinely new pieces are the hero row, recommendations panel, and coverage bar |
| 4 | Rollout, regression guard, docs | 3–5 days | Gated on Phase 1 shipping a stable procurement-rules API surface for the Recommendations panel to consume |

---

## Open questions for stakeholder sign-off

1. **Label change:** "Business Stability" as the public-facing name for `Continuity` — keep the `/api/vendors/{ref}/continuity` endpoint name and add a display alias, or version the API? (Recommend: display alias only; the endpoint is already referenced by name in docs and, presumably, integrations.)
2. **Procurement rule wording:** the advisory text in §1.3's table needs legal/compliance review before it ships — who owns that review?
3. **Source build order:** Companies House insolvency/charges extension is free and nearly built already; recommend it ships first. EDGAR is high-signal but US-public-company-only; OpenCorporates and CourtListener need ToS/licence confirmation before any collector work starts on them, per the existing "ask before you collect" gate.
