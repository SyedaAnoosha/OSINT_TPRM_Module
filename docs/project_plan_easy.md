# Project Plan: OSINT for Third-Party Risk

## Objective
To build a simple, working web application. A user will enter a vendor's name or domain and instantly receive a customized, board-ready risk scorecard. This serves as a decision-support instrument—not a replacement for deep-dive security questionnaires—grouping risks by business category and scoring them for technical posture, incident history, and transparency, backed by an immutable trail of public evidence.

## Scope
* **Targeted Coverage:** We are assessing the publicly observable perimeter and digital footprint of any named vendor. We are not attempting to see inside their internal networks or measure unobservable controls.
* **Data Sources:** We will rely on lawfully published, free, or trial-tier OSINT sources. These include, e.g., Certificate Transparency logs (crt.sh), self-run TLS and HTTP-header checks, DNS queries, SEC EDGAR, Have I Been Pwned (free breach endpoint), GDELT, NVD, CISA KEV, vendor trust pages, and the US ITA Consolidated Screening List (sanctions gate). The full per-source legality, reliability, and limits assessment lives in `source_assessment.md`.
* **Exclusions:** Paid feeds (Shodan, VirusTotal commercial) are excluded under the free-data rule. SSL Labs is excluded on terms-of-service grounds (commercial-use bar and permission clause); our own TLS handshake collector performs the equivalent check as a direct client connection, which is the cheaper legal position documented in `source_assessment.md` §3. Any data involving natural persons (executive PII, PEP screening) is excluded at the bright line per APP 10, the privacy tort, and EU AI Act Art 6(3).

## Scoring Framework
To ensure the output is credible enough for a Chief Risk Officer, every vendor is evaluated using strict, defensible rules mapped to regulatory frameworks (APRA CPS 230) and US federal standards (NIST SP 1326).

### Where the Weights Come From — an honest account
No published standard sets vendor-risk category weights. NIST, APRA and ISO name the categories; none of them says Cyber is worth 24% and Financial 5%. Relative weighting is a risk-appetite judgement — and a regulator (the AFA) is explicit that it must be the client's to make. So we do not claim our weights are "derived from authority." We ship a transparent default resting on three things: its **structure** follows NIST SP 1326 / CSF 2.0; its **non-compensatory rules** (the sanctions gate, the knockout floor) are anchored in Australian law; and its **exact values** are being validated by sensitivity analysis to confirm they sit inside a band that doesn't change the risk rating. Every weight is editable by the client in one config file without a redeploy — which is exactly what "own your rating system" requires. How well we can observe a category affects our confidence, never its weight. Two categories (Digital Footprint, Adverse Media) map to no NIST due-diligence area and no legal mandate, so they lean entirely on the sensitivity check — they are flagged, not hidden. (The full derivation basis, including how the ordering was pressure-tested, is in `methodology.md` §5.6.)

### The 2 Gates (Dealbreakers)
To prevent silent failures or accidental legal breaches, vendors must pass two gates before any math is applied. If a vendor hits a sanctions list (currently screened against the US ITA Consolidated Screening List; DFAT is the intended second input, held pending licence clearance—see Limitations), it does not get a "High Risk" score; it is entirely blocked for human adjudication. If the system cannot confidently resolve the entity name (below 0.5 confidence), it blocks to prevent scoring the wrong company.

### Risk Categories (What Are We Measuring?)
Instead of scoring by technical data source, we score by the business questions the board actually asks. All weights are a tunable default (§5.6). The "anchor" column shows the strongest support each one has — a NIST-named category (structure), a legal mandate, or (for the two weakest) sensitivity analysis alone.

The v3.2 re-tier scores a category only if a working free-data collector actually feeds it — **seven scored**, five held.

| Category | Weight | Strongest anchor | What it measures |
| :--- | :--- | :--- | :--- |
| **Cyber Hygiene & Technical** | 31% | Structure (NIST Foundational Cyber) | Are their technical locks (TLS, DMARC, Headers) working? |
| **Breach & Compromise History** | 25% | Structure (NIST) + realized-harm directness | Have they been hacked, or are their products actively exploited? |
| **Vendor Transparency & Gov** | 14% | Structure (NIST / compliance) | Do they publish a trust center, security.txt, or bug bounty? |
| **Digital Footprint & Assets** | 10% | ⚠ Sensitivity only — no NIST or legal anchor | How large is their subdomain estate, and are there shadow assets? |
| **Business & Financial Stability** | 7% | Structure (NIST resilience) | Is this a live, in-good-standing legal entity (GLEIF LEI register)? |
| **Compliance & Regulatory** | 7% | Structure (NIST / attestations) | Do they claim SOC 2/ISO 27001, and can we verify it? |
| **Adverse Media & Reputation** | 6% | ⚠ Sensitivity only — no NIST or legal anchor | Are there **named regulatory enforcement actions** (hard facts, not sentiment)? |

**Held** (weight 0, emit nothing until source clears): Supply Chain & Dependency (target 13%, CPS 230 ¶48), Data Privacy & Leakage (target 6%), Geopolitical & FOCI (target 4%), ESG & Ethical (target 3%), Emerging Tech & AI (target 2%).

> **v3.2 source moves:** Business Stability re-sourced **EDGAR → GLEIF** (EDGAR was US-listed only; GLEIF is global, free, no-auth, resolves all five vendors). Adverse Media **promoted held → scored** on a hard-fact **regulator-RSS** feed, not GDELT sentiment.

### The Knockout Floor (When Is a Vendor Automatically Penalized?)
A weighted average can sometimes hide a catastrophic flaw. The Knockout Floor prevents good hygiene from laundering a critical failure into a "safe" score. It **auto-fires only on criticals we can observe *directly and currently*** — confidently attributed (≥ 0.7) and with a named cause. A finding we can't confirm is *current* is scored high and flagged for review, not auto-floored — because a coarse match is not proof of a live problem.

| Tier | Trigger | System Behavior |
| :--- | :--- | :--- |
| **Auto-floors the score** | **Expired production certificate** — observed live, unambiguous. Attributed (≥ 0.7). | Overall risk floored to the bottom of the Moderate band; the vendor cannot be reported as anything better. Cause named on the scorecard. |
| **High-severity + review flag** | A **KEV-listed CVE** name-matched to the vendor, or a breach not evidenced as remediated. We can't confirm it's *currently* unpatched. | Scores high (pushes Incident History up) and flags for analyst review; escalates to a floor only once the current/unpatched condition is confirmed. |
| **Scores normally** | High theoretical CVSS without exploitation evidence, a cert expiring in 20 days, or a historical, remediated breach. | Diluted by the rest of the vendor's posture. |

**Why KEV no longer auto-floors:** a match against the known-exploited-vulnerabilities catalogue tells us *"this product line has had a known-exploited CVE,"* not *"the version this vendor ships today is unpatched."* Auto-flooring every major software vendor to Moderate on a years-old, since-patched CVE is not defensible — so it scores high and routes to review instead.

### Multi-Asset & Vendor Dispute
- **Multiple domains — weakest link for criticals.** A vendor usually has many domains. Non-critical findings are averaged across them, but **a critical finding on *any* one domain floors the whole vendor** — one rotten `legacy.vendor.com` cannot be hidden behind a clean main site.
- **A dispute pathway (designed).** Because outside-in OSINT can't see internal compensating controls, a vendor may submit redacted evidence (a SOC 2 report, a patch log, "that IP is our CDN not us") to refute a finding. On human review, accepted evidence reduces or nullifies the finding — logged immutably alongside the original. This corrects the model's built-in tendency to over-penalise well-run but quiet vendors.

### Confidence & Quadrants (How Sure Are We?)
Because public data is patchy, a missing data point must reduce our confidence, never the vendor's risk. We refuse to reward a vendor for being invisible.

| Quadrant | Risk Level | Confidence | Meaning for the Board |
| :--- | :--- | :--- | :--- |
| **Evidenced Clean** | Low (≤ 40) | High (≥ 0.7) | Transparent footprint, corroborated. The only quadrant where "low risk" truly means low risk. |
| **The Ghost** | Low (≤ 40) | Low (< 0.7) | Looks perfect because we found almost nothing. Not a safe vendor; an *unassessed* one. Requires a questionnaire. |
| **Verified Exposure** | High (> 40) | High (≥ 0.7) | Corroborated findings. Act on it. |
| **Uncorroborated Signal** | High (> 40) | Low (< 0.7) | Something is there, but we cannot stand behind it. Review internally; *do not report to the client*. This is a defamation control: publishing an uncorroborated hit against a small vendor (who can sue) exposes the score-buyer to legal action. |

---

## Development Stages (Phase by Phase)

### Phase 1: OSINT Collection & Evidence Store
* **Parallel Collectors:** We build isolated, polite modules for all cleared sources. They run in parallel, respecting rate limits (e.g., throttling SEC EDGAR to 8 requests/second with a compliant `User-Agent` header to avoid 403 blocks).
* **The Evidence Store (The Legal Artifact):** Before any scoring happens, raw data is written to an immutable, append-only database. Every piece of data is timestamped and versioned. This is not just good engineering; it is the legal proof that our score was formed on "reasonable grounds."
* **Handling "Empty" States:** If a source returns nothing (e.g., no SEC filings for a private company), it is logged as a first-class `empty` result. It does not crash the system; it simply reduces the confidence score.

### Phase 2: Scoring, Gates & Modifiers
* **Applying the Gates:** The system checks the ITA sanctions list and entity resolution confidence. If either fails, the vendor is routed to a `BLOCKED` state, emitting no score.
* **Applying NIST Modifiers:** The system applies the four NIST SP 1326 variables to every finding: Age (a 2013 breach decays via a 3-year half-life, never reaching zero), Frequency, Severity, and Mitigation (only applied if publicly evidenced).
* **Calculating the Score:** The system calculates the weighted mean of the 9 scored categories, checks whether the Knockout Floor applies (critical finding, ≥ 0.7 attribution, named cause), and calculates the final Confidence score to assign the correct Quadrant.

### Phase 3: Frontend, Scorecard & Final Polish
* **Streaming Scorecard:** We build a clean, single-screen dashboard. The user types a vendor name, and the scorecard streams in progressively as the collectors finish. There are no wizards or source-pickers.
* **Explainability & Receipts:** For every point deducted, the user can click through to see the exact public evidence (e.g., the specific crt.sh log or HIBP breach). Mandatory attributions (NVD, HIBP, GDELT) appear on the scorecard itself, not in a footnote.
* **Final Polish:** We ensure the design handles edge cases gracefully—like a very long vendor name (60+ characters) breaking the layout, or a vendor triggering "The Ghost" quadrant. The UI clearly labels unassessed vendors so a user never mistakes "The Ghost" for "Evidenced Clean."

---

## System Flow
1. **User Input:** The user visits the web app and enters a vendor's name or domain.
2. **Entity Resolution:** The system resolves the identity. If it cannot do so confidently (< 0.5), it blocks here—scoring the wrong company is worse than not scoring, and there is nothing yet to record.
3. **Parallel Collection:** Rate-limited queries fire to all cleared OSINT sources simultaneously, **including the ITA sanctions screen**.
4. **Evidence Store:** All raw responses—including the sanctions screen result, **hit or clean**—are immutably logged with timestamps before any math. The clean screen is itself the client's statutory defence record (Finding B), so it is retained, never discarded.
5. **Gate → Score → Floor:** *Now* the gate fires: a sanctions hit routes to `BLOCKED`, emitting no score (the record from step 4 survives the block). Otherwise the system normalizes, applies the NIST decay modifiers, calculates the weighted categories, and enforces the Knockout Floor where attribution warrants.
6. **Final Output:** The frontend streams a board-ready scorecard displaying the overall risk, the confidence quadrant, and the evidence receipts.

---

## Limitations
* **The OSINT Blind Spot:** We cannot see internal controls (access management, segmentation, data handling). The score reflects the publicly observable perimeter, not the whole security posture.
* **No Live Attack-Surface / Blocklist View (deliberate v1 constraint — top roadmap item).** We cannot see open RDP/SMB ports or a domain sitting on a live phishing blocklist. This is a *deliberate* boundary, not an oversight: active port-scanning risks an unauthorised-access classification, and the obvious data sources are legally blocked — Shodan/Censys **free** tiers bar commercial use (the same reason we excluded VirusTotal), and the community threat-intel feeds proposed to fill the gap carry unverified commercial-use terms. We proxy attack surface via Certificate Transparency (certs *issued*, not ports *open*) and own the gap openly rather than close it with an unlawful shortcut. Clearing a *properly licensed* source is Roadmap Priority #1.
* **The "Ghost" Problem:** Absence of evidence is not evidence of security. A badly-run vendor with no public footprint will score as "The Ghost" (unassessed), which is frustrating for users who just want a simple "Low Risk" badge.
* **Australian Sanctions Gate Incomplete:** The DFAT Consolidated List is the intended second input to the sanctions gate but is currently held pending licence clearance from the Australian Sanctions Office. Until resolved, the gate screens against the US ITA list only. The scorecard discloses this gap explicitly.
* **ESG Category Held at Weight 0:** The Modern Slavery Register licence is unresolved (AGD query outstanding). The ESG category is present in the structure but scores nothing until cleared.
* **US-Centric Financial Data:** Business stability relies heavily on SEC EDGAR. This provides excellent precision but terrible recall for private, non-US-listed companies, resulting in low confidence for many Australian vendors.
* **Adverse Media Noise:** Media coverage tracks newsworthiness, not actual risk. A large consumer brand will generate more noise than a riskier obscure vendor. We use AI adjudication to filter this, but it remains the noisiest signal in the model.
* **No Weight Is Inherited from an Authority:** No standard publishes category weights, so every weight is a reasoned, tunable default — defended by structure (NIST) and a sensitivity check, not by inheritance. The honest soft spots are the two categories that map to no NIST due-diligence area and no legal mandate (Digital Footprint, Adverse Media), and the fact that the sensitivity analysis that proves the exact values are low-stakes is not yet run (open item 13). Until it is, "the values don't swing the outcome" is claimed, not shown.

---

## Deliverables

*Status: the backend is built and tested — the evidence store, all collectors, and the full scoring engine (gates, decay, knockout floor, confidence, quadrants) run end-to-end on the five vendors. The web frontend, scheduled re-checking, and the multi-asset / dispute workflows are designed and in progress. This document is the target-state model; what is designed-but-not-yet-wired is labelled as such throughout rather than implied complete.*

1. **A Working Web Application:** A clean, frictionless frontend that takes a vendor name and outputs a streaming, evidence-linked risk scorecard.
2. **An Immutable Evidence Store:** A structured, append-only database where every single point deducted from a score is backed by a timestamped, retrievable public record.
3. **A Board-Ready Scorecard:** A presentation-quality output that clearly separates verified risks from unassessed "ghosts," explicitly states the model's confidence limits, and discloses any coverage gaps (e.g., DFAT held).
4. **Methodology & Scoring IP:** A fully documented, human-readable scoring model (`scoring.yaml`) that states each weight as a tunable default, shows its strongest anchor (NIST structure, legal priority, or sensitivity-tested judgment), and records how it is defended and where sensitivity analysis still owes proof.