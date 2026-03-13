/**
 * 简历优化器状态管理 (Zustand)
 * 保持页面状态，避免导航时丢失
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { OptimizeResumeResponse } from '@/api/resumeOptimizer'

interface ResumeOptimizerFormData {
  permanent_resident: boolean
  available_immediately: boolean
  linkedin_url: string
  github_url: string
  portfolio_url: string
  additional_notes: string
}

interface StoredFile {
  name: string
  type: string
  size: number
  base64: string
}

interface ResumeOptimizerStore {
  // 表单数据
  formData: ResumeOptimizerFormData
  setFormData: (data: Partial<ResumeOptimizerFormData>) => void

  // 文件数据（Base64 存储）
  storedFile: StoredFile | null
  setStoredFile: (file: StoredFile | null) => void

  // 优化结果
  optimizedResult: OptimizeResumeResponse | null
  setOptimizedResult: (result: OptimizeResumeResponse | null) => void

  // 重置所有状态
  reset: () => void
}

const initialFormData: ResumeOptimizerFormData = {
  permanent_resident: false,
  available_immediately: false,
  linkedin_url: '',
  github_url: '',
  portfolio_url: '',
  additional_notes: '',
}

export const useResumeOptimizerStore = create<ResumeOptimizerStore>()(
  persist(
    (set) => ({
      formData: initialFormData,
      setFormData: (data) =>
        set((state) => ({
          formData: { ...state.formData, ...data },
        })),

      storedFile: null,
      setStoredFile: (file) => set({ storedFile: file }),

      optimizedResult: null,
      setOptimizedResult: (result) => set({ optimizedResult: result }),

      reset: () =>
        set({
          formData: initialFormData,
          storedFile: null,
          optimizedResult: null,
        }),
    }),
    {
      name: 'resume-optimizer-storage',
    }
  )
)

// 工具函数：File 转 Base64
export async function fileToBase64(file: File): Promise<StoredFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      resolve({
        name: file.name,
        type: file.type,
        size: file.size,
        base64: reader.result as string,
      })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// 工具函数：Base64 转 File
export function base64ToFile(stored: StoredFile): File {
  const arr = stored.base64.split(',')
  const mime = arr[0].match(/:(.*?);/)?.[1] || stored.type
  const bstr = atob(arr[1])
  let n = bstr.length
  const u8arr = new Uint8Array(n)
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n)
  }
  return new File([u8arr], stored.name, { type: mime })
}
