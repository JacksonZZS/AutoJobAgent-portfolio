/**
 * 候选人支持组件 - AI 生成岗位问答与回答建议
 * 支持 JD 链接抓取 + 结合简历生成针对性问题
 */

import { useState, useEffect } from 'react'
import {
  Brain,
  MessageSquare,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  Send,
  Loader2,
  CheckCircle,
  Target,
  TrendingUp,
  BookOpen,
  Sparkles,
  Link,
  FileText,
  AlertCircle
} from 'lucide-react'

interface CandidateSupportQuestion {
  id: number
  category: string
  question: string
  suggested_answer: string
  tips: string[]
  difficulty: string
}

interface AnswerFeedback {
  score: number
  strengths: string[]
  improvements: string[]
  better_answer: string
}

interface Resume {
  id: string
  filename: string
  label?: string
  is_default: boolean
}

export default function CandidateSupport() {
  // JD 链接相关
  const [jdUrl, setJdUrl] = useState('')
  const [fetchingJd, setFetchingJd] = useState(false)
  const [jdError, setJdError] = useState('')

  // 简历相关
  const [resumes, setResumes] = useState<Resume[]>([])
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [loadingResumes, setLoadingResumes] = useState(true)

  // 职位信息
  const [jobTitle, setJobTitle] = useState('')
  const [company, setCompany] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [questionCount, setQuestionCount] = useState(10)
  const [selectedTypes, setSelectedTypes] = useState(['technical', 'behavioral', 'situational'])

  // 生成状态
  const [loading, setLoading] = useState(false)
  const [questions, setQuestions] = useState<CandidateSupportQuestion[]>([])
  const [resumeUsed, setResumeUsed] = useState(false)
  const [expandedQuestions, setExpandedQuestions] = useState<Set<number>>(new Set())
  const [userAnswers, setUserAnswers] = useState<Record<number, string>>({})
  const [feedback, setFeedback] = useState<Record<number, AnswerFeedback>>({})
  const [evaluating, setEvaluating] = useState<number | null>(null)

  // 加载简历列表
  useEffect(() => {
    loadResumes()
  }, [])

  const loadResumes = async () => {
    try {
      setLoadingResumes(true)
      const response = await fetch('/api/v1/upload/resumes', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })
      if (response.ok) {
        const data = await response.json()
        setResumes(data.resumes || [])
        // 自动选择默认简历
        const defaultResume = data.resumes?.find((r: Resume) => r.is_default)
        if (defaultResume) {
          setSelectedResumeId(defaultResume.id)
        }
      }
    } catch (error) {
      console.error('加载简历列表失败:', error)
    } finally {
      setLoadingResumes(false)
    }
  }

  // 抓取 JD
  const handleFetchJd = async () => {
    if (!jdUrl.trim()) return

    setFetchingJd(true)
    setJdError('')

    try {
      const response = await fetch('/api/v1/candidate-support/fetch-jd', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ url: jdUrl })
      })

      const data = await response.json()

      if (data.success) {
        setJobTitle(data.job_title || '')
        setCompany(data.company || '')
        setJobDescription(data.job_description || '')
        setJdError('')
      } else {
        setJdError(data.error || '抓取失败，请手动输入')
      }
    } catch (error) {
      setJdError('抓取失败，请检查链接或手动输入')
    } finally {
      setFetchingJd(false)
    }
  }

  // 生成岗位相关问题
  const handleGenerate = async () => {
    if (!jobTitle.trim()) return

    setLoading(true)
    try {
      const response = await fetch('/api/v1/candidate-support/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          job_title: jobTitle,
          company: company || undefined,
          job_description: jobDescription || undefined,
          resume_id: selectedResumeId || undefined,
          question_types: selectedTypes,
          difficulty,
          count: questionCount
        })
      })

      if (response.ok) {
        const data = await response.json()
        setQuestions(data.questions)
        setResumeUsed(data.resume_used || false)
        setUserAnswers({})
        setFeedback({})
        setExpandedQuestions(new Set([data.questions[0]?.id]))
      }
    } catch (error) {
      console.error('生成岗位问题失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 评估答案
  const handleEvaluate = async (questionId: number, question: string) => {
    const answer = userAnswers[questionId]
    if (!answer?.trim()) return

    setEvaluating(questionId)
    try {
      const response = await fetch('/api/v1/candidate-support/evaluate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          question_id: questionId,
          question,
          user_answer: answer
        })
      })

      if (response.ok) {
        const data = await response.json()
        setFeedback(prev => ({ ...prev, [questionId]: data }))
      }
    } catch (error) {
      console.error('评估答案失败:', error)
    } finally {
      setEvaluating(null)
    }
  }

  // 切换问题展开状态
  const toggleQuestion = (id: number) => {
    setExpandedQuestions(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  // 类型标签颜色
  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'technical': return 'bg-blue-100 text-blue-700'
      case 'behavioral': return 'bg-green-100 text-green-700'
      case 'situational': return 'bg-purple-100 text-purple-700'
      case 'resume_based': return 'bg-orange-100 text-orange-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const getCategoryName = (category: string) => {
    switch (category) {
      case 'technical': return '技术题'
      case 'behavioral': return '行为题'
      case 'situational': return '情景题'
      case 'resume_based': return '简历相关'
      default: return category
    }
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-sky-900">候选人支持</h1>
            <p className="text-sm text-sky-600">AI 生成岗位相关问题与回答建议，辅助候选人准备申请材料</p>
          </div>
        </div>
      </div>

      {questions.length === 0 ? (
        /* 输入表单 */
        <div className="glass-card p-6">
          <h2 className="text-lg font-bold text-sky-900 mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-sky-600" />
            生成岗位问题
          </h2>

          {/* JD 链接抓取 */}
          <div className="mb-6 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border border-indigo-100">
            <label className="block text-sm font-semibold text-indigo-800 mb-2 flex items-center gap-2">
              <Link className="w-4 h-4" />
              职位链接（自动抓取 JD）
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                value={jdUrl}
                onChange={(e) => setJdUrl(e.target.value)}
                placeholder="粘贴 Indeed/LinkedIn/JobsDB 职位链接..."
                className="flex-1 glass-input"
              />
              <button
                onClick={handleFetchJd}
                disabled={fetchingJd || !jdUrl.trim()}
                className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-300 text-white rounded-xl font-medium transition-colors flex items-center gap-2"
              >
                {fetchingJd ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    抓取中
                  </>
                ) : (
                  <>
                    <Link className="w-4 h-4" />
                    抓取
                  </>
                )}
              </button>
            </div>
            {jdError && (
              <div className="mt-2 text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="w-4 h-4" />
                {jdError}
              </div>
            )}
            <p className="text-xs text-indigo-500 mt-2">
              支持 Indeed、LinkedIn、JobsDB 链接，自动提取职位信息
            </p>
          </div>

          {/* 简历选择 */}
          <div className="mb-6 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-100">
            <label className="block text-sm font-semibold text-emerald-800 mb-2 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              选择简历（生成针对性岗位问题）
            </label>
            {loadingResumes ? (
              <div className="flex items-center gap-2 text-emerald-600">
                <Loader2 className="w-4 h-4 animate-spin" />
                加载中...
              </div>
            ) : resumes.length === 0 ? (
              <div className="text-sm text-emerald-600">
                还没有上传简历，
                <a href="/resumes" className="underline hover:text-emerald-800">去上传</a>
              </div>
            ) : (
              <select
                value={selectedResumeId}
                onChange={(e) => setSelectedResumeId(e.target.value)}
                className="glass-input"
              >
                <option value="">不使用简历（通用岗位问题）</option>
                {resumes.map(resume => (
                  <option key={resume.id} value={resume.id}>
                    {resume.filename}
                    {resume.label && ` (${resume.label})`}
                    {resume.is_default && ' ⭐ 默认'}
                  </option>
                ))}
              </select>
            )}
            <p className="text-xs text-emerald-500 mt-2">
              选择简历后，AI 会根据你的经历生成更贴近岗位要求的问题
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 职位名称 */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                目标职位 *
              </label>
              <input
                type="text"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="如：前端开发工程师"
                className="glass-input"
              />
            </div>

            {/* 公司名称 */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                目标公司（可选）
              </label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="如：腾讯、阿里巴巴"
                className="glass-input"
              />
            </div>

            {/* 职位描述 */}
            <div className="md:col-span-2">
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                职位描述（可选，生成更精准的问题）
              </label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="粘贴职位描述，AI 会根据具体要求生成更有针对性的问题..."
                className="glass-input min-h-[100px] resize-none"
              />
            </div>

            {/* 题目类型 */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                题目类型
              </label>
              <div className="flex flex-wrap gap-2">
                {[
                  { id: 'technical', name: '技术题' },
                  { id: 'behavioral', name: '行为题' },
                  { id: 'situational', name: '情景题' }
                ].map(type => (
                  <button
                    key={type.id}
                    onClick={() => {
                      setSelectedTypes(prev =>
                        prev.includes(type.id)
                          ? prev.filter(t => t !== type.id)
                          : [...prev, type.id]
                      )
                    }}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                      selectedTypes.includes(type.id)
                        ? 'bg-sky-500 text-white'
                        : 'bg-sky-100 text-sky-700 hover:bg-sky-200'
                    }`}
                  >
                    {type.name}
                  </button>
                ))}
              </div>
            </div>

            {/* 难度和数量 */}
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="block text-sm font-semibold text-sky-800 mb-2">
                  难度
                </label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="glass-input"
                >
                  <option value="easy">初级</option>
                  <option value="medium">中级</option>
                  <option value="hard">高级</option>
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-sm font-semibold text-sky-800 mb-2">
                  题目数量
                </label>
                <select
                  value={questionCount}
                  onChange={(e) => setQuestionCount(parseInt(e.target.value))}
                  className="glass-input"
                >
                  <option value={5}>5 道</option>
                  <option value={10}>10 道</option>
                  <option value={15}>15 道</option>
                  <option value={20}>20 道</option>
                </select>
              </div>
            </div>
          </div>

          {/* 生成按钮 */}
          <button
            onClick={handleGenerate}
            disabled={loading || !jobTitle.trim() || selectedTypes.length === 0}
            className="w-full mt-6 glass-button flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Brain className="w-5 h-5" />
                生成岗位问题
              </>
            )}
          </button>
        </div>
      ) : (
        /* 岗位问题列表 */
        <>
          {/* 统计信息 */}
          <div className="glass-card p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-sky-700">
                  <strong>{jobTitle}</strong> {company && `@ ${company}`}
                </span>
                <span className="text-sm text-sky-500">
                  共 {questions.length} 道题
                </span>
                {resumeUsed && (
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded-full flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    已结合简历
                  </span>
                )}
              </div>
              <button
                onClick={() => {
                  setQuestions([])
                  setUserAnswers({})
                  setFeedback({})
                }}
                className="text-sm text-sky-600 hover:text-sky-800 underline"
              >
                重新生成
              </button>
            </div>
          </div>

          {/* 题目列表 */}
          <div className="space-y-4">
            {questions.map((q, index) => (
              <div key={q.id} className="glass-card overflow-hidden">
                {/* 题目标题 */}
                <button
                  onClick={() => toggleQuestion(q.id)}
                  className="w-full p-4 flex items-center justify-between hover:bg-sky-50/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 bg-sky-100 rounded-lg flex items-center justify-center text-sm font-bold text-sky-700">
                      {index + 1}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getCategoryColor(q.category)}`}>
                      {getCategoryName(q.category)}
                    </span>
                    <span className="text-sky-900 font-medium text-left">
                      {q.question.length > 50 ? q.question.slice(0, 50) + '...' : q.question}
                    </span>
                  </div>
                  {expandedQuestions.has(q.id) ? (
                    <ChevronUp className="w-5 h-5 text-sky-500" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-sky-500" />
                  )}
                </button>

                {/* 展开内容 */}
                {expandedQuestions.has(q.id) && (
                  <div className="px-4 pb-4 border-t border-sky-100">
                    {/* 完整题目 */}
                    <div className="mt-4 p-4 bg-sky-50 rounded-lg">
                      <p className="text-sky-900 font-medium">{q.question}</p>
                    </div>

                    {/* 回答技巧 */}
                    <div className="mt-4">
                      <h4 className="text-sm font-semibold text-sky-800 flex items-center gap-1 mb-2">
                        <Lightbulb className="w-4 h-4 text-yellow-500" />
                        回答技巧
                      </h4>
                      <ul className="space-y-1">
                        {q.tips.map((tip, i) => (
                          <li key={i} className="text-sm text-sky-600 flex items-start gap-2">
                            <span className="text-sky-400">•</span>
                            {tip}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* 用户答案输入 */}
                    <div className="mt-4">
                      <h4 className="text-sm font-semibold text-sky-800 flex items-center gap-1 mb-2">
                        <MessageSquare className="w-4 h-4 text-sky-500" />
                        你的回答
                      </h4>
                      <textarea
                        value={userAnswers[q.id] || ''}
                        onChange={(e) => setUserAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                        placeholder="尝试回答这个问题，AI 会给你反馈..."
                        className="glass-input min-h-[120px] resize-none"
                      />
                      <button
                        onClick={() => handleEvaluate(q.id, q.question)}
                        disabled={evaluating === q.id || !userAnswers[q.id]?.trim()}
                        className="mt-2 glass-button text-sm flex items-center gap-2"
                      >
                        {evaluating === q.id ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            评估中...
                          </>
                        ) : (
                          <>
                            <Send className="w-4 h-4" />
                            获取 AI 反馈
                          </>
                        )}
                      </button>
                    </div>

                    {/* AI 反馈 */}
                    {feedback[q.id] && (
                      <div className="mt-4 p-4 bg-gradient-to-br from-green-50 to-blue-50 rounded-lg border border-green-100">
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-semibold text-sky-900">AI 评估结果</h4>
                          <div className="flex items-center gap-2">
                            <Target className="w-4 h-4 text-green-600" />
                            <span className="text-lg font-bold text-green-600">
                              {feedback[q.id].score}分
                            </span>
                          </div>
                        </div>

                        {/* 优点 */}
                        <div className="mb-3">
                          <h5 className="text-sm font-medium text-green-700 flex items-center gap-1 mb-1">
                            <CheckCircle className="w-4 h-4" />
                            优点
                          </h5>
                          <ul className="text-sm text-green-600 space-y-1">
                            {feedback[q.id].strengths.map((s, i) => (
                              <li key={i}>• {s}</li>
                            ))}
                          </ul>
                        </div>

                        {/* 改进建议 */}
                        <div className="mb-3">
                          <h5 className="text-sm font-medium text-amber-700 flex items-center gap-1 mb-1">
                            <TrendingUp className="w-4 h-4" />
                            改进建议
                          </h5>
                          <ul className="text-sm text-amber-600 space-y-1">
                            {feedback[q.id].improvements.map((s, i) => (
                              <li key={i}>• {s}</li>
                            ))}
                          </ul>
                        </div>

                        {/* 更好的答案 */}
                        <div>
                          <h5 className="text-sm font-medium text-blue-700 flex items-center gap-1 mb-1">
                            <BookOpen className="w-4 h-4" />
                            优化建议
                          </h5>
                          <p className="text-sm text-blue-600">{feedback[q.id].better_answer}</p>
                        </div>
                      </div>
                    )}

                    {/* 参考答案 */}
                    <details className="mt-4">
                      <summary className="cursor-pointer text-sm font-medium text-sky-700 hover:text-sky-900">
                        查看参考答案
                      </summary>
                      <div className="mt-2 p-3 bg-gray-50 rounded-lg text-sm text-gray-700">
                        {q.suggested_answer}
                      </div>
                    </details>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
