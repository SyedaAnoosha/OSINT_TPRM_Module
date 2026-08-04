import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Activity, AlertTriangle, Building2, Globe, Layers, Loader2, Scale,
} from 'lucide-react'
import {
  getAssessmentPlan, getContinuity, getCoverage, getEvidencePack,
  getFlowdowns, getProfile, getResidualRisk, getScore, getStatusPage,
} from '../api.js'
import { EvidenceRecord, ExportButton } from '../Scorecard.jsx'
import { AssurancePanel } from '../components/Assurance.jsx'
import { DependenciesPanel } from '../components/Dependencies.jsx'
// import { GapAnalysisPanel } from '../components/GapAnalysis.jsx'
import { PeerBenchmarkPanel } from '../components/PeerBenchmark.jsx'
import { VendorProfilePanel } from '../components/VendorProfile.jsx'
import {
  ActionCard, ActionRow, Band, Caveats, CoverageStatement, DeclareInherentPrompt,
  ProvisionalChip, RiskBand,
} from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The vendor assessment — one What / So what / Now what stack.
//
// THREE BANDS, ALWAYS IN THIS ORDER, NEVER TABS. Tabs would let a reader take the What and leave
// without the Now what, which is exactly the failure this redesign exists to fix: we had a
// problem, we built a dashboard, and nobody knew what to do.
//
// Ten independent reads compose this page and every one degrades to an absent card rather than a
// blank screen. A section that 500s must not take the other nine down with it.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function VendorPage() {
  const { ref } = useParams()
  // `reloadKey` rather than a callback the effect invokes: every state write then happens after an
  // await, so declaring an exposure re-reads the page without a synchronous cascade — and without
  // flashing the whole assessment back to a spinner for a change that touches one band.
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
    <div className="flex flex-col gap-9">
      <Header ref_={ref} score={score} profile={profile} plan={plan} />

      {/* ── WHAT ─────────────────────────────────────────────────────────────────────── */}
      <Band kind="what" actions={<ExportButton vendorRef={ref} />}>
        {/* THE ONE RENDERER. `EvidenceRecord` carries posture + confidence, both ceilings, the
            trend, and category → finding → receipt → hash. This page used to draw its own thin
            category list beside it — the same score rendered twice, which is the drift P6's
            `views_agree()` invariant exists to prevent, arriving through the front-end door. */}
        <EvidenceRecord vendorRef={ref} score={score} />

        {/* THE THIRD AXIS. Posture and confidence are inside `EvidenceRecord`; assurity belongs
            beside them in the What band because it is an observation, not an interpretation —
            "an auditor has examined their controls" is a fact about the vendor, on its own scale,
            never added to posture. The compliance gaps ride with it: a gap is an observation
            against a framework the vendor itself asserts. */}
        <AssurancePanel vendorRef={ref} />

        {coverage && <CoverageStatement coverage={coverage} />}

        {continuity && <ContinuityCard continuity={continuity} statusPage={statusPage} />}
        {/* The richer renderer from `components/Dependencies.jsx` — grouped by category, with
            detection-channel confidence and the website-host caveat. A second, thinner
            dependency card lived here until it was noticed that this one already existed. */}
        <DependenciesPanel vendorRef={ref} />
      </Band>

      {/* ── SO WHAT ──────────────────────────────────────────────────────────────────── */}
      <Band kind="sowhat">
        {declared
          ? <ResidualCard residual={residual} provisional={provisional} />
          : <DeclareInherentPrompt vendorRef={ref} onDeclared={reload} />}

        {/* E14 — a third audience view whose renderer is a model, beside the residual tier and
            compliance-gap indicators it reads but never adjusts (see app/gap_analysis.py). */}
        {/* <GapAnalysisPanel vendorRef={ref} /> */}

        {/* PEER BENCHMARK — the v2 system: cohort assignment with the widening ladder, midrank
            ties, `rank_of_n`, per-domain discrimination, and the E10a expectation gap with the
            observations that account for it. It belongs HERE and not in the What band, because a
            rank is not evidence for why the posture is what it is; it interprets the number
            without moving it. */}
        <PeerBenchmarkPanel vendorRef={ref} />

        {/* TARGET MATURITY + firmographics. The baseline gap is NOT a peer comparison — it
            measures the vendor against published requirements, which is why it still renders for
            a vendor whose cohort is too thin to place. `showBenchmark={false}` because the peer
            strip above supersedes the deprecated v1 one this component used to draw. */}
        <VendorProfilePanel vendorRef={ref} posture={score.posture} showBenchmark={false}
          showMaturityGap benchmarkDepth={plan?.depth === 'screening' ? 'summary' : 'full'} />
      </Band>

      {/* ── NOW WHAT ─────────────────────────────────────────────────────────────────── */}
      <Band kind="nowwhat">
        <NowWhat
          ref_={ref} pack={pack} flowdowns={flowdowns} plan={plan}
          declared={declared} score={score}
        />
      </Band>
    </div>
  )
}

// ── header ────────────────────────────────────────────────────────────────────────────────

function Header({ ref_, score, profile, plan }) {
  const domain = profile?.domain || score?.domain
  return (
    <header className="border-b border-border pb-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight">
            {profile?.legal_name?.value || ref_}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
            <span className="font-mono">{ref_}</span>
            {domain && <><span>·</span><span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />{domain}</span></>}
            {profile?.sector?.value && <><span>·</span><span className="inline-flex items-center gap-1"><Building2 className="h-3 w-3" />{profile.sector.value}</span></>}
          </div>
        </div>
        {plan && (
          <div className="rounded-xl border border-border bg-card px-3.5 py-2 text-right">
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
    </header>
  )
}

function ContinuityCard({ continuity, statusPage }) {
  const flags = continuity.flags || []
  // A FLAG IS NOT AUTOMATICALLY BAD. Every registry observation is reported, sound ones included —
  // "the register records this entity as active and in good standing" IS evidence, and hiding it
  // would leave the card showing only problems, so a clean vendor would look unexamined.
  const adverse = flags.filter((f) => f.standing && f.standing !== 'sound')
  const headTone = STANDING_TONE[continuity.standing] || 'var(--ghost)'

  return (
    <ActionCard
      title="Continuity" icon={Scale} tone={headTone}
      noAction={adverse.length
        ? 'registry standing is disclosed, never scored — it is context for the decision above.'
        : 'nothing adverse on the register.'}
    >
      <div className="text-sm font-semibold capitalize" style={{ color: headTone }}>
        {continuity.standing?.replace(/_/g, ' ') || 'unknown'}
        {/* WORST STANDING WINS — non-compensatory, like every other roll-up in this system. */}
        {flags.length > 1 && (
          <span className="ml-2 text-[11px] font-normal text-muted-foreground">
            worst of {flags.length} registry facts
          </span>
        )}
      </div>
      {flags.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {flags.map((f, i) => (
            <li key={i} className="flex gap-2 text-[12px] leading-relaxed">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: STANDING_TONE[f.standing] || 'var(--ghost)' }} />
              <span className={f.standing === 'sound' ? 'text-muted-foreground' : ''}>
                {f.statement}
                {f.source && <span className="ml-1 font-mono text-[10.5px] text-muted-foreground">({f.source})</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
      {/* P7's status page rides BESIDE going-concern standing, never inside it. A cloud outage
          and a deregistration are different facts on different clocks. */}
      {statusPage?.found && (
        <div className="mt-3 border-t border-border/60 pt-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Service availability
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[12.5px]">
            <Activity className="h-3.5 w-3.5 text-accent" />
            <span className="font-medium">{statusPage.indicator_label || statusPage.indicator}</span>
            {statusPage.open_incident_count > 0 && (
              <span className="text-muted-foreground">· {statusPage.open_incident_count} open</span>
            )}
          </div>
        </div>
      )}
    </ActionCard>
  )
}

const STANDING_TONE = {
  sound: 'var(--risk-low)',
  watch: 'var(--risk-moderate)',
  impaired: 'var(--risk-high)',
  failed: 'var(--risk-critical)',
}

// ── so what: the residual cell ─────────────────────────────────────────────────────────────

function ResidualCard({ residual, provisional }) {
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
    <Card className="overflow-hidden">
      <div className="border-b border-border/60 px-5 py-4">
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
        <p className="mt-3 max-w-7xl text-[13.5px] font-medium leading-relaxed">
          {residual.headline}
        </p>
      </div>

      <div className="px-5 py-4">
        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
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
      </div>
    </Card>
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

// ── now what ──────────────────────────────────────────────────────────────────────────────

function NowWhat({ ref_, pack, flowdowns, plan, declared, score }) {
  const asks = pack?.question_count ?? 0
  const clauses = flowdowns?.count ?? 0
  const next = plan?.next_action

  if (score.blocked) {
    return (
      <ActionCard title="This record is blocked" icon={AlertTriangle} tone="var(--blocked)">
        <p className="max-w-7xl text-[13px] leading-relaxed">
          No posture was published, so there is nothing to remediate and nothing to put in a
          contract. The only action available is the one a person has to take.
        </p>
        <div className="mt-4">
          <Link
            to="/queue"
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
          >
            Work the adjudication queue →
          </Link>
        </div>
      </ActionCard>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <ActionRow
        n={1} title="Ask the vendor" count={asks}
        detail={asks ? pack.summary : 'Nothing outstanding — every penalising signal came back clean.'}
        owner="Procurement"
        due={pack?.soonest_recheck ? `re-check in ${pack.soonest_recheck}` : undefined}
        onClick={asks ? () => { window.location.href = `/vendors/${ref_}/pack` } : undefined}
      />

      <ActionRow
        n={2} title="Put in the contract" count={clauses}
        detail={clauses ? flowdowns.summary : 'Nothing a vendor response could not close.'}
        owner="Legal"
        onClick={clauses ? () => { window.location.href = `/vendors/${ref_}/contract` } : undefined}
      />

      {plan && (
        <ActionRow
          n={3} title="Next assessment"
          detail={next?.note || plan.headline}
          owner="TPRM lead"
          due={next?.days != null ? `in ${next.days} day${next.days === 1 ? '' : 's'} · ${next.driver}` : plan.review_cadence?.label}
        />
      )}

      {!declared && (
        <div className="rounded-xl border border-dashed border-border px-4 py-2 text-[12px] text-muted-foreground"
          title="Without a declared inherent tier there is no exposure to rank against, so the order above is the order they were generated in — not the order they matter in.">
          <strong className="text-foreground">These actions are unprioritised</strong> — no inherent
          tier declared.
        </div>
      )}
    </div>
  )
}
