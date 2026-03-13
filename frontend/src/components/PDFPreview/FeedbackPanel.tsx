/**
 * 反馈面板组件 - 快捷标签 + 自定义输入
 */
import { useState } from 'react'

interface FeedbackPanelProps {
  selectedText?: string
  onSubmit: (feedback: string) => Promise<void>
  onClose: () => void
  isLoading?: boolean
}

// 快捷反馈选项
const QUICK_FEEDBACKS = [
  { id: 'concise', label: '📝 更简洁', value: '请让内容更加简洁精炼' },
  { id: 'detailed', label: '📖 更详细', value: '请添加更多细节和具体数据' },
  { id: 'professional', label: '💼 更专业', value: '请使用更专业的措辞和行业术语' },
  { id: 'impactful', label: '🚀 突出成果', value: '请强调成果和影响力，使用量化数据' },
  { id: 'keywords', label: '🔑 加关键词', value: '请添加更多技术关键词' },
  { id: 'format', label: '📋 优化格式', value: '请优化排版格式，使其更易读' },
]

export default function FeedbackPanel({
  selectedText,
  onSubmit,
  onClose,
  isLoading = false
}: FeedbackPanelProps) {
  const [feedback, setFeedback] = useState('')
  const [selectedQuick, setSelectedQuick] = useState<string[]>([])

  // 切换快捷选项
  const toggleQuickOption = (id: string) => {
    setSelectedQuick(prev => 
      prev.includes(id) 
        ? prev.filter(x => x !== id) 
        : [...prev, id]
    )
  }

  // 提交反馈
  const handleSubmit = async () => {
    // 组合快捷反馈和自定义反馈
    const quickFeedbackTexts = selectedQuick
      .map(id => QUICK_FEEDBACKS.find(q => q.id === id)?.value)
      .filter(Boolean)
    
    const fullFeedback = [
      ...quickFeedbackTexts,
      feedback.trim()
    ].filter(Boolean).join('\n')

    if (!fullFeedback) return

    // 如果有选中文本，添加上下文
    const contextFeedback = selectedText 
      ? `针对以下内容：\n"${selectedText}"\n\n修改建议：\n${fullFeedback}`
      : fullFeedback

    await onSubmit(contextFeedback)
  }

  return (
    <div className="w-1/3 min-w-[300px] bg-white border-l border-sky-100 flex flex-col">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 bg-sky-50 border-b border-sky-100">
        <h3 className="font-semibold text-sky-900">反馈优化</h3>
        <button 
          onClick={onClose}
          className="p-1 text-sky-600 hover:bg-sky-100 rounded"
        >
          ✕
        </button>
      </div>

      {/* 内容 */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* 选中文本 */}
        {selectedText && (
          <div className="bg-sky-50 rounded-lg p-3">
            <p className="text-xs text-sky-600 mb-1">选中的内容：</p>
            <p className="text-sm text-sky-900 italic">
              "{selectedText.substring(0, 100)}{selectedText.length > 100 ? '...' : ''}"
            </p>
          </div>
        )}

        {/* 快捷反馈 */}
        <div>
          <p className="text-sm font-medium text-sky-800 mb-2">快捷反馈：</p>
          <div className="flex flex-wrap gap-2">
            {QUICK_FEEDBACKS.map(option => (
              <button
                key={option.id}
                onClick={() => toggleQuickOption(option.id)}
                className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                  selectedQuick.includes(option.id)
                    ? 'bg-sky-500 text-white'
                    : 'bg-sky-100 text-sky-700 hover:bg-sky-200'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* 自定义反馈 */}
        <div>
          <p className="text-sm font-medium text-sky-800 mb-2">自定义反馈：</p>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="请描述你想要的修改，例如：&#10;- 第一段太长，请精简&#10;- 加上 3 年 Python 经验&#10;- 突出项目管理能力"
            className="w-full h-32 p-3 border border-sky-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-sky-500 text-sm"
          />
        </div>

        {/* 提示 */}
        <div className="bg-amber-50 rounded-lg p-3 text-sm text-amber-700">
          💡 提示：可以在 PDF 上选中文本，然后针对该部分给出具体反馈
        </div>
      </div>

      {/* 底部按钮 */}
      <div className="p-4 border-t border-sky-100">
        <button
          onClick={handleSubmit}
          disabled={isLoading || (!feedback.trim() && selectedQuick.length === 0)}
          className="w-full py-3 bg-gradient-to-r from-sky-500 to-blue-500 text-white rounded-lg font-medium hover:from-sky-600 hover:to-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin">⏳</span>
              重新生成中...
            </span>
          ) : (
            '🚀 提交反馈并重新生成'
          )}
        </button>
      </div>
    </div>
  )
}
