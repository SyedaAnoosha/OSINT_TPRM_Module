// Role-based views — one record, five projections. NOT five scores.
//
// THE RULE THIS FILE EXISTS TO HOLD: every view renders from the SAME API response. No role
// fetches different data, and no role sees a different number. The moment an executive summary is
// computed differently from the analyst detail, a score stops being reconstructible — which is the
// one property Finding A actually requires. So a role changes what is shown FIRST and how much is
// expanded by default; it never changes what is true.
//
// A reader can always switch role and reach the receipt behind any figure.

export const ROLES = {
  procurement: {
    label: 'Procurement',
    question: 'Can we buy from this vendor?',
    // Leads with the decision. A procurement reader does not want to scroll into cipher suites to
    // find out whether they can sign.
    lead: 'recommendation',
    expandCategories: false,
    materialOnly: true,      // hide clean categories — only what actually cost points
    showReceipts: false,
    showBenchmark: true,
    benchmarkDepth: 'simple', // quartile / median + one sentence — the decision read, not the stats
    showDisclosures: true,
    canDecide: true,         // records an approve/conditional/reject decision on this vendor
    canDispute: false,
  },
  analyst: {
    label: 'Security analyst',
    question: 'What exactly is wrong, and is it real?',
    lead: 'score',
    expandCategories: true,
    materialOnly: false,     // clean passes are evidence too: "checked, and fine"
    showReceipts: true,
    showBenchmark: true,     // "is the relative position real?" — the analyst wants the cohort too
    benchmarkDepth: 'full',  // full stats · widening path · per-category · charts
    showDisclosures: true,
    canDecide: false,
    canDispute: true,        // investigates, and contests a finding with evidence
  },
  risk: {
    label: 'Risk manager',
    question: 'How does this sit in my risk universe?',
    lead: 'score',
    expandCategories: false,
    materialOnly: true,
    showReceipts: false,
    showBenchmark: true,
    benchmarkDepth: 'full',  // portfolio context when available; the full relative picture
    showDisclosures: true,
    canDecide: false,
    canDispute: true,
  },
  executive: {
    label: 'Executive / CISO',
    question: 'Where is my exposure?',
    lead: 'recommendation',
    expandCategories: false,
    materialOnly: true,
    topFindingsOnly: 3,      // the three that drove the score, not all nine
    showReceipts: false,
    showBenchmark: true,
    benchmarkDepth: 'minimal', // one line — quartile / traffic-light, no stats to parse
    showDisclosures: false,  // still one click away — never removed, only not shown first
    canDecide: true,
    canDispute: false,
  },
  auditor: {
    label: 'Auditor',
    question: 'Show me the evidence.',
    lead: 'score',
    expandCategories: true,
    materialOnly: false,
    showReceipts: true,
    showHashes: true,        // the full chain: score → finding → receipt → hash
    // The auditor reconstructs the ABSOLUTE record; peers are interpretation, not evidence, so the
    // benchmark strip is off by default (still reachable by switching role).
    showBenchmark: false,
    showDisclosures: true,
    canDecide: false,        // verifies the record; does not author decisions or disputes
    canDispute: false,
  },
}

export const DEFAULT_ROLE = 'analyst'

const KEY = 'tprm.role'

export function loadRole() {
  try {
    const v = localStorage.getItem(KEY)
    return v && ROLES[v] ? v : DEFAULT_ROLE
  } catch {
    return DEFAULT_ROLE
  }
}

export function saveRole(role) {
  try {
    localStorage.setItem(KEY, role)
  } catch {
    /* a browser refusing storage is not a reason to fail the render */
  }
}
