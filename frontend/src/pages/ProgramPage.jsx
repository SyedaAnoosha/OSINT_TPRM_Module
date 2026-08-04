import { useEffect, useState } from 'react'
import { Activity, ChevronDown, Loader2, Radio, TrendingDown } from 'lucide-react'
import { getEstateReadiness, getKpis, getMaturity, getMonitoring } from '../api.js'
import { EmptyMetric, PeerFigure } from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The programme — a different subject from every other screen. Not "how is this vendor doing"
// but "how good is our TPRM function".
//
// The maturity half's job is to produce ONE next action, not eight. So the floor dimension is the
// only one expanded by default and the only one with an accent marker; the rest are collapsed.
// The average is rendered, but never as the headline — an average lets strength where we are
// naturally strong conceal the dimension that will fail an audit.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function ProgramPage() {
  const [d, setD] = useState({ loading: true })

  useEffect(() => {
    Promise.all([getMaturity(), getKpis(), getMonitoring(), getEstateReadiness()])
      .then(([maturity, kpis, monitoring, estate]) =>
        setD({ loading: false, maturity, kpis, monitoring, estate }))
  }, [])

  if (d.loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading the programme…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">The programme</h1>
        <p className="mt-1 max-w-7xl text-[13px] leading-relaxed text-muted-foreground">
          Not how a vendor is doing — how <em>we</em> are doing. Nothing on this page reaches any
          vendor score.
        </p>
      </header>

      {d.monitoring && <ScheduleHealth m={d.monitoring} />}
      {d.maturity && <Maturity m={d.maturity} />}
      {d.kpis && <Kpis k={d.kpis} />}
      {d.estate && <EstateReadiness e={d.estate} />}
    </div>
  )
}

// ── schedule health: silence is the alarm ──────────────────────────────────────────────────

function ScheduleHealth({ m }) {
  const h = m.health || {}
  const healthy = h.healthy
  const tone = healthy ? 'var(--risk-low)' : 'var(--risk-critical)'
  return (
    <Card className="overflow-hidden">
      <div
        className="flex flex-wrap items-center gap-3 border-b border-border/60 px-5 py-3.5"
        style={{ background: `color-mix(in srgb, ${tone} 8%, transparent)` }}
      >
        <Radio className="h-4 w-4" style={{ color: tone }} />
        <h2 className="text-sm font-bold">Monitoring schedule</h2>
        <span className="rounded-lg px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider"
          style={{ background: `color-mix(in srgb, ${tone} 18%, transparent)`, color: tone }}>
          {healthy ? 'alive' : 'not running'}
        </span>
      </div>
      <div className="px-5 py-4">
        <p className="max-w-7xl text-[12.5px] leading-relaxed">{h.reason}</p>
        <p className="mt-2 max-w-7xl text-[11.5px] leading-relaxed text-muted-foreground">
          This is a different question from monitoring currency, which can read 100% on a schedule
          that died months ago — nothing is re-scored into staleness when nothing is re-scored at
          all. Here <strong className="text-foreground">silence is the alarm condition</strong>.
        </p>

        {h.last_run && (
          <div className="mt-4 flex flex-wrap gap-6 text-[12px]">
            <Stat label="Considered" value={h.last_run.considered} />
            <Stat label="Re-scored" value={h.last_run.rescored} />
            <Stat label="Drifted" value={h.last_run.drifted} />
            <Stat label="Failed" value={h.last_run.failed} tone={h.last_run.failed ? 'var(--risk-critical)' : undefined} />
            <Stat label="Duration" value={`${h.last_run.duration_secs}s`} />
          </div>
        )}

        {h.incomplete_runs?.length > 0 && (
          <p className="mt-3 text-[11.5px]" style={{ color: 'var(--risk-high)' }}>
            {h.incomplete_runs.length} run{h.incomplete_runs.length === 1 ? '' : 's'} started and never
            finished. A status column would have overwritten that on the next success; the ledger keeps it.
          </p>
        )}

        {/* Retained drift reports — P9 asks for these by name, and a log line that rotates is not
            a retained report. */}
        {m.recent_runs?.some((r) => r.drift?.length) && (
          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Recent drift
            </div>
            <div className="mt-1.5 space-y-1">
              {m.recent_runs.flatMap((r) => r.drift || []).slice(0, 8).map((dr, i) => (
                <div key={i} className="flex items-center gap-2 text-[12px]">
                  <TrendingDown className="h-3.5 w-3.5" style={{ color: dr.delta < 0 ? 'var(--risk-critical)' : 'var(--risk-low)' }} />
                  <span className="font-mono">{dr.ref}</span>
                  <span className="text-muted-foreground">{dr.old} → {dr.new}</span>
                  <span className="font-semibold" style={{ color: dr.delta < 0 ? 'var(--risk-critical)' : 'var(--risk-low)' }}>
                    {dr.delta > 0 ? '+' : ''}{dr.delta}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {!healthy && m.schedule && (
          <div className="mt-4 rounded-xl border border-border bg-secondary/40 px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
              Install the schedule
            </div>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{m.schedule.note}</p>
            <code className="mt-2 block font-mono text-[11.5px]">{m.schedule.entrypoint}</code>
            <code className="mt-1 block font-mono text-[11.5px] text-muted-foreground">{m.schedule.health_check}</code>
          </div>
        )}
      </div>
    </Card>
  )
}

function Stat({ label, value, tone }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-mono text-lg font-bold tabular-nums" style={{ color: tone }}>{value}</div>
    </div>
  )
}

// ── maturity ───────────────────────────────────────────────────────────────────────────────

function Maturity({ m }) {
  const floor = m.overall_level
  const limiting = new Set(m.limiting_dimensions || [])
  const avg = (m.dimensions.reduce((a, d) => a + d.level, 0) / m.dimensions.length).toFixed(1)

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/60 px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="font-mono text-4xl font-bold" style={{ color: 'var(--risk-moderate)' }}>
            Level {floor}
          </span>
          <span className="text-lg font-semibold">{m.overall_level_name}</span>
          <span className="text-[11px] text-muted-foreground">
            assessment v{m.assessment_version} · {m.assessed_on}
          </span>
        </div>
        <p className="mt-2 max-w-7xl text-[13px] leading-relaxed">{m.headline}</p>
      </div>

      <div className="px-5 py-4">
        {m.dimensions.map((d) => (
          <Dimension key={d.key} d={d} isFloor={limiting.has(d.key)} />
        ))}

        {/* The average is shown, and shown as NOT the headline. */}
        <p className="mt-4 max-w-7xl rounded-lg border border-border bg-secondary/30 px-3 py-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
          The average is <strong className="text-foreground">{avg}</strong>. It is not the headline,
          because an average lets strength where we are naturally strong conceal the dimension that
          will actually fail an audit. {m.overall_rule}.
        </p>

        {m.changelog?.length > 1 && (
          <details className="mt-3">
            <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-accent">
              Assessment history
            </summary>
            <ul className="mt-2 space-y-2 border-l-2 border-border pl-3">
              {m.changelog.map((c) => (
                <li key={c.version} className="text-[11.5px] leading-relaxed text-muted-foreground">
                  <strong className="text-foreground">v{c.version}</strong> · {c.date} — {c.change}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </Card>
  )
}

function Dimension({ d, isFloor }) {
  // THE FLOOR IS EXPANDED BY DEFAULT AND NOTHING ELSE IS. This screen's job is to produce one
  // next action, not eight.
  const [open, setOpen] = useState(isFloor)
  const tone = isFloor ? 'var(--risk-critical)' : d.level >= 4 ? 'var(--risk-low)' : 'var(--risk-moderate)'

  return (
    <div className={cn('border-b border-border/40 py-2.5 last:border-0', isFloor && 'rounded-lg bg-secondary/30 px-2.5')}>
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 text-left">
        <span className="w-56 shrink-0 truncate text-[12.5px] font-medium">{d.name}</span>
        <span className="flex gap-0.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <span key={n} className="h-4 w-3.5 rounded-sm"
              style={{ background: n <= d.level ? tone : 'var(--secondary)' }} />
          ))}
        </span>
        <span className="w-24 shrink-0 text-[12px] font-semibold" style={{ color: tone }}>
          {d.level} {d.level_name}
        </span>
        {isFloor && (
          <span className="rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wider"
            style={{ background: 'color-mix(in srgb, var(--risk-critical) 16%, transparent)', color: 'var(--risk-critical)' }}>
            ◀ the floor
          </span>
        )}
        <ChevronDown className={cn('ml-auto h-4 w-4 shrink-0 text-muted-foreground transition', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="mt-2 pl-0 sm:pl-3">
          <p className="max-w-7xl text-[12px] leading-relaxed text-muted-foreground">{d.rationale}</p>
          <div className="mt-2.5 rounded-lg border-l-2 border-accent bg-accent/5 px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-accent">To reach the next level</div>
            <p className="mt-0.5 max-w-7xl text-[12px] leading-relaxed">{d.to_reach_next}</p>
          </div>
          {d.evidence?.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {d.evidence.map((e, i) => (
                <li key={i} className="font-mono text-[10.5px] leading-relaxed text-muted-foreground">· {e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

// ── KPIs ───────────────────────────────────────────────────────────────────────────────────

function Kpis({ k }) {
  const unsupplied = new Set(k.unsupplied || [])
  const notComputable = new Set(k.not_computable || [])
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/60 px-5 py-3.5">
        <h2 className="text-sm font-bold">KPIs and KRIs</h2>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          {k.metrics.length} metrics · {k.metrics.filter((m) => m.provenance === 'platform-derived').length} computed,
          {' '}{k.metrics.filter((m) => m.provenance === 'manually-supplied').length} declared-or-empty.
          A dashboard whose every metric is green is measuring the wrong things.
        </p>
      </div>
      <div className="divide-y divide-border/40">
        {k.metrics.map((m) => (
          <MetricRow key={m.key} m={m}
            kind={unsupplied.has(m.key) ? 'unsupplied' : notComputable.has(m.key) ? 'not_computable' : null} />
        ))}
      </div>
    </Card>
  )
}

function MetricRow({ m, kind }) {
  const [open, setOpen] = useState(false)
  const isObj = m.value && typeof m.value === 'object'
  return (
    <div className="px-5 py-3">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-4 text-left">
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] font-semibold">{m.name}</div>
          <div className="text-[11px] text-muted-foreground">{m.owner} · {m.cadence}</div>
        </div>
        <div className="w-64 shrink-0 text-right">
          {m.value == null ? (
            <div className="flex justify-end">
              <EmptyMetric kind={kind || 'not_computable'} owner={m.owner} reason={m.unavailable_reason} />
            </div>
          ) : isObj ? (
            <div className="flex flex-wrap justify-end gap-1">
              {Object.entries(m.value).map(([k2, v]) => (
                <span key={k2} className="rounded border border-border bg-secondary/50 px-1.5 py-0.5 text-[10.5px]">
                  <span className="text-muted-foreground">{k2.replace(/_/g, ' ')} </span>
                  <strong>{v}</strong>
                </span>
              ))}
            </div>
          ) : (
            <span className="font-mono text-lg font-bold tabular-nums">{m.value}</span>
          )}
        </div>
        <ChevronDown className={cn('mt-1 h-4 w-4 shrink-0 text-muted-foreground transition', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="mt-2 space-y-1.5 border-l-2 border-border pl-3 text-[11.5px] leading-relaxed text-muted-foreground">
          <p><strong className="text-foreground">Formula.</strong> {m.formula}</p>
          <p><strong className="text-foreground">Source.</strong> {m.source}</p>
          <p><strong className="text-foreground">Target.</strong> {m.target}</p>
          {m.unavailable_reason && (
            <p style={{ color: 'var(--risk-moderate)' }}>{m.unavailable_reason}</p>
          )}
          {m.detail?.read_this_first && (
            <p className="text-foreground">{m.detail.read_this_first}</p>
          )}
          {m.detail?.why_it_matters && <p>{m.detail.why_it_matters}</p>}
          {m.detail?.note && <p className="italic">{m.detail.note}</p>}
          {m.peer_comparison?.map((p, i) => (
            <PeerFigure key={i} value={p.value} caption={p.caption} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── E12 readiness ──────────────────────────────────────────────────────────────────────────

function EstateReadiness({ e }) {
  const tone = e.ready ? 'var(--risk-low)' : 'var(--risk-moderate)'
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/60 px-5 py-3.5">
        <div className="flex flex-wrap items-center gap-3">
          <Activity className="h-4 w-4" style={{ color: tone }} />
          <h2 className="text-sm font-bold">Estate fan-out readiness (E12)</h2>
          <span className="rounded-lg px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider"
            style={{ background: `color-mix(in srgb, ${tone} 16%, transparent)`, color: tone }}>
            {e.ready ? 'ready' : 'not ready'}
          </span>
          <span className="ml-auto font-mono text-[11px] text-muted-foreground">probe_cap: {e.current_probe_cap}</span>
        </div>
      </div>
      <div className="px-5 py-4">
        <div className="flex flex-wrap gap-8">
          <Stat label="Book-wide" value={`${Math.round(e.availability * 100)}%`} />
          <Stat label="Relationships" value={`${Math.round(e.relationship_availability * 100)}%`} />
          <Stat label="Threshold" value={`${Math.round(e.threshold * 100)}%`} />
          <Stat label="Median estate" value={e.estate_size?.median ?? '—'} />
        </div>
        <p className="mt-3 max-w-7xl text-[12px] leading-relaxed">{e.verdict}</p>
        <p className="mt-2 max-w-7xl text-[11.5px] leading-relaxed text-muted-foreground">
          {e.coverage_cost_of_switching_on}
        </p>
      </div>
    </Card>
  )
}
