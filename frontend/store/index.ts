'use client'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'

interface AuthState {
  token: string | null
  user: User | null
  lastActivity: number
  login: (token: string, user: Omit<User, 'access_token'>) => void
  logout: () => void
  updateActivity: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      lastActivity: Date.now(),
      login: (token, userInfo) => {
        const user: User = { ...userInfo, access_token: token }
        // Cookie para middleware Next.js
        if (typeof document !== 'undefined') {
          document.cookie = `tracebox_token=${token}; path=/; max-age=${60 * 60 * 12}; SameSite=Lax`
        }
        set({ token, user, lastActivity: Date.now() })
      },
      logout: () => {
        if (typeof document !== 'undefined') {
          document.cookie = 'tracebox_token=; path=/; max-age=0'
        }
        set({ token: null, user: null })
      },
      updateActivity: () => set({ lastActivity: Date.now() }),
    }),
    {
      name: 'tracebox-auth',
      partialize: (s) => ({ token: s.token, user: s.user }),
    }
  )
)

interface UIState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (v: boolean) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
}))
