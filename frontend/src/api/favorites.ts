/**
 * 收藏 API
 */

import apiClient from './client'

export interface FavoriteJob {
  job_id: string
  title: string
  company: string
  link: string
  score: number | null
  platform: string | null
  notes: string | null
  favorited_at: string
}

export interface FavoritesListResponse {
  total: number
  items: FavoriteJob[]
}

export interface AddFavoriteRequest {
  title: string
  company: string
  link: string
  score?: number
  platform?: string
  notes?: string
}

export const favoritesAPI = {
  // 获取收藏列表
  getFavorites: async (page: number = 1, pageSize: number = 20): Promise<FavoritesListResponse> => {
    const response = await apiClient.get(`/api/v1/favorites/?page=${page}&page_size=${pageSize}`)
    return response.data
  },

  // 添加收藏
  addFavorite: async (jobId: string, data: AddFavoriteRequest): Promise<void> => {
    await apiClient.post(`/api/v1/favorites/${jobId}`, data)
  },

  // 移除收藏
  removeFavorite: async (jobId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/favorites/${jobId}`)
  },

  // 更新备注
  updateNotes: async (jobId: string, notes: string): Promise<void> => {
    await apiClient.put(`/api/v1/favorites/${jobId}/notes?notes=${encodeURIComponent(notes)}`)
  },
}
