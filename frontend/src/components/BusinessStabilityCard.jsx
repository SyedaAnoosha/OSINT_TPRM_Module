import { Activity, AlertTriangle, Ban, CheckCircle2, ShieldAlert, TrendingUp, TrendingDown, Minus, ChevronRight } from 'lucide-react'
import { Card } from './ui.jsx'
import { FinancialDetailModal } from './FinancialDetailModal.jsx'
import { useState } from 'react'

// Matches `Standing` exactly as backend/app/continuity.py declares it: "ceased" | "impaired" |
// "watch" | "sound" | "unknown". `unknown` is painted `--ghost` (not a risk colour) on purpose —
// "not evidenced for this vendor's jurisdiction" is not the same claim as "watch", and colouring
// it on the same ramp as an observed problem would assert a severity nobody observed.
const STANDING_CONFIG = {
  sound: { icon: CheckCircle2, tone: 'var(--risk-low)', label: 'Sound' },
  watch: { icon: AlertTriangle, tone: 'var(--risk-moderate)', label: 'Watch' },
  impaired: { icon: ShieldAlert, tone: 'var(--risk-high)', label: 'Impaired' },
  ceased: { icon: ShieldAlert, tone: 'var(--risk-critical)', label: 'Ceased' },
  unknown: { icon: Activity, tone: 'var(--ghost)', label: 'Unknown' },
}

// Age band configuration for longevity display
const AGE_BAND_CONFIG = {
  startup: { label: 'Startup (<2 years)', tone: 'var(--risk-high)', description: 'High failure rate, limited track record, financial uncertainty' },
  young: { label: 'Young (2-5 years)', tone: 'var(--risk-moderate)', description: 'Elevated risk, still establishing market position' },
  established: { label: 'Established (5-10 years)', tone: 'var(--risk-low)', description: 'Moderate risk, proven business model' },
  mature: { label: 'Mature (10-20 years)', tone: 'var(--risk-low)', description: 'Lower risk, demonstrated staying power' },
  veteran: { label: 'Veteran (20+ years)', tone: 'var(--risk-low)', description: 'Lowest risk, survivorship credit, long-term stability' },
  unknown: { label: 'Unknown', tone: 'var(--ghost)', description: 'Age not determinable' },
}

/**
 * THE TIER-1 GLANCE VERSION — one pill, wrapping `Continuity.standing` exactly as the full card
 * does (docs/tprm_feedback_redesign.md §3.4: "<BusinessStabilityBadge> (wraps Continuity.standing)").
 * Shares `STANDING_CONFIG` with the full card below so the hero row and the drill-down tab can never
 * disagree on what colour/label a standing gets — one mapping, two renderings.
 *
 * Renders nothing when `continuity` itself is absent (not yet scored / endpoint 404) rather than
 * asserting "unknown" — `unknown` is itself an observed standing (no registry coverage for this
 * vendor's jurisdiction), a different claim from "we haven't loaded this yet".
 */
export function BusinessStabilityBadge({ standing }) {
  if (!standing) return null
  const config = STANDING_CONFIG[standing] || STANDING_CONFIG.unknown
  const Icon = config.icon
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] font-bold"
      style={{ background: `color-mix(in srgb, ${config.tone} 15%, transparent)`, color: config.tone }}
      title="Registry-derived going-concern standing — Continuity.standing, relabelled. Never affects Posture (docs/tprm_feedback_redesign.md §0.1)."
    >
      <Icon className="h-3.5 w-3.5" /> {config.label}
    </span>
  )
}

/**
 * summary: { standing, registry_facts, flags, procurement_action, procurement_headline,
 *   procurement_blocking, caveats } — the shape GET /api/vendors/{ref}/continuity returns.
 * coverage: { answered, tracked } — a SEPARATE figure from Posture confidence, by design
 *   (docs/tprm_feedback_redesign.md §1.3, ScoringConfig.business_stability_signals). Never
 *   implies "0 of 3" is clean — absence of data is not evidence of health.
 * statusPage: optional — P7's operational status, rendered beside going-concern standing, never
 *   inside it. A cloud outage and a deregistration are different facts on different clocks.
 * stabilityScore: optional — Phase 2 Business Stability score from GET /api/vendors/{ref}/stability
 * financialProfile: optional — Phase 2 financial data from GET /api/vendors/{ref}/financial
 */
export function BusinessStabilityCard({ summary, coverage, statusPage, stabilityScore, financialProfile }) {
  const [showFinancialDetails, setShowFinancialDetails] = useState(false)

  if (!summary) return null
  const config = STANDING_CONFIG[summary.standing] || STANDING_CONFIG.unknown
  const Icon = config.icon
  const facts = summary.registry_facts || []
  const flags = summary.flags || []
  const caveats = summary.caveats || []

  // Phase 2: Business Stability score data
  const score = stabilityScore?.score
  const ageBand = stabilityScore?.age_band || financialProfile?.age_band
  const gateTriggered = stabilityScore?.gate_triggered
  const gateReason = stabilityScore?.gate_reason
  const contingencyRequired = stabilityScore?.contingency_plan_required

  return (
    <Card className="overflow-hidden border-l-4" style={{ borderLeftColor: config.tone }}>
      <div className="flex items-center gap-3 border-b border-border/60 px-5 py-3.5"
           style={{ background: `color-mix(in srgb, ${config.tone} 8%, transparent)` }}>
        <Icon className="h-5 w-5" style={{ color: config.tone }} />
        <div>
          <h2 className="text-sm font-bold">Business Stability</h2>
          <p className="text-[11px] text-muted-foreground">Viability & Insolvency (Procurement Track)</p>
        </div>
        <span className="ml-auto rounded-lg px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider"
              style={{ background: `color-mix(in srgb, ${config.tone} 15%, transparent)`, color: config.tone }}>
          {config.label}
          {/* WORST STANDING WINS — non-compensatory, like every other roll-up in this system. */}
          {flags.length > 1 && (
            <span className="ml-1.5 font-normal normal-case tracking-normal opacity-70">
              · worst of {flags.length}
            </span>
          )}
        </span>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Phase 2: Business Stability Score Display */}
        {score !== undefined && (
          <div className="rounded-lg border border-border/60 px-3 py-2.5 bg-secondary/30">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-0.5">
                  Financial Health Score
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold" style={{ color: score >= 90 ? 'var(--risk-low)' : score >= 75 ? 'var(--risk-moderate)' : 'var(--risk-high)' }}>
                    {score}
                  </span>
                  <span className="text-[11px] text-muted-foreground">/ 100</span>
                </div>
              </div>
              {gateTriggered ? (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded" style={{ background: 'var(--risk-critical)', color: 'white' }}>
                  <Ban className="h-3.5 w-3.5" />
                  <span className="text-[10px] font-bold uppercase">Blocked</span>
                </div>
              ) : (
                <div className="text-right">
                  <div className="text-[10px] text-muted-foreground">Base Score</div>
                  <div className="text-[11px] font-medium">{stabilityScore.base_score}</div>
                </div>
              )}
            </div>
            {gateTriggered && gateReason && (
              <div className="mt-2 text-[11px] font-medium" style={{ color: 'var(--risk-critical)' }}>
                ⚠ {gateReason}
              </div>
            )}
          </div>
        )}

        {/* Phase 2: Business Stability Score Breakdown */}
        {stabilityScore && (
          <div className="mt-4 border-t border-border/60 pt-4">
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
              Score Composition
            </div>
            <div className="space-y-1.5 text-[12px]">
              {/* 1. Age Base */}
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Base Score (Operating History)</span>
                <span className="font-mono font-semibold">
                  {stabilityScore.base_score ?? '—'}
                  <span className="text-[10px] text-muted-foreground ml-1">
                    ({stabilityScore.age_band?.replace('_', ' ')})
                  </span>
                </span>
              </div>

              {/* 2. Financial Penalties */}
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Financial Distress Penalties</span>
                <span className="font-mono font-semibold" style={{ color: 'var(--risk-high)' }}>
                  -{Object.values(stabilityScore.penalties || {}).reduce((a, b) => a + b, 0).toFixed(0) || 0}
                </span>
              </div>

              {/* 3. Survivorship Bonuses */}
              {stabilityScore.bonuses && Object.keys(stabilityScore.bonuses).length > 0 && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Survivorship Bonuses</span>
                  <span className="font-mono font-semibold" style={{ color: 'var(--risk-low)' }}>
                    +{Object.values(stabilityScore.bonuses).reduce((a, b) => a + b, 0).toFixed(0)}
                  </span>
                </div>
              )}
            </div>

            {/* The OSINT Limit Caveat */}
            <div className="mt-3 rounded-lg border border-dashed border-border/60 px-3 py-2 bg-secondary/20">
              <p className="text-[10.5px] leading-relaxed text-muted-foreground">
                <strong className="text-foreground">OSINT Limitation:</strong> Public OSINT can observe legal 
                insolvency (which triggers penalties above) and operating history (which sets the base score). 
                However, internal financial metrics like <em>revenue decline, debt-to-equity, and cash flow</em> 
                are not publicly observable. To assess these, use the Evidence Request Pack to ask the vendor 
                for audited financial statements.
              </p>
            </div>
          </div>
        )}

        {/* Phase 2: Age Band Display */}
        {ageBand && (
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
              Company Age
            </div>
            <div className="flex items-center gap-2">
              <span
                className="rounded px-2 py-0.5 text-[11px] font-medium"
                style={{ background: `color-mix(in srgb, ${AGE_BAND_CONFIG[ageBand]?.tone || 'var(--ghost)'} 15%, transparent)`, color: AGE_BAND_CONFIG[ageBand]?.tone || 'var(--ghost)' }}
              >
                {AGE_BAND_CONFIG[ageBand]?.label || ageBand}
              </span>
              {financialProfile?.operating_years && (
                <span className="text-[11px] text-muted-foreground">
                  ({financialProfile.operating_years.toFixed(1)} years)
                </span>
              )}
            </div>
            <p className="text-[10.5px] text-muted-foreground mt-1">
              {AGE_BAND_CONFIG[ageBand]?.description}
            </p>
          </div>
        )}

        {/* Phase 2: Age Differentiation Profile */}
        {stabilityScore?.age_differentiation && (
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
              Age-Based Risk Analysis
            </div>
            <div className="space-y-2">
              {stabilityScore.age_differentiation.historical_depth && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Historical Depth</span>
                  <span className="font-medium">{stabilityScore.age_differentiation.historical_depth.band}</span>
                </div>
              )}
              {stabilityScore.age_differentiation.financial_transparency && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Financial Transparency</span>
                  <span className="font-medium">{stabilityScore.age_differentiation.financial_transparency.band}</span>
                </div>
              )}
              {stabilityScore.age_differentiation.leadership_risk && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Leadership Risk</span>
                  <span className="font-medium">{stabilityScore.age_differentiation.leadership_risk.band}</span>
                </div>
              )}
              {stabilityScore.age_differentiation.operational_maturity && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Operational Maturity</span>
                  <span className="font-medium">{stabilityScore.age_differentiation.operational_maturity.band}</span>
                </div>
              )}
              {stabilityScore.age_differentiation.media_velocity && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Media Velocity</span>
                  <span className="font-medium">{stabilityScore.age_differentiation.media_velocity.band}</span>
                </div>
              )}
              {stabilityScore.age_differentiation.structural_change && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Structural Change</span>
                  <span className="font-medium">{stabilityScore.age_differentiation.structural_change.band}</span>
                </div>
              )}
              {stabilityScore.age_differentiation.rationale && (
                <p className="text-[10.5px] text-muted-foreground mt-2 italic">
                  {stabilityScore.age_differentiation.rationale}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Phase 2: Financial Metrics */}
        {financialProfile && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                Financial Metrics
              </div>
              <button
                onClick={() => setShowFinancialDetails(true)}
                className="text-[10px] text-accent hover:underline flex items-center gap-1"
              >
                View details <ChevronRight className="h-3 w-3" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              {financialProfile.revenue_trend ? (
                <div className="flex items-center gap-1.5">
                  {financialProfile.revenue_trend === 'growing' && <TrendingUp className="h-3 w-3 text-green-600" />}
                  {financialProfile.revenue_trend === 'declining' && <TrendingDown className="h-3 w-3 text-red-600" />}
                  {financialProfile.revenue_trend === 'stable' && <Minus className="h-3 w-3 text-muted-foreground" />}
                  <span className="capitalize">{financialProfile.revenue_trend}</span>
                  <span className="text-muted-foreground">revenue</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-muted-foreground italic">
                  <Minus className="h-3 w-3" />
                  <span>Revenue not observable</span>
                </div>
              )}
              {financialProfile.cash_flow_trend ? (
                <div className="flex items-center gap-1.5">
                  {financialProfile.cash_flow_trend === 'positive' && <TrendingUp className="h-3 w-3 text-green-600" />}
                  {financialProfile.cash_flow_trend === 'negative' && <TrendingDown className="h-3 w-3 text-red-600" />}
                  <span className="capitalize">{financialProfile.cash_flow_trend}</span>
                  <span className="text-muted-foreground">cash flow</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-muted-foreground italic">
                  <Minus className="h-3 w-3" />
                  <span>Cash flow not observable</span>
                </div>
              )}
              {financialProfile.debt_to_equity !== null && financialProfile.debt_to_equity !== undefined ? (
                <div className="flex items-center gap-1.5">
                  <span className="font-medium">{financialProfile.debt_to_equity.toFixed(2)}x</span>
                  <span className="text-muted-foreground">debt-to-equity</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-muted-foreground italic">
                  <Minus className="h-3 w-3" />
                  <span>Debt-to-equity not observable</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Phase 2: Contingency Plan Flag */}
        {contingencyRequired && (
          <div className="rounded-lg border px-3 py-2" style={{ borderColor: 'var(--risk-moderate)', background: 'color-mix(in srgb, var(--risk-moderate) 7%, transparent)' }}>
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--risk-moderate)' }}>
              <AlertTriangle className="h-3.5 w-3.5" />
              Contingency Plan Required
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">
              Young vendor with critical dependency — develop exit strategy
            </p>
          </div>
        )}

        {coverage && (
          <div
            className="text-[11px] text-muted-foreground"
            title="Gazette (UK), SEC EDGAR (US public) and CourtListener (US federal bankruptcy) — a separate coverage figure from Posture's confidence axis on purpose. It never moves Posture or Confidence; it only says how much of THIS axis was checked."
          >
            Business Stability evidence: <strong className="text-foreground">{coverage.answered} of {coverage.tracked}</strong> checks
            {coverage.answered === 0 && ' — not evidenced, not the same as clean'}
          </div>
        )}

        {/* Registry Facts */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1.5">Registry Facts</div>
          {facts.length === 0 && flags.length === 0 ? (
            <p className="text-[12px] italic text-muted-foreground">no registry facts on record.</p>
          ) : (
            <ul className="space-y-1 text-[12.5px]">
              {facts.map((fact, i) => (
                <li key={`fact-${i}`} className="flex items-baseline gap-2">
                  <span className="text-muted-foreground">•</span> {fact}
                </li>
              ))}
              {flags.map((flag, i) => (
                <li key={`flag-${i}`} className="flex items-baseline gap-2 font-medium" style={{ color: config.tone }}>
                  <span>•</span> {flag.statement} <span className="text-[10px] text-muted-foreground font-normal">({flag.source})</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Procurement Action */}
        {summary.procurement_action && (
          <div
            className="rounded-lg border px-3 py-2.5"
            style={summary.procurement_blocking
              ? { borderColor: 'var(--risk-critical)', background: 'color-mix(in srgb, var(--risk-critical) 7%, transparent)' }
              : { borderColor: 'var(--border)', background: 'color-mix(in srgb, var(--secondary) 30%, transparent)' }}
          >
            <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider"
                 style={{ color: summary.procurement_blocking ? 'var(--risk-critical)' : 'var(--accent)' }}>
              {summary.procurement_blocking && <Ban className="h-3 w-3" />}
              Procurement Action
            </div>
            <p className="text-[12px] font-medium leading-relaxed">{summary.procurement_action}</p>
          </div>
        )}

        {/* P7's status page rides BESIDE going-concern standing, never inside it. */}
        {statusPage?.found && (
          <div className="border-t border-border/60 pt-3">
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

        {/* Caveats (The E4 Invariant) */}
        {caveats.length > 0 && (
          <div className="pt-2 border-t border-border/40">
            {caveats.map((c, i) => (
              <p key={i} className="text-[10.5px] italic text-muted-foreground leading-snug">⚠ {c}</p>
            ))}
          </div>
        )}
      </div>

      {/* Phase 4.4: Financial Detail Modal */}
      {showFinancialDetails && (
        <FinancialDetailModal
          financialProfile={financialProfile}
          onClose={() => setShowFinancialDetails(false)}
        />
      )}
    </Card>
  )
}
