/**
 * 历史记录 API
 */

import apiClient from './client'

export interface HistoryItem {
  job_id: string
  title: string
  company: string
  link: string
  status: string
  score: number | null
  reason: string | null
  resume_path: string | null
  cl_path: string | null
  platform: string | null
  processed_at: string
}

export interface HistoryListResponse {
  total: number
  items: HistoryItem[]
  page: number
  page_size: number
}

export interface HistoryStatistics {
  total: number
  success: number
  skipped: number
  failed: number
}

export interface HistorySearchFilters {
  search?: string
  company?: string
  score_min?: number
  score_max?: number
  date_from?: string
  date_to?: string
  platform?: string
}

export const historyAPI = {
  /**
   * 获取投递历史列表（支持搜索过滤）
   */
  getHistory: async (
    page: number = 1,
    pageSize: number = 50,
    statusFilter?: string,
    sortBy: string = 'time',
    filters?: HistorySearchFilters
  ): Promise<HistoryListResponse> => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      sort_by: sortBy,
    })
    if (statusFilter) {
      params.append('status_filter', statusFilter)
    }
    // 🔴 新增搜索过滤参数
    if (filters?.search) {
      params.append('search', filters.search)
    }
    if (filters?.company) {
      params.append('company', filters.company)
    }
    if (filters?.score_min !== undefined) {
      params.append('score_min', filters.score_min.toString())
    }
    if (filters?.score_max !== undefined) {
      params.append('score_max', filters.score_max.toString())
    }
    if (filters?.date_from) {
      params.append('date_from', filters.date_from)
    }
    if (filters?.date_to) {
      params.append('date_to', filters.date_to)
    }
    if (filters?.platform) {
      params.append('platform', filters.platform)
    }
    const response = await apiClient.get(`/api/v1/history/?${params}`)
    return response.data
  },

  /**
   * 获取统计数据
   */
  getStatistics: async (): Promise<HistoryStatistics> => {
    const response = await apiClient.get('/api/v1/history/statistics')
    return response.data
  },

  /**
   * 清空历史记录
   * @param statusFilter 按状态清除：low_score/success/skip/fail，不传则清除全部
   */
  clearHistory: async (statusFilter?: string): Promise<{ message: string; deleted_count: number }> => {
    const params = statusFilter ? `?status_filter=${statusFilter}` : ''
    const response = await apiClient.delete(`/api/v1/history/clear${params}`)
    return response.data
  },

  /**
   * 导出 CSV
   */
  exportCSV: async (): Promise<Blob> => {
    const response = await apiClient.get('/api/v1/history/export', {
      responseType: 'blob',
    })
    return response.data
  },
}
