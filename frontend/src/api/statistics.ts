/**
 * 统计 API
 */

import apiClient from './client'

export interface PlatformStats {
  total: number
  success: number
  avg_score: number
}

export interface DashboardStatistics {
  total_applications: number
  success_count: number
  skip_count: number
  failed_count: number
  today_count: number
  week_count: number
  month_count: number
  success_rate: number
  avg_score: number
  platform_stats: Record<string, PlatformStats>
}

export interface TrendDataPoint {
  date: string
  applications: number
  success: number
}

export interface TrendsResponse {
  data: TrendDataPoint[]
}

export interface PlatformBreakdownItem {
  platform: string
  count: number
  percentage: number
}

export interface PlatformBreakdownResponse {
  platforms: PlatformBreakdownItem[]
}

export const statisticsAPI = {
  // 获取仪表盘统计
  getDashboardStats: async (period: string = 'all'): Promise<DashboardStatistics> => {
    const response = await apiClient.get(`/api/v1/statistics/dashboard?period=${period}`)
    return response.data
  },

  // 获取趋势数据
  getTrends: async (days: number = 30): Promise<TrendsResponse> => {
    const response = await apiClient.get(`/api/v1/statistics/trends?days=${days}`)
    return response.data
  },

  // 获取平台分布
  getPlatformBreakdown: async (): Promise<PlatformBreakdownResponse> => {
    const response = await apiClient.get('/api/v1/statistics/platform-breakdown')
    return response.data
  },
}
