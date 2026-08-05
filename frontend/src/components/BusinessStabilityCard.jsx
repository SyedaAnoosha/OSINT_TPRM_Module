import { Activity, AlertTriangle, Ban, CheckCircle2, ShieldAlert } from 'lucide-react'
import { Card } from './ui.jsx'

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
 */
export function BusinessStabilityCard({ summary, coverage, statusPage }) {
  if (!summary) return null
  const config = STANDING_CONFIG[summary.standing] || STANDING_CONFIG.unknown
  const Icon = config.icon
  const facts = summary.registry_facts || []
  const flags = summary.flags || []
  const caveats = summary.caveats || []

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
    </Card>
  )
}
