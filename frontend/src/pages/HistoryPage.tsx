/**
 * 投递历史页面 - Professional Glassmorphism (Light Theme)
 */

import { useEffect, useState } from 'react'
import { historyAPI, HistoryItem, HistoryStatistics, HistorySearchFilters } from '@/api/history'
import { useAuthStore } from '@/store/authStore'
import {
  TrendingUp,
  CheckCircle,
  XCircle,
  SkipForward,
  Download,
  ExternalLink,
  Filter,
  FileDown,
  ChevronLeft,
  ChevronRight,
  Award,
  Building2,
  Calendar,
  Trash2,
  Search,
  X,
  Star,
  Globe
} from 'lucide-react'
import { favoritesAPI } from '@/api/favorites'

export default function HistoryPage() {
  const { token } = useAuthStore()
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [statistics, setStatistics] = useState<HistoryStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [clearing, setClearing] = useState(false)
  const [clearType, setClearType] = useState<string>('')
  const [successMessage, setSuccessMessage] = useState('')
  const pageSize = 20

  // 🔴 搜索过滤状态
  const [showFilters, setShowFilters] = useState(false)
  const [searchFilters, setSearchFilters] = useState<HistorySearchFilters>({
    search: '',
    company: '',
    score_min: undefined,
    score_max: undefined,
    date_from: '',
    date_to: '',
    platform: ''
  })
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set())

  // 加载历史记录
  const loadHistory = async () => {
    setLoading(true)
    setError('')
    try {
      // 🔴 构建过滤条件
      const filters: HistorySearchFilters = {
        ...searchFilters,
        score_min: searchFilters.score_min,
        score_max: searchFilters.score_max
      }

      const [historyRes, statsRes] = await Promise.all([
        historyAPI.getHistory(page, pageSize, statusFilter || undefined, 'time', filters),
        historyAPI.getStatistics(),
      ])
      setHistory(historyRes.items)
      setTotal(historyRes.total)
      setStatistics(statsRes)
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载历史记录失败')
    } finally {
      setLoading(false)
    }
  }

  // 🔴 加载收藏列表
  const loadFavorites = async () => {
    try {
      const res = await favoritesAPI.getFavorites(1, 1000)
      setFavoriteIds(new Set(res.items.map(item => item.job_id)))
    } catch (err) {
      console.error('加载收藏失败:', err)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [page, statusFilter, searchFilters])

  useEffect(() => {
    loadFavorites()
  }, [])

  // 🔴 添加/移除收藏
  const handleToggleFavorite = async (item: HistoryItem) => {
    try {
      if (favoriteIds.has(item.job_id)) {
        await favoritesAPI.removeFavorite(item.job_id)
        setFavoriteIds(prev => {
          const next = new Set(prev)
          next.delete(item.job_id)
          return next
        })
      } else {
        await favoritesAPI.addFavorite(item.job_id, {
          title: item.title,
          company: item.company,
          link: item.link,
          score: item.score || undefined,
          platform: item.platform || undefined
        })
        setFavoriteIds(prev => new Set(prev).add(item.job_id))
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '操作失败')
    }
  }

  // 🔴 清除搜索过滤
  const handleClearFilters = () => {
    setSearchFilters({
      search: '',
      company: '',
      score_min: undefined,
      score_max: undefined,
      date_from: '',
      date_to: '',
      platform: ''
    })
    setPage(1)
  }

  // 🔴 检查是否有过滤条件
  const hasFilters = searchFilters.search || searchFilters.company ||
    searchFilters.score_min !== undefined || searchFilters.score_max !== undefined ||
    searchFilters.date_from || searchFilters.date_to || searchFilters.platform

  // 下载文件
  const handleDownload = async (fileType: 'resume' | 'cover_letter', filePath: string) => {
    try {
      const filename = filePath.split('/').pop() || ''
      const response = await fetch(`/api/v1/materials/download/${fileType}/${encodeURIComponent(filename)}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!response.ok) throw new Error('下载失败')
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('下载失败:', err)
    }
  }

  // 导出 CSV
  const handleExportCSV = async () => {
    try {
      const blob = await historyAPI.exportCSV()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `job_history_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('导出失败:', err)
    }
  }

  // 清除历史记录
  const handleClearHistory = async (statusFilter?: string) => {
    const messages: Record<string, string> = {
      '': '确定要清除所有历史记录吗？',
      'low_score': '确定要清除所有「评分不足」的记录吗？',
      'success': '确定要清除所有「已投递」的记录吗？',
      'applied': '确定要清除所有「已投递」的记录吗？',
      'skip': '确定要清除所有「已跳过」的记录吗？',
    }
    const msg = messages[statusFilter || ''] || `确定要清除所有「${statusFilter}」的记录吗？`

    if (!confirm(msg + '\n此操作不可恢复！')) {
      return
    }
    setClearing(true)
    setSuccessMessage('')
    try {
      const result = await historyAPI.clearHistory(statusFilter)
      setSuccessMessage(result.message || `已清除 ${result.deleted_count} 条记录`)
      // 重新加载数据
      await loadHistory()
      // 3秒后清除成功消息
      setTimeout(() => setSuccessMessage(''), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || '清除失败')
    } finally {
      setClearing(false)
    }
  }

  // 状态标签样式
  const getStatusBadge = (status: string) => {
    if (status.includes('success') || status.includes('applied')) {
      return (
        <span className="badge-success flex items-center gap-1">
          <CheckCircle className="w-3 h-3" />
          已投递
        </span>
      )
    } else if (status.includes('skip')) {
      return (
        <span className="badge-warning flex items-center gap-1">
          <SkipForward className="w-3 h-3" />
          已跳过
        </span>
      )
    } else if (status.includes('low_score')) {
      return (
        <span className="badge-info flex items-center gap-1">
          <XCircle className="w-3 h-3" />
          评分不足
        </span>
      )
    } else if (status.includes('fail')) {
      return (
        <span className="badge-error flex items-center gap-1">
          <XCircle className="w-3 h-3" />
          失败
        </span>
      )
    }
    return <span className="badge-info">{status}</span>
  }

  // 格式化时间
  const formatTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      {/* 成功消息 */}
      {successMessage && (
        <div className="glass-card p-4 bg-green-50/80 border-green-200 animate-slide-up">
          <p className="text-green-700 font-medium flex items-center gap-2">
            <CheckCircle className="w-5 h-5" />
            {successMessage}
          </p>
        </div>
      )}

      {/* 统计卡片 */}
      {statistics && (
        <div className="grid grid-cols-4 gap-4 animate-slide-up">
          <div className="stats-card bg-gradient-to-br from-sky-50/80 to-blue-50/80 border-sky-200/60">
            <TrendingUp className="w-8 h-8 text-sky-600 mx-auto mb-3" />
            <p className="text-3xl font-bold text-sky-900 mb-1">{statistics.total}</p>
            <p className="text-xs text-sky-600 uppercase tracking-wide font-semibold">总计</p>
          </div>
          <div className="stats-card bg-gradient-to-br from-green-50/80 to-emerald-50/80 border-green-200/60">
            <CheckCircle className="w-8 h-8 text-green-600 mx-auto mb-3" />
            <p className="text-3xl font-bold text-green-600 mb-1">{statistics.success}</p>
            <p className="text-xs text-green-600 uppercase tracking-wide font-semibold">已投递</p>
          </div>
          <div className="stats-card bg-gradient-to-br from-yellow-50/80 to-amber-50/80 border-yellow-200/60">
            <SkipForward className="w-8 h-8 text-yellow-600 mx-auto mb-3" />
            <p className="text-3xl font-bold text-yellow-600 mb-1">{statistics.skipped}</p>
            <p className="text-xs text-yellow-600 uppercase tracking-wide font-semibold">已跳过</p>
          </div>
          <div className="stats-card bg-gradient-to-br from-red-50/80 to-rose-50/80 border-red-200/60">
            <XCircle className="w-8 h-8 text-red-600 mx-auto mb-3" />
            <p className="text-3xl font-bold text-red-600 mb-1">{statistics.failed}</p>
            <p className="text-xs text-red-600 uppercase tracking-wide font-semibold">失败</p>
          </div>
        </div>
      )}

      {/* 工具栏 */}
      <div className="glass-card p-4 animate-slide-up" style={{ animationDelay: '100ms' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Filter className="w-5 h-5 text-sky-600" />
            <span className="text-sm font-semibold text-sky-800">筛选：</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2 glass-input text-sm min-w-[120px] cursor-pointer"
            >
              <option value="">全部</option>
              <option value="applied">已投递</option>
              <option value="skipped_permanent">永久跳过</option>
              <option value="skip">暂时跳过</option>
              <option value="low_score">评分不足</option>
              <option value="fail">失败</option>
            </select>
            {/* 🔴 高级搜索按钮 */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                showFilters || hasFilters
                  ? 'bg-sky-100 text-sky-700 border border-sky-300'
                  : 'bg-white/60 text-sky-600 border border-sky-200 hover:bg-sky-50'
              }`}
            >
              <Search className="w-4 h-4" />
              高级搜索
              {hasFilters && <span className="w-2 h-2 bg-sky-500 rounded-full" />}
            </button>
            {hasFilters && (
              <button
                onClick={handleClearFilters}
                className="flex items-center gap-1 px-2 py-1 text-xs text-sky-600 hover:text-sky-800 cursor-pointer"
              >
                <X className="w-3 h-3" />
                清除过滤
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* 分类清除下拉菜单 */}
            <div className="relative">
              <select
                value={clearType}
                onChange={(e) => setClearType(e.target.value)}
                className="px-3 py-2 glass-input text-sm min-w-[140px] cursor-pointer text-red-600"
                disabled={clearing || history.length === 0}
              >
                <option value="">清除全部</option>
                <option value="low_score">清除评分不足</option>
                <option value="applied">清除已投递</option>
                <option value="skip">清除已跳过</option>
              </select>
            </div>
            <button
              onClick={() => handleClearHistory(clearType || undefined)}
              disabled={clearing || history.length === 0}
              className="glass-button flex items-center gap-2 text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 className="w-4 h-4" />
              {clearing ? '清除中...' : '执行清除'}
            </button>
            <button
              onClick={handleExportCSV}
              className="glass-button flex items-center gap-2"
            >
              <FileDown className="w-4 h-4" />
              导出 CSV
            </button>
          </div>
        </div>

        {/* 🔴 高级搜索面板 */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-sky-200/60 grid grid-cols-2 md:grid-cols-4 gap-4 animate-fade-in">
            <div>
              <label className="block text-xs font-semibold text-sky-700 mb-1">关键词搜索</label>
              <input
                type="text"
                placeholder="职位或公司名"
                className="glass-input text-sm"
                value={searchFilters.search || ''}
                onChange={(e) => {
                  setSearchFilters({ ...searchFilters, search: e.target.value })
                  setPage(1)
                }}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-sky-700 mb-1">公司名称</label>
              <input
                type="text"
                placeholder="精确匹配"
                className="glass-input text-sm"
                value={searchFilters.company || ''}
                onChange={(e) => {
                  setSearchFilters({ ...searchFilters, company: e.target.value })
                  setPage(1)
                }}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-sky-700 mb-1">分数范围</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="最低"
                  min={0}
                  max={100}
                  className="glass-input text-sm w-20"
                  value={searchFilters.score_min ?? ''}
                  onChange={(e) => {
                    setSearchFilters({
                      ...searchFilters,
                      score_min: e.target.value ? parseInt(e.target.value) : undefined
                    })
                    setPage(1)
                  }}
                />
                <span className="text-sky-500">-</span>
                <input
                  type="number"
                  placeholder="最高"
                  min={0}
                  max={100}
                  className="glass-input text-sm w-20"
                  value={searchFilters.score_max ?? ''}
                  onChange={(e) => {
                    setSearchFilters({
                      ...searchFilters,
                      score_max: e.target.value ? parseInt(e.target.value) : undefined
                    })
                    setPage(1)
                  }}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-sky-700 mb-1">平台</label>
              <select
                className="glass-input text-sm"
                value={searchFilters.platform || ''}
                onChange={(e) => {
                  setSearchFilters({ ...searchFilters, platform: e.target.value })
                  setPage(1)
                }}
              >
                <option value="">全部平台</option>
                <option value="jobsdb">JobsDB</option>
                <option value="indeed">Indeed</option>
                <option value="linkedin">LinkedIn</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-sky-700 mb-1">开始日期</label>
              <input
                type="date"
                className="glass-input text-sm"
                value={searchFilters.date_from || ''}
                onChange={(e) => {
                  setSearchFilters({ ...searchFilters, date_from: e.target.value })
                  setPage(1)
                }}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-sky-700 mb-1">结束日期</label>
              <input
                type="date"
                className="glass-input text-sm"
                value={searchFilters.date_to || ''}
                onChange={(e) => {
                  setSearchFilters({ ...searchFilters, date_to: e.target.value })
                  setPage(1)
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* 历史列表 */}
      <div className="glass-card animate-slide-up" style={{ animationDelay: '200ms' }}>
        {loading ? (
          <div className="p-12 text-center">
            <div className="inline-block w-12 h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin mb-4" />
            <p className="text-sky-600">加载中...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <p className="text-red-600">{error}</p>
          </div>
        ) : history.length === 0 ? (
          <div className="p-12 text-center">
            <SkipForward className="w-12 h-12 text-sky-300 mx-auto mb-4" />
            <p className="text-sky-500">暂无投递记录</p>
          </div>
        ) : (
          <div className="divide-y divide-sky-100">
            {history.map((item, index) => (
              <div
                key={item.job_id}
                className="p-5 hover:bg-sky-50/50 transition-colors animate-fade-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start justify-between gap-4">
                  {/* 左侧：职位信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      {getStatusBadge(item.status)}
                      {item.score !== null && (
                        <div className="flex items-center gap-1.5 px-2 py-1 bg-sky-50/80 border border-sky-200 rounded-full">
                          <Award className="w-3 h-3 text-sky-600" />
                          <span className="text-xs font-semibold text-sky-700">
                            {item.score}%
                          </span>
                        </div>
                      )}
                      {/* 🔴 平台标识 */}
                      {item.platform && (
                        <div className="flex items-center gap-1 px-2 py-1 bg-gray-50/80 border border-gray-200 rounded-full">
                          <Globe className="w-3 h-3 text-gray-500" />
                          <span className="text-xs font-medium text-gray-600 capitalize">
                            {item.platform}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center gap-1.5 text-xs text-sky-500">
                        <Calendar className="w-3 h-3" />
                        {formatTime(item.processed_at)}
                      </div>
                    </div>
                    <h3 className="text-base font-bold text-sky-900 mb-1 truncate">
                      {item.title}
                    </h3>
                    <div className="flex items-center gap-2 mb-2">
                      <Building2 className="w-4 h-4 text-sky-600 flex-shrink-0" />
                      <p className="text-sm text-sky-700">{item.company}</p>
                    </div>
                    {item.reason && (
                      <p className="text-xs text-sky-600 bg-sky-50/50 px-3 py-1.5 rounded-lg inline-block">
                        {item.reason}
                      </p>
                    )}
                  </div>

                  {/* 右侧：操作按钮 */}
                  <div className="flex flex-col gap-2 ml-4 flex-shrink-0">
                    {/* 🔴 收藏按钮 */}
                    <button
                      onClick={() => handleToggleFavorite(item)}
                      className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                        favoriteIds.has(item.job_id)
                          ? 'bg-yellow-100 hover:bg-yellow-200 text-yellow-700 border border-yellow-300'
                          : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
                      }`}
                    >
                      <Star className={`w-3.5 h-3.5 ${favoriteIds.has(item.job_id) ? 'fill-current' : ''}`} />
                      {favoriteIds.has(item.job_id) ? '已收藏' : '收藏'}
                    </button>
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-3 py-2 bg-sky-100 hover:bg-sky-200 text-sky-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      查看职位
                    </a>

                    {item.resume_path && (
                      <button
                        onClick={() => handleDownload('resume', item.resume_path!)}
                        className="flex items-center gap-2 px-3 py-2 bg-green-100 hover:bg-green-200 text-green-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                      >
                        <Download className="w-3.5 h-3.5" />
                        下载简历
                      </button>
                    )}

                    {item.cl_path && (
                      <button
                        onClick={() => handleDownload('cover_letter', item.cl_path!)}
                        className="flex items-center gap-2 px-3 py-2 bg-purple-100 hover:bg-purple-200 text-purple-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                      >
                        <Download className="w-3.5 h-3.5" />
                        求职信
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-sky-200/60 flex items-center justify-between">
            <p className="text-sm text-sky-600">
              共 {total} 条记录，第 {page}/{totalPages} 页
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="flex items-center gap-1 px-3 py-2 glass-button-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
                上一页
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="flex items-center gap-1 px-3 py-2 glass-button-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                下一页
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
