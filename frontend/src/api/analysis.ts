/**
 * 简历分析 API
 */

import apiClient from './client'

export const analysisAPI = {
  // 分析简历
  analyzeResume: async (data: {
    resume_path: string
    transcript_path?: string
  }) => {
    const response = await apiClient.post('/api/v1/analysis/analyze-resume', data)
    return response.data
  },
}
