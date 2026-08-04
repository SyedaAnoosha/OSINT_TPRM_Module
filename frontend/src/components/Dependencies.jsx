import { useEffect, useState } from 'react'
import { Network } from 'lucide-react'
import { getDependencies } from '../api.js'
import { Card } from './ui.jsx'

// WHO the vendor depends on — its fourth parties. DISCLOSED, NEVER SCORED: when Azure or Okta has
// a bad day, every vendor riding them does too, and CPS 230 ¶48 makes that a regulated concern —
// but a shared provider's problem is not THIS vendor's penalty. So this panel states the
// dependencies as context and says so, in as many words.

const CATEGORY_LABELS = {
  hosting: 'Hosting / Cloud',
  cdn_dns: 'CDN / DNS',
  dns: 'DNS',
  cdn: 'CDN',
  identity: 'Identity',
  payment: 'Payment',
  email: 'Email',
  support: 'Support',
  status: 'Status',
  hr: 'HR',
  collaboration: 'Collaboration',
  marketing: 'Marketing',
  analytics: 'Analytics',
  monitoring: 'Monitoring',
  web_server: 'Web server',
  // A static-site platform serving the public web page — the marketing/landing site, not the
  // product's runtime. Ordered LAST and captioned, so it is never mistaken for core infrastructure.
  website: 'Website / landing host',
}

// Render order: core infrastructure first, the low-impact website host last. Anything unlisted
// slots before `website`.
const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS)
const catRank = (c) => { const i = CATEGORY_ORDER.indexOf(c); return i === -1 ? CATEGORY_ORDER.length - 1 : i }

export function DependenciesPanel({ vendorRef }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    let live = true
    getDependencies(vendorRef).then((d) => live && setData(d)).catch(() => {})
    return () => { live = false }
  }, [vendorRef])

  if (!data || !data.dependencies?.length) return null

  // Group by category so a reader sees the shape of the estate, not a flat list.
  const groups = {}
  for (const dep of data.dependencies) (groups[dep.category] ||= []).push(dep)
  const ordered = Object.entries(groups).sort(([a], [b]) => catRank(a) - catRank(b))
  const hasWebsite = 'website' in groups

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <Network className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">Fourth-party dependencies</span>
        <span className="text-[11px] text-muted-foreground">({data.count})</span>
      </div>

      <div className="grid gap-x-8 gap-y-3 p-5 sm:grid-cols-2">
        {ordered.map(([cat, deps]) => (
          <div key={cat}>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {CATEGORY_LABELS[cat] || cat}
            </div>
            <ul className="space-y-1">
              {deps.map((d) => (
                <li key={d.provider} className="flex items-baseline justify-between gap-3 text-[13px]"
                  title={`Detected via: ${d.detected_via.join(', ')}`}>
                  <span className={cat === 'website' ? 'font-medium text-muted-foreground' : 'font-medium'}>
                    {d.provider}
                  </span>
                  {/* More detection channels = a more certain dependency. Shown as small dots. */}
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {'●'.repeat(d.detected_via.length)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {hasWebsite && (
        <div className="border-t border-border px-5 py-2.5 text-[11px] leading-relaxed text-muted-foreground">
          <b>Website / landing host</b> reflects who served the vendor&apos;s <b>public web page</b> — often
          a static marketing site (Netlify, Vercel, GitHub Pages), <b>not</b> the product&apos;s runtime.
          A homepage on Netlify while the app runs on AWS is normal; treat it as low-impact.
        </div>
      )}

      <div className="border-t border-border bg-secondary/40 px-5 py-2.5 text-[11px] leading-relaxed text-muted-foreground">
        <b>Disclosed, not scored.</b> A fourth party&apos;s problems are concentration context, not a
        penalty on this vendor — charging every AWS customer for an AWS incident would punish vendors
        for a dependency they share with their competitors. Portfolio-wide concentration
        (&ldquo;several of your vendors share one provider&rdquo;) needs the portfolio view.
      </div>
    </Card>
  )
}
