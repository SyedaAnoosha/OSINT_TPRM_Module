// Plain label/lookup constants shared between `Scorecard.jsx` and the Tier-1/Tier-2 dashboard
// components (`ExecutiveSummaryHero.jsx`, `TopFindings.jsx`, `EvidenceCoverageBar.jsx`). Split out
// of `Scorecard.jsx` itself rather than re-exported from it: that file exports React components,
// and Vite's fast-refresh boundary breaks when a component module also exports plain constants —
// a second copy of any of these would be a second place for a category name or a grade sentence to
// drift from the one the score card renders.

export const PRETTY = {
  cyber_hygiene_technical: 'Cyber Hygiene & Technical',
  breach_compromise_history: 'Breach & Compromise History',
  vendor_transparency_gov: 'Vendor Transparency & Governance',
  digital_footprint_assets: 'Digital Footprint & Assets',
  business_financial_stability: 'Business & Financial Stability',
  compliance_regulatory: 'Compliance & Regulatory',
  adverse_media_reputation: 'Adverse Media & Reputation',
}

export const deSnake = (s) => String(s || '').replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

// scoring.yaml §0 / docs/tprm_feedback_redesign.md §0.1 — the two CONTEXT categories, asserted by
// a shipped backend test (`test_context_categories_never_penalise`) to never carry a penalty. They
// always publish `posture: 100`, so a "top strengths" ranking that does not exclude them would
// show the same two context categories on every vendor, forever, crowding out the scoring
// categories that actually vary and are the ones a "strength" claim should be about.
export const CONTEXT_CATEGORIES = new Set(['continuity_context', 'assurance_context'])

export const GRADE_MEANING = {
  A: 'Robust posture- few or no external issues found.',
  B: 'Reasonable controls, with some gaps.',
  C: 'Poor controls- serious issues to address.',
  D: 'Severe issues; should not handle sensitive data.',
  F: 'Little to no basic security investment.',
}

// The confidence band's plain sentence — the counterpart to GRADE_MEANING, so the second axis
// explains itself instead of leaving a bare percentage for the reader to interpret. Bands come
// from scoring.yaml (High >=0.90, Medium >=0.70, else Low).
export const CONFIDENCE_MEANING = {
  High: 'Most planned checks returned evidence.',
  Medium: 'Some sources were silent- read with care.',
  Low: 'Thin evidence- treat the grade as unassessed.',
}
