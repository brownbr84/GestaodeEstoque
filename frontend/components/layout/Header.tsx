'use client'
import { Sun, Moon, RefreshCw } from 'lucide-react'
import { useTheme } from 'next-themes'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/store'
import { useQueryClient } from '@tanstack/react-query'

interface HeaderProps {
  title: string
  subtitle?: string
}

export function Header({ title, subtitle }: HeaderProps) {
  const { theme, setTheme } = useTheme()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

  function handleRefresh() {
    queryClient.invalidateQueries()
  }

  return (
    <header className="flex items-center justify-between h-14 px-4 border-b border-border bg-background/95 backdrop-blur shrink-0">
      <div>
        <h1 className="text-base font-semibold text-foreground">{title}</h1>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleRefresh} title="Atualizar dados">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title="Alternar tema"
        >
          {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>
        <div className="flex items-center gap-2 ml-2 pl-2 border-l border-border">
          <div className="text-right">
            <p className="text-xs font-medium text-foreground leading-none">{user?.nome}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">{user?.perfil}</p>
          </div>
          <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary">
            {user?.nome?.charAt(0).toUpperCase() ?? '?'}
          </div>
        </div>
      </div>
    </header>
  )
}
