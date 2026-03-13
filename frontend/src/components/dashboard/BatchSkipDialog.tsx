/**
 * Batch skip dialog for skipping low-score jobs in bulk.
 */
import { useState } from 'react'
import { Trash2, X, Loader2, CheckCircle } from 'lucide-react'
import { jobsAPI } from '@/api/jobs'

interface BatchSkipDialogProps {
  onClose: () => void
}

export default function BatchSkipDialog({ onClose }: BatchSkipDialogProps) {
  const [threshold, setThreshold] = useState(50)
  const [isSkipping, setIsSkipping] = useState(false)
  const [result, setResult] = useState<{ count: number; message: string } | null>(null)

  const handleBatchSkip = async () => {
    setIsSkipping(true)
    setResult(null)
    try {
      const res = await jobsAPI.batchSkipLowScore(threshold, 'SKIP_PERMANENT')
      setResult({ count: res.skipped_count, message: res.message })
      setTimeout(() => {
        onClose()
      }, 3000)
    } catch (err: any) {
      console.error('批量跳过失败:', err)
    } finally {
      setIsSkipping(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="glass-card w-full max-w-md animate-scale-in">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-sky-900 flex items-center gap-2">
              <Trash2 className="w-5 h-5 text-orange-600" />
              批量跳过低分职位
            </h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-sky-100 rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-5 h-5 text-sky-600" />
            </button>
          </div>

          {result ? (
            <div className="text-center py-8">
              <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <p className="text-lg font-semibold text-green-700">{result.message}</p>
              <p className="text-sm text-green-600 mt-2">
                已跳过 {result.count} 个职位
              </p>
            </div>
          ) : (
            <>
              <p className="text-sky-700 mb-6">
                将从历史记录中找出所有评分低于指定阈值的职位，并将它们标记为永久跳过。
              </p>

              <div className="mb-6">
                <label className="block text-sm font-semibold text-sky-800 mb-2">
                  分数阈值
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    className="flex-1 accent-orange-600"
                    value={threshold}
                    onChange={(e) => setThreshold(parseInt(e.target.value))}
                  />
                  <input
                    type="number"
                    min="0"
                    max="100"
                    className="w-20 px-3 py-2 glass-input text-center font-bold"
                    value={threshold}
                    onChange={(e) => setThreshold(parseInt(e.target.value) || 0)}
                  />
                  <span className="text-sm text-sky-700 font-semibold">分</span>
                </div>
                <p className="text-xs text-sky-600 mt-2">
                  所有评分 &lt; {threshold} 分的职位将被永久跳过
                </p>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  className="glass-button-secondary"
                  onClick={onClose}
                  disabled={isSkipping}
                >
                  取消
                </button>
                <button
                  className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                  onClick={handleBatchSkip}
                  disabled={isSkipping}
                >
                  {isSkipping ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> 处理中...</>
                  ) : (
                    <><Trash2 className="w-4 h-4" /> 确认跳过</>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
