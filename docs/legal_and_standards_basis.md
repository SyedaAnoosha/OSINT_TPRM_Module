# Legal & Standards Basis for the Scoring Model

**Supports Deliverable 3** (v1 scoring model — the rationale layer)
**Status:** v0.1 draft · **Verified:** 17 July 2026 · **Author:** *(intern)*

---

## Purpose — and how this differs from `source_assessment.md`

`source_assessment.md` answers one legal question: **may we lawfully collect this?** It answers it well, per source, and that work is not repeated here.

This document answers the *other* legal question, which is not the same one and is currently unanswered anywhere in the project:

> **Once collected, does the score we build on top of it stand up?**

A source register can be flawless and the model built on it still indefensible. The two questions have different answers, different authorities, and — as the first finding below shows — different consequences for getting them wrong.

**Structure.** Four tiers, in descending order of how much they bind us:

| Tier | What it is | Why it matters | Optional? |
|---|---|---|---|
| **1** | Binding law that constrains the model itself | Non-compliance is unlawful | **No** |
| **2** | Regulatory instruments defining what a score must cover | Determines what the client must be able to evidence | **No** — this is the buyer's demand |
| **3** | Standards supplying defensible structure | Borrowed authority; "we follow X" beats "we decided" | Strongly recommended |
| **4** | AI governance instruments | Engages once AI touches the score | Conditional |

**Caveat, stated once and meant.** I am not a lawyer and this is not legal advice. Everything below is a documented, cited position for review by someone qualified — which is exactly the treatment the brief asks for ("ask before you collect, not after"). Claims verified verbatim against primary sources are marked **[verbatim]**; claims resting on secondary summaries are marked **[secondary — verify]** and should not be relied on until confirmed.

---

## The two findings that reframe the project

Everything else in this document is supporting detail. These two are load-bearing, and neither appears anywhere in the existing docs.

### Finding A — "Defensible" is a legal standard in Australia, not a client preference

The brief says *"any score you produce, you should be able to justify"* and reads as a quality bar. **It is not. It is a restatement of Australian law**, and there is a decided Full Federal Court authority directly on point.

In **`ABN AMRO Bank NV v Bathurst Regional Council` [2014] FCAFC 65**, Standard & Poor's was held liable for assigning a AAA rating to CPDO notes. The Full Federal Court's reasoning transfers to this project almost without modification:

- Publishing a rating conveys an **implied representation that the rating was formed on reasonable grounds and as the result of an exercise of reasonable care and skill**. Where it was not, the rating is **misleading and deceptive conduct**.
- The rating agency **owed a duty of care to investors** — a class of people it had **no contract with** — because the rating was procured for the purpose of being communicated to an ascertainable class who would rely on it.
- It is the **only common law case in which a ratings agency has been held liable** to compensate for losses on a rated product. It is Australian, it is appellate, and it is directly analogous.

**Why this lands on us specifically.** Wahid AI would publish a vendor risk score to clients who rely on it to make procurement decisions, exactly as investors relied on the AAA rating. Under **ACL s 18**, misleading or deceptive conduct requires **no intent** — *"it is no defence to say that the misleading conduct was an honest mistake."*

**Design consequences — these are requirements, not suggestions:**

1. **Every score must be reconstructible from stored evidence.** Not explainable in principle — reconstructible in fact, later, from what we retained. "Reasonable grounds" is proved with records or not at all.
2. **The evidence store is a legal artefact, not an engineering convenience.** `ref.md` proposes it as good architecture. It is better than that: it is the discharge of the reasonable-grounds representation. Build it first.
3. **Publish the model's limits alongside the score.** A score presented as more certain than its inputs warrant is the *precise* defect in the AAA rating. This is why "confidence" is not a nice-to-have.
4. **Disclaimers help but do not cure.** S&P had disclaimers. Reasonable grounds is about how the opinion was actually formed.

> **This finding, not the brief, is the strongest argument for the whole methodology-first approach.** It also independently confirms the AFA regulator warning already quoted in `source_assessment.md` — a black-box score is not merely unpersuasive, it is a liability.

### Finding B — Sanctions screening is evidence for a client's statutory defence, not a scoring dimension

`source_assessment.md` correctly notes sanctions breaches carry up to 10 years' imprisonment. The more consequential provision is the **defence**.

Under the **Autonomous Sanctions Act 2011 (Cth) s 16**: **[verbatim]**

- *"An offence against subsection (5) or (6) is an offence of strict liability"* — for a body corporate, **no fault element** is required.
- s 16(7): the subsection *"does not apply if the body corporate proves that it took reasonable precautions, and exercised due diligence, to avoid contravening that subsection."*
- *"The body corporate bears a legal burden in relation to the matter in subsection (7): see section 13.4 of the Criminal Code."*

Penalties: up to **$555,000** (individual), or **$2.2 million or 3× the transaction value, whichever is greater** (body corporate), and/or **up to 10 years' imprisonment**. **[secondary — verify quantum]**

**Read those together and the product changes shape.** Liability is strict — the client is guilty on the fact of dealing alone. The only exit is s 16(7), and the client carries a **legal burden** (balance of probabilities, not merely raising a doubt) to prove reasonable precautions and due diligence. **A screening record is what discharges that burden.** The output is not a risk input; it is the evidence in a criminal defence.

**Design consequences:**

1. **Sanctions must never be a weighted contributor.** `source_mappping.md` already reaches this ("gate") by intuition. The Act supplies the reason: a defence is not partially available. Gate is correct — this is *why*.
2. **False negatives are the catastrophic direction, false positives merely expensive.** A missed hit destroys the defence; a false positive costs an analyst an hour. **Tune recall over precision here and nowhere else in the model.** This inverts the default and must be stated explicitly, since `source_assessment.md`'s (correct) warning about false-positive accusations pushes the opposite way. Both are right: surface generously, adjudicate manually, never auto-conclude.
3. **Screening records are retention-critical.** A defence needs the evidence as it stood **at the time of dealing**. Retain what was checked, against which list version, on what date, with what result — including clean results. A clean screen with no record is worth nothing in court.
4. **This is the commercial argument for resolving the DFAT open item.** Australian sanctions are the list an Australian client's defence turns on. ITA is a competent substitute for *risk*; it is not a substitute for *the defence*. That reframes DFAT from a coverage gap to a product-viability gap.

---

## Tier 1 — Binding law that constrains the model

### 1.1 Privacy Act 1988 (Cth) — engaged, and more than expected

**Publicly available does not mean exempt.** In `Commissioner initiated investigation into Clearview AI, Inc.` **[2021] AICmr 54**, the OAIC held that indiscriminately collecting **publicly available** images was still collection of personal information and breached the APPs, expressly rejecting the argument that public availability removes Privacy Act protection. The OAIC's stated global position: *"personal information that is 'publicly available'... on the internet, is subject to data protection and privacy laws. Individuals and companies that scrape such personal information are therefore responsible for ensuring that they comply."* **[verbatim]**

**The entire OSINT premise of this project is that the data is public. That premise does not carry the privacy analysis.**

**Where personal information enters a vendor risk record** — this is not hypothetical:

- Sanctions lists name **individuals**, not only entities. DFAT's list covers *"individuals, entities and vessels"* (per `source_assessment.md`).
- Sole traders and partnerships are vendors, and their business details are personal information.
- Adverse media names directors and officers.
- `security.txt` and DPA pages publish named DPO contacts.
- SEC EDGAR filings name officers and beneficial owners.

**APP 10 is the sharp one for a scoring product:** an entity must take reasonable steps to ensure personal information it uses or discloses is *"accurate, up-to-date, complete and relevant"* having regard to the purpose. **A stale or misattributed adverse-media hit against a named director is an APP 10 problem on top of everything else** — and entity resolution, already flagged in `source_assessment.md` as the hard problem, is where this bites.

**Small business exemption — still in force, verified directly with OAIC 17 Jul 2026.** The **$3 million** annual turnover threshold has **not** been repealed; widely-reported "removal in 2026" claims are **incorrect as of today** and belong to an unlegislated reform tranche. **Do not design to a repeal that has not happened.**

**But the exemption has exceptions, and one is aimed straight at us.** It does not apply to a business that **trades in personal information**. **[verbatim, OAIC]** A product that collects personal information about vendor personnel and provides it to paying clients requires analysis against that exception — and if it applies, **turnover is irrelevant and the APPs bind in full**. This is a question for counsel before commercialisation, not after.

**Statutory tort of serious invasion of privacy — commenced 10 June 2025.** Introduced by the *Privacy and Other Legislation Amendment Act 2024*. Elements: serious invasion by intrusion upon seclusion **or misuse of information**; reasonable expectation of privacy; **intentional or reckless** conduct; public interest in privacy outweighing countervailing public interest. It is **broader than the Privacy Act — it reaches entities that are not APP entities**, so the small business exemption is no shield against it. Exemptions exist for journalism; **we are not journalists.** The intent/recklessness element is our friend here, and is another reason deliberate scoping and documented restraint have legal value.

**Design consequences:**
1. **Collect information about the vendor as an organisation; avoid personal information unless the signal requires it.** HIBP `/breaches`-not-domain-search (already decided) is exactly this instinct, correctly applied — generalise it into a stated principle.
2. **Named individuals in the record need APP 10 handling:** dated, sourced, adjudicated, and correctable.
3. **A "public data" justification is not available.** Clearview forecloses it.

### 1.2 Copyright Act 1968 (Cth) — ingesting lists is fine; republishing them is not

Two rules, pulling in opposite directions, and the gap between them is the design.

**No text and data mining exception exists.** The Government **explicitly ruled out** a TDM exception in **October 2025**, stating it has *"no plans to weaken copyright protections when it comes to AI"*, referring the question to the Copyright and AI Reference Group instead. **Australia has no TDM safe harbour and is not getting one.** **[secondary — verify]**

**But facts are not protected.** `IceTV Pty Ltd v Nine Network Australia Pty Ltd` **[2009] HCA 14**: copyright does **not** subsist in the underlying data of a compilation, only in *"the particular form of expression"*. Australia has **no sui generis database right** and rejects "sweat of the brow" — the High Court called the resulting lack of database protection a gap in the law.

**Design consequence — and it is a clean one.** Extracting *facts* from a sanctions list, a KEV feed, or a filing is not an infringement, because the facts are not protected. Reproducing a source's *particular expression* — its prose, its arrangement, verbatim article text — is where infringement lives. **So: store normalised facts and pointers; do not warehouse verbatim third-party text.** This is why GDELT's redistribution licence matters more for adverse media (where we would otherwise hold expressive text) than for KEV (where we hold CVE identifiers, which are facts).

### 1.3 Defamation — the exposure is inverted from intuition

Under the uniform **Model Defamation Provisions** (2021 amendments, enacted state by state):

- A corporation **has no cause of action unless it is an "excluded corporation"** — broadly, not-for-profit, or employing **fewer than 10 persons**. **Large vendors cannot sue us. Small ones can.** **[secondary — verify against the applicable state Act, s 9; search summaries on this point were internally contradictory and must not be relied on as written]**
- **Serious harm is an element** the plaintiff must prove (s 10A, 2021 reform, shifting the burden from defendant to plaintiff). For an excluded corporation, harm is not serious unless it caused or is likely to cause **serious financial loss**.
- **Individuals — directors, officers named in adverse media — face no such restriction.**

**Design consequences:**
1. **Adverse media risk concentrates on small vendors and named individuals** — precisely the segment where, per `source_assessment.md`, *"absence of adverse media is close to meaningless"* and coverage is thinnest. The category with the worst signal quality carries the highest legal exposure. That is an argument for adjudication, not for dropping it.
2. **Media reports allegations, not findings** (already correctly stated). Carrying that distinction into the *output wording* — "reported", "alleged", dated, attributed — is what preserves the defences.
3. **ACL s 18 has no serious-harm threshold and no excluded-corporation limit.** A large vendor who cannot sue in defamation is not without remedy. **Do not treat "they're too big to sue in defamation" as safety.**

### 1.4 Criminal Code Act 1995 (Cth) Part 10.7

Already correctly analysed in `source_assessment.md` §3. Carried forward unchanged: retrieving a page published to the world is authorised by the act of publication. No further work needed.

---

## Tier 2 — Instruments that define what the score must cover

These are not constraints on us. **They are the client's obligations — and therefore the product's demand-side specification.** A dimension that maps to a client's statutory duty sells itself; one that doesn't is a hobby.

### 2.1 APRA CPS 230 Operational Risk Management — *and it has changed since the PDF in this repo*

**⚠ The repo copy is out of date.** `docs/Prudential+Standard+CPS+230...pdf` is the **July 2025** version. APRA **finalised targeted amendments in April/May 2026**, and the **updated CPS 230 and CPG 230 commence 1 July 2026** — i.e. **already in force as of today (17 July 2026)**. Any paragraph number cited from the repo PDF, including the ¶48 reference in `source_assessment.md`, must be re-checked against the current instrument before it goes in a client-facing document. **This is open item 1.**

Key structure (subject to that re-check):
- **¶47–48:** the policy must cover how the entity identifies material service providers, manages material risks, **and manages risks from fourth parties that material service providers rely on** to deliver critical operations.
- A material service provider may be a third party, **related party or connected entity**.
- Pre-existing contracts: requirements apply from the earlier of next renewal or **1 July 2026**.

**Why this is the single most commercially valuable mapping in the project.** ¶48 makes **fourth-party risk a regulated obligation** for APRA-regulated entities. `source_assessment.md` already identified that public DPAs and subprocessor lists yield fourth-party data for free, and correctly called it *"the one thing questionnaires are worst at surfacing."* **CPS 230 ¶48 converts that observation into a compliance requirement the client must satisfy anyway.** Concentration findings — six vendors, one subprocessor — are not a clever extra. They are the regulated deliverable.

### 2.2 APRA CPS 234 Information Security

Requires regulated entities to assess third parties' information security capability, evaluate control **design and operating effectiveness**, assess testing frequency, and take reasonable steps regarding **sub-contractor** controls.

**Design consequence — a boundary, honestly drawn.** CPS 234 demands assurance about **control effectiveness**. OSINT cannot see control effectiveness; it sees perimeter artefacts. `source_assessment.md` already concedes ~10 of 27 criteria are invisible to any lawful external observer. **CPS 234 is where that concession must be loudest.** The correct claim is that OSINT **evidences a subset and flags contradictions** — never that it discharges CPS 234. Overclaiming here is both a sales lie and, per Finding A, an ACL s 18 exposure.

### 2.3 SOCI Act 2018 (Cth) + Enhanced CIRMP Rules 2026 — *this closes the FOCI gap argument*

The **Security of Critical Infrastructure (Enhanced Critical Infrastructure Risk Management Program) Rules 2026** were **registered 9 June 2026** under s 61 of the SOCI Act. Applies to critical broadcasting, DNS, electricity, energy market operator, freight infrastructure, freight services, gas, liquid fuel and water assets.

Responsible entities must **map supply chains for major suppliers and critical components**, identify maximum acceptable outages, and assess risks for existing or proposed major suppliers — **and the risks that must be assessed expressly include FOCI-related risks** and risks of access, influence and control exercised by suppliers.

Phase-in: ~mid-2027 for material-risk and patching measures; **~mid-2028 for supply chain and physical/natural hazards**.

**Why this matters to the model.** `source_assessment.md` lists **FOCI / Provenance as the "honest gap in v1"** and treats it as a sourcing shortfall to apologise for. Reframe it: **an Australian instrument registered five weeks ago makes FOCI assessment of major suppliers legally mandatory for critical infrastructure operators, with a mid-2028 deadline.** The gap is not an embarrassment — it is the highest-value item on the roadmap, with a regulatory deadline attached and a named buyer. That is a far stronger thing to say at handover than "we couldn't resolve the registry terms."

### 2.4 Modern Slavery Act 2018 (Cth)

Reporting entities (revenue ≥ AU$100m) must publish annual statements addressing supply-chain risks and remediation. Already correctly identified in `source_assessment.md` as mapping onto the *Modern Slavery & Human Rights* criterion, and correctly **held pending a licence answer**.

**Note the asymmetry:** the *Act* creates a public statutory register. The *register's licence* is unstated. Statutory publication compels disclosure; it does not grant reuse rights. The existing hold is the right call.

---

## Tier 3 — Standards supplying defensible structure

The purpose of this tier is **borrowed authority**. "We adopted NIST's model" survives a client challenge; "we thought this was sensible" does not.

| Standard | What to take from it | Status |
|---|---|---|
| **NIST SP 1326** | Five due-diligence categories; **four per-finding variables: age, frequency, severity, mitigations**; ITA CSL recommended by name | **Primary — already in repo** |
| **NIST SP 800-161r1** | C-SCRM depth; supplier criticality tiering | Recommended |
| **NIST CSF 2.0 — GV.SC** | GV.SC-01…10: supplier **prioritisation by criticality**, **due diligence + ongoing monitoring**, relationship conclusion | **Adopt — maps to agentic monitoring** |
| **ISO/IEC 27001:2022 A.5.19–5.23** | Supplier relationship controls | In repo |
| **ISO/IEC 27036** (4 parts; Pt 1 rev. 2021) | Pt 2 = requirements; **Pt 3 = ICT supply chain**; Pt 4 = cloud | Recommended |
| **ISO 31000:2018 / IEC 31010:2019** | Risk process discipline; **31010 Annex = 41 assessment techniques with stated strengths and limitations** | **Adopt for method defence** |
| **Open FAIR (O-RT / O-RA)** | Frequency × magnitude decomposition; *"consistent and defensible risk statements"* | **Cite, don't implement** |

**Three notes that matter more than the table:**

**NIST SP 1326's four variables are the decay model, handed over by a US federal publication.** `source_assessment.md` spotted this. It is worth being blunt about the value: the hardest thing to defend in any scoring model is *why a 2013 breach counts less than last month's*. `source_mappping.md` raises exactly that question and leaves it open. **SP 1326 answers it with borrowed authority.** Age, frequency, severity, mitigations — adopt the four verbatim as the per-finding modifier set, and the decay curve stops being arbitrary.

**CSF 2.0 GV.SC is the authority for the agentic-AI requirement.** The brief asks where the system could act on the user's behalf — *"re-checking a vendor on a schedule."* GV.SC includes **ongoing monitoring** and **planning for supplier relationship conclusions** as governance outcomes. Scheduled re-scoring is therefore not a product flourish; it is a named C-SCRM outcome. **This is how the roadmap's agentic feature gets justified rather than assumed.**

**Open FAIR should be cited and not built.** FAIR quantifies risk in **financial terms** from frequency and magnitude distributions. OSINT gives us neither loss magnitude nor event frequency for a specific vendor. **Attempting FAIR quantification on OSINT inputs would manufacture exactly the false precision Finding A punishes.** Cite FAIR for the *taxonomy* discipline — separating frequency from magnitude, keeping them from collapsing into one number — and state plainly that v1 does not have the inputs to quantify. **Declining to use FAIR, with a reason, is a stronger methodological statement than using it badly.**

---

## Tier 4 — AI governance (engages the moment AI touches the score)

`source_assessment.md` designates two AI moments: adverse-media summarisation and trust-page classification. Both are inside the scoring path, so this tier engages.

**EU AI Act — high-risk classification almost certainly does not bite, and the reason is worth knowing.** Annex III(5)(b) makes creditworthiness evaluation and credit scoring **of natural persons** high-risk. **Vendor risk scoring assesses legal entities, which falls outside that provision.** However: the **Art 6(3) exception never applies where the system performs profiling of natural persons**. **Design consequence — a bright line:** the moment the model scores a **sole trader** or attaches risk to a **named individual**, the analysis changes. **Keep the model scoring entities, not people.** That is the same line APP 10 and the privacy tort draw, arrived at independently — three separate instruments converging on one design rule is a rule worth taking seriously.

**Australia — Voluntary AI Safety Standard (10 guardrails).** Voluntary. Mandatory guardrails for high-risk settings were **accepted in principle but paused**; the Department published **Guidance for AI Adoption (6 essential practices) on 21 October 2025**, evolving VAISS. An **Australian AI Safety Institute** was slated to be operational in early 2026. **[secondary — verify current status; this area moves fast and the file's verification date will go stale first here]**

**ISO/IEC 42001:2023** (AI management system, certifiable, Stage 1/2 audit, 3-year cycle) and **ISO/IEC 23894:2023** (AI risk management, extends ISO 31000 to AI). **Roadmap, not v1** — 42001 certification runs ~$20–60k and 4–9 months. Worth naming in the roadmap because **Wahid AI is an AI platform**, and a third-party module that already documents its AI risk position is a cheaper input to a future 42001 scope than one that doesn't.

**The AI-specific exposure, stated plainly.** Under Finding A, the reasonable-grounds representation attaches to the **published score**. If an LLM summarises adverse media and that summary moves the score, **"the model said so" is not reasonable grounds.** Design consequence: **AI output must be evidence-linked and human-adjudicable, and must not silently move a score.** This is the same architecture the evidence store already requires — which is convenient, and not a coincidence.

---

## Tier 5 — Roadmap / non-binding today

**EU DORA** — applies since **17 January 2025**; ICT third-party risk management, mandatory **Register of Information** (2026 cycle, reference date 31 Dec 2025), oversight of designated **Critical ICT Third-Party Providers** (ESAs published the list **18 Nov 2025**). Art 28 governs third-party ICT arrangements.

**Why it earns a mention despite being EU law:** in the ESAs' 2024 dry run, **only 6.5% of ~1,000 firms passed all 116 data-quality checks**, with the most common failures being **incomplete contract data and missing subcontractor information**. That is a documented, quantified market failure in **exactly the fourth-party data this project extracts for free from public DPAs.** DORA is not our regulator, but it is evidence that the fourth-party angle has a buyer well beyond one Australian client. **Roadmap material, with a number attached.**

---

## Design consequences — consolidated

The point of the document. Each rule below is traceable to an instrument, which is what makes the model defensible rather than opinionated.

| # | Rule in the model | Authority |
|---|---|---|
| 1 | Every score reconstructible from stored evidence; evidence store built first | ABN AMRO v Bathurst; ACL s 18 |
| 2 | Confidence published alongside every score; never presented as more certain than inputs allow | ABN AMRO v Bathurst |
| 3 | Sanctions = gate, never a weighted term | Autonomous Sanctions Act s 16(7) |
| 4 | Sanctions tuned for **recall**; surface generously, adjudicate manually, never auto-conclude | s 16(7) legal burden |
| 5 | Screening records retained with list version + date + result, **including clean results** | s 16(7) evidentiary need |
| 6 | Missing data reduces **confidence**, never **risk** | Already in `source_assessment.md`; reinforced by APP 10 "complete" |
| 7 | Per-finding modifiers = **age, frequency, severity, mitigations** | NIST SP 1326 |
| 8 | Score **entities, not natural persons**; sole traders are a bright line | APP 10 + privacy tort + EU AI Act Art 6(3) |
| 9 | Store normalised **facts**, not verbatim third-party expression | IceTV; no TDM exception |
| 10 | Adverse media output worded as **reported/alleged**, dated, attributed | Defamation (small vendors + individuals) |
| 11 | AI output evidence-linked, human-adjudicable, never silently score-moving | ABN AMRO + reasonable grounds |
| 12 | Fourth-party / subprocessor concentration = **headline feature**, not extra | CPS 230 ¶48; DORA Art 28 |
| 13 | Scheduled re-scoring justified as a C-SCRM outcome | NIST CSF 2.0 GV.SC |
| 14 | FOCI positioned as **roadmap item with a 2028 regulatory deadline**, not as an apology | SOCI Enhanced CIRMP Rules 2026 |
| 15 | Never claim OSINT discharges CPS 234; claim subset + contradiction-flagging | CPS 234; ACL s 18 |
| 16 | FAIR cited for taxonomy discipline; quantification explicitly declined with reason | Open FAIR O-RT/O-RA |

---

## What not to rely on

Recording these matters as much as the inclusions — an unexamined authority is worse than none.

- **`ref.md`'s source table.** Already contradicted twice by `source_assessment.md` (VirusTotal, SSL Labs). It is a useful brainstorm and **not** an authority. Nothing in it should reach a client document unverified.
- **"It's publicly available."** Foreclosed by Clearview for anything touching personal information.
- **"Australian Government material is usually CC BY 4.0."** `source_assessment.md` already refuses this inference for DFAT. Correct. Do not let it back in elsewhere.
- **The repo's CPS 230 PDF.** Superseded — see §2.1.
- **Claims that the Privacy Act small business exemption has been removed.** Widely repeated in secondary commentary; **false as of 17 Jul 2026** per OAIC direct.
- **Commercial vendors' methodologies** (SecurityScorecard, Bitsight, Black Kite, per `ref.md`). Useful for dimension design. **Not authority** — and the AFA is on record warning against exactly these. Cite the regulator, study the vendors.

---

## Open items

| # | Item | Blocks | Priority |
|---|---|---|---|
| 1 | **Re-obtain current CPS 230 + CPG 230** (in force 1 Jul 2026); re-check ¶47–48 numbering | Every CPS 230 citation, incl. `source_assessment.md` | **High** |
| 2 | **Counsel review of the "trades in personal information" exception** against the product model | Commercialisation | **High** |
| 3 | Verify **defamation excluded-corporation test** against applicable state Act s 9 | Adverse media wording | Medium |
| 4 | Confirm **Autonomous Sanctions Act penalty quantum** from primary source (austlii returned 403) | Methodology accuracy | Medium |
| 5 | Read **SP 1326 §Pre-Checks** and the four variables **in the repo PDF** — decay model depends on the exact wording | Scoring model | **High** |
| 6 | Confirm **VAISS / mandatory guardrail** status closer to handover | AI section currency | Low |
| 7 | Obtain **ISO/IEC 27036-2 and -3** (paywalled — note as future option per brief) | Tier 3 depth | Low |

**Carried from `source_assessment.md` and now re-prioritised by this analysis:** the **DFAT** query (open item 1 there) is upgraded from a coverage gap to a **product-viability question** — see Finding B.4.

---

## Verification log

| Claim | Method | Result | Date |
|---|---|---|---|
| Privacy Act small business exemption | **direct fetch, oaic.gov.au** | **$3m threshold in force**; exceptions incl. trades-in-personal-information | 17 Jul 2026 |
| Autonomous Sanctions Act s 16(7)/(8) | search → austlii text | Strict liability + due diligence defence, legal burden | 17 Jul 2026 |
| Autonomous Sanctions Act s 16 (primary) | **direct fetch → 403 / wrong Act returned** | **Unverified — open item 4** | 17 Jul 2026 |
| ABN AMRO v Bathurst [2014] FCAFC 65 | search, multiple firm notes concurring | Reasonable grounds + duty without contract confirmed | 17 Jul 2026 |
| Clearview AI [2021] AICmr 54 | search, OAIC statements | Public availability ≠ exempt | 17 Jul 2026 |
| Privacy tort commencement | search | **10 June 2025**; broader than APP entities | 17 Jul 2026 |
| CPS 230 amendments | search, APRA + firm notes | **Updated CPS 230/CPG 230 in force 1 Jul 2026** | 17 Jul 2026 |
| SOCI Enhanced CIRMP Rules 2026 | search, Federal Register listing | **Registered 9 Jun 2026**; FOCI mandatory for major suppliers | 17 Jul 2026 |
| TDM exception ruled out | search, multiple firm notes | Oct 2025, no TDM exception | 17 Jul 2026 |
| IceTV | search | Facts unprotected; no database right | 17 Jul 2026 |
| Defamation excluded corporation | search | **Summaries self-contradictory — open item 3** | 17 Jul 2026 |
| EU AI Act Annex III(5)(b) | search | Natural persons only; Art 6(3) profiling carve-out | 17 Jul 2026 |
| DORA dry-run 6.5% pass rate | search | Confirmed; 116 checks, ~1,000 firms | 17 Jul 2026 |

**Method note.** Only the OAIC small business position was confirmed by direct fetch of a primary source. Everything else rests on search results and law-firm commentary, which is adequate for a v0.1 position paper and **not** adequate for a client-facing document. Items 1, 4 and 5 close that gap.

---

## References

**Legislation & instruments**
- *Autonomous Sanctions Act 2011* (Cth) s 16 — http://www.austlii.edu.au/au/legis/cth/consol_act/asa2011270/s16.html
- *Autonomous Sanctions Regulations 2011* (Cth) reg 14–15
- *Privacy Act 1988* (Cth); *Privacy and Other Legislation Amendment Act 2024* (Cth)
- *Copyright Act 1968* (Cth)
- *Criminal Code Act 1995* (Cth) Part 10.7
- *Modern Slavery Act 2018* (Cth)
- *Security of Critical Infrastructure Act 2018* (Cth); Enhanced CIRMP Rules 2026 — https://www.legislation.gov.au/F2026L00701/asmade
- *Competition and Consumer Act 2010* (Cth) Sch 2 (ACL) s 18, s 236
- Model Defamation Provisions (2021), ss 9, 10A — as enacted per state

**Cases**
- *ABN AMRO Bank NV v Bathurst Regional Council* [2014] FCAFC 65
- *Commissioner initiated investigation into Clearview AI, Inc.* [2021] AICmr 54 — https://www.oaic.gov.au/__data/assets/pdf_file/0016/11284/Commissioner-initiated-investigation-into-Clearview-AI,-Inc.-Privacy-2021-AICmr-54-14-October-2021.pdf
- *IceTV Pty Ltd v Nine Network Australia Pty Ltd* [2009] HCA 14

**Regulatory**
- APRA CPS 230 — https://www.apra.gov.au/standards/cps-230 · CPG 230 — https://www.apra.gov.au/practice-guides/cpg-230
- APRA final targeted amendments to CPS 230 — https://www.apra.gov.au/final-targeted-amendments-to-cps-230-operational-risk-management
- APRA CPS 234 — https://www.apra.gov.au/standards/cps-234
- OAIC APP Guidelines ch 10 (APP 10) — https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-10-app-10-quality-of-personal-information
- OAIC small business — https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business
- OAIC statutory tort — https://www.oaic.gov.au/privacy/your-privacy-rights/more-privacy-rights/statutory-tort-for-serious-invasions-of-privacy
- EU DORA (EIOPA) — https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en
- EU AI Act Annex III — https://artificialintelligenceact.eu/annex/3/ · Art 6 — https://artificialintelligenceact.eu/article/6/
- DISR Voluntary AI Safety Standard — https://www.industry.gov.au/publications/voluntary-ai-safety-standard/10-guardrails

**Standards**
- NIST SP 1326 — `docs/NIST.SP.1326.pdf`
- NIST CSF 2.0 — https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf · GV.SC — https://csf.tools/reference/nist-cybersecurity-framework/v2-0/gv/gv-sc/
- NIST SP 800-161r1 — C-SCRM Practices for Systems and Organizations
- ISO/IEC 27001:2022 — `docs/ISO_IEC-270012022-ed.3.pdf`
- ISO/IEC 27036-1:2021 — https://www.iso.org/standard/82905.html
- ISO 31000:2018 — https://www.iso.org/standard/65694.html · IEC 31010:2019 — https://www.iso.org/standard/72140.html
- Open FAIR (O-RT, O-RA) — https://www.opengroup.org/open-fair
- ISO/IEC 42001:2023 — https://www.iso.org/standard/42001 · ISO/IEC 23894:2023

**Internal**
- `docs/source_assessment.md` — source-level legality (the other legal question)
- `docs/source_mappping.md` — proposed category structure
- `docs/OSINT_TPRM_Intern_Brief.md` — the brief
ISO/IEC 42001

EU AI Act

O NIST AI RMF

G DTA Policy v2.0

Al Ethics Principles

4ts APRA CPS 230

APRA CPS 234

& Privacy Act 1988

To design a third-party risk scoring model that will stand up to a grilling by a client’s Chief Risk Officer (CRO) or General Counsel, we have to ground our methodology in established industry frameworks and clear legal safe harbors.

If a client asks, *"Why are you measuring this, and are you sure this data was collected legally?"* we should point directly to these exact standards.

---

## 1. The Regulatory & Security Frameworks (Why We Measure)

Our scoring model shouldn’t invent risk categories. Instead, it should map its dimensions directly to globally recognized standards. This ensures that any "Perimeter Defense" or "Reputational Risk" score we produce aligns with what risk teams are already auditing.

| Framework / Law | Specific Sections to Rely Upon | How It Directs Our Scoring Model |
| --- | --- | --- |
| **NIST SP 800-161 Rev. 1** <br>

<br>*(Cybersecurity Supply Chain Risk Management)* | **Control RA-3** (Risk Assessment) & **PM-31** (Continuous Monitoring) | Mandates that organizations continuously monitor the security posture of their supply chain. This justifies our automated, real-time "Pulse" scanning instead of static annual questionnaires. |
| **EU DORA** <br>

<br>*(Digital Operational Resilience Act)* | **Articles 28–30** (ICT Third-Party Risk Management) | Requires financial entities to conduct proactive, proportionate due diligence *prior* to contracting. Article 28(5) specifically demands assessing the vendor's information security standards, justifying our **Perimeter Defense** dimension. |
| **ISO/IEC 27001:2022** <br>

<br>*(Information Security Management)* | **Annex A.5.19** (Supplier Relationships) & **A.5.22** (Monitoring Supplier Services) | Establishes the requirement to regularly monitor, review, and audit third-party compliance and technical posture. |
| **US Banking Guidance** <br>

<br>*(OCC / FRB / FDIC Interagency Guidance)* | **Section on Due Diligence & Ongoing Monitoring** (June 2023) | Stresses that a bank's use of third parties does not diminish its responsibility. It explicitly outlines that due diligence must review the vendor’s technological and operational resilience. |

---

## 2. The Legal & Collection Safe Harbors (How We Collect Safely)

Our data collection must be entirely "passive"—we must never actively scan or probe a vendor’s network (which can look like a cyberattack). We also need to defend our use of automated public data collection.

### A. The "Gates Up" Doctrine (U.S. CFAA)

To defend our right to pull public infrastructure data (like SSL/TLS status and DNS records), we rely on:

* **The Computer Fraud and Abuse Act (CFAA) - 18 U.S.C. § 1030**
* **hiQ Labs v. LinkedIn (9th Cir. 2022)**
* **Van Buren v. United States (U.S. Supreme Court, 2021)**

> **The Defensible Position:** Under the Supreme Court's "gates-up-or-down" inquiry, if a website or service is publicly accessible without a password or login barrier, accessing or indexing it via automated means is not a violation of the CFAA. Because our OSINT PoC only queries public DNS, certificate transparency logs (`crt.sh`), and public Shodan indexes, we remain firmly "gates-up". We do not bypass any technical access controls.

### B. GDPR Legitimate Interest (European Privacy)

To justify collecting and scoring threat intelligence data that might occasionally touch personal data (like public emails associated with a breached domain), we rely on:

* **GDPR Article 6(1)(f) (Legitimate Interest)**
* **GDPR Recital 49**

> **The Defensible Position:** Recital 49 explicitly states that processing personal data to the extent *strictly necessary and proportionate* for the purpose of ensuring network and information security constitutes a "legitimate interest." Aggregating threat data (like AlienVault OTX alerts) to score a vendor's cybersecurity risk falls squarely under this protection.

### C. Fair Use & Generative AI Summarization (Adverse Media)

When using an LLM to read, categorize, and summarize adverse media (news of breaches, lawsuits, or regulatory fines), we must protect against copyright claims:

* **U.S. Copyright Act - 17 U.S.C. § 107 (Fair Use)**

> **The Defensible Position:** Our PoC uses LLMs to perform **transformative summarization**. We are not redistributing full articles or creative prose; we are programmatically extracting and indexing raw, factual risk points (e.g., "Company X fined $2M for GDPR breach on [Date]"). Factual information itself is not copyrightable, and utilizing snippets for analysis is protected under the Fair Use doctrine.

---

## 3. How This Shapes Our Scoring Rules

To turn these laws and frameworks into our product's scoring engine, we will establish three rule-based guidelines:

1. **Rule of Passive-Only Sourcing:** Our engine is restricted to third-party databases (like Shodan or crt.sh) or standardized protocol queries (like DNS lookups). We never execute active pinging, port scanning, or web scraping of the target's direct servers.
2. **Rule of Strict Fact Attribution:** Every deduction in our scoring model must link to an authenticated public record (e.g., "`-10 points`: Expired TLS Certificate detected via Certificate Serial # [XYZ] on crt.sh"). This satisfies DORA’s requirement for auditability.
3. **Rule of the "Confidence Score" Offset:** In compliance with NIST SP 800-161's focus on data integrity, if a source is stale (e.g., an adverse media article from five years ago) or if data is missing, we must degrade the **Confidence Score** of the assessment rather than artificially lowering the vendor’s **Risk Score**.