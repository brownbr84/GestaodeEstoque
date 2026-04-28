'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Package, Users, ArrowDownToLine, ArrowUpFromLine,
  ClipboardList, MapPin, Tag, FileText, Wrench, ShoppingCart,
  BarChart3, Settings, Shield, Building2, Boxes, LogOut, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore, useUIStore } from '@/store'
import { Button } from '@/components/ui/button'
import { useRouter } from 'next/navigation'

const navItems = [
  { href: '/',               label: 'Torre de Controle',  icon: LayoutDashboard },
  { href: '/cadastro',       label: 'Cadastro',           icon: Package },
  { href: '/produtos',       label: 'Produtos',           icon: Boxes },
  { href: '/parceiros',      label: 'Parceiros',          icon: Building2 },
  { href: '/inbound',        label: 'Inbound',            icon: ArrowDownToLine },
  { href: '/outbound',       label: 'Outbound',           icon: ArrowUpFromLine },
  { href: '/inventario',     label: 'Inventário',         icon: ClipboardList },
  { href: '/matriz-fisica',  label: 'Matriz Física',      icon: MapPin },
  { href: '/etiquetas',      label: 'Etiquetas',          icon: Tag },
  { href: '/fiscal',         label: 'Fiscal (NF-e)',      icon: FileText },
  { href: '/manutencao',     label: 'Manutenção',         icon: Wrench },
  { href: '/requisicao',     label: 'Requisição',         icon: ShoppingCart },
  { href: '/auditoria',      label: 'Auditoria',          icon: Shield },
  { href: '/relatorios',     label: 'Relatórios',         icon: BarChart3 },
  { href: '/configuracoes',  label: 'Configurações',      icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuthStore()
  const { sidebarOpen, toggleSidebar } = useUIStore()

  function handleLogout() {
    logout()
    router.push('/login')
  }

  return (
    <aside className={cn(
      'flex flex-col h-screen bg-sidebar border-r border-sidebar-border transition-all duration-200 shrink-0',
      sidebarOpen ? 'w-56' : 'w-14'
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-4 border-b border-sidebar-border">
        {sidebarOpen && (
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center shrink-0">
              <span className="text-white text-xs font-bold">TB</span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-sidebar-foreground truncate">TraceBox</p>
              <p className="text-[10px] text-muted-foreground">WMS Enterprise</p>
            </div>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className={cn(
            'p-1 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors',
            !sidebarOpen && 'mx-auto'
          )}
        >
          {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              title={!sidebarOpen ? label : undefined}
              className={cn(
                'flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors',
                active
                  ? 'bg-primary/15 text-primary font-medium'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <Icon className={cn('h-4 w-4 shrink-0', active && 'text-primary')} />
              {sidebarOpen && <span className="truncate">{label}</span>}
            </Link>
          )
        })}
      </nav>

      {/* User / Logout */}
      <div className="border-t border-sidebar-border p-2">
        {sidebarOpen ? (
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-xs font-medium text-sidebar-foreground truncate">{user?.nome}</p>
              <p className="text-[10px] text-muted-foreground">{user?.perfil}</p>
            </div>
            <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive" onClick={handleLogout} title="Sair">
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : (
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center p-2 rounded-md text-muted-foreground hover:text-destructive hover:bg-accent transition-colors"
            title="Sair"
          >
            <LogOut className="h-4 w-4" />
          </button>
        )}
      </div>
    </aside>
  )
}
