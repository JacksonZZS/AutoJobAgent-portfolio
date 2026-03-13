/**
 * Hook for managing PDF preview state (blob URLs, open/close, regenerate).
 */
import { useState, useCallback } from 'react'
import { useAuthStore } from '@/store/authStore'

export function usePdfPreview() {
  const { token } = useAuthStore()

  const [showResumePreview, setShowResumePreview] = useState(false)
  const [showCLPreview, setShowCLPreview] = useState(false)
  const [resumeBlobUrl, setResumeBlobUrl] = useState<string | null>(null)
  const [clBlobUrl, setClBlobUrl] = useState<string | null>(null)
  const [loadingPdf, setLoadingPdf] = useState(false)
  const [pdfError, setPdfError] = useState('')

  const fetchPdfAsBlob = useCallback(async (
    fileType: 'resume' | 'cover_letter',
    filePath: string
  ): Promise<string | null> => {
    try {
      const filename = filePath.split('/').pop() || ''
      if (!token) {
        setPdfError('未登录，请先登录')
        return null
      }
      const response = await fetch(
        `/api/v1/materials/preview/${fileType}/${encodeURIComponent(filename)}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      )
      if (!response.ok) throw new Error('获取 PDF 失败')
      const blob = await response.blob()
      return URL.createObjectURL(blob)
    } catch (err) {
      console.error('获取 PDF 失败:', err)
      setPdfError('获取 PDF 失败，请重试')
      return null
    }
  }, [token])

  const openResumePreview = useCallback(async (resumePath: string) => {
    if (!resumePath) return
    setLoadingPdf(true)
    const blobUrl = await fetchPdfAsBlob('resume', resumePath)
    if (blobUrl) {
      setResumeBlobUrl(blobUrl)
      setShowResumePreview(true)
    }
    setLoadingPdf(false)
  }, [fetchPdfAsBlob])

  const openCLPreview = useCallback(async (clPath: string) => {
    if (!clPath) return
    setLoadingPdf(true)
    const blobUrl = await fetchPdfAsBlob('cover_letter', clPath)
    if (blobUrl) {
      setClBlobUrl(blobUrl)
      setShowCLPreview(true)
    }
    setLoadingPdf(false)
  }, [fetchPdfAsBlob])

  const closeResumePreview = useCallback(() => {
    setShowResumePreview(false)
    if (resumeBlobUrl) {
      URL.revokeObjectURL(resumeBlobUrl)
      setResumeBlobUrl(null)
    }
  }, [resumeBlobUrl])

  const closeCLPreview = useCallback(() => {
    setShowCLPreview(false)
    if (clBlobUrl) {
      URL.revokeObjectURL(clBlobUrl)
      setClBlobUrl(null)
    }
  }, [clBlobUrl])

  const regenerateResume = useCallback(async (feedback: string) => {
    if (!token) {
      setPdfError('未登录，请先登录')
      return
    }
    const response = await fetch('/api/v1/materials/regenerate-resume', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ feedback })
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || '重新生成失败')
    }
    // Close and reopen after a short delay
    closeResumePreview()
  }, [token, closeResumePreview])

  return {
    showResumePreview,
    showCLPreview,
    resumeBlobUrl,
    clBlobUrl,
    loadingPdf,
    pdfError,
    setPdfError,
    openResumePreview,
    openCLPreview,
    closeResumePreview,
    closeCLPreview,
    regenerateResume,
  }
}
