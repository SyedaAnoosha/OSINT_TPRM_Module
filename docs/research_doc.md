# Research Methodology — OSINT for Third-Party Risk

**Deliverable: the research methodology document.** For each source: what it signals, how it is collected, how
reliable it is, what it does **not** tell us, and its legal / terms-of-service position.

**Status:** v1 · **Source terms verified live** (not from memory) on the dates in the register and in the
[verification log](source_assessment.md#verification-log). **Scoring direction:** `100 = strongest posture,
0 = weakest` (see [`scoring_model.md`](scoring_model.md)).

> This document is the **method**. The exhaustive per-source verification log, every excluded source with the
> verbatim clause that killed it, and the proposed-source review sit in the companion register
> [`source_assessment.md`](source_assessment.md). The scoring model those signals feed is
> [`scoring_model.md`](scoring_model.md); the full legal/epistemic defence is [`methodology.md`](methodology.md).

---

## 1. How we chose sources — the selection principle

The brief sets two non-negotiables **above coverage**: *legality first*, and *free or trial data only*. Everything
below follows from one rule:

> **Prefer sources published in order to be read.**

Certificate Transparency logs, sanctions lists, and statutory registers exist specifically so outsiders can audit
them — their legal position is not a risk to manage, it is absent by design. Sources that require scraping, or whose
terms say "non-commercial", cost a paragraph of justification each and can collapse later. Because this work is a
candidate for a commercial platform (the Wahid AI third-party module), **any source restricted to non-commercial
use is excluded now, not at handover** — that is why VirusTotal, SSL Labs, and the Shodan/Censys free tiers are out
(see §6).

Three method commitments follow:

1. **Read the live terms, quote them verbatim.** Every legal position below was verified by fetching the actual ToS
   page, not a secondary summary. Where a source states *no* licence, that is recorded as an **open question**, not
   assumed to be permission.
2. **Depth over breadth.** A few signals collected well beat twenty collected badly. We collect **26 signals across
   14 cleared collectors**, each returning the same evidence envelope, failure-isolated — counts verified against
   the shipped model and a live run, not estimated (§5).
3. **When unsure, ask before collecting.** Two locally-relevant Australian sources (DFAT sanctions, the Modern
   Slavery Register) state no licence — both are **held pending a written licence query**, not quietly ingested.

---

## 2. Legal and standards frame (the short version)

| Frame | What it binds us to |
|---|---|
| **Criminal Code Act 1995 (Cth) Part 10.7** | We touch only what the vendor publishes to be read — no auth bypass, no non-public endpoint, no rate abuse. Retrieving a public page is authorised by the act of publication. |
| **Privacy Act / APP 10 · the privacy tort · EU AI Act Art 6(3)** | **We score entities, not natural persons.** Executives, PEPs, person-level ownership, and demographic inference are excluded at a bright line and logged, never silently dropped. |
| **Autonomous Sanctions Act 2011 s16(7)** | A sanctions hit is legally meaningless as a "score" — so it is a **gate that blocks** and routes to a human, never a grade. |
| **NIST SP 1326 (C-SCRM due-diligence quick-start)** | Supplies the four per-finding variables (severity, age, frequency, mitigation) and recommends the ITA screening list by name. Adopted and cited — severity, age and frequency are applied; **mitigation is wired but dormant, because no source on this register evidences remediation** (§4). |
| **APRA CPS 230 ¶48 · ISO/IEC 27001 A.5.19–5.23** | Frame the fourth-party / supplier-relationship signals (subprocessor lists → concentration risk). |

Full derivation and the two "findings" (evidence store as legal artefact; sanctions as a gate) are in
[`methodology.md`](methodology.md) §4.

---

## 3. The cleared sources — signal, collection, reliability, limits, legality

Each row is a source we **use in v1**. "Reliability" is how much weight a positive detection earns; a *clean
receipt* (successfully queried, came back clean) earns a reduced reliability, because absence from a
non-exhaustive corpus is weaker evidence than a hit.

### 3.1 Cyber Hygiene & Technical

**DNS (direct query)** — *SPF, DKIM, DMARC policy, MX, NS, CAA.*
Collection: standard DNS resolution. **Reliability: High** (authoritative, real-time). **Limits:** email-security
posture only — a vendor with `p=reject` can still be insecure elsewhere. **Legal:** clean — the protocol performing
its designed function against records published for public resolution; no ToS, no access control. DMARC is the
sharpest cheap signal and grades on a real ladder (absent → `p=none` → `quarantine` → `reject`).

**Self-run TLS handshake + HTTP security headers** — *TLS versions, ciphers, cert expiry/chain, HSTS, CSP,
X-Frame-Options, `security.txt` (RFC 9116).*
Collection: our own TLS client plus **one HTTP GET** of the public homepage. **Reliability: High** (direct
observation, no intermediary). **Limits:** perimeter only — nothing about encryption at rest or internal
segmentation. **Legal:** clean *and deliberately so* — a single request identical to any browser visit;
**this replaces Qualys SSL Labs on legal grounds** (SSL Labs' ToS forbids commercial use, public sites, and
assessing servers whose owners haven't given permission — structurally incompatible with third-party assessment).

### 3.2 Breach & Compromise History

**Have I Been Pwned — `/breaches` endpoint only** — *confirmed breach events, dates, records affected, data classes
(`Passwords`, `Credit cards`, …), verified flag.*
Collection: `GET /api/v3/breaches`, **no key, no auth**. **Reliability: High** for what it asserts. **Limits: significant,
stated on the scorecard** — absence of a breach record is *not* evidence of security, only of *no publicly known
breach*; coverage skews consumer-facing. **Legal: CC BY 4.0 — commercial use expressly permitted with attribution**
(link to haveibeenpwned.com where the data appears). We deliberately use only `/breaches`, never the domain-search
endpoint (which needs domain-control verification + a paid subscription) — so we learn *that a company was breached*,
never *which of its users were*. That is the privacy-respecting choice as well as the free/lawful one.

**CISA Known Exploited Vulnerabilities (KEV)** — *vulnerabilities known to be actively exploited in the wild.*
Collection: public JSON feed. **Reliability: High and high-signal** — KEV membership means *observed exploitation*,
not hypothesis. **Limits:** same stack-mapping limit as NVD — scope to vendor products. **Legal:** US Government work,
generally not subject to domestic copyright; the feed carries no licence field (**open item** — confirm CISA's
published statement rather than relying on the general rule).

**NVD API** — *CVEs, CVSS severity, affected version ranges.*
Collection: NVD REST API (free key recommended for rate). **Reliability: High** for CVE facts. **Limits — the
important one:** mapping CVEs to a vendor needs their internal stack, which OSINT barely reveals. **Scope narrowly:**
score vendors who *make software* (their product's CVE / end-of-life history), never infer "vendor is vulnerable"
from a banner. **Legal:** commercial OK; **mandatory verbatim notice** on the scorecard — *"This product uses the
NVD API but is not endorsed or certified by the NVD."*

**How that recall limit shapes the model — worst-of, not sum.** Because a keyword match to a vendor name is
*coarse*, a long CVE list is match **volume**, not a count of distinct events. So KEV and NVD findings collapse to
their **worst single representative** and are explicitly exempt from the frequency multiplier: 13 KEV name-matches
against Atlassian contribute one penalty, not thirteen. Without that rule, the vendor with the most public product
surface would score worst regardless of posture — the source's weakness would masquerade as the vendor's.

The bands were also corrected on the same reasoning. NVD bands now state **only the observed CVSS severity**
(`cvss_critical` / `cvss_high` / `cvss_medium_or_low`). An earlier band named `remediated` was a misnomer — it was
the catch-all for anything below HIGH, so a medium CVE was labelled "remediated" purely for not being high, which
asserted a fix NVD had never observed.

**FIRST EPSS** — *exploitation probability per CVE (0–1).*
Collection: public JSON, **no auth**. **Reliability: High** as an enrichment — it sits a probable-exploit CVE between
theoretical CVSS and confirmed KEV. **Limits:** a probability, not a fact of exploitation. **Legal: CC0 / open.**

### 3.3 Digital Footprint & Assets

**Certificate Transparency — crt.sh (primary) + Cert Spotter (fallback)** — *subdomain estate, certificate issuance
history, expiry, weak/deprecated issuance, forgotten dev/staging hosts.*
Collection: HTTPS query to crt.sh; on failure fall back to SSLMate's Cert Spotter (`api.certspotter.com`). Both index
the same public CT logs (RFC 6962). **Reliability: High** — every publicly-trusted cert is logged by design,
cryptographically anchored, not self-reported. **Limits:** shows certs *issued*, not hosts *live* — a logged
subdomain may be dead; wildcard certs hide detail; says nothing about configuration. **Legal:** CT data is public by
RFC 6962. crt.sh publishes **no ToS** (an unstated grant — low residual risk, accepted and logged). Cert Spotter's
free tier is **evaluation-cleared** for the PoC (its ToS bars no commercial/automated use); production should move to
a free SSLMate account per their tiering (**open item**). We rate-limit both, identify our agent honestly, prefer
crt.sh, and fall back only on failure.

**The fallback is not theoretical — it fired during corpus capture (2026-07-23).** crt.sh returned `502 Bad Gateway`
on both attempts for `atlassian.com` and Cert Spotter served the query instead. That is the documented
single-point-of-failure risk for Digital Footprint behaving exactly as designed, and it is also the evidence for
why a *third* passive-DNS source (AlienVault OTX) sits on the roadmap: today this category rests on two providers
indexing the same logs, one of which is visibly flaky.

### 3.4 Vendor Transparency & Governance / Compliance & Regulatory

**Vendor trust pages, `security.txt`, public DPAs, subprocessor lists** — *ISO 27001 / SOC 2 claims and expiry,
pen-test attestations, DPO contact, **subprocessor lists → fourth-party dependencies**, status pages.*
Collection: polite fetch of the vendor's own published pages, honouring `robots.txt`. **Reliability: Low–moderate —
self-reported** (the exact input the brief moves away from); treat as *claim*, not evidence, unless corroborated by a
registry. **Limits:** unverified claims, stale pages; absence correlates with company size, not risk. **Legal:**
published by the vendor to be read — honour `robots.txt`, identify our agent, rate-limit; per-vendor terms checked
for any vendor placed under recurring monitoring. **Why it still earns its place — the fourth-party angle:** public
DPAs list subprocessors, yielding fourth-party dependency data *for free*, serving CPS 230 ¶48 (concentration risk a
questionnaire can't surface).

### 3.5 Business & Financial Stability *(entity-level only — never natural persons)*

**GLEIF — the Global LEI register** — *legal-entity standing (ACTIVE/INACTIVE), LEI currency
(ISSUED/LAPSED/RETIRED/ANNULLED), jurisdiction, legal name, entity-level parent/child.*
Collection: `api.gleif.org/api/v1/lei-records` filtered by legal name; free, **no auth**. **Reliability: High** —
authoritative and *exhaustive* for the fact it asserts, so a clean "active/good standing" is a **full-reliability
positive**, not a discounted receipt. **Limits:** standing, not financials — no going-concern, bankruptcy, or
litigation data; some small vendors have no LEI (a genuine per-vendor `empty` → lowers confidence, not posture).
**Legal: CC0 / public domain — the best on the register** (commercial, no permission, no attribution). **Replaced SEC
EDGAR**, which covered US-listed firms only and fed none of the private/AU test vendors.

**Wikidata — the second, domain-verified register (corroborates GLEIF)** — *entity existence + dissolution (P576),
resolved by **domain** (official-website property P856).*
Collection: `wbsearchentities` → `Special:EntityData/{QID}.json`; keeps **only** a candidate whose P856 registrable
domain equals the vendor's — no domain match → emits nothing. **Reliability: 0.7** (community-edited, but every
emission is domain-anchored to a hard identifier). **Limits:** patchy coverage. **Legal: CC0**; Wikimedia's one hard
condition is a descriptive, contact-bearing User-Agent (honoured). Why Wikidata and not ABN/Companies House:
those need a registered key (auth-gated, breaking the free/no-auth rule); Wikidata is keyless *and* fixes GLEIF's
name-only blind spot by resolving on domain.

**RDAP (domain registration)** — *domain standing: registry hold / imminent expiry / age.*
Collection: RFC 9082/9083 (the IETF successor to WHOIS), served by the registries themselves via the rdap.org
bootstrap — free, **no auth**, answers for essentially **any registered domain worldwide**. **Reliability: 0.85.**
**Limits:** reads *domain* standing, not financials (entity-level, kept off natural persons). **Legal:** public
registry data, no auth. This is the **universal** business-standing signal — it pulls Business Stability out of the
Ghost for the many private/global vendors GLEIF and Wikidata don't cover (verified across 20 vendors in 17
countries).

### 3.6 Adverse Media & Reputation *(hard facts only — not sentiment)*

**Regulator enforcement feeds (FTC + SEC + DOJ (US), CMA + ICO (UK), CNIL (EU/GDPR))** — *named enforcement actions,
settlements, orders, investigations that mention the vendor — dated and attributed.*
Collection: polite `GET` of official RSS/Atom feeds; the vendor name/domain is matched as a **whole word** (so
"canva" does not fire on "canvas"). A matched item is a **review candidate** (defamation control), never an
auto-published verdict; no match → a clean receipt. **Reliability: High when matched** (a regulator's own
publication is a fact); **Low (0.4) for a clean receipt** — a feed exposes only its recent window, so "no action
found" is weak evidence of absence. **Limits — stated, not hidden:** v1 is **US-weighted**; CISA hard-blocks
automated access (anti-bot) and AU regulators (OAIC) publish no stable RSS — an honest coverage gap. **Legal:**
government open data / statutory publications, published to be read and syndicated via RSS.

**ITA Consolidated Screening List (US)** — *US export restrictions, denied/debarred parties across Commerce, State,
Treasury.* → **used as the sanctions GATE, not a score.**
Collection: free API at `developer.trade.gov`. **Reliability: High** — official US Government publication.
**Limits:** US-scope; name-matching is the hard part (see §4). **Legal:** clean — US Government work, no stated
licence restriction; **recommended by name in NIST SP 1326**. A hit **blocks** the record for human adjudication
(§Autonomous Sanctions Act above), it never grades the vendor.

### 3.7 Held / enrichment-only

**GDELT** — *adverse-media candidates, tone, event coding.* **Held / `ai_adjudicated`:** it gathers candidates into
the evidence store but does **not** score, because it reports *allegations* (defamation exposure) and its free API
rate-limits hard. **Legal: the strongest licence on the list** — "unlimited and unrestricted… for any academic,
commercial, or governmental use… without fee." Retained for the designated AI moment (summarising which adverse-media
hits *actually matter*), not for scoring.

*Known wart, recorded rather than hidden:* the collector emits a `tone_volume` signal that the model has no band
for, so it is dropped with a warning on every run. Held-means-unscored is the correct outcome here, but it is
currently achieved by accident (an unmapped signal) rather than by design (an explicit hold). The signal should
either be given a home or stop being emitted.

---

## 4. Cross-cutting limits (properties of the problem, not of sourcing)

- **Entity resolution is the hard problem, not collection.** Proving a breach/sanction/news item belongs to *this*
  vendor — not a homonym, subsidiary, or namesake — is where accuracy is won or lost. Sanctions screening is the
  acute case (a false positive is a serious accusation), so hits surface as **review items with evidence**, never as
  silent automated changes. Two halves of that defence are in different states, and the difference is stated here
  rather than blurred:
  - **Name matching is real and tested.** A query matches only on **whole words**, so *asana* no longer fires on
    *villaSANA* / *SANAbil*. Recall-tuned deliberately: a false positive costs an analyst an hour, a false negative
    costs the point of the screen.
  - **The ambiguity gate is specified but not yet fed.** The model blocks a vendor whose resolution confidence is
    < 0.5, and the engine enforces that — but nothing currently *computes* the confidence. It is an API input
    defaulting to 1.0, so in practice the gate only fires when a caller volunteers a low value. **Until resolution
    confidence is derived from evidence (GLEIF resolving, Wikidata's P856 corroborating the domain, whether the
    domain was supplied or chosen from candidates), treat "we never silently score the wrong company" as a design
    commitment, not an operating control.** The honest v1 mitigation is the one that *is* enforced: a bare name
    never infers a domain — the API stops and asks the caller to confirm one.
- **Absence of evidence is not evidence of absence.** No breach record / no adverse media is the *default* state of
  a small clean vendor *and* of a badly-run one nobody has written about. **Design consequence: missing data reduces
  confidence, never posture.** Any model where a vendor scores well by being invisible is broken — the most likely
  way a naïve implementation fails, and it is worth recording that this implementation *did* fail it for a while.
  Averaging only the categories that returned data let a clean receipt enter the average as a 100 and lift the
  score, so a resolved trust page bought +23 posture and a source outage lowered a vendor's grade. It is now
  arithmetic — the divisor is fixed by the model, so a silent source adds no penalty and cannot move the
  denominator — and a regression test holds it: identical findings with varying silent sources must produce an
  identical posture. **A rule this central should be enforced by the maths, not by intention.**
- **Public data is stale and patchy.** NIST SP 1326's four variables (severity, age, frequency, mitigation) are a
  decay-and-context model handed down by a federal publication. Adopted and cited — with two source-driven
  qualifications stated rather than glossed:
  - **Age applies to occurrences, not to current state.** A breach date and a KEV listing date decay. A
    certificate's `notAfter` does **not** — it is a state boundary, so decaying it would make a cert expired six
    years ago cost *less* than one expiring next week.
  - **Mitigation is live in the engine but has no source to feed it.** Nothing on this register evidences that a
    given vendor fixed a given issue: KEV asserts a product line is exploited, NVD asserts a CVE exists. Neither
    observes *this* vendor's patch state. Remediation is therefore never inferred from severity, and the ×0.6
    discount is currently never applied to anyone.
- **Regulators warn against bought scores.** The French AFA warns that users "must be able to determine their own
  rating system" and that automated tooling "requires human analysis… particularly for the most high-risk third
  parties." A regulator on record that black-box vendor scores are indefensible — the brief's thesis, independently
  confirmed, and why our model lives in a file a client can read and tune.
- **~10 of ~27 typical due-diligence criteria are invisible to any lawful external observer** (access controls,
  monitoring, insurance, contract terms). OSINT does not replace the questionnaire — it pre-fills the fraction it can
  evidence independently and **flags contradictions** where a vendor's self-assessment disagrees with the public
  record.

---

## 5. Source behaviour is pinned, not asserted

Every "Reliability: High" above is a claim about how a source *behaves*. Those claims are now checkable: the full
collector output for the five benchmark vendors (Atlassian, Snowflake, Slack, MYOB, OneTrust) was captured live on
**2026-07-23** and frozen in `backend/tests/fixtures`, then replayed through the scoring engine against a pinned
clock. All 14 collectors returned for all five vendors.

This turns three otherwise-unfalsifiable statements into measurements:

- **Coverage is real.** Full runs return **0.96–1.00** of the 26 planned signals. The register is not aspirational —
  the sources answer, for real vendors, in one pass.
- **Clean receipts are load-bearing.** Snowflake's HIBP clean receipt (§3.2) and the KEV no-match receipts are in
  the fixtures, so the "checked and clean ≠ never checked" rule can be demonstrated rather than described.
- **Failure modes are captured too**, not smoothed away — the crt.sh 502 above is in the record.

The value for *this* document is regression, not decoration: if a source changes what it returns, the fixtures stop
matching live behaviour and the discrepancy is visible instead of silently re-grading vendors. Deliberate
re-baselining is `python -m tests.regolden`, and the resulting diff names the vendor and category that moved.

**One honest limitation.** Frozen fixtures pin what the sources returned *on that date*; they cannot detect that a
source has since changed its terms, its schema, or its licence. The verification log in
[`source_assessment.md`](source_assessment.md) remains the mechanism for that, and it is a human one.

---

## 6. One egress point — the optional LLM summariser

The only component that sends data to a third party *not* on the source register is the **opt-in** evidence
summariser. It is **off by default** (no `TPRM_LLM_*` env → the endpoint returns 503) and, when on, is
**provider-agnostic** over any OpenAI-compatible `chat/completions` host the operator chooses (e.g. OpenRouter,
Groq, Google's OpenAI-compat surface). What leaves the system is the finished **record** — the score roll-up plus
the actual hash-stamped observations — **bounded** (per-receipt and total caps, test-enforced) and consisting only
of already-collected, lawfully-public, entity-level OSINT (PII is minimised at *collection*). The summary is a
**read layer**: it never computes or alters a score, never writes to the immutable evidence store, is returned marked
AI-generated, and cites the `content_hash`es it was built from. An operator enabling it chooses their own provider
and inherits that provider's data-handling terms — a deliberate, documented, single egress point, not a hidden
dependency.

---

## 7. Excluded and held sources (summary — full reasoning in the register)

| Source | Verdict | Reason |
|---|---|---|
| **VirusTotal** | **Excluded** | Public API "must not be used in commercial products or services." |
| **Qualys SSL Labs** | **Excluded** | ToS bars commercial use, public sites, and assessing servers without owner permission — four independent blockers. Replaced by our own TLS client. |
| **Shodan / Censys (free)** | **Excluded (roadmap paid)** | Free/research tiers are **non-commercial** — the VirusTotal trap. Attack surface proxied via CT instead. |
| **OpenCorporates API** | **Excluded** | Free tier non-commercial; commercial API paid. |
| **Google News (scraped)** | **Excluded** | No free API; scraping breaches Google's terms. Superseded by GDELT. |
| **SEC EDGAR** | **Removed → GLEIF** | US-listed only (poor recall) + UA-gated 403. GLEIF is global, CC0, no-auth. |
| **DFAT Consolidated List (AU sanctions)** | **Held — ask first** | No licence stated. Written query to the Australian Sanctions Office pending; ITA is the gate meanwhile, AU coverage logged as a known gap. |
| **AU Modern Slavery Register** | **Held — ask first** | Copyright notice only, no licence. Written query to the Attorney-General's Department pending. |
| **Companies House (UK) · ABN Lookup (AU)** | **Cleared, roadmap** | Both commercial-OK, but each needs a free registered key/GUID — roadmap corroboration for GLEIF/Wikidata. |

Every excluded source above was verified against its **live** terms with the disqualifying clause quoted in
[`source_assessment.md`](source_assessment.md) §6 and the [verification log](source_assessment.md#verification-log).

---

## 8. Coverage against NIST SP 1326 — where v1 is strong and honestly thin

| NIST SP 1326 category | Covered by | Strength |
|---|---|---|
| Foundational Cyber Practices (supplier) | CT, DNS, TLS/headers, HIBP | **Strong** |
| Foundational Cyber Practices (product) | NVD, KEV, EPSS | Moderate — vendor-products only |
| Resilience | GLEIF, Wikidata, RDAP, regulator RSS, HIBP | Moderate — standing, not financials |
| Supply Chain Tiers (fourth party) | subprocessor lists | Moderate — self-reported |
| FOCI / Provenance | *(registries — key-gated)* | **Weak — the honest v1 gap** |

FOCI and Provenance are the honest gap in v1, pending the keyed corporate registries — stated rather than papered
over. What comes next is [`roadmap.md`](roadmap.md).

---

### See also

- [`source_assessment.md`](source_assessment.md) — the exhaustive source register, proposed-source review, and live verification log
- [`scoring_model.md`](scoring_model.md) — the model these signals feed
- [`methodology.md`](methodology.md) — the full legal / epistemic defence
- [`roadmap.md`](roadmap.md) — productisation and what to collect next
