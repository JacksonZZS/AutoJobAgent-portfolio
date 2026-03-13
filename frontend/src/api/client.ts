/**
 * Axios API 客户端配置
 */

import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

// 生产环境使用相对路径（前后端同源），开发环境使用 localhost
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000')

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 增加到 120 秒，支持大文件上传和 LLM 分析
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：自动添加 JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：处理 401 错误自动登出
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期或无效，自动登出
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
