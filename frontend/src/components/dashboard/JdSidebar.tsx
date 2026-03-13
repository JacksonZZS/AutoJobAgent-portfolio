/**
 * JD sidebar overlay showing full job description.
 */
import { X, Gauge, Building2, FileText, ExternalLink } from 'lucide-react'

interface CurrentJob {
  title: string
  company: string
  score?: number
  location?: string
  job_url?: string
  jd_content?: string
}

interface JdSidebarProps {
  job: CurrentJob
  onClose: () => void
}

export default function JdSidebar({ job, onClose }: JdSidebarProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 transition-opacity"
        onClick={onClose}
      />
      {/* Sidebar */}
      <div className="fixed right-0 top-0 h-full w-[500px] max-w-[90vw] z-50 bg-white shadow-2xl transform transition-transform animate-slide-in-right">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-sky-500 to-cyan-500 text-white p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">{job.title}</h2>
              <p className="text-sky-100 text-sm mt-1">{job.company}</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/20 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          {job.score && (
            <div className="mt-3 flex items-center gap-2">
              <Gauge className="w-4 h-4" />
              <span className="text-sm font-medium">匹配度: {job.score}/100</span>
            </div>
          )}
          {job.location && (
            <div className="mt-2 flex items-center gap-2 text-sky-100 text-sm">
              <Building2 className="w-4 h-4" />
              <span>{job.location}</span>
            </div>
          )}
        </div>

        {/* JD content */}
        <div className="p-5 overflow-y-auto h-[calc(100%-180px)]">
          <h3 className="text-sm font-semibold text-sky-700 mb-3 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            职位描述
          </h3>
          {job.jd_content ? (
            <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap leading-relaxed">
              {job.jd_content}
            </div>
          ) : (
            <div className="text-center py-10 text-gray-400">
              <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>暂无职位描述</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-white border-t border-gray-100">
          {job.job_url && (
            <a
              href={job.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full flex items-center justify-center gap-2 py-3 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all"
            >
              <ExternalLink className="w-4 h-4" />
              查看原始职位页面
            </a>
          )}
        </div>
      </div>
    </>
  )
}
