import { useEffect, useState } from 'react'
import { getAssurity } from '../api.js'
import { Caveats, Disclose, EvidenceLink } from './primitives.jsx'
import { Card } from './ui.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// THE THIRD AXIS, AND THE ONLY PLACE IT IS DRAWN.
//
// Assurity answers "how much independent assurance does this vendor actually have?" — a
// different question from posture, because "their TLS is current" and "an auditor has examined
// their controls" are different claims. `synthetic_smallco` in the corpus is posture 97,
// assurity 13.
//
// Two engine guarantees the UI is capable of quietly undoing, so they are design rules here:
//   1. ABSENCE NEVER SUBTRACTS — low assurity means unevidenced, not examined-and-failed. So no
//      traffic-light palette and no risk band. Colouring an unevidenced vendor red is a tax on
//      audit budget, falling hardest on the small suppliers this product exists to assess fairly.
//   2. IT IS NEVER ADDED TO POSTURE — the two figures never share a row or a scale.
//
// PROSE BUDGET: one line of standing text. Everything else — what the axis means, why a
// framework applies, the absence rule — is a tooltip or sits behind a disclosure. The rigour
// lives in the refusals, but printing every refusal inline buries the figures a reader came for
// and the caveats stop being read at all.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function AssurancePanel({ vendorRef, onOpenEvidence }) {
  // Tagged with the ref it describes, so a changed `vendorRef` reads as not-loaded on the first
  // render rather than briefly showing the previous vendor's assurance.
  const [res, setRes] = useState({ ref: null })

  useEffect(() => {
    let live = true
    getAssurity(vendorRef)
      .then((d) => { if (live) setRes({ ref: vendorRef, data: d }) })
      .catch(() => { if (live) setRes({ ref: vendorRef }) })
    return () => { live = false }
  }, [vendorRef])

  // Degrade to nothing, not to an error card: one of ten independent reads on this page, and a
  // 404 (vendor never scored) must not editorialise.
  const data = res.ref === vendorRef ? res.data : null
  if (!data) return null

  const gaps = data.compliance_gaps || []
  const inputs = data.inputs || []
  const score = data.published ? data.assurity : null

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
        <div className="min-w-[128px]"
          title="Independent assurance, not security. Counts what can be externally verified about an audited programme. Absence never subtracts — the floor means unevidenced, not examined and failed. Never added to posture.">
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Assurance
          </div>
          <div className="mt-0.5 flex items-baseline gap-1.5">
            <span className="text-3xl font-black leading-none tracking-tight tabular-nums"
              style={score == null ? { color: 'var(--ghost)' } : undefined}>
              {score ?? 'n/a'}
            </span>
            {score != null && <span className="text-[11px] text-muted-foreground">/ 100</span>}
          </div>
          {score != null && (
            <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-secondary">
              {/* One flat accent, deliberately. A traffic light here would read as a verdict on a
                  vendor that has merely not been audited. */}
              <div className="h-full rounded-full bg-accent"
                style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px]">
          <Stat label="Signals" value={data.observed_signals ?? 0} />
          <Stat label="Gaps" value={gaps.length}
            tone={gaps.length ? 'var(--risk-moderate)' : undefined} />
          <Stat label="Frameworks" value={(data.frameworks_considered || []).length}
            hint={(data.frameworks_considered || []).join(', ')} />
        </div>
      </div>

      <div className="border-t border-border/60 px-5 py-3">
        {inputs.length > 0 && (
          <Disclose label={`What earned it · ${inputs.length}`}>
            <ul className="flex flex-col gap-1">
              {inputs.map((i) => (
                <li key={`${i.signal}·${i.band}`}
                  className="flex flex-wrap items-baseline gap-x-2 text-[12px]">
                  <span className="font-mono text-[11.5px]">{i.signal}</span>
                  <span className="text-muted-foreground">{i.band?.replace(/_/g, ' ')}</span>
                  <span className="font-semibold tabular-nums text-accent">
                    +{Number(i.credit).toFixed(2)}
                  </span>
                  <EvidenceLink id={i.evidence_id} onOpen={onOpenEvidence} />
                </li>
              ))}
            </ul>
          </Disclose>
        )}

        {gaps.length > 0 ? (
          <Disclose label={`Compliance gaps · ${gaps.length}`} tone="var(--risk-moderate)">
            {/* Counted once on the axis, reported in full here: one weakness across three
                asserted frameworks is three gaps but one observation, so publishing more
                certifications can never cost a vendor more. */}
            <ul className="flex flex-col gap-1.5">
              {gaps.map((g, i) => (
                <li key={`${g.framework}·${g.signal}·${i}`} className="text-[12px] leading-relaxed"
                  title={g.applies_because
                    ? `Applies because ${g.applies_because.replace(/_/g, ' ')}${g.applies_detail ? ` — ${g.applies_detail}` : ''}`
                    : undefined}>
                  <span className="font-semibold">{g.framework_name || g.framework}</span>
                  <span className="mx-1.5 font-mono text-[11px] text-muted-foreground">{g.signal}</span>
                  <span className="text-muted-foreground">
                    expected {g.expectation} · observed {g.observed}
                  </span>
                  <EvidenceLink id={g.evidence_id} onOpen={onOpenEvidence} />
                </li>
              ))}
            </ul>
          </Disclose>
        ) : (
          <div className="text-[11.5px] text-muted-foreground"
            title="We check assertions against observations. We do not audit, and this is not a statement of compliance.">
            No compliance gaps observed against the frameworks this vendor asserts.
          </div>
        )}

        <Caveats items={data.caveats} title="Read this with the number" />
      </div>
    </Card>
  )
}

function Stat({ label, value, tone, hint }) {
  return (
    <div title={hint}>
      <div className="text-[9.5px] font-bold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-[15px] font-bold tabular-nums" style={tone ? { color: tone } : undefined}>
        {value}
      </div>
    </div>
  )
}
