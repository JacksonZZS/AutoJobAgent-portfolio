/**
 * 认证 API
 */

import apiClient from './client'
import type { LoginRequest, RegisterRequest, LoginResponse, User } from '@/types/api'

export const authAPI = {
  // 登录
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post('/api/v1/auth/login', data)
    return response.data
  },

  // 注册
  register: async (data: RegisterRequest) => {
    const response = await apiClient.post('/api/v1/auth/register', data)
    return response.data
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get('/api/v1/auth/me')
    return response.data
  },

  // 登出
  logout: async () => {
    const response = await apiClient.post('/api/v1/auth/logout')
    return response.data
  },
}
