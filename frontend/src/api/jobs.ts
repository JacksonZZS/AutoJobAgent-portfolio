/**
 * 任务管理 API
 */

import apiClient from './client'
import type { TaskStatusResponse } from '@/types/api'

export interface BatchSkipResponse {
  skipped_count: number
  message: string
  skipped_jobs: Array<{
    job_id: string
    title: string
    company: string
    score: number
  }>
}

export const jobsAPI = {
  // 启动任务
  startTask: async (data: {
    keywords: string
    target_count?: number
    company_blacklist?: string[]
    title_exclusions?: string[]
  }) => {
    const response = await apiClient.post('/api/v1/jobs/start-task', data)
    return response.data
  },

  // 获取任务状态
  getTaskStatus: async (): Promise<TaskStatusResponse> => {
    const response = await apiClient.get('/api/v1/jobs/task-status')
    return response.data
  },

  // 提交人工决策
  submitManualDecision: async (decision: string) => {
    const response = await apiClient.post('/api/v1/jobs/manual-decision', { decision })
    return response.data
  },

  // 停止任务
  stopTask: async () => {
    const response = await apiClient.post('/api/v1/jobs/stop-task')
    return response.data
  },

  // 批量跳过低分职位
  batchSkipLowScore: async (threshold: number = 60, skipType: string = 'SKIP_PERMANENT'): Promise<BatchSkipResponse> => {
    const response = await apiClient.post('/api/v1/jobs/batch-skip-low-score', {
      threshold,
      skip_type: skipType
    })
    return response.data
  },
}
