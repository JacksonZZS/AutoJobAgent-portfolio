/**
 * Statistics grid showing processed/success/skipped/failed counts.
 */
import { TrendingUp, CheckCircle, SkipForward, XCircle } from 'lucide-react'

interface StatsGridProps {
  stats: {
    total_processed: number
    success: number
    skipped: number
    failed: number
  }
}

export default function StatsGrid({ stats }: StatsGridProps) {
  const items = [
    {
      icon: TrendingUp,
      value: stats.total_processed,
      label: '已处理',
      colors: 'from-sky-50/80 to-blue-50/80 border-sky-200/60',
      textColor: 'text-sky-600',
      valueColor: 'text-sky-900',
    },
    {
      icon: CheckCircle,
      value: stats.success,
      label: '成功',
      colors: 'from-green-50/80 to-emerald-50/80 border-green-200/60',
      textColor: 'text-green-600',
      valueColor: 'text-green-600',
    },
    {
      icon: SkipForward,
      value: stats.skipped,
      label: '跳过',
      colors: 'from-yellow-50/80 to-amber-50/80 border-yellow-200/60',
      textColor: 'text-yellow-600',
      valueColor: 'text-yellow-600',
    },
    {
      icon: XCircle,
      value: stats.failed,
      label: '失败',
      colors: 'from-red-50/80 to-rose-50/80 border-red-200/60',
      textColor: 'text-red-600',
      valueColor: 'text-red-600',
    },
  ]

  return (
    <div className="grid grid-cols-4 gap-4">
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
