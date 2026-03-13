/**
 * PDF 预览组件 - 支持翻页、缩放、文本选择、反馈
 */
import { useState, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import FeedbackPanel from './FeedbackPanel'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

// 🔴 修复：使用本地 worker 文件，避免 CORS 问题
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc

interface PDFPreviewProps {
  pdfUrl: string
  resumeId: string
  version?: number
  versions?: number[]
  onRegenerate?: (feedback: string) => Promise<void>
  onVersionChange?: (version: number) => void
  onClose?: () => void
}

export default function PDFPreview({
  pdfUrl,
  resumeId: _resumeId,
  version = 1,
  versions = [1],
  onRegenerate,
  onVersionChange,
  onClose
}: PDFPreviewProps) {
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [selectedText, setSelectedText] = useState('')
  const [showFeedback, setShowFeedback] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)

  // PDF 加载成功
  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages)
    setCurrentPage(1)
  }, [])

  // 翻页
  const goToPrevPage = () => setCurrentPage(prev => Math.max(prev - 1, 1))
  const goToNextPage = () => setCurrentPage(prev => Math.min(prev + 1, numPages))

  // 缩放
  const zoomIn = () => setScale(prev => Math.min(prev + 0.2, 2.5))
  const zoomOut = () => setScale(prev => Math.max(prev - 0.2, 0.5))

  // 文本选择
  const handleTextSelection = useCallback(() => {
    const selection = window.getSelection()
    if (selection && selection.toString().trim()) {
      setSelectedText(selection.toString().trim())
    }
  }, [])

  // 提交反馈
  const handleFeedbackSubmit = async (feedback: string) => {
    if (!onRegenerate) return
    
    setIsRegenerating(true)
    try {
      await onRegenerate(feedback)
      setShowFeedback(false)
      setSelectedText('')
    } catch (error) {
      console.error('重新生成失败:', error)
    } finally {
      setIsRegenerating(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-lg overflow-hidden">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-4 py-3 bg-sky-50 border-b border-sky-100">
        {/* 左侧：关闭 + 版本 */}
        <div className="flex items-center gap-3">
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 text-sky-600 hover:bg-sky-100 rounded-lg transition-colors"
            >
              ✕
            </button>
          )}
          <span className="text-sm text-sky-600">版本:</span>
          <select
            value={version}
            onChange={e => onVersionChange?.(Number(e.target.value))}
            className="text-sm border border-sky-200 rounded-lg px-2 py-1 bg-white"
          >
            {versions.map(v => (
              <option key={v} value={v}>v{v}</option>
            ))}
          </select>
        </div>

        {/* 中间：翻页 */}
        <div className="flex items-center gap-2">
          <button
            onClick={goToPrevPage}
            disabled={currentPage <= 1}
            className="p-2 hover:bg-sky-100 rounded-lg disabled:opacity-50 transition-colors"
          >
            ◀
          </button>
          <span className="text-sm text-sky-700 min-w-[60px] text-center">
            {currentPage} / {numPages}
          </span>
          <button
            onClick={goToNextPage}
            disabled={currentPage >= numPages}
            className="p-2 hover:bg-sky-100 rounded-lg disabled:opacity-50 transition-colors"
          >
            ▶
          </button>
        </div>

        {/* 右侧：缩放 + 反馈 */}
        <div className="flex items-center gap-2">
          <button onClick={zoomOut} className="p-2 hover:bg-sky-100 rounded-lg">−</button>
          <span className="text-sm text-sky-700 min-w-[50px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button onClick={zoomIn} className="p-2 hover:bg-sky-100 rounded-lg">+</button>
          
          <div className="w-px h-6 bg-sky-200 mx-2" />
          
          <button
            onClick={() => setShowFeedback(true)}
            className="flex items-center gap-1 px-3 py-1.5 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors text-sm"
          >
            💬 反馈优化
          </button>
        </div>
      </div>

      {/* 主内容 */}
      <div className="flex flex-1 overflow-hidden">
        {/* PDF 区域 */}
        <div 
          className={`flex-1 overflow-auto bg-gray-100 p-4 flex justify-center ${showFeedback ? 'w-2/3' : 'w-full'}`}
          onMouseUp={handleTextSelection}
        >
          {isRegenerating ? (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-500" />
              <p className="mt-4 text-sky-600">正在重新生成...</p>
            </div>
          ) : (
            <Document
              file={pdfUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              loading={
                <div className="flex items-center justify-center h-96">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500" />
                </div>
              }
              error={
                <div className="flex items-center justify-center h-96 text-red-500">
                  PDF 加载失败
                </div>
              }
            >
              <Page
                pageNumber={currentPage}
                scale={scale}
                className="shadow-lg"
                renderTextLayer={true}
                renderAnnotationLayer={true}
              />
            </Document>
          )}
        </div>

        {/* 反馈面板 */}
        {showFeedback && (
          <FeedbackPanel
            selectedText={selectedText}
            onSubmit={handleFeedbackSubmit}
            onClose={() => {
              setShowFeedback(false)
              setSelectedText('')
            }}
            isLoading={isRegenerating}
          />
        )}
      </div>

      {/* 选中提示 */}
      {selectedText && !showFeedback && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-black/75 text-white px-4 py-2 rounded-lg text-sm">
          已选中: "{selectedText.substring(0, 50)}{selectedText.length > 50 ? '...' : ''}"
        </div>
      )}
    </div>
  )
}
