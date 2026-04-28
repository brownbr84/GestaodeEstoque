'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store'
import { Sidebar } from '@/components/layout/Sidebar'

const INACTIVITY_MS = 10 * 60 * 1000 // 10 minutos

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { token, logout, updateActivity, lastActivity } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (!token) {
      router.push('/login')
      return
    }

    const checkInactivity = () => {
      if (Date.now() - lastActivity > INACTIVITY_MS) {
        logout()
        router.push('/login')
      }
    }

    const interval = setInterval(checkInactivity, 60_000)
    return () => clearInterval(interval)
  }, [token, lastActivity, logout, router])

  useEffect(() => {
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart']
    const handler = () => updateActivity()
    events.forEach(e => window.addEventListener(e, handler, { passive: true }))
    return () => events.forEach(e => window.removeEventListener(e, handler))
  }, [updateActivity])

  if (!token) return null

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {children}
      </div>
    </div>
  )
}
