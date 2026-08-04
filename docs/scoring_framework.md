# Scoring Framework — how a vendor becomes a score

*Penalty-based posture model (v4.0.0). Inspired by UpGuard's subtractive method, but our own:
our scale, our categories, our differentiators. The model is the deliverable and it lives in
[`scoring.yaml`](../scoring.yaml) — a file a non-engineer can read.*

---

## 1. The one-paragraph version

Every vendor **starts at 100**. For each issue found in lawfully-public OSINT we **subtract a
penalty** sized by severity (Critical -40, High -20, Medium -8, Low -3). Each **category's**
posture is 100 minus its own penalties (floored at 0); the **overall posture score** is the mean
of the covered category postures, with a letter **grade** (A–F) as the headline.
Kept strictly separate — never mixed into the score — is a **confidence** figure: how much of
the planned evidence actually came back. A sanctions hit **blocks** (no score); a directly-
observed current critical **caps** the grade; a vendor we can't cover is a **Ghost**, refused
rather than published.

---

## 2. The two axes — the idea the whole model is built around

Two numbers, never collapsed into one:

| Axis | Range | Question it answers |
|---|---|---|
| **Posture** | 0–100 (100 = strongest) + grade A–F | *How good does the external security posture look?* |
| **Confidence** | 0–1 coverage → High / Medium / Low | *How much of the planned evidence did we actually get?* |

A single number hides the difference between a vendor that is **genuinely clean** and one that
**merely returned little data**. We refuse to hide it. A strong-looking posture on **Low
confidence** is flagged **The Ghost** — unassessed, not safe.

**Confidence is pure evidence coverage.** Of the ~26 signals in the catalogue, how many returned
data? `>90%` High · `70–90%` Medium · `<70%` Low. Below 40% we **refuse** to publish a grade and
say which sources were silent — an 87 built on thin evidence must never read like an 87 built on
full evidence.

---

## 3. The grades

| Posture | Grade | Meaning |
|---|---|---|
| 85–100 | **A** | Robust posture, few or no external issues |
| 70–84 | **B** | Reasonable controls, some gaps |
| 50–69 | **C** | Poor controls, serious issues to address |
| 30–49 | **D** | Severe issues; should not handle sensitive data |
| 0–29 | **F** | Little to no basic security investment |

---

## 4. Severity penalties — the only points table

Every signal is a **pass** (no penalty) or a fail at one severity. Four fixed penalties drive
everything — no per-signal point-tuning, no category-weight derivation to defend.

| Severity | Penalty | Assign when… |
|---|---|---|
| **Critical** | **-40** | Actively dangerous & confirmable — expired production cert, unpatched KEV CVE, CVSS 9–10 |
| **High** | **-20** | Serious weakness — no DMARC, TLS 1.0/1.1, confirmed breach of personal data, CVSS 7–8.9 |
| **Medium** | **-8** | Meaningful gap — weak TLS, `p=none`, missing SPF, CVSS 4–6.9 |
| **Low** | **-3** | Minor hygiene — a missing security header, no DNSSEC, CVSS 0.1–3.9 |
| **Informational** | **0** | Recorded, **not** scored — unverifiable (unproven open port, unconfirmed media) |

**Why penalty-based?** The old model needed a defensible *weight* for every category (why 31%
cyber?) — a question with no authoritative answer. A penalty model deletes that problem: a
category's influence **emerges** from how many issues it has and how bad they are. One lever
(four numbers), every number a plain sentence.

---

## 5. The pipeline — order matters and is not negotiable

```
entity-resolution → collect (parallel, failure-isolated) → EVIDENCE STORE (first)
  → normalize (observation → severity → penalty) → decay (NIST SP 1326)
  → sum penalties per category → GATE (block) → category posture = 100 - its penalties
  → overall posture = MEAN of covered category postures → CRITICAL CEILING
  → grade + confidence (coverage)
```

Evidence is written **before** scoring — the store is the legal artefact (Finding A); a score is
reconstructible from it byte-for-byte months later.

---

## 6. Categories and signals

Seven categories we collect for. Each **signal** maps an observation to a severity (or pass) in
[`scoring.yaml`](../scoring.yaml). No percentages.

| Category | Example signals | Fed by |
|---|---|---|
| **Cyber Hygiene & Technical** | TLS version/cert, DMARC/SPF/DKIM, HSTS/CSP, DNSSEC/CAA | self-run TLS, DNS, HTTP headers |
| **Breach & Compromise History** | confirmed breaches, KEV, NVD+EPSS CVEs | HIBP, CISA KEV, NVD |
| **Digital Footprint & Assets** | subdomain estate, stale/shadow hosts, weak cert issuance | Certificate Transparency |
| **Vendor Transparency & Governance** | security-program disclosure, contactability, VD program | trust pages, `security.txt` |
| **Business & Financial Stability** | legal-entity standing, **domain standing (RDAP)** | GLEIF, Wikidata, RDAP |
| **Compliance & Regulatory** | certifications/attestations, disclosure | trust pages, reports |
| **Adverse Media & Reputation** | named regulator enforcement/investigation | regulator RSS |

Category score = 100 - penalties in that category (for the breakdown). Overall posture = the
**mean of the covered category postures** — a plain average, *not* a running sum of every penalty.
On a 0-100 scale summing all penalties would tank a merely-mediocre vendor to F (one -40 is 40%
of the whole score), so each category's posture is capped at its own 100 first, then averaged.
A genuinely severe *live* critical is still handled non-compensatorily by the ceiling (§8.2), so
the mean can't average a real crisis away.

---

## 7. How a single finding is penalised — the NIST variables

NIST SP 1326's variables, applied to the **penalty** per finding:

- **Severity** — the penalty tier above.
- **Age** — decay `0.5^(months/36)`, floored at 0.15. A 2013 breach penalises less than one from
  last month; it never decays to nothing.
- **Mitigation** — ×0.6 only where remediation is *evidenced*.
- **Multiplicity** — distinct realized issues (breaches) **sum**; a bag of keyword-matched CVEs
  is **worst-of** (the worst represents the group, so coarse-match noise can't tank a clean estate).

---

## 8. The overrides — where normal subtraction stops (the differentiators we kept)

### 8.1 The sanctions gate — emits nothing
A sanctions/watchlist match, or an entity too ambiguous to resolve, **BLOCKS**: the model emits
**no score** and routes to a human. It does **not** grade the vendor F. Under the Autonomous
Sanctions Act s 16(7) the screening record — clean or not — is the client's statutory-defence
evidence. Matching is whole-word (so *asana* can't trip on *villaSANA*) and recall-tuned.

### 8.2 The critical ceiling — non-compensatory (our knockout)
A **directly-observed current critical** (an expired production cert, seen live) **caps** the
posture at the top of Grade D (49) so one severe live issue can't be averaged away. Only signals
we observe as current auto-apply; a coarse KEV name-match penalises but does not ceiling (it
proves "product line had a KEV CVE", not "unpatched here"). A fired ceiling **bypasses the Ghost
refusal** — a directly-observed critical is certain even on thin coverage.

### 8.3 Weakest-link across assets
A vendor is only as strong as its weakest exposed asset: the vendor posture is the **lowest**
asset posture, not the average. (PoC scores the primary asset; multi-asset collection is roadmap.)

### 8.4 The Ghost — refuse rather than mislead
Coverage below 40% → we publish **no grade**, name the silent sources, and label it a Ghost. A
clean-looking vendor we can't stand behind is a designed refusal, not an error.

---

## 9. What is deliberately *not* scored

Excluded at the §4.2 bright line and logged in `excluded_signals` (not silently dropped):
executive/brand risk, PEP screening, person-level beneficial ownership, demographic profiling
(**all natural persons**), and shadow-AI usage (**not lawfully observable**). Five **held**
categories (supply chain, data privacy, geopolitical/FOCI, ESG, emerging-tech) have no lawful
free source yet and sit in a roadmap note — out of the runtime model so the config describes only
what actually scores.

---

## 10. Honest limits — stated up front

- **Perimeter, not posture-in-full.** OSINT sees the external surface; it can't see internal
  compensating controls.
- **Coverage tracks size.** Large vendors publish more, so they surface more signal — read the
  confidence axis, not the grade alone.
- **Fixed penalties are blunter than a calibrated curve.** Four tiers are easier to defend and
  tune than UpGuard's continuous deductions; deliberately blunter.
- **Grades and penalties are a transparent default the client owns** — tunable in one file, no
  authority publishes vendor-risk cut-points.

---

## 11. The sources feeding the model

Fourteen free, public, licence-checked collectors, each returning the same evidence envelope,
failure-isolated: DNS, self-run TLS, HTTP headers, Certificate Transparency (crt.sh + Cert
Spotter), HIBP, CISA KEV, NVD + EPSS, ITA sanctions (gate), GLEIF, Wikidata, **RDAP**, regulator
RSS, and GDELT (enrichment only). Details and licences: [`source_assessment.md`](source_assessment.md).

### See also
- [`../scoring.yaml`](../scoring.yaml) — the machine-readable model.
- [`methodology.md`](methodology.md) — the full legal/epistemic defence.
- [`source_assessment.md`](source_assessment.md) — every source, licence, and verdict.
