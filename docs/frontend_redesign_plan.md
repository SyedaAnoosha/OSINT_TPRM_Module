# Frontend redesign plan

**Status: plan. Nothing below is built.**
**Written 2026-08-01 against commit `e1a2b11` · backend `docs/phases.md` E0–E13, EB, P1–P9 delivered · E14 planned**

---

## 1 · The problem, measured rather than asserted

The backend serves **44 endpoints**. The frontend calls **17** of them and renders **two routes** —
*Score a vendor* and *Methodology*. `/portfolio` and `/perfect-methodology` exist as components and
are **commented out of the nav**.

So the situation is not "the UI needs a refresh." It is:

> **Twenty-seven endpoints have no user interface at all**, including every artefact P1–P9 was built
> to produce — residual risk, the coverage statement, the evidence request pack, contract flow-downs,
> exit readiness, the assessment plan, fourth-party concentration, the programme dashboard, the
> adjudication queue, and the inventory of record.

| Backend capability | Endpoint | Rendered today? |
|---|---|:--:|
| Posture, grade, findings, evidence | `/api/vendors/{ref}`, `/findings`, `/evidence` | ✅ |
| Peer benchmark + history | `/benchmark`, `/peers`, `/benchmark-history` | ◑ partial |
| Disputes and decisions | `/disputes`, `/decisions` | ◑ partial |
| **Residual risk (E10b)** | `/residual-risk` | ❌ |
| **Coverage statement (P2)** | `/coverage` | ❌ |
| **Evidence request pack (P3)** | `/evidence-request-pack` | ❌ |
| **Contract flow-downs (P4)** | `/contract-flowdowns` | ❌ |
| **Assessment plan (P5)** | `/assessment-plan` | ❌ |
| **Audience views (P6)** | `/export?view=` | ❌ |
| **Status page (P7)** | `/status-page` | ❌ |
| **Exit readiness (P8)** | `/exit-readiness` | ❌ |
| **Continuity, assurity, compliance gap** | `/continuity`, `/assurity`, `/assessment` | ❌ |
| **Programme maturity + KPIs (P9)** | `/api/program*` | ❌ |
| **Inventory of record** | `/api/program/inventory` | ❌ |
| **Adjudication queue** | `/api/adjudications/queue` | ❌ |
| **Declare inherent exposure** | `POST /vendors/{ref}/inherent` | ❌ |

**The consequence is specific, not general.** `inherent_tier_declaration_rate` sat at 0.0% for months
partly because there was no route to declare a tier — that is now fixed in the API and *still has no
button*. A backend capability with no UI is, operationally, a capability that does not exist.

---

## 2 · Design language — inherited from wahidai.com

### What I could and could not extract

**Honest note:** `wahidai.com` is a client-rendered site and the fetch returned semantic HTML with no
stylesheet, no `<style>` block and no inline colour values. **I did not measure the site's hex codes.**
What follows is (a) structure and copy, which I *did* read verbatim, and (b) a palette carried forward
from this application's existing `src/index.css`, which is already in the same navy/cyan family and
was evidently derived from the brand.

**Before build, someone should open the site with devtools and confirm the six values in §2.2.** If
they differ, `index.css` is the only file that changes — every token below is already indirected.

### 2.1 Structure and voice, read from the live site

| Pattern | Verbatim from wahidai.com |
|---|---|
| Nav | Platform · Use cases · Trust · Partners · Training · About |
| Hero | *"One Platform for AI Governance"* / *"The governance system of record for AI"* |
| Problem framing | *"Why AI governance stalls"* |
| Numbered modules | `01 · AI Use-Case & Inventory` — *"Declare once. Everything follows."* |
| | `02 · Risk, Controls & Incidents` — *"Every number has one owner."* |
| | `03 · Compliance` — *"What's required and is it met."* |
| | `04 · Third-Party Risk` — *"The same rigour for someone else's model."* |
| | `05 · AI Maturity & the Board` — *"Benchmark it. Then prove it."* |
| Proof section | *"Evidence, not promises"* · *"One audit trail"* · *"One owner per number"* |
| Framework badges | ISO/IEC 42001 · EU AI Act · NIST AI RMF · DTA Policy v2.0 · APRA CPS 230/234 |
| Positioning | *"Built for regulated Australia, by risk practitioners"* |

**Three of those are already this system's own doctrine and should be lifted directly into the UI:**

- **"Evidence, not promises"** → every number links to the hash-stamped receipt it came from.
- **"One owner per number"** → every metric and every recommendation names who owns it.
- **"Declare once. Everything follows."** → this is *literally* the inherent register. One
  declaration routes P5's depth, publishes E10b's residual cell, and tags P3's pack.

Note also that wahidai.com's module `04 · Third-Party Risk` — *"The same rigour for someone else's
model"* — **is this product**. The redesign should read as that module opened up, not as a separate
application with its own visual identity.

### 2.2 Tokens — already in `src/index.css`, confirm against the live site before build

```css
--primary:    #111e41   /* navy — headers, sidebar, primary buttons */
--accent:     #33a0e7   /* cyan — links, active state, icons */
--background: #f6f7fb   /* light surface */
--card:       #ffffff
--muted-foreground: #5a6a8c
--border:     #e3e7f0
--radius:     0.75rem
```

**Type is already correct and needs no change:** Plus Jakarta Sans Variable for UI, JetBrains Mono
Variable for numbers, hashes, refs, and cohort keys. Keeping monospace on every identifier is not
decoration — a `content_hash` in a proportional font is unverifiable by eye.

**Risk band hues stay as they are** (`--risk-low` through `--risk-critical`, plus `--ghost` and
`--blocked`). Two rules about them:

1. **Ghost and Blocked are NOT points on the risk ramp.** They are grey `#7c88a1` and violet `#6b52d6`
   precisely so they cannot be misread as "a bit worse than moderate". A refused score is *unassessed*,
   not *safe*, and colouring it anywhere on the green-to-red ramp asserts a position on a scale the
   system explicitly refused to place it on.
2. **Never colour on posture alone.** A green 90 at 30% confidence is the single most dangerous cell
   the product can render. See §4.3.

### 2.3 What to keep from the current build

React 19 · Vite 8 · Tailwind 4 · shadcn-style CSS variables · `.dark` class toggle persisted to
localStorage · lucide-react.

**None of that is the problem and none of it should be rewritten.** This is an information-architecture
and screen-inventory project, not a re-platform. Any plan that starts with "migrate to X" has
misdiagnosed it.

---

## 3 · The spine: What · So what · Now what

The user's framing, and it is the right one because it names the actual failure mode of risk
dashboards: **we had a problem, we built a dashboard, and now nobody knows what to do.**

Every screen and every card in this redesign resolves three layers, in order, top to bottom:

| Layer | Question | Where the answer comes from |
|---|---|---|
| **What** | What did we observe? | The finding, the posture, the registry fact. Evidence-backed, hash-linked. |
| **So what** | Why does it matter *to us*? | Requires the **inherent tier** — the buyer's declared exposure. Without it, there is no "so what" and the UI must say so rather than invent one. |
| **Now what** | What do I do next, and who owns it? | The `ask_of_vendor`, the flow-down clause, the adjudication, the declaration, the schedule. |

### The four rules this spine imposes

**1 · Every card ends in an action or an explicit statement that there is none.**
A card whose last row is a number is unfinished. Where no action exists, the card says *"No action —
this is context for the decision below"* and links to the decision it feeds. Silence is not an option
because a reader assumes silence means "nothing needed."

**2 · "So what" is refused when the inherent tier is undeclared, and refused loudly.**
This is the strongest UI consequence of E10b's rule that undeclared ≠ low. Where the tier is missing,
the So-what band renders as a **declaration prompt**, not as a blank and not as a neutral grey:

```
┌─ SO WHAT ───────────────────────────────────────────────────┐
│  ⚠  We cannot tell you what this means to you.              │
│                                                              │
│  Residual risk needs your declared exposure, and nobody      │
│  has declared it for this relationship. That is not "low"    │
│  — it is the question nobody has answered.                   │
│                                                              │
│  [ Declare inherent exposure ]   ~2 minutes, no re-scan      │
└──────────────────────────────────────────────────────────────┘
```

That button is `POST /api/vendors/{ref}/inherent`. It is the single highest-value control in the
whole redesign, because **one declaration lights up four downstream features at once**.

**3 · A provisional declaration annotates; it never gates.**
Consistent with `app/inherent_register.py`. Where `inherent.provisional` is true, the residual tier
renders normally with a small **provisional** chip and a one-line hover: *"Declared on the register,
not yet confirmed by the relationship owner."* Chip is muted, not warning-coloured — a provisional
answer is a real answer.

**4 · Now-what actions carry an owner and a due date, or they are not actions.**
"Request their DMARC policy" is a task. "Request their DMARC policy — Procurement, by 14 Aug" is a
commitment. The backend already supplies both halves: `ask_of_vendor` and `recheck_after`.

---

## 4 · Information architecture

### 4.1 Routes

```
/                          Portfolio — the book, and what needs a human
/vendors/:ref              Vendor assessment — the What/So what/Now what stack
/vendors/:ref/pack         Evidence Request Pack (P3), procurement + security views
/vendors/:ref/contract     Contract flow-downs (P4) + exit readiness (P8)
/vendors/:ref/evidence     Receipts — hash-stamped, verifiable
/queue                     Adjudication queue — blocked records needing a person
/inventory                 The inventory of record — 3 populations, declaration gaps
/program                   Programme maturity + KPIs + monitoring health (P9)
/methodology               Existing. Keep. It is the "Evidence, not promises" proof.
```

**Nav grouping**, mirroring wahidai.com's numbered-module pattern:

```
01 · Portfolio        the book
02 · Assess           score a vendor
03 · Act              queue · inventory
04 · Programme        maturity · KPIs · monitoring
—
Methodology
```

### 4.2 Landing on `/` is the biggest single change

Today the app opens on an **empty search box**. That is the right home screen for a demo and the
wrong one for a programme with 146 vendors, 23 declared relationships and 6 records waiting on a
human.

The new `/` opens with **"What needs a person today"** — before any chart:

```
┌────────────────────────────────────────────────────────────────────────┐
│  6 blocked          23 undeclared*     0 overdue        ⚠ schedule     │
│  awaiting a         relationships      re-checks         last run      │
│  decision           unconfirmed                          2h ago  ✓     │
│  → Work the queue   → Confirm          → —               → Health      │
└────────────────────────────────────────────────────────────────────────┘
```

Each tile is a **Now what**, not a statistic. Each links to the screen that resolves it. A tile at
zero renders in muted grey with no link and no call to action — it is not a win to celebrate, it is
a queue that happens to be empty.

**The schedule-health tile is non-negotiable and must never be omitted for space.** `monitoring_currency`
can read 100% on a schedule that died in March, because nothing is re-scored into staleness when
nothing is re-scored. The tile reads `monitoring_health()` from `/api/program/monitoring`, where
**silence is the alarm condition**, and it is the only element on the page that can tell a live book
from a frozen one.

### 4.3 The pairing rule for every posture figure

**Posture and confidence are never rendered apart.** Not in a table cell, not in a tile, not in a
sparkline tooltip. The backend keeps them as separate `Score` fields and holds an invariant that they
never collapse; the UI must hold the same line visually.

```
   A  91          A  91  ·  32% coverage
   ────          ─────────────────────────
   WRONG          RIGHT — and at 32% the grade renders in --ghost,
                  not in green, with "Ghost — unassessed, not safe"
```

**The Ghost cliff is a visual state, not a footnote.** Below the coverage floor the product does not
publish a posture at all, and the card must show the refusal in the space where the number would have
been — never a greyed-out number, which reads as "roughly this."

---

## 5 · Screen designs

### 5.1 `/vendors/:ref` — the assessment

The whole page is one What / So what / Now what stack. **Three bands, always in this order, never
collapsed into tabs** — tabs would let a reader take the What and leave without the Now what, which
is the exact failure this redesign exists to fix.

```
╔═══════════════════════════════════════════════════════════════════════════╗
║  Atlassian                                    atlassian.com               ║
║  T1 Critical · full depth · quarterly            [Declare] [Export ▾]     ║
╚═══════════════════════════════════════════════════════════════════════════╝

┌─ WHAT WE OBSERVED ────────────────────────────────────────────────────────┐
│                                                                            │
│   Posture 79 (B)          Confidence 74%          Assurity 62             │
│   ▓▓▓▓▓▓▓▓▓░              ▓▓▓▓▓▓▓░░░              ▓▓▓▓▓▓░░░░              │
│                                                                            │
│   ── by category ────────────────────────────────────────────────────────  │
│   Cyber hygiene          68  ▓▓▓▓▓▓▓░░░   4 findings   9/12 signals       │
│   Breach history        100  ▓▓▓▓▓▓▓▓▓▓   clean        3/3                │
│   Digital footprint      —   not assessed              0/3  ← why?        │
│   ...                                                                      │
│                                                                            │
│   Continuity: registered, good standing · Service: operational (P7)        │
│                                                                            │
│   ⓘ COVERAGE STATEMENT (P2)                                               │
│   This assessment saw 9 of 12 planned signals. It could not see internal   │
│   controls, and it did not attempt to.                                     │
│                                     [ what was not checked, and why → ]   │
└────────────────────────────────────────────────────────────────────────────┘

┌─ SO WHAT ─────────────────────────────────────────────────────────────────┐
│                                                                            │
│   Residual risk    ███ MEDIUM ███        [provisional]                    │
│                                                                            │
│   Posture 79 (moderate) against HIGH inherent exposure.                    │
│   Inherent = max(criticality: high, data access: high) — the WORSE of the  │
│   two, because neither offsets the other.                                  │
│                                                                            │
│   Strong controls do not resolve high exposure to low residual risk. The   │
│   controls look good today; the exposure is what you carry if that changes.│
│                                                                            │
│   Expectation gap: performs as expected for its cohort (n=10)              │
│   Compliance gap: ISO 27001 claimed, not evidenced                         │
│   Concentration: shares AWS ap-southeast-2 with 7 other critical vendors    │
│                                                                            │
│                                     [ see the 16-cell matrix → ]          │
└────────────────────────────────────────────────────────────────────────────┘

┌─ NOW WHAT ────────────────────────────────────────────────────────────────┐
│                                                                            │
│   ① Ask the vendor          4 items · Procurement · by 14 Aug             │
│      DMARC policy, cert lifecycle, ISO cert PDF, VDP contact               │
│                                              [ open request pack → ]      │
│                                                                            │
│   ② Put in the contract     3 clauses · Legal                             │
│      Breach notification 72h · Sub-processor register · Exit assistance    │
│                                              [ open flow-downs → ]        │
│                                                                            │
│   ③ Next assessment         quarterly · due 12 Nov · full depth           │
│      Pulled forward to 8 Aug by an expired-cert finding (7d re-check)      │
│                                                                            │
│   ④ Decision                [ Approve ] [ Approve w/ conditions ] [ … ]   │
│      Recorded against this score, append-only, with your name on it.       │
└────────────────────────────────────────────────────────────────────────────┘
```

**Details that carry real weight:**

- **`Digital footprint — not assessed ← why?`** — an un-assessed category must be visibly different
  from a category that scored 100. Today's UI risks rendering both as "no problems". The `why?` link
  opens the coverage statement's third bucket.
- **The residual band quotes E10b's caveats verbatim.** They are already written, already argued, and
  paraphrasing them in the UI is how a carefully-worded refusal becomes a soft one.
- **The re-check pull-forward is shown as a *reason*, not just a date.** "Due 12 Nov, pulled to 8 Aug
  by an expired-cert finding" tells a reader why their quarterly vendor is on their desk in a week.

### 5.2 `/queue` — adjudication

Straight rendering of `/api/adjudications/queue`, and the design rule is inherited wholesale from the
module: **it annotates, it never sorts by weakness.**

```
┌────────────────────────────────────────────────────────────────────────────┐
│  6 blocked   ·   5 sanctions   ·   1 entity dissolved                      │
│  Ordered by INHERENT EXPOSURE. Not by how weak the match looks.            │
└────────────────────────────────────────────────────────────────────────────┘

┌─ orange ──────────────────────────── corpus · no tier · blocked 0.1d ─────┐
│                                                                            │
│  Query "orange"  →  ORANGE VOLUNTEERS          head match · Entity · SDN   │
│                                                                            │
│  What to check                                                             │
│  • HEAD match — the query is the leading words of a longer listed name     │
│  • THE QUERY IS ONE ORDINARY ENGLISH WORD. Collisions on common words      │
│    carry far less information than collisions on coined names — compare    │
│    'experian', which collides with nothing.                                │
│  • Seeded benchmarking vendor, not a relationship.                          │
│                                                                            │
│                       [ Clear — not this entity ]  [ Uphold — escalate ]  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Two UI rules the backend's discipline requires:**

1. **No bulk-clear control. Ever.** Not even behind a confirm. A "clear all" button is the rubber
   stamp the sanctions review named, implemented in the interface. Each decision is one click on one
   record, and that friction is the feature.
2. **The decision buttons are equal weight.** Neither is primary-coloured, neither is pre-focused.
   A UI that makes *Clear* the easy button has made the decision on the user's behalf.

### 5.3 `/inventory` — the inventory of record

Three columns, because the whole point is that they are three different populations:

```
  RELATIONSHIPS  23      SEEDED CORPUS  114      INVENTORY DEFECTS  9
  an exposure to         no relationship,        typos, products,
  declare                nothing to declare      own domains
  ─────────────────      ─────────────────       ─────────────────
  ✓ 23 declared          These are excluded      aatlassian → atlassian
  ⚠ 23 PROVISIONAL       from the declaration    http://servicenow → dupe
    0 confirmed          rate by design.         jira → a product
  → Confirm with owners                          → Retire these refs
```

**The "excluded by design" copy is load-bearing.** A reader seeing 114 vendors in a column headed
*corpus* will assume they are being ignored unless the page says why. And the sentence to use is the
register's own: *there is no commercial relationship, so there is no exposure, and inventing one to
move a metric is the failure this register exists to prevent.*

**`unregistered` gets its own alert row above the three columns** whenever it is non-zero. A vendor
nobody has classified is neither declared nor excused, and it must not be quietly absorbed into any
of the three.

### 5.4 `/program` — the programme

Two halves, as `/api/program` already serves them.

**Maturity** renders as eight horizontal bars, 1–5, with the **minimum marked and the average
deliberately not shown as a headline**:

```
  Level 2 / 5 — Reactive
  The MINIMUM across eight dimensions, not an average.
  Held there by: Lifecycle coverage.

  Governance & policy            ███░░  3 Defined
  Inventory & tiering            ███░░  3 Defined      ↑ was 2
  Assessment methodology         ████░  4 Managed
  Continuous monitoring          ███░░  3 Defined      ↑ was 2
  Remediation & issues           ███░░  3 Defined
  Lifecycle coverage             ██░░░  2 Reactive  ◀ THE FLOOR
  Technology / data quality      ███░░  3 Defined
  Reporting & engagement         ████░  4 Managed

  ⓘ The average is 3.1. It is not the headline, because an average lets
    strength where we are naturally strong conceal the dimension that will
    fail an audit.
```

The floor dimension is the only one that gets an accent-coloured marker, and its `to_reach_next` text
renders expanded by default. **Every other dimension is collapsed.** The screen's job is to produce
one next action, not eight.

**KPIs** render as 15 rows. Three formatting rules, all inherited:

- An **unsupplied** manual metric shows an empty cell and its owner's name — never a dash, never a
  zero, never "N/A". `— Finance partner owns supplying this` reads as a chase; `0` reads as a fact.
- **`unsupplied` and `not_computable` are visually distinct.** One is a programme gap with an owner;
  the other is a fact about the book. Same-looking empty cells would let an unmeasurable metric read
  as an unassigned chore.
- **A peer figure never renders without its caption.** `Shared Assessments 2025, n=214` sits directly
  under the comparison, at the same emphasis, always.

### 5.5 `/vendors/:ref/pack` — the two audience views

A single toggle: **Procurement** / **Security**. Same data, two renderings, from `/export?view=`.

The invariant `views_agree()` already ships in the backend. The UI addition worth building: **if the
two views ever disagree, the page renders an error rather than either view.** That will never fire —
which is exactly why it costs nothing and is worth having, since the day it does fire is the day
somebody is signing off on a number the security team never saw.

Procurement view leads with the decision and ends with the ask. Security view leads with the findings
and ends with the receipts. **Section order is asserted by test in the backend and the UI must not
reorder it** — the order *is* the argument.

---

## 6 · Component inventory

| Component | Purpose | Rule it enforces |
|---|---|---|
| `<WhatSoWhatNowWhat>` | The three-band page shell | Bands cannot be reordered or tabbed |
| `<PostureConfidencePair>` | Renders the two axes together, always | Cannot be given a posture without a confidence — a required prop, so it is a build error |
| `<GhostState>` | Refusal in the space a number would occupy | Never a greyed number |
| `<DeclareInherentPrompt>` | The So-what refusal + declaration CTA | The single highest-value control in the app |
| `<ProvisionalChip>` | Muted chip + one-line explanation | Annotates, never gates |
| `<ActionRow>` | Task + owner + due date | Refuses to render without an owner |
| `<EvidenceLink>` | Hash-stamped receipt link, mono font | "Evidence, not promises" |
| `<CoverageStatement>` | P2's three buckets, verbatim | Never paraphrased |
| `<EmptyMetric>` | Unsupplied vs not-computable, visually distinct | Two kinds of missing, kept apart |
| `<PeerFigure>` | Value + survey/year/n caption | Cannot render without the caption |
| `<RiskBand>` | Colour from residual tier, not posture | Ghost/Blocked are off-ramp hues |

**`<PostureConfidencePair>` deserves the emphasis.** Making `confidence` a required prop turns the
system's central invariant into a compile-time property of the UI. Someone who wants to render a bare
posture has to delete a component to do it, and that is a reviewable diff rather than an accident.

---

## 7 · Rules the UI must not break

Mirrors of backend invariants. **A change that breaks one of these is out of scope for a visual
refresh**, in exactly the same way `docs/phases.md` treats its engine invariants.

| Rule | Why |
|---|---|
| Posture never renders without confidence | The two axes never collapse |
| An undeclared inherent tier is a **prompt**, never a blank or a neutral default | Undeclared ≠ low, and the dangerous default is low |
| Ghost and Blocked use off-ramp hues | Unassessed is not "moderately safe" |
| Coverage statements and E10b caveats render **verbatim** | A paraphrase of a carefully-worded refusal is a softer refusal |
| Every number links to its receipt | "Evidence, not promises" |
| No bulk-clear on the adjudication queue | Friction is the control |
| Adjudication buttons are equal weight | A primary-coloured *Clear* decides for the user |
| Manual metrics render empty with an owner | Never backfilled, never estimated, never zero |
| Peer figures carry survey · year · n | A comparison whose population is unstated is not a benchmark |
| Nothing in the UI recomputes a score | It renders the immutable `Score`; it never derives a second one |

---

## 8 · Build sequence

Ordered by **operational value delivered**, not by rendering difficulty. Each stage ships usable.

| # | Stage | Unblocks | Rough size |
|---|---|---|---|
| **1** | `<DeclareInherentPrompt>` + `POST /inherent` on the existing scorecard | Lights up residual risk, P3 tags, P5 depth. **The one change with the largest downstream effect** | ~2 days |
| **2** | The three-band vendor page (§5.1) with residual, coverage, assessment plan | Turns a score into a decision | ~1 week |
| **3** | `/` portfolio with the "needs a person" tiles + schedule-health | Turns the app from a demo into a book | ~4 days |
| **4** | `/queue` adjudication | 6 records currently blocked with no interface | ~3 days |
| **5** | `/vendors/:ref/pack` + `/contract` (P3, P4, P8) | The Now-what actions become clickable artefacts | ~1 week |
| **6** | `/inventory` | Makes the 23 provisional declarations chaseable | ~3 days |
| **7** | `/program` maturity + KPIs | The sponsor view | ~1 week |
| **8** | E14's *Generate Gap Analysis* button | Depends on E14 shipping; see `docs/phases.md` | after E14 |

**Stage 1 alone is worth doing this week**, independent of everything else. The backend route exists,
the register exists, and 23 relationships are one form away from confirmed rather than provisional.

---

## 9 · Explicitly out of scope

- **Re-platforming.** React 19 / Vite 8 / Tailwind 4 stay.
- **A charting library.** Every visualisation above is a bar, a ramp or a table. Adding a charting
  dependency for eight horizontal bars is how bundle size and a second design language arrive together.
- **Mobile-first layout.** This is an analyst's desktop tool. Responsive down to tablet; not a phone
  product, and pretending otherwise would compromise the dense tables that are the point.
- **A vendor-facing portal.** The dispute path is an API today. A vendor-facing surface is a different
  product with a different threat model.
- **Any UI that writes a score.** The frontend renders the immutable `Score` and never derives one.

---

## 10 · The one open question for a person

**§2.2's palette is carried forward, not measured.** Someone with devtools open on wahidai.com should
confirm the six values before stage 1 begins. If they differ, `src/index.css` is the only file that
changes — but it should change *before* eight screens are built against the wrong navy, not after.
