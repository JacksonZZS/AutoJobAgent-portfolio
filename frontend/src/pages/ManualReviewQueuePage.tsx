import { useEffect, useMemo, useState } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useTaskStore } from '@/store/taskStore'
import { useAuthStore } from '@/store/authStore'
import { usePdfPreview } from '@/hooks/usePdfPreview'
import { jobsAPI } from '@/api/jobs'
import type { ManualReviewData } from '@/types/api'
import {
  ClipboardList,
  CheckCircle2,
  SkipForward,
  XCircle,
  Eye,
  Download,
  Copy,
  ExternalLink,
  FileText,
} from 'lucide-react'

function QueueItemCard({
  item,
  isActive,
  isFirst,
  onClick,
}: {
  item: ManualReviewData
  isActive: boolean
  isFirst: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-4 transition-all ${
        isActive
          ? 'border-sky-400 bg-sky-50/80 shadow-sm'
          : 'border-slate-200 bg-white hover:border-sky-200 hover:bg-sky-50/40'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{item.job_title}</p>
          <p className="text-sm text-slate-600 mt-1">{item.company_name}</p>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full font-semibold ${isFirst ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'}`}>
          {isFirst ? '当前待处理' : '队列中'}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-slate-500">
        <span>匹配度 {item.score}/100</span>
        {item.base_resume_label && <span>版本 {item.base_resume_label}</span>}
        <span>{item.resume_path ? '有简历' : '无简历'}</span>
        <span>{item.cl_path ? '有求职信' : '无求职信'}</span>
      </div>
    </button>
  )
}

export default function ManualReviewQueuePage() {
  const { lastMessage } = useWebSocket()
  const { taskStatus, updateStatus } = useTaskStore()
  const { token, user } = useAuthStore()
  const pdf = usePdfPreview()
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const pollStatus = async () => {
      if (!token || !user?.id) return
      try {
        const data = await jobsAPI.getTaskStatus()
        updateStatus(data)
      } catch {
        // Silent fail
      }
    }

    const interval = setInterval(pollStatus, 2000)
    pollStatus()
    return () => clearInterval(interval)
  }, [token, user?.id, updateStatus])

  useEffect(() => {
    if (lastMessage?.type === 'status_update') {
      updateStatus(lastMessage.data)
    }
  }, [lastMessage, updateStatus])

  const queue = useMemo(() => {
    if (taskStatus?.manual_review_queue?.length) return taskStatus.manual_review_queue
    if (taskStatus?.manual_review_data) return [taskStatus.manual_review_data]
    return []
  }, [taskStatus])

  useEffect(() => {
    if (selectedIndex > queue.length - 1) {
      setSelectedIndex(0)
    }
  }, [queue.length, selectedIndex])

  const selectedItem = queue[selectedIndex]
  const isActionable = selectedIndex === 0 && queue.length > 0

  const handleCopyCoverLetter = async () => {
    if (!selectedItem?.cl_text) return
    try {
      await navigator.clipboard.writeText(selectedItem.cl_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // no-op
    }
  }

  const handleDownloadFile = async (fileType: 'resume' | 'cover_letter', filePath: string) => {
    try {
      const filename = filePath.split('/').pop() || ''
      if (!token) return
      const response = await fetch(`/api/v1/materials/download/${fileType}/${encodeURIComponent(filename)}`, {
        headers: { Authorization: `Bearer ${token}` }
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

  const handleDecision = async (decision: 'APPLY' | 'SKIP_TEMPORARY' | 'SKIP_PERMANENT') => {
    if (!isActionable) return
    try {
      await jobsAPI.submitManualDecision(decision)
      const refreshed = await jobsAPI.getTaskStatus()
      updateStatus(refreshed)
      setSelectedIndex(0)
    } catch (err) {
      console.error('提交决策失败:', err)
    }
  }

  if (!queue.length) {
    return (
      <div className="glass-card p-10 text-center">
        <ClipboardList className="w-12 h-12 mx-auto text-sky-300 mb-4" />
        <h2 className="text-xl font-bold text-sky-900 mb-2">暂无待审核职位</h2>
        <p className="text-sky-700">高分职位生成物料后，会自动出现在这里。</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="glass-card p-6">
        <div className="flex items-center gap-3 mb-2">
          <ClipboardList className="w-6 h-6 text-violet-600" />
          <h1 className="text-2xl font-bold text-slate-900">Manual Review Queue</h1>
        </div>
        <p className="text-slate-600">
          查看所有待审核职位，优先处理队列中的第一个职位。
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6">
        <div className="glass-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">待审核列表</h2>
            <span className="text-sm text-violet-700 font-semibold">{queue.length} 个</span>
          </div>
          {queue.map((item, index) => (
            <QueueItemCard
              key={`${item.job_title}-${item.company_name}-${index}`}
              item={item}
              isActive={selectedIndex === index}
              isFirst={index === 0}
              onClick={() => setSelectedIndex(index)}
            />
          ))}
        </div>

        <div className="glass-card p-6 space-y-5">
          <div>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-slate-900">{selectedItem.job_title}</h2>
                <p className="text-slate-600 mt-1">{selectedItem.company_name}</p>
              </div>
              <span className={`text-sm px-3 py-1 rounded-full font-semibold ${isActionable ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'}`}>
                {isActionable ? '当前待处理' : '查看中'}
              </span>
            </div>
            <div className="mt-3 flex items-center gap-3 text-sm text-slate-600">
              <span>匹配度 {selectedItem.score}/100</span>
              {selectedItem.base_resume_label && (
                <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700">
                  使用简历版本: {selectedItem.base_resume_label}
                </span>
              )}
              {selectedItem.job_url && (
                <a
                  href={selectedItem.job_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sky-700 hover:text-sky-800 font-medium"
                >
                  <ExternalLink className="w-4 h-4" />
                  原始职位
                </a>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {selectedItem.resume_path && (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-sm font-semibold text-slate-900 mb-3">定制简历</p>
                {selectedItem.tailored_resume_filename && (
                  <p className="text-xs text-slate-500 mb-3">{selectedItem.tailored_resume_filename}</p>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={() => pdf.openResumePreview(selectedItem.resume_path)}
                    className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-sky-100 text-sky-700 rounded-lg text-sm font-semibold"
                  >
                    <Eye className="w-4 h-4" />
                    预览
                  </button>
                  <button
                    onClick={() => handleDownloadFile('resume', selectedItem.resume_path)}
                    className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold"
                  >
                    <Download className="w-4 h-4" />
                    下载
                  </button>
                </div>
              </div>
            )}

            {selectedItem.cl_path && (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-sm font-semibold text-slate-900 mb-3">Cover Letter</p>
                <div className="flex gap-2 flex-wrap">
                  {selectedItem.cl_text && (
                    <button
                      onClick={handleCopyCoverLetter}
                      className={`inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold ${copied ? 'bg-green-100 text-green-700' : 'bg-sky-100 text-sky-700'}`}
                    >
                      <Copy className="w-4 h-4" />
                      {copied ? '已复制' : '复制'}
                    </button>
                  )}
                  <button
                    onClick={() => pdf.openCLPreview(selectedItem.cl_path)}
                    className="inline-flex items-center justify-center gap-2 px-3 py-2 bg-sky-100 text-sky-700 rounded-lg text-sm font-semibold"
                  >
                    <Eye className="w-4 h-4" />
                    预览
                  </button>
                  <button
                    onClick={() => handleDownloadFile('cover_letter', selectedItem.cl_path)}
                    className="inline-flex items-center justify-center gap-2 px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold"
                  >
                    <Download className="w-4 h-4" />
                    下载
                  </button>
                </div>
              </div>
            )}
          </div>

          {selectedItem.dimensions?.length ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4 text-violet-600" />
                <p className="text-sm font-semibold text-slate-900">评分维度</p>
              </div>
              <div className="space-y-3">
                {selectedItem.dimensions.map((dimension) => (
                  <div key={dimension.name} className="rounded-lg bg-slate-50 p-3">
                    <div className="flex items-center justify-between text-sm font-semibold text-slate-900">
                      <span>{dimension.name}</span>
                      <span>{dimension.score}/100</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">权重 {dimension.weight}%</p>
                    <p className="text-sm text-slate-600 mt-2">{dimension.comment}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="border-t border-slate-200 pt-4">
            <p className="text-sm font-semibold text-slate-900 mb-3">操作</p>
            {isActionable ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <button
                  onClick={() => handleDecision('APPLY')}
                  className="inline-flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-xl font-semibold"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  已投递
                </button>
                <button
                  onClick={() => handleDecision('SKIP_TEMPORARY')}
                  className="inline-flex items-center justify-center gap-2 px-4 py-3 bg-yellow-500 text-white rounded-xl font-semibold"
                >
                  <SkipForward className="w-4 h-4" />
                  跳过
                </button>
                <button
                  onClick={() => handleDecision('SKIP_PERMANENT')}
                  className="inline-flex items-center justify-center gap-2 px-4 py-3 bg-red-600 text-white rounded-xl font-semibold"
                >
                  <XCircle className="w-4 h-4" />
                  永久跳过
                </button>
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                只有队列中的第一个职位可以执行操作。请先处理前面的职位。
              </p>
            )}
          </div>
        </div>
      </div>

      {pdf.showResumePreview && pdf.resumeBlobUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-[90vw] h-[90vh] bg-white rounded-xl overflow-hidden">
            <iframe title="Resume Preview" src={pdf.resumeBlobUrl} className="w-full h-full" />
          </div>
        </div>
      )}

      {pdf.showCLPreview && pdf.clBlobUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-[90vw] h-[90vh] bg-white rounded-xl overflow-hidden">
            <iframe title="Cover Letter Preview" src={pdf.clBlobUrl} className="w-full h-full" />
          </div>
        </div>
      )}
    </div>
  )
}
