import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Flag, Loader2 } from 'lucide-react'
import {
  getAssessmentPlan, getContinuity, getCoverage, getEvidencePack,
  getFlowdowns, getProfile, getResidualRisk, getScore, getStatusPage,
} from '../api.js'
import { EvidenceCoverageBar } from '../components/EvidenceCoverageBar.jsx'
import { ExecutiveSummaryHero } from '../components/ExecutiveSummaryHero.jsx'
import { RecommendationsPanel } from '../components/RecommendationsPanel.jsx'
import { TopFindings } from '../components/TopFindings.jsx'
import { VendorDetailTabs } from '../components/VendorDetailTabs.jsx'
import { Card } from '../components/ui.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// THE EXECUTIVE DASHBOARD — three tiers, docs/tprm_feedback_redesign.md §3.
//
//   Tier 1 (glance, <15s)   — <ExecutiveSummaryHero>: identity, grade, posture+trend,
//                             confidence, assurity, Business Stability, inherent→residual.
//   Tier 2 (scan, 30-60s)   — <TopFindings> (top 3 strengths/weaknesses), <RecommendationsPanel>
//                             (the Now-what content, MOVED UP rather than duplicated — see its own
//                             docstring), <EvidenceCoverageBar>.
//   Tier 3 (drill-down)     — <VendorDetailTabs>: category detail, peer benchmark, gap analysis,
//                             dependencies, assurance detail, Business Stability citations.
//
// This extends `docs/frontend_redesign_plan.md`'s What/So-what/Now-what spine — it does not
// replace it. The three questions that spine protects still get answered, in the same order, on
// this same page: Tier 1+2's "top weaknesses" and coverage bar ARE the What; Tier 1's
// inherent→residual pair and Tier 3's Residual detail ARE the So-what; Tier 2's Recommendations
// panel — now above the fold instead of at the bottom of a long scroll — IS the Now-what. Moving
// it up serves the spine's own invariant (a reader cannot take the What and leave without the Now
// what) better than leaving it where a reader has to scroll past peer benchmarks to find it.
//
// Nine independent reads compose this page and every one degrades to an absent card rather than a
// blank screen — unchanged from before this redesign, just recomposed into tiers instead of bands.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function VendorPage() {
  const { ref } = useParams()
  // `reloadKey` rather than a callback the effect invokes: every state write then happens after an
  // await, so declaring an exposure re-reads the page without a synchronous cascade — and without
  // flashing the whole assessment back to a spinner for a change that touches one tier.
  const [reloadKey, setReloadKey] = useState(0)
  const [{ loading, error, data }, setState] = useState({ loading: true })

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const score = await getScore(ref)
        const [profile, residual, coverage, plan, pack, flowdowns, continuity, statusPage] =
          await Promise.all([
            getProfile(ref), getResidualRisk(ref), getCoverage(ref), getAssessmentPlan(ref),
            getEvidencePack(ref), getFlowdowns(ref), getContinuity(ref), getStatusPage(ref),
          ])
        if (alive) {
          setState({
            loading: false,
            data: { score, profile, residual, coverage, plan, pack, flowdowns, continuity, statusPage },
          })
        }
      } catch (e) {
        if (alive) setState({ loading: false, error: e.message })
      }
    })()
    return () => { alive = false }
  }, [ref, reloadKey])

  const reload = () => setReloadKey((k) => k + 1)

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading {ref}…
      </div>
    )
  }
  if (error) {
    return (
      <Card className="p-6">
        <h1 className="text-lg font-bold">Could not load {ref}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        <Link to="/" className="mt-4 inline-block text-sm font-semibold text-accent hover:underline">
          ← back to the book
        </Link>
      </Card>
    )
  }

  const { score, profile, residual, coverage, plan, pack, flowdowns, continuity, statusPage } = data
  const declared = residual?.inherent?.published
  const provisional = residual?.inherent?.provisional

  return (
    <div className="flex flex-col gap-6">
      {/* ── TIER 1 — GLANCE ──────────────────────────────────────────────────────────── */}
      <ExecutiveSummaryHero
        ref_={ref} score={score} profile={profile} plan={plan}
        continuity={continuity} residual={residual} provisional={provisional}
      />

      {/* ── TIER 2 — SCAN ────────────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-4">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
          Strengths, weaknesses & recommendations
        </h2>

        <TopFindings vendorRef={ref} score={score} />

        <Card className="overflow-hidden">
          <div className="flex items-center gap-2 border-b border-border/60 px-4 py-2.5">
            <Flag className="h-3.5 w-3.5 text-accent" />
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
              Key recommendations
            </h3>
          </div>
          <div className="px-4 py-3.5">
            <RecommendationsPanel
              ref_={ref} pack={pack} flowdowns={flowdowns} plan={plan} declared={declared}
              score={score} continuity={continuity} onDeclared={reload}
            />
          </div>
        </Card>

        <EvidenceCoverageBar
          coverage={coverage} categories={score?.categories}
          businessStabilityCoverage={continuity?.business_stability_coverage}
        />
      </section>

      {/* ── TIER 3 — DRILL-DOWN ──────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
          Detail, on demand
        </h2>
        <VendorDetailTabs
          ref_={ref} score={score} plan={plan} residual={residual} provisional={provisional}
          coverage={coverage} continuity={continuity} statusPage={statusPage}
        />
      </section>
    </div>
  )
}
