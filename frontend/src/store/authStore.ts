/**
 * 认证状态管理 (Zustand)
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/api'

interface AuthStore {
  user: User | null
  token: string | null
  setAuth: (user: User, token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (user, token) => set({ user, token }),
      logout: () => set({ user: null, token: null }),
    }),
    {
      name: 'auth-storage',
    }
  )
)
