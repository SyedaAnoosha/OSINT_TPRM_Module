// Thin client for the scoring API. Two calls the scorecard needs:
//   scoreVendor()  — POST a vendor, then STREAM progress over SSE, then fetch the full record.
//   getEvidence()  — pull one hash-stamped receipt on demand (Finding A: every number is backed).
//
// The API deliberately makes a bare score unrepresentable — every record carries
// posture + confidence(coverage) + grade, with blocked/refused — so the UI never invents a second axis.

/** POST a vendor, open the SSE stream, relay progress, resolve with the final Score record.
 *  A name with no domain does NOT score — the API returns candidate domains to confirm first;
 *  we surface that as `{ needsDomain, name, candidates }` for the caller to prompt on. */
export async function scoreVendor({ name, domain, criticality, sizeBand }, { onProgress } = {}) {
  const body = domain ? (name ? { name, domain } : { domain }) : { name }
  // The client-supplied fields. Never inferred: how much a vendor's failure would hurt YOU is not
  // observable from outside, and public sources publish a headcount for far fewer vendors than
  // they publish an industry. Both are recorded as client-supplied and shown as such; neither
  // touches the posture — criticality shapes the recommendation, size picks the peer group.
  if (criticality) body.criticality = criticality
  if (sizeBand) body.size_band = sizeBand
  const res = await fetch('/api/vendors/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`score request failed (${res.status})`)
  const data = await res.json()

  // No domain supplied for a bare name — ask, don't guess.
  if (data.needs_domain) {
    return { needsDomain: true, name: data.name, candidates: data.candidates || [], message: data.message }
  }

  await streamJob(data.stream, onProgress)
  // The job is done; fetch the durable record (full categories + evidence refs).
  const score = await getScore(data.vendor_ref)
  return { vendorRef: data.vendor_ref, jobId: data.job_id, score, domain: data.domain }
}

/** Consume the SSE stream to completion. Resolves on the terminal `done`/`error` event. */
function streamJob(streamUrl, onProgress) {
  return new Promise((resolve, reject) => {
    const es = new EventSource(streamUrl)
    const done = (fn, arg) => { es.close(); fn(arg) }
    for (const name of ['collecting', 'collector_done', 'scoring']) {
      es.addEventListener(name, (e) => onProgress?.(name, safeParse(e.data)))
    }
    es.addEventListener('done', (e) => { onProgress?.('done', safeParse(e.data)); done(resolve) })
    es.addEventListener('error', (e) => {
      // Distinguish a job error (has payload) from a transport drop (EventSource auto-reconnects).
      const payload = e.data ? safeParse(e.data) : null
      if (payload) return done(reject, new Error(payload.message || 'scoring failed'))
      // A bare error with the stream already closed = server ended it; treat as terminal.
      if (es.readyState === EventSource.CLOSED) done(reject, new Error('stream closed unexpectedly'))
    })
  })
}

export async function getScore(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}`)
  if (!res.ok) throw new Error(`could not load score for ${ref} (${res.status})`)
  return res.json()
}

export async function listEvidence(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/evidence`)
  if (!res.ok) throw new Error(`no evidence for ${ref} (${res.status})`)
  return res.json()
}

export async function getEvidence(ref, id) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/evidence/${id}`)
  if (!res.ok) throw new Error(`receipt ${id} not found (${res.status})`)
  return res.json()
}

/** Signal-level findings behind a score: each observation, the severity/penalty the model
 *  assigned it, and the evidence_id of the raw receipt it came from. [] when none stored. */
export async function listFindings(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/findings`)
  if (res.status === 404) return []
  if (!res.ok) throw new Error(`no findings for ${ref} (${res.status})`)
  return res.json()
}

/** Every score this vendor has had, oldest first — the trend behind the current number. Each
 *  re-score (a scheduled recheck, or a re-score after an accepted dispute) already wrote a row,
 *  so a single point is a grade and a line is a direction. [] when never scored. */
export async function getHistory(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/history`)
  if (res.status === 404) return []
  if (!res.ok) throw new Error(`no history for ${ref} (${res.status})`)
  return res.json()
}

/** Add a client-supplied size to a vendor public sources gave none for, so a peer group can form.
 *  Does NOT re-score — size never touches the posture; only the cohort/benchmark updates. */
export async function setVendorSize(ref, sizeBand) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/size`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ size_band: sizeBand }),
  })
  if (!res.ok) {
    let msg = `could not set size (${res.status})`
    try { const b = await res.json(); if (b.detail) msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail) } catch { /* keep */ }
    throw new Error(msg)
  }
  return res.json()
}

/** The whole book at a glance — every vendor's latest score plus concentration metrics. Every row
 *  is the same immutable score the scorecard renders; this view only aggregates. */
export async function getPortfolio() {
  const res = await fetch('/api/portfolio')
  if (!res.ok) throw new Error(`could not load portfolio (${res.status})`)
  return res.json()
}

/** WHO the vendor is: industry, size, country, ownership, and the peer cohort that follows.
 *  Fetched separately from the score on purpose — the profile is context a score is READ
 *  against, never an input to it. null when the vendor has not been profiled. */
export async function getProfile(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/profile`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`no profile for ${ref} (${res.status})`)
  return res.json()
}

/** This vendor's posture against its peer cohort — or a stated refusal to publish one.
 *  `available: false` with a `reason` is a normal, expected response, not an error: below the
 *  minimum peer count the system deliberately shows no percentile. */
export async function getBenchmark(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/benchmark`)
  if (!res.ok) return null
  return res.json()
}

/** The vendors this one may legitimately be compared with — its cohort, and nobody else. */
export async function getPeers(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/peers`)
  if (!res.ok) return null
  return res.json()
}

/** WHO the vendor depends on — its fourth parties, read from evidence already collected.
 *  Disclosed as concentration context, never scored. null before the vendor is assessed. */
export async function getDependencies(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/dependencies`)
  if (res.status === 404) return null
  if (!res.ok) return null
  return res.json()
}

/** The whole record as one self-contained document — what goes in the procurement file.
 *  Its `reconstruction` block re-derives the published score from the findings, so a reader can
 *  check the arithmetic rather than take it on trust. */
export async function getExport(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/export`)
  if (!res.ok) throw new Error(`could not build an evidence pack for ${ref} (${res.status})`)
  return res.json()
}

/** Limits, coverage gaps and attribution. Served rather than hardcoded so the card and the
 *  evidence pack cannot drift — two of these are obligations, not editorial choices. */
export async function getDisclosures() {
  try {
    const res = await fetch('/api/disclosures')
    if (!res.ok) return null
    return res.json()
  } catch { return null }
}

/** Submit a dispute against a specific finding. Creates a PENDING dispute; changes no score until
 *  a human accepts it. `kind` is 'nullify' (does not apply) or 'mitigate' (evidenced remediation). */
export async function submitDispute(ref, { signal, band_key, kind, evidence, submitted_by }) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/disputes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ signal, band_key, kind, evidence, submitted_by }),
  })
  if (!res.ok) {
    let msg = `dispute failed (${res.status})`
    try { const b = await res.json(); if (b.detail) msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail) } catch { /* keep */ }
    throw new Error(msg)
  }
  return res.json()
}

/** Every dispute for a vendor, with current state and full event history. */
export async function getDisputes(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/disputes`)
  if (!res.ok) return null
  return res.json()
}

/** Record a procurement/executive decision (approve/conditional/reject) on a vendor. Stored beside
 *  the score, stamped with the posture/grade at this moment — it changes no number. */
export async function recordDecision(ref, { decision, conditions, decided_by }) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/decisions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, conditions, decided_by }),
  })
  if (!res.ok) {
    let msg = `decision failed (${res.status})`
    try { const b = await res.json(); if (b.detail) msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail) } catch { /* keep */ }
    throw new Error(msg)
  }
  return res.json()
}

/** Every decision recorded for a vendor, newest first (current + history). null when unreachable. */
export async function getDecisions(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/decisions`)
  if (!res.ok) return null
  return res.json()
}

/** AI digest of a finished record (opt-in). Read layer only — never re-scores. */
export async function summariseVendor(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/summary`, { method: 'POST' })
  if (res.status === 503) throw new Error('The AI summariser is not configured on this server.')
  if (!res.ok) {
    let msg = `summary failed (${res.status})`
    try { const b = await res.json(); if (b.detail) msg = b.detail } catch { /* keep default */ }
    throw new Error(msg)
  }
  return res.json()
}

/** Whether the server has an LLM summariser configured — gates the Summarise button. */
export async function getCapabilities() {
  try {
    const res = await fetch('/health')
    if (!res.ok) return { summary_enabled: false }
    return res.json()
  } catch { return { summary_enabled: false } }
}

function safeParse(s) {
  try { return JSON.parse(s) } catch { return {} }
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The "So what" and "Now what" layers.
//
// Everything below already existed on the API and had no interface. That is not a cosmetic gap:
// `inherent_tier_declaration_rate` sat at 0.0% across 146 vendors partly because there was no
// button to declare a tier, and a backend capability with no UI is operationally a capability
// that does not exist.
// ═══════════════════════════════════════════════════════════════════════════════════════════

/** GET helper: 404 → null (a normal "not applicable yet"), other errors → null with a warning.
 *  A missing section must degrade to an absent card, never to a blank page — the vendor page
 *  composes ten independent reads and one silent 500 must not take the other nine down. */
async function getOrNull(path) {
  try {
    const res = await fetch(path)
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

async function postJson(path, body, what) {
  const res = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let msg = `${what} failed (${res.status})`
    try {
      const b = await res.json()
      if (b.detail) msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail)
    } catch { /* keep */ }
    throw new Error(msg)
  }
  return res.json()
}

/** E10b — the residual cell, recomputed on read from posture × declared inherent tier.
 *  `published: false` with a `reason` is a NORMAL response, not an error: an undeclared exposure
 *  or a blocked score deliberately publishes no residual tier. The UI renders the refusal. */
export const getResidualRisk = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/residual-risk`)

/** DECLARE THE RELATIONSHIP'S INHERENT EXPOSURE — without re-scoring.
 *
 * The highest-value write in the whole client. One declaration publishes an E10b residual tier,
 * tags P3's evidence pack, routes P5's collection depth and cadence, and moves the programme's
 * declaration rate. It touches NO posture: inherent exposure and observed posture run on
 * different clocks, and a contract change must never look like a security event.
 */
export const declareInherent = (ref, body) =>
  postJson(`/api/vendors/${encodeURIComponent(ref)}/inherent`, body, 'declaration')

/** P2 — what this assessment could and could not see. Rendered VERBATIM, never paraphrased. */
export const getCoverage = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/coverage`)

/** P5 — how much assessment this relationship warrants and when it is next due. */
export const getAssessmentPlan = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/assessment-plan`)

/** P3 — the questions worth asking, scoped to what actually failed. */
export const getEvidencePack = (ref, view) =>
  getOrNull(`/api/vendors/${encodeURIComponent(ref)}/evidence-request-pack${view ? `?view=${view}` : ''}`)

/** P4 — what a vendor response cannot close, as contract language. */
export const getFlowdowns = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/contract-flowdowns`)

/** P8 — what leaving would cost, and whether there is anywhere to go. */
export const getExitReadiness = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/exit-readiness`)

/** Going-concern standing from registries. Never a derived distress index. */
export const getContinuity = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/continuity`)

/** P7 — the vendor's own status page. Emits no finding and reaches no score. */
export const getStatusPage = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/status-page`)

/** E9a + E9c — the ASSURANCE axis and the compliance gaps, in one response.
 *
 *  A separate axis from posture on purpose: "their TLS is current" and "an auditor has examined
 *  their controls" are different claims, and a vendor can be strong on one and silent on the
 *  other. Absence never subtracts here — a vendor with no observable assurance sits at the floor
 *  because it is unevidenced, not because it was examined and failed. */
export const getAssurity = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/assurity`)

// ── peer benchmarking v2 (/api/v2) ────────────────────────────────────────────────────────────
//
// The system in docs/benchmarking-design.md, and the one the UI reads. The v1 route
// `/api/vendors/{ref}/benchmark` is deprecated server-side and goes one release from now; it
// cannot do midrank ties, `rank_of_n`, a reproducible cohort snapshot, per-cohort discrimination
// or the dispute path, all of which the screens below render.

/** Where this supplier sits among its peers — the placement, with `n` attached to every figure.
 *  A percentile appears only at n>=30, a quartile only at n>=8, and below that the response
 *  states "insufficient peer data" and gives the actual `n`. Those refusals are the feature. */
export const getPlacement = (ref) =>
  getOrNull(`/api/v2/suppliers/${encodeURIComponent(ref)}/benchmark`)

// `GET /api/v2/suppliers/{ref}/cohort` is deliberately NOT wrapped here. It serves the assignment
// without the comparison, for a supplier disputing its peer group — and the placement above
// already carries the same `assignment` object, rationale ladder and all. A second client for the
// same data is a second thing to keep in step, and the one that drifts is the one nobody renders.

/** E10a — `Posture − E[Posture | cohort]`, with the observations that account for it.
 *  The drivers are RANKED, not a decomposition: since E7a what a finding costs depends on what
 *  else was charged alongside it, so per-signal attributions do not sum to the gap. */
export const getExpectationGap = (ref) =>
  getOrNull(`/api/v2/suppliers/${encodeURIComponent(ref)}/expectation-gap`)

/** The full assessment roll-up: compliance gap, expectation gap, recommendation. */
export const getAssessment = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/assessment`)

/** P6 — one immutable score, two renderings. `view` is 'procurement' | 'security'.
 *  `views_agree()` ships as a backend invariant; the UI cross-checks it anyway (see PackPage). */
export const getExportView = (ref, view) =>
  getOrNull(`/api/vendors/${encodeURIComponent(ref)}/export${view ? `?view=${view}` : ''}`)

// ── programme-level ───────────────────────────────────────────────────────────────────────

/** Blocked records with the facts needed to decide them. Ordered by INHERENT EXPOSURE, never by
 *  how weak the match looks — a queue sorted weakest-first reads as a recommendation to clear
 *  from the top, which is the rubber stamp arriving by a different route. */
export const getAdjudicationQueue = () => getOrNull('/api/adjudications/queue')

/** Record a human decision on a blocked gate. `decision` is 'cleared' | 'upheld'. */
export const adjudicate = (ref, body) =>
  postJson(`/api/adjudications/${encodeURIComponent(ref)}`, body, 'adjudication')

/** The inventory of record — relationships vs seeded corpus vs inventory defects, and the
 *  corrected declaration denominator. */
export const getInventory = () => getOrNull('/api/program/inventory')

/** Is the monitoring schedule alive? A DIFFERENT question from `monitoring_currency`, which can
 *  read 100% on a schedule that died in March — nothing is re-scored into staleness when nothing
 *  is re-scored at all. Here, SILENCE IS THE ALARM CONDITION. */
export const getMonitoring = () => getOrNull('/api/program/monitoring')

/** P9 — the eight-dimension maturity self-assessment. Level is the MINIMUM, never the average. */
export const getMaturity = () => getOrNull('/api/program/maturity')

/** P9 — fifteen metrics, twelve computed and three declared-or-empty. */
export const getKpis = () => getOrNull('/api/program/kpis')

/** E12 — whether the estate fan-out can be switched on. Measured, not asserted. */
export const getEstateReadiness = () => getOrNull('/api/program/estate-readiness')

// ── gap analysis (E14) ────────────────────────────────────────────────────────────────────
//
// A third audience view whose renderer is a language model, over a finished assessment it never
// adjusts. NEVER SILENTLY ABSENT, NEVER ENABLED-BUT-USELESS: `getGapAnalysisGate` is what a
// caller checks BEFORE offering the button, so a disabled state always carries the reason a
// human can read rather than a 409 nobody sees until they click.

/** Whether "Generate Gap Analysis" may run right now, and the stated reason(s) when it may not. */
export const getGapAnalysisGate = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/gap-analysis/gate`)

/** Every analysis generated for this vendor, newest first, each with its recommendations' current
 *  accept/edit/reject status. */
export const getGapAnalysisHistory = (ref) => getOrNull(`/api/vendors/${encodeURIComponent(ref)}/gap-analysis/history`)

/** Generate a new analysis. 409 = a gate condition was not met (message names which); 503 = no
 *  provider configured, or every configured provider failed on transport grounds. Never a
 *  degraded template — a failed generation is an error, not a thinner answer. */
export async function generateGapAnalysis(ref) {
  const res = await fetch(`/api/vendors/${encodeURIComponent(ref)}/gap-analysis`, { method: 'POST' })
  if (!res.ok) {
    let msg = `gap analysis failed (${res.status})`
    try { const b = await res.json(); if (b.detail) msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail) } catch { /* keep */ }
    throw new Error(msg)
  }
  return res.json()
}

/** Accept, edit or reject ONE recommendation. Append-only: a rejection is recorded, never
 *  deleted; an edit keeps the model's original alongside the analyst's rewrite. */
export const recordGapAnalysisAction = (ref, analysisId, recIndex, { action, edited_text, actor, note }) =>
  postJson(
    `/api/vendors/${encodeURIComponent(ref)}/gap-analysis/${encodeURIComponent(analysisId)}/recommendations/${recIndex}`,
    { action, edited_text, actor, note },
    'recommendation action',
  )
