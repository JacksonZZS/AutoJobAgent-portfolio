/**
 * Market Intelligence Page - Glassmorphism Design
 * 7 charts: Skill Demand, Salary, Company Activity, Title Trends,
 *           Location Distribution, Score Distribution, Daily Trends
 */

import { useEffect, useState, useMemo, useRef } from 'react'
import {
  marketIntelligenceAPI,
  MarketIntelligenceResponse,
} from '@/api/marketIntelligence'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  LineChart, Line,
} from 'recharts'
import {
  TrendingUp, Briefcase, MapPin, Star, Activity, Code, DollarSign,
  AlertTriangle, RefreshCw, Users, Download,
} from 'lucide-react'

const COLORS = [
  '#0ea5e9', '#38bdf8', '#7dd3fc', '#bae6fd',
  '#0284c7', '#0369a1', '#075985', '#0c4a6e',
  '#06b6d4', '#22d3ee',
]

// Score Distribution: red(low) → amber(mid) → green(high)
const SCORE_GRADIENT = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308',
  '#84cc16', '#22c55e', '#10b981', '#059669',
  '#0d9488', '#0ea5e9',
]

const CATEGORY_COLORS: Record<string, string> = {
  'Programming': '#0ea5e9',
  'Data & ML': '#8b5cf6',
  'Data Tools': '#06b6d4',
  'Cloud & DevOps': '#f59e0b',
  'Databases': '#10b981',
  'Frameworks': '#ec4899',
  'Soft Skills': '#6366f1',
}

export default function MarketIntelligencePage() {
  const [data, setData] = useState<MarketIntelligenceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedJobType, setSelectedJobType] = useState('all')
  const [timeRange, setTimeRange] = useState<number | undefined>(undefined)
  const skillChartRef = useRef<HTMLDivElement>(null)

  const handleJobTypeClick = (jobType: string) => {
    const matched = (data?.skills_by_job_type ?? []).find((p) => p.job_type === jobType)
    if (matched) {
      setSelectedJobType(jobType)
      skillChartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const loadData = async (days?: number) => {
    setLoading(true)
    setError('')
    try {
      const result = await marketIntelligenceAPI.getOverview(days)
      setData(result)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load market data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData(timeRange)
  }, [timeRange])

  // Hooks must be called before any early return
  const skillChartData = useMemo(() => {
    if (!data || selectedJobType === 'all') {
      return data?.skill_demand ?? []
    }
    const profile = data.skills_by_job_type?.find(
      (p) => p.job_type === selectedJobType
    )
    if (!profile) return []

    const flat: { skill: string; count: number; category: string }[] = []
    for (const cat of profile.categories) {
      for (const s of cat.skills) {
        flat.push({ skill: s.skill, count: s.count, category: cat.category })
      }
    }
    flat.sort((a, b) => b.count - a.count)
    return flat
  }, [selectedJobType, data])

  const visibleCategories = useMemo(() => {
    const cats = new Set<string>()
    for (const item of skillChartData) {
      cats.add(item.category)
    }
    return Array.from(cats)
  }, [skillChartData])

  if (loading) {
    return (
      <div className="glass-card p-12 text-center">
        <div className="inline-block w-12 h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin mb-4" />
        <p className="text-sky-600">Loading market intelligence...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-card p-12 text-center">
        <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
        <p className="text-red-600 mb-4">{error}</p>
        <button onClick={() => loadData()} className="btn-primary">Retry</button>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <TrendingUp className="w-7 h-7 text-sky-600" />
            Market Intelligence
          </h1>
          <p className="text-slate-500 mt-1">
            Job market analysis based on {data.total_jobs_analyzed} scraped positions
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Time Range Filter */}
          <div className="flex rounded-xl border border-sky-200 bg-white/60 overflow-hidden">
            {([
              { label: '7D', value: 7 },
              { label: '30D', value: 30 },
              { label: '90D', value: 90 },
              { label: 'All', value: undefined },
            ] as { label: string; value: number | undefined }[]).map((opt) => (
              <button
                key={opt.label}
                onClick={() => setTimeRange(opt.value)}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  timeRange === opt.value
                    ? 'bg-sky-600 text-white'
                    : 'text-sky-700 hover:bg-sky-50'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => loadData(timeRange)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/60 border border-sky-200 text-sky-700 hover:bg-sky-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          icon={<Briefcase className="w-5 h-5" />}
          label="Total Jobs"
          value={data.total_jobs_analyzed}
          color="sky"
        />
        <SummaryCard
          icon={<Star className="w-5 h-5" />}
          label="Avg Score"
          value={data.avg_score?.toFixed(1) ?? '0'}
          color="violet"
        />
        <SummaryCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="High Score Rate"
          value={`${data.high_score_rate?.toFixed(1) ?? '0'}%`}
          suffix=" (≥70)"
          color="emerald"
        />
        <SummaryCard
          icon={<Activity className="w-5 h-5" />}
          label="This Week"
          value={data.weekly_new ?? 0}
          suffix=" new"
          color="amber"
        />
      </div>

      {/* Legacy data banner */}
      {data.jobs_without_jd > 0 && (
        <div className="glass-card p-3 border-l-4 border-amber-400 bg-amber-50/50">
          <p className="text-sm text-amber-700">
            <AlertTriangle className="w-4 h-4 inline mr-1" />
            {data.jobs_without_jd} legacy jobs lack JD data. Skill and salary charts only reflect jobs with JD content.
            New jobs will automatically include full data.
          </p>
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Skill Demand — Interactive by Job Type */}
        <div ref={skillChartRef}>
        <ChartCard title="Top Skills in Demand" icon={<Code className="w-5 h-5 text-sky-600" />} span="lg:col-span-2" onExport={() => exportToCSV(skillChartData, 'skills_demand')}>
          {/* Job Type Selector + Category Legend */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <select
              value={selectedJobType}
              onChange={(e) => setSelectedJobType(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-sky-200 bg-white/70 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-300"
            >
              <option value="all">All Job Types</option>
              {(data.skills_by_job_type || []).map((p) => (
                <option key={p.job_type} value={p.job_type}>
                  {p.job_type} ({p.total_jobs} jobs)
                </option>
              ))}
            </select>
            <div className="flex flex-wrap gap-2">
              {visibleCategories.map((cat) => (
                <span
                  key={cat}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-white/60 border border-slate-200 text-slate-600"
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: CATEGORY_COLORS[cat] || '#94a3b8' }}
                  />
                  {cat}
                </span>
              ))}
            </div>
          </div>
          {skillChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={skillChartData} layout="vertical" margin={{ left: 100 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" stroke="#64748b" fontSize={12} />
                <YAxis type="category" dataKey="skill" stroke="#64748b" fontSize={12} width={95} />
                <Tooltip
                  contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  formatter={(value: any, _name: any, props: any) => [
                    `${value} jobs`,
                    props.payload.category,
                  ]}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {skillChartData.map((entry, index) => (
                    <Cell key={index} fill={CATEGORY_COLORS[entry.category] || COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No skill data yet. Run scraper with JD fetching enabled." />
          )}
        </ChartCard>
        </div>

        {/* 2. Salary Distribution */}
        <ChartCard title="Salary by Job Type (HKD/month)" icon={<DollarSign className="w-5 h-5 text-emerald-600" />} onExport={() => exportToCSV(data.salary_distribution, 'salary_distribution')}>
          {data.salary_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.salary_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="job_type" stroke="#64748b" fontSize={11} angle={-20} textAnchor="end" height={60} />
                <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                <Tooltip
                  contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }}
                  formatter={(value: any) => [`HK$${Number(value).toLocaleString()}`, '']}
                />
                <Bar dataKey="min_avg" name="Min Avg" fill="#7dd3fc" radius={[4, 4, 0, 0]} />
                <Bar dataKey="max_avg" name="Max Avg" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No salary data found in job descriptions." />
          )}
        </ChartCard>

        {/* 3. Company Activity */}
        <ChartCard title="Top Hiring Companies" icon={<Briefcase className="w-5 h-5 text-violet-600" />} onExport={() => exportToCSV(data.company_activity.slice(0, 10), 'company_activity')}>
          {data.company_activity.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.company_activity.slice(0, 10)} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" stroke="#64748b" fontSize={12} />
                <YAxis type="category" dataKey="company" stroke="#64748b" fontSize={11} width={75}
                  tickFormatter={(v) => v.length > 12 ? v.slice(0, 12) + '...' : v}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }}
                  formatter={(_value: any, name: any, props: any) => {
                    if (name === 'Openings') {
                      const score = props.payload.avg_score
                      return [`${props.value} jobs (avg score: ${score?.toFixed(1) ?? 'N/A'})`, 'Openings']
                    }
                    return [props.value, name]
                  }}
                />
                <Bar dataKey="count" name="Openings" fill="#8b5cf6" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No company data available." />
          )}
        </ChartCard>

        {/* 4. Job Title Trends — click to link Skill chart */}
        <ChartCard title="Job Type Distribution" icon={<Activity className="w-5 h-5 text-pink-600" />} onExport={() => exportToCSV(data.title_trends, 'job_type_distribution')}>
          {data.title_trends.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={data.title_trends.slice(0, 10)}
                onClick={(e: any) => {
                  if (e?.activePayload?.[0]?.payload?.title) {
                    handleJobTypeClick(e.activePayload[0].payload.title)
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="title" stroke="#64748b" fontSize={11} angle={-25} textAnchor="end" height={70} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip
                  contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }}
                  formatter={(value: any) => [`${value} jobs — click to view skills`, 'Jobs']}
                />
                <Bar dataKey="count" name="Jobs" fill="#ec4899" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No title data available." />
          )}
        </ChartCard>

        {/* 5. Job Level Distribution */}
        <ChartCard title="Seniority Level Distribution" icon={<Users className="w-5 h-5 text-indigo-600" />} onExport={() => exportToCSV(data.job_level_distribution ?? [], 'job_level_distribution')}>
          {(data.job_level_distribution ?? []).length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.job_level_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="level" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                <Bar dataKey="count" name="Jobs" radius={[6, 6, 0, 0]}>
                  {(data.job_level_distribution ?? []).map((_entry, index) => {
                    const levelColors = ['#06b6d4', '#22c55e', '#0ea5e9', '#f59e0b', '#8b5cf6', '#94a3b8']
                    return <Cell key={index} fill={levelColors[index % levelColors.length]} />
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No job level data available." />
          )}
        </ChartCard>

        {/* 6. Location Distribution */}
        <ChartCard title="Location Distribution" icon={<MapPin className="w-5 h-5 text-teal-600" />} onExport={() => exportToCSV(data.location_distribution, 'location_distribution')}>
          {data.location_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={data.location_distribution}
                  dataKey="count"
                  nameKey="location"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(props: any) => `${props.location} (${props.percentage}%)`}
                  labelLine={true}
                >
                  {data.location_distribution.map((_entry, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No location data available." />
          )}
        </ChartCard>

        {/* 6. Score Distribution — red→green gradient */}
        <ChartCard title="Match Score Distribution" icon={<Star className="w-5 h-5 text-amber-600" />} onExport={() => exportToCSV(data.score_distribution, 'score_distribution')}>
          {data.score_distribution.some((d) => d.count > 0) ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.score_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="range" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                <Bar dataKey="count" name="Jobs" radius={[6, 6, 0, 0]}>
                  {data.score_distribution.map((_entry, index) => (
                    <Cell key={index} fill={SCORE_GRADIENT[index % SCORE_GRADIENT.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No score data available." />
          )}
        </ChartCard>

        {/* 7. Daily Trends — dual Y-axis */}
        <ChartCard title="Daily Job Volume (30 days)" icon={<TrendingUp className="w-5 h-5 text-sky-600" />} span="lg:col-span-2" onExport={() => exportToCSV(data.daily_trends, 'daily_trends')}>
          {data.daily_trends.some((d) => d.new_jobs > 0) ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.daily_trends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="date"
                  stroke="#64748b"
                  fontSize={11}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis yAxisId="left" stroke="#0ea5e9" fontSize={12} label={{ value: 'Jobs', angle: -90, position: 'insideLeft', style: { fill: '#0ea5e9', fontSize: 11 } }} />
                <YAxis yAxisId="right" orientation="right" stroke="#8b5cf6" fontSize={12} domain={[0, 100]} label={{ value: 'Score', angle: 90, position: 'insideRight', style: { fill: '#8b5cf6', fontSize: 11 } }} />
                <Tooltip
                  contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }}
                  labelFormatter={(label) => `Date: ${label}`}
                  formatter={(value: any, name: any) => [
                    name === 'Avg Score' ? Number(value).toFixed(1) : value,
                    name,
                  ]}
                />
                <Legend />
                <Line yAxisId="left" type="monotone" dataKey="new_jobs" name="New Jobs" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="avg_score" name="Avg Score" stroke="#8b5cf6" strokeWidth={2} dot={false} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No daily trend data yet." />
          )}
        </ChartCard>
      </div>

      {/* Footer */}
      <p className="text-xs text-slate-400 text-right">
        Generated at: {data.generated_at ? new Date(data.generated_at).toLocaleString() : 'N/A'}
      </p>
    </div>
  )
}

/* ─── Helpers ─── */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function exportToCSV(data: any[], filename: string) {
  if (!data.length) return
  const headers = Object.keys(data[0])
  const csvRows = [
    headers.join(','),
    ...data.map((row) =>
      headers.map((h) => {
        const val = row[h]
        const str = String(val ?? '')
        return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str
      }).join(',')
    ),
  ]
  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

function SummaryCard({
  icon, label, value, suffix, color,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  suffix?: string
  color: string
}) {
  const colorMap: Record<string, string> = {
    sky: 'bg-sky-50 border-sky-200 text-sky-700',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    violet: 'bg-violet-50 border-violet-200 text-violet-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
  }
  return (
    <div className={`glass-card p-4 border ${colorMap[color]} flex items-center gap-3`}>
      <div className="p-2 rounded-lg bg-white/80">{icon}</div>
      <div>
        <p className="text-xs uppercase tracking-wide opacity-70">{label}</p>
        <p className="text-xl font-bold">
          {value}{suffix || ''}
        </p>
      </div>
    </div>
  )
}

function ChartCard({
  title, icon, children, span, onExport,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  span?: string
  onExport?: () => void
}) {
  return (
    <div className={`glass-card p-5 ${span || ''}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-700 flex items-center gap-2">
          {icon}
          {title}
        </h3>
        {onExport && (
          <button
            onClick={onExport}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-slate-500 hover:text-sky-600 hover:bg-sky-50 transition-colors"
            title="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
            CSV
          </button>
        )}
      </div>
      {children}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
      <AlertTriangle className="w-8 h-8 mb-2 opacity-50" />
      <p className="text-sm">{message}</p>
    </div>
  )
}
