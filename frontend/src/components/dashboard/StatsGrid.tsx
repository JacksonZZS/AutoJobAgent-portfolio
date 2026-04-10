/**
 * Statistics grid showing clearer pipeline metrics.
 */
import { ScanSearch, Brain, UserRoundSearch, CheckCircle, Filter, AlertTriangle } from 'lucide-react'

interface StatsGridProps {
  stats: {
    total_seen: number
    total_processed: number
    filtered_history: number
    filtered_title: number
    filtered_company: number
    rejected_low_score: number
    failed_scoring: number
    manual_review: number
    success: number
    skipped: number
    failed: number
  }
}

export default function StatsGrid({ stats }: StatsGridProps) {
  const filteredTotal =
    (stats.filtered_history ?? 0) +
    (stats.filtered_title ?? 0) +
    (stats.filtered_company ?? 0)
  const items = [
    {
      icon: ScanSearch,
      value: stats.total_seen ?? 0,
      label: '扫描职位',
      colors: 'from-sky-50/80 to-blue-50/80 border-sky-200/60',
      textColor: 'text-sky-600',
      valueColor: 'text-sky-900',
    },
    {
      icon: Brain,
      value: stats.total_processed ?? 0,
      label: '进入评分',
      colors: 'from-indigo-50/80 to-blue-50/80 border-indigo-200/60',
      textColor: 'text-indigo-600',
      valueColor: 'text-indigo-700',
    },
    {
      icon: UserRoundSearch,
      value: stats.manual_review ?? 0,
      label: '人工复核',
      colors: 'from-violet-50/80 to-fuchsia-50/80 border-violet-200/60',
      textColor: 'text-violet-600',
      valueColor: 'text-violet-700',
    },
    {
      icon: CheckCircle,
      value: stats.success ?? 0,
      label: '投递成功',
      colors: 'from-green-50/80 to-emerald-50/80 border-green-200/60',
      textColor: 'text-green-600',
      valueColor: 'text-green-600',
    },
    {
      icon: Filter,
      value: filteredTotal,
      label: '预过滤跳过',
      colors: 'from-yellow-50/80 to-amber-50/80 border-yellow-200/60',
      textColor: 'text-yellow-600',
      valueColor: 'text-yellow-600',
    },
    {
      icon: AlertTriangle,
      value: (stats.rejected_low_score ?? 0) + (stats.failed_scoring ?? 0),
      label: '低分/评分异常',
      colors: 'from-red-50/80 to-rose-50/80 border-red-200/60',
      textColor: 'text-red-600',
      valueColor: 'text-red-600',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
      {items.map((item) => (
        <div key={item.label} className={`stats-card bg-gradient-to-br ${item.colors}`}>
          <item.icon className={`w-8 h-8 ${item.textColor} mx-auto mb-3`} />
          <p className={`text-4xl font-bold ${item.valueColor} mb-2`}>{item.value}</p>
          <p className={`text-xs ${item.textColor} uppercase tracking-wide font-semibold`}>{item.label}</p>
        </div>
      ))}
    </div>
  )
}
