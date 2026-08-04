import {
  ScrollText, Workflow, Coins, Fingerprint, Radio, ShieldCheck, Layers3, GitBranch,
  Gauge, Scale, TrendingUp, Gavel, Repeat, Sparkles, CheckCircle2, XCircle, Star,
} from 'lucide-react'
import { Card, Badge } from '../components/ui.jsx'

// The ideal enterprise architecture (v2.1) — an 11-stage evidence lifecycle into which any source,
// free or a commercial platform, plugs without changing a single stage. Rendered in the app's own
// design language. Costs are indicative AUD bands, not quotes.

const PRINCIPLES = [
  ['Evidence before scoring', 'Every observation is collected, validated, stored, and traced before any score is calculated.'],
  ['Buy observations, never scores', 'Commercial platforms provide observations — never the final risk rating. Every score is generated with our own published methodology.'],
  ['Separate posture from confidence', 'Two independent outputs, always. Posture measures the observable security position; confidence measures the completeness and reliability of the evidence. More evidence raises confidence, not posture.'],
  ['Deterministic scoring', 'The same evidence always produces the same result. No hidden weights, proprietary ratings, or AI-generated scores.'],
  ['Fully explainable', 'Every deduction traces back to the original evidence. Every score can be reconstructed and audited.'],
]

const STAGES = [
  ['1', 'Entity Resolution', 'Ensure the correct organisation is identified before assessment begins.', Fingerprint],
  ['2', 'Evidence Collection', 'Collect independent observations from multiple sources — every collector returns the same format, so the engine never knows if evidence came from a free source or an enterprise platform.', Radio],
  ['3', 'Evidence Validation', 'Ensure every observation is immutable and auditable. Nothing is deleted; nothing is overwritten.', ShieldCheck],
  ['4', 'Evidence Enrichment', 'Improve collected evidence before scoring.', Layers3],
  ['5', 'Finding Generation', 'Convert validated evidence into standardised, explainable findings.', GitBranch],
  ['6', 'Confidence Analysis', 'Measure the reliability and completeness of the assessment.', Gauge],
  ['7', 'Penalty Scoring', 'Calculate the vendor’s cyber posture using a transparent penalty model.', Scale],
  ['8', 'Benchmarking', 'Interpret the score within an appropriate peer group — context only, never the score itself.', TrendingUp],
  ['9', 'Decision Engine', 'Convert technical findings into deterministic, auditable business decisions.', Gavel],
  ['10', 'Continuous Monitoring', 'Continuously reassess vendor risk; every reassessment creates a new immutable record.', Repeat],
  ['11', 'AI Read Layer', 'Support analysts without ever influencing the assessment.', Sparkles],
]

// Stage 1 — entity platforms
const S1_FREE = ['GLEIF', 'ABN Lookup', 'ASIC', 'Companies House', 'Wikidata']
const S1_PLATFORMS = [
  ['Dun & Bradstreet (D&B)', '$25K–90K', 'Industry-leading company identity, ownership and financial intelligence', true],
  ['Moody’s Orbis', '$40K–120K', 'Global private-company intelligence', false],
  ['S&P Capital IQ', '$70K–200K', 'Enterprise financial intelligence', false],
]

// Stage 2 — evidence capabilities
const S2_CAPS = [
  ['Internet & DNS', 'Certificate Transparency, RDAP, DNS, HTTP headers', 'SecurityTrails Enterprise', '$20K–70K', 'Historical DNS and infrastructure visibility'],
  ['Attack Surface', 'Certificate Transparency', 'Censys Enterprise', '$50K–140K', 'Best visibility into exposed internet-facing assets'],
  ['Alternative Attack Surface', '—', 'Shodan Enterprise', '$20K–80K', 'Alternative to Censys'],
  ['Vulnerability Intelligence', 'CISA KEV, NVD, EPSS', 'VulnCheck Enterprise', '$15K–80K', 'Version-level vulnerability identification'],
  ['Threat Intelligence', 'HIBP', 'Recorded Future', '$80K–400K', 'Threat actor and ransomware intelligence'],
  ['Credential Exposure', 'HIBP', 'SpyCloud', '$60K–200K', 'Enterprise credential exposure'],
  ['Business Intelligence', 'EDGAR, GLEIF', 'Dun & Bradstreet', 'Included', 'Private-company financials'],
  ['Compliance', 'Trust centres', 'OneTrust', '$30K–200K+', 'Governance validation (enterprise reaches the upper end)'],
  ['Regulatory', 'DFAT, ITA CSL, ASIC', 'Dow Jones Risk & Compliance', 'Quote', 'Enterprise sanctions screening'],
  ['Supply Chain', 'Public subprocessors', 'Interos', '$150K–500K+', 'Fourth-party dependency mapping'],
]
const S2_ROI = ['Censys Enterprise', 'SecurityTrails', 'VulnCheck', 'Dun & Bradstreet']

// Stage detail bullets
const S3_RECORD = ['Timestamp', 'Source', 'Raw evidence', 'SHA-256 hash', 'Licence', 'Retention policy']
const S4_ACTIVITIES = ['Entity verification', 'Asset attribution', 'Cross-source corroboration', 'Historical context', 'Version matching', 'Supply-chain mapping']
const S4_PLATFORMS = [
  ['Censys', 'Included', 'Asset attribution'],
  ['SecurityTrails', 'Included', 'Historical infrastructure'],
  ['VulnCheck', 'Included', 'Version matching'],
  ['Dun & Bradstreet', 'Included', 'Ownership enrichment'],
]
const S5_FINDING = ['Severity', 'Penalty', 'Business explanation', 'Evidence reference', 'Recommended remediation']
const S6_CONFIDENCE = ['Evidence coverage', 'Corroboration', 'Freshness', 'Source reliability', 'Entity certainty']
const S7_MODEL = ['Starts at 100', 'Applies published penalties', 'Applies age and frequency modifiers', 'Applies mitigation evidence', 'Enforces regulatory gates', 'Produces the final posture']
const S8_FACTORS = ['Industry', 'Organisation size', 'Geographic region', 'Ownership type']
const S9_OUTCOMES = ['Approve', 'Approve with conditions', 'Request remediation', 'Executive review', 'Reject']
const S10_CADENCE = ['Daily sanctions monitoring', 'Weekly vulnerability updates', 'Monthly reassessments', 'Event-driven rescoring']
const S11_MAY = ['Summarise findings', 'Generate executive reports', 'Explain technical issues', 'Draft remediation requests']
const S11_NEVER = ['Calculate scores', 'Change findings', 'Override decisions', 'Create evidence']

// Procurement
const ROADMAP = [
  ['Tier 0', '$0', 'Open-source intelligence only', true],
  ['Tier 1', '~$80K', 'Censys Enterprise + SecurityTrails', false],
  ['Tier 2', '~$200K', 'VulnCheck + Dun & Bradstreet', false],
  ['Tier 3', '~$400K', 'SpyCloud', false],
  ['Tier 4', '$800K–$1M+', 'Recorded Future, Mandiant, Interos', false],
]
const ORDER = [
  ['1', 'Censys Enterprise', '$50K–140K', 'Largest improvement in external attack surface visibility'],
  ['2', 'SecurityTrails Enterprise', '$20K–70K', 'Historical DNS and infrastructure intelligence'],
  ['3', 'VulnCheck Enterprise', '$15K–80K', 'Version-level vulnerability intelligence and remediation verification'],
  ['4', 'Dun & Bradstreet', '$25K–90K', 'Private-company ownership and financial intelligence'],
  ['5', 'SpyCloud', '$60K–200K', 'Enterprise credential exposure'],
  ['6', 'Recorded Future', '$80K–400K', 'Threat intelligence and ransomware visibility'],
  ['7', 'Interos', '$150K–500K+', 'Supply-chain dependency mapping — mature enterprise deployments only'],
]
const TAKEAWAYS = [
  'The methodology is built around an 11-stage evidence lifecycle, not around individual products.',
  'Commercial platforms increase evidence quality and coverage but never determine the score.',
  'Every assessment remains transparent, deterministic, explainable, and auditable.',
  'The architecture scales from a fully open-source implementation to a multi-million-dollar enterprise deployment without changing the scoring model.',
  'Investment is additive — each new platform strengthens the evidence entering the framework while preserving a single, consistent methodology.',
]

export default function PerfectMethodologyPage() {
  return (
    <div className="flex flex-col gap-10">
      <header>
        <div className="text-[11px] font-medium uppercase tracking-wider text-accent">
          The ideal enterprise architecture · v2.1
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight md:text-3xl">
          Enterprise Third-Party Risk Assessment Methodology
        </h1>
        {/* <p className="mt-1.5 max-w-3xl text-[15px] text-muted-foreground">
          If budget were unlimited, what would the ideal third-party risk platform look like? The
          answer is not collecting more data — it is a structured <b className="text-foreground">evidence
          lifecycle</b> every observation passes through, free or commercial, before it can influence a
          decision. The methodology stays the same at every budget.
        </p> */}
      </header>

      {/* Thesis */}
      <Card className="overflow-hidden border-l-4 border-l-accent">
        <div className="p-5">
          <div className="text-lg font-bold text-accent md:text-xl">Buy observations, never scores.</div>
          <p className="mt-2 max-w-3xl text-[13.5px] leading-relaxed text-muted-foreground">
            Commercial platforms increase the <b className="text-foreground">quality, coverage and
            timeliness</b> of evidence. They never determine the score — every rating is generated with
            our own published, deterministic methodology, and every deduction traces back to the
            original evidence.
          </p>
        </div>
      </Card>

      {/* Core principles */}
      <Section icon={ScrollText} title="Core design principles"
        blurb="Five principles the framework is built on — true at every budget.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PRINCIPLES.map(([t, d], i) => (
            <Card key={t} className="p-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[13px] font-bold text-accent">{String(i + 1).padStart(2, '0')}</span>
                <h3 className="text-[14px] font-semibold">{t}</h3>
              </div>
              <p className="mt-1.5 text-[12.5px] text-muted-foreground">{d}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* The lifecycle */}
      <Section icon={Workflow} title="The evidence lifecycle · eleven stages"
        blurb="Every commercial platform integrates into this lifecycle without changing any stage.">
        <div className="flex flex-col gap-3">
          {STAGES.map(([n, title, purpose, Icon], i) => (
            <Card key={n} className="p-4">
              <div className="flex items-start gap-4">
                <div className="flex flex-col items-center">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
                    <Icon className="h-[18px] w-[18px] text-accent" />
                  </div>
                  {i < STAGES.length - 1 && <div className="mt-1 h-full min-h-3 w-px flex-1 bg-border" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-sm font-bold text-accent">{n}</span>
                    <h3 className="text-[15px] font-semibold">{title}</h3>
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{purpose}</p>

                  {n === '1' && (
                    <StageDetail>
                      <FreeChips items={S1_FREE} />
                      <CostTable head={['Preferred platform', 'Est. annual (AUD)', 'Why']}
                        rows={S1_PLATFORMS.map(([p, c, w, rec]) => [<Named key={p} name={p} rec={rec} />, c, w])} />
                      <Reco>Recommended platform: <b>Dun &amp; Bradstreet</b></Reco>
                    </StageDetail>
                  )}

                  {n === '2' && (
                    <StageDetail>
                      <div className="overflow-x-auto rounded-lg border border-border">
                        <table className="w-full text-left text-[12px]">
                          <thead>
                            <tr className="border-b border-border text-[10px] uppercase tracking-wide text-muted-foreground">
                              <th className="px-3 py-2 font-medium">Capability</th>
                              <th className="px-3 py-2 font-medium">Free sources</th>
                              <th className="px-3 py-2 font-medium">Enterprise platform</th>
                              <th className="px-3 py-2 font-medium">Cost (AUD)</th>
                              <th className="px-3 py-2 font-medium">Why buy it</th>
                            </tr>
                          </thead>
                          <tbody>
                            {S2_CAPS.map(([cap, free, plat, cost, why]) => (
                              <tr key={cap} className="border-b border-border/60 last:border-b-0 align-top">
                                <td className="px-3 py-2 font-semibold">{cap}</td>
                                <td className="px-3 py-2 text-muted-foreground">{free}</td>
                                <td className="px-3 py-2 text-accent font-medium">{plat}</td>
                                <td className="whitespace-nowrap px-3 py-2 font-mono tabular-nums">{cost}</td>
                                <td className="px-3 py-2 text-muted-foreground">{why}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="mt-3">
                        <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          <Star className="h-3.5 w-3.5 text-accent" /> Highest-ROI purchases
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {S2_ROI.map((p) => (
                            <Badge key={p} style={{ color: 'var(--accent)', background: 'color-mix(in srgb, var(--accent) 12%, transparent)' }}>{p}</Badge>
                          ))}
                        </div>
                        <p className="mt-1.5 text-[12px] text-muted-foreground">These four close the largest evidence gaps while preserving the methodology.</p>
                      </div>
                    </StageDetail>
                  )}

                  {n === '3' && <StageDetail><FieldGrid title="Each record contains" items={S3_RECORD} /></StageDetail>}

                  {n === '4' && (
                    <StageDetail>
                      <FieldGrid title="Activities" items={S4_ACTIVITIES} />
                      <CostTable head={['Platform', 'Cost (AUD)', 'Value']} rows={S4_PLATFORMS} />
                    </StageDetail>
                  )}

                  {n === '5' && <StageDetail><FieldGrid title="Each finding includes" items={S5_FINDING} /></StageDetail>}
                  {n === '6' && (
                    <StageDetail>
                      <FieldGrid title="Confidence is calculated from" items={S6_CONFIDENCE} />
                      <Note>Commercial platforms primarily improve confidence by expanding evidence coverage.</Note>
                    </StageDetail>
                  )}
                  {n === '7' && (
                    <StageDetail>
                      <FieldGrid title="The scoring model" items={S7_MODEL} ordered />
                      <Note>Commercial platforms improve the inputs. They never change the scoring model.</Note>
                    </StageDetail>
                  )}
                  {n === '8' && (
                    <StageDetail>
                      <FieldGrid title="Benchmarking considers" items={S8_FACTORS} />
                      <Note>These attributes provide context only. They never affect the score itself.</Note>
                    </StageDetail>
                  )}
                  {n === '9' && <StageDetail><FieldGrid title="Typical outcomes" items={S9_OUTCOMES} /></StageDetail>}
                  {n === '10' && <StageDetail><FieldGrid title="Monitoring includes" items={S10_CADENCE} /></StageDetail>}
                  {n === '11' && (
                    <StageDetail>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <MayNever title="AI may" tone="var(--risk-low, #16a34a)" icon={CheckCircle2} items={S11_MAY} />
                        <MayNever title="AI never" tone="var(--risk-high, #dc2626)" icon={XCircle} items={S11_NEVER} />
                      </div>
                      <Note>The scoring engine always remains deterministic.</Note>
                    </StageDetail>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </Section>

      {/* Procurement roadmap */}
      <Section icon={Coins} title="Enterprise procurement roadmap"
        blurb="Investment is additive — each tier strengthens the evidence entering the framework while preserving one consistent methodology.">
        <div className="flex flex-col gap-3">
          {ROADMAP.map(([tier, cost, cap, shipped]) => (
            <Card key={tier} className={`p-4 ${shipped ? 'border-l-4' : ''}`}
              style={shipped ? { borderLeftColor: 'var(--risk-low)' } : undefined}>
              <div className="grid gap-3 sm:grid-cols-[150px_1fr]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[15px] font-semibold">{tier}</span>
                    {shipped && <Badge style={{ color: 'var(--risk-low)', background: 'color-mix(in srgb, var(--risk-low) 13%, transparent)' }}><CheckCircle2 className="h-3 w-3" />shipped</Badge>}
                  </div>
                  <div className="mt-1 font-mono text-[13px] text-accent tabular-nums">{cost}</div>
                </div>
                <div className="text-[13px] text-muted-foreground sm:border-l sm:border-border sm:pl-4">{cap}</div>
              </div>
            </Card>
          ))}
        </div>

        <div className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Recommended procurement order</div>
        <Card className="mt-2 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead>
                <tr className="border-b border-border text-[10px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">#</th>
                  <th className="px-4 py-2.5 font-medium">Platform</th>
                  <th className="px-4 py-2.5 font-medium">Cost (AUD)</th>
                  <th className="px-4 py-2.5 font-medium">Why</th>
                </tr>
              </thead>
              <tbody>
                {ORDER.map(([p, name, cost, why]) => (
                  <tr key={p} className="border-b border-border/60 last:border-b-0 align-top">
                    <td className="px-4 py-2.5 font-mono font-bold text-accent">{p}</td>
                    <td className="px-4 py-2.5 font-semibold">{name}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono tabular-nums">{cost}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          Indicative AUD bands, not quotes — every vendor here prices by custom quote. Public
          benchmarks are largely quoted in <b>USD</b> (≈1.5× to AUD), so treat these as directional.
          Real total cost is higher than the sticker: contracts commonly carry <b>3–10% annual
          escalators</b>, and first-year <b>implementation adds ~20–40%</b>.
        </p>
      </Section>

      {/* Takeaways */}
      <Section icon={CheckCircle2} title="Executive takeaways">
        <Card className="divide-y divide-border">
          {TAKEAWAYS.map((t, i) => (
            <div key={t} className="grid grid-cols-[2rem_1fr] items-baseline gap-3 px-4 py-3">
              <span className="font-mono text-[13px] font-bold text-accent tabular-nums">{String(i + 1).padStart(2, '0')}</span>
              <div className="text-[13.5px]">{t}</div>
            </div>
          ))}
        </Card>
      </Section>
    </div>
  )
}

// --- small building blocks ---

function Section({ icon: Icon, title, blurb, children }) {
  return (
    <section>
      <div className="mb-4 flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
          <Icon className="h-[18px] w-[18px] text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-bold tracking-tight">{title}</h2>
          {blurb && <p className="mt-0.5 max-w-3xl text-[13px] text-muted-foreground">{blurb}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function StageDetail({ children }) {
  return <div className="mt-3 flex flex-col gap-3 rounded-lg border border-border bg-secondary/30 p-3">{children}</div>
}

function FreeChips({ items }) {
  return (
    <div>
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--risk-low, #16a34a)' }}>Free sources</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((s) => (
          <span key={s} className="rounded-md border border-border bg-card px-2 py-0.5 text-[12px]">{s}</span>
        ))}
      </div>
    </div>
  )
}

function CostTable({ head, rows }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-[12.5px]">
        <thead>
          <tr className="border-b border-border text-[10px] uppercase tracking-wide text-muted-foreground">
            {head.map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border/60 last:border-b-0 align-top">
              <td className="px-3 py-2 font-semibold">{r[0]}</td>
              <td className="whitespace-nowrap px-3 py-2 font-mono tabular-nums">{r[1]}</td>
              <td className="px-3 py-2 text-muted-foreground">{r[2]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Named({ name, rec }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {name}
      {rec && <Badge style={{ color: 'var(--accent)', background: 'color-mix(in srgb, var(--accent) 12%, transparent)' }}>recommended</Badge>}
    </span>
  )
}

function FieldGrid({ title, items, ordered }) {
  return (
    <div>
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      <ul className="grid gap-1 sm:grid-cols-2">
        {items.map((it, i) => (
          <li key={it} className="flex items-baseline gap-2 text-[12.5px]">
            <span className="font-mono text-[11px] text-accent">{ordered ? `${i + 1}.` : '·'}</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function MayNever({ title, tone, icon: Icon, items }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold" style={{ color: tone }}>
        <Icon className="h-4 w-4" /> {title}
      </div>
      <ul className="space-y-1">
        {items.map((it) => (
          <li key={it} className="flex items-baseline gap-2 text-[12.5px] text-muted-foreground">
            <span style={{ color: tone }}>·</span>{it}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Reco({ children }) {
  return <div className="rounded-md bg-accent/10 px-3 py-2 text-[12.5px] text-foreground">{children}</div>
}

function Note({ children }) {
  return <p className="border-l-2 border-border pl-3 text-[12px] italic text-muted-foreground">{children}</p>
}
