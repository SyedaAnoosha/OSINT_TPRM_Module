import { useEffect, useState } from 'react'
import {
  Check, Loader2, Pencil, Sparkles, X,
} from 'lucide-react'
import {
  generateGapAnalysis, getGapAnalysisGate, getGapAnalysisHistory, recordGapAnalysisAction,
} from '../api.js'
import { Caveats, Disclose } from './primitives.jsx'
import { Card } from './ui.jsx'
import { cn } from '../lib/utils.js'

// ═══════════════════════════════════════════════════════════════════════════════════════════
// E14 — a third audience view whose renderer is a language model, over a finished assessment it
// never adjusts. `app/gap_analysis.py` owns the boundary this component must not weaken:
//
//   * every number here (posture, tiers, findings) was already rendered elsewhere on this page —
//     this panel adds PROSE about them, never a second copy of a figure;
//   * a recommendation is not a finding: it is marked AI-generated, and accepting/editing/
//     rejecting it never touches a score;
//   * the button is DISABLED WITH A STATED REASON, never silently absent — `gate.reasons` is
//     what renders when `gate.allowed` is false, not a generic "unavailable".
// ═══════════════════════════════════════════════════════════════════════════════════════════

export function GapAnalysisPanel({ vendorRef }) {
  // Tagged with the ref it describes — same discipline `AssurancePanel` uses — so a changed
  // `vendorRef` reads as not-loaded rather than briefly showing the previous vendor's gate/
  // history. `reloadKey` re-runs the effect after a generate/accept/edit/reject WITHOUT a
  // synchronous setState in the effect body, which is what a `load()` called straight from the
  // effect would otherwise trigger.
  const [reloadKey, setReloadKey] = useState(0)
  const [res, setRes] = useState({ ref: null })
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    Promise.all([getGapAnalysisGate(vendorRef), getGapAnalysisHistory(vendorRef)])
      .then(([gate, history]) => { if (live) setRes({ ref: vendorRef, gate, history }) })
      .catch(() => { if (live) setRes({ ref: vendorRef, gate: null, history: null }) })
    return () => { live = false }
  }, [vendorRef, reloadKey])

  const current = res.ref === vendorRef ? res : null
  const gate = current?.gate
  const history = current?.history
  const latest = history?.analyses?.[0]
  const reload = () => setReloadKey((k) => k + 1)

  const onGenerate = async () => {
    setGenerating(true); setError(null)
    try {
      await generateGapAnalysis(vendorRef)
      reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  const onAction = async (analysisId, recIndex, action, editedText) => {
    try {
      await recordGapAnalysisAction(vendorRef, analysisId, recIndex, { action, edited_text: editedText })
      reload()
    } catch (e) {
      setError(e.message)
    }
  }

  if (!gate) return null   // still loading, or the gate check itself failed — degrade to absent

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-border/60 px-5 py-3">
        <Sparkles className="h-4 w-4 shrink-0 text-accent" />
        <h3 className="text-sm font-semibold">Gap analysis &amp; recommendations</h3>
        <span className="text-[11px] text-muted-foreground">AI-generated — read layer only, never a second score</span>
        <div className="ml-auto">
          <button
            onClick={onGenerate}
            disabled={!gate.allowed || generating}
            title={!gate.allowed ? gate.reasons.join(' ') : undefined}
            className={cn(
              'inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-[12.5px] font-semibold transition',
              gate.allowed && !generating
                ? 'bg-primary text-primary-foreground hover:opacity-90'
                : 'cursor-not-allowed bg-secondary text-muted-foreground',
            )}
          >
            {generating
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…</>
              : <>{latest ? 'Regenerate' : 'Generate'} analysis</>}
          </button>
        </div>
      </div>

      <div className="px-5 py-4">
        {!gate.allowed && (
          <ul className="flex flex-col gap-1.5">
            {gate.reasons.map((r, i) => (
              <li key={i} className="text-[12px] leading-relaxed text-muted-foreground">
                <span className="font-semibold text-foreground">Not available — </span>{r}
              </li>
            ))}
          </ul>
        )}

        {error && (
          <p className="mb-3 text-[12px] leading-relaxed" style={{ color: 'var(--risk-high)' }}>{error}</p>
        )}

        {gate.allowed && gate.inherent_tier_provisional && (
          <p className="mb-3 text-[11.5px] italic text-muted-foreground">
            Inherent tier is provisional — recommendations are prioritised against it anyway; a
            provisional answer routes better than none, and it is labelled everywhere it appears.
          </p>
        )}

        {gate.allowed && !latest && !generating && (
          <p className="text-[12.5px] italic text-muted-foreground">
            Not yet generated. One button turns the assessment above into an executive summary and
            a prioritised, editable list of recommendations.
          </p>
        )}

        {latest && <AnalysisView analysis={latest} onAction={onAction} />}

        {history?.analyses?.length > 1 && (
          <Disclose label={`${history.analyses.length - 1} earlier analysis(es)`}>
            <ul className="flex flex-col gap-2">
              {history.analyses.slice(1).map((a) => (
                <li key={a.id} className="text-[11.5px] text-muted-foreground">
                  {new Date(a.created_at).toLocaleString()} · {a.provider}/{a.model}
                </li>
              ))}
            </ul>
          </Disclose>
        )}
      </div>
    </Card>
  )
}

function AnalysisView({ analysis, onAction }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-prose text-[13px] leading-relaxed">{analysis.executive_summary}</p>

      {analysis.parse_warning && (
        <p className="text-[11.5px] italic text-muted-foreground">{analysis.parse_warning}</p>
      )}

      {(analysis.gaps || []).length > 0 && (
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Where the gap is
          </div>
          <ul className="mt-1.5 flex flex-col gap-2">
            {analysis.gaps.map((g, i) => (
              <li key={i} className="rounded-lg border border-border/70 px-3 py-2 text-[12px] leading-relaxed">
                <span className="font-semibold">{g.theme}</span>
                <div className="mt-0.5 text-muted-foreground">
                  Observed: {g.what_we_observed} — Expected: {g.what_we_expected}
                </div>
                {g.why_it_matters && <div className="mt-0.5">{g.why_it_matters}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(analysis.recommendations || []).length > 0 && (
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Recommendations
          </div>
          <ul className="mt-1.5 flex flex-col gap-2">
            {analysis.recommendations.map((r, i) => (
              <RecommendationRow key={i} rec={r}
                onAction={(action, text) => onAction(analysis.id, i, action, text)} />
            ))}
          </ul>
        </div>
      )}

      <div className="text-[10.5px] text-muted-foreground">
        {analysis.provider}/{analysis.model} ·{' '}
        {analysis.provenance?.generated_at
          ? new Date(analysis.provenance.generated_at).toLocaleString()
          : (analysis.created_at ? new Date(analysis.created_at).toLocaleString() : null)}
        {analysis.dropped_evidence_ids > 0 && (
          <> · {analysis.dropped_evidence_ids} invented citation(s) dropped</>
        )}
      </div>

      <Caveats items={[
        'AI-generated prose over a finished, deterministic assessment. It never computes, adjusts '
        + 'or comments on a score — every number it discusses was formed upstream.',
        'A recommendation is not a finding — it is disposable and regenerable. Accept, edit or '
        + 'reject each one; the disposition is recorded as a permanent event either way.',
      ]} title="Read this with the recommendations" />
    </div>
  )
}

function RecommendationRow({ rec, onAction }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(rec.recommendation || '')
  const status = rec.status || 'pending'

  return (
    <li className="rounded-lg border border-border/70 px-3 py-2 text-[12px] leading-relaxed">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          {rec.priority && (
            <span className="mr-2 rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wider"
              style={{ background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }}>
              {rec.priority}
            </span>
          )}
          <span className="font-semibold">
            {status === 'edited' && rec.edited_text ? rec.edited_text : rec.recommendation}
          </span>
          {rec.rationale && <div className="mt-0.5 text-muted-foreground">{rec.rationale}</div>}
          {rec.effort && (
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              effort: {rec.effort}{rec.owner_hint ? ` · suggested owner: ${rec.owner_hint}` : ''}
            </div>
          )}
        </div>
        <StatusBadge status={status} />
      </div>

      {editing ? (
        <div className="mt-2 flex flex-col gap-2">
          <textarea
            value={text} onChange={(e) => setText(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-[12px]"
            rows={2}
          />
          <div className="flex gap-2">
            <button
              onClick={() => { setEditing(false); onAction('edited', text) }}
              className="rounded-lg bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground"
            >
              Save edit
            </button>
            <button onClick={() => setEditing(false)}
              className="rounded-lg border border-border px-2.5 py-1 text-[11px]">
              Cancel
            </button>
          </div>
        </div>
      ) : status === 'pending' && (
        <div className="mt-2 flex gap-2">
          <IconButton icon={Check} label="Accept" onClick={() => onAction('accepted')} />
          <IconButton icon={Pencil} label="Edit" onClick={() => setEditing(true)} />
          <IconButton icon={X} label="Reject" onClick={() => onAction('rejected')} />
        </div>
      )}
    </li>
  )
}

function IconButton({ icon: Icon, label, onClick }) {
  return (
    <button onClick={onClick}
      className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-[11px] font-medium transition hover:border-accent hover:text-accent">
      <Icon className="h-3 w-3" /> {label}
    </button>
  )
}

const STATUS_LABEL = { accepted: 'accepted', edited: 'edited', rejected: 'rejected', pending: 'pending' }
const STATUS_TONE = {
  accepted: 'var(--risk-low)', edited: 'var(--accent)', rejected: 'var(--muted-foreground)',
  pending: 'var(--ghost)',
}

function StatusBadge({ status }) {
  if (status === 'pending') return null
  return (
    <span className="shrink-0 rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wider"
      style={{ color: STATUS_TONE[status] }}>
      {STATUS_LABEL[status]}
    </span>
  )
}
