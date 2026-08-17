import { useEffect, useState } from 'react'
import {
  ChevronDown, ChevronRight, TriangleAlert, ShieldAlert, FileWarning,
  Sparkles, Loader2, AlertCircle, Download, CheckCircle2, Ban, ClipboardCheck,
} from 'lucide-react'
import { listFindings, summariseVendor, getCapabilities, getExport, getHistory, recordDecision, getDecisions } from './api.js'
import { Card, Badge, Meter, Button } from './components/ui.jsx'
import { PostureConfidencePair } from './components/primitives.jsx'
// `VendorProfilePanel` (firmographics · peer benchmark · target maturity) is imported by
// `pages/VendorPage.jsx` and rendered in its So-what band — see `EvidenceRecord` below.
import { DependenciesPanel } from './components/Dependencies.jsx'
// `cn` was only used by the commented-out RoleSwitcher.
import { postureColor, gradeColor, confColor } from './lib/utils.js'
// Split into their own module (not defined here and re-exported) so this file's fast-refresh
// boundary stays component-only — Vite's react-refresh plugin breaks hot-reload on a module that
// exports both components and plain constants. `ExecutiveSummaryHero.jsx`, `TopFindings.jsx` and
// `EvidenceCoverageBar.jsx` import the same four constants from here too.
import { PRETTY, deSnake, GRADE_MEANING, CONFIDENCE_MEANING } from './lib/labels.js'
// Role-based views temporarily disabled — see FULL_VIEW below.
// import { ROLES, loadRole, saveRole } from './lib/roles.js'

// ROLES ARE OFF: everyone sees the whole record.
//
// This is deliberately the UNION of every role's flags, not one role reused. No single role was
// "everything" — the analyst had `showReceipts` but not `showHashes`, and the auditor had
// `showHashes` but `showBenchmark: false` (peers are interpretation, not evidence). Picking either
// one would have quietly hidden something.
//
// The `view` prop is still threaded through every component exactly as before, so re-enabling
// roles is a small diff: restore the import, restore the RoleSwitcher, and hand the selected role
// back in instead of this constant.
const FULL_VIEW = {
  label: 'Full record',
  lead: 'score',
  expandCategories: true,
  materialOnly: false,      // clean categories shown too — "checked, and fine" is evidence
  showReceipts: true,
  showHashes: true,         // the full chain: score → finding → receipt → hash
  showBenchmark: true,
  benchmarkDepth: 'full',   // full stats · widening path · per-category · charts
  showDisclosures: true,
  canDecide: true,
  canDispute: true,
  // `topFindingsOnly` deliberately left undefined — every finding, never a top-N slice.
}

// Renders the penalty-based POSTURE Score (100 = strongest). Invariants: the confidence
// (coverage) axis is ALWAYS beside the number, and The Ghost / BLOCKED / Insufficient-evidence
// are designed states, not a red number.

// const HELD_CATEGORIES = [
//   ['Supply Chain & Dependency', 'no live free collector yet- re-feed from dns/ct/trust is roadmap'],
//   ['Data Privacy & Leakage', 'no clean free source (HIBP paste/domain is paid)'],
//   ['Geopolitical Footprint', 'needs hosting/jurisdiction enrichment'],
//   ['ESG & Ethical', 'no free authoritative feed'],
//   ['Emerging Tech / AI', 'no observable free signal'],
// ]

// One record, five projections — never five scores. A role changes what is shown FIRST and how
// much is expanded; it never changes what is true, and every view renders from the same response.
// Temporarily unmounted — everyone gets FULL_VIEW.
// function RoleSwitcher({ role, onChange }) {
//   return (
//     <div className="flex flex-wrap items-center gap-1.5 rounded-2xl border border-border/60 bg-secondary/40 p-1 shadow-2xs">
//       <span className="px-2.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
//         View as
//       </span>
//       {Object.entries(ROLES).map(([key, cfg]) => (
//         <button
//           key={key} type="button" onClick={() => onChange(key)}
//           title={cfg.question}
//           className={cn(
//             'rounded-xl px-3 py-1.5 text-xs font-semibold transition-all duration-150 cursor-pointer',
//             key === role
//               ? 'bg-primary text-primary-foreground shadow-xs scale-[1.02]'
//               : 'text-muted-foreground hover:text-foreground hover:bg-secondary/60',
//           )}
//         >
//           {cfg.label}
//         </button>
//       ))}
//     </div>
//   )
// }

function ExportButton({ vendorRef }) {
  const [state, setState] = useState('idle')
  async function run() {
    setState('loading')
    try {
      const pack = await getExport(vendorRef)
      const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `evidence-pack-${vendorRef}-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      setState('idle')
    } catch {
      setState('error')
    }
  }
  return (
    <Button variant="outline" size="sm" onClick={run} disabled={state === 'loading'} className="shadow-2xs">
      <Download className="h-3.5 w-3.5 text-accent" />
      {state === 'loading' ? 'Building…' : state === 'error' ? 'Failed' : 'Evidence pack'}
    </Button>
  )
}

/**
 * THE EVIDENCE RECORD — the deep half of the What band, and NOT a second assessment page.
 *
 * This component used to render the whole record: profile, benchmark, score, categories,
 * dependencies, decisions. That made it a second, independently-maintained React tree for the same
 * score that `/vendors/:ref` also renders — which is the divergence P6's `views_agree()` invariant
 * exists to prevent, reproduced in the client. Two renderers drift, and the day they disagree
 * nobody finds out, because nobody puts them side by side.
 *
 * So its scope is now exactly one thing: **why this number is this number.** Posture and
 * confidence together, the two ceilings kept apart, then category → finding → receipt → hash. The
 * So-what (residual risk) and the Now-what (asks, flow-downs, cadence) belong to the page that
 * embeds this, because they are answers to different questions and were never this card's job.
 *
 * The file keeps its old name so the diff stays readable; the export is `EvidenceRecord`, which
 * says what it is. There is no `Scorecard` alias — nothing imports it any more, and a deprecated
 * name kept for zero callers is dead code carrying a warning.
 */
export function EvidenceRecord({ vendorRef, score }) {
  const view = FULL_VIEW

  // NO FIRMOGRAPHIC / BENCHMARK PANEL HERE. It used to hang off an optional `showProfile` flag
  // that defaulted to false and that no caller ever set, which meant the peer benchmark and the
  // target-maturity gap were built, wired and rendered nowhere. They are INTERPRETATION — "how
  // does this compare, and what should it look like" — not evidence for why the number is the
  // number, so `/vendors/:ref` renders `VendorProfilePanel` in its So-what band instead. One
  // placement, and one that matches what the panel actually says.

  if (score.blocked) {
    return <BlockedCard score={score} />
  }
  if (score.refused) {
    return <RefusedCard score={score} />
  }
  return <ScoredCard vendorRef={vendorRef} score={score} view={view} />
}

export { ExportButton, DependenciesPanel }

// Posture over time — a single point is a grade, a line is a direction. Drawn only when there is
// more than one score on file (a scheduled recheck or a post-dispute re-score wrote another row);
// one run has no trend to show. Confidence is NOT plotted here — it is a separate axis and blending
// the two into one line is exactly the collapse the model refuses everywhere else.
function TrendSparkline({ vendorRef }) {
  const [points, setPoints] = useState(null)
  useEffect(() => {
    let live = true
    getHistory(vendorRef)
      .then((h) => { if (live) setPoints(h) })
      .catch(() => { if (live) setPoints([]) })
    return () => { live = false }
  }, [vendorRef])

  const scored = (points || []).filter((p) => p.posture != null)
  if (scored.length < 2) return null

  const W = 220, H = 40, pad = 4
  const xs = scored.map((_, i) => pad + (i * (W - 2 * pad)) / (scored.length - 1))
  const lo = Math.min(...scored.map((p) => p.posture))
  const hi = Math.max(...scored.map((p) => p.posture))
  const span = Math.max(1, hi - lo)
  const y = (v) => H - pad - ((v - lo) / span) * (H - 2 * pad)
  const path = scored.map((p, i) => `${i ? 'L' : 'M'} ${xs[i].toFixed(1)} ${y(p.posture).toFixed(1)}`).join(' ')
  const first = scored[0].posture, last = scored[scored.length - 1].posture
  const delta = last - first
  const tone = delta < 0 ? 'var(--risk-high)' : delta > 0 ? 'var(--risk-low)' : 'var(--muted-foreground)'

  return (
    <div className="flex items-center gap-3 border-t border-border px-6 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Posture trend
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-9 w-[220px]" role="img"
        aria-label={`Posture over ${scored.length} scores, ${delta >= 0 ? 'up' : 'down'} ${Math.abs(delta)}`}>
        <path d={path} fill="none" stroke={tone} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={xs[xs.length - 1]} cy={y(last)} r="3" fill={tone} stroke="var(--card)" strokeWidth="1.5" />
      </svg>
      <div className="text-[12px]">
        <span className="font-semibold" style={{ color: tone }}>
          {delta > 0 ? `▲ +${delta}` : delta < 0 ? `▼ ${delta}` : '= no change'}
        </span>
        <span className="ml-1.5 text-muted-foreground">over {scored.length} scores</span>
      </div>
    </div>
  )
}

// The procurement/executive ACTION: record a decision on this vendor. It is the "now what?" that a
// score alone never answers. Recorded ALONGSIDE the score (POST /decisions) — it emits no finding
// and moves no number; the posture/grade at the moment of the call are snapshotted so "approved at
// 72 (C)" stays true even after a re-score. A change of mind is a new record, not an edit.
const DECISIONS = [
  { key: 'approve', label: 'Approve', icon: CheckCircle2, tone: 'var(--risk-low, #16a34a)' },
  { key: 'conditional', label: 'Approve with conditions', icon: TriangleAlert, tone: 'var(--risk-med, #d97706)' },
  { key: 'reject', label: 'Reject', icon: Ban, tone: 'var(--risk-high, #dc2626)' },
]

// eslint-disable-next-line no-unused-vars -- temporarily unmounted; kept ready to re-enable
function DecisionBar({ vendorRef }) {
  const [current, setCurrent] = useState(null)   // the latest recorded decision, if any
  const [choice, setChoice] = useState(null)     // a decision being composed
  const [conditions, setConditions] = useState('')
  const [state, setState] = useState('idle')     // idle | sending | error
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    getDecisions(vendorRef).then((d) => live && setCurrent(d?.current || null)).catch(() => {})
    return () => { live = false }
  }, [vendorRef])

  async function submit(kind) {
    if (kind === 'conditional' && !conditions.trim()) { setChoice('conditional'); return }
    setState('sending'); setError(null)
    try {
      const rec = await recordDecision(vendorRef, {
        decision: kind, conditions: kind === 'conditional' ? conditions : undefined,
      })
      setCurrent({ decision: rec.decision, conditions: rec.conditions, posture_at: rec.posture_at,
                   grade_at: rec.grade_at, at: rec.recorded_at })
      setChoice(null); setConditions(''); setState('idle')
    } catch (err) {
      setError(err.message || String(err)); setState('error')
    }
  }

  const meta = current && DECISIONS.find((d) => d.key === current.decision)
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <ClipboardCheck className="h-3.5 w-3.5" /> Decision
      </div>
      <div className="p-5">
        {current && (
          // The current call, stamped with the number it was made on. Shown first so a re-decision
          // is a deliberate override of a visible prior, never a silent overwrite.
          <div className="mb-4 rounded-lg border border-border bg-secondary/40 p-3">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: meta?.tone }}>
              {meta?.icon && <meta.icon className="h-4 w-4" />} {meta?.label || current.decision}
            </div>
            {current.conditions && (
              <div className="mt-1 text-[13px]"><b>Conditions:</b> {current.conditions}</div>
            )}
            <div className="mt-1 text-[11px] text-muted-foreground">
              recorded against posture <b>{current.posture_at ?? '—'}</b>
              {current.grade_at ? ` (${current.grade_at})` : ''} · {current.at ? new Date(current.at).toLocaleString() : ''}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {DECISIONS.map((d) => (
            <Button key={d.key} variant={choice === d.key ? 'default' : 'outline'} size="sm"
              onClick={() => (d.key === 'conditional' ? setChoice('conditional') : submit(d.key))}
              disabled={state === 'sending'}>
              <d.icon className="h-3.5 w-3.5" style={{ color: choice === d.key ? undefined : d.tone }} />
              {d.label}
            </Button>
          ))}
        </div>

        {choice === 'conditional' && (
          <div className="mt-3">
            <textarea value={conditions} onChange={(e) => setConditions(e.target.value)} rows={2}
              placeholder="The terms — e.g. 'remediate the KEV-listed CVE and re-scan before go-live'."
              className="w-full rounded border border-input bg-card p-2 text-[13px]" />
            <div className="mt-2 flex gap-2">
              <Button size="sm" onClick={() => submit('conditional')}
                disabled={state === 'sending' || !conditions.trim()}>
                {state === 'sending' ? 'Recording…' : 'Record conditional approval'}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setChoice(null); setConditions('') }}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {error && <div className="mt-2 text-[12px] text-risk-high">{error}</div>}
        <p className="mt-3 text-[11px] text-muted-foreground">
          The decision is recorded <b>beside</b> the score, stamped with the posture at this moment.
          It changes no number — the model advises; the client decides.
        </p>
      </div>
    </Card>
  )
}

/** One label + one plain sentence. The numbers above are the finding; this is what it means. */
function Meaning({ label, tone, text }) {
  if (!text) return null
  return (
    <div className="rounded-xl border border-border/60 bg-secondary/25 px-3.5 py-2.5">
      <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</div>
      <p className="mt-0.5 text-[12.5px] font-medium leading-relaxed" style={{ color: tone }}>{text}</p>
    </div>
  )
}

function ScoredCard({ vendorRef, score, view = FULL_VIEW }) {
  const conf = score.overall_confidence
  const gcolor = gradeColor(score.grade)

  // The stored signal-level findings- grouped by category, so each row can show WHY it scored:
  // observation -> severity -> penalty, each linked to its raw receipt.
  const [byCategory, setByCategory] = useState({})
  useEffect(() => {
    let live = true
    listFindings(vendorRef)
      .then((rows) => {
        if (!live) return
        const g = {}
        for (const f of rows) (g[f.category] ||= []).push(f)
        setByCategory(g)
      })
      .catch(() => {})
    return () => { live = false }
  }, [vendorRef])

  return (
    <Card className="overflow-hidden shadow-sm">
      {/* ONE IMPLEMENTATION OF THE PAIRING RULE. This used to be two hand-built 24×24 badges here
          and a different pair on the vendor page — the same invariant expressed twice, which is
          twice as many places for it to quietly stop being true. `<PostureConfidencePair>` takes
          `confidence` as a REQUIRED prop, so a bare posture is a build error rather than a
          judgement call. */}
      <div className="px-6 pb-5 pt-6 sm:px-8">
        <PostureConfidencePair
          posture={score.posture} confidence={conf}
          grade={score.grade} band={score.confidence_band}
        />

        {/* The two plain sentences the numbers otherwise leave the reader to supply. */}
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Meaning label="What the grade means" tone={gcolor} text={GRADE_MEANING[score.grade]} />
          <Meaning label="What the confidence means" tone={confColor(conf)}
            text={CONFIDENCE_MEANING[score.confidence_band]} />
        </div>
      </div>

      {score.ghost && (
        <div
          className="border-t border-border/60 px-6 py-3 text-xs"
          style={{ background: 'color-mix(in srgb, var(--ghost) 12%, transparent)', color: 'var(--ghost)' }}
        >
          {/* GHOST USES THE GHOST TOKEN, not a purple literal. It was hardcoded `purple-500`, which
              is the BLOCKED hue — two different states drawn in the same colour, in a UI whose
              whole argument is that "we could not assess this" and "a gate stopped this" are
              different facts. */}
          <b>The Ghost:</b> looks clean only because coverage is thin — read the confidence, not the
          grade alone.
        </div>
      )}

      <Headline score={score} byCategory={byCategory} />

      <TrendSparkline vendorRef={vendorRef} />

      {score.critical_ceiling_applied && (
        <div className="flex items-start gap-2 border-t border-border bg-risk-high/10 px-6 py-3 text-sm text-risk-high">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span><b>Critical ceiling:</b> {score.ceiling_cause || 'a directly-observed critical capped the grade.'}</span>
        </div>
      )}

      {/* TWO DIFFERENT CEILINGS, AND THEY MUST NOT LOOK THE SAME (E7d).
          The critical ceiling above is a statement about the VENDOR — we observed something
          disqualifying, and it is drawn in the risk palette because it is adverse to them. This
          one is a statement about US: we did not see enough to stand behind a number this high.
          Drawing it in the risk palette would let a reader blame the vendor for our coverage, and
          would have the vendor disputing the wrong thing.

          It is shown at all because withholding points silently is the failure mode. A vendor
          whose arithmetic earned 94 and who publishes 80 must not look like a vendor that earned
          80 — the second is a finding about their controls, the first is a limit on our evidence,
          and only one of them is remediable by patching something.

          LIVE JSX, NOT A COMMENT. This block previously sat commented out, which left the ceiling
          binding silently while the string still satisfied the test that guards it — an obligation
          that had lapsed in every way except the one being checked. */}
      {score.confidence_ceiling_applied && (
        <div className="flex items-start gap-2 border-t border-border bg-blocked/10 px-6 py-3 text-sm text-blocked">
          <FileWarning className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <b>Held back by coverage:</b> evidence coverage of {Math.round((score.overall_confidence ?? 0) * 100)}%
            caps what we will publish at <b>{score.confidence_ceiling}</b>. The findings supported a
            higher number; we are not standing behind it on this much evidence. This is a limit on
            <em> our</em> assessment, not a finding against the vendor — more evidence raises it.
          </span>
        </div>
      )}

      <div className="border-t border-border">
        {/* materialOnly (procurement/risk/executive): show only categories that actually cost
            points. A clean category is real evidence ("checked, and fine") the analyst/auditor
            want — but it is noise to a reader deciding whether to sign. Never silent: the count of
            hidden clean categories is stated, and every one is a role-switch away. */}
        {(() => {
          const shown = view.materialOnly
            ? score.categories.filter((c) => (c.penalty ?? 0) > 0)
            : score.categories
          const hiddenClean = score.categories.length - shown.length
          return (
            <>
              {shown.map((c) => (
                <CategoryRow key={c.category} cat={c} findings={byCategory[c.category] || []}
                  view={view} vendorRef={vendorRef} />
              ))}
              {hiddenClean > 0 && (
                <div className="px-6 py-3 text-[11px] italic text-muted-foreground">
                  {hiddenClean} categor{hiddenClean === 1 ? 'y' : 'ies'} with nothing to flag hidden
                  in this view — switch to Security analyst to see every clean pass.
                </div>
              )}
            </>
          )
        })()}
      </div>

      <AiSummary vendorRef={vendorRef} />
    </Card>
  )
}

// What to DO — the answer to "now what?", placed above the breakdown because it is what a
// procurement reader came for. Deterministic: a rule table over grade x confidence x criticality,
// never generated. Labelled advisory, because the client makes the risk decision.
const URGENCY_TONE = {
  stop: 'var(--risk-critical, #b91c1c)',
  act: 'var(--risk-high, #dc2626)',
  assess: 'var(--risk-med, #d97706)',
  routine: 'var(--risk-low, #16a34a)',
}

// eslint-disable-next-line no-unused-vars -- temporarily unmounted; kept ready to re-enable
function RecommendationBanner({ rec, profile }) {
  if (!rec) return null
  const tone = URGENCY_TONE[rec.urgency] || 'inherit'
  return (
    <div className="border-l-4 border-y border-r border-border/60 px-6 py-4 transition-all"
      style={{ borderLeftColor: tone, background: `color-mix(in srgb, ${tone} 8%, transparent)` }}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="text-base font-extrabold tracking-tight" style={{ color: tone }}>{rec.headline}</div>
        <div className="flex items-center gap-2 text-[11px] font-semibold text-muted-foreground">
          {rec.criticality && <Badge className="bg-secondary/70">criticality: {rec.criticality}</Badge>}
          {rec.recheck_after && <Badge className="bg-secondary/70">re-check in {rec.recheck_after}</Badge>}
        </div>
      </div>
      <p className="mt-1.5 max-w-4xl text-xs sm:text-sm leading-relaxed text-foreground/90">{rec.detail}</p>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span><b className="text-foreground">Advisory</b> — the decision is yours; this states what the evidence supports.</span>
        {profile && (
          <span>
            Scored under the <b className="text-foreground">{deSnake(profile).toLowerCase()}</b> profile — severities adjusted.
          </span>
        )}
      </div>
    </div>
  )
}

// Optional AI digest of the finished record. A READ LAYER: it summarizes the score + its
// hash-stamped receipts, it never re-scores and never writes evidence. Hidden entirely when
// the server has no LLM configured (/health → summary_enabled).
function AiSummary({ vendorRef }) {
  // const [enabled, setEnabled] = useState(false)
  const [state, setState] = useState('idle')  // idle | loading | done | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // const [enabledKnown, setEnabledKnown] = useState(false)

  useEffect(() => {
    // let live = true
    getCapabilities()
      // .then((c) => { if (live) { setEnabled(!!c.summary_enabled); setEnabledKnown(true) } })
      // .catch(() => { if (live) setEnabledKnown(true) })
    // return () => { live = false }
  }, [])

  async function run() {
    setState('loading'); setError(null)
    try {
      setResult(await summariseVendor(vendorRef)); setState('done')
    } catch (e) {
      setError(e.message); setState('error')
    }
  }

  return (
    <div className="border-t border-border bg-secondary/30 px-6 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Sparkles className="h-4 w-4 text-accent" />
          AI summary of this record
        </div>
        <Button size="sm" variant="outline" onClick={run} disabled={state === 'loading'}>
          {state === 'loading'
            ? <><Loader2 className="h-4 w-4 animate-spin" /> Summarising…</>
            : <><Sparkles className="h-4 w-4" /> {state === 'done' ? 'Regenerate' : 'Summarise evidence'}</>}
        </Button>
      </div>

      {/* {enabledKnown && !enabled && state === 'idle' && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          No LLM configured on the server- set <span className="font-mono">TPRM_LLM_BASE_URL / _API_KEY / _MODEL</span> to
          enable. The button stays so the feature is discoverable; clicking explains what’s missing.
        </p>
      )} */}

      {state === 'error' && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-risk-high/40 bg-risk-high/10 p-3 text-sm text-risk-high">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {state === 'done' && result && (
        <div className="mt-3 rounded-lg border border-border bg-card p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge style={{ color: 'var(--accent)', background: 'color-mix(in srgb, var(--accent) 14%, transparent)' }}>
              <Sparkles className="h-3 w-3" /> AI-generated
            </Badge>
            {result.model && <span className="font-mono text-[11px] text-muted-foreground">{result.model}</span>}
          </div>
          <div className="whitespace-pre-wrap text-[13px] leading-relaxed text-foreground">{result.summary}</div>
          {/* {result.cited_hashes?.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
              <Receipt className="h-3.5 w-3.5" /> built from receipts:
              {result.cited_hashes.map((h) => (
                <span key={h} className="rounded border border-border bg-secondary px-1.5 py-0.5 font-mono">{h}</span>
              ))}
            </div>
          )} */}
          <p className="mt-3 border-t border-border pt-2 text-[11px] italic text-muted-foreground">{result.disclaimer}</p>
        </div>
      )}
    </div>
  )
}

function CategoryRow({ cat, findings = [], view = FULL_VIEW, vendorRef }) {
  // The role sets the DEFAULT only. Any reader can expand any category and reach the same
  // receipts — a projection changes the starting point, never what is reachable.
  const [open, setOpen] = useState(() => view.expandCategories && (cat.penalty ?? 0) > 0)
  const pct = Math.round((cat.coverage ?? 0) * 100)
  const color = postureColor(cat.posture)
  const hasIssues = (cat.penalty ?? 0) > 0

  return (
    <div className="border-b border-border last:border-b-0 transition-colors hover:bg-secondary/30">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-4 px-6 py-4 text-left transition-all hover:bg-secondary/40 sm:grid-cols-[1fr_auto_150px]"
      >
        <span className="flex items-center gap-2 min-w-0">
          <span className={`transition-transform duration-200 ${open ? 'rotate-90' : ''}`}>
            {open ? <ChevronDown className="h-4 w-4 shrink-0 text-accent" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">{PRETTY[cat.category] || cat.category}</span>
            <span className={`block text-[11px] ${hasIssues ? 'text-muted-foreground' : 'text-risk-low'}`}>
              {cat.posture == null ? 'not covered this run' : hasIssues ? `-${cat.penalty} penalty · ${cat.findings} issue(s)` : 'no issues found'}
            </span>
          </span>
        </span>
        <span
          className={`rounded-lg px-3 py-1.5 text-center font-mono text-sm font-semibold transition-all ${
            hasIssues ? 'shadow-xs' : 'bg-secondary/50'
          }`}
          style={{
            color: cat.posture == null ? 'var(--muted-foreground)' : color,
            background: cat.posture == null ? 'transparent' : `color-mix(in srgb, ${color} 12%, transparent)`,
            minWidth: 70
          }}
        >
          {cat.posture == null ? 'n/a' : `${cat.posture}${cat.grade ? ' ' + cat.grade : ''}`}
        </span>
        <span className="hidden sm:block">
          <Meter value={pct} color={pct >= 80 ? 'var(--risk-low)' : pct >= 50 ? 'var(--risk-med)' : 'var(--risk-high)'} />
          <span className="mt-1 block text-[11px] text-muted-foreground">{pct}% coverage</span>
        </span>
      </button>
      {open && <CategoryDetail cat={cat} findings={findings} view={view} vendorRef={vendorRef} />}
    </div>
  )
}

// Human name for a source id, and a fallback that de-snakes any unmapped key. `deSnake` itself
// comes from `lib/labels.js` now (see the import above).
const SOURCE_LABELS = {
  dns: 'DNS', tls: 'TLS scan', headers: 'HTTP headers', ct: 'Certificate Transparency',
  hibp: 'Have I Been Pwned', kev: 'CISA KEV', nvd: 'NVD', gleif: 'GLEIF', wikidata: 'Wikidata',
  rdap: 'RDAP', regulatory: 'Regulator feeds', trust: 'Trust pages', ita: 'Sanctions list',
}

// Reasons carry a caveat sentence after the headline one ("...This is a name match, not proof").
// The summary takes only the FIRST sentence, or three of them run together become a wall of text.
// const asClause = (s) => {
//   const first = String(s || '').split(/(?<=\.)\s+/)[0] || ''
//   return first.replace(/\.$/, '').replace(/^([A-Z])(?=[a-z])/, (c) => c.toLowerCase())
// }

// The whole answer in one sentence, above the fold. Most readers never expand a category, so the
// three biggest EFFECTIVE deductions have to be right here or they are effectively unpublished.
function Headline({ score, byCategory }) {
  if (score.posture == null) return null
  const top = Object.values(byCategory)
    .flat()
    .filter((f) => (f.effective_penalty ?? 0) > 0 && f.reason)
    .sort((a, b) => (b.effective_penalty ?? 0) - (a.effective_penalty ?? 0))
    .slice(0, 3)

  if (top.length === 0) {
    return (
      <div className="border-t border-border px-6 py-4 text-sm">
        This vendor scored <b>{score.grade}</b> because nothing we could check publicly came back
        as a problem. Read that with the confidence figure, not on its own.
      </div>
    )
  }
  // const clauses = top.map((f) => asClause(f.reason))
  // const joined = clauses.length === 1
  //   ? clauses[0]
  //   : `${clauses.slice(0, -1).join('; ')}; and ${clauses[clauses.length - 1]}`
  // return (
  //   <div className="border-t border-border px-6 py-4 text-sm leading-relaxed">
  //     This vendor scored <b>{score.grade}</b> mainly because {joined}.
  //   </div>
  // )
}

// "checked today" / "March 2021" - the date the evidence PERTAINS to, in words a person reads.
function whenText(f) {
  if (!f.event_date) return 'checked today'
  const d = new Date(f.event_date)
  if (Number.isNaN(d.getTime())) return 'checked today'
  return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

// The sentence that explains an ADJUSTMENT, when the charge differs from the base penalty. This is
// the most defensible thing the model does and it used to be invisible on the card.
function adjustmentText(f) {
  const base = f.penalty ?? 0
  const charged = f.effective_penalty ?? 0
  if (base <= 0) return null
  const n = f.occurrences ?? 1
  // A repeat is only a "pattern" if frequency actually amplified it. A frequency-exempt signal
  // (a bag of keyword-matched CVEs) took its worst instance and nothing more - saying otherwise
  // would describe a calculation that never ran.
  if (n > 1 && f.frequency_amplified) {
    return `Seen ${n} times — counted once as a repeated pattern rather than ${n} times over.`
  }
  if (n > 1) {
    return `${n} matches found — only the most serious one is counted, so a long list of name matches cannot inflate the score.`
  }
  if (charged < base - 0.01) {
    return `This is historic, so it counts for less than a recent finding would — at full weight it would have been −${Math.round(base)}.`
  }
  return null
}

// One deduction, in plain English: what it MEANS, then the technical fact, then WHAT TO DO —
// and where it came from. The action is the half a reader otherwise has to supply themselves,
// which in procurement is where an unactioned amber score becomes a signed contract.
function FindingRow({ f, view = FULL_VIEW }) {
  const charged = Math.round((f.effective_penalty ?? 0) * 10) / 10
  const adjustment = adjustmentText(f)
  const severity = f.severity || 'pass'
  const severityColor = severity === 'critical' ? 'var(--risk-critical)' :
                       severity === 'high' ? 'var(--risk-high)' :
                       severity === 'medium' ? 'var(--risk-med)' :
                       severity === 'low' ? 'var(--risk-low)' : 'var(--muted-foreground)'

  return (
    <div className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 border-t border-border/60 py-3 first:border-t-0 hover:bg-secondary/30 rounded-lg px-2 -mx-2 transition-colors">
      <div className="min-w-0">
        <div className="flex items-start gap-2">
          <div className={`mt-0.5 h-2 w-2 rounded-full shrink-0`} style={{ background: severityColor }} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium text-foreground">{f.reason || deSnake(f.signal)}</div>
            <div className="mt-0.5 text-[12px] text-muted-foreground">{f.observed}</div>
            {adjustment && <div className="mt-1 text-[12px] italic text-muted-foreground">{adjustment}</div>}

            {f.dispute && (
              <div className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-risk-low/15 px-2 py-1 text-[11px] font-medium text-risk-low">
                <CheckCircle2 className="h-3 w-3" />
                {f.dispute === 'nullified'
                  ? 'Refute accepted — does not apply here (penalty removed)'
                  : 'Refute accepted — evidenced remediation (×0.6 applied)'}
              </div>
            )}

            {f.promoted_by && (
              <div className="mt-1 text-[11px] text-risk-med">
                Raised from <b>{f.base_severity}</b> to <b>{f.severity}</b> under the{' '}
                {deSnake(f.promoted_by).toLowerCase()} profile.
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="whitespace-nowrap text-right">
        <div className="font-mono text-[13px] font-semibold" style={{ color: 'var(--risk-high)' }}>
          −{charged}
        </div>
        <div className="mt-0.5 text-[11px] text-muted-foreground">{SOURCE_LABELS[f.source] || deSnake(f.source)} · {whenText(f)}</div>
        {view.showHashes && f.content_hash && (
          <div className="mt-0.5 max-w-[9rem] truncate font-mono text-[10px] text-muted-foreground"
            title={`finding ${f.content_hash}\nevidence ${f.evidence_id || '—'}`}>
            {f.content_hash.slice(0, 12)}…
          </div>
        )}
      </div>
    </div>
  )
}

// The refute route on a single finding. Outside-in scoring systematically over-penalises because it
// cannot see compensating controls; this is how a vendor contests one, with evidence. It NEVER
// changes the score directly — it creates a pending dispute that a human adjudicates.
// function DisputeForm({ f, vendorRef }) {
//   const [open, setOpen] = useState(false)
//   const [kind, setKind] = useState('mitigate')
//   const [evidence, setEvidence] = useState('')
//   const [state, setState] = useState('idle') // idle | sending | done | error
//   const [error, setError] = useState(null)

//   async function send() {
//     if (!evidence.trim()) return
//     setState('sending'); setError(null)
//     try {
//       await submitDispute(vendorRef, { signal: f.signal, band_key: f.band_key, kind, evidence })
//       setState('done')
//     } catch (err) {
//       setError(err.message || String(err)); setState('error')
//     }
//   }

//   if (state === 'done') {
//     return (
//       <div className="mt-1.5 text-[11px] text-risk-low">
//         Dispute submitted — pending human review. It changes no score until accepted.
//       </div>
//     )
//   }
//   if (!open) {
//     return (
//       <button type="button" onClick={() => setOpen(true)}
//         className="mt-1.5 text-[11px] font-medium underline underline-offset-2 text-muted-foreground">
//         Dispute this finding
//       </button>
//     )
//   }
//   return (
//     <div className="mt-1.5 rounded border border-border bg-card p-2">
//       <div className="flex flex-wrap items-center gap-2 text-[11px]">
//         <select value={kind} onChange={(e) => setKind(e.target.value)}
//           className="rounded border border-input bg-card px-1.5 py-0.5">
//           <option value="mitigate">Fixed with evidence (×0.6)</option>
//           <option value="nullify">Does not apply (attribution error)</option>
//         </select>
//         <span className="text-muted-foreground">{f.accepts_as_refute ? `Closes with: ${f.accepts_as_refute}` : ''}</span>
//       </div>
//       <textarea
//         value={evidence} onChange={(e) => setEvidence(e.target.value)}
//         placeholder="Evidence — a SOC 2 reference, a patch log, or why this finding is misattributed."
//         rows={2}
//         className="mt-1.5 w-full rounded border border-input bg-card p-1.5 text-[11px]"
//       />
//       {error && <div className="mt-1 text-[11px] text-risk-high">{error}</div>}
//       <div className="mt-1.5 flex gap-2">
//         <Button size="sm" onClick={send} disabled={state === 'sending' || !evidence.trim()}>
//           {state === 'sending' ? 'Submitting…' : 'Submit dispute'}
//         </Button>
//         <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
//       </div>
//     </div>
//   )
// }

function CategoryDetail({ cat, findings = [], view = FULL_VIEW, vendorRef }) {
  // Only findings that actually COST something get a row - a clean pass has nothing to explain.
  // The per-row source and date carry the provenance, so the old "Sources checked" chip list is
  // gone: it repeated the same information one level less precisely.
  const all = findings
    .filter((f) => (f.effective_penalty ?? 0) > 0)
    .sort((a, b) => (b.effective_penalty ?? 0) - (a.effective_penalty ?? 0))
  // An executive gets the few findings that drove the score, not all nine. The rest are one
  // role-switch away, and the count is stated so nothing looks hidden.
  const issues = view.topFindingsOnly ? all.slice(0, view.topFindingsOnly) : all
  const hasIssues = issues.length > 0

  return (
    <div className="bg-secondary/40 px-6 pb-5 pt-2 text-sm text-muted-foreground">
      <div className="mb-3 flex flex-wrap gap-x-6 gap-y-1.5 rounded-lg bg-card/50 px-4 py-2.5 border border-border/50">
        <span className="flex items-center gap-1.5">
          <span className="text-xs uppercase tracking-wider text-muted-foreground">posture</span>
          <b className="text-foreground text-sm">{cat.posture ?? '—'}{cat.grade ? ` (${cat.grade})` : ''}</b>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-xs uppercase tracking-wider text-muted-foreground">penalty</span>
          <b className="text-foreground text-sm">-{cat.penalty ?? 0}</b>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-xs uppercase tracking-wider text-muted-foreground">coverage</span>
          <b className="text-foreground text-sm">{Math.round((cat.coverage ?? 0) * 100)}%</b>
        </span>
        {cat.posture == null && (
          <span className="flex items-center gap-1.5 text-ghost text-xs">
            <FileWarning className="h-3 w-3" />
            absent- costs confidence, not posture
          </span>
        )}
      </div>

      {hasIssues && (
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Why it lost {Math.round(cat.penalty)} points
          </div>
          {issues.map((f) => <FindingRow key={f.id} f={f} view={view} vendorRef={vendorRef} />)}
          {all.length > issues.length && (
            <div className="mt-2 rounded-lg border border-border/60 bg-secondary/50 px-3 py-2 text-[11px] italic text-muted-foreground">
              {all.length - issues.length} further finding(s) not shown in this view — switch to
              Security analyst to see all of them.
            </div>
          )}
        </div>
      )}
      {!hasIssues && (
        <div className="rounded-lg border border-risk-low/30 bg-risk-low/10 px-4 py-3 text-[13px] text-risk-low">
          {cat.posture == null
            ? 'Not covered this run.'
            : 'Everything we could check here came back clean.'}
        </div>
      )}
    </div>
  )
}

function BlockedCard({ score }) {
  return (
    <Card className="overflow-hidden">
      <div className="p-6">
        <Badge className="text-white" style={{ background: 'var(--blocked)' }}>
          <ShieldAlert className="h-3.5 w-3.5" /> Blocked- human adjudication required
        </Badge>
        <h3 className="mt-4 text-lg font-semibold">This vendor is not auto-scored.</h3>
        <p className="mt-1.5 text-sm text-muted-foreground">{score.blocked_reason}</p>
        <p className="mt-3 text-sm text-muted-foreground">
          A sanctions/watchlist match or an ambiguous entity blocks <em>before</em> any score is formed- the
          model emits nothing (it does NOT grade the vendor F) rather than let a fuzzy match quietly move a
          number. Under the Autonomous Sanctions Act s&nbsp;16(7) the human adjudication is itself the evidence.
        </p>
      </div>
    </Card>
  )
}

// INSUFFICIENT EVIDENCE IS AN ADVERSE RESULT, AND IT HAS TO LOOK LIKE ONE (E7d).
//
// This card used to render a grey `bg-secondary` badge — the same neutral chrome the UI uses for
// "not applicable" and "no data yet". Grey is the visual language of *nothing happened*, and a
// reader skimming a portfolio reads it as an incomplete row rather than a result. That is the
// precise misreading the whole Ghost mechanic exists to prevent: a vendor that returns almost
// nothing to public OSINT is not a vendor awaiting assessment, it is a vendor we could not
// assess, and treating those two the same is what makes HIDING BETTER THAN BEING AVERAGE.
//
// Drawn in the amber/high-risk register rather than the critical one, deliberately. We are not
// claiming the vendor is bad — we have no evidence either way, which is the point. We are claiming
// the RESULT is adverse and must not be cleared past on a skim.
function RefusedCard({ score }) {
  return (
    <Card className="overflow-hidden border-risk-high/40">
      <div className="border-b-2 border-risk-high/50 bg-risk-high/10 p-6">
        <Badge className="text-white" style={{ background: 'var(--risk-high)' }}>
          <FileWarning className="h-3.5 w-3.5" /> Insufficient evidence — adverse result
        </Badge>
        <h3 className="mt-4 text-lg font-semibold">We won’t publish a grade we can’t stand behind.</h3>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Evidence coverage {Math.round(score.overall_confidence * 100)}% is below the floor. This vendor is a
          <b className="text-foreground"> Ghost</b>: it would look clean only because public OSINT returned little-
          not the same as being safe. A designed refusal, not an error.
        </p>
        <p className="mt-3 text-sm font-medium text-risk-high">
          Treat this as an adverse finding, not a blank. A supplier that is unassessable from
          outside is a supplier whose controls nobody outside has been able to check — the correct
          next step is to request evidence directly, not to wait for a number.
        </p>
      </div>
    </Card>
  )
}

// Coverage limits, held-source gaps and attribution — stated ON the card, because claiming
// completeness we do not have is the misrepresentation the product exists to avoid.
//
// FETCHED, NOT HARDCODED. Two of these are obligations rather than editorial choices: the NVD
// notice is required wording, and HIBP's licence requires attribution wherever its data appears
// (methodology §10 — "UI requirements, not footnotes to add later"). Serving them from
// `/api/disclosures` means the card and the evidence pack read the same text, and a missing one
// is a backend test failure rather than a rendering accident. This block was previously written
// as literal JSX and then commented out, which is exactly how an obligation quietly lapses.
