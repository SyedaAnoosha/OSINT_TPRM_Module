# Vendor Comparison Scenarios

**Status:** Implemented — phase 2 of the stakeholder feedback response (financial data integration, scoring-model test coverage, scorecard UX)
**Executable as:** [`backend/tests/test_vendor_comparison_scenarios.py`](../backend/tests/test_vendor_comparison_scenarios.py) — 9 numbered scenarios, 11 test functions, all passing against the real `scoring.yaml`

This is the plain-English version of the acceptance criteria the test file encodes. Each scenario compares two synthetic vendors that differ in exactly one respect, states what the platform must show, and explains why. Read this to review *what the model should do*; read the test file to see *that it does*.

Two scenarios deliberately depart from a literal reading of the original request, for reasons explained inline — the platform can only be tested against signals it actually scores.

---

## Scenario 1 — Severe breach history vs. no known breach

**Setup:** Two otherwise-identical, fully-evidenced vendors. Vendor A has a confirmed breach exposing passwords or payment card data. Vendor B has no known breach.

**Expected:** A's `breach_compromise_history` category takes a real penalty; B's does not. A's overall posture is materially lower than B's.

**Why it matters:** This is the most basic discrimination test — a real, severe security event must move the score, and move it in a category a reader can trace directly to the finding.

**Note on "adverse media":** the original request framed this as "severe adverse media vs. none," implying GDELT-sourced news coverage. Today, GDELT adverse-media findings are **enrichment/review-queue only** — they are not declared anywhere in `scoring.yaml`, so a collector emitting one is silently excluded from scoring rather than penalising posture (confirmed directly against the shipped config, `test_scenario_1b`). This is worth stating to stakeholders plainly rather than leaving it implied: **adverse media does not move the score today.** If that's a gap worth closing, it's a `scoring.yaml` design decision (what band structure, what corroboration bar) — a separate piece of work from this test suite, and one the model's own "no invented derived index" discipline (see `tprm_feedback_redesign.md` §0) argues should be approached carefully. Confirmed breach history (`breach_by_data_class`) is the real, already-scored analogue used for this scenario instead.

---

## Scenario 2 — Bankrupt vs. financially healthy vendor

**Setup:** Two vendors with byte-identical cybersecurity evidence. The only difference: one's company registry record shows liquidation/administration (`entity_status: entity_inactive`); the other shows active good standing.

**Expected:** Posture, confidence, and grade are **identical** between the two. The Business Stability / Continuity standing differs — one reads `ceased`, the other `sound` — and is visible to a reader, just not blended into the security number.

**Why it matters:** This is the single most important scenario in the whole feedback response. It's the direct regression guard for a real historical defect (E4, see `change-notice-v5.md` §3.4): a vendor entering administration used to lose 20 points of *technical security posture*, even though going into administration says nothing about their TLS configuration. Financial distress is real, serious, and must be surfaced — just never mixed into the axis that answers "how exposed is this vendor to compromise."

**Companion scenario (2b):** the same invariant, proven specifically for the *new* collectors this feedback item added (The Gazette, SEC EDGAR, CourtListener) rather than the pre-existing Companies House signal. A `bankruptcy_petition` finding from CourtListener changes neither posture nor confidence versus not having collected it at all — see "A note on how this nearly went wrong" below.

---

## Scenario 3 — Multiple historical breaches vs. none

**Setup:** Vendor A has both a confirmed breach *and* a KEV-listed (actively-exploited) vulnerability — two separate findings in `breach_compromise_history`. Vendor B is clean on both.

**Expected:** A's category penalty reflects **both** findings, not just the worse one — but not their full arithmetic sum either (see Scenario 9). A's posture is materially lower than B's.

**Why it matters:** A vendor with a pattern of security failures should read as worse than one with a single incident, without the model becoming a simple penalty-adding machine that a large enough vendor can never recover from.

---

## Scenario 4 — Poor email security vs. strong email security

**Setup:** Vendor A publishes no DMARC, SPF, or DKIM records. Vendor B publishes DMARC at `p=reject`, a hard-fail SPF record, and DKIM.

**Expected:** A's `identity_email` category takes a real penalty; B's does not. A's posture is lower.

**Why it matters:** Domain-impersonation risk (can someone send email pretending to be this vendor?) is one of the clearest, most binary signals in the model, and the most intuitive one for a non-technical reader to verify themselves.

---

## Scenario 5 — Expired certificate vs. valid certificate

**Setup:** Vendor A is serving an expired production TLS certificate. Vendor B is fully clean, including a valid certificate. Both are otherwise identically well-evidenced.

**Expected:** Vendor A is **capped at posture 49** (the top of Grade D) — not merely penalised proportionally. Vendor B publishes well above that.

**Why it matters:** `cert_validity` is the *only* signal wired to the model's "critical ceiling" — a non-compensatory knockout that says no amount of cleanliness elsewhere can outweigh serving an expired certificate live, in production, right now. This is qualitatively different from every other finding in the model, and the dashboard needs to show it differently (a hard cap, not a deduction) — see Phase 3.

---

## Scenario 6 — Low evidence coverage vs. high evidence coverage (the Ghost)

**Setup:** Vendor A has only 11 of 27 signals answered, all clean. Vendor B has all 27 of 27, also all clean.

**Expected:** A bands **Low confidence** and is flagged as a **Ghost** — a vendor that *looks* clean only because so little was checked. B bands **High confidence** and is not a Ghost.

**Why it matters:** This is the scenario that most directly explains why the executive dashboard (Phase 3) must show Confidence as its own tile, never folded into Posture. A clean-looking score on thin evidence is not the same claim as a clean-looking score on thorough evidence, and conflating them is exactly how a barely-evidenced vendor could look identical to a thoroughly-vetted one.

---

## Scenario 7 — Independent, corroborated assurance vs. a disclosure-only claim

**Setup:** Vendor A claims a security certification that is **not** corroborated against any registry (`cert_posture: claimed_unverified`). Vendor B publishes a detailed trust/security page with no verifiable certification claim at all (`program_disclosure: detailed_policies`).

**Expected:** A's claim reaches `compliance_regulatory` and takes a real penalty (an unverified claim is worse than no claim — see below). B's disclosure lands in `assurance_context`, a context-only category that **never** penalises posture.

**Why it matters:** This is a deliberately drawn distinction from the model's own history (E5): a certification claim that can be checked against a registry is *evidence*; a marketing trust page is not. Note the asymmetry is not "corroborated beats disclosed" in the simple sense — an *unverified* claim actively costs points (asserting something that doesn't check out), while a vendor with no certification claim at all pays nothing for it. A vendor with genuine, registry-corroborated certification (`cert_posture: registry_corroborated`) scores a clean pass, which is the intended positive case this scenario's mirror image demonstrates.

---

## Scenario 8 — Regulatory enforcement action vs. a sanctions-list match

**Setup:** Vendor A has a formal regulatory enforcement action on record. Vendor B has a possible match against a sanctions list.

**Expected:** A **publishes** a score, penalised in `compliance_regulatory`. B receives **no score at all** — blocked pending human adjudication, not a Grade F.

**Why it matters:** These are two fundamentally different mechanisms the platform uses for "this is bad," and conflating them on a dashboard would misrepresent both. A regulatory action is a fact the model can weigh; a sanctions match is a legal question (dealing with a sanctioned entity can be a criminal offence) that a number must never appear to answer. The dashboard (Phase 3) needs a visibly different treatment for "scored and penalised" versus "blocked, needs a human."

---

## Scenario 9 — Compounding findings: diminishing returns within a category

**Setup:** A vendor is missing three security headers (HSTS, CSP, X-Frame-Options) — three separate low-severity findings, all in `attack_surface_hygiene`.

**Expected:** The combined penalty is **less than** the sum of three individual penalties (1.5 points each) — specifically ≈3.29 points, not 4.5.

**Why it matters:** The tenth missing header on a vendor already missing nine tells a reader almost nothing new — it's the same underlying organisational fact ("nobody is minding the headers") counted repeatedly. Without this diminishing-returns rule, a vendor with many small, correlated gaps could rank worse than one with a single serious vulnerability, which inverts what actually matters. **This only applies within one category, never across categories** — a vendor with an expired certificate (`attack_surface_hygiene`) *and* no DMARC (`identity_email`) pays for both in full, because those are two independent facts about the vendor, not one fact restated.

---

## A note on how this nearly went wrong

While wiring the new financial-data collectors (The Gazette, SEC EDGAR, CourtListener — see `tprm_feedback_redesign.md` Phase 1), the first working version declared their signals in the same evidence-coverage denominator that gates every vendor's Posture confidence. That passed every unit test but **failed the frozen regression corpus**: replaying five real vendors' already-stored evidence against a denominator that grew by three (because that historical evidence naturally has no record for collectors that didn't exist yet) silently dropped every one of their confidence bands — Atlassian fell out of "High" confidence entirely, for no evidential reason.

The fix — and the reason Scenario 2b exists as its own test — was to give Business Stability its own, separate coverage count (`ScoringConfig.business_stability_signals`, `continuity.business_stability_coverage`), excluded from the Posture-confidence axis by construction. This is the same principle Scenario 2 demonstrates at the model-design level, caught here at the implementation level: **a new axis must never leak into an existing one's arithmetic, even by accident.**
