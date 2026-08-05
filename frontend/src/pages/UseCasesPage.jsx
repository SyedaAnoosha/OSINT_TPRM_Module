import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Award, Ban, Fingerprint, Ghost as GhostIcon, Loader2, Mail, ShieldAlert, ShieldCheck,
} from 'lucide-react'
import { getAssurity, getContinuity, getPortfolio, getScore } from '../api.js'
import { GhostState, PostureConfidencePair } from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'
import { postureColor } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// Use cases — the nine differentiating scenarios from docs/vendor_comparison_scenarios.md,
// shown live against two REAL vendors from the book, not synthetic fixtures.
//
// THE ONE RULE THIS PAGE FOLLOWS: every figure on it is fetched, never invented. Where two
// chosen vendors happen not to differ on an axis (neither has a Business Stability flag, say),
// this page says so plainly — it does not manufacture contrast, and it never attaches a
// hypothetical condition (bankrupt, sanctioned) to a real vendor's name. Scenarios that need a
// condition no vendor in this book currently has (a sanctions match, a bankruptcy filing) are
// shown as a worked example with clearly labelled synthetic figures, kept visually and textually
// apart from the live comparison above it.
// ═══════════════════════════════════════════════════════════════════════════════════════════

const CAT = {
  breach: 'breach_compromise_history',
  hygiene: 'attack_surface_hygiene',
  email: 'identity_email',
  compliance: 'compliance_regulatory',
}

export default function UseCasesPage() {
  const [state, setState] = useState({ loading: true })
  const [refA, setRefA] = useState('')
  const [refB, setRefB] = useState('')

  useEffect(() => {
    let alive = true
    getPortfolio()
      .then((portfolio) => {
        if (!alive) return
        const rows = portfolio?.vendors || portfolio?.rows || []
        setState({ loading: false, rows })
        if (rows.length >= 2) { setRefA(rows[0].vendor_ref); setRefB(rows[1].vendor_ref) }
        else if (rows.length === 1) { setRefA(rows[0].vendor_ref) }
      })
      .catch((e) => alive && setState({ loading: false, error: e.message }))
    return () => { alive = false }
  }, [])

  if (state.loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading the book…
      </div>
    )
  }
  if (state.error) {
    return <Card className="p-6 text-sm text-muted-foreground">{state.error}</Card>
  }
  if (!state.rows.length) {
    return (
      <Card className="p-6">
        <p className="text-sm text-muted-foreground">
          No scored vendors yet. <Link to="/assess" className="font-semibold text-accent hover:underline">Score one</Link>,
          then a second, to compare them here.
        </p>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Use cases</h1>
        <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-muted-foreground">
          Nine scenarios the scoring model is built to get right, demonstrated live against two
          real vendors from the book — pick any two below. Every figure here is fetched from the
          same score a vendor page would show; nothing is staged. The full write-up with reasoning
          for each scenario is in{' '}
          <span className="font-mono text-[11.5px]">docs/vendor_comparison_scenarios.md</span>.
        </p>
      </header>

      <VendorPickers rows={state.rows} refA={refA} refB={refB} setRefA={setRefA} setRefB={setRefB} />

      {refA && refB && refA !== refB
        ? <Comparison refA={refA} refB={refB} />
        : refA && refB && refA === refB
          ? <Card className="p-5 text-sm text-muted-foreground">Pick two different vendors to compare.</Card>
          : null}

      <SyntheticExamples />
    </div>
  )
}

function VendorPickers({ rows, refA, refB, setRefA, setRefB }) {
  return (
    <Card className="flex flex-wrap items-center gap-4 p-4">
      <Picker label="Vendor A" rows={rows} value={refA} onChange={setRefA} />
      <span className="text-sm text-muted-foreground">vs.</span>
      <Picker label="Vendor B" rows={rows} value={refB} onChange={setRefB} />
    </Card>
  )
}

function Picker({ label, rows, value, onChange }) {
  return (
    <label className="flex items-center gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <select
        value={value} onChange={(e) => onChange(e.target.value)}
        className="h-10 rounded-xl border border-input bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
      >
        {rows.map((r) => <option key={r.vendor_ref} value={r.vendor_ref}>{r.vendor_ref}</option>)}
      </select>
    </label>
  )
}

// ── the live comparison ───────────────────────────────────────────────────────────────────

// One vendor's bundle, or a stated failure — never thrown past this point. `getScore` is the
// one call in the trio that rejects (`getContinuity`/`getAssurity` already degrade to null); a
// vendor whose score 404s (a real, observed case in this book) must not blank the vendor BESIDE
// it that loaded fine, matching VendorPage's own "ten independent reads, one bad read must not
// take the other nine down" rule.
async function loadVendorBundle(ref) {
  try {
    const [score, continuity, assurity] = await Promise.all([
      getScore(ref), getContinuity(ref), getAssurity(ref),
    ])
    return { ref, ok: true, score, continuity, assurity }
  } catch (e) {
    return { ref, ok: false, error: e.message }
  }
}

function Comparison({ refA, refB }) {
  const [state, setState] = useState({ refA: null, refB: null })

  useEffect(() => {
    let alive = true
    Promise.all([loadVendorBundle(refA), loadVendorBundle(refB)]).then(([a, b]) => {
      if (alive) setState({ refA, refB, a, b })
    })
    return () => { alive = false }
  }, [refA, refB])

  // Stale-guard, not a `loading` flag: `refA`/`refB` on state must match the props, or a fast
  // picker change would briefly show the previous pair's data under the new pair's labels — and
  // until they match, this IS the loading state, without a synchronous setState in the effect.
  if (state.refA !== refA || state.refB !== refB) {
    return (
      <div className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading {refA} vs {refB}…
      </div>
    )
  }

  const { a, b } = state
  if (!a.ok && !b.ok) {
    return (
      <Card className="p-6 text-sm text-muted-foreground">
        Neither vendor could be loaded — {a.error}. Pick different vendors.
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <ScenarioCard n={1} icon={ShieldAlert} title="Breach & compromise history"
        detail="Confirmed breaches and actively-exploited (KEV-listed) vulnerabilities associated with the vendor.">
        <CategoryPair refA={refA} refB={refB} a={a} b={b} category={CAT.breach} />
      </ScenarioCard>

      <ScenarioCard n={2} icon={Fingerprint} title="Business Stability"
        detail="Registry-cited going-concern and insolvency facts — Companies House, GLEIF, The Gazette, SEC EDGAR, CourtListener. Disclosed, never scored: identical on Posture no matter what this row shows.">
        <BusinessStabilityPair refA={refA} refB={refB} a={a} b={b} />
      </ScenarioCard>

      <ScenarioCard n={3} icon={Mail} title="Email security"
        detail="DMARC, SPF and DKIM — can someone send email pretending to be this vendor?">
        <CategoryPair refA={refA} refB={refB} a={a} b={b} category={CAT.email} />
      </ScenarioCard>

      <ScenarioCard n={4} icon={ShieldCheck} title="Attack surface & certificate hygiene"
        detail="TLS/certificate configuration, security headers, DNS hardening. An expired production certificate caps this category's vendor at posture 49 regardless of anything else — a knockout, not a deduction.">
        <CategoryPair refA={refA} refB={refB} a={a} b={b} category={CAT.hygiene} />
      </ScenarioCard>

      <ScenarioCard n={5} icon={GhostIcon} title="Evidence coverage — the Ghost"
        detail="A clean-looking posture on thin evidence is flagged, not celebrated. Confidence is never folded into Posture.">
        <CoveragePair refA={refA} refB={refB} a={a} b={b} />
      </ScenarioCard>

      <ScenarioCard n={6} icon={Award} title="Independent assurance"
        detail="How much independently-verifiable assurance (audited controls, corroborated certifications) each vendor actually has. A different axis from Posture — never added to it, and absence never subtracts.">
        <AssurancePair refA={refA} refB={refB} a={a} b={b} />
      </ScenarioCard>

      <ScenarioCard n={7} icon={Ban} title="Regulatory action & blocked records"
        detail="A formal enforcement action is a scored penalty and still publishes. A sanctions-list match is a hard gate — no score at all, pending human adjudication.">
        <CategoryPair refA={refA} refB={refB} a={a} b={b} category={CAT.compliance} showBlocked />
      </ScenarioCard>
    </div>
  )
}

function ScenarioCard({ n, icon: Icon, title, detail, children }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-start gap-3 border-b border-border/60 px-5 py-4">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent/12">
          <Icon className="h-4 w-4 text-accent" />
        </span>
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[11px] font-bold text-muted-foreground">
              {String(n).padStart(2, '0')}
            </span>
            <h3 className="text-sm font-bold">{title}</h3>
          </div>
          <p className="mt-0.5 max-w-3xl text-[12px] leading-relaxed text-muted-foreground">{detail}</p>
        </div>
      </div>
      <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">{children}</div>
    </Card>
  )
}

function VendorCell({ label, error, children }) {
  return (
    <div className="rounded-xl border border-border/60 bg-secondary/25 px-4 py-3">
      <div className="font-mono text-[11px] font-bold text-muted-foreground">{label}</div>
      <div className="mt-1.5">
        {error
          ? <span className="text-[12px] text-muted-foreground">could not load — {error}</span>
          : children}
      </div>
    </div>
  )
}

function CategoryPair({ refA, refB, a, b, category, showBlocked }) {
  const catA = a.ok && a.score.categories?.find((c) => c.category === category)
  const catB = b.ok && b.score.categories?.find((c) => c.category === category)
  return (
    <>
      <VendorCell label={refA} error={!a.ok && a.error}>
        {a.ok && (showBlocked && a.score.blocked
          ? <BlockedNote reason={a.score.blocked_reason} />
          : <CategoryFigure cat={catA} />)}
      </VendorCell>
      <VendorCell label={refB} error={!b.ok && b.error}>
        {b.ok && (showBlocked && b.score.blocked
          ? <BlockedNote reason={b.score.blocked_reason} />
          : <CategoryFigure cat={catB} />)}
      </VendorCell>
    </>
  )
}

function CategoryFigure({ cat }) {
  if (!cat || cat.posture == null) {
    return <span className="text-[12px] italic text-muted-foreground">not covered</span>
  }
  return (
    <div>
      <span className="text-2xl font-bold tabular-nums" style={{ color: postureColor(cat.posture) }}>
        {cat.posture}
      </span>
      <span className="ml-2 text-[11px] text-muted-foreground">
        {cat.findings} finding{cat.findings === 1 ? '' : 's'} · {Math.round((cat.coverage || 0) * 100)}% coverage
      </span>
      {cat.posture <= 49 && (
        <div className="mt-1 text-[11px] font-semibold" style={{ color: 'var(--risk-critical)' }}>
          at or below the critical-ceiling cap (49)
        </div>
      )}
    </div>
  )
}

function BlockedNote({ reason }) {
  return (
    <div className="flex items-start gap-2">
      <Ban className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--blocked)' }} />
      <div>
        <div className="text-[12.5px] font-bold" style={{ color: 'var(--blocked)' }}>No score — blocked</div>
        <p className="mt-0.5 text-[11.5px] text-muted-foreground">{reason || 'a gate stopped this assessment.'}</p>
      </div>
    </div>
  )
}

const STANDING_TONE = {
  sound: 'var(--risk-low)', watch: 'var(--risk-moderate)', impaired: 'var(--risk-high)',
  ceased: 'var(--risk-critical)', unknown: 'var(--ghost)',
}

function BusinessStabilityPair({ refA, refB, a, b }) {
  return (
    <>
      <VendorCell label={refA} error={!a.ok && a.error}>
        {a.ok && <StandingFigure continuity={a.continuity} />}
      </VendorCell>
      <VendorCell label={refB} error={!b.ok && b.error}>
        {b.ok && <StandingFigure continuity={b.continuity} />}
      </VendorCell>
    </>
  )
}

function StandingFigure({ continuity }) {
  const standing = continuity?.standing || 'unknown'
  const bsc = continuity?.business_stability_coverage
  return (
    <div>
      <span className="text-sm font-bold capitalize" style={{ color: STANDING_TONE[standing] }}>
        {standing.replace(/_/g, ' ')}
      </span>
      {bsc && (
        <div className="mt-1 text-[11px] text-muted-foreground">
          {bsc.answered} of {bsc.tracked} Business Stability checks
        </div>
      )}
    </div>
  )
}

function CoveragePair({ refA, refB, a, b }) {
  return (
    <>
      <VendorCell label={refA} error={!a.ok && a.error}>
        {a.ok && <PostureConfidencePair {...pcp(a.score)} size="sm" />}
      </VendorCell>
      <VendorCell label={refB} error={!b.ok && b.error}>
        {b.ok && <PostureConfidencePair {...pcp(b.score)} size="sm" />}
      </VendorCell>
    </>
  )
}

function pcp(score) {
  return {
    posture: score.posture, confidence: score.overall_confidence, grade: score.grade,
    band: score.confidence_band, refused: score.refused, blocked: score.blocked,
  }
}

function AssurancePair({ refA, refB, a, b }) {
  return (
    <>
      <VendorCell label={refA} error={!a.ok && a.error}>
        {a.ok && <AssuranceFigure data={a.assurity} />}
      </VendorCell>
      <VendorCell label={refB} error={!b.ok && b.error}>
        {b.ok && <AssuranceFigure data={b.assurity} />}
      </VendorCell>
    </>
  )
}

function AssuranceFigure({ data }) {
  if (!data) return <span className="text-[12px] italic text-muted-foreground">not available</span>
  const score = data.published ? data.assurity : null
  return (
    <div>
      <span className="text-2xl font-bold tabular-nums" style={score == null ? { color: 'var(--ghost)' } : undefined}>
        {score ?? 'n/a'}
      </span>
      {score != null && <span className="ml-1 text-[11px] text-muted-foreground">/ 100</span>}
      <div className="mt-1 text-[11px] text-muted-foreground">
        {(data.compliance_gaps || []).length} compliance gap{(data.compliance_gaps || []).length === 1 ? '' : 's'}
      </div>
    </div>
  )
}

// ── synthetic worked examples — clearly labelled, never attached to a real vendor ──────────

function SyntheticExamples() {
  return (
    <Card className="overflow-hidden border-dashed">
      <div className="border-b border-border/60 bg-secondary/30 px-5 py-3">
        <h3 className="text-sm font-bold">Two scenarios no vendor in this book currently illustrates</h3>
        <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-muted-foreground">
          A sanctions-list match and a bankruptcy filing are rare by design — most vendors never
          trigger either. Rather than wait for a real one or imply that a real company has a
          condition it does not, these two are shown as worked examples with clearly synthetic
          figures. The full test coverage for both is in{' '}
          <span className="font-mono text-[11.5px]">backend/tests/test_vendor_comparison_scenarios.py</span>.
        </p>
      </div>
      <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">
        <div className="rounded-xl border border-dashed border-border px-4 py-3">
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            Worked example — sanctions gate
          </div>
          <p className="mt-1.5 text-[12.5px] leading-relaxed">
            A possible sanctions-list match blocks the record entirely — rendered below in place of
            any posture, pending human adjudication. It is never scored as a Grade F.
          </p>
          <div className="mt-2">
            <GhostState kind="blocked" />
          </div>
        </div>
        <div className="rounded-xl border border-dashed border-border px-4 py-3">
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            Worked example — bankruptcy filing
          </div>
          <p className="mt-1.5 text-[12.5px] leading-relaxed">
            A synthetic vendor with an identical cyber posture to a healthy peer, differing only in
            a <span className="font-semibold capitalize" style={{ color: STANDING_TONE.ceased }}>ceased</span>{' '}
            Business Stability standing (a Gazette winding-up notice). Posture and Confidence are
            byte-identical between the two — see scenario 2 in the comparison scenarios doc.
          </p>
        </div>
      </div>
    </Card>
  )
}
