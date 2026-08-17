import { useState, useEffect } from 'react'
import {
  Boxes, FileSearch2, Layers, Network, Scale, ShieldCheck, Sparkles, Clock
} from 'lucide-react'
import { EvidenceRecord, ExportButton } from '../Scorecard.jsx'
import { cn } from '../lib/utils.js'
import { AssurancePanel } from './Assurance.jsx'
import { BusinessStabilityCard } from './BusinessStabilityCard.jsx'
import { DependenciesPanel } from './Dependencies.jsx'
import { GapAnalysisPanel } from './GapAnalysis.jsx'
import { PeerBenchmarkPanel } from './PeerBenchmark.jsx'
import { ActionCard, Caveats, ProvisionalChip, RiskBand } from './primitives.jsx'
// import { LifecycleCard } from './LifecycleCard.jsx'
import { getStability, getFinancial } from '../api.js'


// ═══════════════════════════════════════════════════════════════════════════════════════════
// TIER 3 — DRILL-DOWN, ON DEMAND. docs/tprm_feedback_redesign.md §3.2/§3.3/§3.4:
// "Existing components, reorganized under tabs/accordion rather than a single long scroll."
//
// `<VendorDetailTabs>` is a wrapper only — none of the panels it renders changed internally, per
// §3.4 ("no changes to those components' internals required"). Only ONE tab is mounted at a time,
// so switching tabs re-fetches that panel's own data rather than keeping six independent reads
// warm simultaneously; each panel already degrades to an absent card on its own (same "ten
// independent reads" discipline `VendorPage.jsx` documents), so a slow or failing tab cannot take
// the others down.
//
// NOT the top-level What/So-what/Now-what spine — that stays un-tabbed by design (see
// `primitives.jsx#Band`). This tabs the DETAIL beneath Tier 1/2, which the redesign explicitly
// calls for; the spine's own invariant (a reader cannot take the What and leave without the Now
// what) is preserved because the Now-what content now lives in Tier 2, above these tabs, not
// inside one of them.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function VendorDetailTabs({
  ref_, score, residual, provisional, continuity, statusPage,
}) {
  const [tab, setTab] = useState('category')
  // const [lifecycle, setLifecycle] = useState(null)
  const [stabilityScore, setStabilityScore] = useState(null)
  const [financialProfile, setFinancialProfile] = useState(null)

  // useEffect(() => {
  //   // let live = true
  //   // getLifecycle(ref_).then((d) => { if (live) setLifecycle(d) }).catch(() => {})
  //   return () => { live = false }
  // }, [ref_])

  useEffect(() => {
    let live = true
    if (tab === 'stability') {
      Promise.all([getStability(ref_), getFinancial(ref_)]).then(([s, f]) => {
        if (live) {
          setStabilityScore(s)
          setFinancialProfile(f)
        }
      }).catch(() => {})
    }
    return () => { live = false }
  }, [ref_, tab])

  const TABS = [
    { id: 'category', label: 'Category detail', icon: FileSearch2 },
    { id: 'peers', label: 'Peer benchmark', icon: Boxes },
    { id: 'gaps', label: 'Gap analysis', icon: Sparkles },
    { id: 'deps', label: 'Dependencies', icon: Network },
    { id: 'assurance', label: 'Assurance detail', icon: ShieldCheck },
    { id: 'stability', label: 'Business Stability', icon: Scale },
    { id: 'lifecycle', label: 'Lifecycle', icon: Clock },
  ]

  return (
    <div className="rounded-2xl border border-border bg-card">
      <div className="flex flex-wrap gap-1 overflow-x-auto border-b border-border/60 px-2 pt-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id}
            className={cn(
              'inline-flex shrink-0 items-center gap-1.5 rounded-t-lg px-3.5 py-2.5 text-[12.5px] font-semibold transition',
              tab === t.id
                ? 'border-b-2 border-accent text-accent'
                : 'border-b-2 border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            <t.icon className="h-3.5 w-3.5" /> {t.label}
          </button>
        ))}
      </div>

      <div className="p-4 sm:p-5">
        {tab === 'category' && (
          <div className="flex flex-col gap-4">
            <div className="flex justify-end"><ExportButton vendorRef={ref_} /></div>
            <EvidenceRecord vendorRef={ref_} score={score} />
            {/* {coverage && <CoverageStatement coverage={coverage} />} */}
            <ResidualDetail residual={residual} provisional={provisional} />
          </div>
        )}
        {tab === 'peers' && (
          <div className="flex flex-col gap-4">
            <PeerBenchmarkPanel vendorRef={ref_} />
          </div>
        )}
        {tab === 'gaps' && <GapAnalysisPanel vendorRef={ref_} />}
        {tab === 'deps' && <DependenciesPanel vendorRef={ref_} />}
        {tab === 'assurance' && <AssurancePanel vendorRef={ref_} />}
        {tab === 'stability' && (
          continuity
            ? <BusinessStabilityCard summary={continuity} coverage={continuity.business_stability_coverage} statusPage={statusPage} stabilityScore={stabilityScore} financialProfile={financialProfile} />
            : <p className="text-[12.5px] italic text-muted-foreground">No Business Stability data for this vendor yet.</p>
        )}
        {/* {tab === 'lifecycle' && <LifecycleCard lifecycle={lifecycle} />} */}
      </div>
    </div>
  )
}

// The full "how this cell was reached" reasoning — moved here from the old So-what band. The
// glance version (the inherent→residual pair) already rides in the Tier-1 hero; this is the
// drill-down argument behind it, which is exactly what belongs under Category Detail rather than
// above the fold.
function ResidualDetail({ residual, provisional }) {
  if (!residual) return null
  if (!residual.published) {
    return (
      <ActionCard title="Residual risk" icon={Layers} noAction="see the reason below.">
        <div className="rounded-xl border px-4 py-3" style={{ borderColor: 'var(--ghost)' }}>
          <p className="max-w-7xl text-[12.5px] leading-relaxed text-muted-foreground">
            {residual.reason}
          </p>
        </div>
      </ActionCard>
    )
  }

  return (
    <ActionCard title="Residual risk" icon={Layers} noAction="advisory — the decision is yours.">
      <div className="flex flex-wrap items-center gap-3">
        <RiskBand tier={residual.residual} label={residual.residual_label} large />
        {provisional && <ProvisionalChip />}
        {residual.escalated_for_sole_source && (
          <span
            className="rounded-lg px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide"
            style={{ background: 'color-mix(in srgb, var(--risk-high) 15%, transparent)', color: 'var(--risk-high)' }}
          >
            ↑ escalated · sole source
          </span>
        )}
      </div>
      <p className="mt-3 max-w-7xl text-[13.5px] font-medium leading-relaxed">{residual.headline}</p>

      <div className="mt-4 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
        How this cell was reached
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[12.5px]">
        <Cell label="Posture" value={`${residual.posture} (${residual.posture_band})`} />
        <span className="text-muted-foreground">×</span>
        <Cell label="Inherent" value={residual.inherent?.label} />
        <span className="text-muted-foreground">→</span>
        <Cell label="Residual" value={residual.residual_label} accent />
        {residual.escalated_from && (
          <>
            <span className="text-muted-foreground">then +1 band</span>
            <span className="text-[11px] text-muted-foreground line-through">{residual.escalated_from}</span>
          </>
        )}
      </div>
      <p className="mt-3 max-w-7xl text-[12px] leading-relaxed text-muted-foreground">
        {residual.inherent?.basis}
      </p>
      <Caveats items={residual.caveats} />
    </ActionCard>
  )
}

function Cell({ label, value, accent }) {
  return (
    <span className={cn(
      'inline-flex flex-col rounded-lg border px-2.5 py-1',
      accent ? 'border-accent bg-accent/10' : 'border-border bg-secondary/40',
    )}>
      <span className="text-[9.5px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-[12.5px] font-semibold capitalize">{value}</span>
    </span>
  )
}
