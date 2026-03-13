import React, { useMemo, useState } from 'react'
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Plus,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { resumeOptimizerAPI, type ResumeEditInstruction } from '@/api/resumeOptimizer'

type Step = 'upload' | 'info' | 'optimize'
type TargetProfile = 'general' | 'qa' | 'fintech' | 'da'

interface StepConfig {
  id: Step
  title: string
  subtitle: string
  icon: React.ReactNode
}

interface ProfileOption {
  id: TargetProfile
  label: string
  description: string
}

interface EditInstructionDraft extends ResumeEditInstruction {
  id: string
}

const profileOptions: ProfileOption[] = [
  { id: 'general', label: '通用版', description: '保持平衡表达，适合大多数技术岗位' },
  { id: 'qa', label: 'QA 版', description: '突出测试、自动化、质量保障和缺陷预防' },
  { id: 'fintech', label: 'FinTech 版', description: '突出金融业务、风控、准确性与稳定性' },
  { id: 'da', label: 'DA 版', description: '突出 SQL、分析、报表、洞察和业务支持' },
]

const emptyInstruction = (): EditInstructionDraft => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  action: 'modify',
  target: '',
  content: '',
})

const ResumeOptimizerPage: React.FC = () => {
  const { token } = useAuthStore()
  const [currentStep, setCurrentStep] = useState<Step>('upload')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [optimizedPdf, setOptimizedPdf] = useState<string | null>(null)
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [optimizedFilename, setOptimizedFilename] = useState('optimized_resume.pdf')
  const [optimizedPdfPath, setOptimizedPdfPath] = useState('')
  const [saveLabel, setSaveLabel] = useState('')
  const [saveAsDefault, setSaveAsDefault] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [formData, setFormData] = useState({
    isPermanentResident: false,
    canStartImmediately: false,
    linkedinUrl: '',
    githubUrl: '',
    portfolioUrl: '',
    targetProfile: 'general' as TargetProfile,
    additionalNotes: '',
  })
  const [editInstructions, setEditInstructions] = useState<EditInstructionDraft[]>([emptyInstruction()])

  const steps: StepConfig[] = [
    {
      id: 'upload',
      title: '上传简历',
      subtitle: '支持 PDF 格式，最大 10MB',
      icon: <Upload className="w-6 h-6" />,
    },
    {
      id: 'info',
      title: '优化设置',
      subtitle: '选择版本并配置修改指令',
      icon: <FileText className="w-6 h-6" />,
    },
    {
      id: 'optimize',
      title: 'AI 优化',
      subtitle: '生成定制化简历版本',
      icon: <Sparkles className="w-6 h-6" />,
    },
  ]

  const currentStepIndex = steps.findIndex((step) => step.id === currentStep)
  const progressPercent = ((currentStepIndex + 1) / steps.length) * 100
  const selectedProfile = useMemo(
    () => profileOptions.find((option) => option.id === formData.targetProfile),
    [formData.targetProfile]
  )

  const buildInstructionsPayload = (): ResumeEditInstruction[] =>
    editInstructions
      .map(({ action, target, content }) => ({
        action,
        target: target.trim(),
        content: content?.trim(),
      }))
      .filter((item) => item.target && (item.action === 'delete' || item.content))

  const runOptimization = async (notesOverride?: string) => {
    if (!resumeFile) {
      alert('请先上传简历')
      return
    }

    if (!token) {
      alert('请先登录')
      return
    }

    setIsOptimizing(true)
    try {
      const result = await resumeOptimizerAPI.optimizeResume(
        {
          resume_file: resumeFile,
          permanent_resident: formData.isPermanentResident,
          available_immediately: formData.canStartImmediately,
          linkedin_url: formData.linkedinUrl,
          github_url: formData.githubUrl,
          portfolio_url: formData.portfolioUrl,
          target_profile: formData.targetProfile,
          edit_instructions: buildInstructionsPayload(),
          additional_notes: notesOverride ?? formData.additionalNotes,
        },
        token
      )

      const filename = result.pdf_path.split('/').pop() || 'optimized_resume.pdf'
      const pdfBlob = await resumeOptimizerAPI.downloadResume(encodeURIComponent(filename), token)
      const blobUrl = URL.createObjectURL(pdfBlob)
      setOptimizedPdfPath(result.pdf_path)
      setOptimizedFilename(filename)
      setOptimizedPdf(blobUrl)
    } catch (error: any) {
      console.error('优化失败:', error)
      alert(error.message || '简历优化失败，请重试')
    } finally {
      setIsOptimizing(false)
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setResumeFile(e.target.files[0])
    }
  }

  const addInstruction = () => {
    setEditInstructions((prev) => [...prev, emptyInstruction()])
  }

  const updateInstruction = (
    id: string,
    field: 'action' | 'target' | 'content',
    value: string
  ) => {
    setEditInstructions((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [field]: value } : item))
    )
  }

  const removeInstruction = (id: string) => {
    setEditInstructions((prev) => {
      if (prev.length === 1) {
        return [emptyInstruction()]
      }
      return prev.filter((item) => item.id !== id)
    })
  }

  const goNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStep(steps[currentStepIndex + 1].id)
    }
  }

  const goPrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStep(steps[currentStepIndex - 1].id)
    }
  }

  const saveToResumeLibrary = async () => {
    if (!token || !optimizedPdfPath) {
      return
    }

    setIsSaving(true)
    try {
      const form = new FormData()
      form.append('source_pdf_path', optimizedPdfPath)
      form.append('label', saveLabel || selectedProfile?.label || '优化版')
      form.append('is_default', String(saveAsDefault))

      const response = await fetch('/api/v1/upload/resume/save-optimized', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: form,
      })

      const data = await response.json().catch(() => null)
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || '保存失败')
      }

      alert(data?.message || '已保存到简历管理')
    } catch (error: any) {
      alert(error.message || '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold text-gradient">AI 简历优化</h1>
        <p className="text-sky-600 dark:text-sky-400">
          不只是润色，直接生成 QA、FinTech、DA 等目标版本
        </p>
      </div>

      <div className="glass-card p-6 animate-slide-down">
        <div className="flex items-center justify-between mb-4">
          {steps.map((step, index) => (
            <React.Fragment key={step.id}>
              <div className="flex items-center space-x-3">
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 ${
                    index <= currentStepIndex
                      ? 'bg-gradient-to-r from-sky-500 to-cyan-500 text-white shadow-lg shadow-sky-500/30'
                      : 'bg-sky-100 dark:bg-slate-700 text-sky-400 dark:text-slate-400'
                  }`}
                >
                  {index < currentStepIndex ? <Check className="w-6 h-6" /> : step.icon}
                </div>
                <div className="hidden md:block">
                  <div
                    className={`font-semibold ${
                      index <= currentStepIndex
                        ? 'text-sky-700 dark:text-sky-300'
                        : 'text-sky-400 dark:text-slate-500'
                    }`}
                  >
                    {step.title}
                  </div>
                  <div className="text-xs text-sky-500 dark:text-slate-400">{step.subtitle}</div>
                </div>
              </div>
              {index < steps.length - 1 && (
                <div className="flex-1 h-1 mx-4 bg-sky-100 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r from-sky-500 to-cyan-500 transition-all duration-500 ${
                      index < currentStepIndex ? 'w-full' : 'w-0'
                    }`}
                  />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
        <div className="text-center text-sm text-sky-600 dark:text-sky-400 font-medium">
          进度: {Math.round(progressPercent)}%
        </div>
      </div>

      <div className="glass-card p-8 animate-fade-in">
        {currentStep === 'upload' && (
          <div className="space-y-6">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto bg-gradient-to-r from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30 mb-4">
                <Upload className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">上传你的简历</h2>
              <p className="text-sky-600 dark:text-sky-400">支持 PDF 格式，文件大小不超过 10MB</p>
            </div>

            <div
              className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer ${
                resumeFile
                  ? 'border-green-400 dark:border-green-500 bg-green-50/50 dark:bg-green-900/20'
                  : 'border-sky-300 dark:border-sky-600 hover:border-sky-500 dark:hover:border-sky-400 hover:bg-sky-50/30 dark:hover:bg-sky-900/10'
              }`}
              onClick={() => document.getElementById('fileInput')?.click()}
            >
              <input
                id="fileInput"
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileUpload}
              />
              {resumeFile ? (
                <div className="space-y-3">
                  <FileText className="w-12 h-12 mx-auto text-green-600 dark:text-green-400" />
                  <div>
                    <div className="font-medium text-sky-800 dark:text-sky-200">{resumeFile.name}</div>
                    <div className="text-sm text-sky-600 dark:text-sky-400">
                      {(resumeFile.size / 1024 / 1024).toFixed(2)} MB
                    </div>
                  </div>
                  <button
                    className="text-sm text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 underline font-medium"
                    onClick={(e) => {
                      e.stopPropagation()
                      setResumeFile(null)
                    }}
                  >
                    重新上传
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="w-12 h-12 mx-auto text-sky-400 dark:text-sky-500" />
                  <div>
                    <div className="text-lg font-medium text-sky-700 dark:text-sky-300">点击或拖拽文件到这里</div>
                    <div className="text-sm text-sky-500 dark:text-sky-400 mt-1">支持的格式：PDF</div>
                  </div>
                </div>
              )}
            </div>

            <div className="bg-sky-50/50 dark:bg-sky-900/20 rounded-lg p-4 border border-sky-200/60 dark:border-sky-700/60">
              <div className="flex items-start space-x-3">
                <Sparkles className="w-5 h-5 text-sky-600 dark:text-sky-400 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-sky-700 dark:text-sky-300">
                  建议先上传最完整的主简历，再通过下面的目标版本和结构化指令生成不同方向版本。
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === 'info' && (
          <div className="space-y-8">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto bg-gradient-to-r from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30 mb-4">
                <FileText className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">配置优化方式</h2>
              <p className="text-sky-600 dark:text-sky-400">先选目标版本，再明确告诉 AI 哪一段要删、加、改</p>
            </div>

            <div className="space-y-5">
              <div className="space-y-3">
                <h3 className="text-lg font-semibold text-sky-800 dark:text-sky-200">目标版本</h3>
                <div className="grid md:grid-cols-2 gap-4">
                  {profileOptions.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setFormData({ ...formData, targetProfile: option.id })}
                      className={`text-left rounded-xl border p-4 transition-all ${
                        formData.targetProfile === option.id
                          ? 'border-sky-500 bg-sky-50/70 dark:bg-sky-900/20 shadow-lg shadow-sky-500/10'
                          : 'border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 hover:border-sky-300 dark:hover:border-sky-500'
                      }`}
                    >
                      <div className="font-semibold text-sky-800 dark:text-sky-200">{option.label}</div>
                      <div className="text-sm mt-1 text-sky-600 dark:text-sky-400">{option.description}</div>
                    </button>
                  ))}
                </div>
                <p className="text-xs text-sky-500 dark:text-slate-400">
                  当前选择：{selectedProfile?.label}，AI 会根据这个方向重写 summary、关键词和项目表述。
                </p>
              </div>

              <div className="space-y-3">
                <h3 className="text-lg font-semibold text-sky-800 dark:text-sky-200">结构化编辑指令</h3>
                <div className="space-y-4">
                  {editInstructions.map((instruction, index) => (
                    <div
                      key={instruction.id}
                      className="rounded-xl border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 p-4 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-semibold text-sky-700 dark:text-sky-300">
                          指令 {index + 1}
                        </div>
                        <button
                          type="button"
                          onClick={() => removeInstruction(instruction.id)}
                          className="text-rose-500 hover:text-rose-600"
                          aria-label={`删除指令 ${index + 1}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="grid md:grid-cols-[140px_1fr] gap-3">
                        <select
                          value={instruction.action}
                          onChange={(e) => updateInstruction(instruction.id, 'action', e.target.value)}
                          className="px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/80 dark:bg-slate-800/80 text-sky-800 dark:text-sky-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        >
                          <option value="modify">修改</option>
                          <option value="delete">删除</option>
                          <option value="add">增加</option>
                        </select>
                        <input
                          type="text"
                          placeholder="目标位置，例如：AutoJobAgent 项目 / summary / 第二段实习"
                          value={instruction.target}
                          onChange={(e) => updateInstruction(instruction.id, 'target', e.target.value)}
                          className="px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/80 dark:bg-slate-800/80 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        />
                      </div>

                      <textarea
                        rows={3}
                        placeholder={
                          instruction.action === 'delete'
                            ? '删除指令不一定需要补充内容，可留空'
                            : '填写要新增或改写成什么样子，例如更偏 QA、加上指标、强调 SQL 和 dashboard'
                        }
                        value={instruction.content || ''}
                        onChange={(e) => updateInstruction(instruction.id, 'content', e.target.value)}
                        className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/80 dark:bg-slate-800/80 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 resize-none"
                      />
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={addInstruction}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-sky-300 text-sky-700 hover:bg-sky-50 dark:border-sky-700 dark:text-sky-300 dark:hover:bg-sky-900/20 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  新增一条指令
                </button>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <label className="flex items-center justify-between p-4 bg-white/60 dark:bg-slate-800/60 rounded-lg border border-sky-200/60 dark:border-slate-600/60">
                  <div>
                    <div className="font-medium text-sky-800 dark:text-sky-200">永久居民身份</div>
                    <div className="text-sm text-sky-600 dark:text-sky-400">是否拥有本地长期工作资格</div>
                  </div>
                  <input
                    type="checkbox"
                    className="toggle"
                    checked={formData.isPermanentResident}
                    onChange={(e) => setFormData({ ...formData, isPermanentResident: e.target.checked })}
                  />
                </label>

                <label className="flex items-center justify-between p-4 bg-white/60 dark:bg-slate-800/60 rounded-lg border border-sky-200/60 dark:border-slate-600/60">
                  <div>
                    <div className="font-medium text-sky-800 dark:text-sky-200">立即上班</div>
                    <div className="text-sm text-sky-600 dark:text-sky-400">可在简历中标注 available immediately</div>
                  </div>
                  <input
                    type="checkbox"
                    className="toggle"
                    checked={formData.canStartImmediately}
                    onChange={(e) => setFormData({ ...formData, canStartImmediately: e.target.checked })}
                  />
                </label>
              </div>

              <div className="grid md:grid-cols-3 gap-4">
                <input
                  type="url"
                  placeholder="LinkedIn"
                  value={formData.linkedinUrl}
                  onChange={(e) => setFormData({ ...formData, linkedinUrl: e.target.value })}
                  className="px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <input
                  type="url"
                  placeholder="GitHub"
                  value={formData.githubUrl}
                  onChange={(e) => setFormData({ ...formData, githubUrl: e.target.value })}
                  className="px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <input
                  type="url"
                  placeholder="Portfolio"
                  value={formData.portfolioUrl}
                  onChange={(e) => setFormData({ ...formData, portfolioUrl: e.target.value })}
                  className="px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                  补充要求
                </label>
                <textarea
                  rows={4}
                  placeholder="补充整体要求，例如：保留技术真实度，不要编造经历；把 AutoJobAgent 写得更像数据分析项目。"
                  value={formData.additionalNotes}
                  onChange={(e) => setFormData({ ...formData, additionalNotes: e.target.value })}
                  className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 resize-none"
                />
              </div>
            </div>
          </div>
        )}

        {currentStep === 'optimize' && (
          <div className="space-y-6">
            {!optimizedPdf ? (
              <div className="text-center space-y-6">
                <div className="w-16 h-16 mx-auto bg-gradient-to-r from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30">
                  <Sparkles className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">准备生成</h2>
                  <p className="text-sky-600 dark:text-sky-400">
                    将按 {selectedProfile?.label} 方向生成，并执行 {buildInstructionsPayload().length} 条结构化编辑指令
                  </p>
                </div>

                <div className="grid md:grid-cols-3 gap-4 text-left">
                  {[
                    { icon: '🎯', title: '目标版本', desc: selectedProfile?.label || '通用版' },
                    { icon: '🧩', title: '结构化编辑', desc: `${buildInstructionsPayload().length} 条指令` },
                    { icon: '📄', title: '输出结果', desc: '生成新的 PDF 简历版本' },
                  ].map((item) => (
                    <div
                      key={item.title}
                      className="bg-white/60 dark:bg-slate-800/60 rounded-lg p-4 border border-sky-200/60 dark:border-slate-600/60"
                    >
                      <div className="text-3xl mb-2">{item.icon}</div>
                      <div className="font-medium text-sky-800 dark:text-sky-200">{item.title}</div>
                      <div className="text-sm text-sky-600 dark:text-sky-400">{item.desc}</div>
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => runOptimization()}
                  disabled={isOptimizing}
                  className="px-8 py-4 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-sky-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isOptimizing ? 'AI 优化中...' : '开始 AI 优化'}
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center mb-4 shadow-lg shadow-green-500/30">
                    <Check className="w-8 h-8 text-white" />
                  </div>
                  <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">优化完成</h2>
                  <p className="text-sky-600 dark:text-sky-400">你可以预览、下载，或继续给反馈再生成一版</p>
                </div>

                <div className="bg-sky-100/50 dark:bg-slate-700/50 rounded-lg p-4 border-2 border-sky-200/60 dark:border-slate-600/60">
                  <iframe src={optimizedPdf} className="w-full h-[500px] rounded-lg" title="优化后的简历" />
                </div>

                <div className="bg-white/60 dark:bg-slate-800/60 rounded-lg p-4 border border-sky-200/60 dark:border-slate-600/60">
                  <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                    反馈意见
                  </label>
                  <textarea
                    rows={3}
                    placeholder="例如：把 AutoJobAgent 那段再改得更偏 DA；删除最后一个项目；summary 更简洁"
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 resize-none"
                  />
                </div>

                <div className="bg-white/60 dark:bg-slate-800/60 rounded-lg p-4 border border-sky-200/60 dark:border-slate-600/60 space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                      保存到简历管理
                    </label>
                    <input
                      type="text"
                      value={saveLabel}
                      onChange={(e) => setSaveLabel(e.target.value)}
                      placeholder={`例如：${selectedProfile?.label || '优化版'} / QA_v2 / FinTech_2026`}
                      className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>
                  <label className="flex items-center justify-between p-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60">
                    <div>
                      <div className="font-medium text-sky-800 dark:text-sky-200">设为默认简历</div>
                      <div className="text-sm text-sky-600 dark:text-sky-400">后续任务默认使用这一版</div>
                    </div>
                    <input
                      type="checkbox"
                      className="toggle"
                      checked={saveAsDefault}
                      onChange={(e) => setSaveAsDefault(e.target.checked)}
                    />
                  </label>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                  <a
                    href={optimizedPdf}
                    download={optimizedFilename}
                    className="flex-1 py-3 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-sky-500/40 text-center flex items-center justify-center space-x-2"
                  >
                    <Download className="w-5 h-5" />
                    <span>下载简历</span>
                  </a>
                  <button
                    onClick={saveToResumeLibrary}
                    disabled={isSaving}
                    className="px-6 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-lg font-semibold hover:from-emerald-600 hover:to-teal-600 transition-all shadow-lg shadow-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    <span>{isSaving ? '保存中...' : '保存到简历库'}</span>
                  </button>
                  <button
                    onClick={() => runOptimization(feedback)}
                    disabled={isOptimizing || !feedback.trim()}
                    className="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-lg font-semibold hover:from-amber-600 hover:to-orange-600 transition-all shadow-lg shadow-amber-500/30 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    <Sparkles className="w-5 h-5" />
                    <span>{isOptimizing ? '优化中...' : '根据反馈再优化'}</span>
                  </button>
                  <button
                    onClick={() => {
                      setOptimizedPdf(null)
                      setFeedback('')
                      setCurrentStep('info')
                    }}
                    className="px-6 py-3 bg-white/60 dark:bg-slate-800/60 border border-sky-200/60 dark:border-slate-600/60 text-sky-700 dark:text-sky-300 rounded-lg font-medium hover:bg-white/80 dark:hover:bg-slate-700/80 transition-all"
                  >
                    继续编辑
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {!optimizedPdf && (
        <div className="flex justify-between">
          <button
            onClick={goPrev}
            disabled={currentStepIndex === 0}
            className="px-6 py-3 bg-white/60 dark:bg-slate-800/60 border border-sky-200/60 dark:border-slate-600/60 text-sky-700 dark:text-sky-300 rounded-lg font-medium hover:bg-white/80 dark:hover:bg-slate-700/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            <ChevronLeft className="w-5 h-5" />
            <span>上一步</span>
          </button>

          <button
            onClick={goNext}
            disabled={(currentStep === 'upload' && !resumeFile) || currentStepIndex === steps.length - 1}
            className="px-6 py-3 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-sky-500/40 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            <span>下一步</span>
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      )}

      <style>{`
        .toggle {
          appearance: none;
          width: 3rem;
          height: 1.5rem;
          background-color: #e0f2fe;
          border-radius: 9999px;
          position: relative;
          cursor: pointer;
          transition: background-color 0.3s;
        }

        .dark .toggle {
          background-color: #334155;
        }

        .toggle:checked {
          background-color: #0ea5e9;
        }

        .dark .toggle:checked {
          background-color: #38bdf8;
        }

        .toggle::before {
          content: '';
          position: absolute;
          width: 1.25rem;
          height: 1.25rem;
          background-color: white;
          border-radius: 9999px;
          top: 0.125rem;
          left: 0.125rem;
          transition: transform 0.3s;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .toggle:checked::before {
          transform: translateX(1.5rem);
        }
      `}</style>
    </div>
  )
}

export default ResumeOptimizerPage
