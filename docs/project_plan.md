# Project Plan — OSINT for Third-Party Risk

**Execution plan for Deliverables 2, 4 & 5**
**Status:** v0.1 draft · **Date:** 17 July 2026 · **Author:** *(intern)*

> **`methodology.md` is the product; this file is how it gets built.** The *what* and *why* of scoring are not repeated here — only sequencing, stack, and the decisions that have to be made to ship. Where this plan and the methodology disagree, **the methodology wins** and this file is wrong.

---

## 1. Objective

Ship a **client-ready** proof-of-concept that takes a vendor name or domain and returns a defensible, evidence-linked risk record and score for **five real named vendors**, with **automated collection, automated scoring, and automated scheduled re-checking**.

**The standard is set by the brief, and it is not "prototype":**

> *"The strongest work here is a serious candidate to go into our Wahid AI platform as an option under the third-party module."*

**Success is not "it runs."** Success is: a client asks *"why did this vendor score 62?"* and the answer is on screen, sourced, dated, and reconstructible from the evidence store months later.

---

## 2. Scope

### The one-sentence scope

**Five vendors, thirteen cleared sources, seven scored categories plus one gate, one screen, automated end to end.**

### In / out

| In scope | Out of scope | Why out |
|---|---|---|
| 12 cleared sources (`source_assessment.md`) | DFAT, Modern Slavery | **Licence unresolved — P0 blocker** |
| 7 scored categories + sanctions gate | Supply Chain, Data Privacy, ESG | Held at weight 0 (no live free collector) |
| Automated collection + scoring | Paid feeds | Brief: free/trial only |
| Scheduled re-scoring + delta flags | VirusTotal, SSL Labs | ToS prohibit our use case |
| Evidence store + explainability | Multi-tenant auth, RBAC | PoC, not platform |
| One vendor-detail screen | Vendor comparison / portfolio view | Roadmap |
| Confidence + refusal branch | FAIR $ quantification | Inputs don't exist |
| Light/dark, responsive, a11y basics | Mobile-native app | Responsive web suffices |

### Definition of done (per phase)

A phase is done when: it runs against **all 5 real test vendors**, the **empty/error/timeout paths are exercised**, and the **evidence store contains what the score claims**. Not when it works on Atlassian once.

### Build status

**Phases 0–3 are built and verified end-to-end against all five vendors** (Python/FastAPI backend, SQLite + Neon Postgres evidence store, 13 collectors, scoring engine, FastAPI API with SSE; 93 tests passing, ruff clean). The five-vendor live run caught two integration defects the unit tests missed — a coarse NVD keyword match frequency-amplifying distinct CVEs (a LOW CVE reached 100), and a swapped cert-band unpack that silently disabled the expired-cert knockout floor — both fixed with regression tests. **v3.2 source/confidence work:** EDGAR removed → **GLEIF** (business stability, all 5 vendors resolve); **regulator-RSS** adverse-media collector promoted to scored; **certspotter** fallback for crt.sh; **clean-receipt** coverage (§5.4.2) and the transparency/compliance **sub-gap fix** lifted four of five from *refused/ghost* to **evidenced_clean**. **v3.3 confidence work (the two earned levers):** ① per-request **retry+backoff** on the vendor-site collectors (dns/tls/headers/trust) so a transient blip stops manufacturing *the Ghost*; ② a second CC0 register — **Wikidata**, domain-verified — corroborating GLEIF, with an **earned corroboration uplift** (noisy-OR, §5.4.3) that lifts business-standing confidence 0.90 → 0.97 where the two registers agree (3 of 5 vendors). Live validation set updated: **Slack replaces Canva** (Canva kept as a documented HIBP-asymmetry reference); **Xero trialled and correctly BLOCKED** by the sanctions gate. With CT reachable, all five land **evidenced_clean** (~0.73–0.77); the model still ghosts a vendor honestly when a sole source (CT for Digital Footprint) is genuinely unavailable. Phases 4–6 (UI, automation, handover) are pending.

### PoC implementation boundary

`methodology.md` is the **target-state** methodology. v1 proves the **core defensible mechanics end-to-end** on the named vendors — the DMARC ladder, HIBP decay, the sanctions gate, the knockout floor, and two-axis confidence with the refusal branch. Features that are **designed in `scoring.yaml` but not fully wired in v1** are stated as such rather than implied complete: **multi-asset roll-up** (aggregation designed; multi-domain collection is Phase 3), the **dispute/attestation workflow** (designed, roadmap 6), the **weight sensitivity analysis** (open item 13), and **active-exposure** (deliberate constraint, roadmap 1a). This boundary is the honest answer to "can a PoC team actually ship all of this?"

---

## 3. OSINT Sources — implementation view

Positions are settled in `source_assessment.md`. What matters *for building*:

| Collector | Endpoint | Auth | Rate / limit | Failure mode to handle |
|---|---|---|---|---|
| `ct` | crt.sh → **certspotter fallback** | none | **polite self-limit**, honest UA | crt.sh outages → retry then fall back |
| `dns` | system resolver | none | — | NXDOMAIN vs SERVFAIL differ |
| `tls` | own client (`sslyze`) | none | 1 handshake | Timeout, cert chain errors |
| `headers` | 1 × HTTP GET | none | 1 req | Redirect chains, WAF blocks |
| `hibp` | `/api/v3/breaches` | **none** | polite | Absent → **clean receipt** (§5.4.2) |
| `ita` | `developer.trade.gov` | free key | posted | Name-match explosion |
| `gleif` | `api.gleif.org` (LEI) | **none** | polite | Name-based entity resolution is coarse |
| `nvd` | NVD REST | free key | posted | Vendor makes no software → clean receipt |
| `kev` | JSON feed | none | cache daily | No match → clean receipt |
| `regulatory` | FTC + cleared RSS feeds | none | polite | Feed unreachable; US-weighted window |
| `gdelt` | free API | none | — | **Held** — candidates only (ai_adjudicated) |
| `trust` | vendor pages | none | **robots.txt per vendor** | No trust page at all (common) |

> **EDGAR removed (v3.2).** SEC EDGAR required a compliant contact `User-Agent` (403 + IP ban otherwise) and covered only US-*listed* firms — it fed none of the five vendors reliably. Replaced by **GLEIF** (global LEI register, CC0, **no auth**), which resolves all five. The UA machinery is gone.
>
> **`asyncio.gather` still needs per-host rate limiting.** Firing all collectors concurrently is fine, but the politeness limits for `ct`, `nvd`, `gleif`, `gdelt` and the regulator feeds are per-host; a shared token-bucket per source keyed on hostname is the clean form (implemented in `ratelimit.py`). Phase 3 runs collectors via `asyncio.gather` with a per-source timeout.

**Collector contract — every collector returns the same envelope**, so the scoring engine never knows or cares where data came from:

```python
class CollectorResult(BaseModel):
    source: str
    vendor_ref: str
    status: Literal["ok", "empty", "error", "timeout", "skipped_tos"]
    fetched_at: datetime
    source_version: str | None      # e.g. KEV catalogVersion — needed for Finding B
    raw: dict | None                # → evidence store, verbatim
    findings: list[Finding]
    reliability: float              # from source_assessment.md, not invented here
    notes: str | None
```

**`status="empty"` is a first-class result, not an error.** It is the single most important line in this plan: `empty` must reduce **confidence**, never risk. A collector that raises on "nothing found" will silently break the honesty guarantee.

---

## 4. Legal Frameworks & Standards — what constrains the build

Full analysis: `legal_and_standards_basis.md`. **Engineering translation:**

| Rule | Where it lands in code |
|---|---|
| **Evidence store is a legal artefact** (Finding A) | Written **before** scoring; immutable; append-only; retained |
| **Score reconstructible from records** | Every `Finding` carries `source`, `fetched_at`, `locator` |
| **Confidence always emitted** | No API path returns a bare score — enforced at the schema |
| **Sanctions = gate, recall-tuned** (Finding B) | `BLOCKED` state; **no score**; fuzzy match wide |
| **Clean screens retained too** | `status="empty"` on `ita` is persisted, not discarded |
| **Store facts, not expression** (*IceTV*, no TDM exception) | Normalise on ingest; **don't warehouse article text** |
| **Score entities, not persons** (APP 10 + tort + AI Act) | No natural-person records; sole trader → refuse |
| **PII minimisation at ingest** (APP 3 + "trades in PI" exception, `legal_basis` §4.2) | `trust`/`security.txt` collector **strips named-person emails, keeps role addresses** (`security@`, `abuse@`); regex at the collector, before the evidence store |
| **Adverse media = reported/alleged** (defamation) | Wording enforced in the **serializer**, not the UI |
| **AI never silently moves a score** | LLM output → `claim` / `candidate`, never a weight |
| **Attribution is a UI requirement** | NVD verbatim notice, HIBP link, GDELT citation — Phase 4 acceptance criteria |

**Mandatory, verbatim, prominent** — NVD: *"This product uses the NVD API but is not endorsed or certified by the NVD."*

---

## 5. Scoring Framework — build view

Design is `methodology.md` §5 and is not restated. **What the build must honour:**

1. **`0 = lowest risk, 100 = highest risk`.** Never inverted. Assert it in a test.
2. **All bands and weights live in `scoring.yaml`, not code.** The model must be arguable with a client in a room without a deploy. This is the single most important architectural decision in the project.
3. **Weights are a transparent, tunable default — not an inherited derivation** (§5.6). No authority publishes vendor-risk weights; the default's *structure* is NIST-anchored, its *ordering* benchmark-cross-checked (§5.6.2), its non-compensatory rules legally anchored, its *values* sensitivity-bounded (open item 13) and client-editable in the YAML without a redeploy. **Observability is NOT a weight input** — it lives on the confidence axis (§5.4). The YAML carries each weight's basis as comments, so the file itself is the defence.
4. **Renormalise over what's present.** Missing → excluded from mean + subtracted from coverage.
5. **Order is gate → mean → floor → confidence** (§5.1). Sanctions or ambiguous entity → `BLOCKED`, no number. Then the weighted mean. Then the knockout floor. Then confidence + refusal.
6. **Refusal is the Ghost *hardened* — conditional on low risk** (§5.4.1). `confidence < 0.4` → `Insufficient evidence` **only when risk is also low**. A high-risk vendor with thin coverage is **not** refused → `uncorroborated_signal` ("review, don't report"). A fired knockout floor also emits despite thin coverage (we're certain about *that*).
7. **The knockout floor auto-fires only on directly-observed-current criticals** (§5.5.2). In v1 that is an **expired production cert** (seen live). A **KEV name-match scores high + flags for review** but does not auto-floor — a coarse match can't establish "currently unpatched." Must name its cause or not fire; floors, never sets; attribution ≥ 0.7.
8. **Never ship an even intra-category split** (§5.6.1). Four signals at 25% is an unstated claim they carry equal risk.
9. **Multi-asset: weakest-link for criticals** (`scoring.yaml` `aggregation`). Non-critical findings mean across a vendor's assets; **any critical on any asset floors the whole vendor**. Designed in config; multi-domain *collection* wiring is Phase 3 (v1 scores one primary asset).

> **The block below is an abridged excerpt showing the file's *shape*** — weights in config, derivation in comments, gates, knockout, modifiers, quadrants. **The authoritative spec is the hierarchy in `methodology.md` §5.9 (`scoring.yaml` v3.3.0 — seven scored categories, five held).** The excerpt uses simpler illustrative categories only because they read in one screen; the real file has `category → subcategory → signal` and the §5.9 weights (Cyber Hygiene & Technical 31). Do not build from this excerpt — build from §5.9.

```yaml
# scoring.yaml — the deliverable, in a file a non-engineer can read
# ABRIDGED d1 EXCERPT — full v3.0.0 nine-category spec lives in methodology.md §5.9
version: 3.0.0
direction: "0=lowest risk, 100=highest risk"

# --- illustrative d1 categories (shape only; real weights per §5.9) ---
# NB weights are a transparent DEFAULT, not an inherited derivation (§5.6):
# structure=NIST, ordering=benchmark(§5.6.2), values=sensitivity-bounded, client-tunable.
# Observability is NOT here — it lives in `confidence`. The old "client 1.5×obs" comments
# are withdrawn: that framework was an arbitrary demo template.
categories:
  cyber_hygiene:
    weight: 32        # d1 illustration — v3.0.0 value is 24 (Cyber Hygiene & Technical)
    rationale: "Default; ordering cross-checked vs Bitsight/UpGuard (§5.6.2)."
  incident_history:
    weight: 29        # d1 illustration — see §5.9 for v3.0.0 subcategory split
  supplier_transparency:
    weight: 18        # d1 illustration
  supply_chain:
    weight: 13        # priority anchored to CPS 230 ¶48 (fourth-party is regulated)
  business_stability:
    weight: 8         # low: US-listed skew → poor recall drives CONFIDENCE, not this weight
  esg:
    weight: 0         # HELD — licence unresolved (AGD query outstanding)

gates:                        # emit NOTHING — applied before the mean
  sanctions:
    behaviour: block          # never a weight, never 100 — Autonomous Sanctions Act s16(7)
    tuning: recall            # THE ONLY PLACE recall beats precision
  entity_ambiguous:
    behaviour: block          # never silently score the wrong company
    below_confidence: 0.5

knockout:                     # non-compensatory floor — applied AFTER the mean
  floor: band.moderate_lower  # bind to the Moderate band's LOWER bound, not a magic 50.
                              # bands are a tunable default (open item 10); 50 was mid-Moderate — wrong.
  requires_attribution: 0.7   # an unattributed critical floors the WRONG company
  requires_named_cause: true  # a floor that can't state its cause must not fire
  critical_tier:              # the concepts — OBSERVED EXPLOITATION, not theoretical severity
    - kev_cve_unpatched
    - certificate_expired
    - breach_unremediated
  auto_floor: [certificate_expired]   # v1 auto-fires ONLY on directly-observed-current criticals
  requires_confirmation: [kev_cve_unpatched, breach_unremediated]  # coarse match ≠ "unpatched now";
                              # scores HIGH + review flag, escalates to floor only on confirmation
  # NOT critical: high CVSS without exploitation evidence; cert expiring in 20d

modifiers:                    # NIST SP 1326: age, frequency, severity, mitigation
  age:        { half_life_months: 36, floor: 0.15 }   # decay lives HERE, in risk —
  frequency:  { increment: 0.25, cap: 2.0 }           # not only in confidence
  mitigation: { evidenced_factor: 0.6 }

confidence:
  refuse_below: 0.4           # → "Insufficient evidence"
  quadrant_boundary: 0.7      # → "The Ghost" / "Uncorroborated signal" labels

signals:
  dmarc:
    absent:      100
    p_none:      70    # monitoring only — NO enforcement
    p_quarantine: 35
    p_reject:    0

intra_category_weights:
  cyber_hygiene:              # ordered by directness of risk + benchmark (§5.6.2); NOT observability
    dns:     35   # sharpest cheap signal; gradeable; direct BEC linkage
    tls:     30   # direct observation, protocol facts
    headers: 20   # a header is a mitigation, not a vulnerability
    ct:      15   # most reliable SOURCE, weakest RISK linkage — certs issued ≠ hosts live
  # incident_history / supplier_transparency / supply_chain / business_stability:
  #   UNRESOLVED — open item 9. Do not default to an even split.
```

---

## 6. Development Stages

**Stack:** React + Vite + JavaScript · TailwindCSS · shadcn/ui · FastAPI + Pydantic v2 · **SQLite (Postgres-ready)** · APScheduler · `httpx` async.  *(Built: Phases 0–2 in Python/SQLite; frontend is Phase 4.)*

**Why this stack, briefly.** FastAPI because Pydantic models *are* the evidence-store schema and the API contract simultaneously — one definition, no drift, which matters when the schema is a legal artefact. shadcn/ui because components are copied into the repo rather than imported, so there's no version wall between the PoC and the Wahid AI platform's design system. SQLite because the PoC's evidence store must be append-only and portable; the SQLAlchemy layer keeps Postgres one config line away.

---

### Phase 0 — Foundations *(the phase everyone skips)* · ✅ **BUILT**

**Goal:** the skeleton that makes Finding A true.

- [ ] Repo, `.env`, `ruff` + `mypy` strict, `pytest`, Vitest
- [ ] **Pydantic models: `Vendor`, `CollectorResult`, `Finding`, `Evidence`, `Score`**
- [ ] **Evidence store: append-only, immutable, `fetched_at` + `source_version` mandatory**
- [ ] `scoring.yaml` loader + schema validation
- [ ] **Compliant EDGAR `User-Agent` in config** *(or lose a day in Phase 1)*
- [ ] Structured logging; per-source rate limiter

**Exit:** an `Evidence` row can be written and read back byte-identical.

> **Build the evidence store before the first collector.** It is not scaffolding — it is the discharge of the reasonable-grounds representation. A collector written first will make assumptions the store then has to accommodate.

---

### Phase 1 — Collectors *(one module per source)* · ✅ **BUILT** (11/11, verified live on 5 vendors)

**Goal:** all 11 sources returning the `CollectorResult` envelope, failure-isolated.

- [ ] `dns` → **DMARC ladder first** — sharpest cheap signal, proves the chain end-to-end
- [ ] `tls` + `headers` (own client — the SSL Labs replacement)
- [ ] `ct` (polite; honest UA)
- [ ] `hibp` `/breaches`
- [ ] `kev` + `nvd` (scoped to vendor **products** only)
- [ ] `ita` (gate feed)
- [ ] `edgar` (UA + ~8 req/s throttle)
- [ ] `gdelt`
- [ ] `trust` (**robots.txt check per vendor first**; **strip named-person emails at ingest** — keep `security@`/`abuse@` only)
- [ ] **Find the two missing test vendors** — no-footprint + expired cert (empirically, from CT)
  - *Expired cert:* query crt.sh for certs that **expired in the last day or two**, pick a mid-sized B2B org → a real, verifiable expired cert to fire the knockout floor
  - *No footprint:* a small private AU service provider (regional logistics / accounting firm) with no `/security` page, no HIBP record, no news → fires the `confidence < 0.4` refusal and the Ghost quadrant

**Exit:** all 5 vendors return results; **`empty` and `timeout` paths tested**, not just happy path.

> **Order matters:** `dns` first because DMARC is gradeable on a real scale, so it proves collector → finding → score → evidence in one thin slice before breadth.

---

### Phase 2 — Normalizer + Scoring engine · ✅ **BUILT** (74 tests passing)

**Goal:** the deliverable, in code.

- [ ] Normalizer → `Finding`
- [ ] **SP 1326 modifiers** (age / frequency / mitigation)
- [ ] Signal → category (renormalised over **present**, intra-weights from config)
- [ ] **Confidence** = coverage × reliability × freshness
- [ ] **Gates: sanctions + ambiguous entity → `BLOCKED`, no score**
- [ ] **Knockout floor** — after the mean; requires attribution ≥ 0.7; **names its cause**
- [ ] **Quadrant labelling** (§5.4.1) — attached to every emitted score
- [ ] **Refusal branch: `confidence < 0.4` → `Insufficient evidence`**
- [ ] Explainability: every deduction → evidence ref
- [ ] **Weight sensitivity analysis** (addresses open item 13) — for each of the nine category weights, sweep ±5 points and record the overall-score movement across all 5 vendors. **Output a "noise band" table.** The defence for the asserted (non-CPS-230-derived) weights is empirical: *"the ordering is the claim; the exact value sits inside a ±N noise band and is tunable to client risk appetite."* If a small weight change swings a vendor across a risk band, that weight is **not** in the noise and must be derived properly, not asserted — the analysis tells you which ones

**Tests that must exist — these encode the methodology:**

```
test_missing_data_lowers_confidence_not_risk()   # THE honesty guarantee
test_myob_no_edgar_filing_does_not_reduce_risk() # the naive-failure case
test_sanctions_hit_emits_no_score()              # gate, not weight, not 100
test_ambiguous_entity_emits_no_score()           # never score the wrong company
test_low_confidence_refuses_to_score()           # Ghost hardened: LOW risk + thin coverage
test_high_risk_thin_coverage_is_uncorroborated_not_refused()  # the complement — NOT refused
test_direction_convention_never_inverted()       # 0=low, 100=high (+ inversion rejected)
test_every_scored_signal_has_evidence_ref()      # Finding A, mechanised
test_2013_breach_scores_below_2025_breach()      # SP 1326 decay — in RISK, not confidence

# knockout floor (auto-fires on directly-observed-current criticals only)
test_expired_cert_floors_score()                       # cert seen live → floor to Moderate
test_floor_does_not_lower_a_higher_score()             # floors, never sets
test_unattributed_critical_does_not_floor()            # attribution < 0.7 → would floor wrong co
# (KEV name-match deliberately does NOT auto-floor — it scores high + flags for review)

# quadrants
test_quadrant_logic_four_cells()                       # incl. Ghost = unassessed, not safe

# privacy minimisation
test_trust_keeps_role_emails_drops_named_people()      # role addrs kept, PII dropped
```

**Exit:** all 5 vendors scored; every test above green. **(Status: Phase 2 done — 93 tests green; all five vendors scored end-to-end on live data. After the v3.2 clean-receipt + sub-gap work and the v3.3 corroboration/retry levers, all five land in `evidenced_clean` (~0.73–0.77) when CT is reachable; the model still ghosts honestly when a sole source is genuinely down; Ghost / uncorroborated-signal / refusal / BLOCKED behaviours all confirmed live.)**

> `test_missing_data_lowers_confidence_not_risk` is the most important test in the project. `methodology.md` §3.1 names invisibility-scores-well as **the most likely way a naive implementation fails**. This test is the guard.

---

### Phase 3 — API (FastAPI) · ✅ **BUILT** (10 API tests; verified live)

```
POST /api/vendors/score        { name | domain }  → 202 + job_id          ✅
GET  /api/vendors/{ref}                           → record + score + confidence  ✅
GET  /api/vendors/{ref}/evidence[/{id}]           → the receipt (raw + hash)     ✅
GET  /api/vendors/{ref}/history                   → score movement over time     ✅
GET  /api/jobs/{job_id}[/stream]                  → status + SSE partial results ✅
POST /api/adjudications/{ref}                      → record a BLOCKED-gate decision (PoC stub) ✅
```

- [x] **Async collectors via `asyncio.gather`** (`pipeline.py`) — per-source timeout via the collector isolation wrapper; evidence written FIRST as each result lands
- [x] **SSE streaming** (`jobs.py` fan-out + `StreamingResponse`) — progress events (`collecting` → `collector_done` × N → `scoring` → `done`) stream as sources finish; race-free replay + live
- [x] Response schema makes a bare score **unrepresentable** — every response is the `Score` model (always carries `overall_confidence` + `quadrant`/`blocked`/`refused`)
- [x] Per-request store via a dependency (SQLite or Postgres per config); `check_same_thread=False` for the sync-dep/async-route boundary

**Exit:** ✅ `POST` a vendor → 202 + job → SSE progress → full record with retrievable, hash-stamped evidence receipts. Verified live against the five-vendor set (12 on-demand collectors run in parallel; `gleif`+`wikidata`+`regulatory` present, `edgar` gone). `gdelt` is **enrichment-only** (held/ai_adjudicated + rate-limited → 429), so it is excluded from the synchronous score and moved to Phase 5 scheduled enrichment (`run_pipeline(include_enrichment=True)`). Modules: `app/pipeline.py`, `app/jobs.py`, `app/api.py`; run with `uvicorn app.api:app`.

> **Note on 429/backoff:** the per-host `RateLimiter` (Phase 0) keeps us under source ceilings proactively; explicit `429`-retry/backoff per source is a hardening item (most cleared sources are unauthenticated feeds without a 429 contract). crt.sh's flakiness is handled by the retry + certspotter fallback in the `ct` collector.

---

### Phase 4 — UI (React + Vite) · 🚧 **CORE BUILT** (streaming scorecard, all designed states; wired to the live SSE API)

> **Status.** The single-screen streaming scorecard is built and verified against the live API (`frontend/`, Vite + React 19; `npm run build` + `npm run lint` clean). Vendor input → `POST /score` → **SSE progress** (each collector's chip flips as it lands) → full scorecard. Implemented: risk number with **confidence always adjacent**, **quadrant chip + plain-language subtitle** (The Ghost reads as *unassessed*), **knockout-cause banner**, category breakdown → expand → **evidence receipt** (hash-stamped, fetched on demand), **BLOCKED** and **Insufficient-evidence** as distinct designed states, **gap-disclosure** (held sources + DFAT), **NVD/HIBP/GDELT attribution**, **coverage-tracks-size** and **perimeter-not-posture** caveats, responsive down to 375px, light/dark via tokens. **Deferred:** swapping the hand-written CSS design-system for **Tailwind + shadcn/ui** (styling layer only — states/contract unchanged), fuller a11y pass, and screenshot capture at 375/1920. Run: `cd frontend && npm run dev` with the API on `:8000` (Vite proxies `/api`).

**Goal:** client-ready, not prototype. The brief's craft section is the acceptance criteria.

**One screen. One input. `[Score vendor]`** — not `[Submit]`.

- [ ] Vendor input → streaming scorecard (no wizard, no source-picker)
- [ ] Overall + **confidence always adjacent** — never a lone number
- [ ] **Quadrant label beside the score** — `Evidenced clean` / **`The Ghost`** / `Verified exposure` / `Uncorroborated signal`
- [ ] **`The Ghost` reads as *unassessed*, not *safe*** — the whole point; if a user mistakes it for low risk, the design has failed
- [ ] **Knockout floor states its cause** on the scorecard, in the client's words
- [ ] Category breakdown → expand → findings → **evidence receipt**
- [ ] **`BLOCKED` state** — distinct, unmissable, not a red score
- [ ] **`Insufficient evidence`** — a real, designed state
- [ ] Empty / error / timeout / **partial-source-failure** states
- [ ] **Attribution: NVD verbatim notice, HIBP link, GDELT citation**
- [ ] **Coverage-tracks-size caveat, in plain language, on the scorecard**
- [ ] **Gap-disclosure component** — a held/excluded source states itself on the scorecard, not silently absent: *"Australian sanctions (DFAT) not screened — licence unresolved; US ITA list screened."* This is Finding A applied to coverage: claiming completeness we don't have is the misrepresentation. Every `held`/`gate-partial` category renders its gap
- [ ] **Perimeter-not-posture disclaimer** — *"Reflects publicly observable perimeter posture; does not account for unobservable internal compensating controls."* (Partial cover for the no-dispute-path bias, open item 12 — a disclaimer mitigates, the roadmap attestation flow is the real fix)
- [ ] Responsive; resize; **a very long vendor name must not break layout** (e.g. a 60+ char legal name) — UI robustness input, not a real assessment target
- [ ] a11y: contrast, keyboard, labels, `aria-live` for streaming
- [ ] Light/dark consistent

**Exit:** every state screenshots cleanly at 375px and 1920px.

> **The empty states are the deliverable here.** The brief calls out *"especially a source returning nothing, or timing out"* — and for this product a source returning nothing is not an edge case, it's the **normal condition** for most vendors. Design it first, not last.

---

### Phase 5 — Automation & agentic monitoring

**Goal:** the system acts without being asked. **Authority: NIST CSF 2.0 GV.SC** names ongoing monitoring as a C-SCRM outcome — this is justified, not a flourish.

- [ ] **APScheduler**: nightly KEV/ITA refresh, weekly per-vendor re-score
- [ ] **Delta detection** → score movement + **which finding moved it**
- [ ] **Flag on movement** past threshold — the brief's own example
- [ ] Re-score writes **new** evidence; never mutates old *(Finding B: evidence as it stood at the time)*
- [ ] **AI moment 1:** GDELT adverse-media summarisation → ranked candidates + evidence links
- [ ] **AI moment 2:** trust-page → structured certifications + expiry
- [ ] Both AI outputs: **`claim`/`candidate` only — never a weight**

**Exit:** a vendor's score moves on its own and the flag names the cause.

> **What automation must not do.** "Things are going to be automated" is the instruction, and everything above is automated. But the sanctions gate stays human — **not because automation is hard, because s 16(7) makes the adjudication itself the evidence.** Automating it would destroy the artefact the product exists to produce. Automate collection, scoring, re-checking, summarising, flagging. **Adjudicate hits.** That's one human step in the entire pipeline, at the one place where the law puts it.

---

### Phase 6 — Hardening, sample output, handover

- [ ] Sample scorecard for Deliverable 4 (public-record vendor)
- [ ] `scoring.yaml` fully commented with derivations
- [ ] README: run it in one command
- [ ] Methodology ↔ code cross-refs (`§5.6` → `scoring.yaml`)
- [ ] Roadmap finalised

---

## 7. System Flow

Full diagram: `methodology.md` §6. **Runtime view:**

```
React (Vite + JS + Tailwind + shadcn)
    │  POST /api/vendors/score      { "name": "Canva" }
    ▼
FastAPI ──► entity resolution ──► asyncio.gather(collectors)
    │                                   │ per-source timeout, isolated failure
    │         ┌─────────────────────────┘
    │         ▼
    │   ★ EVIDENCE STORE (append-only)      ← written BEFORE scoring
    │         │
    │         ▼
    │   normalize → scoring engine (scoring.yaml)
    │         │
    │         ├── gate: sanctions? ──► BLOCKED (no score) ──► adjudication queue
    │         └── confidence < 0.4? ──► "Insufficient evidence"
    │         ▼
    └──► SSE stream ──► scorecard renders progressively
                             │
                    APScheduler ⟳ weekly re-score ──► delta ──► flag
```

**One input, one screen, partial results streaming.** The user's goal is a defensible view of a vendor; every extra click is friction against it.

---

## 8. Limitations of *this plan*

Product limitations are in `methodology.md` §7. **Delivery risks:**

| Risk | Impact | Mitigation |
|---|---|---|
| **DFAT/AGD replies never arrive** | Gate is US-only; ESG stays 0 | **Send P0, week 1.** Ship with gap documented on the scorecard |
| **Entity resolution eats the timeline** | The accuracy ceiling | **Timebox.** Manual domain confirmation for 5 vendors is acceptable in a PoC — say so |
| **GDELT noise swamps adverse media** | Category degrades | AI adjudication; if it fails, **drop to candidates-only and say so** |
| **crt.sh objects to our traffic** | Source lost | Polite limits; CT logs directly as fallback |
| **Scope creep into platform features** | PoC never lands | Out-of-scope table (§2) is a contract |
| **UI polish deferred to the end** | Reads as prototype — the one thing the brief forbids | Craft criteria are **phase exits**, not a final pass |

**The honest one:** Phase 5's AI work is the most likely thing to be cut under time pressure. If it is, **cut it cleanly and document why** — an undelivered AI feature is fine; a half-wired LLM silently moving scores is a Finding A liability.

---

## 9. Deliverables

| # | Deliverable | Artefact | Phase |
|---|---|---|---|
| **1** | Research methodology | `source_assessment.md`, `methodology.md`, `legal_and_standards_basis.md` | **Draft done** |
| **2** | Working PoC | React + FastAPI, 5 real vendors | 0–4 |
| **3** | v1 scoring model | `methodology.md` §5 + **`scoring.yaml`** | Design done → 2 |
| **4** | Sample output | Client-ready scorecard | 6 |
| **5** | Roadmap | §10 | 6 |

**Ship order if time runs short:** 3 → 1 → 2 → 4 → 5. The brief is unambiguous — *"The code matters less than the method."* A documented model with a thin PoC beats a rich PoC with an undefended model.

---

## 10. Roadmap

| Priority | Item | Why | Blocked on |
|---|---|---|---|
| **1** | **FOCI / Provenance** | **SOCI Enhanced CIRMP Rules 2026 make it mandatory for critical infrastructure — ~mid-2028 deadline.** Named buyer, regulatory clock | Registry terms |
| **2** | **Fourth-party concentration graph** | **CPS 230 ¶48 = regulated obligation.** DORA dry run: **only 6.5% of ~1,000 firms passed**, mostly failing on missing subcontractor data | Nothing — build it |
| **3** | AU sanctions (DFAT) | The list an AU client's **s 16(7) defence** turns on | ASO reply |
| **4** | ESG / Modern Slavery | Statutory, free, locally relevant, **nobody else will think of it** | AGD reply |
| **5** | Registries (ASIC) | Fixes Business Stability's recall | Terms |
| **1a** | **Active-exposure / reputation source** (open RDP/SMB, live phishing blocklists) | Real blind spot — CT shows certs *issued*, not ports *open*. **Deliberate v1 constraint**, now top roadmap item. Must clear a source **lawfully first** | See veto below |
| **6** | **Vendor attestation / dispute path** — **DESIGNED** (`scoring.yaml` `dispute`) | Outside-in **cannot see compensating controls**, so it over-penalises well-run vendors with a thin footprint. A vendor submits a redacted SOC 2 / patch log / attribution correction → human adjudication → `mitigation: evidenced_factor 0.6` (SP 1326), logged immutably. **Open item 12; Finding A** | Nothing — build the workflow |
| **7** | Shodan / Censys | Estate visibility | **Paid, and free tiers bar commercial use** — out of scope per brief |
| **8** | Contradiction engine | **Where OSINT disagrees with the questionnaire** — the real platform play | Platform integration |

> **⚠ Legality veto (recorded, methodology §5.10).** The obvious ways to close the active-exposure gap were reviewed and **rejected as written**: Shodan/Censys **free** tiers bar commercial use (Censys ToS verified live — the VirusTotal trap for a commercial-platform candidate), and the proposed OTI feeds (URLScan, OpenPhish, AlienVault OTX, AbuseIPDB, GreyNoise) carry **unverified** commercial-use terms. They are logged as **candidates requiring `source_assessment.md` ToS verification** (open item 7), **not cleared**. The gap is real; the shortcut is not lawful.

### How this productises

The PoC is already shaped for the Wahid AI third-party module:

- **Weights are a transparent, client-tunable default** (`methodology.md` §5.6) — NIST-anchored structure, benchmark-checked ordering, sensitivity-bounded values. The platform inherits the *derivation method and the editable config*, not a fixed number set, which is exactly what the AFA's "own your rating system" position requires.
- **`scoring.yaml` is the IP**, portable and readable by a non-engineer.
- **The evidence store is the audit trail** the platform needs anyway.
- **Item 7 is the destination.** OSINT never replaces the questionnaire — ~10 of 27 criteria are permanently invisible. But it **independently evidences a subset and flags contradictions** where a vendor's self-assessment disagrees with the public record. **That contradiction is the thing no questionnaire platform can produce about itself** — and it is worth more than the score.

---

## References

- `docs/methodology.md` — **the model; this plan defers to it**
- `docs/source_assessment.md` · `docs/legal_and_standards_basis.md`
- `docs/an_example_risk_scoring_System.md` — ⚠ demo placeholder, **not authoritative**; not a source of weights (§5.6)
- `docs/OSINT_TPRM_Intern_Brief.md` — the brief
