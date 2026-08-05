import { Link } from 'react-router-dom'
import { AlertTriangle, Ban } from 'lucide-react'
import { ActionCard, ActionRow, DeclareInherentPrompt } from './primitives.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// TIER 2 — "Key recommendations". docs/tprm_feedback_redesign.md §3.2/§3.4:
// "merges existing remediation guidance with the new Phase 1 procurement-rule output, so a
// ceased/impaired Business Stability flag surfaces here, not buried in a sub-tab."
//
// This IS the Now-what band's content — moved up to Tier 2 rather than duplicated, because a
// recommendation a reader has to scroll past the peer benchmark and the assurance detail to reach
// is a recommendation that is effectively unpublished. The declaration prompt rides at the very
// top when undeclared: it is the single highest-leverage action in the app (see its own docstring
// in primitives.jsx) — burying it in a tab would undo exactly what moving this panel up is for.
//
// A `ceased`/`impaired` Business Stability flag (`procurement_blocking`) gets its own headline
// callout above the ranked list — precedent: Black Kite's ransomware-susceptibility highlight,
// UpGuard's single risk score with category breakdown underneath (§3.5) — so a Gazette insolvency
// notice cannot read as just another bullet among routine asks.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function RecommendationsPanel({ ref_, pack, flowdowns, plan, declared, score, continuity, onDeclared }) {
  if (score?.blocked) {
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

  const asks = pack?.question_count ?? 0
  const clauses = flowdowns?.count ?? 0
  const next = plan?.next_action
  const blocking = continuity?.procurement_blocking

  return (
    <div className="flex flex-col gap-3">
      {blocking && (
        <div
          className="flex items-start gap-3 rounded-xl border-2 px-4 py-3.5"
          style={{ borderColor: 'var(--risk-critical)', background: 'color-mix(in srgb, var(--risk-critical) 8%, transparent)' }}
        >
          <Ban className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--risk-critical)' }} />
          <div>
            <div className="text-sm font-bold" style={{ color: 'var(--risk-critical)' }}>
              {continuity.procurement_headline || 'Business Stability blocker'}
            </div>
            <p className="mt-1 max-w-7xl text-[12.5px] leading-relaxed">{continuity.procurement_action}</p>
          </div>
        </div>
      )}

      {!declared && <DeclareInherentPrompt vendorRef={ref_} onDeclared={onDeclared} compact />}

      {!blocking && continuity?.procurement_action && (
        <ActionRow
          title="Business Stability" detail={continuity.procurement_action} owner="Procurement"
        />
      )}

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
