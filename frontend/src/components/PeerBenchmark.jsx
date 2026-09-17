import { useEffect, useState } from 'react'
import { Users, TrendingUp, TrendingDown, Minus, BarChart3, AlertCircle, ChevronDown } from 'lucide-react'
import { getExpectationGap, getPlacement } from '../api.js'
import { DistributionBox } from './BenchmarkCharts.jsx'
import { Caveats, Disclose } from './primitives.jsx'
import { Card, Badge } from './ui.jsx'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// PEER BENCHMARKING — the v2 system (docs/design_decisions.md Part 1), and the only one drawn.
//
// The screens read `/api/vendors/{ref}/benchmark` until now, which is deprecated server-side and
// cannot express midrank ties, `rank_of_n`, a reproducible cohort snapshot, per-cohort
// discrimination or the dispute path. All of those are rendered here.
//
// `n` TRAVELS WITH EVERY FIGURE. A percentile appears only at n>=30, a quartile only at n>=8,
// and below that this prints the refusal and the actual `n` instead of a number — the refusal IS
// the figure, not a footnote, because the caption does not travel with the screenshot.
//
// TWO FACTS, NOT ONE. Rank (where you sit) and expectation gap (how far from what a supplier of
// this shape is predicted to score) are different questions; a vendor can be mid-quartile in a
// weak cohort and well below expectation. Two blocks, in that order.
//
// PROSE BUDGET. Figures lead. Ladder rationale, per-domain rows, narratives and caveats are all
// closed at rest; the rules that govern how to read a figure are tooltips on it.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function PeerBenchmarkPanel({ vendorRef }) {
  // ONE STATE OBJECT CARRYING THE REF IT DESCRIBES. The obvious shape — three pieces of state
  // plus a `setState('loading')` at the top of the effect — resets by writing state during the
  // effect body, which cascades a render. Tagging the result with its ref means a changed
  // `vendorRef` reads as "not loaded yet" on the very first render, with no reset write at all.
  const [res, setRes] = useState({ ref: null, state: 'loading' })

  useEffect(() => {
    let live = true
    Promise.all([getPlacement(vendorRef), getExpectationGap(vendorRef)])
      .then(([p, g]) => {
        if (live) setRes({ ref: vendorRef, state: p ? 'ready' : 'absent', placement: p, gap: g })
      })
      .catch(() => { if (live) setRes({ ref: vendorRef, state: 'absent' }) })
    return () => { live = false }
  }, [vendorRef])

  const { placement, gap } = res
  const state = res.ref === vendorRef ? res.state : 'loading'

  // "No benchmark" and "benchmark says you are average" look identical from an empty space. Say
  // which — in one line.
  if (state === 'absent') {
    return (
      <Card className="flex items-center gap-2.5 px-5 py-3.5 text-[12px] text-muted-foreground">
        <Users className="h-4 w-4 shrink-0" />
        <span>
          <b className="text-foreground">No peer comparison.</b> No cohort attributes recorded for
          this supplier, so there is no peer group to place it in.
        </span>
      </Card>
    )
  }
  if (state !== 'ready' || !placement) return null

  const a = placement.assignment || {}
  const o = placement.overall || {}

  return (
    <Card className="overflow-hidden">
      <CohortHeader assignment={a} reliability={placement.reliability} />
      <Placement overall={o} distribution={placement.snapshot?.distribution} />
      <ExpectationGap gap={gap} />

      <div className="border-t border-border/60 px-5 py-2">
        <Domains domains={placement.domains} />
        <Narratives placement={placement} />
        <Caveats items={placement.caveats} title="Read this comparison with" />
      </div>
    </Card>
  )
}

// ── the peer group ────────────────────────────────────────────────────────────────────────────

function CohortHeader({ assignment, reliability }) {
  const sb = assignment.size_band || {}
  const ladder = assignment.rationale || []
  const rel = reliability || {}
  const relTone = /high/i.test(rel.band || '') ? 'var(--risk-low)'
    : /low/i.test(rel.band || '') ? 'var(--risk-moderate)' : undefined

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-b border-border/60 bg-gradient-to-r from-secondary/30 to-secondary/10 px-6 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/15 ring-1 ring-accent/30 text-accent">
          <Users className="h-5 w-5" />
        </div>
        <div className="flex flex-col">
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Peer Group
          </div>
          <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
            <span className="font-semibold text-foreground">{assignment.rung_label || assignment.cohort_key || '—'}</span>
            <Badge variant="outline" className="text-xs font-mono">
              n = {assignment.n ?? 0}
            </Badge>
            {sb.band && (
              <span className="text-xs text-muted-foreground"
                title={sb.disagreed
                  ? `Headcount and revenue disagreed on the band; resolved by ${sb.resolve} to ${sb.band}.`
                  : `Size band resolved by ${sb.resolved_by}.`}>
                · size {sb.band}{sb.disagreed ? ' (disputed)' : ''}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {rel.value != null && (
          <Badge className={cn('text-xs', relTone ? 'border-current' : '')}
            style={relTone ? { background: `color-mix(in srgb, ${relTone} 15%, transparent)`, color: relTone } : undefined}
            title={(rel.notes || []).join(' ')}>
            reliability {rel.band} · {Number(rel.value).toFixed(2)}
          </Badge>
        )}
        {assignment.widened && (
          <Badge variant="outline" className="text-xs font-semibold"
            style={{ borderColor: 'var(--risk-moderate)', color: 'var(--risk-moderate)' }}
            title="The exact peer group was too thin, so the cohort was widened. Open the ladder below to see every rung tried.">
            <AlertCircle className="mr-1 h-3 w-3" />
            widened
          </Badge>
        )}
      </div>
      {ladder.length > 0 && (
        <div className="w-full mt-2">
          <Disclose label="How this peer group was chosen">
            <ol className="flex flex-col gap-2">
              {ladder.map((r, i) => (
                <li key={i} className="flex flex-wrap items-center gap-3 rounded-lg bg-secondary/30 px-3 py-2 text-xs">
                  <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-bold',
                    r.satisfied ? 'bg-accent/15 text-accent' : 'bg-muted text-muted-foreground')}>
                    {r.satisfied ? <ChevronDown className="h-4 w-4" /> : <Minus className="h-4 w-4" />}
                  </span>
                  <span className="flex-1 font-semibold">{r.label}</span>
                  <Badge variant="outline" className="font-mono text-xs">n = {r.n ?? 0}</Badge>
                  {r.skipped_reason && <span className="text-muted-foreground">— {r.skipped_reason}</span>}
                </li>
              ))}
            </ol>
          </Disclose>
        </div>
      )}
    </div>
  )
}

// ── where the supplier sits ───────────────────────────────────────────────────────────────────

function Placement({ overall, distribution }) {
  if (!overall || overall.sufficient === false) {
    return (
      <div className="flex items-center gap-3 rounded-xl bg-secondary/30 px-5 py-4 text-sm text-muted-foreground">
        <AlertCircle className="h-5 w-5 shrink-0 text-risk-high" />
        <div>
          <b className="text-foreground">Insufficient peer data.</b>{' '}
          {overall?.reason || `Only ${overall?.n ?? 0} comparable suppliers assessed.`}
        </div>
      </div>
    )
  }

  const delta = overall.delta_from_median
  const below = overall.direction === 'below'

  return (
    <div className="px-6 py-5">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-accent" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">Placement vs Peers</h3>
      </div>

      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3">
        <Tile label="Posture" value={overall.subject}
          hint="This vendor's published posture — the same number as the scorecard." />
        <Tile label="Peer median" value={overall.median} sub={`n = ${overall.n}`} muted
          hint="The midpoint of the cohort, by nearest rank. Not a mean." />
        <Tile
          label="Vs median"
          value={delta == null ? '—' : `${delta > 0 ? '+' : ''}${delta}`}
          sub={delta == null ? undefined
            : below ? 'below the peer group' : delta === 0 ? 'at the median' : 'above the peer group'}
          tone={below ? 'var(--risk-high)' : delta ? 'var(--risk-low)' : undefined}
          icon={below ? <TrendingDown className="h-4 w-4" /> : delta ? <TrendingUp className="h-4 w-4" /> : <Minus className="h-4 w-4" />}
        />
      </div>

      {overall.outlier_low && (
        <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-risk-high/30 bg-risk-high/10 px-3 py-2 text-xs font-semibold text-risk-high">
          <AlertCircle className="h-4 w-4" />
          Outlier — further below the cohort than its own spread
        </div>
      )}

      <div className="mt-5">
        <DistributionBox stats={distribution} posture={overall.subject} />
      </div>
    </div>
  )
}

/** One tile on the placement grid. `fit` shrinks a long word ("bottom quartile") to the tile
 *  rather than letting it set the row height for the three numeric tiles beside it. */
function Tile({ label, value, sub, tone, muted, hint, fit, icon }) {
  return (
    <div className="flex flex-col justify-between bg-card px-4 py-4" title={hint}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </div>
      <div className={cn('mt-2 font-black leading-none tracking-tight tabular-nums',
        fit ? 'text-xl' : 'text-[28px]', muted && 'text-muted-foreground')}
        style={tone ? { color: tone } : undefined}>
        {value ?? '—'}
      </div>
      {/* Reserved even when empty, so the four numbers sit on one baseline. */}
      <div className="mt-2 min-h-[14px] text-[10.5px] leading-tight text-muted-foreground">
        {sub}
      </div>
    </div>
  )
}

// ── E10a: expectation gap ─────────────────────────────────────────────────────────────────────

function ExpectationGap({ gap }) {
  if (!gap) return null

  if (!gap.published) {
    return (
      <div className="border-t border-border/60 px-6 py-4 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div>
            <b className="text-foreground">Expectation gap:</b> {gap.reason || 'not published.'}
          </div>
        </div>
      </div>
    )
  }

  const g = gap.expectation_gap
  const below = gap.direction === 'below'
  const drivers = gap.drivers || []

  return (
    <div className="border-t border-border/60 px-6 py-5">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-accent" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">Expectation Gap</h3>
      </div>

      <div className="rounded-xl border border-border/60 bg-secondary/30 px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <span className="text-3xl font-black leading-none tabular-nums"
            style={{ color: below ? 'var(--risk-high)' : g ? 'var(--risk-low)' : undefined }}>
            {g > 0 ? '+' : ''}{g}
          </span>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>{gap.posture} observed</span>
            <span>·</span>
            <span>{gap.expected_posture} expected</span>
            <span>·</span>
            <Badge variant="outline" className="font-mono text-xs">n = {gap.n}</Badge>
          </div>
        </div>

        {/* THE SENTENCE THIS WHOLE SUBSYSTEM EXISTS TO PRODUCE. "-19" is a fact; "-19, driven by
            DMARC, which 12 of 14 of your own peers publish" is a remediation a buyer can take to
            the vendor without it being our opinion. It earns its standing line. */}
        <p className="mt-3 text-sm leading-relaxed text-foreground">{gap.headline}</p>
      </div>

      {drivers.length > 0 && (
        <div className="mt-4">
          <Disclose label={`What accounts for it · ${drivers.length}`}>
            <ul className="flex flex-col gap-2">
              {drivers.map((d) => (
                <li key={`${d.signal}·${d.band}`} className="flex flex-col gap-1 rounded-lg bg-secondary/30 px-4 py-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-foreground">{d.signal}</span>
                    <span className="font-black tabular-nums text-risk-high">
                      {Number(d.attribution).toFixed(1)} pts
                    </span>
                  </div>
                  <div className="text-muted-foreground">{d.cited}</div>
                </li>
              ))}
              {/* Ranked, not a decomposition: since E7a what a finding costs depends on what else
                  was charged alongside it, so these cannot be made to sum to the gap. */}
              <li className="text-xs italic text-muted-foreground px-4 py-2">
                Ranked by contribution. They do not sum to the gap — what a finding costs depends on
                what else was charged alongside it.
              </li>
            </ul>
          </Disclose>
        </div>
      )}

      {(gap.suppressed_signals || []).length > 0 && (
        <div className="mt-3 rounded-lg bg-secondary/20 px-4 py-2 text-xs text-muted-foreground"
          title="Constant across this cohort, so not comparisons here.">
          Excluded as constants: {gap.suppressed_signals.join(', ')}
        </div>
      )}
      <Caveats items={gap.caveats} title="Read this gap with" />
    </div>
  )
}

// ── per-domain and narratives, closed at rest ─────────────────────────────────────────────────

const DISCRIMINATION = {
  discriminating: { label: 'discriminating', tone: 'var(--risk-low)' },
  non_discriminating: { label: 'peers barely differ', tone: 'var(--ghost)' },
  untested: { label: 'too few peers to test', tone: 'var(--ghost)' },
}

function Domains({ domains }) {
  if (!domains?.length) return null
  return (
    <Disclose label={`By domain · ${domains.length}`}>
      {/* Discrimination sits on every row: a domain where every peer scores 100 cannot rank
          anybody, and presenting a rank among identical values manufactures signal from a
          constant. */}
      <ul className="flex flex-col divide-y divide-border/50">
        {domains.map((d) => {
          const p = d.placement || {}
          const disc = DISCRIMINATION[d.discrimination] || { label: d.discrimination, tone: 'var(--ghost)' }
          const usable = p.sufficient !== false && d.discrimination === 'discriminating'
          return (
            <li key={d.domain} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5 text-[12px]">
              <span className="min-w-[180px] flex-1">
                {d.label || d.domain?.replace(/_/g, ' ')}
                <span className="ml-2 text-[10px]" style={{ color: disc.tone }}>{disc.label}</span>
              </span>
              <span className="tabular-nums">
                <b className={cn(!usable && 'text-muted-foreground')}>{p.subject ?? '—'}</b>
                <span className="ml-2 text-muted-foreground">
                  {p.sufficient === false
                    ? `n = ${p.n ?? 0} · insufficient`
                    : `median ${p.median} · n = ${p.n}`}
                </span>
              </span>
            </li>
          )
        })}
      </ul>
    </Disclose>
  )
}

function Narratives({ placement }) {
  const sec = placement.security_narrative || []
  const proc = placement.procurement_narrative || []
  if (!sec.length && !proc.length) return null

  return (
    // One dataset, two renderings — the same P6 invariant as the export views. Side by side
    // rather than behind a toggle, so neither audience gets facts the other cannot see.
    <Disclose label="Narratives · security and procurement">
      <div className="grid gap-3 md:grid-cols-2">
        <NarrativeBlock title="Security" lines={sec} />
        <NarrativeBlock title="Procurement" lines={proc}>
          {placement.action && (
            <div className="mt-1.5 text-[12px] leading-relaxed">
              <b>Suggested action:</b> {placement.action}
              <div className="text-[10.5px] text-muted-foreground">{placement.action_disclaimer}</div>
            </div>
          )}
        </NarrativeBlock>
      </div>
    </Disclose>
  )
}

function NarrativeBlock({ title, lines, children }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{title}</div>
      <ul className="mt-1 flex flex-col gap-1">
        {lines.map((l, i) => <li key={i} className="text-[12px] leading-relaxed">{l}</li>)}
      </ul>
      {children}
    </div>
  )
}
