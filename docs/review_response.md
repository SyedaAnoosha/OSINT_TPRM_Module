# Review Response — nine points, answered against the built system

**Status:** review response · v1 · against methodology v1 / scoring model **v4.2.0** / 14 collectors
**Date:** 24 July 2026
**Companions:** [`methodology.md`](methodology.md) · [`scoring.yaml`](../WahidAI/OSINT_TPRM/scoring.yaml) · [`roadmap.md`](roadmap.md) · [`source_assessment.md`](source_assessment.md)

> **What this document is.** A point-by-point answer to nine reviewer comments. For each: what the
> reviewer asked, **where the system actually stands today** (with file references, not claims), the
> design, and an explicit split between **doable now**, **designed**, and **future work**.
>
> **Where I disagree, I say so.** Two of the nine suggestions, taken literally, would break load-bearing
> commitments in the existing methodology — §1 (adding commercial feeds) and §5 (industry weighting).
> Both are right in intent. Both need a different mechanism than the obvious one. Those sections carry
> the argument rather than a shopping list.

---

## Contents

| # | Point | Verdict | Where it lands |
|---|---|---|---|
| 1 | Perfect vs doable methodology | **Accepted, reframed** | New §11 of `methodology.md` |
| 2 | Company size, revenue, industry | **Accepted — real gap** | New collector + `VendorProfile` block |
| 3 | Big vs small companies | **Accepted** | Peer-cohort definition; needs portfolio |
| 4 | Australian sources | **Accepted — partially already done** | `source_assessment.md` register |
| 5 | Benchmark by industry | **Accepted, mechanism changed** | Expected-band + severity profile, **not weights** |
| 6 | Procurement teams | **Accepted** | Value-proposition section |
| 7 | Fourth-party risk | **Already designed, not built** | `roadmap.md` §2.2 — unblocked today |
| 8 | User perspective | **Accepted — real gap** | Persona → surface mapping |
| 9 | So what? Now what? | **Accepted — the sharpest point** | Action layer on every finding |

---

# 1. Perfect methodology vs doable methodology

## 1.1 What the reviewer asked

> *"If money wasn't a limitation, what would the ideal methodology look like?"*

Fair question, and the honest answer has two halves — the sources I would add, and the thing I would
**refuse to add even with an unlimited budget**, because it would cost more than it bought.

## 1.2 Tier 0 — what runs today (the doable methodology)

Free, no-auth or free-key, commercial-use-cleared. **14 failure-isolated collectors, 26 signals,
7 scoring categories**, every source individually assessed in [`source_assessment.md`](source_assessment.md).

| Domain | Sources in production |
|---|---|
| Cyber hygiene | Certificate Transparency (crt.sh + Cert Spotter fallback) · DNS (SPF/DKIM/DMARC/MX/CAA/DNSSEC) · self-run TLS handshake · HTTP security headers · `security.txt` |
| Breach & vulnerability | Have I Been Pwned · CISA KEV · NVD (+ EPSS) |
| Entity & standing | GLEIF (LEI) · Wikidata (CC0, domain-verified) · RDAP |
| Sanctions (gate) | ITA Consolidated Screening List |
| Adverse media | Regulator RSS (FTC + cleared feeds) · GDELT *(candidates, held)* |
| Transparency | Trust centres · published DPAs / subprocessor lists |

**Strengths:** ~A$0 marginal cost per assessment · every score reconstructible from a hash-stamped,
append-only evidence store · no ToS trap · legally usable in a commercial product.

**Limits — stated in [`methodology.md`](methodology.md) §7.1, not discovered later:**
perimeter ≠ posture · ~10 of ~27 due-diligence criteria are invisible to *any* lawful external
observer · absence of evidence is the default state of a clean small vendor *and* a badly-run obscure
one · no active scanning, so no open-port or exposed-service visibility.

## 1.3 Tier 1 — the cheap wins (free key, weeks of work, no budget line)

Worth separating out, because "perfect vs doable" hides a large middle. **These cost nothing but a
registration and clear the project's own legality bar today:**

| Source | Adds | Status |
|---|---|---|
| **Companies House (UK)** | Authoritative UK entity standing + ownership chain | **CLEARED** (OGL, commercial-OK, free key, 600/5min) |
| **ABN Lookup (AU)** | Authoritative AU entity status — solves the MYOB case | **CLEAR-CONDITIONAL** (free GUID) |
| **AlienVault OTX passive DNS** | CT redundancy — removes the single point of failure on Digital Footprint | Cleared pending free key |
| **Cert Spotter token** | Raises the CT rate limit in production | Free key |
| **DFAT Consolidated List** | **Australian** sanctions in the gate | **Held — licence query pending** |
| **AU Modern Slavery Register** | Opens the ESG category | **Held — licence query pending** |

Two of these are *blocking* rather than nice-to-have: the sanctions gate currently runs on a **US list
only**, which is a coverage gap on an Australian product, and it is blocked on a written licence
reply, not on money.

## 1.4 Tier 2 — the perfect methodology (unlimited budget)

Adopting the reviewer's categories, with what each actually buys and what it costs the methodology:

| Layer | Vendors | What it genuinely adds | Cost to the model |
|---|---|---|---|
| **Attack surface** | Censys, Shodan, BinaryEdge, RiskIQ | **The single biggest gap** — open ports, exposed RDP/SMB/databases, service banners, IP-level estate. This is the one thing no free lawful source substitutes for | Low — raw observations, not opinions |
| **Dark web / credential** | SpyCloud, Constella, KELA | Infostealer logs, combolists, initial-access-broker chatter — closes the HIBP recall gap that Snowflake demonstrates live (§2.3) | Medium — sourcing is opaque; provenance must be demanded contractually |
| **Threat intelligence** | Recorded Future, Mandiant, CrowdStrike, Flashpoint, Microsoft Defender TI | Targeting context — *is this vendor's sector being actively hit* | **High** — see §1.5 |
| **Business & financial** | D&B, Moody's, S&P Capital IQ | The half of Business Stability we openly cannot see: distress, litigation, credit deterioration, private-company financials | Low — facts with methodology published |
| **Supply chain** | Interos, Prevalent, Panorays | Pre-mapped n-th party graphs | **High** — this is buying the answer, not the evidence |
| **Compliance / GRC** | OneTrust, AuditBoard | Questionnaire workflow, control mapping, attestation storage | Low — it is the *other* half of the platform, not a rival |

**Indicative budget** — order of magnitude only, confirm against quotes; enterprise pricing is
negotiated and rarely listed. A full stack of the above sits in the **six figures annually (AUD)**,
dominated by threat intel and supply-chain graph licences. Attack-surface and business-data tiers are
materially cheaper than the TI tier and buy more per dollar *for this use case*.

## 1.5 The disagreement — a bought score is not a better methodology

The reviewer's framing is that money buys a 360-degree assessment. Mostly true. But the project's
first thesis, in [`methodology.md`](methodology.md) §1, is a regulator (the AFA) on record warning
against exactly the thing an unlimited budget tempts you into:

> *"users must be able to determine their own rating system with regard to risk mapping."*

And **Finding A** (`ABN AMRO v Bathurst Regional Council` [2014] FCAFC 65) means publishing a score
carries an implied representation that it was formed on **reasonable grounds** — a duty owed with no
contract in place. *"The vendor's model said 62"* is not reasonable grounds.

So the rule that governs the perfect methodology is the same one that governs the doable one:

> **Buy observations, never verdicts.** A commercial feed enters as **evidence** — a hash-stamped
> observation with a source, a timestamp and a severity we assign under our own published bands. A
> commercial feed never enters as a **score**, a weight, or a black-box grade we resell.

Concretely, in tier order of what I would actually buy first:

1. **Censys / Shodan enterprise** — raw observations (port 3389 open on `x.vendor.com`, seen
   2026-07-20). Drops straight into the existing penalty model as new signals with new bands. **Highest
   value per dollar, lowest cost to defensibility.** This is Roadmap Priority #1 in `additions.md` and I
   agree with that ranking.
2. **D&B / Moody's** — closes the honest hole in Business & Financial Stability (§7.2: *"entity
   standing, not financials"*). Published methodology, so it survives a Finding A challenge.
3. **SpyCloud / Constella** — closes the HIBP recall gap, with a contractual demand for provenance on
   every record before a single one is allowed to penalise a vendor.
4. **Threat intelligence — last, and fenced.** Recorded Future's risk score would be displayed as a
   *third-party opinion beside ours*, never merged into ours. Sector-targeting context is real value;
   an imported number is a liability.
5. **Interos / Prevalent — probably never as a scoring input.** Buying a pre-computed n-th party graph
   makes the concentration finding unreconstructible, which is precisely what §2.2 of the roadmap says
   a client *cannot get anywhere else* from us. Buy it as a cross-check, not as the answer.

**The two axes survive the upgrade.** More money raises **confidence** (coverage) far more than it
changes **posture** — which is the model working as designed. A vendor that reads as *The Ghost* on
free sources and stays a Ghost after A$200k of feeds is telling you something real.

## 1.6 What changes

| Action | When |
|---|---|
| Add **§11 "Methodology under different budget constraints"** to `methodology.md` — tiers 0/1/2 and the buy-observations-never-verdicts rule | **Now** — documentation only |
| Chase the two licence replies (DFAT, Modern Slavery) and register the three free keys | **Now** — 0–1 month, `roadmap.md` §2.4 |
| Design the attack-surface signal bands (open port / exposed service severity ladder) *before* any licence exists, so procurement is a config change not a redesign | **Designed** |
| Commercial feeds | **Future work** — explicitly scoped as tier 2 in the roadmap |

---

# 2. Company size, revenue, industry — a real gap

## 2.1 Current state: confirmed missing

Verified against the code, not assumed: `backend/app/models.py` and the collector set carry **no
industry, size, revenue, employee-count or ownership field**. A grep for `industry|sector|revenue|
employee|anzsic|naics` across `backend/app/` returns nothing but false positives. The reviewer is
right, and it is a gap with consequences beyond presentation — **points 3 and 5 are both unbuildable
without it**, because you cannot pick a peer group or an industry profile for a vendor you have not
classified.

## 2.2 The design — a `VendorProfile` block, rendered before the score

Every scorecard opens with context, then the score. Every field carries its own **source and
`fetched_at`**, the same discipline as every other observation:

| Field | Primary source | Fallback | Availability |
|---|---|---|---|
| Legal name | GLEIF | Wikidata, RDAP | High |
| Country / jurisdiction | GLEIF (legal address) | Wikidata P17 | High |
| Industry / sector | Wikidata P452 (industry) | ANZSIC via ABN Lookup (AU), SIC via Companies House (UK) | **Medium** |
| Employees | Wikidata P1128 | Company filings | **Low** |
| Revenue | Wikidata P2139 | SEC EDGAR / ASX / Companies House filings | **Low — listed companies only** |
| Public / private | Wikidata P414 (stock exchange) + GLEIF | — | Medium |
| Entity status | GLEIF · ABN Lookup · Companies House | Wikidata P576 | High |
| Domain age | RDAP (already collected) | CT first-seen | High |
| **Criticality** | **Client input — never inferred** | — | n/a |

**Three rules that keep this from breaking the model:**

1. **Firmographics are context, never score inputs.** They set the *peer group* (§3) and the *industry
   profile* (§5). They never add or remove a penalty directly. The moment revenue moves a score, the
   size bias named in §7.3 — *"coverage tracks company size, not company risk"* — re-enters through the
   front door.
2. **Missing firmographics reduce confidence in the comparison, never the posture.** Same rule as every
   other source. An unclassified vendor gets an absolute grade and **no peer percentile** — not a
   guessed one.
3. **Criticality is the client's, not ours.** How badly this vendor's failure hurts *you* is not
   observable from outside and must never be inferred. It is a one-field input on the scoring request,
   and it drives the recommendation in §9 — not the score.

**Entity-level only.** Directors, officers and beneficial owners who are natural persons stay excluded
at the §4.2 bright line. Industry and size are entity attributes; the people are not.

## 2.3 Worked example (the reviewer's own illustration)

```
┌─ Microsoft Corporation ─────────────────────── microsoft.com ─┐
│  Industry     Technology — packaged software    [Wikidata P452]│
│  Revenue      ~US$250B                          [EDGAR 10-K]   │
│  Employees    ~230,000                          [Wikidata P1128]│
│  Country      United States                     [GLEIF]        │
│  Ownership    Public (NASDAQ: MSFT)             [Wikidata P414]│
│  Criticality  High                              [client input] │
│  Peer cohort  Technology · Mega-enterprise · North America     │
├────────────────────────────────────────────────────────────────┤
│  Posture 88 (A)          Confidence 0.94        Evidenced clean │
│  vs cohort: median 84 · n=31 · 68th percentile                  │
└────────────────────────────────────────────────────────────────┘
```

The peer line is what points 3 and 5 need, and it is the part that requires a portfolio (§3.4).

## 2.4 What changes

| Action | When |
|---|---|
| **`firmographics` collector** — Wikidata P452/P1128/P2139/P414/P17 + GLEIF jurisdiction, all CC0/free, all already-cleared sources. No new legal clearance required | **Doable now** — ~1 collector, the Wikidata client already exists |
| `VendorProfile` in `models.py`, persisted with the evidence record, rendered at the top of `Scorecard.jsx` | **Doable now** |
| `criticality` as an optional field on `POST /api/vendors/score` | **Doable now** |
| ANZSIC (ABN Lookup) / SIC (Companies House) classification | **0–1 month** — rides on the tier-1 keyed collectors |
| Revenue for private companies | **Future work** — no free source; tier 2 (D&B) |

---

# 3. Bigger companies vs smaller companies — compare peers, never absolutes

## 3.1 The reviewer is right, and the methodology already half-admits it

§7.3 already names the bias in plain terms: *"Coverage tracks company size, not company risk. A large
consumer brand generates more breach records, more adverse media and more filings than a smaller,
riskier vendor. Naively, the model would score big vendors as riskier because more is known about
them."* The stated mitigation is the confidence axis — *"a mitigation, not a cure."*

The peer cohort is the missing other half of that cure.

## 3.2 The cohort key

```
peer_cohort = industry × size_band × region   [ × ownership, optional ]
```

| Dimension | Bands |
|---|---|
| **Industry** | ANZSIC division (AU-native) mapped to ~12 working sectors — financial, health, telco, cloud/SaaS, government, education, retail, manufacturing, food, agriculture, professional services, logistics |
| **Size** | Micro (<20) · Small (20–199) · Medium (200–999) · Large (1,000–9,999) · Mega (10,000+) — employee bands, ABS-aligned, with revenue as fallback |
| **Region** | ANZ · North America · UK/EU · APAC (ex-ANZ) · Other — regulatory regime, not geography |
| **Ownership** | Listed · Private · PE/VC-backed · Government · Not-for-profit |

Google and a local bakery never meet. `Technology · Mega · North America` and
`Food · Small · ANZ` are different populations with different expected postures, different observable
surface areas, and different regulatory pressure.

## 3.3 The rules that stop this becoming a lie

1. **Absolute grade is always published.** The cohort percentile is an *overlay*, never a replacement.
   A vendor with an expired production certificate is Grade D whether or not its peers are worse.
2. **Minimum cohort size before any percentile is shown.** Below **n = 8**, publish
   *"insufficient peers"* — a percentile computed on three vendors is noise dressed as precision, and
   that is the false precision Finding A punishes.
3. **Never relax the ceiling for a cohort.** The critical ceiling (`scoring.yaml` → `critical_ceiling`)
   and the sanctions gate are absolute. "Bad for a bakery" is still bad.
4. **The cohort is disclosed on the card** — which industry, which size band, which region, and **n**.
   A comparison whose population is hidden is a bought black-box score with extra steps.

## 3.4 What changes

| Action | When |
|---|---|
| Cohort key computed and displayed from `VendorProfile` (§2) — labels the vendor even with n=1 | **Doable now**, once §2 lands |
| Percentile / median / distribution against the cohort | **Future work — needs the portfolio view.** v1 scores one vendor at a time; a cohort needs a population. This is `roadmap.md` §5 ("Portfolio view"), 3–6 months, blocked on platform integration — not on method |
| Seed cohorts from the frozen 5-vendor corpus for demonstration, clearly marked n=5 and **not** published as a percentile | **Doable now** — demonstrates the mechanism honestly |

---

# 4. Australian sources — expand beyond the US-centric model

## 4.1 Current state

The register is **honestly US-weighted and says so** (§7.2). AU-specific work already done: DFAT and
the Modern Slavery Register are **held pending written licence queries** (the brief's *"ask before you
collect"*), ABN Lookup is **CLEAR-CONDITIONAL**, and OAIC/ACCC/ASIC were **probed and found to publish
no stable RSS** (`source_assessment.md`, verified 20–21 Jul 2026) — a documented gap, not a silent one.

## 4.2 The AU register — what exists, searched 24 July 2026

Each still requires the project's own clearance pass (licence · commercial use · automated access)
before ingestion. Located ≠ cleared.

| Source | What it gives TPRM | Access | Status |
|---|---|---|---|
| **ABN Lookup / ABR** ([abr.business.gov.au](https://abr.business.gov.au/Tools/WebServicesAgreement)) | ABN status (Active/Cancelled), entity type, ANZSIC industry code, GST registration, trading names | Free web services, registration GUID | **CLEAR-CONDITIONAL — build now** |
| **ASIC registers** ([asic.gov.au](https://www.asic.gov.au/online-services/search-asic-registers/company-and-organisation-registers/)) | ACN, company status, type/class, registration date, former names, deregistrations | Free unauthenticated Connect search; bulk extracts are paid; a company dataset is published on data.gov.au | **Terms unresolved — open item 7** |
| **ACNC Charity Register** ([data.gov.au](https://data.gov.au/data/dataset/acnc-register)) | ~60k not-for-profit entities: status, size band, ABN, operating jurisdictions, annual information statements | **Free weekly CSV/XLSX on data.gov.au** | **Strong candidate — likely CC BY, verify** |
| **OAIC Notifiable Data Breaches** ([oaic.gov.au](https://www.oaic.gov.au/privacy/notifiable-data-breaches/notifiable-data-breach-statistics-dashboard)) | **Sector-level breach base rates** (1,205 notifications in CY2025; health 19%), twice-yearly reports + dashboard | Free publications | **Feeds §5 benchmarks, not per-vendor scoring** — the scheme does not publish entity names |
| **DFAT Consolidated List** | Australian sanctions — the gate's missing half | XLSX, no licence stated | **HELD — licence query pending (open item 1)** |
| **AU Modern Slavery Register** | Statutory supply-chain statements — opens ESG | Free, copyright notice only | **HELD — licence query pending (open item 2)** |
| **auDA / .au WHOIS** ([auda.org.au](https://www.auda.org.au/au-domain-names/au-rules-and-policies/au-domain-administration-rules-licensing-2/)) | **`.au` requires a validated Australian presence** — a registered ABN/ACN/trademark. A `.au` domain is therefore itself an entity-existence signal, and registrant eligibility data is public | Public WHOIS, rate-limited | **Genuinely novel — worth a clearance pass** |
| **AusTender** | Australian Government contract awards — a direct read on whether a vendor is trusted with public-sector work, and at what value | Free | Candidate |
| **APRA registers** | Authorised deposit-taking institutions, insurers, RSE licensees — regulated-status verification for financial vendors | Free | Candidate — pairs with §5's financial profile |
| **ASX announcements** | Continuous-disclosure obligations: material incidents, breaches, financial distress for listed AU vendors | Free per-company | Candidate |

**The OAIC entry is the quiet win.** It cannot score a vendor — the NDB scheme publishes statistics,
not entity names — but its **sector breakdown is a published Australian regulator's answer to "which
industries actually get breached"**, which is exactly the evidence §5 needs and which the reviewer's
suggested thresholds currently lack.

## 4.3 Expanding globally — the shape, not a list

The correct fix is not "add AU sources" but **a registry adapter behind one interface**, selected by
the vendor's jurisdiction from §2's `VendorProfile`:

```
jurisdiction → registry adapter → common EntityStanding finding
   AU  → ABN Lookup / ASIC          UK → Companies House (CLEARED)
   US  → SEC EDGAR / state SoS      NZ → Companies Office
   SG  → ACRA                       CA → Corporations Canada
   EU  → BRIS / national registers   *  → GLEIF (global fallback, in production)
```

GLEIF already plays the global fallback role and resolves all five test vendors. Each national adapter
adds **authoritative corroboration** in its own jurisdiction, which raises confidence via the existing
noisy-OR corroboration mechanism (§5.4.3) — no model change, just more evidence.

## 4.4 What changes

| Action | When |
|---|---|
| Escalate the two licence queries — the AU sanctions gap is the single most locally-embarrassing hole | **Now** |
| Build **ABN Lookup** as a keyed Business Stability collector; it also supplies **ANZSIC industry** for §2 and §3 — one build, three points answered | **0–1 month** |
| Clearance pass on **ACNC** (data.gov.au) and **auDA WHOIS** | **0–1 month** |
| Ingest **OAIC NDB sector statistics** as the empirical basis for industry benchmarks | **0–1 month**, feeds §5 |
| Registry adapter interface + Companies House (already cleared) | **0–1 month** |
| AusTender · APRA registers · ASX announcements | **Future work** |

---

# 5. Benchmark by industry — right question, wrong mechanism

## 5.1 Where I disagree — and why it matters

The reviewer's principle is correct and I accept it fully: **a clean score means different things in
different industries; don't compare banks with restaurants.** The proposed mechanism — raise the
weights for high-risk industries — cannot be adopted as written, for a reason internal to the model:

**There are no category weights to raise.** `scoring.yaml` v4.2.0 is a **penalty-subtractive** model.
It was rebased away from weighted-mean scoring precisely because *"no authority publishes vendor-risk
category weights"* and any set of them was a standing liability with no anchor (§5.6). Three open items
dissolved when the weights did. Reintroducing weights per industry would reintroduce all of it —
and multiply it by twelve sectors, each needing its own defence.

The reviewer's example thresholds have the same problem in a second place: **Financial 95+, Retail 70,
Agriculture 65** are asserted numbers with no published authority behind them. If we cannot defend
"Cyber Hygiene = 24%", we cannot defend "Agriculture should score 65" either.

So: keep the intent, change the mechanism. **Two levers, both of which live inside the penalty model.**

## 5.2 Lever A — the expected-posture band (interpretation, not scoring)

The **score stays absolute and cross-comparable**. What becomes industry-relative is the *reading* of it:

```
Posture 78 (B)   ·   Confidence 0.91
Cohort: Financial services · Large · ANZ
Expected for cohort: 88   →   10 below expectation   ⚑ below par for a regulated financial vendor
```

Same 78 in `Agriculture · Small · ANZ` against an expected 68 reads **10 above expectation**. One
number, two honest readings, and the arithmetic is untouched — which means the frozen regression
corpus still holds and no client's historical score silently moves.

**Where the expected band comes from — in order of preference:**

1. **Observed cohort medians**, once the portfolio exists (§3.4). Empirical, defensible, self-updating.
2. **Regulator-published sector evidence** in the interim — the OAIC NDB sector breakdown (§4.2) is a
   real Australian regulator's data on which sectors actually get breached.
3. **A client-set risk appetite**, declared in config, if they want neither. Per the AFA, this must be
   the user's decision to make anyway.

**What it is not:** a number I invent and print. Until (1) or (2) is populated, the field reads
*"no cohort baseline"* rather than showing a fabricated expectation.

## 5.3 Lever B — the industry severity profile (scoring, but one lever, declared)

The reviewer's stronger claim is real: *"a missing DMARC record is a critical failure"* for a bank and
a hygiene item for a farm supplier. That claim can be honoured **without weights**, because the penalty
model has exactly one points table — `severity_penalties` — and signals map to it by band.

An industry profile is therefore a **small, explicit, capped set of severity promotions**:

```yaml
industry_profiles:
  financial_services:
    basis: "APRA CPS 234 · CPS 230 · AFSL obligations"
    promote:
      dmarc.absent:        high     -> critical    # BEC is the sector's dominant fraud loss
      cert_validity.expiring_lt_30d: medium -> high
      cert_posture.none_claimed:     medium -> high
  healthcare:
    basis: "Privacy Act APP 11 · My Health Records Act · OAIC NDB: health = 19% of CY2025 notifications"
    promote:
      breach_by_data_class.personal_info: high -> critical
      dmarc.absent:                       high -> critical
  critical_infrastructure:
    basis: "SOCI Act · Enhanced CIRMP Rules 2026"
    promote:
      kev_listed_cve.listed: critical -> critical   # already max; ceiling applies instead
      program_disclosure.none: medium -> high
```

**Five constraints, all enforceable at load time by the existing config drift guard:**

1. **Promotion only, never demotion.** No industry makes a real weakness cheaper. A "low-risk" industry
   gets the *base* profile — the reviewer's point about food retail is served by lever A (a lower
   expected band), not by discounting its penalties.
2. **Every profile cites a named instrument** in `basis:` — CPS 234, SOCI, APP 11, PCI DSS. A profile
   with no legal or regulator-published anchor does not ship. This is the discipline that survived the
   weights being deleted.
3. **Capped at one severity step** per signal, and a maximum number of promotions per profile — so a
   profile cannot become a shadow weighting scheme.
4. **Declared on the scorecard.** "Scored under the *Financial Services* profile — 3 severities
   promoted, see basis" — with a link. The client can turn it off; per the AFA, the rating system is
   theirs to determine.
5. **Corpus-guarded.** Every profile is regression-tested against the frozen 5-vendor fixtures, so
   adding one shows up as a reviewable diff naming the vendor and category that moved.

## 5.4 Why lever B is legitimate where weights were not

| | Category weights (rejected) | Industry severity profile (proposed) |
|---|---|---|
| What it asserts | "Cyber hygiene is 24% of risk" | "For a bank, spoofable email is a critical failure" |
| Anchor available | **None** — no authority publishes them | **Yes** — CPS 234, SOCI, APP 11, PCI DSS name the obligation |
| Number of judgement calls | 7–9 percentages that must sum to 100, per industry | A short list of named promotions |
| Failure mode | Silent, diffuse, unfalsifiable | Visible, itemised, contestable per line |
| Client override | Requires rebalancing the whole vector | Turn the profile off, or edit one line |

## 5.5 What changes

| Action | When |
|---|---|
| Add `industry_profiles` to `scoring.yaml` with **two** profiles only — `financial_services` and `healthcare`, the two with the clearest AU statutory anchors | **Doable now** — the config drift guard and corpus already exist to keep it honest |
| Expected-band field in the API and on the card, rendering *"no cohort baseline"* until populated | **Doable now** |
| Populate expected bands from OAIC NDB sector data | **0–1 month** (§4.4) |
| Populate expected bands from observed cohort medians | **Future work** — needs the portfolio (§3.4) |
| The remaining ten sector profiles | **Future work** — one at a time, each with a cited basis, never a batch of twelve invented at once |

---

# 6. Procurement teams — why anyone uses this

## 6.1 The problem, quantified

Today's third-party assessment is a questionnaire round-trip: a 200–300 question spreadsheet, two to
six weeks of chasing, and answers that are **self-reported and unverified** at the end of it. The
market failure is documented, not asserted: **DORA's dry run found only 6.5% of ~1,000 EU firms passed
all data-quality checks**, most commonly failing on **missing subcontractor information**
(`methodology.md` §8.3).

## 6.2 The change

| | Today | With this system |
|---|---|---|
| Input | 300-question spreadsheet | A domain |
| Elapsed time | 2–6 weeks | **Minutes** — collectors run in parallel, results stream in |
| Evidence | Vendor's own claims | 26 signals from 14 independent public sources |
| Verifiability | Trust the response | Every deduction traces to a hash-stamped receipt |
| Reproducibility | None | Re-runnable; drift is provable, not asserted |
| Cost per vendor | Analyst-days | ~A$0 marginal |
| Coverage | Everything asked | **~7 of ~27 criteria independently evidenced** |

That last row is the honest one, and it is the load-bearing part of the pitch — see §6.4.

## 6.3 The flow, as a procurement lead experiences it

```
Enter domain  →  evidence collected (parallel, streaming)  →  posture + confidence + grade
              →  every deduction in plain English          →  recommendation + next action (§9)
              →  evidence pack exportable for the file
```

**One step from name to scorecard**, by design (§6 *Speed to answer*): no wizard, no source-selection
screen, no configuration. The only human step is the sanctions adjudication gate — and that one is
deliberate.

## 6.4 What to claim, and what not to

**Do not claim this replaces the questionnaire.** §2 of the methodology is explicit: roughly 7 of ~27
due-diligence criteria are externally observable, ~10 partially, ~10 not at all. Access controls,
security monitoring, data handling, insurance, change management and contract terms are invisible to
any lawful outsider.

The defensible pitch, in the order a procurement lead cares about:

1. **Triage.** Score 40 vendors on Monday morning; send full questionnaires to the 6 that need one.
   The questionnaire budget goes where it earns its cost.
2. **Pre-fill.** The fraction that *is* observable arrives already evidenced, so the vendor is not
   asked to self-report what a stranger can already verify.
3. **Contradiction-flagging.** The vendor's self-assessment against the public record — *"they answered
   'yes, DMARC enforced'; DNS says `p=none`."* **A questionnaire cannot do this for itself, and it is
   the single strongest reason to run both.**
4. **Continuous, not point-in-time.** A questionnaire is true on the day it is signed. Scheduled
   re-scores with drift alerts (`roadmap.md` §4) turn onboarding diligence into monitoring.
5. **Defensibility.** Under CPS 230, the buyer must evidence its own diligence. An immutable evidence
   store with reconstructible scores **is that artefact** — the thing a regulator asks for and a
   spreadsheet cannot produce.

## 6.5 What changes

| Action | When |
|---|---|
| Write this as a client-facing one-pager, `docs/value_proposition.md` | **Doable now** |
| **Evidence pack export** (PDF/JSON) — procurement needs something to put in the file | **Doable now** — the data already exists in the store; this is a rendering job |
| Batch/portfolio scoring for triage | **Future work** — `roadmap.md` §5 |
| Contradiction-flagging against questionnaire responses | **Future work** — needs platform integration |

---

# 7. Fourth-party risk — designed, unblocked, not yet built

## 7.1 Current state

Already in the roadmap as **§2.2, "the sharpest commercial wedge"**, and it is the one item on this
whole list that is **blocked on nothing**. From `roadmap.md`: *"Supply Chain unlocks with no new source
clearance — it re-feeds from the DNS/CT/trust collectors we already run."*

The category sits in `scoring.yaml` → `held_roadmap.supply_chain_dependency` — designed, declared, and
honestly emitting nothing rather than pretending to score.

## 7.2 The concept, stated for the record

```
You  →  Third party (the vendor you contract with)
            →  Fourth party (who your vendor depends on)
                 AWS · Azure · Cloudflare · Okta · Salesforce · Stripe · Twilio · Datadog
```

You have a contract with the third party. You have **no contract, no visibility and no leverage** with
the fourth. When Azure has a bad day, every vendor on Azure has a bad day — simultaneously, which is
the part that matters. **CPS 230 ¶48 makes this a regulated obligation**, not an interesting extra.

## 7.3 How to see it from public data only

| Method | Reveals | Source (all already collected) |
|---|---|---|
| **MX records** | Email provider (Google, Microsoft 365, Proofpoint, Mimecast) | `dns` |
| **SPF `include:`** | Every service authorised to send mail as them — SendGrid, Mailchimp, Salesforce, Zendesk | `dns` |
| **NS records** | DNS/CDN provider (Cloudflare, Route 53, Akamai) | `dns` |
| **CNAME targets** | SaaS in the path — Okta, Zendesk, Statuspage, Workday | `dns` |
| **CT SANs** | Shared-certificate infrastructure and hosting relationships | `ct` |
| **`/subprocessors`, DPAs** | The vendor's **own declared** fourth parties — the authoritative list, published under GDPR Art. 28 | `trust` |
| **`security.txt`** | Security tooling and hosting fingerprints | `headers` |

**The build is a normaliser enhancement plus a critical-third-party dictionary.** No new source, no new
legal clearance, no new egress.

## 7.4 The rule that stops this being unfair

**A fourth party's issues are disclosed as concentration context — they do not penalise the vendor.**

Penalising every AWS customer for an AWS CVE would punish thousands of vendors for one dependency they
share with their competitors, and would double-count the same risk across a client's whole portfolio.
The finding a client actually needs is not *"this vendor uses Okta"* — it is
**"six of your fourteen vendors authenticate through the same identity provider."**

That is a **portfolio** statement, and per `roadmap.md` §2.2 it is *"the finding a client cannot obtain
any other way."* Per-vendor enumeration ships first; concentration follows the portfolio view.

## 7.5 What changes

| Action | When |
|---|---|
| **Fourth-party enumeration** — provider fingerprint dictionary over the existing DNS/CT/trust output; renders as a *Dependencies* panel, disclosed not scored | **Doable now — the highest-value unblocked item on this list** |
| Subprocessor-list parsing from already-fetched trust pages | **Doable now** |
| Portfolio concentration analysis ("N of your M vendors share X") | **Future work** — 3–6 months, portfolio view |
| Fourth-party outage/incident correlation | **Future work** |

---

# 8. User perspective — four stakeholders, one record

## 8.1 Current state

The frontend is a **single-vendor, single-screen scorecard** (`frontend/src/Scorecard.jsx` +
`ScorePage.jsx` + `MethodologyPage.jsx`). It is genuinely well-designed for one reader — a technically
literate analyst looking at one vendor. It serves the other three **partially or not at all**, and the
gaps are structural rather than cosmetic: there is no portfolio, so there is no executive view; there
is no scheduled re-score, so there is no trend.

## 8.2 The four stakeholders

### Procurement Manager
**Question:** *Can I sign this contract?*
**Needs:** grade, confidence, one-line recommendation, deal-breakers, an evidence pack for the file.
**Today:** grade ✓ · confidence ✓ · plain-English reasons ✓ · **recommendation ✗** (§9) ·
**export ✗**.
**Reads:** the top third of the card. Should never need to scroll into TLS cipher suites.

### Cybersecurity Analyst
**Question:** *What exactly is wrong, and is it real?*
**Needs:** per-signal findings, the raw observation, the receipt, the source, the timestamp.
**Today:** **fully served** — category breakdown → expand → hash-stamped receipts, fetched on demand.
This reader is the one the current UI was built for.

### Risk Manager
**Question:** *How does this sit in my risk universe?*
**Needs:** risk categories, **trend**, **peer comparison**, confidence, residual-risk framing.
**Today:** categories ✓ · confidence ✓ · **trend ✗** (needs scheduled re-scores) ·
**peer comparison ✗** (§3, needs portfolio).

### Executive / CISO
**Question:** *Where is my exposure?*
**Needs:** portfolio-level view, top risks, movement since last quarter, concentration.
**Today:** **not served at all.** v1 scores one vendor; an executive view is a portfolio artefact.

## 8.3 The design principle

**One record, four projections. Not four scores.** Every reader sees the same posture, the same
confidence, the same evidence — at a different altitude. The analyst can always reach the receipt
behind the executive's number, and the number is the same number. The moment an executive summary is
computed differently from the analyst detail, Finding A's reconstructibility requirement is broken.

## 8.4 What changes

| Action | When |
|---|---|
| **Role-based default view** — a toggle that sets expansion depth and section order on the existing card. Same data, different first screen | **Doable now** — a UI change, no model change |
| **Executive summary block** at the top: grade, confidence, recommendation, top 3 findings, deal-breakers | **Doable now** — pairs with §9 |
| **Evidence pack export** (PDF/JSON) for the procurement file | **Doable now** |
| **Trend** — posture over time with before/after receipts | **Future work** — needs scheduled re-scores (`roadmap.md` §4, 3–6 months) |
| **Portfolio dashboard** — the executive view | **Future work** — `roadmap.md` §5 |

---

# 9. So what? Now what? — the sharpest point on the list

## 9.1 Why this one matters most

The model currently ends at **explanation** and stops short of **action**. v4.2.0 was a real advance
here: all 54 penalising bands carry a consequence-first plain-English sentence, and the loader refuses
to start if one is missing. So the system already answers *"So what?"* well.

It does not answer *"Now what?"* at all. A score with no recommended action makes the reader do the
translation, which is precisely the work the tool exists to remove — and, in a procurement context,
the point at which an unactioned amber score becomes a signed contract.

## 9.2 So what — already built

```
Posture 65 (C)   ·   Confidence 0.88   ·   Verified exposure

Why:
  ⛔  The security certificate has already expired and is still being served to the
      public. Visitors cannot verify they are talking to the real company.
      → Critical · observed live · ceiling applied (max publishable grade: D)
  ⚠   A product this company is associated with appears on the register of
      vulnerabilities being actively exploited in the wild.
      → Critical · name match against the product line, not proof this company is unpatched
  ⚠   Anyone can send email pretending to be this company.
      → High · no DMARC record published
```

Note the second finding's own caveat. That honesty is already in `scoring.yaml`, and it is what makes
the *"Now what?"* below defensible rather than alarmist.

## 9.3 Now what — the proposed action layer

Every finding gains four fields alongside its existing `reason`:

| Field | Example |
|---|---|
| `action` | "Request the replacement certificate and a screenshot of the renewal, or evidence the host is decommissioned" |
| `ask_of_vendor` | The exact question to send — copy-pasteable into the vendor email |
| `recheck_after` | `7d` for a live critical · `30d` for hygiene · `90d` for historic |
| `accepts_as_refute` | What evidence would close it — ties directly into the dispute path (open item 12) |

And the record gains **one recommendation**, derived from grade × confidence × client criticality:

| Grade | Confidence | Criticality | Recommendation |
|---|---|---|---|
| A–B | High | any | **Proceed.** Schedule re-check at 90 days |
| A–B | Low (*The Ghost*) | High | **Proceed with questionnaire.** Thin evidence ≠ good security — route to full diligence |
| C | High | Low | **Proceed with conditions.** Named remediations, re-check at 30 days |
| C | High | High | **Do not sign yet.** Send the evidence, require remediation proof, re-scan in 7 days |
| D–F | High | any | **Do not proceed** without an executive risk acceptance and compensating controls |
| any | any | any | **BLOCKED** (sanctions/ambiguous entity) → human adjudication. No score, ever |

Worked, in the reviewer's own framing:

> **So what?** Vendor X scores 65 (C). Two reasons: an expired production certificate served live, and
> a product-line KEV match.
> **Now what?** *Do not sign yet.* Send these two receipts to the vendor. Ask for (a) the replacement
> certificate, (b) confirmation of the patched version for the KEV CVE. Re-scan in 7 days.
> **Or:** accept the risk with a compensating control — isolate their access, no production data —
> recorded as an explicit, logged acceptance with a named owner and an expiry date.

## 9.4 Three rules on the action layer

1. **Recommendations are advisory and labelled as such.** A recommendation is not a decision; the
   client decides. Under Finding A, the reasonable-grounds representation attaches to what we publish —
   so a recommendation must be as traceable as the score that produced it.
2. **Criticality is a client input** (§2.2). We never infer how much a vendor matters to a buyer.
3. **The recommendation is deterministic and reconstructible** — derived from published fields by a
   rule table, not generated by the LLM summariser. The summariser stays a **read layer** that never
   computes or alters a score (§5.8), and that fence does not move for this.

## 9.5 What changes

| Action | When |
|---|---|
| `action` + `recheck_after` on every penalising band in `scoring.yaml` — the same discipline as `reasons`, loader-enforced | **Doable now — highest value per hour of work on this entire list** |
| Recommendation rule table + display, with criticality as an input | **Doable now** |
| `ask_of_vendor` copy-paste block per finding | **Doable now** |
| `accepts_as_refute` per band | **Doable now** as config; the **adjudication queue** that consumes it is open item 12 |
| Scheduled re-scan on `recheck_after` + drift alerts | **Future work** — `roadmap.md` §4 |

---

# 10. Consolidated plan

## 10.1 Doable now — no new sources, no new legal clearance, no budget

Ordered by value per hour of work:

| # | Item | Point | Why first |
|---|---|---|---|
| 1 | **`action` + `recheck_after` on all 54 penalising bands** | 9 | Turns explanation into a decision; config-only, loader-enforced |
| 2 | **Recommendation rule table** (grade × confidence × criticality) | 9, 8 | The single most requested output; deterministic |
| 3 | **`firmographics` collector + `VendorProfile`** | 2, 3, 5 | Unblocks three separate review points with one build |
| 4 | **Fourth-party enumeration** from existing DNS/CT/trust | 7 | Roadmap's own "sharpest wedge"; blocked on nothing |
| 5 | **Executive summary block + role-based default view** | 8 | UI only; serves three of four stakeholders |
| 6 | **Evidence pack export** | 6, 8 | Procurement needs a file artefact |
| 7 | **`industry_profiles`** — financial services + healthcare only | 5 | Two profiles with clear AU statutory anchors, corpus-guarded |
| 8 | **§11 of `methodology.md`** — budget tiers + buy-observations-never-verdicts | 1 | Documentation; answers the reviewer directly |

## 10.2 Near term — 0–3 months, blocked on keys and licence replies

| Item | Point | Blocked on |
|---|---|---|
| ABN Lookup collector (entity status **+ ANZSIC industry**) | 2, 3, 4 | Free registration GUID |
| Companies House collector + registry adapter interface | 4 | Free key (already cleared) |
| DFAT sanctions → the gate | 1, 4 | **Written licence reply — chase** |
| Modern Slavery Register → ESG category | 1, 4 | **Written licence reply — chase** |
| OAIC NDB sector statistics → expected-posture bands | 5 | Clearance pass |
| ACNC + auDA clearance passes | 4 | Clearance pass |

## 10.3 Future work — stated as future, not implied as present

| Item | Point | Blocked on |
|---|---|---|
| Peer percentile / cohort medians | 3, 5 | **Portfolio view** — a population, not a method |
| Portfolio concentration ("6 of your 14 share Okta") | 7 | Portfolio view |
| Executive dashboard, trend lines | 8 | Portfolio + scheduled re-scores |
| Scheduled re-scans, drift alerts | 9 | Scheduler + notification layer |
| Vendor dispute / adjudication queue | 9 | Open item 12 — a **known Finding A gap** |
| Commercial feeds (attack surface first, TI last and fenced) | 1 | Budget |

## 10.4 The two things I would not do

1. **Do not reintroduce category weights, per-industry or otherwise.** They were removed for a reason
   that has not changed: no authority publishes them, and the AFA says the rating system must be the
   user's. §5.3's severity profiles achieve the reviewer's intent with an anchor behind every line.
2. **Do not import a commercial risk score as an input.** Buy observations; assign our own severities
   under our own published bands. A score we cannot reconstruct is worse than no score — that is the
   project's first constraint, and it does not relax when the budget does.

---

### See also

- [`methodology.md`](methodology.md) — §5.6 (why no weights) · §7 (limitations) · §9 (open items)
- [`roadmap.md`](roadmap.md) — §2.2 (fourth party) · §4 (agentic) · §5 (platform alignment)
- [`source_assessment.md`](source_assessment.md) — per-source clearance, including the held AU sources
- [`scoring.yaml`](../WahidAI/OSINT_TPRM/scoring.yaml) — the model these changes land in
