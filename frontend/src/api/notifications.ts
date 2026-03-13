/**
 * 通知 API
 */

import apiClient from './client'

export interface NotificationPreferences {
  push_enabled: boolean
  email_enabled: boolean
  email_address: string | null
  high_score_threshold: number
  notify_on_complete: boolean
  notify_on_error: boolean
}

export interface UpdateNotificationPreferencesRequest {
  push_enabled?: boolean
  email_enabled?: boolean
  email_address?: string
  high_score_threshold?: number
  notify_on_complete?: boolean
  notify_on_error?: boolean
}

export interface WebPushSubscription {
  endpoint: string
  keys: Record<string, string>
}

export const notificationsAPI = {
  // 获取通知偏好
  getPreferences: async (): Promise<NotificationPreferences> => {
    const response = await apiClient.get('/api/v1/notifications/preferences')
    return response.data
  },

  // 更新通知偏好
  updatePreferences: async (data: UpdateNotificationPreferencesRequest): Promise<NotificationPreferences> => {
    const response = await apiClient.put('/api/v1/notifications/preferences', data)
    return response.data
  },

  // 订阅 Web Push
  subscribePush: async (subscription: WebPushSubscription): Promise<void> => {
    await apiClient.post('/api/v1/notifications/subscribe-push', subscription)
  },

  // 取消订阅
  unsubscribePush: async (): Promise<void> => {
    await apiClient.delete('/api/v1/notifications/unsubscribe-push')
  },
}
