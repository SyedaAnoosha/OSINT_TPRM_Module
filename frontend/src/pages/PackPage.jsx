import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, ClipboardList, FileSignature, Loader2, } from 'lucide-react'
import { getEvidencePack, getExitReadiness, getExportView, getFlowdowns } from '../api.js'
import { Caveats } from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'
// import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// P3's evidence request pack and P6's two audience views — the Now-what actions as artefacts.
//
// P6 ships `views_agree()` as a backend invariant: the procurement and security renderings come
// from one immutable score and cannot quote different numbers. The UI cross-checks it anyway,
// because the day it fires is the day somebody signs off on a number the security team never saw.
//
// IT FIRED ON EVERY VENDOR. The check compared `view.posture` — which is a BLOCK object, not a
// scalar — with `!==`, a reference comparison that is always true for two separately-parsed
// objects. So the page withheld both renderings and accused the product of breaking its
// headline invariant, on the one screen whose job is to show that invariant holding. See
// `viewsDisagree` below.
//
// The lesson for anything else that mirrors a backend assertion in this UI: Python's `!=` on
// dicts compares by value, JavaScript's `!==` compares by reference. A literal translation of a
// backend equality check is not an equivalent check.
// ═══════════════════════════════════════════════════════════════════════════════════════════

export default function PackPage() {
  const { ref } = useParams()
  // const [view, setView] = useState('procurement')
  const [d, setD] = useState({ loading: true })

  useEffect(() => {
    Promise.all([getEvidencePack(ref), getExportView(ref, 'procurement'), getExportView(ref, 'security')])
      .then(([pack, procurement, security]) => setD({ loading: false, pack, procurement, security }))
  }, [ref])

  if (d.loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading the pack…
      </div>
    )
  }

  const disagree = viewsDisagree(d.procurement, d.security)

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link to={`/vendors/${encodeURIComponent(ref)}`} className="text-[12px] font-semibold text-accent hover:underline">
          ← {ref}
        </Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">Evidence request pack</h1>
        <p className="mt-1 max-w-7xl text-[13px] leading-relaxed text-muted-foreground">
          {d.pack?.summary || 'The questions worth asking, scoped to what actually failed.'}
        </p>
      </header>

      {/* The invariant, checked in the client too. */}
      {disagree && (
        <div className="rounded-2xl border-2 px-5 py-4" style={{ borderColor: 'var(--risk-critical)' }}>
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5" style={{ color: 'var(--risk-critical)' }} />
            <div>
              <h2 className="text-sm font-bold">The two views disagree. Neither is shown.</h2>
              <p className="mt-1 max-w-7xl text-[12.5px] leading-relaxed">
                Procurement and security are rendered from one immutable score and must quote the
                same numbers. They do not: <strong>{disagree}</strong>. Rendering either one would
                mean somebody signs off on a figure the other audience never saw.
              </p>
            </div>
          </div>
        </div>
      )}

      {!disagree && (
        <>
          {/* <div className="flex gap-2">
            {['procurement', 'security'].map((v) => (
              <button key={v} onClick={() => setView(v)}
                className={cn(
                  'rounded-xl border px-4 py-2 text-[13px] font-semibold capitalize transition',
                  view === v ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-card hover:border-accent/40',
                )}>
                {v}
              </button>
            ))}
            <p className="ml-2 self-center text-[11px] text-muted-foreground">
              Same data, two renderings. Section order is the argument and is not reordered here.
            </p>
          </div> */}

          {d.pack?.requests?.length > 0 && <Requests pack={d.pack} />}

          {/* The pack asks; the contract covers what an answer cannot close. Two different
              actions with two different owners, so they are two screens rather than one long one. */}
          <Link
            to={`/vendors/${encodeURIComponent(ref)}/contract`}
            className="flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-4 transition hover:border-accent/50"
          >
            <FileSignature className="h-4 w-4 text-accent" />
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold">What an answer cannot close</div>
              <p className="text-[11.5px] text-muted-foreground">
                Contract flow-downs and exit readiness · Legal
              </p>
            </div>
            <span className="text-[12px] font-semibold text-accent">→</span>
          </Link>
        </>
      )}
    </div>
  )
}

/** The client-side half of `views_agree()`. Returns a description of the first disagreement, or null. */
// The client-side mirror of the backend's `views_agree()` (app/audience_views.py).
//
// IT MUST READ THE SAME PLACE THE BACKEND READS. `view.posture` is a BLOCK — an object carrying
// posture, grade, confidence and the three refusal flags — not a scalar. This function used to do
// `o?.score?.posture ?? o?.posture`, and since no `score` key exists it fell through to the block
// OBJECT. Comparing two distinct objects with `!==` is a reference comparison and is always true,
// so the guard fired on EVERY vendor and printed "[object Object]".
//
// That is worse than having no guard at all. It withheld both renderings, and it accused the
// product of violating the one invariant it advertises most loudly — on a page whose entire job is
// to demonstrate that invariant holding.
//
// Compare the SAME FIELDS the backend compares, so the two checks cannot drift apart into a
// frontend that passes while `views_agree()` would fail.
const AGREEMENT_FIELDS = [
  ['posture', 'posture'],
  ['grade', 'grade'],
  ['confidence', 'confidence'],
  ['published', 'published'],
  ['blocked', 'blocked'],
  ['refused', 'refused'],
  ['ghost', 'ghost'],
]

function viewsDisagree(p, s) {
  if (!p || !s) return null

  const a = p.posture, b = s.posture
  // No posture block means the export shape changed under us. Say that, rather than reporting a
  // disagreement that was never measured — a guard that cannot run must not claim it passed.
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') {
    return 'the export response carries no posture block, so agreement could not be checked'
  }

  for (const [key, label] of AGREEMENT_FIELDS) {
    if (!Object.is(a[key], b[key])) {
      return `${label} reads ${fmt(a[key])} for procurement and ${fmt(b[key])} for security`
    }
  }
  if (p.vendor_ref !== s.vendor_ref) {
    return `vendor_ref reads ${fmt(p.vendor_ref)} for procurement and ${fmt(s.vendor_ref)} for security`
  }

  // THE FAILURE THIS WHOLE HELPER EXISTS FOR: a limitation stated to one audience and not the
  // other. Procurement carries the coverage statement as a section body; security carries it
  // top-level. Both are OBJECTS, and in Python `!=` on two dicts compares by value while in
  // JavaScript `!==` compares by reference — so the literal translation of the backend check is
  // always-true here. That is the same defect this function was just repaired for; comparing the
  // serialised form is what makes the two checks actually equivalent.
  const procCoverage = p.sections?.find((sec) => sec.key === 'coverage_statement')?.body
  if (!sameValue(procCoverage, s.coverage_statement)) {
    return 'the coverage statement differs between the two renderings'
  }
  return null
}

// Value equality for two JSON-derived values. Both sides are serialised by the same backend from
// the same object, so key order is identical and stringify is a sound comparison here — it would
// not be for values assembled independently on the client.
function sameValue(a, b) {
  if (a === b) return true
  if (a == null || b == null) return a == null && b == null
  return JSON.stringify(a) === JSON.stringify(b)
}

// `null` and `undefined` must not both render as "null" in an accusation of disagreement — the
// reader needs to see which side had the field at all.
function fmt(v) {
  if (v === undefined) return 'absent'
  if (v === null) return 'not published'
  return String(v)
}

function Requests({ pack }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border/60 px-5 py-3">
        <ClipboardList className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-bold">Ask the vendor</h2>
        <span className="ml-auto font-mono text-[12px] text-muted-foreground">
          {pack.question_count} question{pack.question_count === 1 ? '' : 's'}
        </span>
      </div>
      <div className="divide-y divide-border/40">
        {pack.requests.map((r, i) => (
          <div key={i} className="px-5 py-3.5">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-[10.5px] font-bold text-accent">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="text-[13px] font-semibold">{r.question}</span>
              {/* {r.recheck_after && (
                <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  re-check {r.recheck_after}
                </span>
              )}
              {r.posture_points_charged > 0 && (
                <span className="font-mono text-[10.5px] text-muted-foreground">
                  −{r.posture_points_charged} posture
                </span>
              )} */}
            </div>

            {/* WHAT WE SAW comes before WHY IT MATTERS. A vendor reading this should be able to
                check the observation against their own estate before being told what it implies. */}
            {/* {r.observed && (
              <p className="mt-1.5 font-mono text-[11.5px] leading-relaxed text-muted-foreground">
                {r.observed}
              </p>
            )} */}
            {r.why_it_matters && (
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{r.why_it_matters}</p>
            )}
            {r.accepts_as_refute && (
              <p className="mt-1.5 text-[11.5px] leading-relaxed">
                <strong className="text-foreground">Accepted as a refute:</strong>{' '}
                <span className="text-muted-foreground">{r.accepts_as_refute}</span>
              </p>
            )}
            <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[10.5px] text-muted-foreground">
              {r.category && <span className="capitalize">{r.category.replace(/_/g, ' ')}</span>}
              {r.severity && <span>· {r.severity}</span>}
              {/* {r.evidence_id && (
                <span className="font-mono">· receipt {String(r.evidence_id).slice(0, 8)}</span>
              )}
              {r.dispute_status && r.dispute_status !== 'none' && (
                <span className="font-semibold" style={{ color: 'var(--accent)' }}>· {r.dispute_status}</span>
              )} */}
            </div>
          </div>
        ))}
      </div>
      {pack.clean_signals_not_asked > 0 && (
        <div className="border-t border-border/60 bg-secondary/25 px-5 py-3">
          <p className="text-[11.5px] leading-relaxed text-muted-foreground">
            <strong className="text-foreground">{pack.clean_signals_not_asked} signals came back clean and are not asked about.</strong>{' '}
            A pack that asks everything is a questionnaire, and a questionnaire is what this system
            exists to make unnecessary.
          </p>
        </div>
      )}
      <Caveats items={pack.caveats} />
    </Card>
  )
}

// ── contract flow-downs + exit readiness ───────────────────────────────────────────────────

export function ContractPage() {
  const { ref } = useParams()
  const [d, setD] = useState({ loading: true })

  useEffect(() => {
    Promise.all([getFlowdowns(ref), getExitReadiness(ref)])
      .then(([flowdowns, exit]) => setD({ loading: false, flowdowns, exit }))
  }, [ref])

  if (d.loading) {
    return (
      <div className="flex items-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link to={`/vendors/${encodeURIComponent(ref)}`} className="text-[12px] font-semibold text-accent hover:underline">
          ← {ref}
        </Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">Contract and exit</h1>
        <p className="mt-1 max-w-7xl text-[13px] leading-relaxed text-muted-foreground">
          What a vendor response cannot close becomes a drafting point. These are observations
          turned into contract language — never legal advice, and never a clause anybody has to accept.
        </p>
      </header>

      {d.flowdowns && <FlowDowns f={d.flowdowns} />}
      {/* {d.exit && <ExitReadiness e={d.exit} />} */}
    </div>
  )
}

function FlowDowns({ f }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border/60 px-5 py-3">
        <FileSignature className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-bold">Contract flow-downs</h2>
        <span className="ml-auto font-mono text-[12px] text-muted-foreground">
          {f.count} clause{f.count === 1 ? '' : 's'} · table v{f.table_version}
        </span>
      </div>
      {f.summary && <p className="px-5 py-3 text-[12.5px] leading-relaxed">{f.summary}</p>}
      <div className="divide-y divide-border/40">
        {(f.flow_downs || []).map((c, i) => (
          <div key={i} className="px-5 py-3.5">
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              {String(c.family).replace(/_/g, ' ')}
            </span>
            {c.observed && (
              <p className="mt-2 text-[12.5px] font-medium leading-relaxed">{c.observed}</p>
            )}
            {/* The suggested protection is a DRAFTING POINT, not a clause anybody has to accept.
                Rendered as quoted text rather than as an instruction, because legal owns the words. */}
            {c.suggested_protection && (
              <p className="mt-2 rounded-lg border-l-2 border-accent bg-secondary/30 px-3 py-2 text-[12px] italic leading-relaxed">
                {c.suggested_protection}
              </p>
            )}
            {c.basis && (
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{c.basis}</p>
            )}
            {c.citations?.length > 0 && (
              <p className="mt-1 font-mono text-[10.5px] text-muted-foreground">
                cites {c.citations.join(', ')}
              </p>
            )}
          </div>
        ))}
      </div>
      <Caveats items={f.caveats} />
    </Card>
  )
}

// function ExitReadiness({ e }) {
//   const tone = e.alert_level === 'high' ? 'var(--risk-critical)'
//     : e.alert_level === 'medium' ? 'var(--risk-high)' : 'var(--risk-moderate)'
//   return (
//     <Card className="overflow-hidden">
//       <div className="flex items-center gap-2 border-b border-border/60 px-5 py-3">
//         <ShieldCheck className="h-4 w-4" style={{ color: tone }} />
//         <h2 className="text-sm font-bold">Exit readiness</h2>
//         {e.substitutability && (
//           <span className="rounded-lg px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider"
//             style={{ background: `color-mix(in srgb, ${tone} 15%, transparent)`, color: tone }}>
//             {e.substitutability.replace(/_/g, ' ')}
//           </span>
//         )}
//       </div>
//       <div className="px-5 py-4">
//         <p className="max-w-7xl text-[13px] font-medium leading-relaxed">{e.headline}</p>

//         {e.going_concern_standing && (
//           <p className="mt-3 text-[12px]">
//             <span className="text-muted-foreground">Going-concern standing: </span>
//             <strong className="capitalize">{e.going_concern_standing}</strong>
//           </p>
//         )}

//         <Section title="What travels with an exit" block={e.what_travels_with_an_exit}
//           listKey="dependency_providers" />
//         <Section title="Market substitutes" block={e.market_substitutes} />
//         {/* THE MOST USEFUL SECTION ON THE PAGE, and it is a list of things we deliberately do not
//             know. Switching cost and lock-in are contract terms, not observations — inferring them
//             would be our opinion published as the buyer's exposure. */}
//         <Section title="Not derivable from outside — ask, do not infer"
//           block={e.not_derivable_from_osint} listKey="items" muted />

//         <Caveats items={e.caveats} />
//       </div>
//     </Card>
//   )
// }

/**
 * An exit-readiness section. Each block is `{ <listKey>?: string[], note?, next_step? }` — the list
 * is the finding and the note is the argument, and the note is rendered even when the list is
 * empty, because "no substitutes were found" is itself the answer.
 */
// function Section({ title, block, listKey, muted }) {
//   if (!block) return null
//   const items = (listKey && block[listKey]) || []
//   const prose = block.note || block.next_step
//   if (!items.length && !prose) return null

//   return (
//     <div className="mt-4">
//       <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{title}</div>
//       {items.length > 0 && (
//         <ul className={cn('mt-1.5 space-y-1 text-[12px] leading-relaxed', muted && 'text-muted-foreground')}>
//           {items.map((it, i) => <li key={i}>· {it}</li>)}
//         </ul>
//       )}
//       {block.note && (
//         <p className="mt-1.5 max-w-7xl text-[11.5px] leading-relaxed text-muted-foreground">{block.note}</p>
//       )}
//       {block.next_step && (
//         <p className="mt-1.5 max-w-7xl text-[11.5px] leading-relaxed" style={{ color: 'var(--accent)' }}>
//           {block.next_step}
//         </p>
//       )}
//     </div>
//   )
// }
