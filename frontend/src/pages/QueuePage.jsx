import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Loader2, Lock, ScrollText, Scale } from 'lucide-react'
import { adjudicate, getAdjudicationQueue } from '../api.js'
import { Card } from '../components/ui.jsx'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The adjudication queue.
//
// TWO RULES INHERITED WHOLESALE FROM `app/adjudication_queue.py`, and both are about resisting
// the same failure — *"an 8.8% false-positive rate on household-name public companies turns
// adjudication into a rubber stamp"*:
//
//   1. NO BULK-CLEAR CONTROL. Ever, not even behind a confirm. A "clear all" button IS the rubber
//      stamp, implemented in the interface. Each decision is one click on one record, and that
//      friction is the feature rather than an oversight.
//   2. THE DECISION BUTTONS ARE EQUAL WEIGHT. Neither is primary-coloured, neither is autofocused.
//      A UI that makes *Clear* the easy button has made the decision on the user's behalf, and the
//      s 16(7) record would then rest on a decision nobody actually took.
//
// The ordering is the backend's: by INHERENT EXPOSURE, never by how weak the match looks. A queue
// sorted weakest-first reads as a recommendation to clear from the top.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function QueuePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAdjudicationQueue().then((d) => { setData(d); setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading the queue…
      </div>
    )
  }
  if (!data) {
    return <Card className="p-6 text-sm text-muted-foreground">The queue could not be loaded.</Card>
  }

  const records = data.records || []

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Adjudication queue</h1>
        <p className="mt-1 max-w-7xl text-[13px] leading-relaxed text-muted-foreground">
          {data.queue_depth} blocked ·{' '}
          {Object.entries(data.by_gate || {}).map(([g, n]) => `${n} ${g.replace(/_/g, ' ')}`).join(' · ')}
        </p>
        <p className="mt-2 max-w-7xl rounded-lg border border-border bg-secondary/40 px-3 py-2 text-[11.5px] leading-relaxed text-muted-foreground">
          Ordered by <strong className="text-foreground">inherent exposure</strong>, not by how weak
          the match looks. Each record is decided on its own — there is deliberately no bulk action,
          because a queue that can be cleared in one click is a queue nobody reads.
        </p>
      </header>

      {records.length === 0 ? (
        <Card className="flex items-center gap-3 p-6">
          <CheckCircle2 className="h-5 w-5" style={{ color: 'var(--risk-low)' }} />
          <p className="text-[13px]">Nothing is blocked. No decision is waiting on anyone.</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {records.map((r) => <BlockedRecord key={r.vendor_ref} r={r} />)}
        </div>
      )}

      <Caveats items={data.caveats} />
    </div>
  )
}

function BlockedRecord({ r }) {
  const [decided, setDecided] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [note, setNote] = useState('')
  const [who, setWho] = useState('')

  async function decide(decision) {
    setBusy(true); setError(null)
    try {
      await adjudicate(r.vendor_ref, { decision, rationale: note.trim(), decided_by: who.trim() })
      setDecided(decision)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const sanctions = r.sanctions
  const canDecide = note.trim().length >= 10 && who.trim().length >= 2

  return (
    <Card className={cn('overflow-hidden', decided && 'opacity-60')}>
      {/* header: who, what gate, how exposed, how long */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border/60 bg-secondary/25 px-5 py-3">
        <Link
          to={`/vendors/${encodeURIComponent(r.vendor_ref)}`}
          className="font-mono text-sm font-bold hover:text-accent"
        >
          {r.vendor_ref}
        </Link>
        <GateChip gate={r.gate} />
        <span className="text-[11px] text-muted-foreground">
          {r.classification === 'relationship'
            ? <strong className="text-foreground">relationship</strong>
            : r.classification || 'unregistered'}
          {' · '}
          {r.inherent_tier ? `${r.inherent_tier} tier` : 'no tier declared'}
          {' · '}blocked {r.age_days}d
        </span>
      </div>

      <div className="px-5 py-4">
        {sanctions ? (
          <>
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              What matched
            </div>
            <div className="mt-1.5 space-y-1.5">
              {sanctions.matches.map((m, i) => (
                <div key={i} className="flex flex-wrap items-baseline gap-x-2 text-[13px]">
                  <span className="font-mono text-muted-foreground">&ldquo;{sanctions.query}&rdquo;</span>
                  <span className="text-muted-foreground">→</span>
                  <span className="font-semibold">{m.name}</span>
                  <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px] uppercase">
                    {m.strength}
                  </span>
                  {m.type && <span className="text-[11px] text-muted-foreground">{m.type}</span>}
                  {m.list && <span className="text-[10.5px] text-muted-foreground">· {m.list}</span>}
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="max-w-7xl text-[12.5px] leading-relaxed">{r.reason}</p>
        )}

        {/* THE POINT OF THE WHOLE SCREEN: the facts that turn a research task into a glance. */}
        {/* {r.what_to_check?.length > 0 && (
          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              What to check
            </div>
            <ul className="mt-1.5 space-y-1.5 border-l-2 border-accent/40 pl-3">
              {r.what_to_check.map((n, i) => (
                <li key={i} className="max-w-7xl text-[12px] leading-relaxed text-muted-foreground">{n}</li>
              ))}
            </ul>
          </div>
        )} */}
      </div>

      {/* decision */}
      {decided ? (
        <div className="border-t border-border/60 px-5 py-3 text-[12.5px] font-semibold">
          Recorded: {decided === 'cleared' ? 'cleared — not this entity' : 'upheld — escalated'}
        </div>
      ) : (
        <div className="border-t border-border/60 bg-secondary/20 px-5 py-4">
          <div className="grid gap-2.5 sm:grid-cols-2">
            <input
              value={who} onChange={(e) => setWho(e.target.value)} placeholder="Decided by (your name)"
              className="h-9 rounded-xl border border-input bg-card px-3 text-[12.5px] outline-none focus:ring-2 focus:ring-ring"
            />
            <input
              value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="Rationale — what you checked"
              className="h-9 rounded-xl border border-input bg-card px-3 text-[12.5px] outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
            Your name and reasoning are the statutory-defence record under Autonomous Sanctions Act
            s 16(7). A decision with neither is not a defence.
          </p>

          {error && (
            <p className="mt-2 text-[12px] font-medium" style={{ color: 'var(--risk-critical)' }}>{error}</p>
          )}

          {/* EQUAL WEIGHT. Same variant, same size, same order every time, nothing autofocused. */}
          <div className="mt-3 flex flex-wrap gap-2.5">
            <DecisionButton
              disabled={!canDecide || busy} onClick={() => decide('cleared')}
              label="Clear — not this entity"
            />
            <DecisionButton
              disabled={!canDecide || busy} onClick={() => decide('upheld')}
              label="Uphold — escalate"
            />
          </div>
        </div>
      )}
    </Card>
  )
}

function DecisionButton({ label, disabled, onClick }) {
  return (
    <button
      onClick={onClick} disabled={disabled}
      className="inline-flex h-10 items-center rounded-xl border border-border bg-card px-4 text-[13px] font-semibold transition hover:border-accent hover:bg-secondary disabled:opacity-40"
    >
      {label}
    </button>
  )
}

function GateChip({ gate }) {
  const sanctions = gate === 'sanctions'
  const tone = sanctions ? 'var(--blocked)' : 'var(--risk-high)'
  const Icon = sanctions ? Scale : Lock
  return (
    <span
      className="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider"
      style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}
    >
      <Icon className="h-3 w-3" /> {gate.replace(/_/g, ' ')}
    </span>
  )
}

function Caveats({ items }) {
  if (!items?.length) return null
  return (
    <div className="rounded-xl border border-border bg-secondary/25 px-4 py-3">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
        <ScrollText className="h-3.5 w-3.5" /> How to read this queue
      </div>
      <ul className="mt-2 space-y-2">
        {items.map((c, i) => (
          <li key={i} className="max-w-7xl text-[11.5px] leading-relaxed text-muted-foreground">{c}</li>
        ))}
      </ul>
    </div>
  )
}
