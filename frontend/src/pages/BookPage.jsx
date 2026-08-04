import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, Ghost, Loader2, Lock, Search
} from 'lucide-react'
import { getAdjudicationQueue, getInventory, getMonitoring, getPortfolio } from '../api.js'
// import { NeedsPersonTile } from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The book — and it opens on WHAT NEEDS A PERSON, before any chart.
//
// The old home screen was an empty search box. That is the right landing page for a demo and the
// wrong one for a programme with 146 vendors, 23 relationships and a queue. Every tile in the
// strip is a Now-what, not a statistic, and each links to the screen that resolves it.
//
// The schedule-health tile is NOT optional and must never be dropped for space. `monitoring_currency`
// can read 100% on a schedule that died in March — nothing is re-scored into staleness when
// nothing is re-scored at all — and reading the run ledger, where SILENCE IS THE ALARM, is the
// only way to tell a live book from a frozen one.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function BookPage() {
  // const nav = useNavigate()
  const [state, setState] = useState({ loading: true })
  const [q, setQ] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([getPortfolio(), getAdjudicationQueue(), getInventory(), getMonitoring()])
      .then(([portfolio, queue, inventory, monitoring]) => {
        if (alive) setState({ loading: false, portfolio, queue, inventory, monitoring })
      })
      .catch((e) => alive && setState({ loading: false, error: e.message }))
    return () => { alive = false }
  }, [])

  const { loading, error, portfolio} = state
  // const { queue, inventory, monitoring } = state 
  const rows = useMemo(() => {
    const all = portfolio?.vendors || portfolio?.rows || []
    if (!q.trim()) return all
    const needle = q.trim().toLowerCase()
    return all.filter((r) => (r.vendor_ref || '').toLowerCase().includes(needle))
  }, [portfolio, q])

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading the book…
      </div>
    )
  }
  if (error) {
    return <Card className="p-6"><p className="text-sm text-muted-foreground">{error}</p></Card>
  }

  // const blocked = queue?.queue_depth ?? 0
  // const unconfirmed = inventory?.provisional ?? 0
  // const undeclared = inventory?.undeclared?.length ?? 0
  // const unregistered = inventory?.unregistered?.length ?? 0
  // const scheduleOk = monitoring?.health?.healthy
  // GHOST AND REFUSED ARE DIFFERENT FACTS and the backend counts them separately: `refused` never
  // published a posture, `ghost` published one that "looks clean only for lack of evidence". The
  // second is the larger and more dangerous number — a refusal announces itself, a ghost does not.
  // const ghosts = portfolio?.summary?.ghosts ?? 0
  // const refused = portfolio?.summary?.refused ?? 0

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">The book</h1>
        {/* <p className="mt-1 text-[13px] text-muted-foreground">
          {inventory?.in_book ?? rows.length} scored ·{' '}
          <strong className="text-foreground">{inventory?.relationships ?? 0} relationships</strong> ·{' '}
          {inventory?.corpus ?? 0} benchmarking corpus · {inventory?.not_a_relationship ?? 0} inventory defects
        </p> */}
      </header>

      {/* ── what needs a person today ──────────────────────────────────────────────── */}
      {/* <section>
        <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
          What needs a person today
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <NeedsPersonTile
            value={blocked} label="Blocked" sub="awaiting a decision"
            action="Work the queue" tone="var(--blocked)"
            onClick={() => nav('/queue')}
          />
          <NeedsPersonTile
            value={undeclared || unconfirmed} label={undeclared ? 'Undeclared' : 'Unconfirmed'}
            sub={undeclared ? 'relationships with no exposure' : 'provisional declarations'}
            action={undeclared ? 'Declare' : 'Confirm with owners'} tone="var(--risk-moderate)"
            onClick={() => nav('/inventory')}
          />
          <NeedsPersonTile
            value={ghosts} label="Ghosts"
            sub={`clean-looking on thin evidence${refused ? ` · ${refused} refused outright` : ''}`}
            action="Review coverage" tone="var(--ghost)"
            onClick={() => setQ('')}
          />
          <ScheduleTile monitoring={monitoring} healthy={scheduleOk} onClick={() => nav('/program')} />
        </div>

        {unregistered > 0 && (
          <div
            className="mt-3 flex items-start gap-2.5 rounded-xl border px-4 py-3"
            style={{ borderColor: 'var(--risk-high)', background: 'color-mix(in srgb, var(--risk-high) 8%, transparent)' }}
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--risk-high)' }} />
            <p className="text-[12.5px] leading-relaxed">
              <strong>{unregistered} vendor{unregistered === 1 ? ' is' : 's are'} on nobody&rsquo;s inventory.</strong>{' '}
              Neither declared nor excused — they are in the book and unclassified, which is the one
              bucket that must never sit quietly at a non-zero value.{' '}
              <Link to="/inventory" className="font-semibold text-accent hover:underline">Classify them →</Link>
            </p>
          </div>
        )}
      </section> */}

      {/* ── concentration ──────────────────────────────────────────────────────────── */}
      {/* {portfolio?.fourth_party_concentration?.single_points_of_failure?.length > 0 && (
        <SpofStrip conc={portfolio.fourth_party_concentration} />
      )} */}

      {/* ── the book ───────────────────────────────────────────────────────────────── */}
      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
            Every vendor
          </h2>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              value={q} onChange={(e) => setQ(e.target.value)} placeholder="filter…"
              className="h-9 w-56 rounded-xl border border-input bg-card pl-8 pr-3 text-[13px] outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        <VendorTable rows={rows} />
      </section>
    </div>
  )
}

// function ScheduleTile({ monitoring, healthy, onClick }) {
//   const health = monitoring?.health
//   const silence = health?.silence_hours
//   return (
//     <NeedsPersonTile
//       value={healthy ? '✓' : '⚠'}
//       label="Monitoring schedule"
//       sub={healthy
//         ? `last run ${silence != null ? `${silence}h` : 'recently'} ago`
//         : 'the sweep is not running'}
//       action={healthy ? 'Run history' : 'Install the schedule'}
//       tone={healthy ? 'var(--risk-low)' : 'var(--risk-critical)'}
//       alarm={!healthy}
//       onClick={onClick}
//     />
//   )
// }

// function SpofStrip({ conc }) {
//   const spofs = conc.single_points_of_failure || []
//   return (
//     <section>
//       <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
//         Fourth-party concentration
//       </h2>
//       <Card className="p-5">
//         <div className="flex items-start gap-3">
//           <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--risk-high)' }} />
//           <div className="min-w-0">
//             <p className="text-[13px] font-semibold">
//               {spofs.length} single point{spofs.length === 1 ? '' : 's'} of failure across the book
//             </p>
//             <div className="mt-2 flex flex-wrap gap-2">
//               {(conc.providers || []).filter((p) => p.single_point_of_failure).map((p) => (
//                 <span key={p.provider} className="rounded-lg border border-border bg-secondary/50 px-2.5 py-1 text-[12px]">
//                   <strong>{p.provider}</strong>
//                   <span className="ml-1.5 text-muted-foreground">
//                     {p.dependent_count} vendors · {Math.round((p.critical_share || 0) * 100)}% of critical-tier
//                   </span>
//                 </span>
//               ))}
//             </div>
//             {/* The honest caveat the backend already computes and most dashboards omit. */}
//             {conc.without_criticality > 0 && (
//               <p className="mt-3 max-w-7xl text-[11.5px] leading-relaxed text-muted-foreground">
//                 <strong className="text-foreground">Critical share is computed over {conc.total_critical} vendors,
//                 not {conc.total_scored}.</strong> {conc.without_criticality} have no declared
//                 criticality and are excluded from that denominator — so this percentage describes
//                 the vendors somebody has classified, not the book.
//               </p>
//             )}
//           </div>
//         </div>
//       </Card>
//     </section>
//   )
// }

function VendorTable({ rows }) {
  if (!rows.length) {
    return <Card className="p-6 text-[13px] text-muted-foreground">No vendors match.</Card>
  }
  return (
    <Card className="overflow-hidden">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border bg-secondary/40 text-left text-[10.5px] uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-2.5 font-semibold">Vendor</th>
            <th className="px-3 py-2.5 text-right font-semibold">Posture</th>
            {/* PAIRED, ALWAYS. Not a design choice — a bare posture column would break the
                invariant the backend holds by keeping the two axes as separate fields. */}
            <th className="px-3 py-2.5 text-right font-semibold">Confidence</th>
            <th className="px-3 py-2.5 font-semibold">State</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => <VendorRow key={r.vendor_ref} r={r} />)}
        </tbody>
      </table>
    </Card>
  )
}

function VendorRow({ r }) {
  const conf = r.overall_confidence ?? r.confidence
  // `ghost` is the backend's own judgement — "looks clean only for lack of evidence" — and it is
  // authoritative here. Re-deriving it from a confidence threshold in the client would give the UI
  // a second opinion about the same thing, which is how the two quietly diverge.
  const thin = r.ghost || (conf ?? 0) < 0.7
  const tone = r.blocked ? 'var(--blocked)' : r.refused || thin ? 'var(--ghost)'
    : r.posture >= 85 ? 'var(--risk-low)' : r.posture >= 70 ? 'var(--risk-moderate)'
    : r.posture >= 50 ? 'var(--risk-high)' : 'var(--risk-critical)'

  return (
    <tr className="border-b border-border/50 last:border-0 hover:bg-secondary/30">
      <td className="px-4 py-2.5">
        <Link to={`/vendors/${encodeURIComponent(r.vendor_ref)}`} className="font-medium hover:text-accent">
          {r.vendor_ref}
        </Link>
      </td>
      <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums" style={{ color: tone }}>
        {r.posture ?? '—'}{r.grade ? ` ${r.grade}` : ''}
      </td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums" style={{ color: thin ? 'var(--ghost)' : undefined }}>
        {conf != null ? `${Math.round(conf * 100)}%` : '—'}
      </td>
      <td className="px-3 py-2.5">
        {r.blocked
          ? <State icon={Lock} tone="var(--blocked)" label="Blocked" />
          : r.refused
            ? <State icon={AlertTriangle} tone="var(--ghost)" label="Refused" />
            : thin
              ? <State icon={Ghost} tone="var(--ghost)" label="Ghost" />
              : <span className="text-[11px] text-muted-foreground">published</span>}
      </td>
    </tr>
  )
}

function State({ icon: Icon, tone, label }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold" style={{ color: tone }}>
      <Icon className="h-3.5 w-3.5" /> {label}
    </span>
  )
}
