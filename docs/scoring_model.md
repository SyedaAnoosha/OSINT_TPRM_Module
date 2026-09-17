# Scoring Model — v2 (`scoring.yaml` v5.4.0, penalty-based posture + Business Stability axis)

**OSINT TPRM vendor scoring — the model, and the arithmetic behind every published number.**

> **Direction, stated once and never inverted: `100 = strongest posture, 0 = weakest`. A penalty is
> *subtracted* for each issue found.**

*The model is the deliverable. It lives in machine-readable form in [`scoring.yaml`](../scoring.yaml) —
a file a non-engineer can read in a room with a client. The full legal and epistemic defence is
[`methodology.md`](methodology.md) Part 1 §5.*

| Part | What it covers |
|---|---|
| **1 · The model in brief** | The guided summary — severity ladder, grades, categories, roll-up, the three axes |
| **2 · Metrics reference** | Every published metric and the arithmetic actually implemented, each constant read from code |
| **3 · Vendor age differentiation** | How age is used across Longevity, Maturity and Business Stability — and why it never touches cybersecurity posture |

## Part 1 · The model in brief

**OSINT TPRM vendor scoring — the model in brief.**

> **Direction, stated once and never inverted: `100 = strongest posture, 0 = weakest`. A penalty is *subtracted* for each issue found.**

*The model is the deliverable. It lives in machine-readable form in [`scoring.yaml`](../scoring.yaml) — a file a
non-engineer can read in a room with a client. This page is the guided summary; the full legal and epistemic
defence is [`methodology.md`](methodology.md) Part 1 §5.*

---

### The model in one line

Take a vendor name or domain, collect lawfully-public evidence, and **start every vendor at 100**. For each
issue found, **subtract a penalty sized by severity**. A category's posture is 100 minus its own penalties; the
**overall posture** is 100 minus the total penalty spread over a **fixed divisor**, published with a letter
**grade (A–F)** and a plain-English sentence for every deduction. Reported *beside* it — never mixed in — are
**confidence** (how much of the planned evidence actually came back, §7) and **assurity** (how much independent
assurance the vendor carries, §8). Two things sit outside the arithmetic: a **sanctions gate** that blocks the
score, and a **critical ceiling** that stops one directly-observed live critical from being diluted by good
hygiene elsewhere.

The core difference from a single-grade platform: **we never collapse posture, confidence and assurity into one
figure.**

#### The three axes, and the four readings beside them

| | What it answers | Range | Who owns it |
|:--|:--|:--|:--|
| **Posture** (§1–6) | How strong does this vendor look from outside? | 0–100 · A–F | Ours to measure |
| **Business Stability** (§6.1) | Is this vendor financially viable? | 0–100 · Age-based | Ours to measure |
| **Confidence** (§7) | How much of the vendor could we actually see? | 0–1 · High/Med/Low | Ours to measure |
| **Assurity** (§8) | Has anyone independent checked? | 0–100 | Ours to measure |
| Compliance gap (§8.1) | Are the vendor's own claims reliable? | a list, with citations | Observed |
| Inherent → residual (§9) | How much do *we* stand to lose? | 4 tiers → 16 cells | **The buyer declares it** |
| Peer placement (§10) | Am I typical? | quartile / percentile, with `n` | Computed from the book |
| Expectation gap (§10.1) | Am I what my peer group predicts? | posture − E[posture ∣ cohort] | Computed from the book |
| Target maturity (§7.2) | Am I adequate? | met / applicable controls | Published standards |

Everything below the axes **interprets** the scores. None of it can move them.

---

### Why penalty-based (and why we changed)

The earlier model needed a defensible *weight* for every category — *why is Cyber Hygiene 31%?* — a question with
no authoritative answer (no standard publishes vendor-risk weights). A penalty model **deletes that problem**: a
category's influence **emerges** from how many issues it has and how bad they are. One lever — four severity
numbers — and every number maps to a plain sentence a client can challenge. It is inspired by UpGuard's subtractive
method but is **our own**: our 0–100 scale (not 950), our five scoring categories, and our three differentiators (below)
that a pure technical rating does not have.

---

### 1 · Severity penalties — the only points table

Every signal is a **pass** (no penalty) or a fail at exactly one severity. Four fixed penalties drive everything —
no per-signal point-tuning, no category-weight derivation to defend.

| Severity | Penalty | Assign when… |
|:--|--:|:--|
| **Critical** | **−40** | Actively dangerous & confirmable — expired production cert, unpatched KEV CVE, breach exposing passwords/cards, CVSS 9–10 |
| **High** | **−20** | Serious weakness — no DMARC, TLS 1.0/1.1, confirmed breach of personal data, CVSS 7–8.9 |
| **Medium** | **−8** | Meaningful gap — weak TLS, `p=none`, missing SPF, CVSS 4–6.9 |
| **Low** | **−3** | Minor hygiene — a missing security header, no DNSSEC, CVSS 0.1–3.9 |
| **Informational** | **0** | Recorded, **not** scored — unverifiable (unproven open port, unconfirmed media allegation) |

**All bands live in [`scoring.yaml`](../scoring.yaml), not in code** — the model must be arguable with a client
without a redeploy. Each finding is then adjusted by the NIST SP 1326 variables (§4) before it is subtracted.

---

### 2 · The grades

The overall posture (0–100) maps to a letter grade — a documented, client-tunable default (no authority publishes
vendor-risk cut-points).

| Posture | Grade | Meaning |
|:--|:--|:--|
| 85–100 | **A** | Robust posture, few or no external issues |
| 70–84 | **B** | Reasonable controls, some gaps |
| 50–69 | **C** | Poor controls, serious issues to address |
| 30–49 | **D** | Severe issues; should not handle sensitive data |
| 0–29 | **F** | Little to no basic external security investment |

Confidence runs **0–1** and is reported *beside* the grade, never mixed into it (§5).

---

### 3 · Categories and signals

**Five scoring categories and two context categories.** Each **signal** maps an observation to a severity (or
pass) in [`scoring.yaml`](../scoring.yaml) — **no category percentages**; a category's influence emerges from
the issues found in it, which is the whole point of a penalty model.

The keys below are the ones the engine uses and the scorecard renders, so a category name can be carried from
this page to a vendor's record and back.

#### Scoring categories — *how exposed is this vendor to compromise?*

| # | Category | Engine key | Example signals | Fed by |
|:-:|:--|:--|:--|:--|
| 1 | **Breach & Compromise History** | `breach_compromise_history` | confirmed breaches by data class, KEV-listed CVEs, NVD CVEs by CVSS | HIBP, CISA KEV, NVD, FIRST EPSS |
| 2 | **Attack Surface & Hygiene** | `attack_surface_hygiene` | TLS version, certificate validity, HSTS/CSP/X-Frame-Options, DNSSEC/CAA, stale hosts, weak issuance, estate-wide TLS and expiry | self-run TLS, DNS, HTTP headers, Certificate Transparency |
| 3 | **Identity & Email** | `identity_email` | DMARC, SPF, DKIM | DNS |
| 4 | **Transparency** | `transparency` | vulnerability-disclosure programme, `security.txt` | HTTP headers, trust pages |
| 5 | **Compliance & Regulatory** | `compliance_regulatory` | certification posture (claimed vs registry-corroborated), regulator action | trust pages, regulator feeds |

#### Context categories — collected, counted toward coverage, **never penalising**

| Category | Engine key | Signals | Feeds |
|:--|:--|:--|:--|
| **Continuity Context** | `continuity_context` | entity status, entity existence, entity maturity, domain registration | the Continuity axis (E4) |
| **Assurance Context** | `assurance_context` | programme disclosure, contactability, reporting posture | **Assurity** (§8) |

Three things about this split are worth stating plainly, because it is the largest structural change the model
has had:

- **Why two categories stopped scoring.** A vendor entering administration does not thereby have worse TLS.
  Companies House mapped liquidation and insolvency onto `entity_inactive`, which cost **20 points of technical
  security posture**. And penalising the absence of an audit or a public security page is a tax on audit budget
  — it measures spend, not risk, and falls hardest on small suppliers. Both facts are still collected and still
  published; neither charges posture any more.
- **Why they were not simply deleted.** `planned_signal_count` is the confidence denominator. Delete nine
  signals and every vendor's confidence rises for no evidential reason — the check still ran, we merely stopped
  charging for it. Keeping them holds the denominator at **27** and keeps the receipt showing the check
  happened. `test_context_categories_never_penalise` asserts they carry no penalising band.
- **Identity & email is separate from hygiene on purpose.** It is one decision at the apex, answered by three
  DNS records that stand or fall together, and a per-host *rate* has no meaning for it.

**Signals are unique across categories** — the engine keys penalties on `(category, signal)`, so a signal
appearing twice would be charged twice. Asserted by `test_no_signal_appears_in_two_categories`.

**Held** (designed, but no free lawful source feeds them yet — out of the runtime model, in a roadmap note):
Supply Chain & Dependency · Data Privacy & Leakage · Geopolitical & FOCI · ESG & Ethical · Emerging Tech & AI.

**The directness ladder** (inside Category 1, worth calling out): a realized breach outranks observed
exploitation (KEV) outranks a theoretical CVE (NVD). What *happened* penalises harder than what merely *could*.

---

### 4 · How a single finding is penalised — the NIST variables

NIST SP 1326's variables, applied to the **penalty** per finding before it is subtracted:

```
effective_penalty = severity_penalty × age × frequency × mitigation
```

| Variable | Rule | Why |
|:--|:--|:--|
| **Severity** | the four-tier penalty above | signal-specific, the main lever |
| **Age** | `max(0.15, 0.5 ^ (months / 36))` | 3-year half-life, floored at 0.15 — a 2013 breach penalises less than one from last month, but never decays to nothing |
| ↳ *exception* | current-state signals **never decay** | a cert's `event_date` is its expiry boundary, not an event. Decaying it made a cert expired 6 years ago cost **−10** while one expiring next week cost **−20** — the longer it stayed broken, the cheaper it got. Listed in `modifiers.age.never_decays` |
| **Frequency** | `1 + 0.25 × (n − 1)`, cap 2.0 | three breaches are a pattern, not one counted thrice |
| **Mitigation** | `× 0.6` only where remediation is **evidenced** | claims don't count; corroboration does |

**Collapse, then amplify — never sum.** Every `(category, signal)` group contributes **one** penalty: its
**worst instance after decay**. Recurrence is then counted exactly once, by the frequency factor. Three
breaches are `20 × 1.5 = 30`, not `20+20+20 = 60` — summing *and* amplifying would count the same pattern
twice, and two breaches would already outweigh a −40 critical.

**CVE bags are frequency-exempt.** Forty keyword-matched CVEs are match *volume*, not forty events: they
collapse to their worst representative with no amplification, so coarse-match noise can't tank a clean
estate. Realized events (breaches, regulator actions) *are* amplified — there, recurrence is real.

**Mitigation is live but dormant.** It is carried on the finding, never inferred from severity — and no
free source we collect currently evidences that a vendor fixed a given issue, so nothing sets it today.
The rule is real; the discount is not yet being handed out.

---

### 5 · How the numbers roll up

```
observation → severity → penalty (× age × frequency × mitigation)
   ↓  collapse each (category, signal) group to its WORST instance
   ↓  sum penalties PER CATEGORY, each capped at 100
category posture = 100 − its own penalties      (for the breakdown)
   ↓  GATE ── sanctions hit / ambiguous entity ──►  BLOCKED, no score emitted
overall posture = 100 − (total penalty ÷ FIXED divisor, currently 2.86)
   ↓  CRITICAL CEILING ── directly-observed current critical ──►  capped at 49 (top of D)
grade (A–F)  +  confidence (coverage, reported separately)  +  assurity (§8)
   +  a plain-English reason per deduction (§11)
```

**Overall is `100 − total penalty ÷ a fixed divisor`.** Each category's damage is capped at its own 100 first
(one catastrophic category cannot dominate without bound), then the total is divided by a divisor **fixed by the
model** — currently **2.86**. Not a running sum: on a 0–100 scale that tanks a merely-mediocre vendor to F. And
deliberately **not** an average of the categories that happened to return data — that let a clean trust page buy
**+23 posture**, because each clean category entered the average as a 100 and pulled it up. A silent source adds
no penalty and cannot move the denominator, so *"missing data never changes posture"* is arithmetic, not a promise.

#### Why 2.86, and why the divisor must move when the category count does

The model's **maximum damage** is `scoring_categories × 100 ÷ divisor`. That product is the thing being held
fixed, and it is the trap the E5 restructure had to avoid:

| Scoring categories | 7 | 6 | **5** | 4 | 3 |
|:--|--:|--:|--:|--:|--:|
| Divisor | 4.00 | 3.43 | **2.86** | 2.29 | 1.71 |

At seven categories and a divisor of 4, maximum damage was **175 posture points**. E5 left five scoring
categories — the other two are context and can never penalise — so **leaving the divisor at 4 would have cut
maximum damage to 125 and made the model quietly more forgiving**: a larger *fraction* of the model would have
to fail before a vendor bottomed out. Nobody would have decided that; it would simply have happened.
`test_divisor_preserves_maximum_damage` counts scoring categories only and asserts the relationship.

The original calibration argument still holds underneath: a divisor equal to the category count is
algebraically the plain mean of the category postures, and that proved very forgiving of *concentrated*
failure — every benchmark vendor scored A (86–92), including one with 13 known-exploited product matches. The
current value is calibrated against the frozen corpus (`backend/tests/fixtures`). A genuinely severe *live*
critical is still handled non-compensatorily by the ceiling (§6).

**The order is not negotiable: gate → total → ceiling.** The gate is first because a blocked record has no score to
cap. The ceiling is last because its job is to correct the division's compensatory arithmetic — applying it earlier
would let the spreading dilute it again.

**The rule that keeps this honest:**

> **Missing data reduces *confidence*. It never changes *posture*.**

A signal that returns nothing is dropped from its category's coverage — never scored as a comfortable pass and
never as a penalty. **A vendor cannot look strong simply by being invisible**, and cannot be punished for silence
either; silence is a confidence problem, surfaced as such.

---

### 6 · The three differentiators (where normal subtraction stops)

Spreading the total over a divisor is *compensatory* — strengths dilute weaknesses. That is correct for hygiene
signals that genuinely trade off, and **wrong** for these three, which we keep deliberately.

**① Sanctions gate — emits nothing.** A sanctions / watchlist hit does **not** score badly or grade F — under the
Autonomous Sanctions Act 2011 s16(7) a weighted contribution is legally meaningless. The record is **blocked** and
routed to human adjudication. An entity too ambiguous to resolve (confidence < 0.5) blocks too — we never silently
score the wrong company. Matching is **whole-word** (so *asana* can't trip on *villaSANA*) and recall-tuned: this
is the one place recall beats precision.

**② Critical ceiling — non-compensatory (our knockout).** A **directly-observed current critical** — an expired
production certificate, seen live — **caps** the posture at the top of Grade D (49) so one severe live issue can't
be averaged away by good hygiene elsewhere. Only signals we observe as *current* auto-apply; a coarse KEV
name-match penalises but does **not** ceiling (it proves "this product line had a known-exploited CVE," not
"unpatched here"). A fired ceiling **bypasses the Ghost refusal** — a directly-observed critical is certain even on
thin coverage.

**③ The Ghost — refuse rather than mislead.** Below **40% evidence coverage** the product publishes **no grade**,
names the silent sources, and labels the vendor a Ghost. A clean-*looking* vendor we can't stand behind is a
designed refusal, not an error. (A high-*penalty* vendor with thin coverage is not refused — we found a real
problem — it surfaces flagged for review.)

**Weakest-link across assets.** A vendor is only as strong as its weakest exposed asset: the vendor posture is the
**lowest** asset posture, not the average. (The PoC scores the primary asset; multi-asset collection is roadmap.)

---

### 7 · Confidence — the second axis

Confidence is **evidence coverage first**: of the signals we planned to collect, how many returned data. A
bounded multiplier for the vendor's **operating history** is then applied — how much track record stands behind
the measurement (§7.1). It moves confidence only; posture arithmetic is untouched.

```
coverage        = signals_covered / signals_planned
confidence      = coverage × assurance_multiplier      (0.96 … 1.04, continuous)
confidence_band = High (≥0.90) · Medium (≥0.70) · Low (<0.70)
```

Posture is always read *with* confidence, never alone. A strong-looking posture on **Low confidence** is flagged
**The Ghost** — unassessed, not safe. This is the single most important honesty guarantee in the model: an 87 built
on thin evidence must never read like an 87 built on full coverage.

**Clean receipts count toward coverage.** "Checked and found nothing" must not read the same as "never checked". A
source that is successfully queried and comes back clean (HIBP no breach, KEV no product match) contributes to
coverage as a benign pass — this is what lifts a genuinely-clean vendor out of the Ghost quadrant without claiming
false certainty. Note this is the *only* thing a clean receipt does: it lifts confidence and **never** posture (§5).

#### The ceiling ramp — thin evidence caps how good a vendor may *look*

`refuse_below: 0.4` used to be the whole story: a cliff at 40%, and above it nothing. So a vendor seen through
four collectors could publish **100** and read identically to one seen through fourteen — which made *being
hard to observe* the cheapest route to a high score, the precise incentive this product exists to remove.

| Coverage | Published posture may not exceed | |
|:--|--:|:--|
| ≥ 0.90 | **100** | full collection — no cap |
| ≥ 0.75 | **97** | can still reach A, cannot be flawless |
| ≥ 0.60 | **90** | the top of A is not available on this evidence |
| ≥ 0.40 | **80** | B at best |
| < 0.40 | *not published* | the Ghost refusal (§6③) |

**It is a cap, never a deduction.** It touches no category penalty, so §5's honesty rule holds exactly as
before — missing data still costs no posture. What it limits is **the claim we are prepared to publish on the
evidence we hold**. The findings are the vendor's; the ceiling above them is ours.

**And the refusal below 0.40 is adverse, not neutral.** The config carries the required wording so the UI
cannot quietly soften it: *"this supplier could not be assessed from public sources, and it must not be read as
a clean bill of health."* A grey chip reading as neutral is the failure mode — a supplier nobody can see is a
supplier nobody has checked, and **that is a finding**.

**The bands are calibrated, not decorative.** All five benchmark vendors return **0.96–1.00** on a full
collection run and band **High**, so the ladder discriminates rather than pinning everything to Low. A
regression test asserts this: if a signal is ever added to the model with no collector to feed it, the
denominator grows, `High` becomes unreachable, and the build fails rather than quietly turning every vendor
into a Ghost.

---

### 7.1 · Operating history — continuous, and fenced off from posture

How long the entity has traded, on a **saturating curve** rather than a ladder of bands
([`backend/app/maturity.py`](../backend/app/maturity.py)):

```
maturity_index(y) = min(1, ln(1 + y) / ln(1 + 25))
```

| Years | 1 | 2 | 5 | 10 | 20 | 25+ |
|:--|--:|--:|--:|--:|--:|--:|
| index | 0.21 | 0.34 | 0.55 | 0.74 | 0.93 | 1.00 |

**Why a curve.** The previous model banded age into five rungs whose top one opened at ten years, so an
11-year-old vendor and a 40-year-old one were **byte-identical**, and a 2-year-old differed from a 40-year-old by
a single `low` — 3 penalty points, **0.75 posture** after the divisor, well inside the noise of a grade band.
The curve is steep where the difference is real (year one against year five is a genuine difference in
demonstrated continuity) and flat where it is not (year twenty-five against year forty is not), so
*diminishing returns on operating history* is a claim the arithmetic actually makes rather than one the prose
asserts. The band keys are **unchanged**, so every severity, reason and action in `scoring.yaml` still resolves;
the band is now a label and the index is what the model computes with.

**Sources are weighted, because age is purchasable.** An aged domain is bought at auction for a few hundred
dollars; a company inception date in a national register is not. So a registered inception (GLEIF, Companies
House, ABN, Wikidata P571) carries full weight and an RDAP domain-creation date is discounted to **0.6** — a
40-year domain with no corroborating register earns roughly what a 5-year registered company earns. The discount
is **one-directional**: it can only lower assurance, never manufacture it, and where sources disagree the engine
takes the most conservative reading.

**What the CURVE is allowed to change.** Confidence, and which baseline controls could yet exist (§7.2). It sets
no penalty of its own.

> **The continuous index never reaches a penalty.** `tests/test_maturity.py::test_maturity_never_reaches_a_penalty`
> asserts it, and the frozen corpus is unmoved.

**Be precise about the band, which is a separate and older thing.** `entity_maturity` *is* a scored signal:
`young_2_5`, `startup_lt_2` and `new_lt_1` each carry a **Low (−3)**, worth about **0.75 posture** after the
divisor, while `established_5_10` and `mature_gt_10` are a `pass`. So a vendor under five years old does carry
one small age-related deduction, and from five years upward age costs nothing. That predates the curve and is
deliberately unchanged. The claim worth making is the narrow one — *the continuous measure is confined to
confidence* — not the broad one that age never touches posture at all.

This is not squeamishness. The underlying research (context-aware vendor risk scoring, §1.4)
records the finding plainly — *"Company **age** predicts security posture: **No published evidence found**"* —
and §1.6 places maturity in Confidence and Benchmarking only. A firmographic multiplier on posture would make the
score non-comparable across vendors, unvalidatable against outcomes, and purchasable.

---

### 7.2 · Target maturity — the baseline that needs no peers

Peer benchmarking answers *"am I typical?"*. This answers *"am I adequate?"* — and the vendors where the two
**disagree** are the interesting ones. Configured in [`benchmarks.yaml`](../benchmarks.yaml) under
`target_maturity`, evaluated in [`backend/app/targets.py`](../backend/app/targets.py).

**Why both.** A percentile has two failure modes a cohort cannot fix from the inside. The peer pool is a
**convenience sample** of whatever this deployment happened to score, so a book skewed toward weak vendors
produces a flattering median and every comparison inherits the skew; and below the minimum peer count it
publishes nothing at all — precisely the position of a new deployment or a niche sector. A published baseline is
fixed and external, so it cannot drift with the portfolio and it **works at n=0 peers**.

**Every control names a real instrument, or it does not ship.** The loader refuses a control with no `basis`,
exactly as it refuses an `expected_posture` without one.

| Control | Expected | Basis |
|:--|:--|:--|
| DMARC | `p=reject` (partial: `p=quarantine`) | CISA **BOD 18-01** (Oct 2017) — `p=none` in 90 days, `p=reject` within one year |
| SPF | hard fail | CISA **BOD 18-01** — valid SPF on all second-level domains within 90 days |
| TLS version | 1.3 or 1.2 | **NIST SP 800-52 Rev. 2** (Aug 2019); **PCI DSS v4.0** req. 4.2.1 forbids SSL and early TLS |
| Certificate validity | valid | **NIST SP 800-52 Rev. 2** |
| HSTS | present | CISA **BOD 18-01** |
| Known-exploited CVEs | none matched | CISA **BOD 26-04** (10 Jun 2026), which revoked and replaced BOD 22-01 and BOD 19-02 |
| Vuln-disclosure programme | bug bounty (partial: `security.txt` only) | CISA **BOD 20-01** (Sep 2020) — VDP published by March 2021 |
| `security.txt` | present | **RFC 9116** (Apr 2022). *Not* mandated by BOD 20-01 — the directive requires the **policy**; RFC 9116 is the mechanism |
| Independent certification | registry-corroborated | **ISO/IEC 27001** Stage 1 + Stage 2 audit; **AICPA SOC 2 Type II** observation period |

Controls we could not source — DNSSEC and CAA among them — are **absent rather than asserted**. It is easy to
write a plausible baseline out of professional intuition and hang an official-sounding citation on it; that
produces numbers a client cannot trace, which is the failure this file exists to refuse.

**Scope, stated rather than implied.** Most of these bind US federal civilian agencies, not private vendors. They
are used as the strongest available *published, dated, checkable* statement of what a competent operator does —
never as a claim that a given vendor is legally bound by them.

**Attainability is not leniency.** `attainable_after_years` exists only where an artefact is **arithmetically
impossible** sooner: a SOC 2 Type II attests to controls operating *across* an observation window, so a company
younger than that window cannot hold one, and counting its absence would measure the calendar rather than the
vendor. Excluded controls leave the denominator and are **named** in the summary. It is *not* a grace period —
DMARC, SPF, TLS, certificate validity and HSTS cost engineering hours rather than years, small firms
under-adopt them badly (Inc. 5000 at 15.2% `p=reject` against Fortune 500 at 62.7%), and every vendor is held to
them from day one. A vendor whose age we could not determine is held to the **full** baseline, so being
unmeasurable is never a way to shed controls.

**Not observed is not failed**, and below `min_controls` observed nothing is published — the same two
disciplines the engine applies one level up.

---

### 8 · Assurity — the third axis

*Implemented in [`backend/app/assurity.py`](../backend/app/assurity.py); configured under `assurity:` in
[`scoring.yaml`](../scoring.yaml). Served at `GET /api/vendors/{ref}/assurity`.*

Posture cannot answer *"has anyone independent actually checked?"*. **"Their TLS is current and they have no
known breaches"** and **"an auditor has examined their controls"** are different claims, and a buyer needs
both. `synthetic_smallco` in the corpus is exactly the vendor where they diverge: **posture 97, assurity 13**.

```
Assurity = 100 × sigmoid( A₀ + Σⱼ creditⱼ − Σₖ γ · ComplianceGapₖ )
```

| Parameter | Value | Why |
|:--|--:|:--|
| `intercept` (A₀) | **−1.2** → ≈23/100 | A vendor with nothing observable sits at a **low intercept, not zero**. Unevidenced is not disproved, and a 0 would read as *audited and failed* |
| `scale` | 1.0 | sigmoid steepness |
| `min_observed_signals` | **3** | Below this, **nothing is published**. "2 of 3" assembled from whichever signals happened to return is the same false precision as a median over three peers |

**Absence never subtracts — enforced, not merely intended.** `_validate` rejects a negative credit *at load*.
This is the other half of E2's argument. E2 said "not doing what almost nobody does is not a failing" and
stopped `cert_posture.none_claimed` costing 8 points — a charge that fired on **five of five** corpus vendors,
which is a tax on audit budget rather than a measure of risk, falling hardest on exactly the small suppliers
this product exists to assess fairly. E2 could not say *"and doing it **is** a distinction"*, because
`penalty_for` returns zero or positive and the engine had no bonus path. This axis is that path.

**The credits** (abridged — full table in `scoring.yaml`):

| Signal | Band | Credit |
|:--|:--|--:|
| `cert_posture` | registry-corroborated | **+1.4** — an independently *verifiable* certification, the strongest signal here |
| `cert_posture` | claimed, uncorroborated | +0.2 — worth something, not much |
| `reporting_posture` | substantive | +0.9 — a real security report, not a landing page |
| `vd_program` | funded bug bounty | +0.8 — evidence of an operating security function |
| `program_disclosure` | detailed policies | +0.6 |
| `contactability` | DPO **and** security contact | +0.4 |
| `security_txt` | present | +0.2 |

**Why a sigmoid rather than a sum.** Bounded without a cliff at either end: the twentieth certification cannot
buy what the second did, and no vendor is ever pinned at 0 or 100 — so the axis keeps resolving differences at
both extremes.

> **Why it is a separate axis and not a posture bonus.** Credit for publishing a trust page must never buy back
> points lost to an expired certificate. Keeping them apart is what stops assurance theatre becoming a security
> score, and it is the same discipline that keeps confidence out of posture.

**Worked example — why "no gaps" doesn't mean equal scores.** Two vendors with zero compliance gaps still land
on different numbers, because the credits — not the absence of gaps — are the only thing driving the score
above baseline:

```
Vendor A: cert_posture registry-corroborated (+1.4) + program_disclosure detailed (+0.6) + security_txt (+0.2)
          = 2.2 credits → 100·sigmoid(−1.2 + 2.2) ≈ 73

Vendor B: same two, no security_txt
          = 2.0 credits → 100·sigmoid(−1.2 + 2.0) ≈ 69
```

The 4-point gap is one missing `security_txt: present` credit (+0.2) — "no gaps observed" only means neither
vendor *contradicted* a claim; it says nothing about how much positive evidence either one actually has.

**Independent verification, not self-report at face value.** Two collectors feed this axis at different
reliability: `trust_collector.py` (reliability 0.5) reads vendor-published claims off their own trust page —
explicitly marked *"claim, not evidence"* — while `registry_lookup_collector.py` (reliability 0.8) corroborates
against official company registries. A claimed-but-uncorroborated certification earns `claimed_unverified`
(+0.2); the same certification independently confirmed earns `registry_corroborated` (+1.4) — a 7× difference
in credit for the same fact, scaled by how much it should be trusted.

#### 8.1 · The compliance gap — the only thing that lowers assurity

*Implemented in [`backend/app/compliance_gap.py`](../backend/app/compliance_gap.py).*

A gap is **not an absence**. It is a vendor **asserting a framework** and then being **observed failing one of
its controls** — a statement about the reliability of their own claims, which is precisely what this axis
measures. Everything else on this axis only ever adds.

This is where E1's deleted sector expectation landed, correctly. `industry_profiles` used to *promote a
finding's severity by one step* when a sector cited a named instrument, so a missing DMARC record read as a
hygiene gap for a farm supplier and a live fraud exposure for a bank. That destroyed cross-vendor
comparability: the same evidence scoring differently because of a label **we** assigned. Compare:

> *"This DMARC finding is worth more points."* ← an opinion wearing a number
>
> *"Vendor is APRA-regulated and publishes no DMARC record; CPS 234 requires controls commensurate with the
> threat."* ← disputable, citable, actionable

The second changes no arithmetic. It states an obligation, names the instrument, names the observation, and
can be argued with — which the first cannot, because there is nothing to argue with except our judgement.

**Four disciplines the implementation enforces:**

- **Bound-by vs asserted are kept apart.** A framework applies either because the client told us the vendor is
  subject to it (`sector` — client-supplied, **never inferred**) or because the **vendor claims it**. Both are
  recorded, because they carry different weight in a conversation: one is a legal obligation the vendor cannot
  decline, the other is the vendor's own marketing. The asserted case is higher-signal precisely because gaming
  it means dropping the claim.
- **Which certification, not merely that there is one.** `cert_posture` bands say `claimed_unverified`, not
  `claimed ISO 27001`. Matching on the band alone would fire for every framework keyed to that signal, so a
  vendor claiming SOC 2 and nothing else would have been published as *"asserts ISO/IEC 27001:2022"* — us
  putting a claim in the vendor's mouth and then finding them short against it. Every `asserted_by` block must
  name `claim_contains`, matched against what the collector actually read off the trust page.
- **Distinct observations, not gap count.** A vendor asserting ISO 27001, SOC 2 and PCI DSS while negotiating
  TLS 1.0 breaches three frameworks with **one weakness**. Assurity charges it **once**; all three gaps are
  still reported. Charging three times would mean the axis punished a vendor for publishing more
  certifications, which is the opposite of what it measures.
- **Posture is untouched.** The underlying finding already charged whatever it charges. Charging it again here
  would be the double-count E3 spent a phase removing.

---

### 9 · Inherent risk and residual risk

*Implemented in [`backend/app/residual_risk.py`](../backend/app/residual_risk.py). Served at
`GET /api/vendors/{ref}/residual-risk`.*

Posture answers *"how strong is this vendor?"*. It cannot answer *"how much do we stand to lose if they
fail?"* — that depends on what **this buyer** has given them, which no amount of outside-in scanning can
observe. So the buyer declares it, and the two combine.

| Layer | Owner | Moves when |
|:--|:--|:--|
| **Posture** | Ours to measure | Their TLS moves — twice a quarter is normal |
| **Inherent** | **Theirs to declare** | The *relationship* moves, and not otherwise |
| **Residual** | Neither — a deterministic lookup | Either input moves |

**Inherent tier is `max(criticality, data_access_scope)` — never an average.** A low-criticality vendor with
production-data access is not a medium-risk vendor. Non-compensatory, like every other roll-up here.

**The published matrix — sixteen cells, argued over once, then fixed.** Rows are posture bands
(`strong ≥80 · moderate ≥60 · weak ≥40 · poor`), columns are inherent tiers:

| Posture ↓ / Inherent → | low | medium | high | critical |
|:--|:--|:--|:--|:--|
| **strong** | Low | Low–Med | Medium | Med–High |
| **moderate** | Low–Med | Medium | High | High |
| **weak** | Medium | High | High | Critical |
| **poor** | Med–High | High | Critical | Critical |

Three properties of that table are deliberate:

- **A strong posture never reaches Low at high inherent exposure.** An A-grade vendor holding your production
  data lands at Medium. They are still holding your production data, and the day their posture moves you
  discover how much was riding on it.
- **Undeclared is not Low.** A relationship nobody has classified routes to the **deepest** assessment, not the
  shallowest — the vendors nobody has got round to classifying are disproportionately the ones nobody has
  looked at.
- **Sole-source escalates one band.** If the relationship has no substitute, the cell moves one rung up the
  ladder, and the response names that this happened.

**Residual is recomputed on read and stored nowhere.** It is a lookup over two things that are each stored, so
it can never drift from the inputs it was derived from. It is also **advisory**: it states what the evidence
and the declared exposure together support. The client decides.

---

### 10 · Peer benchmarking — am I typical?

*Implemented in [`backend/app/benchmarking/`](../backend/app/benchmarking/), configured under `benchmarking:`
in [`benchmarks.yaml`](../benchmarks.yaml), served under `/api/v2/suppliers/{ref}/…`. Design notes:
[`design_decisions.md`](design_decisions.md) Part 1.*

**`n` travels with every figure, and the refusal is the figure.** Not a greyed-out number, not a dash that
reads as a rendering bug — the sentence, with the actual `n` in it.

| Resolution | Floor | Why that number |
|:--|--:|:--|
| **Percentile** | **n ≥ 30** | The conventional floor for treating a sample percentile as a point estimate. Below it the sampling error is wider than the gap between adjacent percentile labels |
| **Quartile** | **n ≥ 8** | Below this a single peer is more than an eighth of the population, so "bottom quartile" can flip on one supplier joining |
| Below 8 | — | **Insufficient peer data**, with the `n` stated. Read the absolute posture |

Both floors are **enforced in code**, not only in YAML. A YAML edit may raise them; it may not lower them.
That is not paranoia: the superseded v1 module shipped `min_cohort_n: 1`, and *"make it 3 for the demo"* is
exactly how a demo setting survives into production, where it is indistinguishable from a decision nobody made.

**The cohort is a widening ladder, and every rung it tried is published** with that rung's `n` — because
"which peers?" is the only question anyone actually asks about a benchmark. `sector + size + delivery model`
first, then `sector + size`, then `sector`. **There is deliberately no rung meaning "every supplier ever
assessed"**: a comparison against everything is not a peer group. When the ladder widens, the card says so on
its face, because a comparison against a wider population is a weaker claim.

**Comparison reliability is published separately from confidence.** They are different facts: a
well-evidenced supplier can sit in a poorly-supported peer group. Reliability combines sample adequacy, how
exact the winning rung was, how well-evidenced the peers themselves are, and freshness.

**Per-domain discrimination is stated on every row.** A domain where every peer scores 100 cannot rank
anybody, and presenting a rank among identical values manufactures signal from a constant. Each domain is
labelled *discriminating*, *peers barely differ*, or *too few peers to test*.

**A snapshot is frozen when published.** The percentile trend reads points that were true when taken, never
today's cohort against an old posture — otherwise the cohort's movement gets attributed to the supplier.
Snapshots are member-bearing internally and every tenant-facing path calls `.public()`, which structurally
cannot carry peer refs.

**The cohort is disputable; the placement is not.** The cohort, snapshot and resulting placement are
deterministic lookups over the inputs and carry no independent judgement. Dispute an *input* — sector, size
band, delivery model, headcount, revenue.

#### 10.1 · The expectation gap — am I what my peer group predicts?

`Posture − E[Posture ∣ cohort]`, with the observations that account for it. The sentence this whole subsystem
exists to produce:

> *"Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group. The gap is driven
> by dmarc (absent) — 12 of 14 peers are not in this band."*

A buyer handed `−19` has a fact. A buyer handed `−19, driven by DMARC, which 12 of 14 of their own peers
publish` has a **remediation** — and one they can take to the vendor with a count of the vendor's own peer
group attached, rather than an opinion of ours.

Two disciplines:

- **The drivers are ranked, not a decomposition**, and the response says so. Since E7a what a finding costs
  depends on what else was charged alongside it, so per-signal attributions **do not sum to the gap** and no
  arrangement of them can be made to. A reader who adds them up and finds they miss has caught a real property
  of the model, not a bug.
- **Constants are excluded and named.** A signal that does not vary across the cohort is not a comparison
  there; reporting it as a driver would dress a constant as a difference.

---

### 11 · Every deduction has a sentence

A score a client cannot have explained to them is the thing this product exists **not** to produce. So every
band that costs points carries a plain-English reason in [`scoring.yaml`](../scoring.yaml), written
**consequence first**:

```yaml
reasons:
  dmarc:
    absent: "Anyone can send email pretending to be this company. There is no published rule
             telling mail servers to stop it, which is the standard opening move in invoice
             fraud and staff impersonation."
```

"Anyone can send email pretending to be this company" is what a procurement lead reads; *"no DMARC record"* is
the supporting fact and sits underneath. The page stops needing a translator.

**The loader refuses to start if a penalising band has no reason** — and equally if a reason exists for a band
that doesn't. All **57** penalising bands are covered. The explanation can't silently fall behind the model.

**Adjustments are shown, not hidden.** The receipts also state *why* a charge differs from the base penalty —
which is the most defensible thing the model does and used to be invisible:

> *Customer passwords were exposed in a confirmed public breach.* **−16**
> This is historic, so it counts for less than a recent finding would — at full weight it would have been −40.

> *A product this company is associated with appears on the register of vulnerabilities actively exploited in
> the wild.* **−27.1**
> 13 matches found — only the most serious one is counted, so a long list of name matches cannot inflate the score.

Note the second sentence is *not* "counted once as a pattern" — CVE bags are frequency-**exempt** (§4), and the
UI must not describe a calculation that never ran.

---

### 12 · Worked example — a real vendor, reproducible

Not a toy. **Atlassian**, as it stands in the live store. Re-run the frozen-corpus version with
`python -m tests.regolden`.

| Category | Kind | Penalty | Posture |
|:--|:--|--:|--:|
| Breach & Compromise History | scoring | −33.62 | 66 |
| Attack Surface & Hygiene | scoring | −21.05 | 79 |
| Identity & Email | scoring | −1.50 | 98 |
| Transparency | scoring | −1.50 | 98 |
| Compliance & Regulatory | scoring | −1.50 | 98 |
| Continuity Context | context | 0 *(cannot penalise)* | 100 |
| Assurance Context | context | 0 *(cannot penalise)* | 100 |
| **Total** | | **−59.17** | |

**Overall = 100 − 59.17 ÷ 2.86 = 79 (B)**, at **100% coverage / High confidence**.

Beside it, on their own axes: **assurity 82** from 8 observed signals with **no compliance gaps**, and a peer
placement of **9th percentile, ranked 36 of 39** against a `sector=technology` cohort — with an expectation
gap of **−11** driven by `kev_listed_cve`, which **28 of its 39 peers** avoid.

That cohort clears **n ≥ 30**, so a percentile is published rather than a quartile — but only because the
peer group was populated. The same vendor read *"insufficient peer data, n=3"* until the scoring pipeline
began recording cohort attributes (§10); the peers had been assessed all along and were simply not in the
table the cohort query reads.

Read those together and the record says something no single grade can: this vendor is well-documented and
publishes what it claims (assurity 82), it is not carrying an assurance problem, and its posture deficit
against its own peer group has **one named cause**. That is a conversation to have with the vendor, not a
letter to file.

Two mechanisms are visible in the breach figure. KEV product matches collapse to **one** penalty
(frequency-exempt worst-of, §4), and that survivor decays with age. Under the pre-4.2.0
mean-of-covered-categories this vendor scored **90 (A)** — *"robust posture, few or no external issues"* while
carrying 13 known-exploited product matches. That is the leniency the fixed divisor corrects.

*Change one fact — the certificate is expired and serving production — and the **critical ceiling** fires:
Attack Surface & Hygiene collapses, and the published posture is capped at **49 (Grade D)**, cause named,
regardless of the good hygiene elsewhere.*

---

### 13 · Honest about what this simplifies

- **Perimeter ≠ posture.** OSINT measures what a stranger can see; a perfect header score is fully compatible with
  a bad internal posture. It's a proxy, labelled as one.
- **No live-blocklist / open-port visibility (a deliberate v1 constraint).** Active port-scanning risks an
  unauthorised-access classification, and the obvious feeds (Shodan/Censys free tiers) bar commercial use. We proxy
  attack surface via Certificate Transparency (certs *issued*, not ports *open*) and own the gap.
- **Coverage tracks *size*, not *risk*.** Big vendors publish more, so they surface more signal. The confidence
  axis mitigates this — it does not cure it. Read the confidence band, not the grade alone.
- **Peers are a convenience sample, not the industry.** Every cohort is built from vendors this deployment
  happened to score, so a skewed portfolio produces a skewed median. The target maturity baseline (§7.2) exists
  to give a reading that does not inherit that bias; the placement still does, and says so on the card. The
  `n ≥ 30` / `n ≥ 8` floors (§10) bound how confidently the skew can be stated — they do not remove it.
- **The expectation gap's drivers are ranked, not apportioned.** They will not sum to the gap, by construction
  (§10.1). Anyone reading them as a decomposition will conclude the arithmetic is broken; it is not, and the
  response says so in its own caveats.
- **Assurity measures observable assurance, not security.** A vendor can hold every certification listed and
  still be poorly run. It is published on its own axis precisely so that it can never be mistaken for, or
  averaged into, a security judgement.
- **Residual risk is advisory.** It states what the evidence and the declared exposure together support. It
  does not make the decision, and it is only ever as good as the declaration behind it (§9).
- **Operating history is a weak signal, carried weakly.** No authoritative source scores by founding date, so
  age is confined to a bounded confidence multiplier and to control attainability — never to posture (§7.1).
- **Fixed penalties are blunter than a calibrated curve** — four tiers, deliberately, because they are easier to
  defend and tune than a continuous deduction curve.
- **We score entities, not people.** Executive/brand risk, PEP screening, person-level ownership, and demographic
  signals are excluded at a bright line (§4.2: APP 10, the privacy tort, EU AI Act Art 6(3)) — logged with a
  reason in `excluded_signals`, never silently dropped.

---

#### See also

- [`scoring.yaml`](../scoring.yaml) — the machine-readable model (the actual deliverable)
- [`methodology.md`](methodology.md) Part 1 §5 — full derivation, legal basis, and benchmark defence
- [`methodology.md`](methodology.md) Part 3 — per-source reliability, legality, and limits
- Part 2 of this document — the per-metric arithmetic, every constant read from code

---

## Part 2 · Metrics reference

*Where configuration and code disagree, that is called out explicitly rather than smoothed over.*

This document explains the metrics the OSINT TPRM Module publishes, the theory each one rests on,
and the arithmetic actually implemented in the code. Every constant quoted here was read from
`scoring.yaml` or the module named beside it — where configuration and code disagree, that is
called out explicitly rather than smoothed over.

Model version: `scoring.yaml` `version: 5.4.0`, `model: penalty_subtractive`.

### Overview

The module deliberately reports several **separate axes** rather than one blended number, because
each answers a different question and blending them destroys the ability to act on any of them:

| Axis | Question it answers | Where it is computed |
|---|---|---|
| **Posture** | How exposed is this vendor to compromise? | `scoring/engine.py` |
| **Confidence** | How much of the evidence we would *expect* for a company like this did we find? | `confidence_calculator.py` |
| **Business Stability** | How likely is this vendor to still be trading? | `business_stability.py` |
| **Assurity** | How much *independent* assurance stands behind their claims? | `assurity.py` |
| **Longevity / Maturity** | How long have they operated, and how well is that evidenced? | `longevity.py`, `maturity.py` |
| **Lifecycle** | What organisational stage are they in? | `lifecycle.py` |

#### The theoretical commitment behind separate axes

This is a **multi-attribute decision model with deliberately non-compensatory aggregation across
axes**. In MCDA terms, a fully compensatory model (weighted sum of everything) allows a strong
attribute to buy back a weak one. That is the wrong property here: a published trust page must
never offset an expired production certificate, and financial distress must never read as a
security failing. Each axis is therefore aggregated internally (partially compensatory, with
limits) and **never** across axes.

Two structural rules follow, and both are enforced in arithmetic rather than by convention:

1. **Missing data reduces Confidence, never Posture.** The posture divisor is fixed by the model,
   so a silent collector contributes no penalty *and* cannot move the denominator.
2. **Absence never subtracts on Assurity.** Not holding a certification is not a finding. The
   only thing that subtracts on that axis is a *compliance gap* — a vendor asserting a framework
   and being observed failing a control inside its scope.

---

### 1. Posture Score

#### What it measures

The strength of a vendor's externally observable security posture — how exposed they are to
compromise, on public evidence only.

#### Theoretical model

A **subtractive penalty model**, not a weighted-additive scorecard. Every vendor starts at 100 and
each observed issue subtracts. The property this buys is the important one: a signal that returned
nothing contributes nothing, so the model cannot reward opacity or punish a vendor for being
hard to observe. There are **no category weights at all** — influence emerges from what was found,
which is the point of a penalty model.

The severity ladder and the aggregation decay are **expert judgement, not calibrated values**, and
`scoring.yaml` requires them to be labelled as such wherever they are published. Calibration
requires outcome labels, which this deployment does not yet collect.

#### Scale

- **0–100** (100 = strongest, 0 = weakest)
- **Grades** (`scoring.yaml grades`): **A ≥ 85 · B ≥ 70 · C ≥ 50 · D ≥ 30 · F ≥ 0**

#### Severity ladder (`severity_penalties`)

| Severity | Penalty | Example |
|---|---:|---|
| Critical | **50** | expired production cert, unpatched KEV, CVSS 9–10 |
| High | **20** | no DMARC, TLS 1.0/1.1, confirmed breach of personal data |
| Medium | **6** | weak TLS, `p=none`, missing SPF, CVSS 4–6.9 |
| Low | **1.5** | missing security header, no DNSSEC, CVSS 0.1–3.9 |
| Informational | **0** | recorded but **not scored** — unverifiable observations |

Critical : Low is **33.3 : 1**. This ratio was widened deliberately (E7b). At the old ladder,
four Medium plus eight Low findings (56 points) outranked one Critical (40) — a dozen missing HTTP
headers beating an actively-exploited vulnerability at 0.71 : 1. Widening alone only reaches
1.39 : 1; it ships with rank decay (below) because neither half is sufficient. Together: **3.06 : 1**.

#### Categories (`scoring.yaml categories`)

**Five scoring categories** — these can penalise:

1. **`breach_compromise_history`** — realized > exploited > theoretical
   (`breach_by_data_class`, `kev_listed_cve`, `nvd_cve`)
2. **`attack_surface_hygiene`** — the estate and how well it is kept
   (`tls_version`, `cert_validity`, `hsts`, `csp`, `x_frame_opts`, `dnssec`, `caa`,
   `subdomain_estate`, `stale_hosts`, `weak_issuance`, `estate_tls_legacy`, `estate_cert_expired`)
3. **`identity_email`** — can this vendor be impersonated? (`dmarc`, `spf`, `dkim`)
4. **`transparency`** — can this vendor be *told* about a vulnerability? (`vd_program`, `security_txt`)
5. **`compliance_regulatory`** — claim reliability, not audit budget (`cert_posture`, `regulator_action`)

**Two context categories** — they count toward coverage but contribute **exactly zero** to posture
by construction:

6. **`continuity_context`** — will this vendor still be trading? (`entity_status`, `entity_existence`,
   `entity_maturity`, `domain_registration`, `sec_filing`, `sec_going_concern`, `insolvency_notice`,
   `bankruptcy_petition`)
7. **`assurance_context`** — `contactability`, `program_disclosure`, `reporting_posture`

Context categories exist rather than the signals being deleted because `planned_signal_count` is
the coverage denominator (**27** signals). Deleting them would raise every vendor's confidence for
no evidential reason — the check still ran, we would simply have stopped recording it.

#### Per-finding modifiers (`modifiers`)

Applied to each finding before aggregation:

- **Age decay** — `0.5 ^ (months / 36)`, floored at **0.15**. A three-year half-life on historic
  occurrences. `cert_validity` is in `never_decays`: a certificate's `notAfter` is a *state
  boundary*, not an event, so decaying it made a cert expired six years ago cheaper than one
  expiring next week.
- **Frequency** — `1 + 0.25 × (n − 1)`, capped at **2.0**. Three breaches are a pattern (×1.5),
  not one breach counted three times. `kev_listed_cve` and `nvd_cve` are exempt: a bag of
  keyword-matched CVEs is coarse-match noise, not distinct events.
- **Mitigation** — **×0.6**, applied only where remediation is *evidenced*, and applied once.

#### Aggregation within a category (`aggregation.decay = 0.7`)

```
CategoryPenalty(c) = Σᵢ pᵢ × 0.7^(rankᵢ − 1)      # ranked by descending penalty
```

**Rationale.** The tenth missing header on a vendor already missing nine tells you almost nothing
new — you already know nobody is minding the headers. Charging it in full counts one organisational
fact ten times. Rank decay expresses diminishing informational return, and it is applied **within**
a category only: a cross-category discount would let a vendor's worst category be cheapened by
their second-worst, which is precisely the compensatory behaviour the critical ceiling exists to
prevent.

Two prior steps protect the ranking:
- **Worst-of collapse** — every `(category, signal)` group contributes one penalty, its worst
  member *after* decay. So a fresh High can outrank a long-decayed Critical.
- **Root-cause deduplication** — one remediation ticket, one penalty. Patching a KEV-listed CVE
  fixes the NVD finding in the same action. Suppression zeroes the *penalty*, never the *evidence*.

#### Final posture

```
Posture = 100 − ( Σ_categories min(penalty, 100) ) / 2.86
```

**Why a fixed divisor.** It is *not* a mean over the categories that answered. Averaging only
answering categories made a clean trust page worth +23 posture, because each clean category entered
the average as a 100 and pulled it up — silence changing the score, which is exactly what
"missing data never changes posture" forbids.

**Why 2.86 specifically.** `divisor(n) = n × (4/7)` holds maximum damage constant at 175 posture
points regardless of how many scoring categories exist. Five scoring categories → **2.86**. Leaving
it at the old 4 would have cut maximum damage to 125 and made the model *quietly more forgiving*
without anything visibly failing. Asserted by `test_divisor_preserves_maximum_damage`.

Category-level posture shown in the breakdown is `100 − category_penalty` (undivided).

#### Non-compensatory overrides

- **Gates (emit nothing).** Entity resolution confidence < **0.5**, a sanctions hit, or a
  configured finding gate (`entity_dissolved`) **BLOCKS**: no posture, no grade, routed to a human.
  A gate is not a low score — a vendor with a disqualifying finding publishing 60 clears a
  ">= 50" procurement threshold and gets onboarded by a rule nobody re-read.
- **Critical ceiling (caps, never sets).** A directly-observed current critical caps posture at
  **49** — the top of Grade D. Armed only by `cert_validity` on the **apex host**
  (`auto_signal_scope`); arming on any host in a fanned-out estate would cap every large vendor on
  one abandoned staging certificate, and a non-compensatory response that fires constantly is one
  nobody reads. `kev_listed_cve` and `breach_by_data_class` require human confirmation to arm.
- **Confidence ceiling ramp** — see §2.
- **Refusal (the Ghost).** Confidence < **0.40** → posture is **not published**. Per
  `insufficient_evidence_is_adverse: true`, this is an **adverse** result, not a neutral one, and
  the UI is required to render it that way.

#### Log-odds preview (E13, not published as posture)

`max(0, …)` means a vendor at three times the cap and one at six times both publish 0, so the model
cannot rank the worst suppliers in a book. A bounded log-odds transform with shrinkage toward a
peer rate (`scoring/log_odds.py`) is computed **alongside** as a preview field. It refuses whenever
`L_peer` would come from fewer than eight real peers — shrinking an under-evidenced vendor toward
invented postures is worse than not shrinking at all.

---

### 2. Confidence Score

#### What it measures

Not "how much data did we get" but: **what percentage of the evidence we would expect to exist for
a company like this did we actually find?**

#### Theoretical model

The naïve formulation `found / all_possible` embeds a systematic bias: it penalises young and
small companies for lacking evidence they could not yet have produced. A two-month-old startup has
no five-year SOC 2 observation window, and no SEC filings, and cannot acquire either by trying
harder.

The implemented alternative is a **conditional expectation ratio** — the denominator is the
evidence set expected *given the vendor's profile*, so an unattainable signal never enters it:

```
Confidence = Σ weights(expected ∧ found) / Σ weights(expected)      # capped at 1.0
```

This is the same principle as `attainable_after_years` in `benchmarks.yaml`: measure vendors
against what is attainable for them, not against an absolute footprint.

#### Scale

- **0.0–1.0**
- **Bands** (`confidence.bands`): **High ≥ 0.90 · Medium ≥ 0.70 · Low < 0.70**
- Below **0.40** (`refuse_below`) nothing is published.

#### Signal expectations (`confidence_config.py`)

**Always expected — attainable day 1, total weight 108:**

| Signal | Weight | | Signal | Weight |
|---|---:|---|---|---:|
| `domain_registration` | 15 | | `dmarc` | 12 |
| `entity_status` | 15 | | `spf` | 8 |
| `cert_validity` | 12 | | `dkim` | 5 |
| `entity_existence` | 10 | | `hsts` | 5 |
| `tls_version` | 10 | | `csp` | 5 |
| `dnssec` | 5 | | `x_frame_opts` | 3 |
| `caa` | 3 | | | |

**Scales with age** — expected only past a minimum operating age:

| Signal | Weight | Expected after |
|---|---:|---|
| `insolvency_notice`, `bankruptcy_petition` | 15, 15 | 1 year |
| `kev_listed_cve`, `nvd_cve` | 15, 10 | 1 year |
| `security_txt`, `contactability` | 5, 8 | 1 year |
| `regulator_action` | 20 | 2 years |
| `breach_by_data_class` | 15 | 2 years |
| `vd_program`, `program_disclosure`, `reporting_posture` | 12, 10, 8 | 2 years (and ≥ small) |
| `sec_filing` | 20 | 2 years (and ≥ medium, US only) |
| `cert_posture` | 15 | 3 years (and ≥ small) |

**Scales with size** — `subdomain_estate` (8), `stale_hosts` (10), `estate_tls_legacy` (10),
`estate_cert_expired` (10) require ≥ medium; `weak_issuance` (8) requires ≥ small.

#### Expected-weight denominators (computed from the code)

| Operating years | Band | Size unknown | Size small | Size medium+ |
|---|---|---:|---:|---:|
| 0.5 | startup | 108 | 116 | 154 |
| 1.5 | startup | 176 | 184 | 222 |
| 2.5 | young | 211 | 249 | 307 |
| 3.5+ | young → veteran | 211 | 264 | 322 |

The denominator **plateaus at three years** — past that, age adds no further expectations and only
size does. Note that an **unknown size band is treated as the smallest**, so every size-gated
signal drops out of the denominator; this is conservative but it means confidence for a vendor with
no size evidence is computed over a materially smaller expected set.

#### Worked comparison

- **Startup, 0.5 years, size unknown, all 13 always-expected signals found** → 108/108 = **100%**.
- **Veteran, 15 years, size unknown, only the always-expected 13 found** → 108/211 = **51.2%** (Low).

A veteran missing financial filings is penalised; a startup missing the same filings is not,
because they are not yet expected. The differentiation is produced by the denominator, not by a
flat penalty table.

#### Signal statuses

Only `FOUND` and `NOT_FOUND` move the number. `SEARCH_FAILED` (our collector broke),
`NOT_APPLICABLE` and `NOT_CHECKED` are excluded from **both** numerator and denominator — our
infrastructure failing is not the vendor's evidence gap. Signals the run *planned* and got nothing
for are reclassified as `NOT_FOUND`: planned means attempted, and attempted-and-absent is exactly
what a reader needs itemised.

#### Confidence ceiling ramp (`confidence.ceiling_ramp`)

Thin evidence caps how good a vendor may **look** — a cap, never a deduction, so no category
penalty is touched:

| Coverage ≥ | Posture ceiling |
|---|---:|
| 0.90 | 100 (no cap) |
| 0.75 | 97 |
| 0.60 | 90 |
| 0.40 | 80 |
| < 0.40 | not published |

Before this ramp there was a single cliff at 40%: a vendor seen through four collectors could
publish 100 and read identically to one seen through fourteen, making *being hard to observe* the
cheapest route to a high score.

#### Fallback path

If the age-based calculation raises, `scoring/engine.py` falls back to raw coverage
(`covered / planned`) multiplied by a bounded assurance multiplier derived from `entity_maturity`
(floor **0.40**, ceiling **1.04**). When multiple maturity observations exist, the **most
conservative** multiplier wins, so an old domain in front of a young company cannot buy assurance
the company has not earned.

#### Deduction labels

Each gap carries a human-readable label and category — e.g. "DMARC email authentication missing"
(`email_security`, −12), "SEC regulatory filings missing" (`financial_transparency`, −20). Impact
is banded: high ≥ 15, medium ≥ 8, low otherwise.

> **Known defect.** `ConfidenceCalculator.calculate_from_profile` passes `profile.sector` into the
> `jurisdiction` parameter. For `sec_filing` (the only `jurisdiction_required` signal) any
> non-US-looking value drops it from the denominator. Harmless while size is unknown, since
> `sec_filing` is size-gated anyway, but wrong for medium+ vendors.

---

### 3. Business Stability Score

#### What it measures

Financial health and continuity — will this vendor still be trading? Deliberately separate from
posture: **a bankrupt company can have excellent security controls, and a secure startup can run
out of cash.**

#### Theoretical model

Age-anchored base score plus evidenced adjustments. The age anchor rests on the **liability of
newness** (Stinchcombe, 1965): young organisations face materially higher hazard rates because
they must build roles, routines and external trust from nothing while consuming scarce resources.

**Real-world survival base rates.** US Bureau of Labor Statistics Business Employment Dynamics
establishment survival data supports, approximately:

- ~**20%** of new establishments fail within the first year
- ~**50%** survive to five years
- ~**33%** survive to ten years
- surviving cohorts show a **declining hazard rate** — the longer a firm has traded, the lower its
  annual failure probability, which is what justifies survivorship credit

These are establishment-level US figures used as a **proxy** for entity survival, not a fitted
model of any specific vendor. They set the shape of the base curve; they are not a prediction.

**Explicitly out of scope:** Altman Z-score, cash burn, funding runway, D&B-style credit scoring
and any natural-person financial data. Computing an in-house distress index from scraped
fundamentals is credit-rating territory and defamation-adjacent when wrong. These sit on
`held_roadmap` (see `continuity.py`).

#### Scale

- **0–100**, or **None** when gated
- **Standing**: sound ≥ 80 · watch ≥ 60 · impaired ≥ 40 · ceased < 40 (or gated)

#### Gate logic (checked first, blocks scoring)

- Any insolvency record with `status == "active"` → **BLOCK**
- Company status in {`liquidation`, `administration`, `receivership`, `dissolved`} → **BLOCK**

A gate returns `score: None` with a stated reason. Historical insolvency is a penalty, not a gate.

#### Base score by age band (`longevity.py base_age_score`)

| Band | Years | Base | `base_adjustment` | **Effective base** |
|---|---|---:|---:|---:|
| startup | < 2 | 50 | −30 | **20** |
| young | 2–5 | 65 | −20 | **45** |
| established | 5–10 | 80 | 0 | **80** |
| mature | 10–20 | 90 | 0 | **90** |
| veteran | 20+ | 100 | 0 | **100** |
| unknown | — | 60 | not applied* | **60** |

\* `_apply_age_based_adjustments` returns early for `unknown`, so neither the −15 adjustment nor
any multiplier is applied.

#### Financial penalties (`_apply_financial_penalties`)

| Signal | Penalty | Source |
|---|---:|---|
| Going-concern language | 25 | SEC EDGAR — the vendor's own auditor doubting continuity |
| Historical insolvency, ≤ 3 years ago | 20 | resolved but recent |
| Historical insolvency, > 3 years ago | 5 | minor |
| Revenue declining across recent periods | 15 | every consecutive period lower |
| Debt-to-equity > 3 | 10 | latest period |
| Debt-to-equity > 2 | 5 | latest period |
| Negative net income across last 2 periods | 15 | net income used as a cash-flow proxy |

Only one historical-insolvency penalty is charged. `scoring.yaml` additionally declares
`voluntary_arrangement` (15), `declining_profitability` (10), `high_customer_concentration` (10)
and `no_recent_funding_18_months` (5) — **these are declared but not yet wired** in
`business_stability.py`.

#### Survivorship bonus and age multipliers

Bonus: mature **+5**, veteran **+10**, others 0 (a further +5 for surviving a known downturn is
implemented in `survivorship_bonus` but not currently invoked by the engine).

| Band | Penalty × | Bonus × |
|---|---:|---:|
| startup | 1.5 | 0.5 |
| young | 1.2 | 0.7 |
| established | 1.0 | 1.0 |
| mature | 0.9 | 1.2 |
| veteran | 0.8 | 1.5 |

The asymmetry is the theory made arithmetic: a young firm has less balance-sheet buffer, so the
same distress signal is worse; a veteran has demonstrated it can absorb shocks, so the same signal
is less predictive of exit.

```
Business Stability = clamp(0, 100, effective_base − Σ(penalties × mult) + Σ(bonuses × mult))
```

#### Outcomes with no adverse financial evidence at all

| Band | Score | Standing |
|---|---:|---|
| startup | **20** | ceased |
| young | **45** | impaired |
| established | **80** | sound |
| mature | **96** | sound |
| veteran | **100** | sound |
| unknown | **60** | watch |

> **⚠️ Two divergences that need a decision.**
>
> 1. **Config and code disagree on the base curve.** `scoring.yaml`
>    `business_stability.age_base_scores` reads 70/75/80/85/100/60 and its
>    `confidence_adjustments` read −0.15/−0.10. The runtime path
>    (`business_stability.py` → `longevity.py`) reads 50/65/80/90/100/60 and −0.60/−0.50, and never
>    loads the YAML block. **The code wins at runtime; the YAML block is inert.** `methodology.md` Part 1
>    documents the YAML numbers and is therefore describing values that never execute.
> 2. **A clean startup is labelled "ceased".** With zero adverse findings, a <2-year-old vendor
>    scores 20 and lands in the same standing as a company in liquidation. That is a base-rate
>    prior being reported in vocabulary reserved for an observed outcome, and it contradicts
>    `lifecycle.py`'s own caveat: *"A young company is not thereby an impaired counterparty — that
>    is the founding-date scoring this system refuses."* Either the base curve or the standing
>    thresholds should move.

#### Age differentiation profile (`age_risk_factors.py`)

Alongside the score, six dimensions are banded for narrative context:

| Dimension | Bands |
|---|---|
| Historical depth | sparse · limited · moderate · rich · extensive |
| Financial transparency | opaque · limited · partial · transparent · comprehensive |
| Leadership risk | founder_dependent/high · moderate · low · stable |
| Operational maturity | immature · developing · mature · established · legacy |
| Media velocity | unknown · low · moderate · high · critical |
| Structural change | neutral · low · moderate · high_suspicion |

The same observation is read differently by age — a name change at 18 months is normal
repositioning; three name changes and two address changes at 20 years is a suspicion signal.
Several inputs (leadership history, media counts, structural changes) are **currently passed as
placeholders** from `business_stability.py` and are not yet collector-fed.

---

### 4. Assurity Score

#### What it measures

**Independent assurance** — how much externally verifiable evidence exists that a security
programme is audited and operating. It is explicitly *not* a security score.

#### Theoretical model

```
Assurity = 100 × σ( intercept + scale × Σ credits − γ × compliance_gaps )
```

where `σ(x) = 1 / (1 + e^(−x))`.

**Why this axis exists.** Before it, the model expressed assurance by *subtracting* for its
absence — `cert_posture.none_claimed` cost 8 points and fired on five of five corpus vendors. That
is a tax on audit budget, not a measure of risk, and it fell hardest on exactly the small suppliers
this product exists to assess fairly.

**Why a sigmoid rather than a sum.** The logistic function is bounded without a cliff at either
end and is monotone in the credit sum. The twentieth certification cannot buy what the second did
(saturation), and no vendor is ever pinned at exactly 0 or 100 — so the axis keeps resolving
differences at both extremes, which is precisely the defect the log-odds work exists to fix for
Posture. Credits are additive in **log-odds** space, which is the natural space for combining
independent pieces of evidence.

**Absence never subtracts — enforced, not intended.** `_validate` rejects a negative credit at load
time. A vendor with nothing observable sits at the intercept, which is deliberately **low rather
than zero**, because unevidenced is not disproved and a 0 would read as *"audited and failed"*.

#### Parameters (`scoring.yaml assurity`)

- `enabled: true` · `intercept: −1.2` · `scale: 1.0` · `gamma: 0.8` · `min_observed_signals: 3`
- **Published range: 23 → 97.** Floor = σ(−1.2) ≈ 0.231. Ceiling = σ(−1.2 + 4.8) ≈ 0.973.

#### Credit table

| Signal | Band | Credit |
|---|---|---:|
| `cert_posture` | `registry_corroborated` | **1.4** |
| `cert_posture` | `claimed_unverified` | 0.2 |
| `reporting_posture` | `substantive` | 0.9 |
| `reporting_posture` | `partial` | 0.3 |
| `vd_program` | `bug_bounty` | 0.8 |
| `vd_program` | `security_txt_only` | 0.3 |
| `program_disclosure` | `detailed_policies` | 0.6 |
| `program_disclosure` | `marketing_only` | 0.1 |
| `contactability` | `dpo_and_security_contact` | 0.4 |
| `contactability` | `partial` | 0.1 |
| `dnssec` | `valid` | 0.3 |
| `security_txt` | `present` | 0.2 |
| `caa` | `present` | 0.2 |

The gap between `registry_corroborated` (1.4) and `claimed_unverified` (0.2) is the axis's whole
thesis: an independently verifiable certification is worth seven times a marketing claim.

#### The only subtraction

A **compliance gap** (γ = 0.8 each) — the vendor asserting a framework and being observed failing a
control within its scope. That is a statement about the reliability of their own claims, which is
exactly what this axis measures. A compliance gap **never touches Posture**. It is high-signal
precisely because the way to game it is to drop the claim, which is itself informative.

#### Publication threshold

Below **3 observed signals**, nothing is published. "2 of 3" assembled from whichever checks
happened to return is the same false precision as a median over three peers.

Note that `observed` counts signals that were **checked**, whether or not they evidenced anything —
a checked-and-empty signal is a real observation, and is still not a subtraction.

#### Age handling

Age does **not** adjust the credit sum or the score. It adjusts only the reported **confidence**,
via `longevity.confidence_adjustment` mapped from the `entity_maturity` band: startup −0.60,
young −0.50, established/mature/veteran 0.00, unknown −0.05.

> **Correction to earlier documentation.** There is no weighted-component model
> (25/20/20/15/10/10), no "attainability" band (Full/Partial/Minimal), and no age cap on the
> attainable score. Those described a design that was never implemented.

---

### 5. Longevity and Maturity

#### What it measures

Operating history, and — separately — **how well that history is evidenced**.

#### Age bands (`longevity.age_band_from_years`)

```
< 2 → startup   |   2–5 → young   |   5–10 → established   |   10–20 → mature   |   20+ → veteran
```

`maturity.py` carries a parallel band vocabulary used by `scoring.yaml` for narrative lookup:
`new_lt_1` · `startup_lt_2` · `young_2_5` · `established_5_10` · `mature_gt_10`.

#### The maturity index — why it saturates

```
index(y) = min(1, ln(1 + y) / ln(1 + 25))          SATURATION_YEARS = 25
```

A step table could not tell an 11-year-old vendor from a 40-year-old one: everything past ten years
was one bucket. But a linear-in-years term would make "old" the single largest term in the model.
The **logarithmic, saturating** curve encodes the actual epistemics: year two of trading is
enormously informative, year forty is not. A vendor trading 25 years has demonstrated continuity
across at least two full economic cycles; one trading 40 has not demonstrated meaningfully more.

#### Evidence strength — why age is discounted by source

**Age is purchasable.** An aged domain costs a few hundred dollars at an expiry auction; a company
inception date in a national register does not. Weighting every source equally would have made
"buy an old domain" the cheapest posture uplift in the product.

```
assurance_index(y, source) = min( index(y), index(y) × evidence_strength(source) )
```

| Source | Strength | |
|---|---:|---|
| `gleif`, `companies_house`, `abn` | 1.00 | authoritative entity registers |
| `wikidata` | 0.90 | curated inception date, community-maintained |
| `firmographics`, `pdl` | 0.80 | aggregated founding year |
| `rdap` | 0.60 | domain creation — a proxy, and a buyable one |
| unrecognised | 0.60 | a new collector earns its weight; it does not inherit it |

The discount is **one-directional**: a weak source can never buy assurance, and can never
manufacture youth that isn't there either.

#### Source priority for the date itself

1. Incorporation date from entity registers (OpenCorporates, Companies House, ABR, GLEIF)
2. Wikidata P571 (legal inception)
3. RDAP domain creation date (discounted, free fallback)
4. `unknown`

#### Where age is allowed to reach

Age reaches exactly three places, and **posture is not one of them**:

1. **Confidence** — the bounded assurance multiplier (floor 0.40, ceiling 1.04)
2. **Benchmarking** — cohort assignment and `attainable_after_years`
3. **Business Stability** — base score and penalty/bonus multipliers

There is **no published evidence that founding date predicts security posture**, which is why age
is confined to Confidence and Benchmarking on the security side. `scoring/engine.py` carries an explicit comment recording that a previous
revision added a table charging young vendors 6–15 posture points *where no finding had been
observed* — a deduction with no evidence behind it, levied on a company for being new — and why it
was removed. Two vendors with identical findings get an identical posture. That is deliberate.

#### Contingency planning

`contingency_plan_required` returns True for **high** criticality with a startup or young vendor,
and for **medium** criticality with a startup — a control response to elevated base-rate exit risk,
rather than a score deduction.

---

### 6. Lifecycle

#### What it measures

Organisational stage — and it is **context only**. It is not a score, it emits no finding, it
writes nothing to the store, and it cannot reach the scoring engine.

#### Theoretical model: Adizes corporate lifecycle

`lifecycle.py` implements stages from the **Adizes corporate lifecycle** model (Adizes, 1979;
*Corporate Lifecycles*, 1988), which characterises organisations by the changing balance of
flexibility and control rather than by funding or headcount. Firms are most flexible and least
controlled at birth, most controlled and least flexible in old age, and best balanced at Prime.

```python
< 1  → infancy      # under 1 year
< 2  → go_go        # rapid growth, processes forming
< 5  → adolescence  # structure emerging, not yet stable
< 15 → prime        # peak balance of control and flexibility
≥ 15 → aging        # established, accumulating path-dependency
None → unknown
```

Derived solely from operating years (entity inception, or domain age as fallback).

#### What each stage means for a buyer

| Stage | Buyer-relevant reading |
|---|---|
| **Infancy** | Financial fragility (no revenue history), compliance immaturity (no SOC 2 observation window yet), key-person dependency. DMARC/TLS gaps are greenfield misses — hygiene not embedded in founding habits. |
| **Go-Go** | Processes forming, financial model unproven. Gaps indicate security deprioritised during growth. SOC 2 Type 2 unlikely — insufficient observation window. |
| **Adolescence** | Structure emerging. Cohort benchmarking against similarly-aged peers is more meaningful than comparison with incumbents. Gaps here suggest deliberate inaction rather than resource constraint. |
| **Prime** | Established processes and governance. Watch for emerging path-dependency. Gaps are concerning — years have been available. SOC 2 absence is a choice or a programme failure. |
| **Aging** | Accumulating path-dependency; legacy systems constrain modernisation. Gaps suggest accepted obsolescence or under-investment. |
| **Unknown** | Cannot assess lifecycle risk. Request incorporation evidence directly. |

#### Key-person risk

A **flag with a stated basis**, never a score: headcount ≤ **10** (observed via Wikidata) in a
**high-criticality** relationship. Deliberately weak — headcount is a *scale* proxy, not a
*concentration* measure, and internal dependency concentration is not externally observable.

#### Technology obsolescence framing

Re-labels findings the engine **already charged for** (`tls_version`, `kev_listed_cve`) as
path-dependency context, adding no arithmetic. The same finding is described differently by age:
TLS 1.0 on a 2-year-old vendor is a configuration decision fixable by config change; on a
20-year-old vendor it is likely path-dependency that may require system replacement. Deduplicated
per unique `(signal, band_key)` so the UI does not repeat itself.

> **Correction to earlier documentation.** The funding-stage model (Seed / Series A/B / Series C+ /
> IPO), employee-count stages, product-maturity stages and market-presence tiers described
> previously are **not implemented** and have no collector behind them. `LifecycleStage` is the
> Adizes five-stage vocabulary above.

---

### Metric relationships

#### Posture ↔ Confidence
Different questions: how strong are the controls, versus how much of the expected evidence we
found. High posture with low confidence means clean *observable* controls on thin evidence — common
for young vendors. **A bare posture is unrepresentable; never publish one without its confidence.**
Confidence acts on posture in one direction only: as a **ceiling**, never as a deduction.

#### Posture ↔ Business Stability
Orthogonal by construction. Business Stability signals are excluded from **both sides** of the
posture coverage ratio, and the two context categories cannot penalise. A vendor can be sound and
exposed, or impaired and well-controlled.

#### Posture ↔ Assurity
Complementary: implementation versus independent verification. Assurity credit can **never** buy
back posture lost to a real finding. Keeping them apart is what stops assurance theatre from
becoming a security score.

#### Longevity → everything except Posture
Foundational context. It sets the Confidence denominator, the Business Stability base and
multipliers, the benchmark cohort, and the Assurity confidence adjustment. It reaches Posture
**nowhere**.

#### Business Stability ↔ Lifecycle
Strongly correlated — both are age-anchored — but lifecycle is narrative and stability is scored.
Lifecycle is what lets a reader interpret a stability score in context rather than as a verdict.

---

### Key principles

1. **Never mix axes.** Each answers a different question; none may influence another's arithmetic.
2. **Missing data reduces Confidence, never Posture.** Enforced by the fixed divisor, not by
   convention.
3. **Absence of evidence is not evidence of failure.** Not holding a certification is not a
   finding. Only an *asserted-then-failed* control is.
4. **Age-appropriate expectations.** Confidence denominators and attainability rules scale with
   profile, so the maths handles fairness rather than a special case doing it.
5. **Separate gates from scores.** Some conditions must **block**, not merely reduce: sanctions,
   ambiguous entity resolution, active insolvency, dissolution. A low score clears a threshold; a
   gate does not.
6. **Insufficient evidence is adverse, not neutral.** A supplier nobody can see is a supplier
   nobody has checked.
7. **No vendor context reaches the posture arithmetic.** Sector, revenue, headcount, country,
   ownership and age are all out. The same evidence must score the same way for everyone, or
   comparability is gone.
8. **Judgement is labelled as judgement.** The severity ladder, the aggregation decay and the
   divisor are expert judgement. They are defensible and reviewable; they are not calibrated
   against outcomes, and nothing may present them as though they were.

---

### API endpoints

**Posture and confidence**
- `GET /api/vendors/{ref}` — the published Score (posture, grade, confidence, categories)
- `GET /api/vendors/{ref}/confidence` — confidence breakdown with deduction labels
- `GET /api/vendors/{ref}/coverage` — evidence coverage analysis
- `GET /api/vendors/{ref}/history` — prior scores
- `GET /api/vendors/{ref}/findings`, `/evidence`, `/evidence/{evidence_id}` — the receipts

**Business stability and continuity**
- `GET /api/vendors/{ref}/stability` — score, standing, penalties, bonuses, gate status
- `GET /api/vendors/{ref}/financial` — raw financial profile
- `GET /api/vendors/{ref}/continuity` — registry facts and going-concern status

**Assurity**
- `GET /api/vendors/{ref}/assurity` — score, inputs, gap penalty, caveats
- `GET /api/vendors/{ref}/evidence-request-pack` — what to ask the vendor for

**Longevity and lifecycle**
- `GET /api/vendors/{ref}/lifecycle` — stage, key-person flag, obsolescence framing
- `GET /api/vendors/{ref}/profile` — operating years, age band, size band

**Scoring**
- `POST /api/vendors/score` · `POST /api/vendors/{ref}/rescore` — 202 + job id
- `GET /api/jobs/{job_id}` · `GET /api/jobs/{job_id}/stream`

---

### Summary

| Metric | Range | Aggregation | Age's role |
|---|---|---|---|
| **Posture** | 0–100, A–F | `100 − Σ capped penalties / 2.86`, with rank decay 0.7 | **none** |
| **Confidence** | 0–1 | `Σ w(expected ∧ found) / Σ w(expected)` | sets the denominator |
| **Business Stability** | 0–100 or gated | base − penalties + bonuses, age-multiplied | base score + multipliers |
| **Assurity** | 23–97 | `100 × σ(−1.2 + Σ credits − 0.8·gaps)` | confidence only |
| **Longevity** | bands + 0–1 index | `ln(1+y)/ln(26)`, discounted by source | is the metric |
| **Lifecycle** | 5 Adizes stages | none — narrative only | is the metric |

Each axis is computed independently by a method appropriate to what it measures, and they are
reported side by side rather than blended. The age-based differentiation makes the treatment of
young and small vendors fair *by construction* — through what is expected of them, not through a
penalty applied and then apologised for.

#### Open items flagged by this review

1. `business_stability.age_base_scores` / `confidence_adjustments` in `scoring.yaml` are **inert** —
   the runtime reads `longevity.py`. One of the two must be deleted or wired.
2. A clean startup scores **20 / "ceased"** on Business Stability. The standing vocabulary and the
   base curve need to be reconciled.
3. Four declared financial penalties (`voluntary_arrangement`, `declining_profitability`,
   `high_customer_concentration`, `no_recent_funding_18_months`) are **not wired**.
4. Several `age_risk_factors` inputs are passed as placeholders from `business_stability.py`
   (`finding_count=0`, leadership, media, structural-change fields) — the profile currently reports
   on defaults rather than observations.
5. `calculate_from_profile` passes `sector` as `jurisdiction`.
6. `methodology.md` Part 1 §"Age-based base scores" documents the inert YAML values (base 70) and
   should be corrected alongside this file.

---

## Part 3 · Vendor age differentiation

*Key principle: a 2-year-old startup can have excellent cybersecurity controls, and a 40-year-old company can have poor security. Age affects **Business Stability and Confidence only**, never cybersecurity posture.*

### Overview

The OSINT-based Third-Party Risk Management (TPRM) module implements a sophisticated vendor age differentiation system that distinguishes between vendors of different ages (e.g., 2 years vs 20 years) through multiple complementary mechanisms. This system recognizes that vendor age is a contextual factor for business stability assessment rather than a direct cybersecurity penalty.

**Key Principle:** A 2-year-old startup can have excellent cybersecurity controls, and a 40-year-old company can have poor security. Age affects BUSINESS STABILITY only, not cybersecurity posture.

### Architecture

The age differentiation system consists of three main modules:

1. **`longevity.py`** - Discrete age band classification with base scores and confidence adjustments
2. **`maturity.py`** - Continuous logarithmic maturity index with evidence strength weighting  
3. **`business_stability.py`** - Integration of age into Business Stability scoring

### Module 1: longevity.py - Age Band Classification

The six age bands, their base Business Stability scores, confidence adjustments and survivorship
bonuses are the authoritative table in [`methodology.md`](methodology.md) Part 1 §5.2.1 (not repeated
here to avoid the two drifting apart) — `longevity.py` is the implementation of that table.
`base_scores`: startup 70, young 85, established 90, mature 95, veteran 100, unknown 85.
`confidence_adjustments`: startup −0.20, young −0.10, established/mature/veteran 0.00, unknown
−0.05. `survivorship_bonuses`: mature +5, veteran +10, plus +5 for surviving a named downturn
(2008, 2020) if the vendor was operating through it.

#### Age-Specific Risk Factors

Different risk factors are assessed based on age band:

**Startup (<2 years):**
- Funding runway remaining
- Customer concentration risk
- Founder dependency (key person risk)

**Young (2-5 years):**
- Growth sustainability
- Market validation (product-market fit)
- Team completeness and hiring ability

**Established (5-10 years):**
- Market position in industry
- Operational efficiency and margin pressure
- Scalability without breaking operations

**Mature (10-20 years):**
- Decline signals (revenue/market share trends)
- Acquisition risk (leadership changes, PE ownership)
- Innovation stagnation (R&D investment, product pipeline)

**Veteran (20+ years):**
- Institutional health (governance, succession planning)
- Adaptability to market changes
- Legacy risk (technical debt, outdated systems)

### Module 2: maturity.py - Continuous Age Index

#### Logarithmic Maturity Index

The system uses a continuous logarithmic index that saturates at 25 years:

```python
def maturity_index(years: float | None) -> float | None:
    """Operating history as a saturating 0-1 index."""
    if years is None:
        return None
    years = max(0.0, float(years))
    return min(1.0, math.log1p(years) / math.log1p(SATURATION_YEARS))
```

**Formula:** `index(y) = min(1, ln(1 + y) / ln(1 + 25))`

**Values:**
- 1 year → 0.21
- 2 years → 0.34
- 5 years → 0.55
- 10 years → 0.74
- 20 years → 0.93
- 25+ years → 1.00

**Rationale for Saturation at 25 Years:**
A vendor trading 25 years has demonstrated continuity across at least two full economic cycles; one trading 40 years has not demonstrated meaningfully more. Treating 40 years as significantly higher would let "old" dominate the scoring model.

#### Evidence Strength Weighting

Different data sources receive different weights for age claims:

```python
EVIDENCE_STRENGTH: dict[str, float] = {
    "gleif": 1.0,               # LEI registration — authoritative entity record
    "companies_house": 1.0,     # UK register
    "abn": 1.0,                 # Australian Business Register
    "wikidata": 0.9,            # Curated inception date; community-maintained
    "firmographics": 0.8,       # Aggregated founding year
    "pdl": 0.8,
    "rdap": 0.6,                # Domain creation date — proxy, and buyable
}
```

**Rationale:** A national register records the legal entity's inception; RDAP records when somebody paid for a domain name. These are different claims, and only the first is what "operating history" means.

#### Assurance Index

The confidence multiplier combines maturity index with evidence strength:

```python
def assurance_index(years: float | None, source: str | None = None) -> float | None:
    """The index used for the CONFIDENCE multiplier: operating history, discounted by evidence."""
    index = maturity_index(years)
    if index is None:
        return None
    # Discount is one-directional only - can scale down, never up
    return min(index, round(index * evidence_strength(source), 4))
```

**Key Principle:** The discount is deliberately one-directional. It scales the index DOWN, so a weakly-evidenced forty-year-old domain earns roughly what a well-evidenced seven-year-old company earns — which is the intended answer, because an aged domain is a thing you can buy and a seven-year trading record is not.

### Module 3: business_stability.py - Integration

#### Age-Based Base Score Calculation

The Business Stability score starts with an age-based base score:

```python
def _compute_age_base(self) -> None:
    """Compute base score from vendor age."""
    # Priority order for age sources:
    # 1. incorporation_date from entity registers
    # 2. entity_maturity from Wikidata (P571 - legal inception date)
    # 3. entity_maturity from RDAP (domain creation date - discounted)
    # 4. Fallback to "unknown" if no source available
    
    if self.profile.incorporation_date:
        self.profile.operating_years = operating_years(self.profile.incorporation_date.value)
    else:
        # Fallback to Wikidata or RDAP maturity data
        wikidata_years = getattr(self.profile, 'wikidata_years', None)
        rdap_years = getattr(self.profile, 'rdap_years', None)
        
        if wikidata_years is not None:
            self.profile.operating_years = wikidata_years
        elif rdap_years is not None:
            self.profile.operating_years = rdap_years
        else:
            self.profile.operating_years = None
    
    # Determine age band and base score
    self.profile.age_band = age_band_from_years(self.profile.operating_years)
    self._base_score = base_age_score(self.profile.age_band or "unknown")
```

#### Complete Age Modifier Application

```python
def apply_age_modifiers(
    profile: FinancialProfile,
    base_confidence: float,
) -> tuple[int, float]:
    """Apply all age-based modifiers to Business Stability score and confidence."""
    # Calculate operating years if not already computed
    if profile.operating_years is None and profile.incorporation_date:
        profile.operating_years = operating_years(profile.incorporation_date.value)
    
    # Determine age band if not already computed
    if profile.age_band is None:
        profile.age_band = age_band_from_years(profile.operating_years)
    
    # Get base score from age band
    age_score = base_age_score(profile.age_band or "unknown")
    
    # Apply confidence adjustment
    conf_adj = confidence_adjustment(profile.age_band or "unknown")
    adjusted_confidence = max(0.0, min(1.0, base_confidence + conf_adj))
    
    return age_score, adjusted_confidence
```

### Concrete Examples: 2-Year vs 20-Year Vendor

#### Example 1: 2-Year-Old Vendor

**Vendor Profile:**
- Operating years: 2.0
- Age band: "young"
- Base Business Stability score: 85/100
- Confidence adjustment: -10%
- Maturity index: 0.34

**Scoring Impact:**
```python
# Base score calculation
base_score = base_age_score("young")  # Returns 85

# Confidence calculation
base_confidence = 0.90  # From evidence coverage
adjusted_confidence = 0.90 + confidence_adjustment("young")  # 0.90 - 0.10 = 0.80

# Risk factors assessed
risk_factors = age_risk_factors("young")
# Returns: growth_sustainability, market_validation, team_completeness

# Benchmarking cohort
benchmark_cohort = age_appropriate_benchmarking("young")
# "Benchmark against other young vendors (2-5 years) with similar funding stages"
```

**Final Assessment:**
- Business Stability starts at 85/100
- Must prove financial health to increase score
- 10% confidence penalty due to limited track record
- Compared against other young vendors
- Focus on growth sustainability and market validation

#### Example 2: 20-Year-Old Vendor

**Vendor Profile:**
- Operating years: 20.0
- Age band: "mature"
- Base Business Stability score: 95/100
- Confidence adjustment: 0%
- Maturity index: 0.93
- Survivorship bonus: +5 points

**Scoring Impact:**
```python
# Base score calculation
base_score = base_age_score("mature")  # Returns 95

# Confidence calculation
base_confidence = 0.90  # From evidence coverage
adjusted_confidence = 0.90 + confidence_adjustment("mature")  # 0.90 + 0.00 = 0.90

# Survivorship bonus
bonus = survivorship_bonus("mature")  # Returns 5

# Risk factors assessed
risk_factors = age_risk_factors("mature")
# Returns: decline_signals, acquisition_risk, innovation_stagnation

# Benchmarking cohort
benchmark_cohort = age_appropriate_benchmarking("mature")
# "Benchmark against other mature vendors (10-20 years) in the same industry"
```

**Final Assessment:**
- Business Stability starts at 95/100 (higher baseline)
- +5 survivorship bonus for demonstrated staying power
- No confidence penalty (extensive track record)
- Compared against other mature vendors
- Focus on decline signals and innovation stagnation

#### Key Differences Summary

| Aspect | 2-Year-Old Vendor | 20-Year-Old Vendor |
|--------|------------------|-------------------|
| **Age Band** | young | mature |
| **Base Score** | 85/100 | 95/100 |
| **Confidence Penalty** | -10% | 0% |
| **Maturity Index** | 0.34 | 0.93 |
| **Survivorship Bonus** | 0 | +5 |
| **Risk Focus** | Growth, market fit | Decline, stagnation |
| **Benchmarking** | Young vendors (2-5yr) | Mature vendors (10-20yr) |

### Data Model Integration

#### FinancialProfile Model

The `FinancialProfile` model in `models.py` includes age-related fields:

```python
class FinancialProfile(BaseModel):
    vendor_ref: str
    
    # Primary age source
    incorporation_date: ProfileField | None  # Date company was legally incorporated
    
    # Fallback age sources when entity registers unavailable
    wikidata_years: float | None  # Years from Wikidata (P571) - free fallback
    rdap_years: float | None  # Years from domain registration - discounted fallback
    
    # Computed age fields
    operating_years: float | None  # Years since incorporation (computed)
    age_band: Literal["startup", "young", "established", "mature", "veteran", "unknown"] | None
```

### Design Principles

#### 1. Age as Context, Not Penalty

Age affects BUSINESS STABILITY only, not cybersecurity posture. A bankrupt company can have excellent security, and a secure startup can run out of cash. These are separate risk dimensions.

#### 2. Survivorship Recognition

The system rewards demonstrated staying power through survivorship bonuses. Companies that weather economic downturns or survive for decades have proven business models.

#### 3. Evidence Quality Matters

Not all age sources are equal. Entity registers (GLEIF, Companies House) receive full credit, while domain age (RDAP) is discounted because domains can be purchased on expiry auctions.

#### 4. Age-Appropriate Benchmarking

Young vendors are benchmarked against peers of similar age, not against established companies. This prevents unfair comparisons and ensures relevant risk assessment.

#### 5. Diminishing Returns on Age

The logarithmic maturity index recognizes that the difference between 1 and 5 years is meaningful, but the difference between 25 and 40 years is not. The curve saturates at 25 years.

#### 6. Confidence vs. Risk

Confidence adjustments reflect uncertainty in our assessment, not poor vendor performance. A young vendor with limited public information receives a confidence penalty, not a risk penalty.

### Usage Examples

#### Basic Age Assessment

```python
from datetime import datetime, UTC
from app.longevity import operating_years, age_band_from_years, base_age_score
from app.maturity import maturity_index, assurance_index

# Calculate operating years
incorporation_date = datetime(2024, 1, 1, tzinfo=UTC)
years = operating_years(incorporation_date)  # Returns ~2.0

# Determine age band
age_band = age_band_from_years(years)  # Returns "young"

# Get base score
score = base_age_score(age_band)  # Returns 85

# Calculate maturity index
maturity = maturity_index(years)  # Returns ~0.34

# Calculate assurance with evidence strength
assurance = assurance_index(years, source="companies_house")  # Returns ~0.34
assurance_rdap = assurance_index(years, source="rdap")  # Returns ~0.20 (discounted)
```

#### Full Business Stability Calculation

```python
from app.business_stability import BusinessStabilityScore
from app.models import FinancialProfile

# Create financial profile
profile = FinancialProfile(
    vendor_ref="example_vendor",
    incorporation_date=ProfileField(
        value=datetime(2024, 1, 1, tzinfo=UTC),
        source="companies_house"
    )
)

# Calculate Business Stability score
scorer = BusinessStabilityScore(profile)
result = scorer.compute()

# Result includes:
# - score: final Business Stability score (age-adjusted)
# - base_score: starting score from age band
# - age_band: vendor's age classification
# - penalties: financial distress penalties
# - bonuses: survivorship bonuses
```

### Integration with Benchmarking

The age differentiation system integrates with the benchmarking module to ensure age-appropriate comparisons:

```python
def age_appropriate_benchmarking(age_band: AgeBand) -> str:
    """Return benchmarking guidance based on vendor age."""
    guidance = {
        "startup": "Benchmark against other startups (<2 years) with similar funding stages",
        "young": "Benchmark against other young vendors (2-5 years) with similar growth trajectories",
        "established": "Benchmark against established vendors (5-10 years) in same industry",
        "mature": "Benchmark against mature vendors (10-20 years) in same industry",
        "veteran": "Benchmark against veteran vendors (20+ years) with similar market positions",
        "unknown": "Benchmark against industry averages (age unknown)",
    }
    return guidance.get(age_band, "Benchmark against industry averages")
```

### References

- **Research Basis:** "Liability of newness" (Stinchcombe, 1965) - established research on higher failure rates for young organizations
- **Vendor Risk Best Practices:** Industry standard treating age as business stability factor, not security factor
- **Regulatory Alignment:** Approach aligns with Australian regulatory guidance on transparent, defensible scoring
- **Related Documentation:** 
  - `methodology.md` Part 1 - Overall OSINT TPRM methodology
  - `design_decisions.md` Part 2 - Business Stability axis design
  - Part 1 of this document - Complete scoring model documentation

### Gaps and Enhancement Opportunities

Based on comprehensive vendor risk management best practices, the current implementation has several enhancement opportunities to fully leverage vendor age as a material risk differentiator:

#### 1. Inherent Risk Baseline Adjustment

**Current State:** Inherent risk is calculated solely from `criticality` and `data_access_scope` (see `residual_risk.py`). Age does not factor into inherent risk calculation.

**Recommended Enhancement:** Apply age-based modifier to inherent risk baseline:
- Young vendors (<3-5 years): Apply upward adjustment to inherent risk due to limited track record and elevated failure risk
- Mature vendors (≥10-15 years): Apply downward adjustment or neutral baseline; focus on long-term patterns

**Implementation Location:** `residual_risk.py` - `inherent_tier()` function

#### 2. Monitoring Cadence by Age

**Current State:** Monitoring cadence is determined by inherent tier (T1-T4) via `assessment_depth.py`. Age does not influence monitoring frequency.

**Recommended Enhancement:** Implement age-adjusted monitoring cadence:
- Young vendors: Higher-frequency continuous monitoring, tighter alert thresholds, shorter reassessment cycles
- Mature vendors: Risk-based cadence scaled to tier + recent signal strength; historical stability can justify relaxed intervals

**Implementation Location:** `assessment_depth.py` - Assessment plan lookup table, `monitor.py` - scheduling logic

#### 3. Evidence Weighting by Vendor Age

**Current State:** Evidence strength is based on source reliability (GLEIF=1.0, RDAP=0.6) but not on vendor age. (see `maturity.py`)

**Recommended Enhancement:** Apply age-specific evidence weighting:
- 20-year vendor: Weight multi-year trends more heavily; rich OSINT corpus gets higher confidence
- 2-year vendor: Sparse data means single red flags carry higher relative weight; require stronger corroboration

**Implementation Location:** `maturity.py` - Evidence strength calculation, confidence scoring

#### 4. Age-Specific Residual Risk Thresholds

**Current State:** Residual risk matrix uses posture bands vs inherent tiers uniformly. No age-based adjustments to residual risk thresholds.

**Recommended Enhancement:** Implement age-adjusted residual risk thresholds:
- Young vendors: Lower residual-risk acceptance bars (same posture → higher residual risk classification)
- Mature vendors: Standard thresholds; long history supports current posture assessment

**Implementation Location:** `residual_risk.py` - `_RESIDUAL` matrix lookup

#### 5. Incident & Reputation Pattern Analysis by Age

**Current State:** Incident scoring applies uniformly regardless of vendor age. No age-specific incident weight or pattern analysis.

**Recommended Enhancement:** Age-specific incident analysis:
- Mature vendors: Look for recurring themes, severity trends, remediation evidence over time
- Young vendors: Treat any material incident as higher-impact (little positive counter-history); scrutinize founder/key-personnel OSINT more aggressively

**Implementation Location:** Scoring configuration (`scoring.yaml`), incident collectors

#### 6. Change & Continuity Monitoring by Age

**Current State:** Change monitoring applies uniformly. No age-specific change focus areas.

**Recommended Enhancement:** Age-specific change indicators:
- Mature vendors: Monitor for late-stage risks (ownership changes, divestitures, key-person departures, declining sentiment)
- Young vendors: Monitor for rapid scaling signals (headcount jumps, geographic expansion, new product lines) and acquisition/wind-down probability

**Implementation Location:** `monitor.py` - change detection logic, alert thresholds

#### 7. Financial Signal Focus by Age

**Current State:** Financial signals apply uniformly via `business_stability.py`. Some age-specific risk factors exist but financial focus is not age-differentiated.

**Recommended Enhancement:** Age-specific financial focus:
- Mature vendors: Emphasize multi-year financial health, credit history, bankruptcy/lien records, consistent growth patterns
- Young vendors: Prioritize recent funding rounds, burn-rate proxies, founder/background checks, early customer traction; treat limited transparency as elevated risk

**Implementation Location:** `business_stability.py` - financial penalty application

### Implementation Priority Matrix

| Enhancement | Impact | Complexity | Priority |
|-------------|--------|------------|----------|
| Inherent Risk Baseline Adjustment | High | Medium | High |
| Monitoring Cadence by Age | High | Low | High |
| Evidence Weighting by Age | Medium | Medium | Medium |
| Age-Specific Residual Risk Thresholds | High | Low | High |
| Incident Pattern Analysis by Age | Medium | High | Medium |
| Change Monitoring by Age | Medium | Medium | Medium |
| Financial Signal Focus by Age | Low | Low | Low |

### Conclusion

The current vendor age differentiation system provides a solid foundation through Business Stability scoring, maturity indexing, and evidence strength weighting. However, it does not fully leverage vendor age as a material risk differentiator across all risk dimensions as recommended by best practices.

The key enhancement opportunities are:
1. **Integrate age into inherent risk calculation** - Young vendors should have higher inherent risk baselines
2. **Implement age-based monitoring cadence** - Young vendors need more frequent monitoring
3. **Apply age-specific evidence weighting** - Sparse data for young vendors should elevate individual findings
4. **Adjust residual risk thresholds by age** - Lower acceptance bars for young vendors

These enhancements would align the system with the principle that "a clean OSINT profile on a 2-year-old vendor is inherently less reassuring than the same profile on a 20-year-old vendor with a long, observable history."
