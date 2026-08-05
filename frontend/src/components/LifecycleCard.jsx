import { Clock, Users, HardDrive } from 'lucide-react'
import { Caveats } from './primitives.jsx'
import { Card } from './ui.jsx'

export function LifecycleCard({ lifecycle }) {
  if (!lifecycle) return null

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">Lifecycle context</span>
      </div>

      <div className="p-5 space-y-4">
        {/* Stage label */}
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Stage
          </div>
          <div className="mt-1 text-[14px] font-semibold">{lifecycle.stage_label}</div>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
            {lifecycle.risk_profile_note}
          </p>
          {lifecycle.operating_years != null && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Operating for ~{Math.round(lifecycle.operating_years)} year{
                Math.round(lifecycle.operating_years) === 1 ? '' : 's'
              }
            </p>
          )}
        </div>

        {/* Key-person flag — only shown if true */}
        {lifecycle.key_person_risk && lifecycle.key_person_basis && (
          <div className="flex items-start gap-2.5 rounded-lg border px-3.5 py-3"
               style={{ borderColor: 'var(--risk-moderate)' }}>
            <Users className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--risk-moderate)' }} />
            <div>
              <div className="text-[12px] font-semibold">Key-person risk</div>
              <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
                {lifecycle.key_person_basis}
              </p>
            </div>
          </div>
        )}

        {/* Obsolescence signals — only shown if non-empty */}
        {lifecycle.obsolescence_signals?.length > 0 && (
          <div>
            <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Technology obsolescence indicators
            </div>
            <ul className="space-y-1.5">
              {lifecycle.obsolescence_signals.map((s) => (
                <li key={s.finding_id} className="flex items-start gap-2 text-[12px] leading-relaxed">
                  <HardDrive className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span>{s.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <Caveats items={lifecycle.caveats} />
      </div>
    </Card>
  )
}