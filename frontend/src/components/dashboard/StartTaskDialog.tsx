/**
 * Smart start dialog: upload resume → AI analyze → confirm params → start task.
 */
import { useState, useEffect } from 'react'
import {
  Upload, FileText, Loader2, X, ArrowRight,
  Target, Sparkles, Play, Building2, Filter, Gauge
} from 'lucide-react'
import { uploadAPI, LastUploadInfo } from '@/api/upload'
import { analysisAPI } from '@/api/analysis'
import { jobsAPI } from '@/api/jobs'

interface StartTaskDialogProps {
  onClose: () => void
}

export default function StartTaskDialog({ onClose }: StartTaskDialogProps) {
  const [step, setStep] = useState<'upload' | 'uploaded' | 'analyzing' | 'confirm'>('upload')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [lastUpload, setLastUpload] = useState<LastUploadInfo | null>(null)
  const [useLastUpload, setUseLastUpload] = useState(false)
  const [selectedPlatform, setSelectedPlatform] = useState<'jobsdb' | 'indeed' | 'linkedin'>('jobsdb')
  const [resumePath, setResumePath] = useState('')
  const [transcriptPath, setTranscriptPath] = useState('')
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [formData, setFormData] = useState({
    keywords: '',
    target_count: 10,
    company_blacklist: '',
    title_exclusions: '',
    score_threshold: 60
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchLastUpload = async () => {
      try {
        const data = await uploadAPI.getLastUpload()
        if (data.has_resume) {
          setLastUpload(data)
          if (data.last_platform) {
            setSelectedPlatform(data.last_platform)
          }
        }
      } catch {
        // No previous upload
      }
    }
    fetchLastUpload()
  }, [])

  const handleUploadOnly = async () => {
    if (!resumeFile) {
      setError('请先上传简历')
      return
    }
    setUploading(true)
    setError('')

    try {
      const resumeResult = await uploadAPI.uploadResume(resumeFile)
      setResumePath(resumeResult.file_path)

      if (transcriptFile) {
        const transcriptResult = await uploadAPI.uploadTranscript(transcriptFile)
        setTranscriptPath(transcriptResult.file_path)
      }

      // Cache analysis result if available, but don't auto-trigger
      if (resumeResult.cached_analysis) {
        setAnalysisResult(resumeResult.cached_analysis)
      }

      setStep('uploaded')
    } catch (err: any) {
      setError(err.response?.data?.detail || '上传失败，请重试')
      setStep('upload')
    } finally {
      setUploading(false)
    }
  }

  const handleStartAnalysis = async () => {
    setError('')

    // If we already have cached analysis, skip API call
    if (analysisResult) {
      setFormData({
        keywords: analysisResult.keywords || '',
        target_count: 10,
        company_blacklist: analysisResult.blocked_companies || '',
        title_exclusions: analysisResult.title_exclusions || '',
        score_threshold: 60
      })
      setStep('confirm')
      return
    }

    setStep('analyzing')
    try {
      const analysisData = await analysisAPI.analyzeResume({
        resume_path: resumePath,
        transcript_path: transcriptPath || undefined
      })
      setAnalysisResult(analysisData)
      setFormData({
        keywords: analysisData.keywords || '',
        target_count: 10,
        company_blacklist: analysisData.blocked_companies || '',
        title_exclusions: analysisData.title_exclusions || '',
        score_threshold: 60
      })
      setStep('confirm')
    } catch (err: any) {
      setError(err.response?.data?.detail || '分析失败，请重试')
      setStep('uploaded')
    }
  }

  const handleStartTask = async () => {
    setIsSubmitting(true)
    setError('')
    try {
      const payload = {
        keywords: formData.keywords,
        platform: selectedPlatform,
        target_count: formData.target_count,
        company_blacklist: formData.company_blacklist
          ? formData.company_blacklist.split(',').map(s => s.trim())
          : [],
        title_exclusions: formData.title_exclusions
          ? formData.title_exclusions.split(',').map(s => s.trim())
          : [],
        score_threshold: formData.score_threshold,
        resume_path: resumePath,
        transcript_path: transcriptPath || undefined
      }
      await jobsAPI.startTask(payload)
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || '启动任务失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleUseLastUpload = async () => {
    if (!lastUpload) return
    setUseLastUpload(true)
    const currentResumePath = lastUpload.resume_path || ''
    const currentTranscriptPath = lastUpload.transcript_path || ''
    setResumePath(currentResumePath)
    if (currentTranscriptPath) setTranscriptPath(currentTranscriptPath)

    // Cache analysis if available, but don't auto-trigger
    if (lastUpload.cached_analysis) {
      setAnalysisResult(lastUpload.cached_analysis)
    }

    // Stop at 'uploaded' step, wait for user to click "启动分析"
    setStep('uploaded')
  }

  const handleClose = () => {
    if (!uploading && !isSubmitting) onClose()
  }

  const platforms = [
    { id: 'jobsdb' as const, emoji: '🇭🇰', name: 'JobsDB', region: '香港' },
    { id: 'indeed' as const, emoji: '🇭🇰', name: 'Indeed', region: '香港' },
    { id: 'linkedin' as const, emoji: '💼', name: 'LinkedIn', region: '全球' },
  ]

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="glass-card w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-scale-in scrollbar-thin">
        {/* Header */}
        <div className="sticky top-0 bg-white/80 backdrop-blur-md p-6 border-b border-sky-200/60 z-10">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-sky-900 flex items-center gap-2">
              {step === 'upload' && <><Upload className="w-5 h-5" /> 上传简历</>}
              {step === 'uploaded' && <><Sparkles className="w-5 h-5" /> 文档已就绪</>}
              {step === 'analyzing' && <><Loader2 className="w-5 h-5 animate-spin" /> AI 智能分析中...</>}
              {step === 'confirm' && <><Target className="w-5 h-5" /> 确认任务参数</>}
            </h2>
            <button
              onClick={handleClose}
              disabled={uploading || isSubmitting}
              className="p-2 hover:bg-sky-100 rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-5 h-5 text-sky-600" />
            </button>
          </div>
        </div>

        <div className="p-6">
          {error && (
            <div className="bg-red-50/80 border border-red-200 text-red-700 text-sm py-3 px-4 rounded-xl mb-6 animate-fade-in">
              {error}
            </div>
          )}

          {/* Step 1: Upload */}
          {step === 'upload' && (
            <div className="space-y-6">
              {/* Platform selection */}
              <div>
                <label className="block text-sm font-semibold text-sky-800 mb-3">
                  选择求职平台 <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {platforms.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setSelectedPlatform(p.id)}
                      className={`p-4 rounded-xl border-2 transition-all cursor-pointer ${
                        selectedPlatform === p.id
                          ? 'border-sky-500 bg-sky-50/80 text-sky-800'
                          : 'border-gray-200 bg-white/60 text-gray-600 hover:border-sky-300'
                      }`}
                    >
                      <div className="text-2xl mb-1">{p.emoji}</div>
                      <div className="font-semibold">{p.name}</div>
                      <div className="text-xs text-gray-500">{p.region}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Use last upload */}
              {lastUpload?.has_resume && !useLastUpload && (
                <div className="bg-green-50/80 border border-green-200 p-4 rounded-xl animate-fade-in">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-green-800 font-semibold">📂 发现上次上传的文档</p>
                      <p className="text-green-600 text-sm mt-1">
                        简历: {lastUpload.resume_filename}
                        {lastUpload.has_transcript && ` | 成绩单: ${lastUpload.transcript_filename}`}
                      </p>
                    </div>
                    <button
                      onClick={handleUseLastUpload}
                      disabled={isSubmitting}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSubmitting ? '启动中...' : '使用上次文档'}
                    </button>
                  </div>
                </div>
              )}

              {useLastUpload ? (
                <div className="bg-sky-50/80 border border-sky-200 p-4 rounded-xl">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sky-800 font-semibold">✅ 使用上次上传的文档</p>
                      <p className="text-sky-600 text-sm mt-1">{lastUpload?.resume_filename}</p>
                    </div>
                    <button
                      onClick={() => {
                        setUseLastUpload(false)
                        setResumePath('')
                        setTranscriptPath('')
                      }}
                      className="text-sky-600 hover:text-sky-800 text-sm font-semibold"
                    >
                      更换文档
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-semibold text-sky-800 mb-3">
                      简历文件 <span className="text-red-500">*</span>
                    </label>
                    <div className="border-2 border-dashed border-sky-300 hover:border-sky-500 p-8 text-center transition-colors rounded-xl bg-white/40 cursor-pointer">
                      <input
                        type="file"
                        accept=".pdf"
                        onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                        className="hidden"
                        id="resume-upload"
                      />
                      <label htmlFor="resume-upload" className="cursor-pointer">
                        {resumeFile ? (
                          <div className="text-sky-700">
                            <FileText className="w-12 h-12 mx-auto mb-3 text-sky-600" />
                            <p className="font-semibold">{resumeFile.name}</p>
                            <p className="text-xs text-sky-500 mt-1">
                              {(resumeFile.size / 1024).toFixed(1)} KB
                            </p>
                          </div>
                        ) : (
                          <div className="text-sky-600">
                            <Upload className="w-12 h-12 mx-auto mb-3" />
                            <p className="font-semibold">点击上传 PDF 文件</p>
                            <p className="text-xs mt-1">或拖拽文件到这里</p>
                          </div>
                        )}
                      </label>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-sky-800 mb-3">
                      成绩单（可选）
                    </label>
                    <div className="border-2 border-dashed border-sky-200 hover:border-sky-400 p-8 text-center transition-colors rounded-xl bg-white/40 cursor-pointer">
                      <input
                        type="file"
                        accept=".pdf"
                        onChange={(e) => setTranscriptFile(e.target.files?.[0] || null)}
                        className="hidden"
                        id="transcript-upload"
                      />
                      <label htmlFor="transcript-upload" className="cursor-pointer">
                        {transcriptFile ? (
                          <div className="text-sky-700">
                            <FileText className="w-12 h-12 mx-auto mb-3 text-sky-600" />
                            <p className="font-semibold">{transcriptFile.name}</p>
                            <p className="text-xs text-sky-500 mt-1">
                              {(transcriptFile.size / 1024).toFixed(1)} KB
                            </p>
                          </div>
                        ) : (
                          <div className="text-sky-500">
                            <Upload className="w-12 h-12 mx-auto mb-3" />
                            <p className="font-semibold">点击上传成绩单</p>
                            <p className="text-xs mt-1">用于增强简历分析准确度</p>
                          </div>
                        )}
                      </label>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 1.5: Uploaded - wait for user to start analysis */}
          {step === 'uploaded' && (
            <div className="py-8 text-center space-y-4">
              <FileText className="w-16 h-16 text-green-500 mx-auto" />
              <p className="text-sky-800 font-semibold text-lg">文档已上传成功</p>
              <p className="text-sky-600 text-sm">
                {resumePath ? resumePath.split('/').pop() : '简历已就绪'}
                {transcriptPath && ` + ${transcriptPath.split('/').pop()}`}
              </p>
              {analysisResult && (
                <p className="text-green-600 text-xs">已检测到历史分析缓存，点击下方按钮即可秒速加载</p>
              )}
              <p className="text-sky-500 text-sm mt-2">准备好后，点击下方「启动 AI 分析」按钮开始分析</p>
            </div>
          )}

          {/* Step 2: Analyzing */}
          {step === 'analyzing' && (
            <div className="py-12 text-center">
              <Loader2 className="w-16 h-16 text-sky-600 mx-auto mb-4 animate-spin" />
              <p className="text-sky-700 font-semibold">AI 正在分析您的简历...</p>
              <p className="text-xs text-sky-500 mt-2">这可能需要 10-30 秒</p>
            </div>
          )}

          {/* Step 3: Confirm params */}
          {step === 'confirm' && (
            <div className="space-y-5">
              {analysisResult?.user_profile && (
                <div className="glass-card p-4 border-l-4 border-sky-500">
                  <div className="flex items-start gap-3">
                    <Sparkles className="w-5 h-5 text-sky-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-semibold text-sky-800 mb-1">AI 分析结果</p>
                      <p className="text-sm text-sky-700">{analysisResult.user_profile}</p>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-semibold text-sky-800 mb-2">
                  搜索关键词 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="AI 生成的关键词"
                  className="glass-input"
                  value={formData.keywords}
                  onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
                />
                <p className="text-xs text-sky-600 mt-1">AI 已为您生成，可手动调整</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-sky-800 mb-2">
                  目标职位数量
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  className="glass-input"
                  value={formData.target_count}
                  onChange={(e) => setFormData({ ...formData, target_count: parseInt(e.target.value) })}
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-sky-800 mb-2 flex items-center gap-2">
                  <Building2 className="w-4 h-4" />
                  公司黑名单
                </label>
                <input
                  type="text"
                  placeholder="AI 识别的前雇主"
                  className="glass-input"
                  value={formData.company_blacklist}
                  onChange={(e) => setFormData({ ...formData, company_blacklist: e.target.value })}
                />
                <p className="text-xs text-sky-600 mt-1">AI 已自动识别前雇主，可手动调整</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-sky-800 mb-2 flex items-center gap-2">
                  <Filter className="w-4 h-4" />
                  职位标题排除
                </label>
                <input
                  type="text"
                  placeholder="AI 生成的排除词"
                  className="glass-input"
                  value={formData.title_exclusions}
                  onChange={(e) => setFormData({ ...formData, title_exclusions: e.target.value })}
                />
                <p className="text-xs text-sky-600 mt-1">基于您的资历等级自动生成</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-sky-800 mb-2 flex items-center gap-2">
                  <Gauge className="w-4 h-4" />
                  匹配分数阈值 <span className="text-red-500">*</span>
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    className="flex-1 accent-sky-600"
                    value={formData.score_threshold}
                    onChange={(e) => setFormData({ ...formData, score_threshold: parseInt(e.target.value) })}
                  />
                  <input
                    type="number"
                    min="0"
                    max="100"
                    className="w-20 px-3 py-2 glass-input text-center font-bold"
                    value={formData.score_threshold}
                    onChange={(e) => setFormData({ ...formData, score_threshold: parseInt(e.target.value) || 0 })}
                  />
                  <span className="text-sm text-sky-700 font-semibold">分</span>
                </div>
                <p className="text-xs text-sky-600 mt-1">
                  只有匹配度 ≥ {formData.score_threshold} 分的职位才会被投递
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer buttons */}
        <div className="sticky bottom-0 bg-white/80 backdrop-blur-md p-6 border-t border-sky-200/60 flex gap-3 justify-end">
          <button
            className="glass-button-secondary"
            onClick={handleClose}
            disabled={uploading || isSubmitting}
          >
            取消
          </button>

          {step === 'upload' && (
            <button
              className="glass-button flex items-center gap-2"
              onClick={handleUploadOnly}
              disabled={!resumeFile || uploading}
            >
              {uploading ? '上传中...' : '上传文档'}
              <ArrowRight className="w-5 h-5" />
            </button>
          )}

          {step === 'uploaded' && (
            <button
              className="glass-button flex items-center gap-2"
              onClick={handleStartAnalysis}
            >
              启动 AI 分析
              <Sparkles className="w-5 h-5" />
            </button>
          )}

          {step === 'confirm' && (
            <button
              className="glass-button-success flex items-center gap-2"
              onClick={handleStartTask}
              disabled={isSubmitting || !formData.keywords.trim()}
            >
              {isSubmitting ? '启动中...' : '开始投递'}
              <Play className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
