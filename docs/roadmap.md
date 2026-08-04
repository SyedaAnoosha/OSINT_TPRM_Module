# Roadmap — from PoC to the Wahid AI third-party module

**Deliverable: the roadmap.** How this proof-of-concept productises, how it aligns with the wider TPRM platform, and
what we would collect next — sequenced by *value and regulatory pull*, and gated by the same legality-first bar that
built v1.

> **The rule that governs this roadmap:** every future source clears the same bar as the v1 register — *free (or a
> free key), commercial + automated use permitted, no ToS trap, reachable and parseable*. Nothing on this list is
> "collect first, check later." Where a source is held, it is held on a **named open item**, not a vague maybe.

---

## 1. Where v1 stands

A working PoC takes a **vendor name or domain → an evidence-linked posture score** assembled from 26 lawfully-public
signals across 14 failure-isolated collectors, written to an **immutable, hash-stamped evidence store first**, then
scored by the penalty-based posture model in [`scoring.yaml`](../scoring.yaml) v4.2.0 (see
[`scoring_model.md`](scoring_model.md)). Every deduction is published with a **plain-English reason**, and the model
is held in place by a **frozen five-vendor regression corpus** — so a change that re-grades a vendor is visible as a
diff rather than a surprise.

**Seven categories score today.** Five are **designed but held** — no free lawful source feeds them yet — and sit in
the config's `held_roadmap` so the model describes only what actually scores. Closing that gap, lawfully, is the
spine of this roadmap.

| Category | v1 status | Unlock |
|---|---|---|
| Cyber Hygiene · Breach History · Digital Footprint · Transparency · Business Stability · Compliance · Adverse Media | **Scoring** | — |
| **Supply Chain & Dependency** | Held | Re-feed from *already-cleared* DNS/CT/trust — no new clearance (§3.1) |
| **Data Privacy & Leakage** | Held | No clean free collector yet (HIBP domain is paid) — policy-page parse (§3.3) |
| **Geopolitical & FOCI** | Held | Corporate-registry terms (open item 7) + DFAT licence — **highest-value** (§3.2) |
| **ESG & Ethical** | Held | Modern Slavery Register licence (open item 2) |
| **Emerging Tech & AI** | Held | No lawfully-observable external source |

---

## 2. Near-term — unlock held categories, lawfully (0–3 months)

### 2.1 FOCI is the highest-value next item — a named buyer with a regulatory clock

The **SOCI Enhanced CIRMP Rules 2026** make FOCI (Foreign Ownership, Control or Influence) assessment of major
suppliers **legally mandatory** for critical-infrastructure operators, with a **~mid-2028 deadline**. That is a
regulator creating demand for exactly this signal. It is blocked only on **corporate-registry terms**, and the path
is already scouted: **Companies House (UK)** is CLEARED (OGL, commercial-OK, free key, 600/5min) and **ABN Lookup
(AU)** is CLEAR-CONDITIONAL (third-party extracts OK, free GUID). Wiring both as keyed Business-Stability collectors
adds authoritative AU/UK standing *and* the entity-level ownership chain FOCI needs — **entity-level only, never
director personal data** (holding the §4.2 bright line).

### 2.2 Fourth-party concentration is the sharpest commercial wedge

CPS 230 ¶48 makes fourth-party risk a *regulated obligation*, and DORA's dry run found only **6.5% of ~1,000 EU
firms** passed all data-quality checks — most failing on **missing subcontractor information**. That is a quantified
market failure in precisely the data we already extract for free from public DPAs and subprocessor lists. **Supply
Chain unlocks with no new source clearance** — it re-feeds from the DNS/CT/trust collectors we already run: third-party
infra suffixes in DNS/MX/CNAME (`amazonses.com`, `okta.com`, `cloudflare.net`), CT SAN dependencies, and published
`/subprocessors` lists. The build is a normaliser enhancement plus a "critical third-party" dictionary. Per-vendor
enumeration ships first; **portfolio-wide concentration** ("six of your vendors share one subprocessor") needs the
platform's portfolio view (§4) — and is the finding a client **cannot obtain any other way**.

### 2.3 Data Privacy & Leakage — a policy-page parse

No clean free breach-corpus re-feed exists (HIBP's domain endpoint is paid), but the *disclosure* half is reachable:
parse published privacy policies / DPAs for retention, cross-border transfer, and breach-notification commitments —
already-fetched pages, an LLM-classification enhancement, no new egress.

### 2.4 Australian sanctions + ESG — close the two "ask-first" licences

Two locally-relevant sources are **held pending a written licence query**, exactly as the brief instructs
(*ask before you collect*): **DFAT Consolidated List** (Australian Sanctions Office) to add AU sanctions to the gate,
and the **AU Modern Slavery Register** (Attorney-General's Department) to open the ESG category. Both are drafted;
neither is ingested until the licence is confirmed.

---

## 3. AI integration — where it genuinely saves the analyst work

Not bolted on — placed at the two moments the brief itself names, where a human would otherwise read unstructured
text by hand:

- **Adverse-media triage (live, opt-in).** The evidence summariser already digests the finished record; the next
  step is letting it adjudicate **GDELT** candidates (held today for defamation exposure) — reading which
  adverse-media hits *actually matter* and surfacing them as **review items with evidence**, never auto-published
  verdicts. Provider-agnostic, off by default, read-only, cited to hash-stamped receipts — the single documented
  egress point, never a scorer.
- **Trust-page classification.** Turn an unstructured trust page into structured certifications with expiry dates
  (ISO 27001 / SOC 2 claims → normalised signals) — the Compliance category's self-reported inputs, machine-read.
- **Contradiction-flagging.** The highest-value AI use is comparing the vendor's *self-assessment* against the
  *public record* and flagging where they disagree — the one thing questionnaires can't do for themselves.

---

## 4. Agentic AI — act, don't just answer

The brief asks where the system could act on the user's behalf. Three steps, each building on the immutable evidence
store (every score is reconstructible, so drift is *provable*, not asserted):

1. **Scheduled re-checks.** Re-run a vendor on a cadence rather than on demand — the collectors are already
   idempotent and failure-isolated.
2. **Drift alerts.** Because each run is hash-stamped, a **posture move** (a cert expired, a new breach, a KEV match,
   an LEI lapsed, a domain entered registry hold) raises a flag with the before/after receipts attached — surfacing a
   change instead of waiting to be asked.
3. **Continuous concentration monitoring.** At portfolio scale, watch for a *shared* fourth-party dependency
   emerging across many vendors — a systemic signal no single-vendor questionnaire can see.

---

## 5. Alignment with the wider TPRM platform (the Wahid AI third-party module)

The PoC is deliberately shaped to slot in as **the outside-in, evidence layer** of the platform's third-party module —
it does not replace the questionnaire framework, it pre-fills and pressure-tests it:

- **Portfolio view.** v1 scores one vendor; the platform holds many. That unlocks the concentration finding (§2.2),
  cross-vendor benchmarking, and drift dashboards.
- **Questionnaire pre-fill + contradiction.** OSINT independently evidences the fraction of due-diligence criteria a
  stranger *can* see (~7 of ~27), and **flags contradictions** where a vendor's self-assessment disagrees with the
  public record — turning weeks of evidence-chasing into a reviewed exception list.
- **Two axes carried through.** The platform inherits the non-negotiable that **posture and confidence never
  collapse into one number** — a Ghost (clean-looking, thinly-evidenced) routes to a questionnaire; an evidenced
  exposure routes to action.
- **The sanctions gate and evidence store are platform primitives.** The gate (block → human adjudication, never a
  silent grade) and the immutable, hash-stamped store (the legal artefact behind every score) are exactly the
  controls a regulated buyer under CPS 230 needs — they generalise straight into the platform.

---

## 6. Engineering hardening (parallel track)

Client-ready, not prototype — the craft items that separate the two.

**Landed (v4.2.0).** Four items are done and are listed because they change what the roadmap can safely assume:

- **A frozen regression corpus.** Five real vendors' collector output captured once into `backend/tests/fixtures`,
  replayed against a pinned clock and asserted to per-category penalties. Every model change from here is a
  reviewable diff naming the vendor and category that moved. Re-baseline deliberately with `python -m tests.regolden`.
- **Plain-English explanations.** All 54 penalising bands carry a consequence-first sentence in `scoring.yaml`,
  surfaced per finding and summarised in a one-line headline. The loader refuses to start if a penalising band has
  no reason, or if a reason outlives its band.
- **The receipts reconstruct the score.** `effective_penalty` and `occurrences` are now persisted (both the SQLite
  and Postgres backends), so stored findings sum exactly to the published category penalties. Previously only the
  pre-adjustment base was stored, and a decayed breach's receipt visibly failed to add up.
- **A drift guard on the model file.** Every `scoring.yaml` key must declare itself engine-read or
  documentation-only; anything else fails at load. This closes the failure mode that had produced two inert NIST
  variables, a dead KEV band, and an NVD band whose name asserted a fix no source had observed.

**Open:**

- **A dispute / refute path (open item 12).** Outside-in scoring *systematically over-penalises* because it can't see
  compensating controls; both benchmarked platforms accept evidenced refutes for exactly this reason. Publishing a
  score with **no contest mechanism** is a known gap — a reviewer-facing adjudication queue is the fix, and it
  generalises the gate's existing human-in-the-loop. The explanation surface makes this materially easier: a client
  now disputes a *named sentence*, not an opaque number.
- **Multi-asset collection.** The model already specifies **weakest-link across assets**; the PoC scores the primary
  asset. Discovering and scoring an in-scope asset set is a pipeline build, not a model change.
- **A remediation source, or retire the mitigation variable.** The NIST mitigation factor (×0.6) is wired end-to-end
  and correct, but **dormant**: nothing we lawfully collect evidences that a vendor fixed a given issue. KEV says a
  product line is known-exploited; NVD says a CVE exists. Running-version detection is the only real evidence and
  sits close to the active-scanning line the project refuses; vendor advisories are self-reported, which contradicts
  the variable's own "corroboration over claims" defence. A guard test asserts the dormancy, so wiring any source
  forces the docs and UI to be corrected in the same change.
- **Three loose ends.** `score_harness.py` still references pre-v4 fields and would crash if run (the corpus
  supersedes it); the GDELT collector emits a `tone_volume` signal the model has no home for, so it is dropped with
  a warning every run; and `Finding.severity_base` is vestigial.
- **A second subdomain source.** CT (crt.sh + Cert Spotter) is the real single point of failure for Digital
  Footprint; **AlienVault OTX passive DNS** is cleared-pending-a-free-key as CT redundancy.
- **Evidence store → Postgres (Neon).** Append-only triggers and hash-stamping already exist on both SQLite and
  Postgres; the platform path is the managed Postgres with the immutability guarantees carried through.
- **Attribution obligations are UI requirements, not footnotes** — the NVD non-endorsement notice, HIBP CC BY link,
  and GDELT citation ship *with* the scorecard.

---

## 7. Sequenced plan

| Horizon | Item | Unblocks | Blocked on |
|---|---|---|---|
| **Now** | Supply Chain re-feed (DNS/CT/trust) → per-vendor fourth-party enumeration | CPS 230 ¶48 wedge | *nothing — already-cleared sources* |
| **0–1 mo** | Companies House + ABN keyed collectors | FOCI (§2.1), AU/UK standing corroboration | free key/GUID registration |
| **0–1 mo** | DFAT + Modern Slavery licence queries | AU sanctions gate, ESG category | written licence replies (open items 1, 2) |
| **1–3 mo** | GDELT AI-adjudication (adverse-media triage) | Adverse Media depth | operator-enabled LLM provider |
| **1–3 mo** | Trust-page + privacy-policy LLM classification | Compliance, Data Privacy | — |
| **3–6 mo** | Portfolio view → concentration monitoring | The platform's core wedge | platform integration |
| **3–6 mo** | Scheduled re-checks + drift alerts (agentic) | Continuous monitoring | scheduler + notification layer |
| **Ongoing** | Dispute path · multi-asset · OTX redundancy | Client-readiness / fairness | — |
| **Ongoing** | A corroborating remediation source, or retire the mitigation variable | The 4th NIST variable becoming real | no lawful free source evidences a fix (§6) |
| **Done** | Regression corpus · plain-English reasons · reconstructible receipts · config drift guard | Safe model change, client-legible scores | — |

---

### See also

- [`research_doc.md`](research_doc.md) — the source register these next-sources are vetted against
- [`scoring_model.md`](scoring_model.md) — the model the held categories plug into
- [`methodology.md`](methodology.md) §8.3 — the FOCI / fourth-party roadmap headline and open items
- [`source_assessment.md`](source_assessment.md) — per-source clearance status, including the roadmap-cleared keyed registries
