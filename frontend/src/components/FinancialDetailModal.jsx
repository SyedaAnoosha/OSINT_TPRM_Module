import { X, TrendingUp, TrendingDown, Minus, AlertTriangle, Info } from 'lucide-react'
import { useState } from 'react'
import { Card } from './ui.jsx'

/**
 * Financial Detail Modal — Phase 4.4 Interactive Element
 *
 * Displays detailed financial metrics with drill-down capabilities.
 * Shows revenue trends, debt ratios, and cash flow analysis with explanations.
 */
export function FinancialDetailModal({ financialProfile, onClose }) {
  const [activeTab, setActiveTab] = useState('overview')

  if (!financialProfile) return null

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'trends', label: 'Trends' },
    { id: 'ratios', label: 'Ratios' },
    { id: 'insolvency', label: 'Insolvency' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <Card className="relative max-h-[90vh] w-full max-w-3xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/60 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold">Financial Health Details</h2>
            <p className="text-sm text-muted-foreground">
              {financialProfile.vendor_ref}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 hover:bg-secondary/80 transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border/60 px-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="overflow-y-auto px-6 py-4">
          {activeTab === 'overview' && <OverviewTab profile={financialProfile} />}
          {activeTab === 'trends' && <TrendsTab profile={financialProfile} />}
          {activeTab === 'ratios' && <RatiosTab profile={financialProfile} />}
          {activeTab === 'insolvency' && <InsolvencyTab profile={financialProfile} />}
        </div>
      </Card>
    </div>
  )
}

function OverviewTab({ profile }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label="Operating Years"
          value={profile.operating_years?.toFixed(1)}
          suffix="years"
          description="Time since company incorporation"
        />
        <MetricCard
          label="Age Band"
          value={profile.age_band?.replace('_', ' ')}
          description="Company maturity classification"
        />
      </div>

      <div className="rounded-lg border border-border/60 bg-secondary/30 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Info className="h-4 w-4 text-accent" />
          <span className="text-sm font-semibold">Age-Based Risk Context</span>
        </div>
        <p className="text-sm text-muted-foreground">
          {getAgeBandDescription(profile.age_band)}
        </p>
      </div>

      {profile.contingency_plan_required && (
        <div className="rounded-lg border border-border/60 bg-orange-500/10 p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-orange-600" />
            <span className="text-sm font-semibold text-orange-600">Contingency Plan Required</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Young vendor with critical dependency — develop exit strategy
          </p>
        </div>
      )}
    </div>
  )
}

function TrendsTab({ profile }) {
  return (
    <div className="space-y-4">
      <TrendItem
        label="Revenue Trend"
        trend={profile.revenue_trend}
        description="Direction of revenue over recent periods"
      />
      <TrendItem
        label="Cash Flow Trend"
        trend={profile.cash_flow_trend}
        description="Operating cash flow direction"
      />

      {profile.financial_metrics && profile.financial_metrics.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3">Recent Financial Metrics</h3>
          <div className="rounded-lg border border-border/60 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Period</th>
                  <th className="px-3 py-2 text-right font-medium">Revenue</th>
                  <th className="px-3 py-2 text-right font-medium">Net Income</th>
                  <th className="px-3 py-2 text-right font-medium">Debt/Equity</th>
                </tr>
              </thead>
              <tbody>
                {profile.financial_metrics.slice(0, 5).map((metric, i) => (
                  <tr key={i} className="border-t border-border/40">
                    <td className="px-3 py-2">{metric.period_end}</td>
                    <td className="px-3 py-2 text-right">
                      {metric.revenue ? `$${(metric.revenue / 1000000).toFixed(1)}M` : 'N/A'}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {metric.net_income ? `$${(metric.net_income / 1000000).toFixed(1)}M` : 'N/A'}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {metric.equity && metric.long_term_debt
                        ? `${(metric.long_term_debt / metric.equity).toFixed(2)}x`
                        : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function RatiosTab({ profile }) {
  return (
    <div className="space-y-4">
      <RatioCard
        label="Debt-to-Equity"
        value={profile.debt_to_equity}
        description="Total debt divided by shareholder equity"
        thresholds={[
          { value: 1.0, label: 'Healthy', color: 'green' },
          { value: 2.0, label: 'Moderate', color: 'yellow' },
          { value: 3.0, label: 'High', color: 'orange' },
        ]}
      />

      {profile.financial_metrics && profile.financial_metrics.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3">Financial Health Indicators</h3>
          <div className="space-y-2">
            <IndicatorCard
              label="Profitability"
              value={calculateProfitability(profile.financial_metrics)}
              description="Net income as percentage of revenue"
            />
            <IndicatorCard
              label="Asset Turnover"
              value={calculateAssetTurnover(profile.financial_metrics)}
              description="Revenue divided by total assets"
            />
          </div>
        </div>
      )}
    </div>
  )
}

function InsolvencyTab({ profile }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border/60 bg-secondary/30 p-4">
        <div className="flex items-center gap-2 mb-2">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm font-semibold">Insolvency Status</span>
        </div>
        <p className="text-sm text-muted-foreground">
          {profile.insolvency_gate ? (
            <span className="text-red-600 font-medium">
              BLOCKED: {profile.insolvency_gate_reason}
            </span>
          ) : (
            <span className="text-green-600 font-medium">No active insolvency proceedings</span>
          )}
        </p>
      </div>

      {profile.insolvency_records && profile.insolvency_records.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3">Insolvency Records</h3>
          <div className="space-y-2">
            {profile.insolvency_records.map((record, i) => (
              <div key={i} className="rounded-lg border border-border/60 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium">{record.proceeding_type}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      record.status === 'active'
                        ? 'bg-red-500/20 text-red-600'
                        : 'bg-yellow-500/20 text-yellow-600'
                    }`}
                  >
                    {record.status}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground space-y-0.5">
                  <div>Date: {record.date}</div>
                  <div>Jurisdiction: {record.jurisdiction}</div>
                  <div>Case: {record.case_number}</div>
                  <div>Source: {record.source}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value, suffix, description }) {
  return (
    <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-lg font-bold">
        {value}
        {suffix && <span className="text-sm font-normal text-muted-foreground ml-1">{suffix}</span>}
      </div>
      <div className="text-xs text-muted-foreground mt-1">{description}</div>
    </div>
  )
}

function TrendItem({ label, trend, description }) {
  const config = {
    growing: { icon: TrendingUp, color: 'text-green-600', label: 'Growing' },
    stable: { icon: Minus, color: 'text-muted-foreground', label: 'Stable' },
    declining: { icon: TrendingDown, color: 'text-red-600', label: 'Declining' },
    positive: { icon: TrendingUp, color: 'text-green-600', label: 'Positive' },
    negative: { icon: TrendingDown, color: 'text-red-600', label: 'Negative' },
  }

  const cfg = config[trend] || { icon: Minus, color: 'text-muted-foreground', label: 'Unknown' }
  const Icon = cfg.icon

  return (
    <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{label}</span>
        <Icon className={`h-4 w-4 ${cfg.color}`} />
      </div>
      <div className={`text-sm font-medium ${cfg.color}`}>{cfg.label}</div>
      <div className="text-xs text-muted-foreground mt-1">{description}</div>
    </div>
  )
}

function RatioCard({ label, value, description, thresholds }) {
  const color = value === null ? 'text-muted-foreground' : 
    value < thresholds[0].value ? 'text-green-600' :
    value < thresholds[1].value ? 'text-yellow-600' :
    value < thresholds[2].value ? 'text-orange-600' : 'text-red-600'

  return (
    <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>
        {value !== null ? value.toFixed(2) : 'N/A'}x
      </div>
      <div className="text-xs text-muted-foreground mt-1">{description}</div>
      <div className="mt-2 flex gap-2">
        {thresholds.map((t, i) => (
          <span key={i} className="text-xs px-2 py-0.5 rounded bg-secondary/50">
            {t.label}: {t.value}x
          </span>
        ))}
      </div>
    </div>
  )
}

function IndicatorCard({ label, value, description }) {
  return (
    <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-sm font-bold">
        {value !== null ? `${value.toFixed(1)}%` : 'N/A'}
      </div>
      <div className="text-xs text-muted-foreground mt-1">{description}</div>
    </div>
  )
}

function getAgeBandDescription(band) {
  const descriptions = {
    startup: 'Companies under 2 years old have the highest failure rate (~3× established companies). Limited track record makes financial health harder to assess.',
    young: 'Companies 2-5 years old have passed the initial startup phase but are still establishing market position and financial stability.',
    established: 'Companies 5-10 years old have proven business models and established market presence. Lower failure rate than younger companies.',
    mature: 'Companies 10-20 years old have demonstrated staying power through multiple economic cycles. Strong survivorship indicator.',
    veteran: 'Companies 20+ years old have survived multiple economic downturns and market shifts. Highest survivorship credit.',
    unknown: 'Age could not be determined from available registry data. Confidence in financial assessment is reduced.',
  }
  return descriptions[band] || 'No age information available.'
}

function calculateProfitability(metrics) {
  if (!metrics || metrics.length === 0) return null
  const latest = metrics[metrics.length - 1]
  if (!latest.revenue || !latest.net_income) return null
  return (latest.net_income / latest.revenue) * 100
}

function calculateAssetTurnover(metrics) {
  if (!metrics || metrics.length === 0) return null
  const latest = metrics[metrics.length - 1]
  if (!latest.revenue || !latest.total_assets) return null
  return (latest.revenue / latest.total_assets) * 100
}
