/**
 * 统计面板页面 - Professional Glassmorphism (Light Theme)
 */

import { useEffect, useState } from 'react'
import { statisticsAPI, DashboardStatistics, TrendDataPoint } from '@/api/statistics'
import {
  BarChart3,
  TrendingUp,
  CheckCircle,
  XCircle,
  SkipForward,
  Calendar,
  Target as _Target,
  Percent,
  Award,
  Globe
} from 'lucide-react'

export default function StatisticsPage() {
  const [stats, setStats] = useState<DashboardStatistics | null>(null)
  const [trends, setTrends] = useState<TrendDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [period, setPeriod] = useState<string>('all')

  // 加载统计数据
  const loadStats = async () => {
    setLoading(true)
    setError('')
    try {
      const [statsRes, trendsRes] = await Promise.all([
        statisticsAPI.getDashboardStats(period),
        statisticsAPI.getTrends(30)
      ])
      setStats(statsRes)
      setTrends(trendsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载统计数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStats()
  }, [period])

  if (loading) {
    return (
      <div className="glass-card p-12 text-center">
        <div className="inline-block w-12 h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin mb-4" />
        <p className="text-sky-600">加载统计数据...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-card p-12 text-center">
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 标题和时间筛选 */}
      <div className="glass-card p-6 animate-slide-up">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-6 h-6 text-sky-600" />
            <h2 className="text-2xl font-bold text-sky-900">投递统计</h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-sky-600">时间范围：</span>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="glass-input text-sm"
            >
              <option value="all">全部</option>
              <option value="today">今天</option>
              <option value="week">本周</option>
              <option value="month">本月</option>
            </select>
          </div>
        </div>
      </div>

      {/* 核心统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-slide-up" style={{ animationDelay: '100ms' }}>
          <div className="stats-card bg-gradient-to-br from-sky-50/80 to-blue-50/80 border-sky-200/60">
            <TrendingUp className="w-8 h-8 text-sky-600 mx-auto mb-3" />
            <p className="text-4xl font-bold text-sky-900 mb-2">{stats.total_applications}</p>
            <p className="text-xs text-sky-600 uppercase tracking-wide font-semibold">总投递</p>
          </div>
          <div className="stats-card bg-gradient-to-br from-green-50/80 to-emerald-50/80 border-green-200/60">
            <CheckCircle className="w-8 h-8 text-green-600 mx-auto mb-3" />
            <p className="text-4xl font-bold text-green-600 mb-2">{stats.success_count}</p>
            <p className="text-xs text-green-600 uppercase tracking-wide font-semibold">成功</p>
          </div>
          <div className="stats-card bg-gradient-to-br from-yellow-50/80 to-amber-50/80 border-yellow-200/60">
            <SkipForward className="w-8 h-8 text-yellow-600 mx-auto mb-3" />
            <p className="text-4xl font-bold text-yellow-600 mb-2">{stats.skip_count}</p>
            <p className="text-xs text-yellow-600 uppercase tracking-wide font-semibold">跳过</p>
          </div>
          <div className="stats-card bg-gradient-to-br from-red-50/80 to-rose-50/80 border-red-200/60">
            <XCircle className="w-8 h-8 text-red-600 mx-auto mb-3" />
            <p className="text-4xl font-bold text-red-600 mb-2">{stats.failed_count}</p>
            <p className="text-xs text-red-600 uppercase tracking-wide font-semibold">失败</p>
          </div>
        </div>
      )}

      {/* 时间维度统计 */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 animate-slide-up" style={{ animationDelay: '200ms' }}>
          <div className="glass-card p-5 text-center">
            <Calendar className="w-6 h-6 text-sky-600 mx-auto mb-2" />
            <p className="text-3xl font-bold text-sky-900">{stats.today_count}</p>
            <p className="text-sm text-sky-600 mt-1">今日投递</p>
          </div>
          <div className="glass-card p-5 text-center">
            <Calendar className="w-6 h-6 text-sky-600 mx-auto mb-2" />
            <p className="text-3xl font-bold text-sky-900">{stats.week_count}</p>
            <p className="text-sm text-sky-600 mt-1">本周投递</p>
          </div>
          <div className="glass-card p-5 text-center">
            <Calendar className="w-6 h-6 text-sky-600 mx-auto mb-2" />
            <p className="text-3xl font-bold text-sky-900">{stats.month_count}</p>
            <p className="text-sm text-sky-600 mt-1">本月投递</p>
          </div>
        </div>
      )}

      {/* 成功率和平均分 */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 animate-slide-up" style={{ animationDelay: '300ms' }}>
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-4">
              <Percent className="w-6 h-6 text-green-600" />
              <h3 className="text-lg font-bold text-sky-900">成功率</h3>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-5xl font-bold text-green-600">
                {(stats.success_rate * 100).toFixed(1)}
              </span>
              <span className="text-2xl text-green-500 mb-1">%</span>
            </div>
            <div className="mt-4 h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full transition-all duration-500"
                style={{ width: `${stats.success_rate * 100}%` }}
              />
            </div>
          </div>
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-4">
              <Award className="w-6 h-6 text-sky-600" />
              <h3 className="text-lg font-bold text-sky-900">平均匹配度</h3>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-5xl font-bold text-sky-600">
                {stats.avg_score.toFixed(1)}
              </span>
              <span className="text-2xl text-sky-500 mb-1">分</span>
            </div>
            <div className="mt-4 h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-sky-500 to-sky-400 rounded-full transition-all duration-500"
                style={{ width: `${stats.avg_score}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* 平台分布 */}
      {stats && Object.keys(stats.platform_stats).length > 0 && (
        <div className="glass-card p-6 animate-slide-up" style={{ animationDelay: '400ms' }}>
          <div className="flex items-center gap-3 mb-6">
            <Globe className="w-6 h-6 text-sky-600" />
            <h3 className="text-lg font-bold text-sky-900">平台分布</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {Object.entries(stats.platform_stats).map(([platform, data]) => (
              <div key={platform} className="p-4 bg-sky-50/50 rounded-xl border border-sky-200/60">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-2xl">
                    {platform === 'jobsdb' ? '🇭🇰' : platform === 'indeed' ? '🔍' : '💼'}
                  </span>
                  <span className="font-bold text-sky-900 capitalize">{platform}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-sky-600">总投递</span>
                    <span className="font-semibold text-sky-900">{data.total}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-600">成功</span>
                    <span className="font-semibold text-green-700">{data.success}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sky-600">平均分</span>
                    <span className="font-semibold text-sky-900">{data.avg_score.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 趋势图 (简化版) */}
      {trends.length > 0 && (
        <div className="glass-card p-6 animate-slide-up" style={{ animationDelay: '500ms' }}>
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="w-6 h-6 text-sky-600" />
            <h3 className="text-lg font-bold text-sky-900">30天投递趋势</h3>
          </div>
          <div className="h-48 flex items-end gap-1">
            {trends.slice(-30).map((point, _index) => {
              const maxApps = Math.max(...trends.map(t => t.applications), 1)
              const height = (point.applications / maxApps) * 100
              return (
                <div
                  key={point.date}
                  className="flex-1 flex flex-col items-center group relative"
                >
                  <div
                    className="w-full bg-gradient-to-t from-sky-500 to-sky-400 rounded-t transition-all duration-300 hover:from-sky-600 hover:to-sky-500 cursor-pointer"
                    style={{ height: `${Math.max(height, 2)}%` }}
                  />
                  {/* Tooltip */}
                  <div className="absolute bottom-full mb-2 hidden group-hover:block bg-sky-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                    {point.date}: {point.applications} 投递, {point.success} 成功
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between mt-2 text-xs text-sky-500">
            <span>{trends[0]?.date}</span>
            <span>{trends[trends.length - 1]?.date}</span>
          </div>
        </div>
      )}
    </div>
  )
}
