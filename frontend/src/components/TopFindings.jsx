import { useEffect, useState } from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { listFindings } from '../api.js'
import { CONTEXT_CATEGORIES, PRETTY, deSnake } from '../lib/labels.js'
import { Card } from './ui.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// TIER 2 — SCAN, 30-60 SECONDS. docs/tprm_feedback_redesign.md §3.2:
// "Top 3 strengths and top 3 weaknesses, ranked by penalty magnitude (weaknesses) and by
// category headroom (strengths)."
//
// Reads the SAME findings/categories the Category Detail tab (`EvidenceRecord`) renders in full —
// this is a ranked slice of that data, never a second scoring pass. Weaknesses are the three
// highest `effective_penalty` findings across every category; strengths are the three categories
// with the most headroom (highest published posture among categories that were actually covered —
// an uncovered category is not a strength, it is a coverage gap, and `EvidenceCoverageBar` is
// where that gets said).
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function TopFindings({ vendorRef, score }) {
  const [findings, setFindings] = useState(null)
  useEffect(() => {
    let live = true
    listFindings(vendorRef).then((rows) => { if (live) setFindings(rows) }).catch(() => { if (live) setFindings([]) })
    return () => { live = false }
  }, [vendorRef])

  if (score?.blocked || score?.refused || score?.posture == null) return null
  const categories = score?.categories || []
  if (findings == null) return null

  const weaknesses = findings
    .filter((f) => (f.effective_penalty ?? 0) > 0 && f.reason)
    .sort((a, b) => (b.effective_penalty ?? 0) - (a.effective_penalty ?? 0))
    .slice(0, 3)

  // CONTEXT CATEGORIES EXCLUDED (lib/labels.js#CONTEXT_CATEGORIES) — they always publish
  // posture 100 by construction (scoring.yaml §0), so including them would show the same two
  // rows on every vendor regardless of actual security strength.
  const strengths = categories
    .filter((c) => c.posture != null && (c.coverage ?? 0) > 0 && !CONTEXT_CATEGORIES.has(c.category))
    .sort((a, b) => (b.posture ?? 0) - (a.posture ?? 0))
    .slice(0, 3)

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border/60 px-4 py-2.5">
          <ThumbsUp className="h-3.5 w-3.5" style={{ color: 'var(--risk-low)' }} />
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Top strengths</h3>
        </div>
        <div className="px-4 py-3">
          {strengths.length === 0 ? (
            <p className="text-[12px] italic text-muted-foreground">No covered category came back clean enough to call a strength.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {strengths.map((c) => (
                <li key={c.category} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                  <span className="min-w-0 truncate font-medium">{PRETTY[c.category] || deSnake(c.category)}</span>
                  <span className="shrink-0 font-mono font-semibold tabular-nums" style={{ color: 'var(--risk-low)' }}>
                    {c.posture}{c.grade ? ` ${c.grade}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border/60 px-4 py-2.5">
          <ThumbsDown className="h-3.5 w-3.5" style={{ color: 'var(--risk-high)' }} />
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Top weaknesses</h3>
        </div>
        <div className="px-4 py-3">
          {weaknesses.length === 0 ? (
            <p className="text-[12px] italic text-muted-foreground">Nothing we could check publicly came back as a problem.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {weaknesses.map((f) => (
                <li key={f.id} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                  <span className="min-w-0 font-medium">{f.reason || deSnake(f.signal)}</span>
                  <span className="shrink-0 font-mono font-semibold tabular-nums" style={{ color: 'var(--risk-high)' }}>
                    −{Math.round((f.effective_penalty ?? 0) * 10) / 10}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  )
}
