import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { PRETTY, deSnake } from '../lib/labels.js'
import { Card, Meter } from './ui.jsx'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// TIER 2 — "Evidence coverage bar". design note §3.2:
// "overall fraction plus a per-category breakdown (X of 27 signals), including the new Business
// Stability coverage fraction from §1.3."
//
// ONE HUE, NOT A TRAFFIC LIGHT (dataviz skill — sequential = magnitude, one ramp light→dark).
// Coverage is "how much did we see", not "is it good or bad" — a category can be 100% covered and
// still score an F. Painting the bar green-to-red would smuggle a verdict onto an axis that is not
// making one, which is the exact collapse `PostureConfidencePair` refuses for posture/confidence.
// Business Stability's coverage rides in the SAME strip, at the SAME single hue, for the same
// reason: it is a separate axis's coverage, not a second opinion on this one.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function EvidenceCoverageBar({ coverage, categories = [], businessStabilityCoverage }) {
  const [open, setOpen] = useState(false)
  if (!coverage && categories.length === 0 && !businessStabilityCoverage) return null

  const covered = coverage?.signals_covered
  const planned = coverage?.signals_planned
  const pct = planned ? Math.round((covered / planned) * 100) : null

  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 text-left"
      >
        <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
          Evidence coverage
        </span>
        {planned ? (
          <span className="flex min-w-[180px] flex-1 items-center gap-2.5">
            <Meter value={pct} color="var(--accent)" />
            <span className="whitespace-nowrap font-mono text-[12.5px] font-semibold">
              {covered}/{planned} signals
            </span>
          </span>
        ) : (
          <span className="text-[12px] text-muted-foreground">not yet computed for this vendor</span>
        )}
        {businessStabilityCoverage && (
          <span className="whitespace-nowrap text-[11.5px] text-muted-foreground"
            title="A SEPARATE coverage figure from Posture's — the Business Stability axis has its own denominator.">
            Bus. Stability {businessStabilityCoverage.answered}/{businessStabilityCoverage.tracked}
          </span>
        )}
        <ChevronDown className={cn('ml-auto h-4 w-4 shrink-0 text-muted-foreground transition', open && 'rotate-180')} />
      </button>

      {open && categories.length > 0 && (
        <div className="border-t border-border/60 px-5 py-3">
          <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {categories.map((c) => {
              const cpct = Math.round((c.coverage ?? 0) * 100)
              return (
                <div key={c.category} className="flex items-center gap-2.5 text-[12px]">
                  <span className="w-40 shrink-0 truncate text-muted-foreground">{PRETTY[c.category] || deSnake(c.category)}</span>
                  <Meter value={cpct} color="var(--accent)" />
                  <span className="w-9 shrink-0 text-right font-mono tabular-nums">{cpct}%</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </Card>
  )
}
