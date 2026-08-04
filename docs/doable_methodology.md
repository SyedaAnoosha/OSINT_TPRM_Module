# Doable Methodology — what can actually be built, with no budget

**Status:** work plan · v1 · against scoring model **v4.2.0** · 14 collectors, 26 signals, 7 scored categories
**Date:** 24 July 2026
**Companions:** [`perfect_methodology.md`](perfect_methodology.md) (the target state) · [`methodology.md`](methodology.md) (the shipped model) · [`roadmap.md`](roadmap.md) · [`review_response.md`](review_response.md)

---

> **The question this answers.** *"What can I actually do?"*
>
> **The answer in one line.** Of the eleven lifecycle stages in
> [`perfect_methodology.md`](perfect_methodology.md), **five run at or near full strength today**, **four
> more reach it in ~90 days on free sources and free keys**, and **two are limited by money or by not yet
> having a portfolio**. Nothing on the build list below is blocked on budget.
>
> **The claim worth defending.** The doable methodology is not a cut-down version of the perfect one. It
> is **the same model** — the same 100-minus-penalties arithmetic, the same gates, the same two axes —
> running on less evidence, and **saying so honestly on every card**. That is why the upgrade path is
> additive rather than a rewrite.

---

## Contents

| Part | What it covers |
|---|---|
| **I** | What runs today — verified against the code, not claimed |
| **II** | The eleven lifecycle stages on a free tier — coverage and honest limits |
| **III** | **The build backlog** — twelve items, sequenced, with acceptance tests |
| **IV** | The free source register — built · cleared · candidates · ask-first |
| **V** | Free substitutes for paid capabilities — what works, what half-works, what doesn't |
| **VI** | What stays impossible for free — and how to say it |
| **VII** | The 90-day plan |

---

# Part I — What runs today

Verified against the repository, not asserted.

| Piece | Where | State |
|---|---|---|
| **14 collectors** | `backend/app/collectors/` | `dns` `tls` `headers` `ct` `hibp` `kev` `nvd` `ita` `gleif` `wikidata` `rdap` `regulatory` `gdelt` `trust` |
| **Failure isolation** | `collectors/base.py` | Timeout → `timeout`, raise → `error`, nothing-found → `empty`. **A collector cannot sink an assessment** |
| **Immutable evidence store** | `evidence_store.py`, `pg_store.py` | Append-only (DB triggers reject UPDATE/DELETE), sha256 over canonical JSON, byte-identical read-back verified by test |
| **Penalty scoring engine** | `scoring/engine.py`, `normalize.py`, `modifiers.py` | 100 − penalties · four NIST modifiers · gates · critical ceiling |
| **The model as config** | [`scoring.yaml`](../scoring.yaml) v4.2.0 | 7 categories · 54 penalising bands · every one carrying a plain-English reason, **loader-enforced** |
| **Config drift guard** | `scoring_config.py` | Every key must declare itself engine-read or documentation-only, or the app refuses to start |
| **Frozen regression corpus** | `backend/tests/fixtures/` | 5 real vendors, pinned clock, asserted per-category penalties |
| **API + SSE** | `api.py` | `POST /api/vendors/score` · job stream · score · **history** · evidence · findings · **adjudication** |
| **Streaming scorecard** | `frontend/src/Scorecard.jsx` | Two axes, quadrant, category breakdown → receipts, BLOCKED and Insufficient-evidence states |
| **Read-layer AI summary** | `summariser.py` | Off by default, provider-agnostic, never scores, cites hashes |

**Two things already there that the build plan can lean on, and which are easy to overlook:**

- **`GET /api/vendors/{ref}/history`** already returns every stored `Score` for a vendor. **Trend is a
  rendering job, not a data problem** — the scheduler makes it automatic, but the history exists now.
- **`POST /api/adjudications/{ref}`** already accepts and validates a human decision on a blocked gate.
  The **dispute path (open item 12) has a working precedent to generalise**, not a blank page.

---

# Part II — The eleven lifecycle stages, on a free tier

How much of [`perfect_methodology.md`](perfect_methodology.md) the free stack actually delivers.

| Stage | Free coverage | What you get without money | The honest limit |
|---|---|---|---|
| **1. Entity Resolution** | ◐ **50%** | Two-pass resolution (pre-collection + re-derived from the registries), the `< 0.5` block, GLEIF/Wikidata/RDAP standing | **No firmographics** — no industry, size, revenue, ownership or criticality. This is the gap that blocks Stage 8 |
| **2. Evidence Collection** | ◕ **65%** | 14 collectors across six of the eight evidence buckets; uniform envelope; failure isolation; `empty` first-class | **Attack surface and credential buckets are empty.** No open ports, no service versions, no credential recapture |
| **3. Evidence Validation** | ● **95%** | Hash-stamped, append-only, byte-identical read-back, `source_version` retained | **No `licence` / `retention_until` / `redistributable` fields** — free-tier sources don't need them; the moment a paid feed arrives, they do |
| **4. Evidence Enrichment** | ◐ **45%** | Entity re-resolution, cross-source corroboration (noisy-OR), freshness, CVE enrichment via EPSS | **No version matching, no asset attribution, no dependency-graph assembly, no historical context.** Most commercial value lands here |
| **5. Finding Generation** | ● **95%** | 54 penalising bands, severity mapping, loader-enforced plain-English reasons | **No `action`, `ask_of_vendor`, `recheck_after` or `accepts_as_refute`** — pure config work |
| **6. Confidence Analysis** | ● **95%** | Coverage, corroboration, source reliability, clean-receipt discounting, refusal below 0.40, the quadrant | Freshness weighting is coarse |
| **7. Penalty Scoring** | ● **100%** | The full model — penalties, all four NIST modifiers, both gates, the critical ceiling | **Mitigation modifier is dormant** — no free source evidences a fix |
| **8. Benchmarking** | ○ **0%** | — | **Needs Stage 1 firmographics** (buildable) **+ a portfolio** (not) |
| **9. Decision Engine** | ◔ **30%** | Grade, confidence, quadrant, plain-English reasons | **No recommendation, no action, no re-check date.** The dispute loop is unbuilt — open item 12 |
| **10. Monitoring** | ◔ **20%** | Score history stored; collectors idempotent and failure-isolated | **No scheduler**, no drift alerts |
| **11. AI Read Layer** | ◕ **60%** | Read-layer summariser — fenced, opt-in, cites hashes, never scores | Adverse-media adjudication and trust-page classification not wired |
| **Presentation** | ◔ **25%** | One well-built analyst view | No procurement, executive or auditor projection; no evidence-pack export |

**Read the pattern.** The weakest rows are **not** the ones that need money. Stages 8–10 and Presentation
score 0–30% and are blocked on **build effort**. Only **Stage 2's two empty buckets** (attack surface,
credential) and the enrichment they would feed at **Stage 4** genuinely need a cheque — and the
lifecycle structure is what makes that visible: budget touches two stages, not fourteen domains.

---

# Part III — The build backlog

Twelve items. Ordered by **value per day of work**. Every one is free, lawful, and needs no new source
clearance unless stated. Effort is indicative: **S** ≈ 1–2 days, **M** ≈ 3–5 days, **L** ≈ 1–2 weeks.

---

### 1 · Action layer on every penalising band — **S**

**Answers:** review point 9 · Stages 5 + 9
**Why first:** the highest value per hour in the entire project. The system already explains; it does
not yet advise.

Add three keys beside every existing `reasons` entry in [`scoring.yaml`](../scoring.yaml):

```yaml
actions:
  dmarc:
    absent:
      action:       "Ask the vendor to publish a DMARC record, starting at p=none and moving to p=reject"
      ask_of_vendor: "Do you publish a DMARC policy for your sending domains? If not, what is the timeline?"
      recheck_after: 30d
      accepts_as_refute: "A published DMARC record at p=quarantine or p=reject"
  cert_validity:
    expired_serving_prod:
      action:       "Request the replacement certificate, or evidence the host is decommissioned"
      ask_of_vendor: "The certificate on <host> expired on <date>. Is this host still in production?"
      recheck_after: 7d
      accepts_as_refute: "A valid certificate observed on the host, or written confirmation of decommissioning"
```

**Files:** `scoring.yaml` · `scoring_config.py` (extend the loader invariant — every penalising band must
now carry a reason **and** an action) · `api.py` (serve alongside `reason`) · `Scorecard.jsx`.
**Acceptance:** the app **refuses to start** if a penalising band has no action. Every finding on the
card shows what to do and when to look again.

---

### 2 · Recommendation rule table — **S**

**Answers:** review points 8, 9 · Stage 9

A deterministic table over `grade × confidence_band × criticality`, computed at serve time from
published fields. **Never LLM-generated** — that fence does not move.

**Files:** new `app/scoring/recommend.py` · `models.py` (`Score.recommendation`) · `api.py` ·
`ScoreRequest.criticality` · `Scorecard.jsx`.
**Acceptance:** every non-blocked score carries a recommendation; blocked scores carry none, ever;
identical inputs give identical output (unit-tested against the frozen corpus).

**The one new input:** `criticality: low | medium | high` on the score request — **client-supplied,
never inferred.** How much a vendor matters to a buyer is not observable from outside.

---

### 3 · `firmographics` collector + `VendorProfile` — **M**

**Answers:** review points 2, 3, 5 · Stage 1
**Why it punches above its weight:** it unblocks three separate review points with one build.

All from **already-cleared, CC0, no-key** sources:

| Field | Wikidata property |
|---|---|
| Industry | P452 |
| Employees | P1128 |
| Revenue | P2139 *(listed companies mostly)* |
| Stock exchange → public/private | P414 |
| Country | P17 |
| Inception → company age | P571 |
| Parent organisation | P749 *(entity-level only)* |

Plus jurisdiction and entity category from **GLEIF**, already collected.

**Files:** new `collectors/firmographics_collector.py` (the Wikidata client and domain-verification
logic already exist in `wikidata_collector.py` — reuse the P856 match so the profile is anchored to the
same verified entity) · `models.py` (`VendorProfile`) · `collectors/__init__.py` (register) ·
`Scorecard.jsx` (render above the score).

**Acceptance:** all five corpus vendors get a profile; **no profile field ever changes a penalty** —
asserted by a regression test that scores with and without the profile and requires identical output.

---

### 4 · Fourth-party enumeration — **M**

**Answers:** review point 7 · Stages 2 + 4
**Why:** [`roadmap.md`](roadmap.md) §2.2 calls it *"the sharpest commercial wedge"* and it is
**blocked on nothing** — it re-feeds collectors already running.

A provider-fingerprint dictionary over existing output:

```python
# app/fourth_party.py — a dictionary, not a new source
PROVIDERS = {
    "amazonses.com":     ("AWS SES",        "email"),
    "outlook.com":       ("Microsoft 365",  "email"),
    "sendgrid.net":      ("SendGrid",       "email"),
    "okta.com":          ("Okta",           "identity"),
    "cloudflare.net":    ("Cloudflare",     "cdn_dns"),
    "awsdns":            ("AWS Route 53",   "dns"),
    "zendesk.com":       ("Zendesk",        "support"),
    "statuspage.io":     ("Atlassian Statuspage", "status"),
    # …extend from MX, SPF include:, NS, CNAME, CT SANs
}
```

**Files:** new `app/fourth_party.py` · normaliser hook · a *Dependencies* panel in `Scorecard.jsx`.
**Acceptance:** all five corpus vendors return a dependency list. **Disclosed, never scored** — a
regression test asserts the posture is byte-identical with the panel on and off.

> **The rule that keeps it fair.** A fourth party's issues are **concentration context**, not a vendor
> penalty. Penalising every AWS customer for an AWS CVE punishes thousands of vendors for a dependency
> they share with their competitors. The finding that matters — *"six of your fourteen vendors share one
> identity provider"* — is a **portfolio** statement, and that half needs the platform.

---

### 5 · Executive summary block + role-based default view — **S**

**Answers:** review point 8 · Presentation

One toggle setting section order and expansion depth on the existing card. **Same record, same number,
different first screen.** The analyst can always reach the receipt behind the executive's figure.

**Files:** `Scorecard.jsx` · `Layout.jsx` · `lib/` (persist the preference).
**Acceptance:** four views render from one API response; **no view calls a different endpoint** — the
guarantee that no projection can drift from another.

---

### 6 · Evidence pack export — **S**

**Answers:** review point 6 · Presentation (the auditor projection)

Procurement needs something to put in the file. The data exists; this is rendering.

**Contents:** vendor profile · score + confidence + quadrant · every finding with its reason, action and
receipt hash · source list with `fetched_at` · the disclosure block (held sources, DFAT not screened,
attribution notices) · model version.

**Files:** new `api.py` route `GET /api/vendors/{ref}/export` · a print stylesheet.
**Acceptance:** the export reconstructs the published score from its own contents. If it cannot, it is
not an evidence pack.

---

### 7 · Industry severity profiles — **S**

**Answers:** review point 5 · Stage 8

**Two profiles only** — the two with unambiguous Australian statutory anchors. Promotion-only, capped at
one severity step, each citing a named instrument, declared on the card, client-switchable.

```yaml
industry_profiles:
  financial_services:
    basis: "APRA CPS 234 · CPS 230"
    promote:
      dmarc.absent: high -> critical
      cert_posture.none_claimed: medium -> high
  healthcare:
    basis: "Privacy Act APP 11 · My Health Records Act · OAIC NDB: health = 19% of CY2025 notifications"
    promote:
      breach_by_data_class.personal_info: high -> critical
      dmarc.absent: high -> critical
```

**Files:** `scoring.yaml` · `scoring/normalize.py` · `Scorecard.jsx` (the declaration).
**Acceptance:** re-goldening the corpus under a profile produces a **reviewable diff naming the vendor
and category that moved**. A profile without a `basis:` fails the loader.

> **Not weights.** [`methodology.md`](methodology.md) §5.6 deleted category weights because no authority
> publishes them. This is a **severity promotion with a cited instrument behind each line** — one lever,
> itemised, contestable per line, and it does not resurrect what §5.6 buried.

---

### 8 · ABN Lookup collector — **M** · *needs a free GUID*

**Answers:** review points 2, 3, 4 · Stages 1, 2

**CLEAR-CONDITIONAL** in [`source_assessment.md`](source_assessment.md): third-party extracts permitted,
no commercial bar, free registration GUID, must not imply Commonwealth endorsement.

Gives **authoritative AU entity status** (Active / Cancelled / Deregistered) — *"the source that actually
solves the MYOB test"* — **and ANZSIC industry codes**, which feed items 3 and 7.

**Entity status only. Never director or officer personal data** — the §4.2 bright line holds.

**Files:** new `collectors/abn_collector.py` · `config.py` (`TPRM_ABN_GUID`) · register.
**Acceptance:** MYOB resolves to an authoritative AU status corroborating GLEIF; confidence rises via
the existing noisy-OR path with no engine change.

---

### 9 · Companies House collector + registry adapter — **M** · *needs a free key*

**Answers:** review point 4 · Stages 1, 2

**CLEARED** — OGL, commercial use permitted, free key, 600 requests / 5 min. Adds UK entity standing,
**free filed accounts** (real financial data for UK companies), and the **PSC register** for
entity-level ownership — the FOCI chain SOCI will require from ~mid-2028.

Build it behind a **`RegistryAdapter` interface** so ASIC, NZ Companies Office and ACRA slot in later
without touching the engine. GLEIF stays the global fallback.

**Files:** new `collectors/registry/` package · `base.py` interface · `companies_house.py` ·
`abn.py` (item 8, refactored in).
**Acceptance:** jurisdiction from `VendorProfile` selects the adapter; unknown jurisdiction falls back to
GLEIF and **says so on the card**.

---

### 10 · CT redundancy — AlienVault OTX passive DNS — **S** · *needs a free key*

**Answers:** a live single point of failure · Stage 2

Digital Footprint depends **entirely** on Certificate Transparency. crt.sh is famously flaky; a brief
outage zeroes the category and tips a genuinely clean vendor to *The Ghost*. Slack is the documented
archetype of this fragility.

**Files:** new `collectors/otx_collector.py` · merge into the CT subdomain set.
**Acceptance:** with `ct` forced to `error`, Digital Footprint still returns a posture. **This is a
resilience fix, not a feature** — it removes the most likely cause of a wrong published result.

---

### 11 · Dispute / refute path — **M**

**Answers:** open item 12 — a **live Finding A exposure** · Stage 9 (the dispute loop)

Publishing a score with no contest mechanism, while knowing the method systematically over-penalises
(it cannot see compensating controls), is the gap both benchmarked commercial platforms close and we do
not.

**Generalise the existing adjudication endpoint.** `POST /api/adjudications/{ref}` already validates a
human decision and retains the reasoning. Extend it from *gates only* to *any finding*: a vendor submits
evidence → a human adjudicates → an accepted refute applies the `mitigation` modifier (×0.6) or nullifies
the finding → **the dispute, the evidence and the resolution are logged immutably** and a **new** Score
is written. Nothing is ever edited.

**Files:** `api.py` · `evidence_store.py` (a `Dispute` record) · a reviewer queue view.
**Acceptance:** a disputed finding produces a *new* immutable score with the dispute in its chain — the
original stays readable. Item 1's `accepts_as_refute` tells the vendor exactly what to send.

---

### 12 · Scheduled re-score + drift alerts — **L**

**Answers:** review points 8, 9 · Stage 10 (the monitoring loop)

Collectors are already idempotent and failure-isolated, and `GET /api/vendors/{ref}/history` already
returns every stored score. **The scheduler is the only missing piece.**

Because every run is hash-stamped, a posture move raises a flag **with before/after receipts attached** —
drift is *provable*, not asserted.

**Files:** new `app/scheduler.py` · `api.py` (subscriptions) · a trend chart on the card.
**Acceptance:** a vendor re-scored twice with a changed cert produces a drift event naming the signal,
the direction, and both receipt hashes.

---

## Backlog summary

| # | Item | Effort | Blocked on | Review point | Status |
|---|---|---|---|---|---|
| 1 | Action layer on all 54 bands | S | — | 9 | |
| 2 | Recommendation rule table | S | — | 8, 9 | |
| 3 | `firmographics` + `VendorProfile` | M | — | 2, 3, 5 | **DONE** |
| 4 | Fourth-party enumeration | M | — | 7 | |
| 5 | Executive block + role views | S | — | 8 | |
| 6 | Evidence pack export | S | — | 6, 8 | |
| 7 | Industry severity profiles | S | — | 5 | |
| 8 | ABN Lookup | M | free GUID | 2, 3, 4 | **DONE** (skips without a GUID) |
| 9 | Companies House + adapter | M | free key | 4 | |
| 10 | OTX (CT redundancy) | S | free key | — | |
| 11 | Dispute path | M | — | 9 | |
| 12 | Scheduler + drift | L | — | 8, 9 | |
| 13 | **Peer benchmarking** — cohort key, minimum-peers gate, cohort-bounded comparison, seeder | M | — | 3, 5 | **DONE** |

**Seven of thirteen are blocked on nothing at all.** Three need a free registration. None needs money.

### What landed with items 3, 8 and 13

- **`benchmarks.yaml`** — cohort key (sector × size × region), size bands, `min_cohort_n` (default 8).
  **No arithmetic**: the scoring model is untouched and the frozen corpus still passes.
- **A loader-enforced citation rule** — an `expected_posture` without a `basis:` fails at load, the
  same discipline `scoring.yaml` applies to `reasons`. Shipped empty, deliberately.
- **Cohort-bounded comparison** — `POST /api/compare` returns **409** across cohorts, naming both.
- **Two client-supplied inputs** — `criticality` and `size_band`, both recorded as client-supplied
  and neither scored. `size_band` exists because of a *measured* gap: public sources publish an
  industry for most vendors but a headcount for far fewer, and a sector with no size has no cohort.
- **A guard test** — every corpus vendor scored with and without firmographics must produce an
  identical Score. The profile is context; it cannot reach the engine.
- **One honest limitation recorded** — ANZSIC is non-public ABR data (government agencies only), so
  AU sector classification falls back to the Wikidata label mapping.

---

# Part IV — The free source register

## Tier 0 — built and running

`ct` · `dns` · `tls` · `headers` · `hibp` · `kev` · `nvd` · `ita` · `gleif` · `wikidata` · `rdap` ·
`regulatory` · `gdelt` · `trust`

## Tier 1 — cleared, free, needs a key or a licence reply

| Source | Status | Unlocks |
|---|---|---|
| **Companies House (UK)** | **CLEARED** — OGL, commercial-OK, free key | UK standing · **free filed accounts** · PSC ownership → FOCI |
| **ABN Lookup (AU)** | **CLEAR-CONDITIONAL** — free GUID | AU standing · **ANZSIC industry** |
| **AlienVault OTX** | Cleared pending free key | CT redundancy |
| **Cert Spotter token** | Free key | Higher CT rate limit in production |
| **NVD API key** | Free | Higher NVD rate limit |
| **DFAT Consolidated List** | **HELD — licence query pending** | **Australian sanctions in the gate** |
| **AU Modern Slavery Register** | **HELD — licence query pending** | The ESG category |

> **The two held items are the most locally embarrassing gaps in the product, and both are blocked on a
> letter, not a cheque.** An Australian TPRM tool whose sanctions gate runs on a US list only is a
> defensible v1 position exactly once. Chase them.

## Tier 1b — candidates worth a clearance pass

Located, not cleared. Each must pass the project's own bar — *free · commercial + automated use
permitted · no ToS trap · reachable and parseable* — before a single record is ingested.

| Source | Would add | First look |
|---|---|---|
| **ACNC Charity Register** (data.gov.au) | ~60k AU not-for-profit entities: status, size band, ABN — weekly CSV | Likely CC BY. **Strong candidate** |
| **OAIC Notifiable Data Breaches** | **Sector-level breach base rates** — the empirical basis for expected-posture bands (item 7) | Publications, no entity names — a *benchmark* input, never a vendor score |
| **auDA / `.au` WHOIS** | `.au` requires a **validated Australian presence** — so a `.au` domain is itself an entity-existence signal | Public, rate-limited. Genuinely novel |
| **IP/ASN RDAP (via the RIRs)** | Netblock and ASN ownership — **partial attack-surface attribution without scanning**. Uses the protocol `rdap_collector.py` already speaks | Registry data, same posture as domain RDAP. **Best free step toward Stage 2** |
| **Wayback Machine / CDX API** | Historical trust pages and policy changes — *when* did `security.txt` appear, *when* did the certification claim change | Free API |
| **AusTender** | AU Government contract awards — a read on public-sector trust | Free |
| **ASX announcements** | Continuous-disclosure events for listed AU vendors | Free per company |

## Tier 1c — ask-first (verified restrictive, 24 Jul 2026)

Two sources that look free and are not, for our use case. **Recorded here so nobody re-discovers them
and assumes.**

| Source | What it would give | Why it is ask-first |
|---|---|---|
| **[ransomware.live](https://www.ransomware.live/about)** | Ransomware leak-site victim postings — the closest free thing to KELA's *"this vendor is being extorted"* signal, and one of the highest-value single facts in TPRM | The public API is **free for personal use and "not intended for corporate or business use"**; commercial use is governed by separate terms. → **written query before any ingestion**, exactly the DFAT pattern |
| **[RIPEstat](https://www.ripe.net/about-us/legal/ripestat-service-terms-and-conditions/)** | ASN/netblock data — attack-surface attribution without scanning | Free for **non-commercial** use; *"packaging it as a commercial product is not allowed unless permission is granted in writing by the RIPE NCC"* → **written query**, or use **RIR RDAP** instead |

**The RIPEstat finding has a clean workaround:** IP and ASN lookups over **RDAP** hit the RIRs' own
bootstrap-published registry service — the same protocol and the same open-registry posture as the
domain RDAP collector already in production. **Prefer the adapter you already own.**

## Permanently excluded

**VirusTotal** and **SSL Labs** — ToS prohibit our use case. Not a coverage decision; a legality one.
They do not come back at any budget.

---

# Part V — Free substitutes for paid capabilities

The honest accounting. **Green means the free path is genuinely adequate. Red means say so and move on.**

| Paid capability | Free substitute | Verdict |
|---|---|---|
| **Fourth-party graph** (Interos, Panorays) | MX/SPF/NS/CNAME + CT SANs + published subprocessor lists | 🟢 **Adequate for tier 2.** The vendor's own published DPA is the *authoritative* list — a paid graph is inferring what the vendor already tells you |
| **Certification verification** (GRC platforms) | Trust-page parsing + `security.txt` | 🟡 **Half.** You get the *claim*, labelled `claimed_unverified`. Promotion to `registry_corroborated` needs a register |
| **UK financials** (D&B) | **Companies House filed accounts — free** | 🟢 **Genuinely adequate for UK entities.** A rare free win |
| **AU/US financials** (D&B, Moody's) | EDGAR (US-listed) · ASX (AU-listed) · nothing for private | 🔴 **No substitute for private companies.** Say it |
| **Attack surface** (Censys, Shodan) | CT + DNS + our own TLS/headers + RIR RDAP netblocks | 🔴 **Not substitutable.** You can enumerate *names* and *netblocks*; you cannot see *services*. **Do not fake it with active scanning** — that is the line v1 refuses |
| **Credential exposure** (SpyCloud) | HIBP `/breaches` — the domain endpoint is paid, and third-party domain search needs ownership verification you cannot have | 🔴 **No substitute.** Snowflake demonstrates the gap live |
| **Ransomware extortion listings** (KELA) | Public leak-site aggregators — see Tier 1c | 🟡 **Possible, pending a licence reply** |
| **Version-level CVE matching** (VulnCheck) | KEV + NVD product-name matching | 🟡 **Coarse.** Correctly penalises without applying the ceiling, because a name match is not proof this vendor is unpatched |
| **Historical infrastructure** (SecurityTrails) | Wayback CDX + CT issuance history | 🟡 **Partial.** Good for pages and certificates, weak for DNS |
| **Sector breach base rates** (TI vendors) | **OAIC NDB sector statistics** | 🟢 **Better, arguably** — it is an Australian regulator's own published data |
| **Continuous monitoring** (all platforms) | Our own scheduler over idempotent collectors | 🟢 **Fully substitutable.** Pure build effort |
| **Peer benchmarking** (all platforms) | Your own portfolio, once you have one | 🟡 **Needs a population, not a purchase** |

**The pattern:** most "paid" capabilities in TPRM are **build effort dressed as a product**. The three
that genuinely are not — attack surface, credential exposure, private financials — are precisely the
three named in [`methodology.md`](methodology.md) §7.2 as known weaknesses. **The limitations section
was already correct.**

---

# Part VI — What stays impossible for free, and how to say it

Do not apologise for these. State them as scope, once, on the card — the brief's own instruction is
*"say what a signal does and does not tell you."*

| Gap | The sentence to use |
|---|---|
| **Open ports / exposed services** | *"This assessment does not include internet-wide port scanning. v1 makes no active connections to vendor infrastructure beyond a single TLS handshake and one HTTPS request to the primary domain — a deliberate Terms-of-Service and lawful-access boundary, not an oversight. Estate visibility via a licensed provider is Roadmap Priority #1."* |
| **Private-company financials** | *"Business stability here means entity standing — is this a live, in-good-standing legal entity — not financial health. No free source publishes private-company financials."* |
| **Non-consumer breaches** | *"Breach data skews consumer-facing. A vendor with no breach record may simply have had no consumer-facing incident. Absence of a breach record is not evidence of security."* |
| **AU sanctions** | *"The sanctions gate currently screens the US Consolidated Screening List. Australian DFAT coverage is pending a licence confirmation and is recorded as a known gap."* |
| **Internal controls** | *"Roughly ten of twenty-seven standard due-diligence criteria — access controls, security monitoring, data handling, insurance, change management, contract terms — are invisible to any lawful external observer. This assessment pre-fills what can be independently evidenced and flags contradictions; it does not replace a questionnaire."* |
| **Perimeter ≠ posture** | *"A strong external posture is compatible with a weak internal one. This measures what a stranger can see."* |
| **Size bias** | *"Coverage tracks company size, not company risk. Larger vendors generate more public records. The confidence axis mitigates this; it does not cure it."* |

> **These sentences are a feature.** Both benchmarked commercial platforms disclose *less* about their
> own limits than this list does — SecurityScorecard's own methodology concedes that **60–89% of
> breaches go unreported** and that its statistical power is limited by that. A tool that names its
> blind spots is more usable than one that hides them, and under Finding A it is also the safer one.

---

# Part VII — The 90-day plan

| Weeks | Ship | Outcome |
|---|---|---|
| **1–2** | Items 1, 2, 7 — action layer, recommendations, two industry profiles | **The score becomes a decision.** Config-heavy, corpus-guarded, no new sources |
| **3–4** | Items 3, 5 — firmographics, executive block + role views | **Every vendor is profiled and every reader is served.** Unblocks benchmarking |
| **5–6** | Items 4, 6 — fourth-party enumeration, evidence pack export | **The CPS 230 ¶48 wedge, and something to put in the procurement file** |
| **7–8** | Items 8, 9, 10 — ABN Lookup, Companies House + adapter, OTX | **AU/UK authority, ANZSIC industry, CT redundancy.** Free keys only |
| **9–10** | Item 11 — dispute path | **Open item 12 closed.** The known Finding A exposure |
| **11–12** | Item 12 — scheduler + drift | **Point-in-time becomes continuous** |
| **Throughout** | Chase DFAT and Modern Slavery licence replies | **AU sanctions in the gate; ESG category open** |

**Where that leaves the eleven lifecycle stages:**

| | Before | After 90 days |
|---|---|---|
| Stages at ≥70% coverage | 4 of 12 *(incl. Presentation)* | **9 of 12** |
| Stages at 0% | 1 | **0** |
| Blocked on money | Two evidence buckets in Stage 2, and the Stage 4 enrichment they feed | **unchanged — and honestly labelled** |

**What is still not done at day 90, and should be said out loud:** portfolio-dependent work — peer
percentiles, concentration analysis, the executive dashboard. Those need a **population of vendors**,
which is a platform integration, not a methodology gap. Everything else on the free tier is finished.

---

## The claim this document defends

> **The doable methodology is not the perfect one with the expensive parts removed.**
>
> It is the **same model** — the same arithmetic, the same gates, the same two axes, the same evidence
> store — running on the evidence a lawful, free register can supply, **and declaring the difference on
> every card it publishes**.
>
> That is why every item in Part III is additive: when a budget arrives, commercial feeds enter as new
> signals with new bands under the existing points table. **Nothing built on this plan is thrown away.**

---

### See also

- [`perfect_methodology.md`](perfect_methodology.md) — the target state and what each paid tier buys
- [`review_response.md`](review_response.md) — the nine reviewer points these items answer
- [`roadmap.md`](roadmap.md) — the productisation path
- [`source_assessment.md`](source_assessment.md) — the clearance bar every candidate source must pass
- [`scoring.yaml`](../scoring.yaml) — where items 1, 2 and 7 land
