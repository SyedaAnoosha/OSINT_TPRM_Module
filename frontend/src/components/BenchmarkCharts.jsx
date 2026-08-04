// Benchmark visuals — all render from what /benchmark already returns; no backend change.
//
// DESIGN NOTES (dataviz skill):
//  * Form picked by the data's job: radar for identity-across-categories, box plot for a
//    distribution, gauge for one headline, bars for magnitude-vs-reference.
//  * Colour by job, last. Two-series charts use ONE accent for "you" over a NEUTRAL grey
//    "peer" reference — a highlight-vs-reference pair, not a categorical rainbow, so it is
//    CVD-safe by construction. Status (ahead/behind) ships with a ✓/✗ glyph, never colour alone.
//  * Theme-aware: every colour is a CSS variable the app already flips for light/dark.
//  * Text wears ink tokens, never a series colour; grid/axes are recessive.

const ACCENT = 'var(--accent)'          // "you"
const PEER = 'var(--muted-foreground)'  // peer reference
const GRID = 'var(--border)'
const AHEAD = 'var(--risk-low, #16a34a)'
const BEHIND = 'var(--risk-high, #dc2626)'

const PRETTY = {
  cyber_hygiene_technical: 'Cyber', breach_compromise_history: 'Breach',
  vendor_transparency_gov: 'Transparency', digital_footprint_assets: 'Footprint',
  business_financial_stability: 'Business', compliance_regulatory: 'Compliance',
  adverse_media_reputation: 'Reputation',
}
const short = (c) => PRETTY[c] || String(c).replace(/_/g, ' ')
const deSnake = (s) => String(s || '').replace(/_/g, ' ')

function Legend({ items }) {
  return (
    <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1.5 text-[11px] font-medium text-muted-foreground">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5 rounded-md border border-border/40 bg-secondary/30 px-2 py-0.5 shadow-2xs">
          <span className="inline-block h-2 w-2 rounded-full shadow-xs" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

// --- 1. Category radar — you (solid) over the peer median (shaded). The standard TPRM visual:
//        which categories you lead, which you lag, at a glance. -------------------------------
export function CategoryRadar({ categories }) {
  const rows = (categories || []).filter((c) => c.posture != null && c.median != null)
  if (rows.length < 3) return null   // a radar needs ≥3 axes to mean anything

  const size = 260, cx = size / 2, cy = size / 2, R = 96
  const N = rows.length
  const ang = (i) => (-90 + (i * 360) / N) * (Math.PI / 180)
  const pt = (i, v) => [cx + Math.cos(ang(i)) * (v / 100) * R,
                        cy + Math.sin(ang(i)) * (v / 100) * R]
  const poly = (key) => rows.map((c, i) => pt(i, c[key]).join(',')).join(' ')

  // Axis labels sit OUTSIDE the plot circle, so the viewBox must be wider than the plot or they
  // are clipped at the horizontal extremes — "Business" rendered as "Busines" and "Footprint" as
  // "ootprint". Two fixes together: pad the viewBox horizontally, and anchor each label away from
  // the centre (start on the right, end on the left) so text grows outward instead of straddling
  // the edge. Anchoring alone halves the overhang; the padding covers the rest.
  const PAD_X = 56, PAD_Y = 16
  const anchorFor = (i) => {
    const c = Math.cos(ang(i))
    return c > 0.25 ? 'start' : c < -0.25 ? 'end' : 'middle'
  }

  return (
    <figure className="mt-2">
      <svg viewBox={`${-PAD_X} ${-PAD_Y} ${size + PAD_X * 2} ${size + PAD_Y * 2}`}
        className="mx-auto block w-full max-w-[420px] drop-shadow-xs"
        role="img" aria-label="Radar of category posture versus peer median">
        <defs>
          <linearGradient id="radarAccentGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={ACCENT} stopOpacity="0.35" />
            <stop offset="100%" stopColor={ACCENT} stopOpacity="0.08" />
          </linearGradient>
          <linearGradient id="radarPeerGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={PEER} stopOpacity="0.22" />
            <stop offset="100%" stopColor={PEER} stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* recessive concentric rings */}
        {[25, 50, 75, 100].map((r) => (
          <circle key={r} cx={cx} cy={cy} r={(r / 100) * R} fill="none" stroke={GRID}
            strokeWidth="1" strokeDasharray={r < 100 ? '3 3' : undefined} opacity={r === 100 ? 0.8 : 0.4} />
        ))}
        {rows.map((c, i) => {
          const [x, y] = pt(i, 100)
          const [lx, ly] = pt(i, 118)
          return (
            <g key={c.category}>
              <line x1={cx} y1={cy} x2={x} y2={y} stroke={GRID} strokeWidth="1" opacity="0.35" />
              <text x={lx} y={ly} textAnchor={anchorFor(i)} dominantBaseline="middle"
                className="fill-muted-foreground text-[9.5px] font-medium">{short(c.category)}</text>
            </g>
          )
        })}

        {/* peer median — shaded reference underneath */}
        <polygon points={poly('median')} fill="url(#radarPeerGrad)"
          stroke={PEER} strokeWidth="1.5" strokeDasharray="4 3" opacity="0.9" />

        {/* you — solid gradient on top */}
        <polygon points={poly('posture')} fill="url(#radarAccentGrad)"
          stroke={ACCENT} strokeWidth="2.5" />

        {rows.map((c, i) => {
          const [x, y] = pt(i, c.posture)
          return (
            <g key={c.category} className="transition-all hover:scale-125 origin-center">
              <circle cx={x} cy={y} r="4.5" fill={ACCENT}
                stroke="var(--card)" strokeWidth="2" className="shadow-sm">
                <title>{short(c.category)}: you {c.posture} vs peer {c.median} ({c.variance_from_median >= 0 ? '+' : ''}{c.variance_from_median})</title>
              </circle>
            </g>
          )
        })}
      </svg>
      <Legend items={[{ label: 'You', color: ACCENT }, { label: 'Peer median', color: PEER }]} />
    </figure>
  )
}

// --- 2. Distribution box-and-whisker — where your score sits in the spread of peers. --------
/**
 * Peer distribution — min · IQR · median, with this vendor marked.
 *
 * LAID OUT IN CSS, NOT IN A STRETCHED SVG, and that is a bug fix rather than a preference. This
 * was an SVG with `viewBox="-4 0 108 38"` and `preserveAspectRatio="none"`, rendered into a box
 * roughly 1350px wide by 60 tall — about 12.5x horizontally against 1.6x vertically. Non-uniform
 * scaling applies to STROKES AND SHAPES, not just to positions: every 1.75px vertical rule came
 * out ~22px wide, the whisker caps rendered as slabs, and `<circle r="4">` became a 100px ellipse.
 * The chart in the screenshot was not mis-designed, it was mis-projected.
 *
 * Percentage-positioned elements have no aspect ratio to distort, so rules stay 2px and the marker
 * dot stays round at every viewport width.
 *
 * THE SUBJECT CAN LIE OUTSIDE THE PEER RANGE, and this must not be drawn as though it cannot. The
 * cohort excludes the vendor being placed, so its posture is not bounded by the peers' min and max
 * — a vendor below every peer is exactly the case a reader most needs to see. The old code fed an
 * unclamped coordinate straight to the renderer, which put the marker off-canvas with nothing to
 * say it had gone. Here it clamps to the rail and the marker says which edge it ran off.
 */
export function DistributionBox({ stats, posture, label = 'Peer distribution' }) {
  if (!stats || stats.minimum == null || stats.maximum == null) return null

  const { minimum: lo, maximum: hi, p25, p75, median } = stats
  // A cohort where every peer scored the same is a real state (a non-discriminating domain), and
  // dividing by a zero span would put every mark at the same place with no hint why.
  const flat = hi <= lo
  const pct = (v) => (flat ? 50 : ((v - lo) / (hi - lo)) * 100)
  const clamp = (n) => Math.max(0, Math.min(100, n))

  const below = posture != null && posture < lo
  const above = posture != null && posture > hi
  const at = posture == null ? null : clamp(pct(posture))

  return (
    <figure className="mt-3">
      <figcaption className="mb-2 flex flex-wrap items-baseline gap-x-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
        {label}
        <span className="font-medium normal-case tracking-normal">
          n = {stats.n ?? '—'} · box is the middle half
        </span>
      </figcaption>

      <div className="rounded-xl border border-border/60 bg-secondary/20 px-5 pb-2 pt-8">
        {/* The plot. `relative` + percentage lefts — the whole reason this is not an SVG. */}
        <div className="relative h-9">
          {/* rail: the full observed range */}
          <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />

          {/* whisker caps */}
          {[0, 100].map((p) => (
            <span key={p} aria-hidden
              className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-muted-foreground/70"
              style={{ left: `${p}%` }} />
          ))}

          {/* IQR — the middle half of the cohort */}
          {p25 != null && p75 != null && !flat && (
            <div className="absolute top-1/2 h-5 -translate-y-1/2 rounded-md border border-muted-foreground/40 bg-muted-foreground/15"
              style={{ left: `${clamp(pct(p25))}%`, width: `${clamp(pct(p75) - pct(p25))}%` }}
              title={`Middle half of peers: ${p25} to ${p75}`} />
          )}

          {/* median — the reference every figure above is quoted against */}
          {median != null && (
            <span className="absolute top-1/2 h-7 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground"
              style={{ left: `${clamp(pct(median))}%` }} title={`Peer median ${median}`} />
          )}

          {/* this vendor — drawn last so it always wins the stack */}
          {at != null && (
            <div className="absolute top-1/2 -translate-y-1/2" style={{ left: `${at}%` }}>
              <span className="absolute left-0 top-1/2 h-9 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ background: ACCENT }} />
              <span className="absolute left-0 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
                style={{ background: ACCENT }} />
              {/* `accent-foreground`, never a hard-coded white: the token flips with the theme, and
                  the dark palette pairs this blue with near-black text rather than white. */}
              <span
                className="absolute left-0 -translate-x-1/2 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-bold tabular-nums text-accent-foreground"
                style={{ background: ACCENT, bottom: 'calc(50% + 1.25rem)' }}
              >
                {below && '↤ '}{posture}{above && ' ↦'}
              </span>
            </div>
          )}
        </div>

        {/* Axis. Min and max anchor the ends; the median is placed where it actually falls, because
            a centred "Median 90" under a median sitting at 78% of the rail is a caption arguing
            with its own chart. */}
        <div className="relative mt-1 h-4 text-[11px] text-muted-foreground">
          <span className="absolute left-0">{lo}</span>
          {median != null && !flat && (
            <span className="absolute -translate-x-1/2 font-semibold text-foreground"
              style={{ left: `${clamp(pct(median))}%` }}>
              {median}
            </span>
          )}
          <span className="absolute right-0">{hi}</span>
        </div>
      </div>

      {(below || above || flat) && (
        <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
          {flat && 'Every peer in this cohort scored the same, so there is no spread to place against. '}
          {below && `This vendor scores below every peer in the cohort (lowest peer ${lo}). `}
          {above && `This vendor scores above every peer in the cohort (highest peer ${hi}). `}
          {(below || above) && 'The cohort excludes the vendor being placed, so its score is not bounded by the peers’ range.'}
        </p>
      )}
    </figure>
  )
}

// --- 3. Percentile gauge — one executive-glance figure, with the median tick for reference. --
// export function PercentileGauge({ percentile, resolution }) {
//   if (percentile == null) return null
//   const W = 180, H = 105, cx = W / 2, cy = 92, R = 72
//   // semicircle from 180° (left, 0th) to 0° (right, 100th)
//   const a = (p) => Math.PI - (p / 100) * Math.PI
//   const arc = (p0, p1) => {
//     const [x0, y0] = [cx + R * Math.cos(a(p0)), cy - R * Math.sin(a(p0))]
//     const [x1, y1] = [cx + R * Math.cos(a(p1)), cy - R * Math.sin(a(p1))]
//     return `M ${x0} ${y0} A ${R} ${R} 0 0 1 ${x1} ${y1}`
//   }
//   const [mx, my] = [cx + R * Math.cos(a(50)), cy - R * Math.sin(a(50))]

//   return (
//     <figure className="mt-2 text-center">
//       <figcaption className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
//         Percentile in cohort
//       </figcaption>
//       <div className="relative mx-auto max-w-[240px]">
//         <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img"
//           aria-label={`Percentile gauge: ${percentile}th`}>
//           <defs>
//             <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
//               <stop offset="0%" stopColor="var(--risk-high, #dc2626)" />
//               <stop offset="50%" stopColor="var(--risk-med, #d97706)" />
//               <stop offset="100%" stopColor="var(--accent)" />
//             </linearGradient>
//           </defs>

//           {/* Background Arc */}
//           <path d={arc(0, 100)} fill="none" stroke={GRID} strokeWidth="10" strokeLinecap="round" opacity="0.6" />
          
//           {/* Active Percentile Arc */}
//           <path d={arc(0, percentile)} fill="none" stroke="url(#gaugeGrad)" strokeWidth="10"
//             strokeLinecap="round" />

//           {/* median reference tick at 50th */}
//           <line x1={cx + (R - 10) * Math.cos(a(50))} y1={cy - (R - 10) * Math.sin(a(50))}
//             x2={mx + 4 * Math.cos(a(50))} y2={my - 4 * Math.sin(a(50))}
//             stroke="var(--foreground)" strokeWidth="2" strokeLinecap="round" />

//           <text x={cx} y={cy - 16} textAnchor="middle" className="fill-foreground"
//             style={{ fontSize: 32, fontWeight: 800, fontFamily: 'var(--font-sans)' }}>{percentile}<tspan style={{ fontSize: 16 }}>th</tspan></text>
//           <text x={cx} y={cy + 4} textAnchor="middle" className="fill-muted-foreground"
//             style={{ fontSize: 9.5, fontWeight: 500 }}>±{resolution} · median ▲ at 50</text>
//         </svg>
//       </div>
//     </figure>
//   )
// }

// --- 4. Signal prevalence bars — "how many peers pass this control", with your ✓/✗. ---------
export function PrevalenceBars({ signals }) {
  const rows = (signals || []).filter((s) => s.standing !== 'typical').slice(0, 6)
  if (!rows.length) return null

  return (
    <figure className="mt-2">
      <figcaption className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Controls · Vendor vs their industry
      </figcaption>
      <div className="space-y-2">
        {rows.map((s) => {
          const pct = Math.round(s.peer_pass_rate * 100)
          const behind = s.standing === 'behind'
          const tone = behind ? BEHIND : AHEAD
          return (
            <div key={s.signal} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3 rounded-lg border border-border/40 bg-card/60 p-2 text-xs transition-all hover:bg-secondary/30"
              title={`${s.peers_passing} of ${s.peers_checked} peers assessed pass ${deSnake(s.signal)}`}>
              <span className="truncate font-semibold text-foreground">{deSnake(s.signal)}</span>
              <div className="h-2.5 rounded-full bg-secondary/80 overflow-hidden" role="img"
                aria-label={`${pct}% of peers pass`}>
                <div className="h-2.5 rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: PEER, opacity: 0.7 }} />
              </div>
              <span className="inline-flex items-center gap-1 font-semibold text-[11px] rounded-md px-2 py-0.5" style={{ color: tone, background: `color-mix(in srgb, ${tone} 12%, transparent)` }}>
                {pct}% peers · {s.passing ? '✓ Pass' : '✗ Lag'}
              </span>
            </div>
          )
        })}
      </div>
      <p className="mt-2 text-[10.5px] text-muted-foreground">
        Bar = percentage of peers passing control. Tag = vendor status relative to peers.
      </p>
    </figure>
  )
}
