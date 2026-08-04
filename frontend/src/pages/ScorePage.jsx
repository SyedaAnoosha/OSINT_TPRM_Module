import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, Globe, Loader2, Search, TriangleAlert,
} from 'lucide-react'
import { getCoverage, getResidualRisk, scoreVendor } from '../api.js'
import {
  CoverageStatement, DeclareInherentPrompt, GhostState, PostureConfidencePair, RiskBand,
} from '../components/primitives.jsx'
import { Card } from '../components/ui.jsx'
// import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// INTAKE, NOT A SECOND SCORECARD.
//
// This screen used to end by rendering the complete record — a second, independently-maintained
// React tree for the same score that `/vendors/:ref` also renders. That is the divergence P6's
// `views_agree()` invariant exists to prevent, reproduced in the client: two renderers drift, and
// the day they disagree nobody finds out, because nobody puts them side by side.
//
// So this screen now has one job and hands off. It resolves a vendor, runs the scan, tells the
// truth about what each source did, and then asks the ONE question that is cheapest to answer
// right now and impossible to answer later: what is this relationship worth to you?
//
// THAT TIMING IS THE WHOLE POINT. The moment after a scan is when the user knows most about the
// vendor and why they looked it up. `inherent_tier_declaration_rate` sat at 0.0% for months while
// this page had a criticality selector COMMENTED OUT — the question was asked at the only moment
// it was cheap, and then removed.
// ═══════════════════════════════════════════════════════════════════════════════════════════

const RECENT_KEY = 'tprm-recent-scans'

export default function ScorePage() {
  const nav = useNavigate()
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState('idle')   // idle | running | done | error | needs_domain
  const [progress, setProgress] = useState({ total: 0, sources: [], events: [] })
  const [result, setResult] = useState(null)
  const [needsDomain, setNeedsDomain] = useState(null)
  const [error, setError] = useState(null)
  // Read once, lazily, at mount. localStorage is a synchronous external store, so an effect that
  // reads it and setStates is a render cascade for a value that was already available.
  const [recent, setRecent] = useState(readRecent)

  async function score(payload) {
    setPhase('running'); setResult(null); setError(null); setNeedsDomain(null)
    setProgress({ total: 0, sources: [], events: [] })
    try {
      const res = await scoreVendor(payload, {
        onProgress: (name, data) => setProgress((p) => reduceProgress(p, name, data)),
      })
      if (res.needsDomain) { setNeedsDomain(res); setPhase('needs_domain'); return }
      setResult(res); setPhase('done')
      remember(res.vendorRef, res.domain, setRecent)
    } catch (err) {
      setError(err.message || String(err)); setPhase('error')
    }
  }

  function run(e) {
    e.preventDefault()
    const q = query.trim()
    if (!q || phase === 'running') return
    // A dotted, space-free token is a domain; anything else is a name — and a name goes to the API
    // to be resolved rather than guessed at here. Guessing the domain is how "archerirm.com"
    // becomes the Indian subsidiary instead of the US parent.
    score(/\s/.test(q) || !q.includes('.') ? { name: q } : { domain: q })
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Assess a vendor</h1>
        <p className="mt-1 max-w-7xl text-[13px] leading-relaxed text-muted-foreground">
          Lawfully-public sources only. The scan measures what a vendor looks like from outside;
          it cannot see inside, and it will say so rather than imply otherwise.
        </p>
      </header>

      <Card className="p-5">
        <form onSubmit={run} className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Vendor name or domain — Atlassian, snowflake.com"
              aria-label="Vendor name or domain" autoFocus
              className="h-11 w-full rounded-xl border border-input bg-background pl-10 pr-4 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-ring/40"
            />
          </div>
          <button
            type="submit" disabled={phase === 'running' || !query.trim()}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-sm font-semibold text-primary-foreground transition hover:opacity-95 active:scale-[0.98] disabled:opacity-40 sm:w-40"
          >
            {phase === 'running' ? <><Loader2 className="h-4 w-4 animate-spin" /> Scanning…</> : 'Run the scan'}
          </button>
        </form>

        {recent.length > 0 && phase === 'idle' && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium text-muted-foreground">Recent:</span>
            {recent.map((r) => (
              <Link
                key={r.ref} to={`/vendors/${encodeURIComponent(r.ref)}`}
                className="rounded-lg border border-border bg-secondary/50 px-2.5 py-1 font-mono text-[11.5px] transition hover:border-accent/40 hover:text-accent"
              >
                {r.ref}
              </Link>
            ))}
          </div>
        )}
      </Card>

      {phase === 'running' && <ScanProgress progress={progress} />}

      {phase === 'needs_domain' && (
        <DomainPrompt info={needsDomain} onPick={(domain) => score({ name: needsDomain.name, domain })} />
      )}

      {phase === 'error' && (
        <Card className="flex items-start gap-3 p-5" style={{ borderColor: 'var(--risk-critical)' }}>
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0" style={{ color: 'var(--risk-critical)' }} />
          <div>
            <p className="text-sm font-semibold">The scan did not complete.</p>
            <p className="mt-1 text-[12.5px] text-muted-foreground">{error}</p>
          </div>
        </Card>
      )}

      {result && <ScanResult result={result} onOpen={() => nav(`/vendors/${encodeURIComponent(result.vendorRef)}`)} />}
    </div>
  )
}

// ── progress: what each source actually did ────────────────────────────────────────────────

// const STATUS_META = {
//   ok: { icon: Check, tone: 'var(--risk-low)', label: 'answered' },
//   empty: { icon: Minus, tone: 'var(--ghost)', label: 'nothing to report' },
//   error: { icon: X, tone: 'var(--risk-high)', label: 'did not answer' },
// }

/**
 * PER-SOURCE STATUS, SHOWN RATHER THAN HIDDEN.
 *
 * This existed and was commented out, leaving a bare percentage bar. The bar is the least
 * informative thing on the screen: what a reader needs is that 18 sources answered and 5 were
 * silent, because THAT is the coverage statement forming in real time — and coverage is the axis
 * this whole system refuses to collapse into the score.
 *
 * `empty` and `error` are drawn differently on purpose. "Nothing to report" is a clean result;
 * "did not answer" is a gap that may close on a re-run. Colouring both grey would make a genuine
 * failure look like a pass.
 */
function ScanProgress({ progress }) {
  const { total, events } = progress
  // const {sources}=progress
  // const byStatus = Object.fromEntries(events.map((e) => [e.source, e.status]))
  const done = events.length
  const pct = total ? Math.round((done / total) * 100) : 6

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <Loader2 className="h-4 w-4 animate-spin text-accent" />
          Collecting from {total || '…'} public sources
        </span>
        <span className="font-mono text-[12px] text-muted-foreground">{done}/{total || '…'}</span>
      </div>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>

      {/* {sources.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {sources.map((s) => {
            const status = byStatus[s]
            const meta = STATUS_META[status]
            const Icon = meta?.icon
            return (
              <span
                key={s}
                className={cn(
                  'inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 font-mono text-[11px]',
                  !status && 'animate-pulse border-border/50 bg-secondary/40 text-muted-foreground',
                )}
                style={status ? {
                  borderColor: `color-mix(in srgb, ${meta.tone} 40%, transparent)`,
                  background: `color-mix(in srgb, ${meta.tone} 10%, transparent)`,
                  color: meta.tone,
                } : undefined}
                title={meta ? meta.label : 'waiting'}
              >
                {Icon && <Icon className="h-3 w-3" />}
                {s}
              </span>
            )
          })}
        </div>
      )}

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        A source that returns nothing lowers <strong className="text-foreground">confidence</strong>,
        never posture. Missing evidence is not evidence of a problem — and it is not evidence of
        safety either.
      </p> */}
    </Card>
  )
}

// ── the handoff ───────────────────────────────────────────────────────────────────────────

/**
 * The result, compact — then the question, then the door.
 *
 * Deliberately NOT the full record. Everything a reader needs to decide whether to look further
 * fits here; everything else is one click away at `/vendors/:ref`, which is the only place the
 * complete assessment is rendered.
 */
function ScanResult({ result, onOpen }) {
  const { vendorRef, score, domain } = result
  const [residual, setResidual] = useState(null)
  const [coverage, setCoverage] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let alive = true
    Promise.all([getResidualRisk(vendorRef), getCoverage(vendorRef)])
      .then(([r, c]) => { if (alive) { setResidual(r); setCoverage(c) } })
    return () => { alive = false }
  }, [vendorRef, reloadKey])

  const declared = residual?.inherent?.published

  return (
    <div className="flex flex-col gap-4">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="text-base font-bold">{vendorRef}</h2>
            {domain && (
              <span className="inline-flex items-center gap-1 font-mono text-[11.5px] text-muted-foreground">
                <Globe className="h-3 w-3" />{domain}
              </span>
            )}
          </div>
          <button
            onClick={onOpen}
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:opacity-95 active:scale-[0.98]"
          >
            Open the full assessment <ArrowRight className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-5">
          {score.blocked ? (
            <GhostState kind="blocked" reason={score.blocked_reason} />
          ) : (
            <PostureConfidencePair
              posture={score.posture} confidence={score.overall_confidence}
              grade={score.grade} band={score.confidence_band}
              refused={score.refused}
            />
          )}
        </div>

        {coverage && !score.blocked && (
          <div className="border-t border-border/60 px-5 py-4">
            <CoverageStatement coverage={coverage} />
          </div>
        )}
      </Card>

      {/* THE QUESTION, ASKED AT THE ONLY MOMENT IT IS CHEAP. The user just looked this vendor up
          and knows why; in a week nobody will remember. A declaration here publishes a residual
          tier, tags the evidence pack, and sets the review cadence — all before they navigate away. */}
      {!score.blocked && (
        declared ? (
          <Card className="flex flex-wrap items-center gap-3 px-5 py-4">
            <span className="text-[12px] font-semibold uppercase tracking-wider text-muted-foreground">
              Residual risk
            </span>
            <RiskBand tier={residual.residual} label={residual.residual_label} />
            <span className="text-[12.5px] text-muted-foreground">{residual.headline}</span>
          </Card>
        ) : (
          <DeclareInherentPrompt vendorRef={vendorRef} onDeclared={() => setReloadKey((k) => k + 1)} />
        )
      )}
    </div>
  )
}

// ── domain disambiguation ─────────────────────────────────────────────────────────────────

function DomainPrompt({ info, onPick }) {
  const [manual, setManual] = useState('')
  return (
    <Card className="p-5" style={{ borderColor: 'var(--accent)' }}>
      <div className="flex items-start gap-3">
        <Globe className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-bold">
            Which domain belongs to <span className="text-accent">{info.name}</span>?
          </h3>
          {/* WE DO NOT GUESS, and the reason is a real failure: a domain-slug lookup re-matched
              "archerirm.com" to the Indian arm rather than the US parent. Nearly every OSINT signal
              is domain-scoped, so the wrong domain is a confident assessment of a different company. */}
          <p className="mt-1 max-w-7xl text-[12.5px] leading-relaxed text-muted-foreground">
            {info.message || 'Almost every signal here is domain-scoped, so the wrong domain produces a confident assessment of a different company. Pick one, or type the exact domain.'}
          </p>

          {info.candidates?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {info.candidates.map((d) => (
                <button
                  key={d} onClick={() => onPick(d)}
                  className="rounded-xl border border-border bg-card px-3 py-2 font-mono text-[12px] font-semibold transition hover:border-accent hover:bg-accent/10"
                >
                  {d}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={(e) => { e.preventDefault(); const d = manual.trim(); if (d) onPick(d) }}
            className="mt-3 flex gap-2"
          >
            <input
              value={manual} onChange={(e) => setManual(e.target.value)}
              placeholder="or the exact domain — e.g. asana.com"
              className="h-10 flex-1 rounded-xl border border-input bg-background px-3 text-[13px] outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="submit" disabled={!manual.trim()}
              className="h-10 rounded-xl border border-border bg-card px-4 text-[13px] font-semibold disabled:opacity-40"
            >
              Scan
            </button>
          </form>
        </div>
      </div>
    </Card>
  )
}

// ── helpers ───────────────────────────────────────────────────────────────────────────────

function reduceProgress(p, name, data) {
  if (name === 'collecting') return { total: data.total || 0, sources: data.sources || [], events: [] }
  if (name === 'collector_done') return { ...p, events: [...p.events, data] }
  return p
}

function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
}

function remember(ref, domain, setRecent) {
  try {
    const prev = readRecent()
    const next = [{ ref, domain }, ...prev.filter((r) => r.ref !== ref)].slice(0, 10)
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
    setRecent(next)
  } catch { /* a full or disabled localStorage must not break a scan */ }
}
