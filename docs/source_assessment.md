# Source Assessment — OSINT for Third-Party Risk

**Deliverable 1 of 5** (research methodology document — source register)
**Status:** v0.1 draft · **Terms verified:** 17 July 2026 (register); GLEIF, Cert Spotter, FTC RSS added & verified 20 July 2026 · **Author:** *(intern)*

---

## Purpose and method

The brief sets two non-negotiables above coverage: *legality first*, and *free or trial data only*. This document records, per source, what it signals, how it is collected, how reliable it is, what it does **not** tell us, and its legal / terms-of-service position.

**Selection principle — prefer sources published in order to be read.**
Certificate Transparency logs, sanctions lists and statutory registers exist specifically so outsiders can audit them. Their legal position is not a risk to be managed; it is absent by design. Sources requiring scraping, or whose terms say "non-commercial", cost a paragraph of justification each and can collapse later. Because this work is a candidate for a commercial platform (Wahid AI third-party module), **any source restricted to non-commercial use is excluded now, not at handover.**

**Every position below was verified by reading the live terms on 17 July 2026**, not from memory or secondary summaries. Quotes are verbatim. Where a source states no licence, that is recorded as an open question rather than assumed to be permission.

**Scoring direction convention (used throughout):** `0 = lowest risk, 100 = highest risk`. Stated once here and never inverted.

---

## Summary register

| # | Source | Signals | Position | Verdict |
|---|--------|---------|----------|---------|
| 1 | Certificate Transparency (crt.sh + certspotter fallback) | Subdomains, cert history, expiry | Public by RFC 6962; crt.sh no ToS, certspotter ToS bars no commercial/automated use | **Use** (see caveat) |
| 2 | DNS (direct query) | SPF, DKIM, DMARC, MX, NS | Protocol operating as designed | **Use** |
| 3 | Self-run TLS + HTTP headers | TLS version, cipher, HSTS, CSP | Own client; one GET of a public page | **Use** |
| 4 | Have I Been Pwned `/breaches` | Confirmed breaches, dates, data classes | CC BY 4.0 — commercial OK w/ attribution | **Use** |
| 5 | ITA Consolidated Screening List | US sanctions / export exclusions | US Gov, free API, no restriction stated | **Use** (gate) |
| 6 | DFAT Consolidated List | Australian sanctions | **No licence stated — query required** | **Ask first** |
| 7 | **GLEIF (LEI register)** | Entity standing, registration currency, jurisdiction | **CC0 / public domain; commercial OK, no auth** | **Use** (replaces EDGAR) |
| 7b | **Wikidata (structured data)** | Entity existence / dissolution — *domain-verified* corroboration of GLEIF | **CC0 / public domain; commercial + automated OK; only a contact-bearing UA required** | **Use** (2nd register) |
| 8 | NVD API | CVEs against vendor products | Commercial OK; attribution notice required | **Use** (scoped) |
| 9 | CISA KEV | Known *exploited* vulnerabilities | US Gov work; no licence field in feed | **Use** (scoped) |
| 10 | **Regulator RSS (FTC + cleared feeds)** | Named enforcement actions / investigations | Gov open data / statutory publications | **Use** (adverse media) |
| 11 | GDELT | Adverse-media *candidates* (ai_adjudicated) | "unlimited and unrestricted... commercial" | **Use** (held, Phase 5) |
| 12 | Vendor trust pages / security.txt / DPAs | Certifications, fourth parties | Vendor's own publication; robots.txt applies | **Use** |
| 13 | AU Modern Slavery Register | Statutory statements | **No licence stated — query required** | **Ask first** |
| 14 | **ABN Lookup (AU)** | AU entity status (Active / Cancelled), entity type, trading names | Web Services Agreement permits third-party extracts, **no commercial bar, no bulk-harvest bar**; free registration GUID; must not imply Commonwealth endorsement | **Use** (built; `empty` without a GUID) |
| 15 | **Wikidata firmographics (P452/P1128/P2139/P414/P17/P571/P749)** | Industry, employees, revenue, listing, country, inception, corporate parent — **profile context only, emits no findings** | **CC0 / public domain**; contact-bearing UA required | **Use** (never scored) |
| — | SEC EDGAR | Filings, financial distress, ownership | US-listed only (poor recall) + UA-gated | **REMOVED** (→ GLEIF) |
| — | VirusTotal | Reputation | *"must not be used in commercial products"* | **EXCLUDED** |
| — | Qualys SSL Labs | TLS grade | Commercial + permission + publication bars | **EXCLUDED** |
| — | **Google Safe Browsing API** | Domain/URL reputation — malware & phishing flags | **Commercial use prohibited**; revenue-generating use is directed to the paid Web Risk API (verified 24 Jul 2026) | **EXCLUDED** — the VirusTotal pattern |
| — | Shadowserver Foundation | Exposure reports | Reports are issued to **the network owner / national CERT**, not to third parties assessing them | **Not applicable** |
| — | Shodan / Censys | Exposed services | Free tier too thin; paid = out of scope | **Roadmap** |
| — | Companies House | UK registry — entity status | OGL, commercial OK, free key, 600/5min | **Cleared (roadmap)** |
| 16 | **AlienVault OTX (passive DNS)** | Subdomain enumeration — **CT redundancy** for Digital Footprint | Free API key; cleared as CT redundancy | **Use** (built; `empty` without a key) |
| 17 | **Companies House (UK)** | UK entity status (active / dissolved / liquidation) | **OGL, commercial-OK, free key, 600/5min** | **Use** (built; `empty` without a key) |
| — | ~~ABN Lookup (AU)~~ | *promoted to #14 — BUILT* | — | **Built** |
| — | ~~Companies House~~ | *promoted to #17 — BUILT* | — | **Built** |
| — | ABN Lookup — **ANZSIC industry code** | Industry classification per ABN | **Non-public ABR data: released to eligible government agencies only** — absent from the public JSON services (verified 24 Jul 2026) | **Unavailable to us** — sector falls back to Wikidata |
| — | Google News (scraped) | Adverse media | Against ToS; no free API | **EXCLUDED** — use GDELT |

---

## Proposed-source review — v3.4 (2026-07-21)

A batch of candidate sources was proposed to harden the weak categories. Each was vetted against
the same bar the rest of the register uses: **free, commercial + automated use permitted, no ToS
trap, and reachable/parseable**. Verdicts below; the two cleared ones are IMPLEMENTED and live-verified.

### ✅ Implemented (cleared + verified live)

| Source | Category | What it adds | Licence | Verified |
|---|---|---|---|---|
| **FIRST EPSS** | Breach & Compromise | Exploitation *probability* per CVE — enriches NVD; a CVE ≥ 0.5 becomes `probable_exploit`, scored between theoretical CVSS and confirmed KEV | **CC0 / open, no auth** | 200 JSON; Snowflake 25/25 CVEs enriched; Atlassian's known criticals score EPSS 0.95–1.00 |
| **Regulator feeds — global** | Adverse Media | FTC + **SEC + DOJ** (US), **CMA + ICO** via gov.uk Atom (UK, incl. the data-protection regulator), **CNIL** (EU/GDPR). Added to the existing regulator collector, polled in parallel | US public domain / UK OGL / FR Licence Ouverte | All six 200 with items; reached live on the 5-vendor run |
| **RDAP** (domain registration) | Business Stability | The **universal** business-standing signal. RFC 9082/9083, the IETF successor to WHOIS, served by the registries themselves — free, **no auth**, answers for essentially ANY registered domain worldwide. Reads domain STANDING (registry hold / imminent expiry / age), NOT financials (entity-level, §4.2). Feeds the new `domain_standing` subcategory (30% of Business Stability); this is what pulls Business Stability out of The Ghost for the many private/global vendors GLEIF and Wikidata don't cover | **Public registry data, no auth** | Live-verified across 20 vendors in 17 countries (.com via Verisign RDAP, plus .co.jp/.de/.nz/.br/… authoritative servers via the rdap.org bootstrap) — every registered domain returned a standing record |

### ⏳ Cleared but needs a free key (ready-to-wire; can't self-provision the key here)

| Source | Category | Why held | Path |
|---|---|---|---|
| **AlienVault OTX** passive DNS | Digital Footprint | Second subdomain source (CT redundancy — the real single-point-of-failure). Free API **key required**; endpoint also timed out on probe | Add `TPRM_OTX_API_KEY` collector (roadmap) |
| **CourtListener** (RECAP) | Business Stability | US federal litigation. Free key; but name-matching dockets is noisy → review-candidate only | Optional-key collector (roadmap) |
| **Companies House / ABN / SEDAR+ / NZ** | Business Stability | Authoritative registries, but each needs a registered key/GUID. Would corroborate GLEIF+Wikidata for UK/AU/CA/NZ | Roadmap (keyed) |

### ⛔ Rejected — ToS / auth / anti-bot / no clean feed

| Source | Reason |
|---|---|
| **OpenCorporates API** | Free tier is **non-commercial**; commercial API is paid. Fails the free-commercial bar (same trap as the excluded feeds). Bulk data is ODbL but not the live API. |
| **Shodan / Censys free** | Free tiers are **non-commercial** — excluded for a commercial PoC (already on the register). |
| **GreyNoise / URLScan** | Community/free tiers are non-commercial or commercial-murky; needs a key. Held pending explicit ToS clearance. |
| **RapidDNS / BufferOver** | RapidDNS is a scrape target (anti-bot, unclear ToS); BufferOver is now key/Cloudflare-gated. |
| **CSA STAR / IAF CertSearch / UKAS / JAS-ANZ / ANAB / BSI / DNV** | Cert-verification directories with **no clean public API** — web search + anti-bot; scraping is fragile and ToS-uncertain. Real value, but not a lawful *free-API* path today. |
| **GDELT — scored (event-code filtered)** | Deliberately **kept held/ai-adjudicated (Phase 5)**. It reports allegations (defamation exposure, §5.4.1) and its free API 429s hard; it was just removed from the on-demand path for that reason. Event-code filtering doesn't change the licence/defamation posture. |
| **Mozilla Observatory / internet.nl** | Observatory's public API endpoints 404/502'd (service migrated); internet.nl needs a granted account. Both only *corroborate* our own scanner anyway (lower marginal value). |
| **GitHub Security Advisories / CISA Vulnrichment** | Work no-auth but largely **overlap NVD**; deferred as lower-value once EPSS is in. |
| **HHS OCR / FCC / ACCC / ASIC / OAIC / EDPB** | No reachable/stable public RSS found (403 or 404 on probe, 2026-07-21). AU regulators specifically publish no clean feed — an honest coverage gap, not silently dropped. |

---

## Cleared sources

### 1. Certificate Transparency — crt.sh (primary) + Cert Spotter (fallback)

- **Signals:** subdomain estate, certificate issuance history, expiry, weak/deprecated issuance, infrastructure sprawl (forgotten dev/staging hosts).
- **Collection:** HTTPS query to `crt.sh`; on failure, fall back to **SSLMate's Cert Spotter API** (`api.certspotter.com/v1/issuances`). Both index the same public CT logs (RFC 6962).
- **Reliability:** **High.** Every publicly trusted certificate is logged by design (RFC 6962). Not self-reported; cryptographically anchored.
- **Limits:** Shows certificates *issued*, not hosts *live*. A logged subdomain may be dead. Wildcard certs hide subdomain detail. Says nothing about whether the host is well configured — only that a cert exists.
- **Legal / ToS position:** Verified 17 Jul 2026 — **crt.sh publishes no terms of service, acceptable use policy, or stated rate limit**; operated by Sectigo Limited. **Cert Spotter added 20 Jul 2026** because crt.sh is operationally flaky (verified live: multi-minute `ReadTimeout` outages that zeroed Digital Footprint for all five vendors). SSLMate's ToS (`sslmate.com/policies/tos`, fetched live) **bars no commercial use, automated access, scraping, or redistribution** — only "illegal or unauthorized purpose." The free no-key tier is documented "for personal or evaluation purposes" (our PoC = evaluation); a free SSLMate account (Small plan) is the production path.
- **Caveat — honest reading:** absence of stated terms (crt.sh) is *not* an explicit grant, and Cert Spotter's free tier is **CLEAR-CONDITIONAL** — evaluation-cleared for the PoC, production needs a (free) SSLMate account per their tiering (**open item**). The underlying CT data is public by design either way; both are convenience indexes we could replace with direct CT-log queries. **Mitigation:** rate-limit both, identify our agent honestly, prefer crt.sh, fall back only on failure. Residual (low) risk logged, not a claimed clean grant.

### 2. DNS records

- **Signals:** SPF, DKIM, **DMARC policy**, MX, NS, CAA.
- **Collection:** standard DNS resolution.
- **Reliability:** **High**, authoritative, real-time.
- **Limits:** email-security posture only. A vendor with `p=reject` can still be catastrophically insecure elsewhere. No inference beyond the mail path.
- **Legal / ToS position:** **Clean.** A DNS query is the protocol performing its designed function against records published for public resolution. No scraping, no ToS, no access control circumvented.
- **Why it earns its place:** DMARC is the sharpest cheap signal available and is *gradeable on a real scale* — absent → `p=none` (monitoring only, no enforcement) → `p=quarantine` → `p=reject`. It ties directly to business email compromise, a risk clients understand immediately.

### 3. Self-run TLS handshake + HTTP security headers

- **Signals:** TLS protocol versions, cipher suites, certificate expiry/chain, HSTS, CSP, X-Frame-Options, `security.txt` (RFC 9116) presence.
- **Collection:** our own TLS client (`sslyze` / `testssl.sh`) plus **one HTTP GET** of the vendor's public homepage.
- **Reliability:** **High** — direct observation, no intermediary.
- **Limits:** Perimeter only. Says nothing about encryption at rest, internal segmentation, or key management. A perfect header score is compatible with a terrible internal posture.
- **Legal / ToS position:** **Clean, and deliberately so.** This is a single request identical to what any browser issues when a member of the public visits the site — no authentication bypassed, no rate abuse, no non-public endpoint touched. Under the Criminal Code Act 1995 (Cth) Part 10.7, unauthorised *access* turns on access being unauthorised; retrieving a page the vendor publishes to the world for the purpose of being read is authorised by the act of publication.
- **Design note — this replaces SSL Labs deliberately.** Same signal, no ToS to breach (see exclusions). Running our own client is the *cheaper* legal position, not just the cheaper commercial one.

### 4. Have I Been Pwned — `/breaches` endpoint only

- **Signals:** confirmed breach events, breach date, records affected, data classes exposed (`Passwords`, `Credit cards`, …), verified/unverified flag.
- **Collection:** `GET /api/v3/breaches` — **no API key, no authentication.**
- **Reliability:** **High** for what it asserts; breaches are curated and flagged verified/unverified.
- **Limits:** **Significant, and must be stated on the scorecard.** Absence of a breach record is *not* evidence of security — it is evidence of *no publicly known breach*. Undisclosed and undetected breaches are invisible. Coverage skews to consumer-facing services; a B2B vendor may be breached without ever appearing.
- **Legal / ToS position:** **Verified clean, and better than expected.** Licensed **Creative Commons Attribution 4.0 International** — commercial use is expressly permitted with attribution to Have I Been Pwned and a link to `haveibeenpwned.com` displayed where the data appears. AUP prohibits querying to harm breach victims, DoS, misidentifying user agents, and misrepresenting the data source — none of which we do.
- **Scope decision — one endpoint, not the other.** The **domain search** endpoint requires (1) adding the domain to a dashboard, (2) **verifying control of it via DNS or email**, (3) an API key, and (4) a Pro subscription. We will never control a vendor's domain, and the subscription is a paid feed. **Domain search is therefore excluded on both legality and the free-data rule.** We learn *that a company was breached* — never *which of its users were*. This distinction is deliberate and worth defending: it is also the privacy-respecting choice.

### 5. ITA Consolidated Screening List (US)

- **Signals:** US export restrictions, denied/debarred parties, entity exclusions across Commerce, State and Treasury lists.
- **Collection:** free API at `developer.trade.gov`; CSV / TSV / JSON downloads.
- **Reliability:** **High** — official US Government publication.
- **Limits:** US-scope only. Name matching is the hard part, not retrieval (see *Entity resolution* below).
- **Legal / ToS position:** **Clean.** US Government work; page states the tools "may be used as an aid to industry in conducting electronic screens of potential parties to regulated transactions," with no stated licence restriction. ITA notes "additional due diligence should be conducted before proceeding" and that the Federal Register is the official publication — which we mirror as a confidence caveat rather than treating a hit as dispositive.
- **Standing:** **Recommended by name in NIST SP 1326** (Pre-Checks, p.5). Citing NIST's recommendation is itself part of the defence.

### 7. GLEIF — the Global LEI register (replaces SEC EDGAR)

- **Signals:** legal-entity standing (ACTIVE / INACTIVE), LEI registration currency (ISSUED / LAPSED / RETIRED / ANNULLED), legal jurisdiction, entity legal name, parent/child structure (Level 2, entity-level only).
- **Collection:** `api.gleif.org/api/v1/lei-records` filtered by legal name. Free, **no auth**. Entity resolution is name-based (no domain index) and therefore coarse — the collector ranks candidates and records the count so an ambiguous pick is visible, never silent.
- **Reliability:** **High** — the LEI register is authoritative; issuance is regulated and periodically revalidated. Because it is *exhaustive* for the fact it asserts (an entity either is or isn't on the register in a given state), a clean "active / good standing" is a **full-reliability positive observation**, not a discounted clean receipt (methodology §5.4.2).
- **Limits:** entity STANDING, not financials. It does **not** carry going-concern, bankruptcy, litigation, or ownership-*change* data — those subcategories stay `held` (no free authoritative source; change-detection needs history a snapshot can't give). A `LAPSED` LEI is a mild governance signal (the entity stopped renewing), not proof of distress. Some small vendors have no LEI at all → genuine per-vendor `empty` (lowers confidence, not risk — the MYOB principle).
- **Legal / ToS position:** **Verified clean 20 Jul 2026 (best on the register).** GLEIF Level-1 data is published under **CC0 1.0 — public domain**: freely accessible, copyable, and usable **for any lawful purpose including commercial, without permission, payment, or attribution** (`gleif.org/en/about/open-data`, `/meta/lei-data-terms-of-use`, fetched live). The only ToU constraints are not misrepresenting the data as GLEIF-provided/endorsed and not implying affiliation — trivially honored.
- **Why it replaced EDGAR:** EDGAR covered **US-listed firms only** — it fed *none* of the five test vendors reliably (2 listed, 3 private/AU) and required a contact-bearing UA on pain of a 403 IP ban. GLEIF resolves **all five**. EDGAR removed from the collector registry.
- **Coverage verified live 20 Jul 2026:** Atlassian, Snowflake, Canva, OneTrust, MYOB all resolve to an LEI record (MYOB's shows a `LAPSED` registration — a real, if mild, signal).

### 7b. Wikidata — the second, domain-verified register (corroborates GLEIF)

- **Why a second source (lever 2).** Confidence should reward *corroboration*: two independent public registers agreeing that an entity is live is stronger evidence than one. GLEIF is register #1; Wikidata is register #2. When both land on `legal_entity_status` and agree, the engine combines their reliabilities (noisy-OR, methodology §5.4.3) and the category reads at higher confidence than either alone — **earned**, not tuned.
- **Why Wikidata and not ABN Lookup / Companies House.** ABN Lookup and Companies House both require a **registered API key** (auth-gated), which breaks the free/no-auth PoC rule. Wikidata is **CC0 / public domain, no key**, *and* it carries the official-website property (P856) that GLEIF lacks — so it resolves by **domain**, fixing GLEIF's name-only blind spot. ABN/Companies House remain roadmap enrichments for a keyed build.
- **Collection:** `wbsearchentities` (name → candidates), then `Special:EntityData/{QID}.json` per candidate. Resolution keeps **only** a candidate whose P856 official-website registrable domain **equals the vendor's domain**; no domain match → emit **nothing** (`empty`). Corroborating the *wrong* entity is worse than not corroborating — so honest silence is the default.
- **Signals:** entity existence + dissolution (P576). Domain-verified & no P576 → benign "active_confirmed"; P576 present → "dissolved" (distress). Entity-level only (§4.2 — no natural persons).
- **Reliability:** **0.7** — community-edited, but every emission is domain-anchored to a hard identifier, so a false attribution is very unlikely.
- **Legal / ToS position:** **Verified clean 21 Jul 2026.** Wikidata structured data is **CC0 1.0** (`wikidata.org/wiki/Wikidata:Licensing`, fetched live): no restriction on automated access or commercial use, no attribution required. Wikimedia's **one** hard condition is a descriptive, contact-bearing **User-Agent** (a generic/library UA is 403'd by their robot policy) — honored by the shared client's UA.
- **Coverage verified live 21 Jul 2026:** Canva, Atlassian, Xero, Slack all domain-verify (Xero resolves to *Xero Limited* — a bare name search returns a film); **Cochlear** returns no domain match in the candidate set → correctly emits no corroboration (GLEIF alone stands).

### 8. NVD API

- **Signals:** CVEs, CVSS severity, affected version ranges.
- **Collection:** NVD REST API (API key recommended for rate).
- **Reliability:** **High** for CVE facts.
- **Limits — the important one.** Mapping CVEs to a vendor requires knowing their internal stack, which OSINT barely reveals. **Therefore scope narrowly:** use NVD to score vendors who *make software* (their product's CVE and end-of-life history), **not** as a proxy for infrastructure they merely run. Inferring "vendor is vulnerable" from a banner is speculation, and we will not do it.
- **Legal / ToS position:** **Clean with obligations.** Commercial use permitted. Without an API key, limited to posted public rate limits; higher volume requires a free registered key, which "should not be used by, or shared with, individuals or organizations other than the original requestor." **Mandatory attribution — the product must display prominently:** *"This product uses the NVD API but is not endorsed or certified by the NVD."* NIST's name may not be used to imply endorsement. **Action:** this notice is a UI requirement on the scorecard, not a footnote to add later.

### 9. CISA Known Exploited Vulnerabilities (KEV)

- **Signals:** vulnerabilities **known to be actively exploited in the wild** — a sharper signal than CVSS severity, which measures theoretical badness.
- **Collection:** public JSON feed. **Verified live 17 Jul 2026** — `catalogVersion 2026.07.16`, 1,647 vulnerabilities.
- **Reliability:** **High**, and high-signal: KEV membership means *observed exploitation*, not hypothesis.
- **Limits:** same stack-mapping limit as NVD — scope to vendor products.
- **Legal / ToS position:** feed carries **no licence field**. As a US Government work, CISA material is generally not subject to domestic copyright. **Open item:** confirm CISA's published data-licence statement rather than relying on the general rule.

### 10. GDELT

- **Signals:** adverse media, incident reporting, tone/sentiment, event coding across global news.
- **Collection:** free API / bulk files.
- **Reliability:** **Moderate.** Media reports allegations, not findings. Coverage volume tracks newsworthiness, not risk — a large consumer brand generates more coverage than a riskier obscure vendor.
- **Limits:** noisy; severe entity-resolution burden; **absence of adverse media is close to meaningless** for a small vendor. Media tone must never drive score directly without human or AI adjudication.
- **Legal / ToS position:** **The strongest licence on this list.** Verbatim: *"all datasets released by the GDELT Project are available for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind without fee."* Redistribution and rehosting expressly permitted with citation to the GDELT Project and a link to `gdeltproject.org`.
- **Why this instead of Google News:** Google News has no free official API and scraping it breaches Google's terms. GDELT delivers the same signal class with an unimpeachable licence. **This is the selection principle working as intended** — we chose the source with the better legal position, not the more familiar name.
- **Designated AI moment:** summarising which adverse-media hits *actually matter* is precisely the work a human would otherwise do by hand — the brief's own example.
- **v3.2 status change:** GDELT is now **held / `ai_adjudicated`** — it gathers candidates into the evidence store but does **not** score. The *scored* adverse-media signal moved to hard-fact regulator feeds (§10a), which report findings, not allegations, and carry no defamation exposure.

### 10a. Regulator enforcement feeds (FTC + cleared feeds) — the scored adverse-media source

- **Signals:** named enforcement actions, settlements, orders, and investigations that mention the vendor — hard facts, dated and attributed.
- **Collection:** polite `GET` of official RSS/Atom feeds; parse entries; match the vendor name/domain as a **word** (so "canva" does not fire on "canvas"). A matched item is a **review candidate** (§5.4.1 defamation control), never an auto-published verdict; no match → a clean receipt.
- **Reliability:** **High when matched** (a regulator's own publication is a fact). **Low for a clean receipt (0.4):** a feed only exposes its recent window, not a searchable history, so "no action found" is weak evidence of absence.
- **Limits — stated, not hidden:** v1 is **US-weighted**. The FTC press feed (`ftc.gov/feeds/press-release.xml`) is reachable and clean (verified live 20 Jul 2026, valid RSS with real enforcement entries). **CISA hard-blocks automated access** (Akamai anti-bot — 403 even with a browser UA; excluded on ToS grounds, and its advisories are product-vuln already covered by KEV/NVD). **OAIC and ICO publish no stable public RSS** (verified 20 Jul 2026) — AU/UK regulator feeds are a roadmap gap. The collector polls whatever cleared feeds are listed and degrades gracefully.
- **Legal / ToS position:** **Clean.** Government open data / statutory publications, published to be read and syndicated via RSS. Honour rate limits, identify our agent.

### 11. Vendor trust pages, `security.txt`, public DPAs and subprocessor lists

- **Signals:** ISO 27001 / SOC 2 claims and expiry, pen-test attestations, DPO contact, **subprocessor lists → fourth-party dependencies**, status pages, published SLAs.
- **Collection:** polite fetch of the vendor's own published pages; honour `robots.txt`.
- **Reliability:** **Low to moderate — self-reported.** This is the vendor talking about itself, i.e. the exact input the brief is trying to move away from. Treat as *claim*, not *evidence*, unless independently corroborated (e.g. certificate registry lookup).
- **Limits:** unverified claims; stale pages; absence of a trust page correlates with company size, not risk.
- **Legal / ToS position:** publicly published by the vendor for the purpose of being read. Honour `robots.txt`, identify our agent, rate-limit. Per-vendor terms must be checked for any vendor placed under recurring monitoring.
- **Why it still earns its place — the fourth-party angle.** Public DPAs list subprocessors, which yields fourth-party dependency data **for free**. This directly serves **CPS 230 ¶48** (managing risks from fourth parties a material service provider relies on) and is the one thing questionnaires are worst at surfacing. Discovering that six vendors share one subprocessor is a concentration finding a client cannot obtain any other way.
- **Designated AI moment:** classifying an unstructured trust page into structured certifications with expiry dates — the brief's other stated example.

---

## Sources requiring a decision before collection

The brief says: *"If you are unsure, ask before you collect — not after."* These two are that case. Both are Australian, both are the most locally relevant sources on the list, and **neither states a licence.**

### 6. DFAT Consolidated List (Australian sanctions)

- **Signals:** individuals, entities and vessels under Australian sanctions — targeted financial sanctions, travel bans, arms embargos.
- **Collection:** XLSX at `dfat.gov.au/sites/default/files/Australian_Sanctions_Consolidated_List.xlsx` — verified present, last updated 10 July 2026.
- **Status:** **No licence or terms of use located on the DFAT sanctions pages.** Australian Government material is *often* released under CC BY 4.0 per the Open Access and Licensing framework, **but DFAT has not stated this for this file and we will not assume it.**
- **Why it matters commercially:** dealing with a listed entity is a criminal offence (up to 10 years). The list exists to be screened against, so a use-restriction would be perverse — but "would be perverse" is not a legal position.
- **→ ACTION:** written query to the Australian Sanctions Office confirming licence terms for automated ingestion and use within a commercial screening product. **Until answered, use the ITA Consolidated Screening List as the sanctions gate and record Australian sanctions coverage as a known gap on the scorecard.**

### 12. Australian Modern Slavery Statements Register

- **Signals:** statutory modern-slavery statements under the *Modern Slavery Act 2018* (Cth) — supply-chain diligence, remediation, governance.
- **Status:** register confirmed live. Only legal statement located: **"Copyright Attorney-General's Department © 2026"** — no licence, no stated API, no stated bulk-download terms.
- **Why it matters:** free, statutory (its importance grounded in the *Modern Slavery Act 2018*, not in any demo framework), locally relevant, and an obvious *Modern Slavery & Human Rights* signal — and it is very unlikely anyone else on this project will think of it.
- **→ ACTION:** written query to the Attorney-General's Department on licence and automated access. **Held out of v1 pending reply.**

---

## Excluded sources

### VirusTotal — EXCLUDED (commercial use prohibited)

Public API terms state: **"The Public API must not be used in commercial products or services."** Also barred from use "in business workflows that do not contribute new files." Enforcement is stated as "immediate permanent ban." Free tier is 500 requests/day at 4/minute.

Since the strongest work here is a candidate for the Wahid AI platform, this is disqualifying **now**. Excluding it at the start is cheaper than discovering it at handover. Commercial licensing exists and is a paid feed — out of scope per the brief. *Note: `ref.md` lists VirusTotal without flagging this.*

### Qualys SSL Labs — EXCLUDED (four independent blockers)

The most instructive exclusion on the list. Verbatim from the Terms of Use, **"You are not allowed, without our express permission, to:"**

- *"(i) use the API for commercial purposes;"*
- *"(ii) use the API on a public web site;"*
- *"(iii) publish any information received from us via the APIs without the owner's express permission;"*
- *"(iv) distribute, proxy, or otherwise make the API available for access or use by any person or entity other than your authorized employees, including but not limited to acting as a service bureau or developing a competing product or service offering."*

And the permitted-use clause is fatal on its own: **"use the API only to inspect only sites and servers whose owners have given you permission to do so."** We are assessing vendors precisely *because* we have no relationship with them — we will never have that permission. Separately: *"Using automation to request site assessments and/or extract assessment results from HTML pages ('scraping') is expressly forbidden."*

**Any of the four kills it. The permission clause alone makes SSL Labs structurally incompatible with third-party OSINT assessment — the product's own terms forbid the use case.** We obtain the same signal by running our own TLS handshake (source 3), which is why that choice was made on legal grounds first. *Note: `ref.md` lists SSL Labs as a recommended source.*

### Shodan / Censys — ROADMAP

Free tier limits results and query types; meaningful assessment volume pushes into paid, which the brief rules out. Shodan's terms permit product integration with attribution, but academic/research access is expressly non-commercial — meaning the *free* route and the *commercial* route are not the same route. Most estate-visibility value is already obtained from Certificate Transparency at zero cost and zero ToS risk. **Documented as a future paid option per the brief's instruction to note paywalled sources and move on.**

### Google News (scraped) — EXCLUDED

No free official API; scraping breaches Google's terms. **Superseded by GDELT**, which is licensed for exactly this.

### Corporate registries — ABN Lookup (AU) CLEAR-CONDITIONAL · Companies House (UK) CLEARED · OpenCorporates UNRESOLVED

**These directly address Business & Financial Stability's recall gap** — EDGAR is US-listed only (the MYOB test). Reviewed 20 Jul 2026 against each source's *actual* terms, fetched live, not a secondary summary.

- **ABN Lookup (AU) — CLEAR-CONDITIONAL, adopt (roadmap collector).** The Web Services Agreement (`abr.business.gov.au/Tools/WebServicesAgreement`, fetched live) permits *"provide relevant extracts of the ABN Lookup Web Services to third parties"* at your own risk, sets **no commercial bar** and **no bulk-harvest bar** (we do targeted per-vendor lookups, not bulk extraction), and requires only that you **not imply Commonwealth endorsement**. Free; needs a free registration **GUID** (same identify-yourself posture as EDGAR). Authoritative for AU status (Active / Cancelled / Deregistered) — **this is the source that actually solves the MYOB test.**
- **Companies House (UK) — CLEARED, adopt (roadmap collector).** Confirmed live: data is under the **Open Government Licence** with **no commercial restriction** (*"use the data in commercial applications without licensing fees"*), free API key, **600 requests / 5 min**, attribution required. Authoritative for UK status (Active / Dissolved / Liquidation / Administration / insolvency). **Resolves the earlier "auth wall — unresolved" finding.**
- **USPTO trademarks — HELD (weak proxy).** Public-domain US-gov data (legally clean), but *"dead trademark ⇒ business closure"* is a weak inference and the named TESS interface was retired in 2023 (now Trademark Search / TSDR API). Roadmap at most; not built first.
- **OpenCorporates — UNRESOLVED.** Terms URL still 404s; not cleared, not used.

**PII discipline (all of the above):** take **entity status only** — never director/officer personal data — holding the §4.2 bright line (score entities, not natural persons). **Status (v3.2):** Business & Financial Stability is now wired to **GLEIF** (§7) — global, CC0, no auth, resolves all five test vendors. ABN Lookup + Companies House remain **roadmap enrichments** that would add a *second* authoritative source for AU/UK entities (corroboration raises confidence); they are no longer the *only* path off EDGAR.

### Data-availability re-feed candidates (v3.1 gap-closers)

The v3.1 re-tier (§5.9) held three categories for having no live collector. Reviewed 20 Jul 2026 — two have a **legally clean re-feed path**, one needing *no new external API*:

- **Supply Chain & Dependency — re-feed from ALREADY-CLEARED collectors (strongest).** Fourth-party dependency is inferable from data `dns`, `ct` and `trust` *already* retrieve: third-party infra suffixes in DNS/MX/CNAME (`amazonses.com`, `okta.com`, `cloudflare.net`), CT SAN/CNAME dependencies (`herokuapp.com`, `azurewebsites.net`), and published `/subprocessors` · `/dpa` lists. **No new clearance** — DNS/CT are facts (*IceTV*, RFC 6962), trust pages are published to be read. Build = a normalizer enhancement + a "critical third-party" dictionary. **Caveat:** gives per-vendor *enumeration*; `concentration_risk` (shared dependencies across the portfolio) still needs the portfolio view (roadmap).
- **Adverse Media — BUILT in v3.2 (regulator RSS).** The factual half of adverse media now scores via the regulator-feed collector (§10a): FTC enforcement RSS is reachable and clean (verified live 20 Jul 2026); a matched named action is a hard fact. On probing, **CISA blocks automated access** and **OAIC/ICO have no stable RSS**, so v1 is honestly US-weighted with a configurable feed list (documented, not hidden). Raw GDELT sentiment stays `ai_adjudicated`/held. Adverse Media was **promoted held → scored (6%)**. Wikidata `legal case`/`fine` (CC0) remains a patchy roadmap supplement.

**Supply Chain** remains a **roadmap build** (re-feed from already-cleared dns/ct/trust — no new clearance). **Adverse Media is done** (above). **Data Privacy & Leakage** has **no** clean free re-feed found yet (HIBP paste/domain is paid). Business & Financial Stability was **re-sourced EDGAR → GLEIF (§7)** and, in v3.3, **corroborated by a second register — Wikidata (§7b)** — domain-verified, which lifts confidence where both agree (4 of 5 test vendors); ABN Lookup + Companies House stay roadmap (both key-gated).

---

## Cross-cutting limits

These apply to the register as a whole and belong in the methodology, not in any single source row.

**Entity resolution is the hard problem, not collection.** Proving a breach, sanction or news item belongs to *this* vendor — not a homonym, subsidiary, or unrelated namesake — is where accuracy is actually won or lost. The French Compliance Society white paper flags this directly, warning about "the rate of homonymy" and false positives, and the AFA concludes that automated tooling "requires human analysis in order to adjust the assessment, particularly for the most high-risk third parties." Sanctions screening is the acute case: a false positive on a sanctions gate is a serious accusation against a real company. **Design consequence:** sanctions hits must surface as *review items with evidence*, never as silent automated score changes.

**Absence of evidence is not evidence of absence.** No breach record, no adverse media and no SEC filing are the *default* state of a small private vendor with a clean public footprint — and also of a badly-run one nobody has written about yet. **Design consequence:** missing data must reduce *confidence*, never reduce *risk*. Any model where a vendor scores well by being invisible is broken, and this is the most likely way a naive implementation fails.

**Public data is stale and patchy.** NIST SP 1326 gives us the four variables to weigh per finding — **age of the information, frequency of occurrence, severity, and mitigations in place** — which is effectively a decay-and-context model handed over by a US federal publication. Adopt it, and cite it.

**Regulator warning against bought scores — the argument for this project.** The AFA "warns about the automatic rating systems provided by digital solutions, specifying that users must be able to determine their own rating system with regard to risk mapping." A regulator is on record saying black-box vendor scores are not defensible and that you must own your model. **This is the brief's thesis, independently confirmed by a regulator, and it belongs in the methodology's opening argument.**

**Data egress — the optional LLM summariser.** The only component that sends data to a third party *not* on the source register is the opt-in evidence summariser (`app/summariser.py`, methodology "the AI moment"). It is off by default (no `TPRM_LLM_*` env → the endpoint returns 503) and, when on, is provider-agnostic over any OpenAI-compatible `chat/completions` host the operator chooses (OpenRouter, Groq, Google's OpenAI-compat surface). What leaves the system is the finished **record** — the score roll-up **plus the actual hash-stamped observations each source returned** (so the digest is about *what was found*, not a restatement of the numbers). This is deliberately **bounded** (per-receipt and total caps, test-enforced: `test_context_is_bounded_per_receipt`) and it is **only the already-collected, lawfully-public OSINT the system already holds** — PII is minimised at *collection* (entity-level / role addresses only), so the summariser exposes nothing the collectors did not already lawfully retain. The summary is a read layer: it never computes or alters a score, never writes to the immutable evidence store, is returned marked AI-generated, and cites the `content_hash`es it was built from so a reviewer can verify it against the receipts. **Design consequence:** an operator turning this on chooses their own LLM provider and inherits *that* provider's data-handling terms for the entity-level evidence described above — a deliberate, documented, single egress point, not a hidden dependency.

---

## Coverage against the scoring model

Mapping the cleared sources against NIST SP 1326's five due-diligence categories shows where v1 is strong and where it is honestly thin:

| NIST SP 1326 category | Covered by | Strength |
|---|---|---|
| Foundational Cyber Practices (supplier) | CT, DNS, TLS/headers, HIBP | **Strong** |
| Foundational Cyber Practices (product) | NVD, KEV | Moderate — vendor-products only |
| Resilience | GLEIF (entity standing), regulator RSS, HIBP | Moderate — standing not financials |
| Supply Chain Tiers (fourth party) | Subprocessor lists | Moderate — self-reported |
| FOCI / Provenance | *(registries — unresolved)* | **Weak — v1 gap** |

**FOCI and Provenance are the honest gap in v1**, pending resolution of ASIC / Companies House / OpenCorporates. This is stated rather than papered over, per the brief's instruction to be honest about confidence.

**Note on what OSINT cannot reach.** Taking the ~27 criteria in `an_example_risk_scoring_System.md` (an illustrative demo template, **not authoritative** — used here only as a rough criteria inventory) as a checklist: roughly 7 are observable from public data, ~10 are partially observable via proxy, and ~10 (access controls, security monitoring, data handling, insurance, change management, contract terms) are invisible to any lawful external observer. **No source register can close that gap** — it is a property of the problem, not of the sourcing. The product implication: OSINT does not replace the questionnaire framework; it pre-fills the fraction it can evidence independently and **flags contradictions** where a vendor's self-assessment disagrees with the public record.

---

## Open items

1. **DFAT** — written query to the Australian Sanctions Office on licence terms. *(blocking AU sanctions coverage)*
2. **Modern Slavery Register** — written query to the Attorney-General's Department. *(blocking ESG dimension)*
3. **CISA KEV** — confirm published data-licence statement rather than relying on the general US Gov rule.
4. **ASIC / OpenCorporates** — resolve terms. *(blocking FOCI + Provenance)* — **Companies House RESOLVED (cleared, OGL) and ABN Lookup CLEAR-CONDITIONAL (both 20 Jul 2026); build as Business-Stability collectors, roadmap.**
5. **crt.sh** — accept the low residual risk of an unstated-terms index. **Cert Spotter fallback added (20 Jul 2026)** for crt.sh's frequent outages; production use of Cert Spotter should move to a free SSLMate account per their tiering (evaluation-cleared for the PoC).
6. **Per-vendor `robots.txt`** — must be checked per test vendor before trust-page collection.
7. **Active-exposure / reputation candidates — VERIFY BEFORE CLEARING.** To close the "no live blocklist / open-port" gap (methodology §5.10 Roadmap #1) *without* the Shodan/Censys free tier — whose commercial-use bar disqualifies it for a commercial-platform candidate (Censys ToS verified 20 Jul 2026: *"Censys Free Customers… are expressly prohibited from using the Service and Censys Data for commercial purposes of any kind"* — the VirusTotal trap). Candidates proposed with **unverified** commercial-use claims, each needing the live-ToS treatment before use: **URLScan.io**, **OpenPhish**, **PhishStats**, **AlienVault OTX**, **AbuseIPDB**, **GreyNoise Community** (community tiers of the latter two are often non-commercial — check). **None cleared. Do not integrate on a secondary claim.**

## Verification log

| Source | Method | Result | Date |
|---|---|---|---|
| crt.sh | live fetch | No ToS/AUP found; Sectigo operates | 17 Jul 2026 |
| HIBP | live fetch of `/API/v3` | CC BY 4.0; `/breaches` unauthenticated | 17 Jul 2026 |
| GDELT | live fetch of `/about.html` | Unrestricted commercial use confirmed | 17 Jul 2026 |
| NVD | live fetch of ToS page | Commercial OK; attribution notice mandatory | 17 Jul 2026 |
| CISA KEV | live fetch of JSON feed | v2026.07.16, 1,647 CVEs, no licence field | 17 Jul 2026 |
| ITA CSL | live fetch | Free API; no restriction stated | 17 Jul 2026 |
| SEC EDGAR | live fetch → **403** | UA + 10 req/s enforcement confirmed → **REMOVED (→ GLEIF)** | 17 Jul 2026 |
| **GLEIF (LEI)** | live API + terms fetch | **CC0/public domain, commercial OK, no auth; all 5 vendors resolve** | 20 Jul 2026 |
| **Cert Spotter (SSLMate)** | live API + ToS fetch | 200 in ~2s; ToS bars no commercial/automated use; free tier = eval | 20 Jul 2026 |
| **FTC enforcement RSS** | live fetch | Valid RSS, real enforcement entries; gov open data | 20 Jul 2026 |
| CISA feeds | live fetch (browser UA) | **403 — anti-bot; excluded** for automated adverse-media | 20 Jul 2026 |
| OAIC / ICO RSS | search + probe | **No stable public RSS found** — AU/UK feed gap | 20 Jul 2026 |
| DFAT | live fetch + search | XLSX confirmed; **no licence found** | 17 Jul 2026 |
| Modern Slavery Register | live fetch | Copyright notice only; **no licence** | 17 Jul 2026 |
| VirusTotal | ToS lookup | Commercial use prohibited | 17 Jul 2026 |
| SSL Labs | ToS PDF, extracted | 4 blocking clauses quoted | 17 Jul 2026 |
| Shodan | ToS lookup | Free tier limited; non-commercial research tier | 17 Jul 2026 |
| OpenCorporates | live fetch → 404 | Unresolved | 17 Jul 2026 |
| Companies House | OGL confirmed — commercial OK, free key, 600/5min | **Cleared** | 20 Jul 2026 |
| ABN Lookup (AU) | Web Services Agreement fetched — 3rd-party extracts OK, GUID required | **Clear-conditional** | 20 Jul 2026 |

---

## References

- NIST SP 1326, *C-SCRM Due Diligence Assessment Quick-Start Guide* (July 2026) — `docs/NIST.SP.1326.pdf`
- APRA *Prudential Standard CPS 230 Operational Risk Management* (July 2025) — `docs/Prudential+Standard+CPS+230...pdf`
- French Compliance Society, *From Third Party Assessment to Third Party Risk Management* — `docs/TPRM_digital_version_anglaise.pdf`
- ISO/IEC 27001:2022, Annex A controls 5.19–5.23 (supplier relationships) — `docs/ISO_IEC-270012022-ed.3.pdf`
- Have I Been Pwned API v3 — https://haveibeenpwned.com/API/v3
- GDELT Project — https://www.gdeltproject.org/about.html
- NVD API Terms of Use — https://nvd.nist.gov/developers/terms-of-use
- CISA KEV Catalog — https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- ITA Consolidated Screening List — https://www.trade.gov/consolidated-screening-list
- DFAT Consolidated List — https://www.dfat.gov.au/international-relations/security/sanctions/consolidated-list
- GLEIF Open Data / LEI Data Terms of Use (CC0) — https://www.gleif.org/en/about/open-data · https://www.gleif.org/en/meta/lei-data-terms-of-use
- SSLMate Cert Spotter CT Search API + ToS — https://sslmate.com/ct_search_api/ · https://sslmate.com/policies/tos
- FTC press-release RSS — https://www.ftc.gov/feeds/press-release.xml
- SEC EDGAR access policy *(source removed v3.2 — retained for provenance)* — https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Qualys SSL Labs Terms of Use — https://www.ssllabs.com/downloads/Qualys_SSL_Labs_Terms_of_Use.pdf
- VirusTotal API — https://docs.virustotal.com/reference/public-vs-premium-api
- Shodan Terms of Service — https://static.shodan.io/legal/terms.html

*Attribution obligations carried into the product: HIBP (CC BY 4.0 + link), GDELT (citation + link), NVD (verbatim non-endorsement notice).*
