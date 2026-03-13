/**
 * 多简历管理页面 - Glassmorphism 风格
 */

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/authStore'
import {
  FileText,
  Upload,
  Star,
  Trash2,
  Plus,
  Loader2,
  CheckCircle,
  AlertCircle,
  Tag,
  Calendar
} from 'lucide-react'

interface Resume {
  id: string
  filename: string
  label?: string
  is_default: boolean
  uploaded_at: string
  file_size?: number
}

export default function ResumeManagerPage() {
  const { token } = useAuthStore()
  const [resumes, setResumes] = useState<Resume[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [label, setLabel] = useState('')
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // 加载简历列表
  useEffect(() => {
    loadResumes()
  }, [])

  const loadResumes = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/v1/upload/resumes', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      if (response.ok) {
        const data = await response.json()
        setResumes(data.resumes || [])
      }
    } catch (error) {
      console.error('加载简历列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 上传简历
  const handleUpload = async () => {
    if (!selectedFile) return

    setUploading(true)
    setMessage(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      if (label) {
        formData.append('label', label)
      }

      const response = await fetch('/api/v1/upload/resume-with-label', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        setMessage({ type: 'success', text: '简历上传成功！' })
        setShowUploadModal(false)
        setSelectedFile(null)
        setLabel('')
        loadResumes()
      } else {
        const error = await response.json()
        setMessage({ type: 'error', text: error.detail || '上传失败' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: '上传失败，请重试' })
    } finally {
      setUploading(false)
    }
  }

  // 设为默认
  const handleSetDefault = async (id: string) => {
    try {
      const response = await fetch(`/api/v1/upload/resume/${id}/default`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        setMessage({ type: 'success', text: '已设为默认简历' })
        loadResumes()
      }
    } catch (error) {
      setMessage({ type: 'error', text: '操作失败' })
    }
  }

  // 删除简历
  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这份简历吗？')) return

    try {
      const response = await fetch(`/api/v1/upload/resume/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        setMessage({ type: 'success', text: '简历已删除' })
        loadResumes()
      }
    } catch (error) {
      setMessage({ type: 'error', text: '删除失败' })
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-sky-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-sky-900">简历管理</h1>
              <p className="text-sm text-sky-600">管理多份简历，针对不同职位使用不同版本</p>
            </div>
          </div>
          <button
            onClick={() => setShowUploadModal(true)}
            className="glass-button flex items-center gap-2"
          >
            <Plus className="w-5 h-5" />
            上传新简历
          </button>
        </div>
      </div>

      {/* 消息提示 */}
      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-2 ${
          message.type === 'success'
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle className="w-5 h-5" />
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          <span>{message.text}</span>
          <button
            onClick={() => setMessage(null)}
            className="ml-auto text-gray-400 hover:text-gray-600"
          >
            ×
          </button>
        </div>
      )}

      {/* 简历列表 */}
      {resumes.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <FileText className="w-16 h-16 text-sky-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-sky-800 mb-2">还没有上传简历</h3>
          <p className="text-sky-600 mb-4">上传你的第一份简历开始使用</p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="glass-button"
          >
            <Upload className="w-5 h-5 inline mr-2" />
            上传简历
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {resumes.map((resume) => (
            <div
              key={resume.id}
              className={`glass-card p-5 transition-all hover:shadow-lg ${
                resume.is_default ? 'ring-2 ring-sky-500 ring-offset-2' : ''
              }`}
            >
              {/* 默认标记 */}
              {resume.is_default && (
                <div className="absolute -top-2 -right-2 bg-sky-500 text-white text-xs px-2 py-1 rounded-full flex items-center gap-1">
                  <Star className="w-3 h-3 fill-current" />
                  默认
                </div>
              )}

              {/* 文件图标和名称 */}
              <div className="flex items-start gap-3 mb-4">
                <div className="w-12 h-12 bg-sky-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText className="w-6 h-6 text-sky-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-sky-900 truncate" title={resume.filename}>
                    {resume.filename}
                  </h3>
                  {resume.label && (
                    <div className="flex items-center gap-1 mt-1">
                      <Tag className="w-3 h-3 text-sky-500" />
                      <span className="text-xs text-sky-600">{resume.label}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 元信息 */}
              <div className="flex items-center gap-4 text-xs text-sky-500 mb-4">
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(resume.uploaded_at)}
                </div>
                {resume.file_size && (
                  <span>{formatFileSize(resume.file_size)}</span>
                )}
              </div>

              {/* 操作按钮 */}
              <div className="flex items-center gap-2">
                {!resume.is_default && (
                  <button
                    onClick={() => handleSetDefault(resume.id)}
                    className="flex-1 py-2 px-3 bg-sky-50 hover:bg-sky-100 text-sky-700 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1"
                  >
                    <Star className="w-4 h-4" />
                    设为默认
                  </button>
                )}
                <button
                  onClick={() => handleDelete(resume.id)}
                  className="py-2 px-3 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1"
                >
                  <Trash2 className="w-4 h-4" />
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 上传弹窗 */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="glass-card p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-sky-900 mb-4 flex items-center gap-2">
              <Upload className="w-5 h-5 text-sky-600" />
              上传新简历
            </h2>

            {/* 文件选择 */}
            <div className="mb-4">
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                选择文件 *
              </label>
              <div
                className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
                  selectedFile
                    ? 'border-sky-500 bg-sky-50'
                    : 'border-sky-200 hover:border-sky-400'
                }`}
              >
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="resume-upload"
                />
                <label htmlFor="resume-upload" className="cursor-pointer">
                  {selectedFile ? (
                    <div className="flex items-center justify-center gap-2 text-sky-700">
                      <FileText className="w-8 h-8" />
                      <div>
                        <p className="font-medium">{selectedFile.name}</p>
                        <p className="text-xs text-sky-500">
                          {formatFileSize(selectedFile.size)}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sky-500">
                      <Upload className="w-10 h-10 mx-auto mb-2" />
                      <p>点击或拖拽上传 PDF 文件</p>
                    </div>
                  )}
                </label>
              </div>
            </div>

            {/* 标签输入 */}
            <div className="mb-6">
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                简历标签（可选）
              </label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="如：技术岗、产品岗、海外版"
                className="glass-input"
              />
              <p className="text-xs text-sky-500 mt-1">
                添加标签帮助你区分不同版本的简历
              </p>
            </div>

            {/* 按钮 */}
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowUploadModal(false)
                  setSelectedFile(null)
                  setLabel('')
                }}
                className="flex-1 py-2 px-4 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-medium transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleUpload}
                disabled={!selectedFile || uploading}
                className="flex-1 glass-button flex items-center justify-center gap-2"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    上传中...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    上传
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
