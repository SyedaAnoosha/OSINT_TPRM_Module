import { useEffect, useState } from 'react'
import {
  Building2, Globe, Minus, ShieldQuestion, TrendingDown, TrendingUp,
} from 'lucide-react'
import { getAssurity, getHistory } from '../api.js'
import { GRADE_MEANING } from '../lib/labels.js'
import { BusinessStabilityBadge } from './BusinessStabilityCard.jsx'
import { GhostState, InherentResidualPair } from './primitives.jsx'
import { confColor, gradeColor, postureColor } from '../lib/utils.js'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// TIER 1 — THE GLANCE ROW. docs/tprm_feedback_redesign.md §3.2/§3.3/§3.4.
//
// Everything a stakeholder needs without scrolling or clicking: vendor identity, overall grade,
// posture + trend, confidence, assurance, Business Stability, and the inherent→residual pair.
// Composes existing axis components (`InherentResidualPair`, `BusinessStabilityBadge`) rather
// than redrawing them — a second implementation of "what colour is a residual tier" is exactly
// the drift `views_agree()` exists to prevent, and that discipline should not stop at the door
// of a new component.
//
// DEGRADES TILE-BY-TILE, NOT AS A WHOLE ROW. A vendor with no Continuity coverage still has a
// posture; a blocked vendor still has a Business Stability standing. Losing one axis must not
// take the others down — this is the same "ten independent reads" ethos `VendorPage.jsx`
// documents for its bands, applied one level down to the tiles inside a single row.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function ExecutiveSummaryHero({ ref_, score, profile, plan, continuity, residual, provisional }) {
  const domain = profile?.domain || score?.domain
  const lastScored = score?.computed_at ? new Date(score.computed_at) : null

  return (
    <header className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm md:sticky md:top-0 md:z-20 md:backdrop-blur md:bg-card/95">
      {/* identity row */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/60 px-5 py-4 sm:px-6">
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">
            {profile?.legal_name?.value || ref_}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
            <span className="font-mono">{ref_}</span>
            {domain && <><span>·</span><span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />{domain}</span></>}
            {profile?.sector?.value && <><span>·</span><span className="inline-flex items-center gap-1"><Building2 className="h-3 w-3" />{profile.sector.value}</span></>}
            <span>·</span>
            <span>Last scored: {lastScored ? lastScored.toLocaleDateString() : '—'}</span>
          </div>
        </div>
        {plan && (
          <div className="rounded-xl border border-border bg-secondary/30 px-3.5 py-2 text-right">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Assessment plan
            </div>
            <div className="text-[13px] font-semibold">{plan.tier_label}</div>
            <div className="text-[11px] text-muted-foreground">
              {plan.collection?.depth} depth · {plan.review_cadence?.label?.toLowerCase()}
            </div>
          </div>
        )}
      </div>

      {/* the tile strip */}
      <div className="grid grid-cols-2 gap-px bg-border/60 sm:grid-cols-3 lg:grid-cols-6">
        {score?.blocked ? (
          <div className="col-span-2 bg-card p-4 sm:col-span-3 lg:col-span-3">
            <GhostState kind="blocked" />
          </div>
        ) : score?.refused || score?.posture == null ? (
          <div className="col-span-2 bg-card p-4 sm:col-span-3 lg:col-span-3">
            <GhostState kind="refused" confidence={score?.overall_confidence} />
          </div>
        ) : (
          <>
            <GradeTile grade={score.grade} />
            <PostureTile ref_={ref_} posture={score.posture} />
            <ConfidenceTile confidence={score.overall_confidence} band={score.confidence_band} ghost={score.ghost} />
          </>
        )}
        <AssurityTile vendorRef={ref_} />
        <div className="flex flex-col justify-center bg-card px-4 py-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Business Stability
          </div>
          <div className="mt-1.5">
            {continuity
              ? <BusinessStabilityBadge standing={continuity.standing} />
              : <span className="text-[12px] text-muted-foreground">—</span>}
          </div>
        </div>
        <div className="flex flex-col justify-center bg-card px-4 py-3">
          <InherentResidualPair residual={residual} provisional={provisional} />
        </div>
      </div>
    </header>
  )
}

function GradeTile({ grade }) {
  const tone = gradeColor(grade)
  return (
    <div className="flex flex-col justify-center bg-card px-4 py-3" title={GRADE_MEANING[grade]}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        Overall
      </div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-3xl font-black leading-none" style={{ color: tone }}>{grade}</span>
      </div>
      <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{GRADE_MEANING[grade]}</div>
    </div>
  )
}

// Trend arrow — the compact companion to `TrendSparkline` in Scorecard.jsx. That component draws
// the full line for the Tier-3 Category Detail tab; this tile only needs the direction and the
// delta, so it fetches the same history independently rather than threading the line's data down
// through a prop only one of the two callers uses.
function PostureTile({ ref_, posture }) {
  const [delta, setDelta] = useState(null)
  useEffect(() => {
    let live = true
    getHistory(ref_)
      .then((points) => {
        if (!live) return
        const scored = (points || []).filter((p) => p.posture != null)
        if (scored.length < 2) return
        setDelta(scored[scored.length - 1].posture - scored[0].posture)
      })
      .catch(() => {})
    return () => { live = false }
  }, [ref_])

  const tone = postureColor(posture)
  return (
    <div className="flex flex-col justify-center bg-card px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        Posture
      </div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-3xl font-black leading-none tabular-nums" style={{ color: tone }}>{posture}</span>
        <span className="text-[12px] text-muted-foreground">/100</span>
      </div>
      {delta != null && (
        <div className="mt-0.5 flex items-center gap-1 text-[11px] font-semibold"
          style={{ color: delta > 0 ? 'var(--risk-low)' : delta < 0 ? 'var(--risk-high)' : 'var(--muted-foreground)' }}>
          {delta > 0 ? <TrendingUp className="h-3 w-3" /> : delta < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
          {delta > 0 ? `+${delta}` : delta}
        </div>
      )}
    </div>
  )
}

function ConfidenceTile({ confidence, band, ghost }) {
  const pct = Math.round((confidence ?? 0) * 100)
  const tone = confColor(confidence)
  return (
    <div className="flex flex-col justify-center bg-card px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        Confidence
      </div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-3xl font-black leading-none tabular-nums" style={{ color: tone }}>{pct}</span>
        <span className="text-[12px] text-muted-foreground">%</span>
      </div>
      <div className={cn('mt-0.5 text-[11px]', ghost && 'font-semibold')} style={ghost ? { color: 'var(--ghost)' } : undefined}>
        {ghost ? <><ShieldQuestion className="mr-0.5 inline h-3 w-3" />Ghost — thin coverage</> : band}
      </div>
    </div>
  )
}

// Self-contained, same pattern as `AssurancePanel` — an independent read that degrades to an
// absent tile on its own rather than blocking or blanking the rest of the row.
function AssurityTile({ vendorRef }) {
  const [res, setRes] = useState({ ref: null })
  useEffect(() => {
    let live = true
    getAssurity(vendorRef).then((d) => { if (live) setRes({ ref: vendorRef, data: d }) }).catch(() => { if (live) setRes({ ref: vendorRef }) })
    return () => { live = false }
  }, [vendorRef])
  const data = res.ref === vendorRef ? res.data : null
  const score = data?.published ? data.assurity : null
  return (
    <div className="flex flex-col justify-center bg-card px-4 py-3"
      title="Independent assurance, not security — absence never subtracts, and this never adds to posture.">
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        Assurity
      </div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-3xl font-black leading-none tabular-nums" style={score == null ? { color: 'var(--ghost)' } : undefined}>
          {score ?? 'n/a'}
        </span>
        {score != null && <span className="text-[12px] text-muted-foreground">/100</span>}
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">
        {(data?.compliance_gaps || []).length > 0
          ? `${data.compliance_gaps.length} compliance gap${data.compliance_gaps.length === 1 ? '' : 's'}`
          : score == null ? 'unevidenced' : 'no gaps observed'}
      </div>
    </div>
  )
}
