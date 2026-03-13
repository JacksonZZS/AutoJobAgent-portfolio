/**
 * 文件上传 API
 */

import apiClient from './client'

export interface LastUploadInfo {
  has_resume: boolean
  resume_path: string | null
  resume_filename: string | null
  has_transcript: boolean
  transcript_path: string | null
  transcript_filename: string | null
  last_platform: 'jobsdb' | 'indeed' | 'linkedin' | null  // 🔴 上次使用的平台
  cached_analysis: {
    keywords: string
    blocked_companies: string
    title_exclusions: string
    last_platform?: string
  } | null
}

// 🔴 多简历管理
export interface ResumeInfo {
  resume_id: string  // 🔴 修复: 与后端一致
  filename: string
  label: string
  file_path: string
  file_hash: string  // 🔴 修复: 添加后端返回的字段
  is_default: boolean
  uploaded_at: string
}

export interface ResumeListResponse {
  resumes: ResumeInfo[]
  default_resume_id: string | null  // 🔴 修复: 与后端一致
}

export const uploadAPI = {
  // 获取上次上传的文档
  getLastUpload: async (): Promise<LastUploadInfo> => {
    const response = await apiClient.get('/api/v1/upload/last-upload')
    return response.data
  },

  // 上传简历
  uploadResume: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiClient.post('/api/v1/upload/resume', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // 上传成绩单
  uploadTranscript: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiClient.post('/api/v1/upload/transcript', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // 🔴 多简历管理 API
  // 获取所有简历列表
  getResumes: async (): Promise<ResumeListResponse> => {
    const response = await apiClient.get('/api/v1/upload/resumes')
    return response.data
  },

  // 上传简历（带标签）
  uploadResumeWithLabel: async (file: File, label: string): Promise<ResumeInfo> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('label', label)

    const response = await apiClient.post('/api/v1/upload/resume-with-label', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // 设为默认简历
  setDefaultResume: async (resumeId: string): Promise<void> => {
    await apiClient.put(`/api/v1/upload/resume/${resumeId}/default`)
  },

  // 删除简历
  deleteResume: async (resumeId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/upload/resume/${resumeId}`)
  },
}
