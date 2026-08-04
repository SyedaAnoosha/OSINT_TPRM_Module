import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, CircleAlert, Loader2, TriangleAlert, Users } from 'lucide-react'
import { getInventory } from '../api.js'
import { ProvisionalChip } from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The inventory of record — three columns, because the whole point is that they are three
// different populations and a single count averaged over them was the original defect.
//
// `inherent_tier_declaration_rate` read 0.0% across 146 vendors. That number was wrong in both
// directions: the numerator was zero because there was no route to declare, and the denominator
// counted 114 seeded benchmarking vendors and 9 typos as suppliers nobody had classified.
//
// The "excluded by design" copy is LOAD-BEARING. A reader seeing 114 rows under a heading they do
// not recognise will assume they are being ignored unless the page says why — and the sentence to
// use is the register's own.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function InventoryPage() {
  const [inv, setInv] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { getInventory().then((d) => { setInv(d); setLoading(false) }) }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading the inventory…
      </div>
    )
  }
  if (!inv) return <Card className="p-6 text-sm text-muted-foreground">Inventory unavailable.</Card>

  const rate = inv.declaration_rate == null ? null : Math.round(inv.declaration_rate * 100)
  const confirmedRate = inv.confirmed_rate == null ? null : Math.round(inv.confirmed_rate * 100)

  return (
    <div className="flex flex-col gap-7">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Inventory of record</h1>
        <p className="mt-1 max-w-7xl text-[13px] leading-relaxed text-muted-foreground">
          Which rows in the book are relationships, and which are not. This is the denominator every
          declaration figure is computed against — {inv.in_book} scored rows are not {inv.in_book}{' '}
          relationships.
        </p>
      </header>

      {/* the one bucket that must never sit quietly non-zero */}
      {inv.unregistered?.length > 0 && (
        <div
          className="flex items-start gap-3 rounded-2xl border px-5 py-4"
          style={{ borderColor: 'var(--risk-high)', background: 'color-mix(in srgb, var(--risk-high) 8%, transparent)' }}
        >
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--risk-high)' }} />
          <div>
            <h2 className="text-sm font-bold">{inv.unregistered.length} unregistered</h2>
            <p className="mt-1 max-w-7xl text-[12.5px] leading-relaxed">
              In the book, and on nobody&rsquo;s inventory — <strong>neither declared nor excused</strong>.
              Reported on its own rather than folded into any of the three columns below, because
              assuming an unknown row is a relationship and assuming it is not are both guesses,
              and only one of them is visible.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {inv.unregistered.map((r) => (
                <Link key={r} to={`/vendors/${encodeURIComponent(r)}`}
                  className="rounded-md border border-border bg-card px-2 py-0.5 font-mono text-[11px] hover:text-accent">
                  {r}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* the declaration rate, with its two numbers kept apart */}
      <Card className="p-5">
        <div className="flex flex-wrap items-end gap-8">
          <Figure
            label="Declared" value={rate == null ? '—' : `${rate}%`}
            sub={`${inv.declared} of ${inv.relationships} relationships`}
            tone={rate === 100 ? 'var(--risk-low)' : 'var(--risk-moderate)'}
          />
          <Figure
            label="Confirmed" value={confirmedRate == null ? '—' : `${confirmedRate}%`}
            sub={`${inv.confirmed} by an accountable owner`}
            tone={inv.confirmed > 0 ? 'var(--risk-low)' : 'var(--risk-moderate)'}
          />
          <Figure
            label="Provisional" value={inv.provisional}
            sub="declared, not yet confirmed" tone="var(--ghost)"
          />
        </div>
        <p className="mt-4 max-w-7xl text-[12px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Declared and confirmed are counted separately on purpose.</strong>{' '}
          A provisional declaration is a real one — it routes assessment depth and publishes a
          residual tier — but reporting the two as one green number is exactly how an unconfirmed
          answer gets read as a confirmed one.
        </p>
        {inv.unapplied?.length > 0 && (
          <p className="mt-3 rounded-lg border px-3 py-2 text-[12px]" style={{ borderColor: 'var(--risk-high)' }}>
            <strong>{inv.unapplied.length} declared on the register but never written to the store.</strong>{' '}
            Run <code className="font-mono">python -m app.inherent_register --apply</code>.
          </p>
        )}
      </Card>

      {/* three populations */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Column
          icon={Users} tone="var(--accent)"
          title="Relationships" count={inv.relationships}
          blurb="An exposure to declare. Somebody owns answering the question."
        >
          <div className="space-y-1.5">
            {(inv.relationships_detail || []).map((e) => (
              <div key={e.ref} className="rounded-lg border border-border/70 px-2.5 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Link to={`/vendors/${encodeURIComponent(e.ref)}`}
                    className="font-mono text-[12px] font-semibold hover:text-accent">
                    {e.ref}
                  </Link>
                  {e.provisional && <ProvisionalChip />}
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5 text-[10.5px]">
                  <Tag label="criticality" value={e.criticality} />
                  <Tag label="scope" value={e.data_access_scope} />
                  {e.substitutability && <Tag label="subst." value={e.substitutability} />}
                </div>
                {e.note && (
                  <p className="mt-1.5 text-[10.5px] leading-snug" style={{ color: 'var(--risk-high)' }}>
                    {e.note}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Column>

        <Column
          icon={Boxes} tone="var(--ghost)"
          title="Seeded corpus" count={inv.corpus}
          blurb="No relationship, nothing to declare."
        >
          <p className="max-w-7xl text-[12px] leading-relaxed text-muted-foreground">
            Scored by <code className="font-mono text-[11px]">seed_cohorts</code> to give the peer
            cohorts a population.{' '}
            <strong className="text-foreground">
              These are excluded from the declaration rate by design.
            </strong>{' '}
            There is no commercial relationship, so there is no exposure — and inventing one to move
            a metric is the failure this register exists to prevent.
          </p>
          <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
            Derived from the seed list rather than listed here, so the two can never disagree.
          </p>
        </Column>

        <Column
          icon={CircleAlert} tone="var(--risk-high)"
          title="Inventory defects" count={inv.not_a_relationship}
          blurb="In the book, and not vendors."
        >
          <div className="space-y-2">
            {(inv.inventory_defects || []).map((d) => (
              <div key={d.ref} className="rounded-lg border border-border/70 px-2.5 py-2">
                <div className="font-mono text-[12px] font-semibold">{d.ref}</div>
                <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{d.note}</p>
              </div>
            ))}
          </div>
        </Column>
      </div>

      {inv.note && (
        <p className="max-w-7xl rounded-xl border border-border bg-secondary/25 px-4 py-3 text-[11.5px] leading-relaxed text-muted-foreground">
          {inv.note}
        </p>
      )}
    </div>
  )
}

function Figure({ label, value, sub, tone }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: tone }}>{value}</div>
      <div className="text-[11px] text-muted-foreground">{sub}</div>
    </div>
  )
}

function Column({ icon: Icon, tone, title, count, blurb, children }) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4" style={{ color: tone }} />
          <h2 className="text-sm font-bold">{title}</h2>
          <span className="ml-auto font-mono text-xl font-bold tabular-nums" style={{ color: tone }}>
            {count}
          </span>
        </div>
        <p className="mt-0.5 text-[11px] text-muted-foreground">{blurb}</p>
      </div>
      <div className="max-h-[32rem] overflow-y-auto px-4 py-3">{children}</div>
    </Card>
  )
}

function Tag({ label, value }) {
  if (!value) return null
  return (
    <span className="rounded border border-border bg-secondary/50 px-1.5 py-0.5">
      <span className="text-muted-foreground">{label} </span>
      <span className="font-semibold capitalize">{value.replace(/_/g, ' ')}</span>
    </span>
  )
}
