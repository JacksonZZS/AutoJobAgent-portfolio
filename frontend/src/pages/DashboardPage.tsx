/**
 * Dashboard 主页 - Professional Glassmorphism (Light Theme)
 * Composed from sub-components for maintainability.
 */

import { useEffect, useRef, useState } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useTaskStore } from '@/store/taskStore'
import { useAuthStore } from '@/store/authStore'
import { usePdfPreview } from '@/hooks/usePdfPreview'
import { Activity, Wifi, WifiOff, Sparkles, Play, StopCircle, Trash2 } from 'lucide-react'
import { jobsAPI } from '@/api/jobs'
import PDFPreview from '@/components/PDFPreview'
import StatsGrid from '@/components/dashboard/StatsGrid'
import JobReviewCard from '@/components/dashboard/JobReviewCard'
import BatchSkipDialog from '@/components/dashboard/BatchSkipDialog'
import JdSidebar from '@/components/dashboard/JdSidebar'
import StartTaskDialog from '@/components/dashboard/StartTaskDialog'

export default function DashboardPage() {
  const { lastMessage, isConnected } = useWebSocket()
  const { taskStatus, updateStatus } = useTaskStore()
  const { token, user } = useAuthStore()
  const pdf = usePdfPreview()

  const lastStatusHashRef = useRef<string>('')
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [showBatchSkipDialog, setShowBatchSkipDialog] = useState(false)
  const [showJdSidebar, setShowJdSidebar] = useState(false)

  // Poll status with hash-based dedup to avoid flicker
  useEffect(() => {
    const pollStatus = async () => {
      if (!token || !user?.id) return
      try {
        const response = await fetch(`/api/v1/jobs/status`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (response.ok) {
          const data = await response.json()
          const newHash = JSON.stringify({
            status: data.status,
            progress: data.progress,
            job_id: data.manual_review_data?.job_id,
            resume_path: data.manual_review_data?.resume_path,
            cl_path: data.manual_review_data?.cl_path,
            stats: data.stats
          })
          if (newHash !== lastStatusHashRef.current) {
            lastStatusHashRef.current = newHash
            updateStatus(data)
          }
        }
      } catch {
        // Silent fail
      }
    }
    const interval = setInterval(pollStatus, 2000)
    pollStatus()
    return () => clearInterval(interval)
  }, [token, user?.id, updateStatus])

  // WebSocket status updates
  useEffect(() => {
    if (lastMessage?.type === 'status_update') {
      updateStatus(lastMessage.data)
    }
  }, [lastMessage, updateStatus])

  const isTaskRunning = taskStatus && ![
    'idle', 'completed', 'stopped', 'error'
  ].includes(taskStatus.status)

  const handleDecision = async (decision: 'APPLY' | 'SKIP_TEMPORARY' | 'SKIP_PERMANENT') => {
    try {
      if (!token) return
      const response = await fetch('/api/v1/jobs/manual-decision', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ decision })
      })
      if (!response.ok) throw new Error('提交决策失败')
      if (taskStatus) {
        updateStatus({
          ...taskStatus,
          manual_review_data: undefined,
          current_job: undefined,
          message: decision === 'APPLY'
            ? '✅ 已投递，正在搜索下一个职位...'
            : '⏭️ 已跳过，正在搜索下一个职位...'
        } as any)
      }
    } catch (err) {
      console.error('提交决策失败:', err)
    }
  }

  const handleDownloadFile = async (fileType: 'resume' | 'cover_letter', filePath: string) => {
    try {
      const filename = filePath.split('/').pop() || ''
      if (!token) return
      const response = await fetch(`/api/v1/materials/download/${fileType}/${encodeURIComponent(filename)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
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

  const handleStopTask = async () => {
    try { await jobsAPI.stopTask() } catch (err) { console.error('停止任务失败:', err) }
  }

  return (
    <div className="space-y-6">
      {/* Task Console */}
      <div className="glass-card p-8 animate-slide-up">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 text-sky-600" />
            <h2 className="text-2xl font-bold text-sky-900">任务控制台</h2>
          </div>
          <div className={`flex items-center gap-2 px-4 py-2 rounded-xl backdrop-blur-md border transition-all duration-200 ${
            isConnected
              ? 'bg-green-50/80 border-green-200'
              : 'bg-gray-50/80 border-gray-200'
          }`}>
            {isConnected
              ? <Wifi className="w-4 h-4 text-green-600 animate-pulse" />
              : <WifiOff className="w-4 h-4 text-gray-400" />
            }
            <span className={`text-sm font-semibold ${isConnected ? 'text-green-700' : 'text-gray-500'}`}>
              {isConnected ? '实时连接' : '未连接'}
            </span>
          </div>
        </div>

        {taskStatus ? (
          <div className="space-y-6">
            {/* Progress bar */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-sky-700 font-medium">{taskStatus.message}</p>
                <span className="text-sm font-bold text-sky-600">{taskStatus.progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${taskStatus.progress}%` }} />
              </div>
            </div>

            <JobReviewCard
              currentJob={taskStatus.current_job}
              manualReviewData={taskStatus.manual_review_data}
              queueLength={taskStatus.manual_review_queue?.length ?? (taskStatus.manual_review_data ? 1 : 0)}
              loadingPdf={pdf.loadingPdf}
              onOpenJdSidebar={() => setShowJdSidebar(true)}
              onOpenResumePreview={() => {
                if (taskStatus.manual_review_data?.resume_path) {
                  pdf.openResumePreview(taskStatus.manual_review_data.resume_path)
                }
              }}
              onOpenCLPreview={() => {
                if (taskStatus.manual_review_data?.cl_path) {
                  pdf.openCLPreview(taskStatus.manual_review_data.cl_path)
                }
              }}
              onDownloadFile={handleDownloadFile}
              onDecision={handleDecision}
            />

            <StatsGrid stats={taskStatus.stats} />

            <div className="flex justify-end mt-4">
              <button
                onClick={() => setShowBatchSkipDialog(true)}
                className="flex items-center gap-2 px-4 py-2 bg-orange-100 hover:bg-orange-200 text-orange-700 text-sm font-semibold rounded-lg transition-colors cursor-pointer border border-orange-300"
              >
                <Trash2 className="w-4 h-4" />
                批量跳过低分职位
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-12">
            <Activity className="w-12 h-12 text-sky-300 mx-auto mb-4" />
            <p className="text-sky-500">暂无运行中的任务</p>
          </div>
        )}
      </div>

      {/* Quick Start */}
      <div className="glass-card p-8 animate-slide-up" style={{ animationDelay: '100ms' }}>
        <div className="flex items-start gap-4">
          <Sparkles className="w-6 h-6 text-sky-600 mt-1 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="text-xl font-bold text-sky-900 mb-2">快速开始</h3>
            <p className="text-base text-sky-700 mb-6 leading-relaxed">
              上传简历 → AI 智能分析 → 启动自动投递
            </p>
            <div className="flex gap-4">
              <button
                className="glass-button flex items-center gap-2"
                onClick={() => setShowUploadDialog(true)}
                disabled={isTaskRunning || false}
              >
                <Play className="w-5 h-5" />
                {isTaskRunning ? '任务运行中...' : '开始使用'}
              </button>
              {isTaskRunning && (
                <button
                  className="glass-button-danger flex items-center gap-2"
                  onClick={handleStopTask}
                >
                  <StopCircle className="w-5 h-5" />
                  停止任务
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Dialogs & Overlays */}
      {showUploadDialog && (
        <StartTaskDialog onClose={() => setShowUploadDialog(false)} />
      )}

      {showBatchSkipDialog && (
        <BatchSkipDialog onClose={() => { setShowBatchSkipDialog(false) }} />
      )}

      {showJdSidebar && taskStatus?.current_job && (
        <JdSidebar
          job={taskStatus.current_job}
          onClose={() => setShowJdSidebar(false)}
        />
      )}

      {pdf.showResumePreview && pdf.resumeBlobUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-[90vw] h-[90vh] bg-white rounded-xl overflow-hidden">
            <PDFPreview
              pdfUrl={pdf.resumeBlobUrl}
              resumeId="current"
              onClose={pdf.closeResumePreview}
              onRegenerate={async (feedback) => {
                await pdf.regenerateResume(feedback)
                setTimeout(() => {
                  if (taskStatus?.manual_review_data?.resume_path) {
                    pdf.openResumePreview(taskStatus.manual_review_data.resume_path)
                  }
                }, 500)
              }}
            />
          </div>
        </div>
      )}

      {pdf.showCLPreview && pdf.clBlobUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-[90vw] h-[90vh] bg-white rounded-xl overflow-hidden">
            <PDFPreview
              pdfUrl={pdf.clBlobUrl}
              resumeId="current"
              onClose={pdf.closeCLPreview}
            />
          </div>
        </div>
      )}
    </div>
  )
}
