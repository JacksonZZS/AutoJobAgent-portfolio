/**
 * 任务状态管理 (Zustand)
 */

import { create } from 'zustand'
import type { TaskStatusResponse } from '@/types/api'

interface TaskStore {
  taskStatus: TaskStatusResponse | null
  updateStatus: (status: TaskStatusResponse) => void
  reset: () => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  taskStatus: null,
  updateStatus: (status) => set({ taskStatus: status }),
  reset: () => set({ taskStatus: null }),
}))
