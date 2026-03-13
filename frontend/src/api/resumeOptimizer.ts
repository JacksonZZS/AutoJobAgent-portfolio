/**
 * 简历优化 API
 */

export interface OptimizeResumeRequest {
  resume_file: File
  permanent_resident?: boolean
  available_immediately?: boolean
  linkedin_url?: string
  github_url?: string
  portfolio_url?: string
  target_profile?: 'general' | 'qa' | 'fintech' | 'da'
  edit_instructions?: ResumeEditInstruction[]
  additional_notes?: string
}

export interface ResumeEditInstruction {
  action: 'delete' | 'add' | 'modify'
  target: string
  content?: string
}

export interface OptimizedResumeData {
  name: string
  email: string
  phone: string
  linkedin?: string
  github?: string
  portfolio?: string
  work_eligibility: string
  availability: string
  summary: string
  experience: Array<{
    title: string
    company: string
    location: string
    date: string
    bullets: string[]
  }>
  skills: Array<{
    name: string
    keywords: string[]
  }>
  education: {
    university: string
    degree: string
    date: string
    honors?: string
  }
  projects?: Array<{
    name: string
    date: string
    bullets: string[]
  }>
  certifications?: string[]
  additional_info?: string
}

export interface OptimizeResumeResponse {
  success: boolean
  message: string
  pdf_path: string
  optimized_data: OptimizedResumeData
}

export interface OptimizerHistoryRecord {
  id: number
  original_filename: string
  optimized_pdf_path: string
  optimized_pdf_filename: string
  permanent_resident: boolean
  available_immediately: boolean
  linkedin_url: string
  github_url: string
  portfolio_url: string
  target_profile?: string
  edit_instructions?: ResumeEditInstruction[]
  additional_notes: string
  created_at: string
}

export const resumeOptimizerAPI = {
  /**
   * 优化简历（使用原生 fetch + 手动传递 token）
   */
  async optimizeResume(
    request: OptimizeResumeRequest,
    token: string
  ): Promise<OptimizeResumeResponse> {
    const formData = new FormData()
    formData.append('resume_file', request.resume_file)
    formData.append('permanent_resident', String(request.permanent_resident || false))
    formData.append('available_immediately', String(request.available_immediately || false))
    formData.append('linkedin_url', request.linkedin_url || '')
    formData.append('github_url', request.github_url || '')
    formData.append('portfolio_url', request.portfolio_url || '')
    formData.append('target_profile', request.target_profile || 'general')
    formData.append('edit_instructions', JSON.stringify(request.edit_instructions || []))
    formData.append('additional_notes', request.additional_notes || '')

    const response = await fetch('/api/v1/resume/optimize', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        // 🔴 不要手动设置 Content-Type，让浏览器自动设置（包含 boundary）
      },
      body: formData,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '未知错误' }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    return response.json()
  },

  /**
   * 下载优化后的简历PDF（使用原生 fetch + 手动传递 token）
   */
  async downloadResume(filename: string, token: string): Promise<Blob> {
    const response = await fetch(`/api/v1/resume/download/${filename}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })

    if (!response.ok) {
      throw new Error('下载失败')
    }

    return response.blob()
  },
}
