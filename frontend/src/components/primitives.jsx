import { useState } from 'react'
import {
  AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, FileText, Ghost, Info, Lock, ShieldAlert,
} from 'lucide-react'
import { declareInherent } from '../api.js'
import { cn } from '../lib/utils.js'
import { Badge, Card } from './ui.jsx'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// The invariants, expressed as components.
//
// `docs/frontend_redesign_plan.md` §7 lists ten rules the UI must not break. Most of them are
// mirrors of backend invariants, and a rule that lives only in a document is a rule that gets
// broken by the next person in a hurry. So the load-bearing ones are built into the component
// signatures here: `<PostureConfidencePair>` cannot be rendered without a confidence, and
// `<PeerFigure>` cannot be rendered without its caption. Breaking those means deleting a
// component, which is a reviewable diff rather than an accident.
// ═══════════════════════════════════════════════════════════════════════════════════════════

// ── the What / So what / Now what spine ───────────────────────────────────────────────────

const BAND_META = {
  what: {
    label: 'Evidence we observed',
    // hint: 'Evidence, not promises — every number links to the receipt it came from',
  },
  sowhat: {
    label: 'What this means for YOU',
    // hint: 'What this means for YOU — needs your declared exposure',
  },
  nowwhat: {
    label: 'The next action',
    // hint: 'The next action',
  },
}

/**
 * One band of the spine. Always rendered in the order What → So what → Now what, and
 * DELIBERATELY NOT TABBED: tabs would let a reader take the What and leave without the Now what,
 * which is the exact failure this redesign exists to fix ("we had a problem, we built a
 * dashboard, and nobody knows what to do").
 */
export function Band({ kind, children, actions }) {
  const meta = BAND_META[kind]
  return (
    <section className="relative">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
          {meta.label}
        </h2>
        {/* <p className="text-[11px] text-muted-foreground">{meta.hint}</p> */}
        {actions && <div className="ml-auto">{actions}</div>}
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  )
}

/**
 * A card that must end in something. `action` is the Now-what; when there genuinely is none,
 * pass `noAction` with the reason.
 *
 * A card whose last row is a number is unfinished — a reader assumes silence means "nothing
 * needed", so the absence of an action has to be stated rather than implied.
 */
export function ActionCard({ title, icon: Icon, children, action, noAction, tone, className }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      {title && (
        <div className="flex items-center gap-2 border-b border-border/60 px-5 py-3">
          {Icon && <Icon className="h-4 w-4 shrink-0" style={{ color: tone || 'var(--accent)' }} />}
          <h3 className="text-sm font-semibold">{title}</h3>
        </div>
      )}
      <div className="px-5 py-4">{children}</div>
      {(action || noAction) && (
        <div className="border-t border-border/60 bg-secondary/30 px-5 py-3">
          {action || (
            <p className="text-[12px] italic text-muted-foreground">
              No action — {noAction}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

// ── the pairing rule ──────────────────────────────────────────────────────────────────────

function ramp(v) {
  if (v == null) return 'var(--ghost)'
  if (v >= 85) return 'var(--risk-low)'
  if (v >= 70) return 'var(--risk-moderate)'
  if (v >= 50) return 'var(--risk-high)'
  return 'var(--risk-critical)'
}

/**
 * POSTURE AND CONFIDENCE, NEVER APART.
 *
 * `confidence` is a REQUIRED prop, not an optional one — that is the whole point of this
 * component existing rather than two spans. The backend keeps the two axes as separate `Score`
 * fields and holds an invariant that they never collapse; rendering a bare posture would break
 * that invariant in the one place a user actually reads it.
 *
 * A green 91 at 32% coverage is the single most dangerous cell this product can draw, so below
 * the floor the grade is painted `--ghost` and captioned — never green, and never a greyed-out
 * number, which reads as "roughly this".
 */
export function PostureConfidencePair({ posture, confidence, grade, band, refused, blocked, size = 'lg' }) {
  if (blocked) return <GhostState kind="blocked" />
  if (refused || posture == null) return <GhostState kind="refused" confidence={confidence} />

  const pct = Math.round((confidence ?? 0) * 100)
  const thin = (confidence ?? 0) < 0.7
  const colour = thin ? 'var(--ghost)' : ramp(posture)
  const big = size === 'lg'

  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Posture
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className={cn('font-bold tabular-nums', big ? 'text-5xl' : 'text-3xl')}
            style={{ color: colour }}
          >
            {posture}
          </span>
          {grade && (
            <span className={cn('font-bold', big ? 'text-2xl' : 'text-lg')} style={{ color: colour }}>
              {grade}
            </span>
          )}
        </div>
      </div>

      <div className="h-10 w-px self-center bg-border" aria-hidden />

      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Confidence
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className={cn('font-bold tabular-nums', big ? 'text-5xl' : 'text-3xl')}
            style={{ color: pct >= 90 ? 'var(--risk-low)' : pct >= 70 ? 'var(--risk-moderate)' : 'var(--ghost)' }}
          >
            {pct}
            <span className={big ? 'text-2xl' : 'text-lg'}>%</span>
          </span>
          {band && <span className="text-xs text-muted-foreground">{band}</span>}
        </div>
      </div>

      {thin && (
        <p className="w-full text-[12px] font-medium" style={{ color: 'var(--ghost)' }}>
          <Ghost className="mr-1 inline h-3.5 w-3.5" />
          Thin evidence. This posture is painted grey rather than green on purpose — at {pct}%
          coverage it describes the perimeter we could see, not the vendor.
        </p>
      )}
    </div>
  )
}

/**
 * The refusal, rendered IN THE SPACE THE NUMBER WOULD HAVE OCCUPIED.
 *
 * Not a greyed-out figure, which reads as "roughly this", and not a blank, which reads as "still
 * loading". Ghost and Blocked use off-ramp hues (grey and violet) so neither can be misread as a
 * point on the green-to-red scale: an unassessed vendor is not "moderately safe", and a blocked
 * one has not been assessed at all.
 */
export function GhostState({ kind, confidence, reason }) {
  const blocked = kind === 'blocked'
  const colour = blocked ? 'var(--blocked)' : 'var(--ghost)'
  const Icon = blocked ? Lock : Ghost
  return (
    <div
      className="flex items-start gap-3 rounded-xl border px-4 py-3.5"
      style={{ borderColor: colour, background: `color-mix(in srgb, ${colour} 8%, transparent)` }}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" style={{ color: colour }} />
      <div>
        <div className="text-sm font-bold" style={{ color: colour }}>
          {blocked ? 'Blocked — pending human adjudication' : 'Ghost — unassessed, not safe'}
        </div>
        <p className="mt-1 max-w-7xl text-[12px] leading-relaxed text-muted-foreground">
          {reason || (blocked
            ? 'A gate stopped this assessment before a posture was formed. There is no number here to soften — a person has to decide.'
            : `Evidence coverage${confidence != null ? ` (${Math.round(confidence * 100)}%)` : ''} is below the floor, so no posture is published. That is an ADVERSE result, not a neutral one.`)}
        </p>
      </div>
    </div>
  )
}

// ── the declaration prompt: the highest-value control in the app ───────────────────────────

const CRITICALITY = [
  ['low', 'Low', 'We could lose them for a month and cope'],
  ['medium', 'Medium', 'Disruptive within a week'],
  ['high', 'High', 'A business process stops'],
]
const SCOPE = [
  ['low', 'Low', 'No data of ours'],
  ['medium', 'Medium', 'Internal, non-sensitive'],
  ['high', 'High', 'Confidential or client material'],
  ['critical', 'Critical', 'Production customer data'],
]
const SUBSTITUTABILITY = [
  ['high', 'Easily replaced', ''],
  ['medium', 'Replaceable with effort', ''],
  ['low', 'Hard to replace', ''],
  ['sole_source', 'Sole source', 'Escalates the residual tier one band'],
]

/**
 * THE "SO WHAT" REFUSAL, AND THE FORM THAT RESOLVES IT.
 *
 * Where the inherent tier is undeclared, the So-what band renders THIS — not a blank, and not a
 * neutral grey placeholder. E10b's rule is that undeclared ≠ low, and the dangerous default is
 * low: every vendor nobody has classified would otherwise present as low-residual, and the ones
 * nobody has classified are disproportionately the ones nobody has looked at.
 *
 * `basis` is required and long-form on purpose. A declaration nobody can contest is a number, and
 * this system publishes no numbers nobody can contest.
 */
export function DeclareInherentPrompt({ vendorRef, onDeclared, compact }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    criticality: '', data_access_scope: '', substitutability: '',
    basis: '', declared_by: '', confirmed: false,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const valid = (form.criticality || form.data_access_scope)
    && form.basis.trim().length >= 40 && form.declared_by.trim().length >= 2

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const body = { basis: form.basis.trim(), declared_by: form.declared_by.trim(), confirmed: form.confirmed }
      if (form.criticality) body.criticality = form.criticality
      if (form.data_access_scope) body.data_access_scope = form.data_access_scope
      if (form.substitutability) body.substitutability = form.substitutability
      const res = await declareInherent(vendorRef, body)
      onDeclared?.(res)
      setOpen(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <div
        className="rounded-2xl border-2 border-dashed px-5 py-5"
        style={{ borderColor: 'var(--risk-moderate)', background: 'color-mix(in srgb, var(--risk-moderate) 7%, transparent)' }}
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--risk-moderate)' }} />
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-bold">We cannot tell you what this means to you.</h3>
            {!compact && (
              // The full list of what stays switched off is a tooltip. It matters, but this card
              // is the standing state on every undeclared vendor, so it earns one line, not five.
              <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground"
                title="Four things stay switched off until it is declared: the residual tier, the evidence pack's decision tags, the assessment depth, and this relationship's review cadence.">
                Residual risk needs your declared exposure.{' '}
                <strong className="text-foreground">Undeclared is not &ldquo;low&rdquo;</strong> — it
                is the question nobody has answered.
              </p>
            )}
            <button
              onClick={() => setOpen(true)}
              className="mt-3 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:opacity-95 active:scale-[0.98]"
            >
              Declare inherent exposure
              <ArrowRight className="h-4 w-4" />
            </button>
            <span className="ml-3 text-[11px] text-muted-foreground">
              ~2 minutes · does not re-scan · does not change the posture
            </span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border border-border bg-card p-5">
      <h3 className="text-sm font-bold">Declare inherent exposure</h3>
      <p className="mt-1 max-w-7xl text-[12px] leading-relaxed text-muted-foreground">
        Both inputs are yours and neither is inferred — how much a vendor&rsquo;s failure hurts YOU is
        not observable from outside. The tier is the <strong className="text-foreground">worse</strong>{' '}
        of the two, never an average: a vendor holding production data is a critical exposure even if
        the service is replaceable.
      </p>

      <Choice label="Business criticality" hint="How badly does their failure hurt us?"
        options={CRITICALITY} value={form.criticality}
        onChange={(v) => setForm({ ...form, criticality: v })} />

      <Choice label="Data access scope" hint="What do they hold for us?"
        options={SCOPE} value={form.data_access_scope}
        onChange={(v) => setForm({ ...form, data_access_scope: v })} />

      <Choice label="Substitutability" hint="Optional — how replaceable is the relationship?"
        options={SUBSTITUTABILITY} value={form.substitutability}
        onChange={(v) => setForm({ ...form, substitutability: v })} />

      <label className="mt-5 block">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Basis — why this exposure
        </span>
        <textarea
          rows={3} value={form.basis}
          onChange={(e) => setForm({ ...form, basis: e.target.value })}
          placeholder="The sentence a relationship owner would argue with. e.g. 'Holds the engagement record for every client assessment; delivery stops without it and the content is client-confidential.'"
          className="mt-1.5 w-full rounded-xl border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <span className={cn('text-[11px]', form.basis.trim().length >= 40 ? 'text-muted-foreground' : 'text-[var(--risk-high)]')}>
          {form.basis.trim().length}/40 minimum — a declaration nobody can contest is a number, not a basis
        </span>
      </label>

      <label className="mt-4 block">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Declared by
        </span>
        <input
          value={form.declared_by}
          onChange={(e) => setForm({ ...form, declared_by: e.target.value })}
          placeholder="Your name — one owner per number"
          className="mt-1.5 w-full rounded-xl border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </label>

      <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-xl border border-border/70 bg-secondary/30 px-3 py-2.5">
        <input
          type="checkbox" checked={form.confirmed}
          onChange={(e) => setForm({ ...form, confirmed: e.target.checked })}
          className="mt-0.5 h-4 w-4 accent-[var(--accent)]"
        />
        <span className="text-[12px] leading-relaxed">
          <strong>I am the accountable relationship owner.</strong>
          <span className="text-muted-foreground">
            {' '}Leave this unticked and the declaration is <em>provisional</em> — it still routes
            depth and publishes a residual tier, but every page that shows it says so.
          </span>
        </span>
      </label>

      {error && (
        <p className="mt-3 text-[12px] font-medium" style={{ color: 'var(--risk-critical)' }}>{error}</p>
      )}

      <div className="mt-5 flex items-center gap-3">
        <button
          type="submit" disabled={!valid || busy}
          className="inline-flex h-10 items-center rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-40"
        >
          {busy ? 'Declaring…' : 'Declare'}
        </button>
        <button
          type="button" onClick={() => setOpen(false)}
          className="text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function Choice({ label, hint, options, value, onChange }) {
  return (
    <div className="mt-5">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-[11px] text-muted-foreground">{hint}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map(([v, title, sub]) => (
          <button
            key={v} type="button"
            onClick={() => onChange(value === v ? '' : v)}
            className={cn(
              'rounded-xl border px-3 py-2 text-left transition',
              value === v
                ? 'border-accent bg-accent/10 ring-1 ring-accent'
                : 'border-border bg-card hover:border-accent/40',
            )}
          >
            <div className="text-[13px] font-semibold">{title}</div>
            {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Declared, but not by the accountable owner. MUTED, not warning-coloured — a provisional answer
 * is a real answer, and colouring it amber would tell a reader to distrust a figure that is
 * currently the best statement of exposure anyone has made.
 */
export function ProvisionalChip({ className }) {
  return (
    <span
      title="Declared on the inherent register, not yet confirmed by the accountable relationship owner. It routes assessment depth and publishes a residual tier; it is labelled because an unconfirmed answer read as a confirmed one is worse than either."
      className={cn(
        'inline-flex cursor-help items-center gap-1 rounded-full border border-border bg-secondary/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground',
        className,
      )}
    >
      <Info className="h-3 w-3" /> provisional
    </span>
  )
}

// ── now-what actions ──────────────────────────────────────────────────────────────────────

/**
 * A task with an owner and a date. Refuses to render without an owner.
 *
 * "Request their DMARC policy" is a task. "Request their DMARC policy — Procurement, by 14 Aug"
 * is a commitment. The backend supplies both halves (`ask_of_vendor`, `recheck_after`), so an
 * ownerless row here means a caller dropped one on the floor and should be told loudly.
 */
export function ActionRow({ n, title, detail, owner, due, href, onClick, count }) {
  if (!owner) {
    return (
      <div className="rounded-lg border border-dashed px-3 py-2 text-[12px]" style={{ borderColor: 'var(--risk-high)' }}>
        <strong>{title}</strong> — no owner supplied. An action without an owner is not an action;
        this is a bug in the caller, not a task.
      </div>
    )
  }
  const Wrapper = href || onClick ? 'button' : 'div'
  return (
    <Wrapper
      onClick={onClick}
      className={cn(
        'flex w-full items-start gap-3 rounded-xl border border-border/70 px-3.5 py-3 text-left',
        (href || onClick) && 'cursor-pointer transition hover:border-accent/50 hover:bg-secondary/40',
      )}
    >
      {n != null && (
        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-accent/12 font-mono text-[11px] font-bold text-accent">
          {String(n).padStart(2, '0')}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-[13px] font-semibold">{title}</span>
          {count != null && (
            <span className="font-mono text-[11px] text-muted-foreground">{count} item{count === 1 ? '' : 's'}</span>
          )}
        </div>
        {detail && <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{detail}</p>}
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
          <span className="font-semibold text-accent">{owner}</span>
          {due && <span className="text-muted-foreground">· {due}</span>}
        </div>
      </div>
      {(href || onClick) && <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />}
    </Wrapper>
  )
}

/** A hash-stamped receipt link. Monospace because a content hash in a proportional font is
 *  unverifiable by eye — that is a functional requirement, not a stylistic one. */
export function EvidenceLink({ id, source, onOpen }) {
  if (!id) return null
  return (
    <button
      onClick={() => onOpen?.(id)}
      className="inline-flex items-center gap-1.5 font-mono text-[10.5px] text-muted-foreground underline decoration-dotted underline-offset-2 transition hover:text-accent"
      title="Open the hash-stamped receipt this number came from"
    >
      <FileText className="h-3 w-3" />
      {source ? `${source} · ` : ''}{String(id).slice(0, 8)}
    </button>
  )
}

// ── refusals and empties ──────────────────────────────────────────────────────────────────

/**
 * P2's coverage statement, VERBATIM.
 *
 * Never paraphrased and never summarised. It is already the honest sentence about what the
 * assessment could not see; a shorter version of a carefully-worded limitation is a softer
 * limitation, and the softened one is the one that gets read.
 */
export function CoverageStatement({ coverage }) {
  const [open, setOpen] = useState(false)
  if (!coverage) return null
  const never = coverage.never_observable_from_outside || []
  const notRun = coverage.not_collected_this_run || []
  const noSource = coverage.held_no_lawful_free_source || []

  return (
    <div className="rounded-xl border border-border/70 bg-secondary/25 px-4 py-3.5">
      <div className="flex items-start gap-2.5">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            Coverage statement
          </div>
          <p className="mt-1 max-w-7xl text-[12.5px] leading-relaxed">{coverage.statement}</p>
          <button
            onClick={() => setOpen((o) => !o)}
            className="mt-2 inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent hover:underline"
          >
            {open ? 'Hide' : 'What was not checked, and why'}
            <ChevronDown className={cn('h-3.5 w-3.5 transition', open && 'rotate-180')} />
          </button>

          {open && (
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              {/* THREE BUCKETS, KEPT APART. "Did not run this time" is a re-run; "no lawful free
                  source" is a procurement decision; "never observable" is a fact about the method.
                  One list for all three would make a transient gap look permanent and a permanent
                  one look fixable. */}
              <Bucket title="Did not return this run" items={notRun}
                note="May close on a re-run." />
              <Bucket title="No lawful free source" items={noSource}
                note="A procurement decision, not a gap in the method." />
              <Bucket title="Never observable from outside" items={never}
                note="No re-run closes these. They need internal due diligence." />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Bucket({ title, items, note }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card px-3 py-2.5">
      <div className="text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">{title}</div>
      <div className="mt-1 font-mono text-lg font-bold tabular-nums">{items.length}</div>
      {items.length > 0 && (
        <ul className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
          {items.slice(0, 6).map((it) => <li key={it}>· {it}</li>)}
          {items.length > 6 && <li className="italic">+{items.length - 6} more</li>}
        </ul>
      )}
      <p className="mt-1.5 text-[10.5px] italic text-muted-foreground">{note}</p>
    </div>
  )
}

/**
 * TWO KINDS OF MISSING, KEPT VISUALLY APART.
 *
 * `unsupplied` — nobody has supplied it. A programme gap with a named owner. Renders as a chase.
 * `not_computable` — there is no population to measure. A fact about the book, not a chore.
 *
 * Same-looking empty cells would let an unmeasurable metric read as an unassigned task, which is
 * the collapse P2 refuses for its coverage buckets. And neither is ever a zero: a plausible
 * number in an empty cell is worse than the empty cell, because the empty cell asks a question.
 */
export function EmptyMetric({ kind, owner, reason }) {
  const chase = kind === 'unsupplied'
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-mono text-lg text-muted-foreground/50">—</span>
      <span
        className={cn('text-[11px] leading-snug', chase ? 'font-medium' : 'italic')}
        style={{ color: chase ? 'var(--risk-moderate)' : 'var(--muted-foreground)' }}
      >
        {chase ? <>Not supplied · <strong>{owner}</strong> owns it</> : (reason || 'No population to measure')}
      </span>
    </div>
  )
}

/**
 * A peer comparison and its caption, together or not at all.
 *
 * `caption` is required. "Industry average: 42" with no survey behind it is the version of EB's
 * unlabelled-cohort mistake that a board actually sees, and the caption is the only thing that
 * makes the number arguable.
 */
export function PeerFigure({ value, caption, unit }) {
  return (
    <div>
      <span className="font-mono text-sm font-semibold tabular-nums">{value}{unit}</span>
      <span className="ml-2 text-[10.5px] text-muted-foreground">{caption}</span>
    </div>
  )
}

/** Residual tier chip. Colour comes from the RESIDUAL cell, never from the posture — the whole
 *  point of E10b is that a strong posture against high exposure is not low residual risk. */
const RESIDUAL_TONE = {
  low: 'var(--risk-low)',
  low_medium: 'var(--risk-low)',
  medium: 'var(--risk-moderate)',
  medium_high: 'var(--risk-high)',
  high: 'var(--risk-high)',
  critical: 'var(--risk-critical)',
}

export function RiskBand({ tier, label, large }) {
  const tone = RESIDUAL_TONE[tier] || 'var(--ghost)'
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-lg font-bold uppercase tracking-wide',
        large ? 'px-4 py-2 text-lg' : 'px-2.5 py-1 text-[11px]',
      )}
      style={{ background: `color-mix(in srgb, ${tone} 16%, transparent)`, color: tone }}
    >
      {label || tier || 'Not declared'}
    </span>
  )
}

/**
 * INHERENT → RESIDUAL, AS ONE PAIR, NEVER TWO DISCONNECTED NUMBERS.
 *
 * docs/tprm_feedback_redesign.md §3.2: "shown as a pair … so the delta — what controls/mitigations
 * actually bought — is visible at a glance." Inherent is drawn muted (it is a client-supplied fact
 * about exposure, not a finding); only the residual side takes the risk colour, because E10b's
 * whole point is that a strong posture against a high inherent exposure is not automatically a low
 * residual number — the arrow is the only place that delta gets to exist as one shape.
 *
 * Undeclared renders as a plain dash pair, never a colour — the same "undeclared is not low" rule
 * `DeclareInherentPrompt` exists to enforce, restated here in one line instead of the full form.
 */
export function InherentResidualPair({ residual, provisional, size = 'sm' }) {
  const big = size === 'lg'
  if (!residual?.published) {
    return (
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Inherent → Residual
        </div>
        <div className={cn('font-bold text-muted-foreground', big ? 'text-lg' : 'text-sm')}>
          Not declared
        </div>
      </div>
    )
  }
  const tone = RESIDUAL_TONE[residual.residual] || 'var(--ghost)'
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        Inherent → Residual
      </div>
      <div className="mt-0.5 flex items-center gap-1.5">
        <span className={cn('font-semibold capitalize text-muted-foreground', big ? 'text-base' : 'text-[13px]')}>
          {residual.inherent?.label || '—'}
        </span>
        <ArrowRight className={cn('shrink-0 text-muted-foreground', big ? 'h-4 w-4' : 'h-3.5 w-3.5')} />
        <span className={cn('font-bold capitalize', big ? 'text-base' : 'text-[13px]')} style={{ color: tone }}>
          {residual.residual_label || residual.residual}
        </span>
        {provisional && <ProvisionalChip />}
        {residual.escalated_for_sole_source && (
          <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--risk-high)' }}
            title="Escalated one band — sole source">↑ sole source</span>
        )}
      </div>
    </div>
  )
}

/** A caveat list rendered verbatim. The backend's caveats are argued text, not filler. */
/**
 * A one-line disclosure. The default answer to "this detail matters but does not belong on the
 * page at rest".
 *
 * Standing explanatory paragraphs are how these screens got congested: every figure here carries
 * a real qualification, and printing all of them inline buries the numbers a reader came for —
 * at which point the qualifications stop being read, which is the opposite of the intent. A
 * closed row costs one line and keeps the detail one click away.
 */
export function Disclose({ label, tone, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="py-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground transition hover:text-accent"
        style={tone && !open ? { color: tone } : undefined}
      >
        <ChevronDown className={cn('h-3.5 w-3.5 transition', open && 'rotate-180')} />
        {label}
      </button>
      {open && <div className="mt-2 border-l-2 border-border pl-3">{children}</div>}
    </div>
  )
}

export function Caveats({ items, title = 'Read this with the number' }) {
  const [open, setOpen] = useState(false)
  if (!items?.length) return null
  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-accent"
      >
        <ShieldAlert className="h-3.5 w-3.5" />
        {title} ({items.length})
        <ChevronDown className={cn('h-3.5 w-3.5 transition', open && 'rotate-180')} />
      </button>
      {open && (
        <ul className="mt-2 space-y-2 border-l-2 border-border pl-3">
          {items.map((c, i) => (
            <li key={i} className="max-w-7xl text-[12px] leading-relaxed text-muted-foreground">{c}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** A tile on the "what needs a person" strip. At zero it is deliberately inert: an empty queue is
 *  not a win to celebrate, and giving it a call-to-action trains people to click through nothing. */
export function NeedsPersonTile({ value, label, sub, action, onClick, tone, alarm }) {
  const zero = value === 0 || value === '0'
  return (
    <button
      onClick={zero ? undefined : onClick}
      className={cn(
        'flex flex-col items-start rounded-2xl border px-4 py-3.5 text-left transition',
        zero ? 'cursor-default border-border/60 bg-card/50' : 'cursor-pointer border-border bg-card hover:border-accent/50 hover:shadow-sm',
      )}
      style={alarm ? { borderColor: 'var(--risk-critical)', background: 'color-mix(in srgb, var(--risk-critical) 7%, transparent)' } : undefined}
    >
      <div
        className="font-mono text-3xl font-bold tabular-nums"
        style={{ color: zero ? 'var(--muted-foreground)' : (tone || 'var(--foreground)') }}
      >
        {value}
      </div>
      <div className="mt-0.5 text-[12px] font-semibold leading-tight">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] leading-tight text-muted-foreground">{sub}</div>}
      <div className="mt-2 text-[11px] font-semibold text-accent">
        {zero ? <span className="text-muted-foreground">—</span> : <>→ {action}</>}
      </div>
    </button>
  )
}

export { Badge, Card, CheckCircle2 }
