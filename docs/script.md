# Script — what this system is, and why each part of it exists

**A walkthrough of the OSINT TPRM platform.** Written to be delivered: read top to bottom and it is a
forty-minute demo; read one section and it is the defence of one decision.

Every figure in here is live, taken from the running system rather than from a slide. Where a number is
calibrated rather than derived, it says so. Where something is deliberately *not* built, it says that too —
the refusals are the product, and a walkthrough that hides them has sold something else.

---

## 0 · The one-paragraph version

> We assess third-party vendors from lawfully-public evidence only. Every vendor starts at 100 and loses points
> for what we can actually observe, so there are no category weights to defend. We publish **three numbers that
> are never averaged into one** — how strong the vendor looks, how much of it we could see, and whether anyone
> independent has checked — plus a residual risk tier that only exists once **the buyer** has declared what the
> relationship is worth. Every deduction carries a plain-English sentence and a hash-stamped receipt. When the
> evidence is too thin, the system **refuses to publish a grade** and says which sources stayed silent.

The thing to sell is not the score. It is that **the score can be walked backwards**, and that the system says
"I don't know" out loud.

---

## 1 · The problem this is aimed at

Third-party risk assessment today has two failure modes, and they are opposites.

**The questionnaire.** A 300-row spreadsheet, filled in by the vendor, about themselves, once a year. It
measures a vendor's willingness to fill in spreadsheets. It ages the moment it is signed.

**The single-grade rating platform.** One number, 0–950, produced by a proprietary method. It is current, and
it is unarguable — which sounds like a strength until a vendor disputes it and nobody in the room can explain
what moved. Worse, it cannot distinguish **a vendor that is genuinely clean** from **a vendor we could barely
see**. Both come back looking fine.

That second confusion is the one this system exists to end.

**What to say:** *"A rating platform will tell you this vendor is an 820. It will not tell you that we could
only observe four of the twenty-seven things we planned to check. Those are different situations and they
require different decisions."*

---

## 2 · The shape of the system

Nine screens over one API over one append-only store.

| Screen | Route | The question it answers |
|:--|:--|:--|
| The book | `/` | What is in my portfolio, and where is the concentration? |
| Assess | `/assess` | Score a vendor now |
| Vendor record | `/vendors/:ref` | What did we find, what does it mean, what do I do? |
| Evidence pack | `/vendors/:ref/pack` | What do I ask the vendor? |
| Contract flowdowns | `/vendors/:ref/contract` | What goes in the contract? |
| Adjudication queue | `/queue` | What needs a human? |
| Inventory | `/inventory` | Is the register of relationships itself sound? |
| Programme | `/program` | Is the TPRM function working? |
| Methodology | `/methodology` | How does any of this work? |

Behind them: **20 collectors**, one per source, each independently failure-isolated — all 20 at *full* depth,
11 at *core*, 7 at *screening*. **51 test modules, ~1,120 tests.** One Postgres store where `UPDATE` and
`DELETE` are rejected by database trigger.

**What to show:** the vendor record. Everything else is context for that page.

---

## 3 · The pipeline, in the order it actually runs

Say this in sequence, because the order is load-bearing and a reordered version of it would be a different
product.

### 3.1 Identity resolution — the hard problem, first

You type a name or a domain. A name resolves to candidate organisations and you confirm one. Nothing is
guessed.

**Why it comes first:** every downstream number is a claim about a specific legal entity. Assess the wrong
`acme.com` and every receipt beneath it is a receipt for the wrong company — and it will look completely
credible.

### 3.2 Two gates that stop the assessment before any score exists

**Sanctions.** A watchlist match does not score badly and does not grade F. Under the *Autonomous Sanctions
Act 2011* s16(7) a weighted contribution is legally meaningless — you are either dealing with a sanctioned
entity or you are not. The record is **blocked** and routed to a person. Matching is whole-word and
recall-tuned: this is the one place in the system where recall beats precision, because a missed sanctions hit
is a legal exposure and a false positive is five minutes of someone's time.

**Ambiguous identity.** Below 0.5 attribution confidence the assessment stops rather than risk reporting on the
wrong company.

**What to say:** *"These are the two places the system refuses to produce a number at all. Both hand the
decision to a person, because both are legal or factual questions rather than measurement questions."*

### 3.3 Collection — parallel, and failure-isolated

All applicable sources at once: DNS, TLS, HTTP headers, Certificate Transparency, HIBP, CISA KEV, NVD + EPSS,
GLEIF, Wikidata, RDAP, ABN Lookup, Companies House, trust pages, regulator feeds, and the ITA screening list
for the gate.

**One source failing lowers coverage. It never stops the run and it never lowers posture.** That sentence is
the entire design of the collector layer.

### 3.4 Evidence is stored **before** anything is scored

Every raw response is written to the store with its fetch time, source version, content hash and reliability,
**then** scoring begins.

**Why:** a score you cannot reproduce is an opinion. This ordering is what makes "walk it backwards" true
rather than aspirational — and the store is append-only at the *database* level, so a correction is a new row
and the original stays readable.

**What to show:** click a finding on the vendor page, follow it to its receipt, show the hash.

### 3.5 Classification and scoring

Each observation maps to a **pass** or exactly one of four severities. That table is the only points table in
the system:

| Severity | Penalty |
|:--|--:|
| Critical | −40 |
| High | −20 |
| Medium | −8 |
| Low | −3 |
| Informational | 0 — recorded, not scored |

Then each penalty is adjusted by the NIST SP 1326 variables — age, frequency, mitigation — before it is
subtracted.

**The single most-asked question, pre-answered:** *why does a 2013 breach count for less than last month's?*
Because NIST SP 1326 says so, on a three-year half-life floored at 0.15 so it decays but never vanishes. We
adopted a US federal publication rather than inventing a curve, precisely so that this question has an answer
that is not "we felt it was about right".

**The exception worth naming, because it was a real bug:** current-state signals never decay. A certificate's
event date is its *expiry boundary*, not an event. Decaying it meant a certificate that expired six years ago
cost −10 while one expiring next week cost −20 — **the longer it stayed broken, the cheaper it got.**

---

## 4 · Why there are no category weights

This is the strongest architectural claim in the system, so give it its own moment.

The earlier design was a weighted mean: `category → subcategory → signal`, each with a percentage. It needed a
defensible answer to *"why is Cyber Hygiene 31%?"* — and **no standard publishes vendor-risk category
weights.** There is no authority to cite. Every weight was going to be our judgement wearing a number.

A penalty model deletes the question. A category's influence **emerges** from how many issues it has and how
bad they are. One lever, four numbers, every one of them mapped to a sentence a client can argue with.

**Five scoring categories, two context categories:**

| Scoring | Answers |
|:--|:--|
| `breach_compromise_history` | Has something already gone wrong? |
| `attack_surface_hygiene` | Is the estate being kept? |
| `identity_email` | Can this vendor be impersonated? |
| `transparency` | Can this vendor be *told* about a vulnerability? |
| `compliance_regulatory` | Do their certification claims check out? |

| Context — collected, counted toward coverage, **never penalising** | Feeds |
|:--|:--|
| `continuity_context` | the Continuity axis |
| `assurance_context` | Assurity |

**Two categories stopped scoring, and the reasons are the interesting part.** Companies House mapped
liquidation and insolvency onto `entity_inactive`, which cost **20 points of technical security posture** — but
a vendor entering administration does not thereby have worse TLS. And charging for the *absence* of an audit or
a public security page is a tax on audit budget: it measures spend rather than risk, and it falls hardest on
exactly the small suppliers a fair assessment should serve. Both facts are still collected and still published.
Neither charges posture any more.

**They were not deleted, and that matters.** `planned_signal_count` is the confidence denominator. Delete nine
signals and every vendor's confidence *rises* for no evidential reason — the check still ran, we merely stopped
charging for it. Keeping them holds the denominator at 27 and keeps the receipt showing the check happened.

### The divisor, and the trap in it

`overall = 100 − total penalty ÷ 2.86`.

Not a running sum — on a 0–100 scale one −40 is 40% of the score and tanks a mediocre vendor to F. And
deliberately **not** an average of the categories that happened to return data: that let a clean trust page buy
**+23 posture**, because each clean category entered the mean as a 100 and pulled it up. Silence changed the
score, which is the one thing the model forbids.

The divisor is bound to the **number of scoring categories**, because maximum damage is
`categories × 100 ÷ divisor`. At seven categories and a divisor of 4 that was 175 points. Dropping to five
scoring categories while leaving the divisor at 4 would have cut maximum damage to 125 and made the model
**quietly more forgiving** — a larger fraction of the model would have to fail before a vendor bottomed out.
Nobody would have decided that; it would simply have happened. A test asserts the relationship holds.

**What to say:** *"That is the kind of change that ships silently in most systems. Here it fails the build."*

---

## 5 · Three axes, never collapsed

This is the centre of the product. Everything else is machinery.

| Axis | Answers | Range |
|:--|:--|:--|
| **Posture** | How strong does this vendor look from outside? | 0–100 · A–F |
| **Confidence** | How much of the vendor could we actually see? | 0–1 · High / Med / Low |
| **Assurity** | Has anyone independent checked? | 0–100 |

**The rule that keeps them honest, stated once:**

> **Missing data reduces confidence. It never changes posture.**

A signal that returns nothing is dropped from its category's coverage — never scored as a comfortable pass and
never as a penalty. **A vendor cannot look strong simply by being invisible, and cannot be punished for silence
either.**

### Assurity, and why it is not a posture bonus

*"Their TLS is current"* and *"an auditor has examined their controls"* are different claims. A vendor can be
strong on one and silent on the other. In the corpus, `synthetic_smallco` is **posture 97, assurity 13** — a
vendor that a single grade actively misdescribes.

```
Assurity = 100 × sigmoid( A₀ + Σ credits − Σ γ · compliance gaps )
```

**Absence never subtracts, and it is enforced rather than intended** — the loader rejects a negative credit. A
vendor with nothing observable sits at a low intercept of about 23, **not zero**, because unevidenced is not
disproved and a 0 would read as *audited and failed*. Below three observed signals nothing is published at all.

**Why it is a separate axis:** credit for publishing a trust page must never buy back points lost to an expired
certificate. That fence is the whole reason it exists on its own scale.

**The only thing that lowers it is a compliance gap** — a vendor asserting a framework and being observed
failing one of its controls. That is a statement about the reliability of their own claims, which is exactly
what this axis measures.

### The compliance gap — how to state an obligation without corrupting the score

An earlier design promoted a finding's *severity* by one step when a sector cited a named instrument: a missing
DMARC record read as hygiene for a farm supplier and as fraud exposure for a bank. That destroyed cross-vendor
comparability — the same evidence scoring differently because of a label **we** assigned.

The obligation was never the problem. The expression of it was:

> *"This DMARC finding is worth more points."* ← an opinion wearing a number
>
> *"Vendor is APRA-regulated and publishes no DMARC record; CPS 234 requires controls commensurate with the
> threat."* ← disputable, citable, actionable — **and it changes no arithmetic**

**One detail worth showing**, because it is the kind of thing that separates a careful system from a plausible
one: a vendor asserting ISO 27001, SOC 2 and PCI DSS while negotiating TLS 1.0 breaches three frameworks with
**one weakness**. We charge the axis **once** and report all three gaps. Charging three times would mean the
system punished a vendor for publishing more certifications.

---

## 6 · The three refusals

Three different things, routinely read as one. A UI that colours them alike is the bug this distinction exists
to prevent.

| | What happened | What the reader should do |
|:--|:--|:--|
| **Ghost** | Published, but only looks clean for lack of evidence | Read the confidence, not the grade. **Unassessed is not safe** |
| **Refused** | Coverage fell below 40% — nothing published | Get more evidence, or accept you do not have an assessment |
| **Blocked** | A gate stopped it before scoring | A person decides. This is not a low score and is never rendered as one |

### The ceiling ramp — the answer to "why not just be invisible?"

Worth its own thirty seconds, because it closes the loophole a sceptic will reach for.

The 40% floor used to be the whole story: a cliff, and above it nothing. So a vendor seen through four
collectors could publish **100** and read identically to one seen through fourteen — which made *being hard to
observe* the cheapest route to a high score. Now coverage caps how good a vendor may **look**:

| Coverage | Posture may not exceed |
|:--|--:|
| ≥ 90% | 100 — no cap |
| ≥ 75% | 97 — can still reach A, cannot be flawless |
| ≥ 60% | 90 — the top of A is not available on this evidence |
| ≥ 40% | 80 — B at best |
| < 40% | not published |

**It is a cap, not a deduction.** No category penalty moves, so *"missing data never costs posture"* still
holds exactly. What it limits is the **claim we are prepared to publish on the evidence we hold**. The findings
are the vendor's; the ceiling above them is ours.

**And the refusal is adverse, not neutral** — the required wording lives in config so the UI cannot soften it:
*"this supplier could not be assessed from public sources, and it must not be read as a clean bill of health."*

**The critical ceiling** is the fourth non-compensatory mechanism: a **directly-observed current** critical —
an expired production certificate, seen live — caps posture at 49, the top of Grade D, so one severe live issue
cannot be averaged away by good hygiene elsewhere. A coarse KEV name-match penalises but does **not** ceiling,
because it proves *"this product line had a known-exploited CVE"*, not *"unpatched here"*.

**What to say:** *"A rating platform gives you a number in every situation. We give you a number in the
situations where we have earned one, and a named refusal in the ones where we haven't."*

---

## 7 · Residual risk — the half the buyer owns

A posture score cannot answer *"how much do **we** stand to lose if they fail?"*, because that depends on what
this buyer has given them, which no amount of outside-in collection can observe.

So the buyer declares two things — business criticality and data-access scope — and the tier is
**`max(criticality, data_access_scope)`, never an average**. A low-criticality vendor with production-data
access is not a medium-risk vendor.

Posture band × inherent tier resolves through a fixed 16-cell matrix, **recomputed on read and stored
nowhere**, so it can never drift from the two inputs it is derived from.

Three properties to point at on the matrix:

- **A strong posture never reaches Low at high inherent exposure.** An A-grade vendor holding production data
  lands at Medium. They are still holding it, and the day their posture moves you find out how much was riding
  on it.
- **Undeclared is not Low.** An unclassified relationship routes to the **deepest** assessment, not the
  shallowest — the vendors nobody has got round to classifying are disproportionately the ones nobody has
  looked at.
- **Sole-source escalates one band**, and the record names that it happened.

**What to show:** an undeclared vendor. The page says *"We cannot tell you what this means to you"* and names
the four things that stay switched off until someone answers. That is the product refusing to guess on the
buyer's behalf.

---

## 8 · Interpretation — four readings that cannot move the score

### Peer benchmarking — *am I typical?*

**`n` travels with every figure, and the refusal is the figure.** A percentile needs **n ≥ 30**. A quartile
needs **n ≥ 8**. Below that the response says *insufficient peer data* and gives the actual `n`.

Both floors are enforced **in code**, not only in configuration. A config edit may raise them; it may not lower
them. That is not paranoia — the superseded module shipped `min_cohort_n: 1`, and *"make it 3 for the demo"* is
exactly how a demo setting survives into production, where it is indistinguishable from a decision nobody made.

The cohort is a **widening ladder** — sector + size + delivery model, then sector + size, then sector — and
**every rung it tried is published with that rung's `n`**, because "which peers?" is the only question anyone
actually asks about a benchmark. There is deliberately **no rung meaning "everyone we have ever assessed"**: a
comparison against everything is not a peer group. When the ladder widens, the card says so on its face.

Two further honesty mechanisms worth a sentence each. **Comparison reliability is published separately from
confidence**, because a well-evidenced supplier can sit in a poorly-supported peer group — different facts.
And **discrimination is stated on every domain row**: a domain where every peer scores 100 cannot rank anybody,
and presenting a rank among identical values would manufacture signal from a constant.

### The expectation gap — *am I what my peer group predicts?*

This is the sentence the whole subsystem exists to produce:

> *"Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group. The gap is driven by
> dmarc (absent) — 12 of 14 peers are not in this band."*

A buyer handed **−19** has a fact. A buyer handed **−19, driven by DMARC, which 12 of 14 of their own peers
publish** has a *remediation* — and one they can put to the vendor with a count from the vendor's own peer
group attached, rather than an opinion of ours.

**Say this before anyone asks:** the drivers are **ranked, not apportioned**. They will not sum to the gap,
because what a finding costs depends on what else was charged alongside it. A reader who adds them up and finds
they miss has caught a real property of the model, not a bug — and the response says so in its own caveats.

### Target maturity — *am I adequate?*

Peer benchmarking asks *am I typical*. This asks *am I adequate* — and **the vendors where the two disagree are
the interesting ones**.

A percentile has two failure modes a cohort cannot fix from the inside: the peer pool is a **convenience
sample** of whatever this deployment happened to score, so a book skewed toward weak vendors produces a
flattering median; and below the minimum peer count it publishes nothing at all, which is precisely the
position of a new deployment. A published baseline is fixed, external, and **works at n=0 peers**.

**Every control names a real instrument, or it does not ship.** DMARC against CISA BOD 18-01. TLS against NIST
SP 800-52 Rev. 2 and PCI DSS v4.0 req. 4.2.1. `security.txt` against RFC 9116 — and specifically *not* against
BOD 20-01, because that directive requires the *policy* and RFC 9116 is the *mechanism*. Controls we could not
source, DNSSEC and CAA among them, are **absent rather than asserted**. It is easy to write a plausible
baseline out of professional intuition and hang an official-sounding citation on it; that produces numbers a
client cannot trace.

**And attainability is not leniency.** A SOC 2 Type II attests to controls operating *across* an observation
window, so a company younger than that window cannot hold one — counting its absence would measure the calendar
rather than the vendor. Excluded controls leave the denominator and are **named**. DMARC, SPF, TLS and HSTS
cost engineering hours rather than years, so every vendor is held to them from day one. A vendor whose age we
could not determine is held to the **full** baseline: being unmeasurable is never a way to shed controls.

### Operating history — *how much track record is behind this?*

A saturating curve, `min(1, ln(1+y) / ln(26))`, not a ladder of bands. The previous model's top band opened at
ten years, so an 11-year-old vendor and a 40-year-old one were byte-identical.

**And it is fenced.** Age moves *confidence* and *control attainability*. It sets no penalty. The research file
records the finding plainly — *"Company age predicts security posture: no published evidence found"* — and a
firmographic multiplier on posture would make the score non-comparable across vendors, unvalidatable against
outcomes, and **purchasable**: an aged domain is bought at auction for a few hundred dollars. That is why an
RDAP domain-creation date is discounted to 0.6 while a registered inception date carries full weight.

---

## 9 · The worked example — Atlassian, live

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

**Posture = 100 − 59.17 ÷ 2.86 = 79 (B)**, at **100% coverage, High confidence**.

Beside it, on their own axes:

- **Assurity 82** from 8 observed signals, with **no compliance gaps**
- **9th percentile, ranked 36 of 39** against a `sector=technology` cohort — a percentile rather than a
  quartile, because n=39 clears the floor of 30
- **Expectation gap −11**, driven by `kev_listed_cve`, which **28 of its 39 peers** avoid

**Now read those together, because this is the payoff of not collapsing them.** This vendor is well-documented
and publishes what it claims. It is not carrying an assurance problem. Its posture deficit against its own peer
group has **one named cause**. That is a conversation to have with the vendor — not a letter to file.

A single-grade platform would have handed you "79" and left you to guess which of those four things it meant.

**One more comparison worth making.** Under the old mean-of-covered-categories, this same vendor scored **90
(A)** — *"robust posture, few or no external issues"* — while carrying 13 known-exploited product matches. That
is the leniency the fixed divisor corrects.

---

## 10 · The programme layer — does the function itself work?

Everything above assesses vendors. This assesses **you**.

- **Inventory** separates real relationships from seeded corpus vendors, so the declaration denominator is
  right. A seeded vendor has no relationship with you and therefore no inherent tier to declare — counting it
  as undeclared would make the programme look negligent about a question that does not apply.
- **KPIs**, computed rather than asserted, with the ones that *cannot* be computed left explicitly empty and
  attributed to an owner rather than filled with a plausible number.
- **Monitoring liveness**, which is a **different question** from monitoring currency. Currency can read 100%
  on a schedule that died in March, because nothing is re-scored into staleness when nothing is re-scored at
  all. **A scheduled job's failure mode is silence, not error** — so the scheduler writes a run ledger, and
  silence is the alarm condition.

**What to say:** *"Most TPRM tooling will tell you your vendors' risk. Very little of it will tell you that
your own monitoring stopped firing six weeks ago."*

---

## 11 · The engineering claims, briefly

Worth having ready, because a technical audience will ask.

**The store is append-only, enforced by the database.** `BEFORE UPDATE` and `BEFORE DELETE` triggers call
`reject_mutation()` on evidence, scores, findings, disputes, decisions, profiles, cohort tables and monitor
runs. A correction is a new row. Tests get a fresh schema per test rather than cleaning rows, because they
cannot clean rows.

**Performance is a correctness property here, not a nicety.** Three defects were found and fixed:

| | Before | After |
|:--|--:|--:|
| Store construction | 3.2 s *per request* | 0.080 s |
| `/api/portfolio` | 48 s | 1.69 s |
| `/api/program/kpis` | 75 s | 3.81 s |

The first was 24 `CREATE OR REPLACE TRIGGER` statements — each taking an `AccessExclusiveLock` — running in
front of **every HTTP request**. It did not merely queue under concurrency; it deadlocked. The schema now
applies once per process under a transaction-level advisory lock, so a web worker and a CLI run starting at the
same moment cannot deadlock against each other either.

The other two were N+1 read loops, replaced with bulk store reads. **Correctness was proven rather than
argued:** an equivalence harness compared bulk against per-vendor reads across 25 vendors and 5 read paths, and
it caught a regression that reading the code had not — an ordering change that silently dropped a source for
one vendor.

**And one bug worth admitting out loud**, because it says something about how to review a system like this: the
entire v2 benchmarking subsystem — cohorts, placements, snapshots, discrimination, disputes — **had never
worked against Postgres**. A `WHERE` clause referenced a `SELECT` alias, which is not in scope in `WHERE`, so
every call that excluded the subject from its own cohort raised `UndefinedColumn`. Every call excludes the
subject, because a cohort must never count the supplier being placed. It was one word.

**The interesting part is why the tests missed it.** The placement arithmetic was thoroughly tested against
fabricated peer lists, and the store-backed paths were assumed to be covered one layer up. They were not:
**nothing in the suite ever executed that query against Postgres.** The generalisable lesson is that a query
assembled by string concatenation is only tested by running it — so there is now a store-backed test module
that does, covering every cohort dimension, the append-only latest-row filters, and the unscorable-supplier
exclusions.

**And once it ran, it showed a second defect underneath.** Every cohort was refusing for want of peers —
n=3 in a technology sector holding 37 assessed vendors. `supplier_attributes` is the only table the cohort
query reads, and **nothing in the scoring pipeline wrote it**: the only writers were the v2 attributes route
and the inherent register. 144 profiles, 128 with a sector resolved from Wikidata or GLEIF, against 23
attribute rows of which 4 had a sector. The vendors were assessed; they were simply not in the table.

Worse, the register made the blank permanent. A relationship declared *before* the vendor was scored has no
profile, so the register wrote an empty row — and thereafter read that empty row back instead of the profile,
so re-running it after the vendor was assessed rewrote the same emptiness. Nineteen of twenty-three suppliers
were in that state.

Fixed both ways: the pipeline now records cohort attributes on every run, and the register merges the
profile's firmographics into the stored row rather than inheriting it wholesale. Both **merge, never
overwrite**, because the table is append-only and a fresh row missing a buyer-side declaration would make the
newest row — the one every read takes — the one that lost it. The technology cohort went from **3 to 39**,
which is the difference between *"insufficient peer data"* and a published percentile.

---

## 12 · The bright lines — what this system will not do

State these unprompted. They are a large part of what is being bought.

- **We score entities, not people.** Executive and brand risk, PEP screening, person-level ownership and
  demographic signals are excluded at a bright line — APP 10, the Australian privacy tort, EU AI Act Art 6(3).
  Exclusions are logged with a reason in `excluded_signals`, never silently dropped.
- **No active scanning.** Port-scanning risks an unauthorised-access classification. Attack surface is proxied
  through Certificate Transparency — certificates *issued*, not ports *open* — and the gap is owned rather than
  hidden.
- **No source whose licence we have not read.** Censys's free tier expressly prohibits commercial use of any
  kind; it is logged as a candidate requiring verification, not quietly used.
- **AI never computes or moves a score.** Where it is used it is a read layer over already-collected evidence,
  every output evidence-linked and human-adjudicable. *"The model said so"* is not reasonable grounds.

---

## 13 · What this simplifies — say it before you are asked

- **Perimeter is not posture.** OSINT measures what a stranger can see. A perfect header score is fully
  compatible with a bad internal posture. It is a proxy, labelled as one.
- **Coverage tracks size, not risk.** Big vendors publish more and therefore surface more signal. The
  confidence axis mitigates this; it does not cure it.
- **Peers are a convenience sample, not the industry.** The `n` floors bound how confidently the skew can be
  stated. They do not remove it. That is why target maturity exists alongside.
- **Four fixed penalty tiers are blunter than a calibrated curve** — deliberately, because they are easier to
  defend and to tune than a continuous deduction curve.
- **Outside-in scoring systematically over-penalises well-run vendors with thin footprints**, because it cannot
  see compensating controls. The dispute path exists for exactly this, and only a **human-accepted** refute
  ever moves a score.

**Closing line:** *"Every one of those is written into the documentation, not just into this walkthrough. A
limitation you only mention in the room is a limitation you are hiding."*

---

## Appendix · Demo running order

1. **`/` — the book.** Portfolio, concentration. Thirty seconds; it is orientation.
2. **`/assess`** — score a vendor live. Show that it streams, and that it stores evidence before scoring.
3. **`/vendors/atlassian` — spend most of your time here.**
   - **What band:** posture and confidence together, category → finding → receipt → hash. Then the assurance
     card: 82, eight signals, zero gaps.
   - **So-what band:** residual risk (or the *"we cannot tell you what this means to you"* refusal), the peer
     placement with its widening ladder and `n=16` quartile-only refusal, the expectation gap with
     `kev_listed_cve` named, and the baseline-control gap.
   - **Now-what band:** ask the vendor, put it in the contract, next assessment — each with an owner.
4. **`/queue`** — one blocked record. Show that the system routed a legal question to a person.
5. **`/program`** — the function measuring itself, including monitoring liveness.
6. **`/methodology`** — the whole model, arguable, in the product rather than in a PDF.

**If you only have five minutes:** the vendor record's three axes, one refusal, and the expectation-gap
sentence. That is the product.

---

### See also

- [`scoring_model.md`](scoring_model.md) — the model in full, with every table
- [`methodology.md`](methodology.md) — the legal and epistemic defence
- [`running_guide.md`](running_guide.md) — how to start the thing
- [`../scoring.yaml`](../scoring.yaml) — the machine-readable model, which is the actual deliverable
