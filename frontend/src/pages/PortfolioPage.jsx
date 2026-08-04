import { useEffect, useState } from 'react'
import { Layers, ShieldAlert, Ghost, TriangleAlert } from 'lucide-react'
import { getPortfolio } from '../api.js'
import { Card } from '../components/ui.jsx'
import { postureColor, gradeColor } from '../lib/utils.js'

// The whole book at a glance. A single-vendor scorecard answers "is this one safe?"; a risk
// manager or CISO also needs "where is my exposure across the book?" Every row here is the SAME
// immutable score the scorecard renders — this page aggregates, it never recomputes a number.

const CRIT_TONE = {
  high: 'var(--risk-high, #dc2626)',
  medium: 'var(--risk-med, #d97706)',
  low: 'var(--risk-low, #16a34a)',
}
const GRADE_ORDER = ['A', 'B', 'C', 'D', 'E', 'F']

function StatTile({ icon: Icon, label, value, tone }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5" />} {label}
      </div>
      <div className="mt-1 text-3xl font-bold" style={{ color: tone }}>{value}</div>
    </Card>
  )
}

// Grade distribution — one neutral bar per grade, magnitude-vs-reference. A count on each bar, so
// the shape and the number are both readable; grade tone carries identity, never colour alone.
function GradeBars({ byGrade, total }) {
  const max = Math.max(1, ...GRADE_ORDER.map((g) => byGrade[g] || 0))
  const present = GRADE_ORDER.filter((g) => byGrade[g])
  if (!present.length) return null
  return (
    <Card className="p-5">
      <div className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Grade distribution · {total} vendor{total === 1 ? '' : 's'}
      </div>
      <div className="space-y-1.5">
        {present.map((g) => {
          const n = byGrade[g] || 0
          return (
            <div key={g} className="grid grid-cols-[1.5rem_1fr_2rem] items-center gap-2 text-xs">
              <span className="font-mono font-bold" style={{ color: gradeColor(g) }}>{g}</span>
              <div className="h-3 rounded bg-secondary">
                <div className="h-3 rounded" style={{ width: `${(n / max) * 100}%`, background: gradeColor(g), opacity: 0.65 }} />
              </div>
              <span className="text-right font-medium">{n}</span>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

export default function PortfolioPage() {
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('loading') // loading | ready | error

  useEffect(() => {
    let live = true
    getPortfolio()
      .then((d) => { if (live) { setData(d); setStatus('ready') } })
      .catch(() => { if (live) setStatus('error') })
    return () => { live = false }
  }, [])

  if (status === 'loading') {
    return <p className="text-sm text-muted-foreground">Loading portfolio…</p>
  }
  if (status === 'error') {
    return (
      <Card className="p-5 text-sm text-muted-foreground">
        <b className="text-foreground">Portfolio unavailable.</b> The score store could not be
        reached. Every vendor you have scored appears here once the store is reachable again.
      </Card>
    )
  }
  if (!data || data.total === 0) {
    return (
      <Card className="p-5 text-sm text-muted-foreground">
        <b className="text-foreground">No vendors scored yet.</b> Score a vendor and it appears in
        the portfolio here — with its grade, criticality, and where it sits in the book.
      </Card>
    )
  }

  const s = data.summary
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Portfolio</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {data.total} vendor{data.total === 1 ? '' : 's'} scored · latest score each · aggregated, never recomputed.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile icon={Layers} label="Vendors" value={data.total} />
        <StatTile icon={TriangleAlert} label="High-dependency · below 60"
          value={s.high_criticality_below_60}
          tone={s.high_criticality_below_60 > 0 ? CRIT_TONE.high : undefined} />
        <StatTile icon={ShieldAlert} label="Blocked" value={s.blocked}
          tone={s.blocked > 0 ? 'var(--blocked, #7c3aed)' : undefined} />
        <StatTile icon={Ghost} label="Ghosts · unassessed" value={s.ghosts} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <GradeBars byGrade={s.by_grade} total={data.total} />

        {/* The board-level number: high-dependency vendors that also score low. This is where
            exposure lives — a low score on a vendor you barely use is not it. */}
        <Card className="p-5">
          <div className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Concentration · high-dependency vendors below 60
          </div>
          {data.concentration.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              None. No vendor marked high-criticality is scoring below 60. (Concentration can only
              count vendors whose criticality you supplied at score time.)
            </p>
          ) : (
            <ul className="space-y-1.5">
              {data.concentration.map((c) => (
                <li key={c.vendor_ref} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate font-medium">{c.vendor_ref}</span>
                  <span className="shrink-0">
                    <span className="font-mono font-bold" style={{ color: postureColor(c.posture) }}>{c.posture}</span>
                    <span className="ml-1.5 text-muted-foreground">{c.grade}</span>
                    {c.sector && <span className="ml-2 text-[11px] text-muted-foreground">{c.sector}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* The full book — lowest posture first, because that is what a reader scans for. */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-5 py-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          All vendors · lowest posture first
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-5 py-2 font-medium">Vendor</th>
                <th className="px-3 py-2 font-medium">Posture</th>
                <th className="px-3 py-2 font-medium">Grade</th>
                <th className="px-3 py-2 font-medium">Confidence</th>
                <th className="px-3 py-2 font-medium">Criticality</th>
                <th className="px-5 py-2 font-medium">Sector</th>
              </tr>
            </thead>
            <tbody>
              {data.vendors.map((v) => (
                <tr key={v.vendor_ref} className="border-b border-border/60 last:border-b-0 hover:bg-secondary/40">
                  <td className="px-5 py-2.5 font-medium">{v.vendor_ref}</td>
                  <td className="px-3 py-2.5">
                    {v.blocked ? <span className="text-[12px]" style={{ color: 'var(--blocked, #7c3aed)' }}>blocked</span>
                      : v.posture == null ? <span className="text-muted-foreground">—</span>
                        : <span className="font-mono font-bold" style={{ color: postureColor(v.posture) }}>{v.posture}</span>}
                  </td>
                  <td className="px-3 py-2.5 font-mono font-semibold" style={{ color: v.grade ? gradeColor(v.grade) : undefined }}>
                    {v.grade || '—'}{v.ghost && <span className="ml-1 text-[10px] font-sans text-ghost">ghost</span>}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {v.confidence == null ? '—' : `${Math.round(v.confidence * 100)}%`}
                  </td>
                  <td className="px-3 py-2.5 capitalize" style={{ color: v.criticality ? CRIT_TONE[v.criticality] : undefined }}>
                    {v.criticality || <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-5 py-2.5 text-muted-foreground">{v.sector || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {data.caveats?.length > 0 && (
        <ul className="space-y-1 text-[11px] leading-relaxed text-muted-foreground">
          {data.caveats.map((c, i) => (
            <li key={i} className="flex gap-1.5"><span aria-hidden>·</span><span>{c}</span></li>
          ))}
        </ul>
      )}
    </div>
  )
}
