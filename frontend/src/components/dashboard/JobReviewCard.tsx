/**
 * Job review card: current job info + generated materials + decision buttons.
 */
import {
  Building2, Gauge, Eye, FileText, Download,
  ExternalLink, Copy, Check, CheckCircle,
  SkipForward, XCircle
} from 'lucide-react'
import { useState } from 'react'

interface CurrentJob {
  title: string
  company: string
  score?: number
  location?: string
  job_url?: string
  jd_content?: string
}

interface ManualReviewData {
  resume_path?: string
  cl_path?: string
  cl_text?: string
  job_url?: string
  job_id?: string
  base_resume_label?: string
  base_resume_filename?: string
  tailored_resume_filename?: string
}

interface JobReviewCardProps {
  currentJob?: CurrentJob
  manualReviewData?: ManualReviewData
  queueLength?: number
  loadingPdf: boolean
  onOpenJdSidebar: () => void
  onOpenResumePreview: () => void
  onOpenCLPreview: () => void
  onDownloadFile: (fileType: 'resume' | 'cover_letter', filePath: string) => void
  onDecision: (decision: 'APPLY' | 'SKIP_TEMPORARY' | 'SKIP_PERMANENT') => void
}

export default function JobReviewCard({
  currentJob,
  manualReviewData,
  queueLength = 0,
  loadingPdf,
  onOpenJdSidebar,
  onOpenResumePreview,
  onOpenCLPreview,
  onDownloadFile,
  onDecision,
}: JobReviewCardProps) {
  const [copied, setCopied] = useState(false)

  const handleCopyCoverLetter = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('复制失败:', err)
    }
  }

  return (
    <>
      {/* Current job info */}
      {currentJob && (
        <div className="glass-card p-5 border-l-4 border-sky-500 animate-fade-in">
          <div className="flex items-start gap-3">
            <Building2 className="w-5 h-5 text-sky-600 mt-1 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-sky-600 mb-1">正在处理</p>
              <h3 className="text-lg font-bold text-sky-900 mb-1">{currentJob.title}</h3>
              <p className="text-sm text-sky-700">{currentJob.company}</p>
              {currentJob.score && (
                <div className="flex items-center gap-2 mt-2">
                  <Gauge className="w-4 h-4 text-sky-600" />
                  <span className="text-sm font-semibold text-sky-600">
                    匹配度: {currentJob.score}/100
                  </span>
                </div>
              )}
              <button
                onClick={onOpenJdSidebar}
                className="mt-3 flex items-center gap-2 px-3 py-1.5 bg-sky-100 hover:bg-sky-200 text-sky-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer border border-sky-300"
              >
                <Eye className="w-3.5 h-3.5" />
                查看 JD
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Generated materials + decision buttons */}
      {manualReviewData && (manualReviewData.resume_path || manualReviewData.cl_path) && (
        <div className="glass-card p-5 border-l-4 border-green-500 animate-fade-in">
          <div className="flex items-start gap-3 mb-4">
            <FileText className="w-5 h-5 text-green-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-green-700 mb-3">生成的物料</p>
              {queueLength > 1 && (
                <p className="text-xs text-green-600 mb-3">
                  当前待审核队列: {queueLength} 个职位
                </p>
              )}
              {manualReviewData.base_resume_label && (
                <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700">
                  使用简历版本: {manualReviewData.base_resume_label}
                </div>
              )}
              <div className="space-y-2">
                {manualReviewData.resume_path && (
                  <div className="flex items-center justify-between p-3 bg-white/60 rounded-lg">
                    <div>
                      <span className="text-sm text-green-700 font-medium">定制化简历</span>
                      {manualReviewData.tailored_resume_filename && (
                        <p className="text-xs text-slate-500 mt-1">{manualReviewData.tailored_resume_filename}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={onOpenResumePreview}
                        disabled={loadingPdf}
                        className="flex items-center gap-2 px-3 py-1.5 bg-sky-100 hover:bg-sky-200 text-sky-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer border border-sky-300 disabled:opacity-50"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        {loadingPdf ? '加载中...' : '预览'}
                      </button>
                      <button
                        onClick={() => onDownloadFile('resume', manualReviewData.resume_path!)}
                        className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                      >
                        <Download className="w-3.5 h-3.5" />
                        下载
                      </button>
                    </div>
                  </div>
                )}
                {manualReviewData.cl_path && (
                  <div className="flex items-center justify-between p-3 bg-white/60 rounded-lg">
                    <span className="text-sm text-green-700 font-medium">Cover Letter</span>
                    <div className="flex items-center gap-2">
                      {manualReviewData.cl_text && (
                        <button
                          onClick={() => handleCopyCoverLetter(manualReviewData.cl_text!)}
                          className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                            copied
                              ? 'bg-green-100 text-green-700 border border-green-300'
                              : 'bg-sky-100 hover:bg-sky-200 text-sky-700 border border-sky-300'
                          }`}
                        >
                          {copied ? (
                            <><Check className="w-3.5 h-3.5" /> 已复制</>
                          ) : (
                            <><Copy className="w-3.5 h-3.5" /> 复制</>
                          )}
                        </button>
                      )}
                      <button
                        onClick={onOpenCLPreview}
                        disabled={loadingPdf}
                        className="flex items-center gap-2 px-3 py-1.5 bg-sky-100 hover:bg-sky-200 text-sky-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer border border-sky-300 disabled:opacity-50"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        {loadingPdf ? '加载中...' : '预览'}
                      </button>
                      <button
                        onClick={() => onDownloadFile('cover_letter', manualReviewData.cl_path!)}
                        className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                      >
                        <Download className="w-3.5 h-3.5" />
                        下载
                      </button>
                    </div>
                  </div>
                )}
                {manualReviewData.job_url && (
                  <a
                    href={manualReviewData.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-green-600 hover:text-green-700 font-medium transition-colors cursor-pointer"
                  >
                    <ExternalLink className="w-4 h-4" />
                    查看职位详情
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Decision buttons */}
          <div className="pt-4 border-t border-green-200/60">
            <p className="text-sm font-semibold text-green-800 mb-3">请选择操作</p>
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => onDecision('APPLY')}
                className="flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-green-600 to-green-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-green-500/30 hover:shadow-xl hover:shadow-green-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer"
              >
                <CheckCircle className="w-4 h-4" />
                已投递
              </button>
              <button
                onClick={() => onDecision('SKIP_TEMPORARY')}
                className="flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-yellow-600 to-yellow-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-yellow-500/30 hover:shadow-xl hover:shadow-yellow-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer"
              >
                <SkipForward className="w-4 h-4" />
                跳过
              </button>
              <button
                onClick={() => onDecision('SKIP_PERMANENT')}
                className="flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-red-600 to-red-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-red-500/30 hover:shadow-xl hover:shadow-red-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer"
              >
                <XCircle className="w-4 h-4" />
                永久跳过
              </button>
            </div>
            <p className="text-xs text-green-600 mt-2 text-center">
              选择后将继续匹配下一个职位
            </p>
          </div>
        </div>
      )}
    </>
  )
}
