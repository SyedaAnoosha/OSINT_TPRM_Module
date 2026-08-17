import { useEffect, useState } from 'react'
import { Building2, Users, Globe, Landmark, CalendarClock, Layers, Info, CloudOff, RotateCw, Ruler, Timer, BarChart3, Target, CheckCircle2, XCircle, CircleDashed, ChevronDown, ChevronUp } from 'lucide-react'
import { getProfile, getBenchmark, setVendorSize } from '../api.js'
import { Card, Badge, Button } from './ui.jsx'
import { cn, postureColor } from '../lib/utils.js'
import { CategoryRadar} from './BenchmarkCharts.jsx'

// WHO the vendor is, shown ABOVE the score — because a reader who sees "78" before they know
// whether they are looking at a mega-cap bank or a twelve-person food supplier has already
// misread it. Two invariants this component holds:
//
//   1. Source provenance is not surfaced on the card (a UI choice). It is not lost — every field's
//      `source`/`locator` still rides on the /profile response and the evidence pack, so any value
//      remains traceable for audit; it is simply not shown here.
//   2. Nothing here moved the score. The panel says so in as many words, because a "Revenue"
//      row sitting above a risk grade otherwise implies a relationship that does not exist.

const SECTOR_LABELS = {
  financial_services: 'Financial Services',
  healthcare: 'Healthcare & Life Sciences',
  technology: 'Technology & Software',
  telecommunications: 'Telecommunications',
  government: 'Government & Public Sector',
  education: 'Education & Research',
  retail: 'Retail & Consumer',
  manufacturing: 'Manufacturing & Industrial',
  food_agriculture: 'Food & Agriculture',
  professional_services: 'Professional & Business Services',
  transport_logistics: 'Transport & Logistics',
  energy_utilities: 'Energy & Utilities',
}

const EMPLOYEE_LABELS = {
  micro: '<20 staff',
  small: '20–199 staff',
  medium: '200–999 staff',
  large: '1k–10k staff',
  mega: '10k+ staff',
}

const REVENUE_LABELS = {
  micro: '<$2M rev',
  small: '$2–20M rev',
  medium: '$20–100M rev',
  large: '$100M–1B rev',
  mega: '$1B+ rev',
}

const REGION_LABELS = {
  anz: 'Australia & NZ',
  north_america: 'North America',
  uk_eu: 'UK & EU',
  apac: 'APAC',
  other: 'Other',
}

const CRITICALITY_TONE = {
  high: 'var(--risk-high, #dc2626)',
  medium: 'var(--risk-med, #d97706)',
  low: 'var(--risk-low, #16a34a)',
}

const fmtNumber = (n) => (typeof n === 'number' ? n.toLocaleString() : n)

// Headcount as a RANGE, not an exact figure. A Wikidata employee count is a point-in-time estimate
// (often years stale), so a precise "8,179" implies a certainty the source does not have — a band
// is the honest read, and it is also all the peer cohort ever uses. Familiar LinkedIn-style bins.
function employeeRange(n) {
  if (typeof n !== 'number') return null
  const bands = [
    [10, '1–10'], [50, '11–50'], [200, '51–200'], [500, '201–500'],
    [1000, '501–1,000'], [5000, '1,001–5,000'], [10000, '5,001–10,000'],
  ]
  for (const [cap, label] of bands) if (n <= cap) return label
  return '10,000+'
}

function fmtRevenue(profile) {
  const amount = profile?.revenue?.value
  if (typeof amount !== 'number') return null
  // The reported figure keeps its OWN currency. Conversion happens only to pick a size band,
  // never to show a number we invented from a rate that may be months stale.
  const currency = profile?.revenue_currency?.value || ''
  const units = [[1e9, 'B'], [1e6, 'M'], [1e3, 'K']]
  for (const [scale, suffix] of units) {
    if (amount >= scale) return `${currency} ${(amount / scale).toFixed(1)}${suffix}`.trim()
  }
  return `${currency} ${fmtNumber(amount)}`.trim()
}

function fmtAge(days) {
  if (typeof days !== 'number') return null
  const years = Math.floor(days / 365)
  return years >= 1 ? `${years} yr${years > 1 ? 's' : ''}` : `${days} days`
}

/** How stale a dated figure is, in years. Sources like Wikidata keep quantities as a time series,
 *  so a headcount can easily be a decade old — and a reader who cannot see that will read it as
 *  current. Anything two years or older is called out rather than merely footnoted. */
function ageOf(asOf) {
  if (!asOf) return null
  const year = Number(String(asOf).slice(0, 4))
  if (!year) return null
  const years = new Date().getFullYear() - year
  return { years, stale: years >= 2 }
}

/** One fact. The source is deliberately NOT shown on the card — for any field (industry, size,
 *  employees, country, domain age, revenue). It still travels with the record (the /profile API
 *  field and the evidence pack keep `source`/`locator`); it is just not surfaced here. The as-of
 *  date stays, because a stale figure that looks current also picks the wrong peer group. */
function Fact({ icon: Icon, label, field, value }) {
  const shown = value ?? field?.value
  if (shown === null || shown === undefined || shown === '') return null
  const age = ageOf(field?.as_of)

  return (
    <div className="flex flex-col justify-between rounded-xl border border-border/50 bg-secondary/30 p-3 min-w-[130px] flex-1 transition-all hover:bg-secondary/50 hover:border-border"
      title={field?.as_of ? `Reported as at ${field.as_of}` : undefined}>
      <div className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5 text-accent" />}
        {label}
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-1.5">
        <span className="truncate text-sm font-bold tracking-tight text-foreground">{shown}</span>
        {field?.as_of && (
          <span className={cn('shrink-0 text-[10px] font-medium px-1.5 py-0.2 rounded',
            age?.stale ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold' : 'text-muted-foreground')}>
            {field.as_of.slice(0, 7)}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * `showBenchmark` and `showMaturityGap` are separate switches, not one.
 *
 * The peer comparison moved to `PeerBenchmarkPanel`, which reads the v2 system — midrank ties,
 * `rank_of_n`, a reproducible cohort snapshot, per-cohort discrimination. The BASELINE maturity
 * gap has no v2 equivalent and is not a peer comparison at all: it measures the vendor against
 * published requirements, which is why it renders for a vendor with no cohort. It still arrives
 * on the (deprecated) v1 benchmark response, so this component still fetches that response — for
 * `maturity_gap` alone.
 */
export function VendorProfilePanel({ vendorRef, posture, showBenchmark = true,
                                     showMaturityGap = showBenchmark, benchmarkDepth = 'full' }) {
  const [profile, setProfile] = useState(null)
  const [benchmark, setBenchmark] = useState(null)
  const [status, setStatus] = useState('loading')
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let live = true
    getProfile(vendorRef)
      .then((p) => { if (live) { setProfile(p); setStatus(p ? 'ready' : 'empty') } })
      .catch(() => { if (live) setStatus('error') })
    getBenchmark(vendorRef).then((b) => live && setBenchmark(b)).catch(() => {})
    return () => { live = false }
  }, [vendorRef, nonce])

  if (status === 'error') {
    return (
      <Card className="overflow-hidden border-risk-high/30 bg-risk-high/5">
        <div className="flex flex-wrap items-start gap-3 px-5 py-4">
          <CloudOff className="mt-0.5 h-4 w-4 shrink-0 text-risk-high" />
          <div className="flex-1 min-w-[220px] text-xs leading-relaxed text-muted-foreground">
            <b className="text-foreground">Vendor info unavailable.</b> The profile store could not
            be reached, so firmographics and the peer benchmark are not shown for this vendor. This
            does not affect the score above — the profile is context, never a score input.
          </div>
          <Button variant="outline" size="sm" onClick={() => setNonce((n) => n + 1)}>
            <RotateCw className="h-3.5 w-3.5" /> Retry
          </Button>
        </div>
      </Card>
    )
  }

  if (!profile) return null

  const sector = profile.sector?.value
  const completenessPct = Math.round((profile.completeness || 0) * 100)

  return (
    <div className="flex flex-col gap-5">
      <Card className="overflow-hidden shadow-sm">
        <div className="p-6">
          {/* Header - no vendor name to avoid duplication with ExecutiveSummaryHero */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-5">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Vendor Firmographics
              </div>
              <div className="text-sm text-muted-foreground">
                Context, not score input — posture is unaffected
              </div>
            </div>
            {sector && (
              <Badge className="bg-accent/10 text-accent border-accent/20 px-3 py-1 text-xs">
                {SECTOR_LABELS[sector] || sector}
              </Badge>
            )}
          </div>

          {/* Grid of facts */}
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <Fact icon={Layers} label="Industry" field={profile.industry_label} />
            <Fact icon={Users} label="Employees" field={profile.employees}
              value={employeeRange(profile.employees?.value)} />
            <Fact icon={Building2} label="Revenue" field={profile.revenue}
              value={fmtRevenue(profile)} />
            <Fact icon={Globe} label="Country" field={profile.country} />
            <Fact icon={Landmark} label="Ownership" field={profile.ownership}
              value={profile.ownership?.value === 'listed' ? 'Public (listed)' : profile.ownership?.value} />
            <Fact icon={CalendarClock} label="Domain age" field={profile.domain_age_days}
              value={fmtAge(profile.domain_age_days?.value)} />
            {profile.criticality && (
              <div className="flex flex-col justify-between rounded-xl border border-border/50 bg-secondary/30 p-3 min-w-[130px] flex-1" title="Client-supplied — never inferred">
                <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Criticality
                </div>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className="text-sm font-bold capitalize"
                    style={{ color: CRITICALITY_TONE[profile.criticality] }}>
                    {profile.criticality}
                  </span>
                  <span className="text-[9.5px] text-muted-foreground">client-supplied</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Notice bar */}
        <div className="flex items-center justify-between gap-3 border-t border-border/60 bg-secondary/40 px-6 py-3 text-[11.5px] text-muted-foreground">
          <div className="flex items-center gap-2">
            <Info className="h-3.5 w-3.5 shrink-0 text-accent" />
            <span>
              Profile is <b className="text-foreground font-semibold">context, not score input</b> — posture is unaffected.
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[11px] font-medium">Completeness</span>
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-secondary">
              <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${completenessPct}%` }} />
            </div>
            <span className="text-[11px] font-bold text-foreground">{completenessPct}%</span>
          </div>
        </div>
      </Card>

      {showBenchmark && (
        <BenchmarkStrip profile={profile} benchmark={benchmark} posture={posture}
          depth={benchmarkDepth} vendorRef={vendorRef} reload={() => setNonce((x) => x + 1)} />
      )}
      {/* OUTSIDE the cohort guard, deliberately. The baseline needs no peers, so it must still
          render for a vendor whose industry could not be established or whose cohort is too thin —
          those are the cases where it is the only comparison we have. */}
      {showMaturityGap && (
        <MaturityGapPanel gap={benchmark?.maturity_gap} depth={benchmarkDepth} />
      )}
    </div>
  )
}

function quartileWord(q) {
  return q === 4 ? 'Top quartile' : q === 3 ? 'Upper-middle' : q === 2 ? 'Lower-middle'
    : q === 1 ? 'Bottom quartile' : '—'
}
function quartileTone(q) {
  return q >= 4 ? 'var(--risk-low, #16a34a)' : q === 3 ? 'var(--foreground)'
    : q === 2 ? 'var(--risk-med, #d97706)' : 'var(--risk-high, #dc2626)'
}

// `--risk-med` is not a defined token (the variable is `--risk-moderate`), and unlike the other
// uses of that name in this file this one carried no fallback — so the badge rendered colourless.
function ProvisionalBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
      style={{ background: 'color-mix(in srgb, var(--risk-moderate) 15%, transparent)', color: 'var(--risk-moderate)' }}
      title="This cohort only just cleared the minimum — one peer joining or leaving could move the percentile.">
      <Timer className="h-3 w-3" /> provisional
    </span>
  )
}

function AddSizePanel({ vendorRef, reload }) {
  const [size, setSize] = useState('')
  const [state, setState] = useState('idle')
  const [error, setError] = useState(null)

  async function submit() {
    if (!size) return
    setState('sending'); setError(null)
    try {
      await setVendorSize(vendorRef, size)
      setState('idle')
      reload?.()
    } catch (e) {
      setError(e.message || String(e)); setState('error')
    }
  }

  return (
    <div className="text-xs p-1">
      <div className="flex items-start gap-2.5">
        <div className="p-2 rounded-xl bg-accent/10 text-accent">
          <Ruler className="h-4 w-4 shrink-0" />
        </div>
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          <b className="text-foreground font-semibold">No peer group yet.</b> Public sources published this
          vendor&apos;s industry but not its size. Know the size or contract entity? Add it to compare with peers. <b className="text-foreground font-semibold">It
          changes no score</b> — size never reaches the posture.
        </p>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 pl-9">
        <select value={size} onChange={(e) => setSize(e.target.value)}
          aria-label="Vendor size band"
          className="h-9 rounded-xl border border-input bg-card px-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <option value="">Select size band…</option>
          <option value="micro">Micro · under 20</option>
          <option value="small">Small · 20–199</option>
          <option value="medium">Medium · 200–999</option>
          <option value="large">Large · 1k–10k</option>
          <option value="mega">Mega · 10k+</option>
        </select>
        <Button size="sm" onClick={submit} disabled={!size || state === 'sending'}>
          {state === 'sending' ? 'Adding…' : 'Add size band'}
        </Button>
        <span className="text-[11px] text-muted-foreground">recorded as client-supplied</span>
      </div>
      {error && <div className="mt-1.5 pl-9 text-[11px] font-semibold text-risk-high">{error}</div>}
    </div>
  )
}

function StatTile({ label, value, sub, tone, hint }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-secondary/20 p-4 transition-all hover:bg-secondary/40 hover:border-border" title={hint}>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1.5 text-3xl font-black leading-none tracking-tight tabular-nums"
        style={tone ? { color: tone } : undefined}>{value}</div>
      {sub && <div className="mt-1.5 text-[11px] font-medium text-muted-foreground">{sub}</div>}
    </div>
  )
}

function FramedChart({ title, hint, children }) {
  return (
    <figure className="rounded-2xl border border-border/70 bg-card p-5 shadow-xs transition-all hover:border-border">
      <figcaption className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground"
        title={hint}>{title}</figcaption>
      {children}
    </figure>
  )
}

// "How to read this" — a collapsible explainer that sits with the charts, so a reader (or a
// reviewer) can decode each visual in context instead of being handed a separate document. Every
// line is a plain-English "what it is + how to read it"; the swatches echo the charts' own marks.
// const GUIDE_ITEMS = [
//   {
//     key: 'gauge', title: 'Percentile gauge',
//     swatch: <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: 'var(--accent)' }} />,
//     body: (
//       <>You score higher than that percent of your peers. The <b>±N</b> beside it is the finest step
//       this many peers can express — precision stated honestly, not a rounded-off number.</>
//     ),
//   },
//   {
//     key: 'box', title: 'Peer distribution (box plot)',
//     swatch: <span className="inline-block h-2.5 w-4 rounded-sm border" style={{ borderColor: 'var(--muted-foreground)' }} />,
//     body: (
//       <>The <b>box</b> is the middle 50% of peers; the <b>dark line</b> is the peer median; the{' '}
//       <b style={{ color: 'var(--accent)' }}>coloured mark</b> is this vendor. To the right of the box
//       = ahead of most peers; inside = middle of the pack.</>
//     ),
//   },
//   {
//     key: 'radar', title: 'Category radar',
//     swatch: <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: 'var(--muted-foreground)' }} />,
//     body: (
//       <><b style={{ color: 'var(--accent)' }}>Solid</b> = this vendor, <b>dashed grey</b> = the peer
//       median, per scoring category. Where the shape pushes <b>outside</b> the grey it leads; where it
//       caves <b>inside</b>, it lags.</>
//     ),
//   },
//   {
//     key: 'bars', title: 'Control prevalence',
//     swatch: <span className="text-[11px] font-bold" style={{ color: 'var(--risk-high)' }}>✗</span>,
//     body: (
//       <>Each bar is the <b>share of peers that pass a control</b>; the <b>✓/✗</b> is whether this
//       vendor passes it. A red row means it falls short of its own industry — the sharpest, most
//       actionable line.</>
//     ),
//   },
//   {
//     key: 'tiles', title: 'The four tiles',
//     swatch: <BarChart3 className="h-3 w-3 text-accent" />,
//     body: (
//       <>Your <b>score</b> against the <b>peer median</b>, your <b>quartile</b> (4 = top 25%), and the{' '}
//       <b>gap</b> to the median (green above, red below).</>
//     ),
//   },
//   {
//     key: 'honest', title: 'Read it honestly',
//     swatch: <Info className="h-3 w-3 text-muted-foreground" />,
//     // body: (
//     //   <>Peers are vendors <b>this deployment happened to score</b> — a convenience sample, not an
//     //   industry census. The absolute grade stands on its own; this panel only <b>reads</b> it.{' '}
//     //   <b>Nothing here changed the score.</b></>
//     // ),
//   },
// ]

// function BenchmarkGuide() {
//   const [open, setOpen] = useState(false)
//   return (
//     <div className="rounded-xl border border-border bg-secondary/20">
//       <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
//         className="flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left">
//         <span className="flex items-center gap-2 text-[12px] font-semibold text-muted-foreground">
//           <HelpCircle className="h-4 w-4 text-accent" /> How to read this benchmark
//         </span>
//         <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform', open && 'rotate-180')} />
//       </button>
//       {open && (
//         <div className="grid gap-3 border-t border-border px-4 py-3.5 sm:grid-cols-2">
//           {GUIDE_ITEMS.map((it) => (
//             <div key={it.key} className="flex gap-2.5">
//               <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center">{it.swatch}</span>
//               <div className="text-[12px] leading-relaxed text-muted-foreground">
//                 <div className="font-semibold text-foreground">{it.title}</div>
//                 {it.body}
//               </div>
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   )
// }

function BenchmarkStrip({ profile, benchmark, posture, depth = 'full', vendorRef, reload }) {
  const cohort = profile?.cohort
  const sector = profile?.sector?.value

  if (!cohort) {
    // A sector but no cohort means size is the only missing piece — offer to add it. No sector at
    // all means size cannot help (a peer group needs an industry too), so say that instead.
    return (
      <Card className="p-5">
        {sector ? (
          <AddSizePanel vendorRef={vendorRef} reload={reload} />
        ) : (
          <p className="text-[13px] text-muted-foreground">
            <b className="text-foreground">No peer cohort.</b> This vendor&apos;s industry could not be
            established from public sources, so it has an absolute grade and no comparison — and a size
            would not help, because a peer group needs an industry too.
          </p>
        )}
      </Card>
    )
  }

  // All four factors, with unknown size dimensions shown as such rather than quietly dropped —
  // "revenue unknown" is a fact about the evidence, and hiding it would overstate the match.
  const cohortLabel = [
    SECTOR_LABELS[cohort.sector] || cohort.sector,
    cohort.employee_band ? EMPLOYEE_LABELS[cohort.employee_band] : 'headcount unknown',
    cohort.revenue_band ? REVENUE_LABELS[cohort.revenue_band] : 'revenue unknown',
    REGION_LABELS[cohort.region] || cohort.region,
  ].join(' · ')

  const n = benchmark?.stats?.n ?? 0
  const median = benchmark?.stats?.median
  const available = benchmark?.available
  const sizeBadge = profile?.size_client_supplied
  const variance = benchmark?.variance_from_median
  const varianceText = variance > 0 ? `+${variance}` : variance < 0 ? `${variance}` : '0'
  const varianceTone = variance > 0 ? 'var(--risk-low, #16a34a)'
    : variance < 0 ? 'var(--risk-high, #dc2626)' : 'var(--foreground)'

  // MINIMAL (executive): one clean line — quartile + variance, no stats to parse.
  if (depth === 'minimal') {
    return (
      <Card className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-4">
        {available ? (
          <>
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Peer standing</span>
            <span className="text-lg font-bold" style={{ color: quartileTone(benchmark.quartile) }}>
              {quartileWord(benchmark.quartile)}
            </span>
            <span className="text-sm text-muted-foreground">
              {varianceText} vs peer median · n={n}
            </span>
            {sizeBadge && <span className="text-[11px] text-muted-foreground">· client-supplied size</span>}
            {benchmark.provisional && <ProvisionalBadge />}
          </>
        ) : (
          <p className="text-[13px] text-muted-foreground">
            <b className="text-foreground">No peer comparison</b> — {benchmark?.reason || 'insufficient peers'}.
          </p>
        )}
      </Card>
    )
  }

  // SIMPLE (procurement) and FULL (analyst/risk) — a spacious card with a header band, a hero
  // gauge + KPI row, and (full only) the charts, each in its own frame.
  return (
    <Card className="overflow-hidden">
      {/* Header band */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-secondary/30 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
            <BarChart3 className="h-[18px] w-[18px] text-accent" />
          </div>
          <div>
            <div className="text-sm font-bold">Peer benchmark</div>
            <div className="text-[11px] text-muted-foreground">{cohortLabel} · n={n}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {sizeBadge && (
            <Badge className="gap-1" title="The peer group rests on a size you supplied, not an observed one. The posture is unaffected.">
              <Ruler className="h-3 w-3" /> client-supplied size
            </Badge>
          )}
          {benchmark?.provisional && <ProvisionalBadge />}
          {/* Labelled "comparison strength", NOT "confidence". The scorecard already shows a
              Confidence axis meaning something else entirely — evidence coverage for this vendor —
              and two different quantities sharing one word on one page is a reading error waiting
              to happen. The API field stays `benchmark.confidence`; only the label changes.
              Deliberately not called "Assurity": that name is reserved for the proposed third axis
              covering a vendor's own assurance artefacts (ISO 27001, SOC 2, VDP). */}
          {benchmark?.confidence != null && (
            <span className="text-[11px] text-muted-foreground"
              title="How much weight this COMPARISON bears — sample size, whether the peer group had to be widened, and how fresh and well-evidenced the peers are. Separate from the score's own Confidence, which is this vendor's evidence coverage.">
              comparison strength {Math.round(benchmark.confidence * 100)}% ({benchmark.confidence_band})
            </span>
          )}
        </div>
      </div>

      {available ? (
        <div className="flex flex-col gap-6 p-6">
          {benchmark.widened && (
            <div className="rounded-lg bg-secondary/60 px-3 py-2 text-[12px]">
              <b>Wider peer group used:</b> {benchmark.level}. The exact match was too thin.
            </div>
          )}

          {/* KPI row. NOT wrapped in a `sm:grid-cols-[auto_1fr]` two-column grid any more: the
              percentile gauge that used to occupy the first column is commented out, which left
              this row as the sole child of an `auto` track — so it shrank to its content width and
              bunched against the left edge instead of spanning the card. */}
          <div className="grid grid-cols-2 gap-10 lg:grid-cols-4">
            <StatTile label="Vendor score" value={posture} tone={postureColor(posture)} />
            <StatTile label="Peer median" value={median} />
            <StatTile label="Quartile" value={<>{benchmark.quartile}<span className="text-base text-muted-foreground">/4</span></>}
              sub={quartileWord(benchmark.quartile)} tone={quartileTone(benchmark.quartile)} />
            <StatTile label="vs peers" value={varianceText} tone={varianceTone}
              sub={variance > 0 ? 'above median' : variance < 0 ? 'below median' : 'at median'} />
          </div>

          {/* FULL depth only (analyst/risk): the charts and per-category detail, each framed. */}
          {depth === 'full' && (
            <>
              {/* <FramedChart title="Where you sit in the peer spread"
                hint="Box = middle 50% of peers; line = peer median; accent tick = you">
                <DistributionBox stats={benchmark.stats} posture={posture} />
              </FramedChart> */}

              {benchmark.outlier && (
                <div className="rounded-lg px-3 py-2 text-[12px] font-medium"
                  style={{ background: 'color-mix(in srgb, var(--risk-high) 12%, transparent)',
                    color: 'var(--risk-high)' }}>
                  Outlier — below the normal range for this peer group. Being far behind one&apos;s own
                  industry is a finding in itself, even where the absolute score looks moderate.
                </div>
              )}

              {/* Single column while the prevalence chart beside it stays commented out — a
                  two-column grid with one child left half the card empty. */}
              <div className="grid gap-6">
                <FramedChart title="Category posture · you vs peer median">
                  <CategoryRadar categories={benchmark.categories} />
                </FramedChart>
                {/* <FramedChart title="Controls · You vs your industry">
                  <PrevalenceBars signals={benchmark.signals} />
                </FramedChart> */}
              </div>

              {/* The numeric per-category detail with gap drivers, for readers who want the exact
                  figures the polygon only shows in shape. */}
              {/* <CategoryComparison categories={benchmark.categories} /> */}
            </>
          )}

          {benchmark.expected_posture != null && (
            <p className="text-[11px] text-muted-foreground">
              Expected for this sector: <b>{benchmark.expected_posture}</b> — {benchmark.expected_basis}
            </p>
          )}

          <Caveats items={benchmark?.caveats} />
        </div>
      ) : (
        <div className="p-6">
          <p className="text-[13px] text-muted-foreground">
            <b className="text-foreground">No comparison published.</b> {benchmark?.reason || 'insufficient peers'}.
            The absolute grade stands on its own; a median over a handful of vendors would be noise
            presented as precision.
          </p>
          <Caveats items={benchmark?.caveats} />
        </div>
      )}

      {/* Always available on the card — "how to read this benchmark" — so the explanation is never
          buried behind a role or a populated cohort. Collapsed by default; open to decode each mark. */}
      {/* <div className="border-t border-border px-5 py-3">
        <BenchmarkGuide />
      </div> */}
    </Card>
  )
}

/** Per-category variance — the actionable half. "Your cyber hygiene is below peers but your
 *  business stability is above" tells a reader what to raise with the vendor; a single overall
 *  variance does not. Categories no peer covered are omitted rather than shown as zero. */
// function CategoryComparison({ categories }) {
//   const all = categories || []
//   const rows = all.filter((c) => c.median != null && c.n > 0)
//   // Categories the vendor HAS but no peer covered (n = 0). The overall percentile can be available
//   // while a specific category has no peer coverage — and hiding those categories would let a reader
//   // assume every category was benchmarked. Naming them is the honest "overall yes, this one no".
//   const uncovered = all.filter((c) => c.posture != null && (c.n ?? 0) === 0)
//   if (!rows.length && !uncovered.length) return null

//   return (
//     <div className="mt-3 border-t border-border pt-3">
//       <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
//         By category · you vs peer median
//       </div>
//       <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
//         {rows.map((c) => {
//           const delta = c.variance_from_median
//           const tone = delta > 0 ? 'var(--risk-low, #16a34a)'
//             : delta < 0 ? 'var(--risk-high, #dc2626)' : 'inherit'
//           return (
//             <div key={c.category} className="flex items-baseline justify-between gap-3 text-xs"
//               title={`${c.n} peer${c.n === 1 ? '' : 's'} covered this category`}>
//               <span className="truncate text-muted-foreground">
//                 {String(c.category).replace(/_/g, ' ')}
//               </span>
//               <span className="shrink-0 font-mono">
//                 {c.posture} vs {c.median}
//                 <b className="ml-1.5" style={{ color: tone }}>
//                   {delta > 0 ? `+${delta}` : delta}
//                 </b>
//                 {c.percentile != null && (
//                   <span className="ml-1.5 text-muted-foreground">{c.percentile}th</span>
//                 )}
//               </span>
//             </div>
//           )
//         })}
//         {/* A gap with no named cause is a number; a gap with three named causes is a to-do list. */}
//         {/* {rows.filter((c) => c.gap_drivers?.length).map((c) => (
//           <div key={`${c.category}-drivers`} className="sm:col-span-2 text-[11px] text-muted-foreground">
//             <b>{String(c.category).replace(/_/g, ' ')}</b> gap driven by:{' '}
//             {c.gap_drivers.join(' · ')}
//           </div>
//         ))} */}
//       </div>

//       {/* The explicit "overall available, this category isn't" line. Categories the vendor has but
//           no peer covered are NAMED, not dropped — otherwise a reader assumes every category was
//           benchmarked and reads a partial comparison as a complete one. */}
//       {uncovered.length > 0 && (
//         <p className="mt-2 text-[11px] text-muted-foreground">
//           <b>Not benchmarked (no peer coverage):</b>{' '}
//           {uncovered.map((c) => String(c.category).replace(/_/g, ' ')).join(' · ')}.
//         </p>
//       )}
//     </div>
//   )
// }

/** Everything a reader needs to read the comparison correctly. These are UI requirements, not
 *  footnotes — a widened, small or thinly-evidenced cohort that presents itself as a clean
 *  percentile is precisely the black-box comparison this project refuses to ship. */
// --------------------------------------------------------------------- target maturity
//
// The reading that does NOT depend on the peer pool. It is rendered outside `BenchmarkStrip`'s
// cohort guard on purpose: a vendor with no industry, or with too few peers to publish a
// percentile, is exactly the case this measure exists to answer, and putting it behind the same
// `if (!cohort)` early-return would have hidden it precisely when it is the only thing we can say.

const CONTROL_LABELS = {
  dmarc: 'DMARC enforcement',
  spf: 'SPF policy',
  tls_version: 'TLS version',
  cert_validity: 'Certificate validity',
  hsts: 'HSTS',
  kev_listed_cve: 'Known-exploited vulnerabilities',
  vd_program: 'Vulnerability disclosure programme',
  security_txt: 'security.txt',
  cert_posture: 'Independent certification',
}

const STATUS_META = {
  meets: { word: 'Met', tone: 'var(--risk-low)', icon: CheckCircle2 },
  partial: { word: 'Partial', tone: 'var(--risk-moderate)', icon: CircleDashed },
  gap: { word: 'Not met', tone: 'var(--risk-high)', icon: XCircle },
  not_yet_attainable: { word: 'Not yet attainable', tone: 'var(--muted-foreground)', icon: Timer },
  unchecked: { word: 'Not observed', tone: 'var(--muted-foreground)', icon: CloudOff },
}

const controlLabel = (signal) => CONTROL_LABELS[signal]
  || String(signal || '').replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

function MaturityGapPanel({ gap, depth = 'full' }) {
  const [open, setOpen] = useState(false)
  if (!gap) return null

  if (!gap.available) {
    return (
      <Card className="flex items-center gap-3 rounded-xl bg-secondary/30 px-5 py-4 text-sm text-muted-foreground">
        <Target className="h-5 w-5 shrink-0 text-muted-foreground" />
        <div>
          <b className="text-foreground">No baseline reading.</b> {gap.reason
            || 'too few baseline controls could be observed'}. Stating a maturity position from a
          couple of checks would be the same false precision as a median over three vendors.
        </div>
      </Card>
    )
  }

  const pct = Math.round((gap.attainment ?? 0) * 100)
  const tone = pct >= 85 ? 'var(--risk-low)' : pct >= 60 ? 'var(--risk-moderate)' : 'var(--risk-high)'
  const misses = gap.controls?.filter((c) => c.status === 'gap' || c.status === 'partial') ?? []
  const excluded = gap.controls?.filter(
    (c) => c.status === 'not_yet_attainable' || c.status === 'unchecked') ?? []

  // MINIMAL (executive): the headline only — how many of the expected controls are in place.
  if (depth === 'minimal') {
    return (
      <Card className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-4">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Baseline controls
        </span>
        <span className="text-lg font-bold" style={{ color: tone }}>{gap.met}/{gap.applicable}</span>
        <span className="text-sm text-muted-foreground">
          met · measured against published requirements, not against peers
        </span>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 bg-gradient-to-r from-secondary/30 to-secondary/10 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/15 ring-1 ring-accent/30 text-accent">
            <Target className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-bold text-foreground">Baseline Maturity</div>
            <div className="text-[11px] text-muted-foreground">
              Measured against published requirements — no peers involved
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-3xl font-black tabular-nums" style={{ color: tone }}>
              {gap.met}<span className="text-base text-muted-foreground">/{gap.applicable}</span>
            </div>
            <div className="text-xs text-muted-foreground">{pct}% attainment</div>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Progress bar */}
        <div className="mb-5">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-semibold uppercase tracking-wider text-muted-foreground">Overall attainment</span>
            <span className="font-bold" style={{ color: tone }}>{pct}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%`, background: tone }}
            />
          </div>
        </div>

        {/* Control status breakdown */}
        {misses.length > 0 && (
          <div className="mb-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Gaps and partials ({misses.length})
              </span>
              <button
                onClick={() => setOpen((v) => !v)}
                className="flex items-center gap-1 text-xs font-medium text-accent hover:underline"
              >
                {open ? 'Hide' : 'Show'} details
                {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
              </button>
            </div>
            {open && (
              <div className="flex flex-col gap-2">
                {misses.map((c) => {
                  const meta = STATUS_META[c.status] || {}
                  const Icon = meta.icon
                  return (
                    <div key={c.signal} className="flex items-center gap-3 rounded-lg bg-secondary/30 px-4 py-3 text-sm">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" style={{ background: `color-mix(in srgb, ${meta.tone} 15%, transparent)`, color: meta.tone }}>
                        {Icon && <Icon className="h-4 w-4" />}
                      </div>
                      <div className="flex-1">
                        <div className="font-semibold text-foreground">{controlLabel(c.signal)}</div>
                        <div className="text-xs text-muted-foreground">{meta.word}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {excluded.length > 0 && (
          <div className="rounded-lg bg-secondary/20 px-4 py-3 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">Not applicable:</span>{' '}
            {excluded.map((c) => controlLabel(c.signal)).join(' · ')}
          </div>
        )}

        {gap.basis && (
          <div className="mt-4 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">Basis:</span> {gap.basis}
          </div>
        )}

        <Caveats items={gap.caveats} />
      </div>
    </Card>
  )
}

function Caveats({ items }) {
  if (!items?.length) return null
  return (
    <ul className="mt-3 space-y-1 border-t border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
      {items.map((c, i) => (
        <li key={i} className="flex gap-1.5">
          <span aria-hidden>·</span><span>{c}</span>
        </li>
      ))}
    </ul>
  )
}

