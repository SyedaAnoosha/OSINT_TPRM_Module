**`OSINT TPRM  ·  SCORING MODEL`**

UpGuard-Style Vendor Scoring

*A simplified, faithful version of UpGuard’s method — built to implement in a PoC, not to replicate the full platform.*

**The model in one line**

Start every vendor at **950**, subtract a **severity-weighted penalty** for each risk found in public data, group findings into weighted categories, and report a **separate confidence score** for how much evidence you actually had. Subtractive, not additive — this is the core difference from the first draft.

**1 · Scale and grades**

Score runs 0–950, mirroring UpGuard, with a letter grade for the headline. A vendor with no detected issues sits at 950 (Grade A); every finding pushes it down.

| `Score (0–950)` | `Grade` | `What it means` |
| :---- | :---- | :---- |
| `801–950` | **A** | Robust posture, few or no external issues |
| `601–800` | **B** | Reasonable controls, some gaps |
| `401–600` | **C** | Poor controls, serious issues to address |
| `201–400` | **D** | Severe issues; should not handle sensitive data |
| `0–200` | **F** | Little to no basic security investment |

**2 · Severity penalties (the only points table you need)**

Every signal you collect is either a pass (no penalty) or a fail at one of four severities. Fixed penalty per severity — no per-signal point tuning. These four numbers are the main lever; start here and calibrate later.

| `Severity` | `Penalty` | `Assign it when…` |
| :---- | :---- | :---- |
| **Critical** | **`-150`** | Actively dangerous & confirmable — exposed database, malware/phishing blocklist, CVSS 9.0–10 CVE |
| **High** | **`-70`** | Serious weakness — expired cert, exposed RDP/SMB, end-of-life software, CVSS 7.0–8.9 |
| **Medium** | **`-30`** | Meaningful gap — weak TLS, missing SPF/DMARC, CVSS 4.0–6.9 |
| **Low** | **`-10`** | Minor hygiene — a missing security header, no DNSSEC, CVSS 0.1–3.9 |
| **Informational** | **`0`** | Cannot verify (unconfirmed adverse media, unproven open port) — record it, do not score it |

*For vulnerabilities, read severity straight off the CVSS band as shown — the same mapping UpGuard uses.*

**3 · Categories and example signals**

Group signals into these six OSINT-collectable categories — aligned to where UpGuard puts most of its weight (encryption, website, vulnerabilities, attack surface, reputation). You don’t set category percentages: the weighting emerges from how many signals sit in each and how hard they are penalised.

| `Category` | `Example public signals` | `Typical severity` |
| :---- | :---- | :---- |
| Encryption / TLS | SSL Labs grade, protocol/cipher strength, certificate validity & expiry, HSTS | Low → Critical |
| Website security | Security headers (CSP, X-Frame-Options), cookie flags, exposed admin/login pages | Low → High |
| Vulnerability mgmt | Known CVEs on detected software versions, end-of-life / unpatched products | Medium → Critical |
| Attack surface / network | Open ports, exposed services (databases, RDP, SMB), unnecessary services | Low → Critical |
| DNS & email | SPF, DKIM, DMARC presence & strength, DNSSEC, open resolvers | Low → High |
| Reputation & exposure | Domain/IP on malware or phishing blocklists, breach/leak appearances, exposed cloud storage | High → Critical |

**4 · How the numbers roll up**

**1**   Collect every signal in the catalogue for the vendor’s asset (domain / IP).

**2**   Overall score \= **950 - (sum of every penalty found)**, floored at 0\. All findings count against one running total — this is what makes a vendor with problems in several categories drop faster, exactly like UpGuard’s uncapped overall.

**3**   Category score \= **950 - (penalties in that category only)**, floored at 0 — for the breakdown display, so a reader sees which area dragged the vendor down.

**4   Confidence \= evidence coverage**, reported separately (never mixed into the score):

| `Evidence coverage` | `Confidence` |
| :---- | :---- |
| More than 90% of planned signals returned data | **High** |
| 70–90% | **Medium** |
| Under 70% | **Low** |

State plainly which sources didn’t respond, so an 87 built on thin evidence is never read as an 87 built on full evidence.

**5   Override.** A direct sanctions / watchlist match, or a confirmed active breach or ransomware event, forces the grade to F regardless of the number. Some findings are disqualifying and must not be averaged away.

**6   Multiple assets — weakest link.** If a vendor has several domains or IPs, the vendor score is the **lowest** asset score, not the average. A vendor is only as strong as its weakest exposed asset.

**5 · Pseudocode**

`MAX = 950`  
`PENALTY = { Critical:150, High:70, Medium:30, Low:10, Informational:0 }`  
   
`def score_asset(asset):`  
    `overall = MAX`  
    `category = { c: MAX for c in CATEGORIES }`  
    `planned = evaluated = 0`  
   
    `for signal in SIGNAL_CATALOGUE:`  
        `planned += 1`  
        `result = collect(asset, signal)          # OSINT collector`  
        `if result is None or result == 'unverified':`  
            `continue                              # informational: no penalty`  
        `evaluated += 1`  
        `if result == 'fail':`  
            `sev = severity(signal, result)        # CVSS band for CVEs`  
            `overall              -= PENALTY[sev]`  
            `category[signal.cat] -= PENALTY[sev]`  
   
    `overall  = max(0, overall)`  
    `category = { c: max(0, s) for c, s in category.items() }`  
    `confidence = band(evaluated / planned)        # High / Medium / Low`  
    `return overall, category, confidence`  
   
`def score_vendor(vendor):`  
    `assets = [score_asset(a) for a in vendor.assets]`  
    `vendor_score = min(a.overall for a in assets)  # weakest link`  
    `if sanctions_match(vendor) or confirmed_breach(vendor):`  
        `return grade='F', reason='override'`  
    `return grade_band(vendor_score), vendor_score`

**6 · Worked example**

A vendor’s single domain returns: SSL Labs grade C (Medium, -30), one expired certificate (High, -70), missing DMARC (Medium, -30), two missing security headers (Low, -10 each \= -20), and one CVSS 9.1 CVE on an exposed service (Critical, -150). Nine of ten planned signals returned data.

Overall \= 950 - (30 \+ 70 \+ 30 \+ 20 \+ 150\) \= **650 → Grade B.**  Coverage 9/10 \= 90% → **Confidence: High.**  No sanctions or breach, so no override. Headline: **650 / 950 (B), High confidence**, with Vulnerability Management and Encryption shown as the weakest categories.

**7 · Be honest about what this simplifies**

Two deliberate simplifications versus the real UpGuard, worth stating in the methodology note: **(a)** four fixed severity penalties instead of UpGuard’s continuous, calibrated deductions — easier to defend and tune, slightly blunter; **(b)** weakest-link `min()` across assets instead of UpGuard’s lower-weighted Gaussian mean — same intent, simpler maths. Keep the confidence layer and the sanctions override: the first is better than UpGuard’s (it publishes evidence coverage rather than silently dropping unverifiable findings), and the second is a sensible TPRM extension beyond UpGuard’s purely technical rating.