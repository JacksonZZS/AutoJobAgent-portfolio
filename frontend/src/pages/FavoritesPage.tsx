/**
 * 收藏页面 - Professional Glassmorphism (Light Theme)
 */

import { useEffect, useState } from 'react'
import { favoritesAPI, FavoriteJob } from '@/api/favorites'
import {
  Star,
  ExternalLink,
  Trash2,
  Award,
  Building2,
  Calendar,
  Globe,
  MessageSquare,
  Save,
  X
} from 'lucide-react'

export default function FavoritesPage() {
  const [favorites, setFavorites] = useState<FavoriteJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [total, setTotal] = useState(0)

  // 备注编辑状态
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editNotes, setEditNotes] = useState('')

  // 加载收藏列表
  const loadFavorites = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await favoritesAPI.getFavorites(1, 100)
      setFavorites(res.items)
      setTotal(res.total)
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载收藏失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFavorites()
  }, [])

  // 移除收藏
  const handleRemove = async (jobId: string) => {
    if (!confirm('确定要取消收藏吗？')) return
    try {
      await favoritesAPI.removeFavorite(jobId)
      setFavorites(prev => prev.filter(f => f.job_id !== jobId))
      setTotal(prev => prev - 1)
    } catch (err: any) {
      setError(err.response?.data?.detail || '操作失败')
    }
  }

  // 保存备注
  const handleSaveNotes = async (jobId: string) => {
    try {
      await favoritesAPI.updateNotes(jobId, editNotes)
      setFavorites(prev => prev.map(f =>
        f.job_id === jobId ? { ...f, notes: editNotes } : f
      ))
      setEditingId(null)
      setEditNotes('')
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存失败')
    }
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

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="glass-card p-6 animate-slide-up">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Star className="w-6 h-6 text-yellow-500 fill-current" />
            <h2 className="text-2xl font-bold text-sky-900">我的收藏</h2>
            <span className="px-3 py-1 bg-yellow-100 text-yellow-700 text-sm font-semibold rounded-full">
              {total} 个职位
            </span>
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="glass-card p-4 bg-red-50/80 border-red-200 animate-fade-in">
          <p className="text-red-700 font-medium">{error}</p>
        </div>
      )}

      {/* 收藏列表 */}
      <div className="glass-card animate-slide-up" style={{ animationDelay: '100ms' }}>
        {loading ? (
          <div className="p-12 text-center">
            <div className="inline-block w-12 h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin mb-4" />
            <p className="text-sky-600">加载中...</p>
          </div>
        ) : favorites.length === 0 ? (
          <div className="p-12 text-center">
            <Star className="w-12 h-12 text-sky-300 mx-auto mb-4" />
            <p className="text-sky-500">暂无收藏的职位</p>
            <p className="text-sky-400 text-sm mt-2">在历史记录中点击星标即可收藏</p>
          </div>
        ) : (
          <div className="divide-y divide-sky-100">
            {favorites.map((item, index) => (
              <div
                key={item.job_id}
                className="p-5 hover:bg-sky-50/50 transition-colors animate-fade-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start justify-between gap-4">
                  {/* 左侧：职位信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      {item.score !== null && (
                        <div className="flex items-center gap-1.5 px-2 py-1 bg-sky-50/80 border border-sky-200 rounded-full">
                          <Award className="w-3 h-3 text-sky-600" />
                          <span className="text-xs font-semibold text-sky-700">
                            {item.score}%
                          </span>
                        </div>
                      )}
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
                        {formatTime(item.favorited_at)}
                      </div>
                    </div>
                    <h3 className="text-base font-bold text-sky-900 mb-1 truncate">
                      {item.title}
                    </h3>
                    <div className="flex items-center gap-2 mb-2">
                      <Building2 className="w-4 h-4 text-sky-600 flex-shrink-0" />
                      <p className="text-sm text-sky-700">{item.company}</p>
                    </div>

                    {/* 备注区域 */}
                    {editingId === item.job_id ? (
                      <div className="mt-3 flex items-center gap-2">
                        <input
                          type="text"
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          placeholder="添加备注..."
                          className="glass-input text-sm flex-1"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveNotes(item.job_id)}
                          className="p-2 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition-colors cursor-pointer"
                        >
                          <Save className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingId(null)
                            setEditNotes('')
                          }}
                          className="p-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg transition-colors cursor-pointer"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <div
                        onClick={() => {
                          setEditingId(item.job_id)
                          setEditNotes(item.notes || '')
                        }}
                        className="mt-3 flex items-center gap-2 text-xs text-sky-600 bg-sky-50/50 px-3 py-1.5 rounded-lg cursor-pointer hover:bg-sky-100 transition-colors"
                      >
                        <MessageSquare className="w-3 h-3" />
                        {item.notes || '点击添加备注...'}
                      </div>
                    )}
                  </div>

                  {/* 右侧：操作按钮 */}
                  <div className="flex flex-col gap-2 ml-4 flex-shrink-0">
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-3 py-2 bg-sky-100 hover:bg-sky-200 text-sky-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      查看职位
                    </a>
                    <button
                      onClick={() => handleRemove(item.job_id)}
                      className="flex items-center gap-2 px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      取消收藏
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
