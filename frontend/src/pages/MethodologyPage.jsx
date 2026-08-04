import { useState } from 'react'
import {
  // `Users` dropped with the role-based views section.
  Scale, GitBranch, GitCompareArrows, Database, Layers, Gavel, Radio, CheckCircle2, Ban,
  ChevronDown, TrendingUp, Target, History, ScrollText, ShieldAlert,
} from 'lucide-react'
import { Disclose } from '../components/primitives.jsx'
import { Card, Badge } from '../components/ui.jsx'


// [display name, ENGINE KEY, what we CHECK, [signals in the category]]. No weights - a penalty
// model has none; a category's influence emerges from the issues found in it.
//
// THE ENGINE KEY IS PUBLISHED HERE ON PURPOSE. These are the seven keys `scoring.yaml` actually
// defines and the scorecard actually renders, so a reader can carry a category name from this page
// to a vendor's record and back. The list this replaced had drifted badly: it invented an "Adverse
// Media & Reputation" category (regulator actions live under compliance), split hygiene across two
// headings the engine does not have, folded email authentication into hygiene when it is its own
// category, and omitted `assurance_context` altogether. Seven names either way, four of them
// wrong. Do not edit this list without checking it against `scoring.yaml`.
const CATEGORIES = [
  ['Breach & Compromise History', 'breach_compromise_history',
    'Any confirmed breaches, and known or actively-exploited vulnerabilities?',
    ['Confirmed breaches, by data class', 'KEV-listed CVEs (actively exploited)',
      'NVD CVEs by CVSS, plus probable-exploit']],
  ['Attack Surface & Hygiene', 'attack_surface_hygiene',
    'Is traffic encrypted, the web configuration hardened, and the exposed estate under control?',
    ['TLS version & cipher strength', 'Certificate validity', 'HSTS', 'CSP', 'X-Frame-Options',
      'DNSSEC', 'CAA', 'Subdomain estate size', 'Stale / abandoned hosts',
      'Weak certificate issuance', 'Estate-wide legacy TLS', 'Estate-wide expired certificates']],
  ['Identity & Email', 'identity_email',
    'Can someone send mail that appears to come from this domain?',
    ['DMARC policy', 'SPF', 'DKIM']],
  ['Transparency', 'transparency',
    'Is there a way to report a vulnerability, and someone to report it to?',
    ['Vulnerability-disclosure programme', 'security.txt']],
  ['Compliance & Regulatory', 'compliance_regulatory',
    'Are certifications claimed and corroborated — and has a regulator acted?',
    ['Certification posture (claimed vs registry-corroborated)',
      'Regulator investigation / enforcement action']],
  ['Continuity Context', 'continuity_context',
    'Is this a live, in-good-standing entity with a real operating history?',
    ['Legal-entity status', 'Entity existence (GLEIF + Wikidata)',
      'Entity maturity, from legal inception', 'Domain registration standing (RDAP)']],
  ['Assurance Context', 'assurance_context',
    'Does the vendor publish a security programme, and can it be reached?',
    ['Security-programme disclosure', 'Contactability', 'Reporting posture']],
]

// The three axes, never collapsed. Each answers a question the other two cannot, which is the
// whole reason they are not averaged into one number.
//
// The Ghost used to occupy the third slot here. It is a REFUSAL STATE, not an axis — a thing that
// can happen to a measurement rather than a thing being measured — and it now sits with the other
// two refusal states further down, where the distinction between them can actually be drawn.
// [label, scale, the one-line answer, the governing rule (tooltip), tone]. The rule is the part
// that used to sit open on the card; it is real and it is enforced in the engine, but three
// four-line paragraphs above the fold is how this page stopped being read.
const AXES = [
  ['Posture', '0–100 · grade A–F',
    'How strong the vendor looks from outside. Ours to measure.',
    'Start at 100; subtract a penalty per issue by severity. Higher = stronger.',
    'var(--risk-low)'],
  ['Confidence', 'coverage-first · High / Med / Low',
    'How much of the vendor we could actually see.',
    'Coverage is the base. Operating history then nudges it on a bounded, continuous curve — a 20-year record reads differently from a 2-year one. That adjustment moves confidence only; it sets no penalty.',
    'var(--accent)'],
  ['Assurity', '0–100 · independent assurance',
    'Whether anyone independent has checked.',
    '“Their TLS is current” and “an auditor examined their controls” are different claims. Absence NEVER subtracts here — a vendor with nothing observable sits at a low intercept, not at zero, because unevidenced is not disproved.',
    'var(--accent)'],
]

// Why Assurity is its own axis and not a posture bonus — the single sentence that justifies the
// separation, kept beside the axes rather than buried in a later section.
const ASSURITY_FENCE =
  'Credit for publishing a trust page must never buy back points lost to an expired certificate. '
  + 'The only thing that lowers Assurity is a COMPLIANCE GAP — a vendor asserting a framework and '
  + 'then being observed failing one of its controls — because that is a statement about the '
  + 'reliability of their own claims, which is exactly what this axis measures.'

// The only points table - four fixed penalties drive everything.
const SEVERITIES = [
  ['Critical', '-40', 'Expired prod cert · unpatched KEV · CVSS 9–10', 'var(--risk-critical)'],
  ['High', '-20', 'No DMARC · TLS 1.0/1.1 · breach of personal data', 'var(--risk-high)'],
  ['Medium', '-8', 'Weak TLS · missing SPF · CVSS 4–6.9', 'var(--risk-moderate)'],
  ['Low', '-3', 'Missing header · no DNSSEC · CVSS 0.1–3.9', 'var(--risk-low)'],
  ['Informational', '0', 'Unverifiable - recorded, not scored', 'var(--ghost)'],
]

// NIST SP 1326 per-finding adjustment, applied to the PENALTY before it is subtracted. All four
// run in the engine (scoring/modifiers.py via engine.py) - keep this list matching what that code
// actually does. Mitigation is no longer dormant: the dispute/refute path activates the ×0.6.
const NIST_FACTORS = [
  ['Severity',
    'Determines the starting penalty based on how serious the issue is'],
  ['Age',
    'Three-year half-life, floored at 0.15. Older issues count less over time, but never disappear completely. This applies to things that happened — a breach, a vulnerability disclosure. Something still broken today does not soften with age.'],
  ['Frequency',
    'Recurrence read as a pattern rather than one issue counted n times. A long list of vulnerabilities matched only by product name is treated as one finding.'],
  // ['Mitigation',
  //   'A human-adjudicated, evidenced fix reduces the penalty (×0.6) — activated through the dispute path below. A vendor’s claim alone never does; the evidence must be accepted first.'],
]

// ---------------------------------------------------------------- inherent & residual risk (E10b)
//
// Three things kept apart, and the separation IS the design. Posture is ours to measure; inherent
// exposure is the buyer's to declare; residual is the published combination of the two and is a
// deterministic lookup rather than a third measurement.
const RISK_LAYERS = [
  ['Posture', 'Ours to measure', 'How strong the vendor looks from outside. Moves when their TLS moves — twice a quarter is normal.'],
  ['Inherent', 'THEIRS to declare', 'How much this buyer stands to lose: the higher of criticality and data-access scope, never averaged. Moves when the RELATIONSHIP moves, and not otherwise.'],
  ['Residual', 'Neither — a lookup', 'The published combination. Recomputed on read from the two above and stored nowhere, so it can never drift from the inputs it was derived from.'],
]

// Verbatim from `residual_risk._RESIDUAL` — sixteen cells, argued over once, then fixed. Rows are
// posture bands best-to-worst; columns are inherent tiers. Keep this in step with that table.
const RESIDUAL_ROWS = ['strong', 'moderate', 'weak', 'poor']
const RESIDUAL_COLS = ['low', 'medium', 'high', 'critical']
const RESIDUAL_MATRIX = {
  strong: { low: 'low', medium: 'low_medium', high: 'medium', critical: 'medium_high' },
  moderate: { low: 'low_medium', medium: 'medium', high: 'high', critical: 'high' },
  weak: { low: 'medium', medium: 'high', high: 'high', critical: 'critical' },
  poor: { low: 'medium_high', medium: 'high', high: 'critical', critical: 'critical' },
}
const RESIDUAL_LABEL = {
  low: 'Low', low_medium: 'Low–Med', medium: 'Medium',
  medium_high: 'Med–High', high: 'High', critical: 'Critical',
}
const RESIDUAL_TONE = {
  low: 'var(--risk-low)', low_medium: 'var(--risk-low)', medium: 'var(--risk-moderate)',
  medium_high: 'var(--risk-moderate)', high: 'var(--risk-high)', critical: 'var(--risk-critical)',
}

// P5 — effort matched to exposure, from `assessment_depth.table()`. A T4 supplier and the vendor
// holding production data should not cost the same to assess or be re-checked on the same day.
const DEPTHS = [
  ['T1 Critical', 'full', 'all sources', 'Quarterly', true],
  ['T2 Important', 'full', 'all sources', 'Semi-annual', true],
  ['T3 Standard', 'core', '11 sources', 'Annual', true],
  ['T4 Low', 'screening', '7 sources', 'Passive — no scheduled re-score', false],
]

// The three ways an assessment declines to publish a grade. They are DIFFERENT FACTS and were
// being read as one; a UI that colours them alike is the bug this list exists to prevent.
const NO_SCORE_STATES = [
  ['Ghost', 'Published, but only looks clean for lack of evidence',
    'We assessed the vendor and retained too little coverage to stand behind a grade. The record is published with its confidence stated. UNASSESSED IS NOT SAFE — read the confidence, not the grade.',
    'var(--ghost)'],
  ['Refused', 'Published nothing at all',
    'Coverage fell below the 40% floor. Rather than print a number we cannot defend, the assessment reports Insufficient Evidence and names the sources that stayed silent.',
    'var(--ghost)'],
  ['Blocked', 'A gate stopped it before scoring',
    'A sanctions or watchlist match, a dissolved legal entity, or an identity too ambiguous to attribute. This is a legal or factual question routed to a person — not a low score, and never rendered as one.',
    'var(--blocked)'],
]

const GRADES = [
  ['A', '85–100', 'Robust posture', 'var(--risk-low)'],
  ['B', '70–84', 'Reasonable, some gaps', 'var(--risk-moderate)'],
  ['C', '50–69', 'Poor controls', 'var(--risk-high)'],
  ['D', '30–49', 'Severe issues', 'var(--risk-critical)'],
  ['F', '0–29', 'Little to no investment', 'var(--risk-critical)'],
]

// Each step: [title, the one-line summary, the full explanation (behind an expander), icon]. A
// fixed, non-negotiable order.
//
// The full explanations are unchanged and still worth having — they are what lets a non-engineer
// challenge the pipeline. Seven of them open at once was a page of continuous prose under a
// diagram that had already conveyed the shape.
const FLOW = [
  ['1 · Enter a vendor',
    'A domain is assessed directly; a company name asks you to confirm which organisation first.',
    'Enter either a domain or a company name. A domain (for example, snowflake.com) is assessed directly; a company name shows matching organisations and domains for you to confirm before continuing. This prevents the wrong company from being assessed.',
    Layers],
  ['2 · Identity & sanctions gate',
    'Two things stop an assessment before any score exists: a sanctions match, or an identity we cannot attribute.',
    'A sanctions or watchlist match sends the record to a person instead of grading it — a sanctions hit is a legal question, not a number. And if we cannot establish that the website being assessed really belongs to the company named — for example, the address was guessed from a name rather than confirmed — the assessment stops rather than risk reporting on the wrong company. Both are judged from the evidence actually collected, so they are settled as the record is built rather than guessed at the start.',
    Gavel],
  ['3 · Collect public evidence',
    'Every supported public source is queried at once, and one failing source does not stop the run.',
    'The system collects from all supported public sources at the same time: DNS, TLS certificates, HTTP security headers, Certificate Transparency, vulnerability databases, business registries, domain registration records and regulatory enforcement feeds. If one source is unavailable, the assessment continues using the remaining sources.',
    Radio],
  ['4 · Store the evidence',
    'Findings are saved before scoring begins, so every score can be reproduced later.',
    'Every finding is saved before scoring begins. This creates a permanent audit record, so every score can be reproduced and verified later — the store is append-only, and the database itself rejects an update or a delete.',
    Database],
  ['5 · Classify each finding',
    'Pass, Low, Medium, High or Critical. A clean check earns no points but does count as coverage.',
    'Each finding is compared against the scoring rules and classified as Pass, Low, Medium, High or Critical. Each severity has a fixed penalty; a successful check receives no penalty but still contributes to evidence coverage.',
    GitBranch],
  ['6 · Calculate the posture score',
    'Categories start at 100 and lose their own penalties; the overall is the total over a fixed divisor.',
    'Every category starts at 100. Penalties are subtracted from the category where they occur, producing a posture score for each category. The overall posture is 100 minus the total penalty, spread across a fixed number of categories — fixed, so that a check which comes back clean can never raise the score, and a source that stays silent can never lower it. Older findings receive smaller penalties through time-based decay, while a confirmed current critical issue can cap the maximum published grade.',
    Scale],
  ['7 · Report the result',
    'Three separate results — posture, confidence, assurity — plus residual risk where the buyer has declared exposure.',
    'The final report contains three separate results, never combined into one: Posture (0–100 and Grade A–F), showing the vendor’s external security posture; Confidence (High, Medium or Low), showing how much of the vendor we could actually see; and Assurity (0–100), showing how much independent assurance the vendor carries. Confidence is coverage-first and is then modestly adjusted by how much corroborated operating history stands behind the vendor; posture arithmetic is unchanged. Where the buyer has declared what this relationship is worth losing, the report also states the residual risk tier. Alongside these it states how the vendor measures against a published baseline of controls, where it places among its peers, and how far it sits from what that peer group predicts. Every deduction is listed in plain English — what the issue means, what it cost, which source found it and when — so a score can be read and challenged without an engineer. If less than 40% confidence is retained, no posture score is published: the assessment is reported as Insufficient Evidence (“The Ghost”).',
    CheckCircle2],
]

// The pipeline as a DIAGRAM — the shape of the assessment, above the prose steps that follow.
//
// Rendered as nodes rather than as pre-formatted ASCII so it stays readable in both themes, wraps
// on a phone, and can be corrected in one place. Node kinds:
//   step     — one full-width box
//   decision — a question, then its two outcomes side by side, labelled Yes / No
//   parallel — two boxes computed at the same time from the same findings
// `tone` picks the accent: 'stop' for a path that emits no score, 'ghost' for a refusal, 'end'
// for the terminal node.
const PIPELINE = [
  { kind: 'step', title: 'Start assessment', tone: 'start' },
  { kind: 'step', title: 'Enter company name or domain' },
  { kind: 'step', title: 'Identity resolution',
    items: ['Match the correct organisation', 'Resolve the official domain'] },
  { kind: 'decision', title: 'Identity & sanctions gate',
    items: ['Sanctions or watchlist match?', 'Identity too ambiguous to attribute?'],
    no: { title: 'Continue assessment' },
    yes: { title: 'Manual review', note: 'No score is emitted', tone: 'stop' } },
  { kind: 'step', title: 'Collect public evidence', note: 'All sources queried in parallel',
    chips: ['DNS', 'TLS', 'HTTP', 'CT', 'HIBP', 'KEV', 'NVD', 'GLEIF', 'Wikidata', 'Trust pages', 'RDAP'] },
  { kind: 'step', title: 'Store raw evidence & receipts', note: 'The audit trail, written before any scoring' },
  { kind: 'step', title: 'Classify findings',
    chips: ['Pass', 'Low', 'Medium', 'High', 'Critical'] },
  { kind: 'parallel', title: 'Computed from the same findings, never combined',
    left: { title: 'Calculate posture',
      items: ['Apply penalties', 'Age decay', 'Frequency'] },
    right: { title: 'Calculate confidence',
      items: ['Evidence coverage', 'Operating history', 'Confidence band'] } },
  { kind: 'decision', title: 'Confidence ≥ 40%?',
    yes: { title: 'Publish score', note: 'Posture + grade' },
    no: { title: 'The Ghost', note: 'Insufficient evidence — no grade published', tone: 'ghost' } },
  // The third axis. Sits after the publish gate because it is computed and published independently
  // of whether a posture survived that gate — an unassessable vendor can still hold certifications.
  { kind: 'step', title: 'Calculate assurity',
    note: 'Independent assurance. Absence never subtracts; only an observed compliance gap does',
    items: ['Certification credits', 'Compliance gaps', 'Minimum observed signals or nothing is published'] },
  { kind: 'step', title: 'Build benchmark profile',
    chips: ['Industry', 'Revenue', 'Employees', 'Region'] },
  { kind: 'decision', title: 'Find peer cohort — enough peers?',
    yes: { title: 'Peer benchmark', note: 'Percentile · quartile · peer median' },
    no: { title: 'Sector reference baseline', note: 'Labelled as a substitution, not real peers' } },
  { kind: 'step', title: 'Target maturity assessment',
    note: 'Compared against published standards',
    chips: ['CISA', 'NIST', 'PCI DSS', 'RFC 9116', 'ISO/IEC 27001', 'SOC 2'] },
  // Inherent tier is a CLIENT DECLARATION, so it enters the pipeline here rather than being
  // collected: nothing upstream could have observed it.
  { kind: 'decision', title: 'Inherent tier declared for this relationship?',
    items: ['max(criticality, data-access scope) — never averaged'],
    yes: { title: 'Residual risk published', note: 'Deterministic 16-cell lookup, stored nowhere' },
    no: { title: 'No residual tier', note: 'Routed to FULL depth — undeclared is not Low' } },
  { kind: 'step', title: 'Build final assessment',
    items: ['Posture', 'Confidence', 'Assurity', 'Residual risk', 'Benchmark', 'Target maturity',
      'Evidence & receipts', 'Fourth-party context'] },
  // Role-based projections are disabled — every reader now gets the complete record. This node
  // claimed five of them for two releases after they were switched off.
  { kind: 'step', title: 'Final report', note: 'One record, complete — the same numbers for every reader', tone: 'end' },
]

// The three interpretation layers, each stated in one short paragraph.
//
// These replaced longer multi-row breakdowns. The detail still exists and is still enforced in
// code — the peer median is a nearest-rank median rather than a mean, the reference baseline is a
// fixed internal series rather than a published one, and every target-maturity control is refused
// at load without a named instrument. It is simply no longer spelled out on this page.
//
// ONE KNOWN IMPRECISION, recorded so it is not lost: `entity_maturity` IS a scored signal in
// scoring.yaml, so a vendor under five years old carries a Low (−3, about 0.75 posture after the
// divisor); from five years upward age costs nothing. "Not the posture score itself" is therefore
// true of the CONTINUOUS operating-history measure and not of the underlying age bands. The
// wording below is the author's deliberate choice — do not restore the longer version without
// asking, but do not extend the claim any further either.
const INTERPRETATION = [
  ['Peer benchmarking', TrendingUp, 'Am I typical?',
    'Places the vendor against comparable organisations by sector, size and delivery model. The '
    + 'peer count travels with every figure: a percentile needs 30 peers, a quartile needs 8, and '
    + 'below that the comparison states its own n and refuses to rank.'],
  ['Expectation gap', GitCompareArrows, 'Am I what my peer group predicts?',
    'Posture minus the cohort’s expected posture, with the observations that account for the '
    + 'difference and how many peers avoid each one. A gap with named causes is a remediation '
    + 'list; a gap on its own is only a number.'],
  ['Target maturity', Target, 'Am I adequate?',
    'Measures the vendor against published standards rather than against other vendors, so it '
    + 'still reads for a vendor with no peer group at all. Every control names a real instrument '
    + 'or it does not ship.'],
  ['Compliance gap', ScrollText, 'Are the vendor’s own claims reliable?',
    'A framework the vendor asserts, and an observation that contradicts one of its controls. One '
    + 'weakness across three asserted frameworks is three gaps but one charge — publishing more '
    + 'certifications must never cost a vendor more.'],
  ['Operating history', History, 'How much track record is behind this?',
    'A continuous curve rather than age bands. It moves confidence and which controls could yet '
    + 'exist; it sets no penalty of its own.'],
]

// Fourth-party context — WHO the vendor depends on, disclosed and never scored.
// const FOURTH_PARTY = [
  // ['What they are', 'Fourth parties are the services the vendor itself relies on — cloud providers, email providers, identity providers and CDNs. They are identified from DNS, TLS, HTTP headers and other evidence already collected, so no new source is queried.'],
  // ['Informational only', 'Fourth-party providers are shown for awareness. Their issues are not counted against this vendor’s score, because many vendors share the same providers — charging every customer of a cloud platform for that platform’s bad day would penalise a dependency their competitors also carry.'],
  // ['Website host is scoped apart', 'A marketing page on Netlify or Vercel is flagged as a low-impact website host, not confused with the product’s core runtime.'],
// ]

// [source, what it checks, used for, kind]. Gate = screened, never scored.
// `Used for` names the CATEGORY THE ENGINE ACTUALLY SCORES INTO — the same seven above. It
// previously named categories that do not exist, which made the table impossible to reconcile
// against a scorecard.
const SOURCES = [
  ['DNS', 'SPF, DKIM, DMARC', 'Identity & Email', 'ok'],
  ['DNS', 'DNSSEC, CAA', 'Attack Surface & Hygiene', 'ok'],
  ['TLS Scanner', 'TLS version, cipher suites, certificate validity', 'Attack Surface & Hygiene', 'ok'],
  ['HTTP Headers', 'HSTS, CSP, X-Frame-Options', 'Attack Surface & Hygiene', 'ok'],
  ['HTTP Headers', 'security.txt', 'Transparency', 'ok'],
  ['Certificate Transparency', 'Subdomains, certificate history, shadow assets, estate-wide TLS and expiry', 'Attack Surface & Hygiene', 'ok'],
  ['Have I Been Pwned', 'Confirmed public breaches and exposed data types', 'Breach & Compromise History', 'ok'],
  ['CISA KEV', 'Known Exploited Vulnerabilities', 'Breach & Compromise History', 'ok'],
  ['NVD + EPSS', 'CVEs, CVSS severity, exploitation probability', 'Breach & Compromise History', 'ok'],
  ['GLEIF', 'Legal entity status and standing', 'Continuity Context', 'ok'],
  ['Wikidata', 'Entity existence and identity verification', 'Continuity Context', 'ok'],
  ['Wikidata (P571)', 'Legal inception date -> operating history (primary maturity source, full weight)', 'Continuity Context & Confidence', 'ok'],
  ['RDAP', 'Domain age, expiry, registration status; maturity corroboration at a discount — an aged domain is purchasable, a trading record is not', 'Continuity Context', 'ok'],
  ['ABN Lookup', 'Australian entity status (Active / Cancelled)', 'Continuity Context', 'ok'],
  ['Companies House', 'UK entity status and filed accounts', 'Continuity Context', 'ok'],
  ['AlienVault OTX', 'Passive DNS — Certificate-Transparency redundancy', 'Attack Surface & Hygiene', 'ok'],
  ['Vendor Trust Pages', 'Certifications and attestations', 'Compliance & Regulatory', 'ok'],
  ['Vendor Trust Pages', 'Security-programme disclosure, contactability, reporting posture', 'Assurance Context', 'ok'],
  ['Vendor Trust Pages', 'Vulnerability-disclosure programme', 'Transparency', 'ok'],
  ['Regulatory Feeds', 'Official investigations and enforcement actions', 'Compliance & Regulatory', 'ok'],
  // ['GDELT', 'Adverse-media candidates, held for human review', 'No scored category — held', 'held'],
  ['Firmographics (Wikidata)', 'Industry, size, ownership, country — sets the peer cohort', 'Profile & benchmarking', 'context'],
  ['PDL Free Company Dataset', 'Industry / size / country fallback — offline, opt-in', 'Profile & benchmarking', 'context'],
  ['ITA Consolidated Screening List', 'Sanctions and export restrictions', 'Sanctions gate - not scored', 'gate'],
]

// Disputes, monitoring and role-based views — shipped features beyond the one-shot score.
// const DISPUTES = [
//   ['Contest a finding with evidence', 'Outside-in scoring cannot see the compensating controls a vendor runs, so it may refute a finding — a SOC 2 reference, a patch log, “that IP is our CDN, not us.”'],
//   ['A human adjudicates', 'Submitting a dispute changes no score. Only an accepted refute applies: nullify (penalty → 0, attribution error) or mitigate (×0.6, evidenced fix).'],
//   ['A new immutable score', 'An accepted refute re-scores through the same pipeline. The original score and the whole dispute trail stay readable — nothing is ever edited.'],
// ]

// const MONITORING = [
//   ['Risk is not point-in-time', 'A vendor that scored A last quarter can lose a certificate, get breached, or drop a DMARC record tomorrow. Stale scores are re-run on a cadence.'],
//   ['Drift is provable', 'Every run is hash-stamped, so a posture move is shown with before/after receipts attached — proven, not asserted.'],
//   ['Always a new record', 'A re-score writes a new immutable row through the same scoring path; history is never overwritten.'],
// ]

// Role-based views temporarily disabled — every reader now gets the complete record, so a page
// describing five projections would describe something the product no longer does.
// const ROLE_PRINCIPLES = [
//   ['One assessment, different views', 'Each role uses the same assessment data. Only the presentation changes to suit the user’s responsibilities. Pick a role from the “View as” switcher on any scorecard.'],
//   ['Emphasis, not truth', 'Role-based views change what is shown first, not what is true. Every user can reach the complete evidence if they need it, and it is always the same number underneath.'],
// ]

// [role, main focus] — the compact table.
// const ROLE_FOCUS = [
//   ['Procurement', 'Buy or not buy'],
//   ['Security Analyst', 'Technical findings and evidence'],
//   ['Risk Manager', 'Overall risk and peer comparison'],
//   ['Executive / CISO', 'Key risks and recommendation'],
//   ['Auditor', 'Complete evidence trail and audit records'],
// ]

// [role, the question they walk in with, what they SEE first, what they can DO]. Straight from
// the role config in frontend/src/lib/roles.js — one projection each, never a separate score.
// const ROLE_DEFS = [
//   ['Procurement', 'Can we buy from this vendor?',
//     'Leads with the recommendation. Shows only findings that actually cost points, and a simplified peer read — the decision, not the cipher suites.',
//     'Record a decision: approve · approve-with-conditions · reject.'],
//   ['Security analyst', 'What exactly is wrong — and is it real?',
//     'Leads with the number. Every finding expanded to its receipt, the full benchmark, and clean passes shown too (“checked, and fine” is evidence).',
//     'Dispute a finding with evidence.'],
//   ['Risk manager', 'How does this sit in my risk universe?',
//     'Leads with the number. Categories, trend and peer comparison, framed for portfolio context rather than a single deep dive.',
//     'Dispute a finding · set a tier.'],
//   ['Executive / CISO', 'Where is my exposure?',
//     'Leads with the recommendation. Only the top three findings that drove the score and a one-line peer standing — no noise.',
//     'Record a decision · share the board pack.'],
//   ['Auditor', 'Show me the evidence.',
//     'Leads with the number, then the full chain: score → finding → receipt → source → timestamp → hash. Peers are interpretation, so the benchmark is off by default.',
//     'Verify the hashes · export the evidence pack.'],
// ]

// const AI_MOMENTS = [
//   ['Adverse media', 'Summarise which GDELT hits actually matter - the triage a human would do by hand.', 'Ranked candidate list with evidence links - never a score.'],
//   ['Trust pages', 'Read unstructured pages into structured certifications + expiry dates.', 'A claim record, flagged self-reported.'],
//   ['Whole-record digest', 'Summarise what the sources actually found - the hash-stamped evidence plus the score roll-up - into a plain-English brief.', 'Read layer only: describes the evidence (never re-scores), cites content_hashes, marked AI-generated; fed only the already-collected, entity-level OSINT the system holds.'],
// ]

export default function MethodologyPage() {
  return (
    <div className="flex flex-col gap-10">
      <header>
        <h1 className="-mt-6 text-2xl font-bold tracking-tight md:text-3xl">Methodology</h1>
        {/* <p className="mt-1.5 max-w-7xl text-[15px] text-muted-foreground">
          The scoring model <em>is</em> the deliverable. It’s legality-first, uses only free public OSINT,
          and is <b className="text-foreground">penalty-based</b>: start at 100, subtract a penalty per
          issue, and keep two axes - <b className="text-foreground">posture</b> and{' '}
          <b className="text-foreground">confidence</b> - that it never collapses into one number.
        </p> */}
      </header>

      {/* Three axes */}
      <Section icon={Scale} title="Three axes, never collapsed"
        blurb="Three questions, three published numbers."
        detail="Averaging them into one would let a good answer to one hide a bad answer to another.
                Missing data lowers confidence; it never lowers posture, and it never lowers assurity.">
        <div className="grid gap-3 sm:grid-cols-3">
          {AXES.map(([label, axes, headline, note, color]) => (
            <Card key={label} className="p-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
                <h3 className="font-semibold" style={{ color }}>{label}</h3>
              </div>
              <div className="mt-1 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">{axes}</div>
              {/* The one-line answer stands; the rule that governs it is a tooltip on the card. */}
              <p className="mt-2 text-[13px] text-muted-foreground" title={note}>{headline}</p>
            </Card>
          ))}
        </div>
        <Card className="mt-3 px-4 py-3">
          <Disclose label="Why Assurity is a separate axis, not a posture bonus">
            <p className="max-w-4xl text-[12.5px] leading-relaxed text-muted-foreground">{ASSURITY_FENCE}</p>
          </Disclose>
        </Card>
      </Section>

      {/* No grade published — three different reasons */}
      <Section icon={Ban} title="When no grade is published"
        blurb="Three different things, routinely read as one."
        detail="Each is a designed outcome rather than an error, and each needs a different response
                from the reader. A UI that colours them alike is the bug this distinction exists to
                prevent.">
        <div className="grid gap-3 md:grid-cols-3">
          {NO_SCORE_STATES.map(([label, headline, body, color]) => (
            <Card key={label} className="flex flex-col p-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
                <h3 className="font-semibold" style={{ color }}>{label}</h3>
              </div>
              {/* Headline stands; the full statement is the tooltip. */}
              <div className="mt-1 text-[12.5px]" title={body}>{headline}</div>
            </Card>
          ))}
        </div>
      </Section>

      {/* Penalties + grades */}
      <Section icon={Layers} title="Scoring framework — subtract a penalty per issue"
        blurb="Four fixed severity penalties are the only points table."
        detail="No category weights to defend: a category's influence emerges from the issues found
                in it. Each category posture is 100 minus its own penalties; the overall posture is
                100 minus the total penalty over a FIXED divisor — fixed so a clean check can never
                raise the score and a silent source can never lower it.">
        <div className="grid gap-3 lg:grid-cols-2">
          <Card className="overflow-hidden">
            <div className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Severity penalties</div>
            <div className="divide-y divide-border">
              {SEVERITIES.map(([sev, pen, ex, color]) => (
                <div key={sev} className="grid grid-cols-[auto_auto_1fr] items-center gap-x-3 gap-y-0 px-4 py-2.5">
                  <span className="font-semibold" style={{ color }}>{sev}</span>
                  <span className="font-mono text-sm tabular-nums" style={{ color }}>{pen}</span>
                  <span className="text-[12px] text-muted-foreground">{ex}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card className="overflow-hidden">
            <div className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Grades (from posture)</div>
            <div className="divide-y divide-border">
              {GRADES.map(([g, range, note, color]) => (
                <div key={g} className="grid grid-cols-[auto_auto_1fr] items-center gap-3 px-4 py-2.5">
                  <span className="grid h-7 w-7 place-items-center rounded-md text-sm font-bold"
                    style={{ color, background: `color-mix(in srgb, ${color} 15%, transparent)` }}>{g}</span>
                  <span className="font-mono text-[12px] text-muted-foreground">{range}</span>
                  <span className="text-[13px]">{note}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card className="mt-3 overflow-hidden">
          <div className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Per-finding adjustment · NIST SP 1326
          </div>
          <div className="px-4 pt-3">
            <div className="overflow-x-auto">
              <code className="block whitespace-nowrap font-mono text-[12.5px]">
                <span>effective penalty</span>
                <span className="text-muted-foreground"> = </span>
                <span>severity × age × frequency</span>
                {/* <span className="text-muted-foreground"> (×0.6 when an evidenced fix is accepted)</span> */}
              </code>
            </div>
          </div>
          <div className="mt-2 divide-y divide-border border-t border-border">
            {NIST_FACTORS.map(([name, note]) => (
              <div key={name} className="grid gap-x-4 gap-y-0.5 px-4 py-3 sm:grid-cols-[7rem_1fr]">
                <span className="text-sm font-semibold">{name}</span>
                <p className="text-[12px] leading-relaxed text-muted-foreground">{note}</p>
              </div>
            ))}
          </div>
        </Card>

        <div className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Seven categories · the signals in each</div>
        <Card className="mt-2 divide-y divide-border">
          {CATEGORIES.map(([name, key, check, signals]) => (
            <CategoryRow key={key} name={name} engineKey={key} check={check} signals={signals} />
          ))}
        </Card>

        {/* <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Mini title="Critical ceiling" body="Non-compensatory. A directly-observed current critical (an expired production cert) CAPS the posture at the top of Grade D - one severe live issue can't be averaged away." />
          <Mini title="Worst-of vs sum" body="Distinct realized issues (breaches) sum; a bag of keyword-matched CVEs is worst-of, so coarse-match noise can't tank a clean estate." />
          <Mini title="The Ghost" body="Below 40% evidence coverage we publish no grade and name the silent sources - a clean-looking vendor we can't stand behind is a designed refusal, not an error." />
        </div> */}
      </Section>

      {/* Inherent & residual risk — the layer procurement actually decides from. */}
      <Section icon={ShieldAlert} title="Inherent risk and residual risk"
        blurb="Posture cannot say how much you stand to lose. The buyer declares that."
        detail="“How strong is this vendor?” and “how much do we stand to lose if they fail?” are
                different questions. The second depends on what this buyer has given them, which no
                amount of outside-in scanning can observe. The two combine into the tier a decision
                is actually made against.">
        <div className="grid gap-3 md:grid-cols-3">
          {RISK_LAYERS.map(([name, owner, note]) => (
            <Card key={name} className="p-4" title={note}>
              <h3 className="text-sm font-semibold">{name}</h3>
              <div className="mt-0.5 font-mono text-[10.5px] uppercase tracking-wide text-accent">{owner}</div>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
                {note.split('. ')[0]}.
              </p>
            </Card>
          ))}
        </div>

        <div className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          The published matrix · sixteen cells, fixed
        </div>
        <Card className="mt-2 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Posture ↓ / Inherent →</th>
                  {RESIDUAL_COLS.map((c) => (
                    <th key={c} className="px-4 py-2.5 font-medium capitalize">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {RESIDUAL_ROWS.map((band) => (
                  <tr key={band} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-2.5 text-[13px] font-semibold capitalize">{band}</td>
                    {RESIDUAL_COLS.map((tier) => {
                      const cell = RESIDUAL_MATRIX[band][tier]
                      return (
                        <td key={tier} className="px-4 py-2.5">
                          <span className="rounded-md px-2 py-1 text-[12px] font-medium"
                            style={{ color: RESIDUAL_TONE[cell],
                              background: `color-mix(in srgb, ${RESIDUAL_TONE[cell]} 14%, transparent)` }}>
                            {RESIDUAL_LABEL[cell]}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

      </Section>

      {/* P5 — assessment depth */}
      <Section icon={Layers} title="Assessment depth — effort matched to exposure"
        blurb="The declared inherent tier sets sources, cadence and artefacts."
        detail="Not every relationship warrants the same assessment. A screening-depth plan
                publishes no posture and says so BEFORE the run, so a reader never meets a refusal
                and mistakes it for a finding about the vendor.">
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Tier</th>
                  <th className="px-4 py-2.5 font-medium">Depth</th>
                  <th className="px-4 py-2.5 font-medium">Sources</th>
                  <th className="px-4 py-2.5 font-medium">Review cadence</th>
                  <th className="px-4 py-2.5 font-medium">Posture</th>
                </tr>
              </thead>
              <tbody>
                {DEPTHS.map(([tier, depth, sources, cadence, publishes]) => (
                  <tr key={tier} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-2.5 text-[13px] font-semibold text-accent">{tier}</td>
                    <td className="px-4 py-2.5 text-[13px] capitalize">{depth}</td>
                    <td className="px-4 py-2.5 text-[13px] text-muted-foreground">{sources}</td>
                    <td className="px-4 py-2.5 text-[13px] text-muted-foreground">{cadence}</td>
                    <td className="px-4 py-2.5">
                      {publishes
                        ? <Badge style={{ color: 'var(--risk-low)', background: 'color-mix(in srgb, var(--risk-low) 13%, transparent)' }}><CheckCircle2 className="h-3 w-3" />published</Badge>
                        : <Badge className="bg-secondary text-muted-foreground">not published</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="mt-2">
          <Disclose label="Two clocks, published separately and never averaged">
            <p className="max-w-4xl text-[12.5px] leading-relaxed text-muted-foreground">
              The review cadence above tracks how much the RELATIONSHIP is worth reassessing, and
              moves when the contract moves. A finding’s re-check date (7–90 days) tracks one thing
              we FOUND, and moves when the vendor’s controls move. Whichever falls sooner is the
              next action, and the report names which clock set it.
            </p>
          </Disclose>
        </div>
      </Section>

      {/* System flow — the diagram first for shape, then the same steps in prose for detail. */}
      <Section icon={GitBranch} title="System flow"
        blurb="A fixed sequence. Evidence is stored before any scoring begins."
        detail="Two paths end without a published grade, and both are designed states rather than
                errors: a sanctions or identity match goes to a person, and a vendor below the
                evidence floor is reported as a Ghost. A Ghost still receives the target-maturity
                reading, because that measure depends on neither a published posture nor a peer
                group.">
        <PipelineDiagram nodes={PIPELINE} />

        <div className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          The same sequence, step by step
        </div>
        <Card className="mt-2 divide-y divide-border">
          {FLOW.map(([title, summary, body, Icon]) => (
            <FlowStep key={title} title={title} summary={summary} body={body} Icon={Icon} />
          ))}
        </Card>
      </Section>

      {/* Sources */}
      <Section icon={Database} title="Sources"
        blurb="Free, public, licence-checked, failure-isolated."
        detail="Each collector returns the same evidence envelope, so a source that fails lowers
                coverage without stopping the run. Excluded on principle: anything trading in
                natural-person data, and paid or ToS-restricted feeds. Exclusions are logged with a
                reason, never silently dropped.">
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Source</th>
                  <th className="px-4 py-2.5 font-medium">What it checks</th>
                  <th className="px-4 py-2.5 font-medium">Used for</th>
                  <th className="px-4 py-2.5 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {/* A source can feed more than one category (DNS scores into two), so the row key
                    is source + category, not source. */}
                {SOURCES.map(([source, checks, usedFor, kind]) => (
                  <tr key={`${source}·${usedFor}`} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-2.5 text-[13px] font-semibold text-accent">{source}</td>
                    <td className="px-4 py-2.5 text-[13px]">{checks}</td>
                    <td className="px-4 py-2.5 text-[13px] text-muted-foreground">{usedFor}</td>
                    <td className="px-4 py-2.5"><KindBadge kind={kind} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        {/* <p className="mt-3 text-[13px] text-muted-foreground">
          <b className="text-foreground">Excluded on principle:</b> anything trading in natural-person data
          (executives, PEP screening, person-level ownership) and paid/ToS-restricted feeds
          (Shodan/Censys free tiers, VirusTotal). Logged, not silently dropped.
        </p> */}
      </Section>

      {/* THE INTERPRETATION LAYERS, in one section rather than five.
          Each one interprets the posture without moving it; splitting them across five headings
          with a card apiece made the page longer without making any of them clearer. */}
      <Section icon={TrendingUp} title="Interpretation — what the number means beside other things"
        blurb="Five readings that give the posture context. None of them can change it."
        detail="Every layer here answers a question the posture cannot answer about itself: am I
                typical, am I adequate, am I what my peer group predicts, are my own assertions
                reliable, and how much track record stands behind the measurement. Each is computed
                from the published score and none feeds back into it.">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {INTERPRETATION.map(([title, Icon, question, body]) => (
            <Card key={title} className="p-4">
              <h3 className="flex items-center gap-1.5 text-sm font-semibold">
                <Icon className="h-4 w-4 shrink-0 text-accent" />{title}
              </h3>
              <div className="mt-1 text-[12px] font-medium text-accent">{question}</div>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">{body}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* Fourth-party dependencies */}
      {/* <Section icon={Network} title="Fourth-party dependencies"
        blurb="Who the vendor itself relies on — the providers behind the provider. Disclosed as concentration context, never charged against this vendor's score.">
        <RowCard rows={FOURTH_PARTY} />
      </Section> */}

      {/* Disputes / refute path */}
      {/* <Section icon={MessageSquare} title="Disputes & refutes"
        blurb="Outside-in scoring systematically over-penalises, because it cannot see compensating controls. A vendor can contest a finding with evidence — and only a human-accepted refute ever moves the score.">
        <RowCard rows={DISPUTES} />
      </Section> */}

      {/* Continuous monitoring */}
      {/* <Section icon={RefreshCw} title="Continuous monitoring"
        blurb="A point-in-time assessment is true on the day it is signed; risk is not. Stale vendors are re-scored on a cadence, and every run is a new immutable record.">
        <RowCard rows={MONITORING} />
      </Section> */}

      {/* Role-based views — temporarily hidden.
      <Section icon={Users} title="Role-based views"
        blurb="The same record, read five ways — procurement, analyst, risk, executive, auditor. A role changes what is shown first, never what is true.">
        <RowCard rows={ROLE_PRINCIPLES} />

        <Card className="mt-3 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Role</th>
                  <th className="px-4 py-2.5 font-medium">Main focus</th>
                </tr>
              </thead>
              <tbody>
                {ROLE_FOCUS.map(([role, focus]) => (
                  <tr key={role} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-2.5 text-[13px] font-semibold text-accent">{role}</td>
                    <td className="px-4 py-2.5 text-[13px]">{focus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </Section> */}

      {/* Where AI is used - and where it is fenced */}
      {/* <Section icon={Sparkles} title="Where AI is used - and where it is fenced"
        blurb="Three designated moments. AI never computes or moves a score - every output is evidence-linked and human-adjudicable. “The model said so” is not reasonable grounds.">
        <div className="grid gap-3 md:grid-cols-3">
          {AI_MOMENTS.map(([moment, task, fence]) => (
            <Card key={moment} className="flex flex-col p-4">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent" />
                <h3 className="text-sm font-semibold">{moment}</h3>
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{task}</p>
              <div className="mt-3 flex items-start gap-1.5 border-t border-border pt-2 text-[12px] text-foreground">
                <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                <span><b>Fence:</b> {fence}</span>
              </div>
            </Card>
          ))}
        </div>
        <p className="mt-3 text-[13px] text-muted-foreground">
          <b className="text-foreground">The digest is opt-in and provider-agnostic.</b> It speaks the
          OpenAI-compatible API, so an operator points it at any provider they trust (OpenRouter, Groq,
          Gemini) - off by default. It reads the <em>record</em>, not the raw internet: only the already-collected,
          entity-level OSINT the system holds (the hash-stamped observations + the score roll-up) crosses the
          boundary - bounded per-receipt - so it is the system’s single, documented data-egress point and can
          never become a shadow scorer.
        </p>
      </Section> */}
    </div>
  )
}

/**
 * A section header: one line of orientation, and the argument behind a toggle.
 *
 * `blurb` is a single short sentence — what this section is. `detail` is the reasoning, which is
 * the part that used to sit open as a four-line paragraph under every heading on this page. Nine
 * such paragraphs is a wall of text before a reader reaches a single figure, at which point none
 * of them get read and the rigour they carry is lost. Closed, the argument is one click away and
 * still on the page for anyone who wants to challenge it.
 */
function Section({ icon: Icon, title, blurb, detail, children }) {
  const [open, setOpen] = useState(false)
  return (
    <section>
      <div className="mb-4 flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
          <Icon className="h-[18px] w-[18px] text-accent" />
        </div>
        <div className="min-w-0">
          <h2 className="text-lg font-bold tracking-tight">{title}</h2>
          <div className="flex flex-wrap items-baseline gap-x-2">
            {blurb && <p className="text-[13px] text-muted-foreground">{blurb}</p>}
            {detail && (
              <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
                className="text-[12px] font-semibold text-accent hover:underline">
                {open ? 'less' : 'why'}
              </button>
            )}
          </div>
          {open && detail && (
            <p className="mt-2 max-w-4xl border-l-2 border-border pl-3 text-[12.5px] leading-relaxed text-muted-foreground">
              {detail}
            </p>
          )}
        </div>
      </div>
      {children}
    </section>
  )
}

function CategoryRow({ name, engineKey, check, signals }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 p-3.5 text-left transition hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-sm font-medium">{name}</span>
            {/* The key the scorecard shows, so a category can be carried between the two screens. */}
            <code className="font-mono text-[10.5px] text-muted-foreground">{engineKey}</code>
          </div>
          <div className="truncate text-[11px] text-muted-foreground">{check}</div>
        </div>
        <div className="font-mono text-[11px] text-muted-foreground">{signals.length} signal{signals.length > 1 ? 's' : ''}</div>
      </button>
      {open && (
        <div className="border-t border-border bg-secondary/30 px-3.5 pb-3 pt-2 sm:pl-10">
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Signals - each maps an observation to a severity (or pass)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {signals.map((s) => (
              <span key={s} className="rounded-md border border-border bg-card px-2 py-1 text-[12px] text-foreground">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// One row per pipeline step: icon, title, a single summary line, and the full explanation on
// demand. Same component shape as `CategoryRow` above, deliberately — a reader learns one
// interaction on this page rather than four.
function FlowStep({ title, summary, body, Icon }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="grid w-full grid-cols-[auto_auto_1fr] items-center gap-3 p-3.5 text-left transition hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
          <Icon className="h-[15px] w-[15px] text-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-semibold">{title}</div>
          <div className="text-[12px] leading-relaxed text-muted-foreground">{summary}</div>
        </div>
      </button>
      {open && (
        <p className="max-w-4xl border-t border-border bg-secondary/30 px-3.5 py-3 text-[12.5px] leading-relaxed text-muted-foreground sm:pl-[4.5rem]">
          {body}
        </p>
      )}
    </div>
  )
}

// function Mini({ title, body }) {
//   return (
//     <Card className="p-4">
//       <h4 className="mb-1 flex items-center gap-1.5 text-sm font-semibold">
//         <CheckCircle2 className="h-4 w-4 shrink-0 text-accent" />{title}
//       </h4>
//       <p className="text-[13px] leading-relaxed text-muted-foreground">{body}</p>
//     </Card>
//   )
// }


// --------------------------------------------------------------------- the pipeline diagram

const NODE_TONE = {
  start: 'var(--accent)',
  end: 'var(--risk-low)',
  stop: 'var(--blocked)',
  ghost: 'var(--ghost)',
}

function Connector() {
  return (
    <div aria-hidden className="flex h-5 justify-center">
      <div className="w-px bg-border" />
    </div>
  )
}

function PipelineNode({ title, note, items, chips, tone, compact }) {
  const color = NODE_TONE[tone]
  return (
    <div className={cnLocal('rounded-xl border bg-card px-4 shadow-2xs', compact ? 'py-2.5' : 'py-3')}
      style={color ? { borderColor: color, background: `color-mix(in srgb, ${color} 7%, var(--card))` } : undefined}>
      <div className="text-[13px] font-semibold" style={color ? { color } : undefined}>{title}</div>
      {note && <div className="mt-0.5 text-[11px] text-muted-foreground">{note}</div>}
      {items && (
        <ul className="mt-1.5 space-y-0.5">
          {items.map((it) => (
            <li key={it} className="flex gap-1.5 text-[11.5px] text-muted-foreground">
              <span aria-hidden>·</span><span>{it}</span>
            </li>
          ))}
        </ul>
      )}
      {chips && (
        <div className="mt-2 flex flex-wrap gap-1">
          {chips.map((c) => (
            <span key={c} className="rounded border border-border bg-secondary/50 px-1.5 py-0.5 font-mono text-[10.5px] text-muted-foreground">
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// A labelled fork. The two outcomes sit side by side so the reader sees both destinations at once
// rather than having to hold one in their head while scrolling to the other.
function PipelineBranch({ yes, no, yesLabel = 'Yes', noLabel = 'No' }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {[[noLabel, no], [yesLabel, yes]].map(([label, node]) => (
        <div key={label} className="flex flex-col">
          <div className="mb-1 text-center text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            {label}
          </div>
          <PipelineNode {...node} compact />
        </div>
      ))}
    </div>
  )
}

function PipelineDiagram({ nodes }) {
  return (
    <Card className="p-5">
      <div className="mx-auto flex max-w-2xl flex-col">
        {nodes.map((n, i) => (
          <div key={n.title}>
            {i > 0 && <Connector />}
            {n.kind === 'decision' ? (
              <div className="flex flex-col">
                <PipelineNode title={n.title} items={n.items} />
                <Connector />
                <PipelineBranch yes={n.yes} no={n.no} />
              </div>
            ) : n.kind === 'parallel' ? (
              <div className="flex flex-col">
                <div className="mb-2 text-center text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  {n.title}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <PipelineNode {...n.left} compact />
                  <PipelineNode {...n.right} compact />
                </div>
              </div>
            ) : (
              <PipelineNode {...n} />
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}

// Local class-joiner — this page does not otherwise import the shared `cn`, and one tiny helper
// beats pulling in a utility for a single conditional class.
function cnLocal(...parts) {
  return parts.filter(Boolean).join(' ')
}

// `SummaryCard` was here — a full-width card holding one paragraph, used by the three separate
// benchmark / target-maturity / operating-history sections. Those are now one `INTERPRETATION`
// grid, so the wrapper has no callers and is gone rather than left dormant.

// A titled two-column list. Its last live caller was the role-principles block; kept because the
// commented-out fourth-party, disputes and monitoring sections all render through it too.
// function RowCard({ rows }) {
//   return (
//     <Card className="divide-y divide-border">
//       {rows.map(([name, note]) => (
//         <div key={name} className="grid gap-x-4 gap-y-0.5 px-4 py-3 sm:grid-cols-[13rem_1fr]">
//           <span className="text-sm font-semibold">{name}</span>
//           <p className="text-[12.5px] leading-relaxed text-muted-foreground">{note}</p>
//         </div>
//       ))}
//     </Card>
//   )
// }

function KindBadge({ kind }) {
  if (kind === 'gate') return <Badge style={{ color: 'var(--blocked)', background: 'color-mix(in srgb, var(--blocked) 14%, transparent)' }}><Ban className="h-3 w-3" />gate</Badge>
  if (kind === 'held') return <Badge className="bg-secondary text-muted-foreground">held</Badge>
  if (kind === 'context') return <Badge className="bg-secondary text-muted-foreground">context · not scored</Badge>
  return <Badge style={{ color: 'var(--risk-low)', background: 'color-mix(in srgb, var(--risk-low) 13%, transparent)' }}><CheckCircle2 className="h-3 w-3" />scored</Badge>
}




//         <div className="mt-3 grid gap-3 sm:grid-cols-3">
//          <Mini title="Undeclared is not Low"
//            body="A relationship nobody has classified routes to the DEEPEST assessment, not the shallowest. The vendors nobody has got round to classifying are disproportionately the ones nobody has looked at." />
//          <Mini title="Strong posture never reaches Low"
//            body="High inherent exposure with an A grade lands at Medium. A vendor holding your production data is still holding your production data, and the day their posture moves you discover how much was riding on it." />
//          <Mini title="Non-compensatory"
//            body="Inherent tier is the HIGHER of criticality and data-access scope — never the average. A low-criticality vendor with production data access is not a medium-risk vendor." />
//        </div>