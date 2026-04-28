'use client'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { dashboard } from '@/lib/api'
import {
  Package, MapPin, Wrench, ShoppingCart, AlertTriangle, TrendingUp,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function MetricCard({ label, value, icon: Icon, color = 'text-primary' }: {
  label: string; value?: number | string; icon: React.ElementType; color?: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="p-2.5 rounded-lg bg-primary/10">
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          {value !== undefined
            ? <p className="text-2xl font-bold text-foreground mt-0.5">{value}</p>
            : <Skeleton className="h-7 w-16 mt-1" />}
        </div>
      </CardContent>
    </Card>
  )
}

export default function TorreControle() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-metricas'],
    queryFn: () => dashboard.metricas() as Promise<Record<string, unknown>>,
    refetchInterval: 60_000,
  })

  const metricas = data as Record<string, unknown> | undefined

  // Dados para gráficos
  const statusData = metricas
    ? [
        { name: 'Disponível', value: Number(metricas.disponiveis ?? 0) },
        { name: 'Em Uso', value: Number(metricas.em_uso ?? 0) },
        { name: 'Manutenção', value: Number(metricas.em_manutencao ?? 0) },
        { name: 'Trânsito', value: Number(metricas.em_transito ?? 0) },
      ].filter(d => d.value > 0)
    : []

  const polosData = metricas?.polos_resumo
    ? (metricas.polos_resumo as unknown as Array<{ polo: string; total: number }>)
    : []

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Torre de Controle" subtitle="Visão geral do estoque em tempo real" />
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Métricas */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <MetricCard label="Total de Ativos" value={isLoading ? undefined : Number(metricas?.total_ativos ?? 0)} icon={Package} />
          <MetricCard label="Polos Ativos" value={isLoading ? undefined : Number(metricas?.total_polos ?? 0)} icon={MapPin} />
          <MetricCard label="Em Manutenção" value={isLoading ? undefined : Number(metricas?.em_manutencao ?? 0)} icon={Wrench} color="text-amber-400" />
          <MetricCard label="Req. Pendentes" value={isLoading ? undefined : Number(metricas?.requisicoes_pendentes ?? 0)} icon={ShoppingCart} color="text-blue-400" />
          <MetricCard label="Alertas de Falta" value={isLoading ? undefined : Number(metricas?.produtos_em_falta ?? 0)} icon={AlertTriangle} color="text-red-400" />
        </div>

        {/* Gráficos */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Status */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                Distribuição por Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : statusData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false} fontSize={11}>
                      {statusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v) => [v, 'Itens']} contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
                  Sem dados de status
                </div>
              )}
            </CardContent>
          </Card>

          {/* Por Polo */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <MapPin className="h-4 w-4 text-primary" />
                Estoque por Polo
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : polosData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={polosData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="polo" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                    <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="total" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} name="Itens" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
                  Sem dados por polo
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Info adicional da API */}
        {metricas && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(metricas.alertas as Array<{ tipo: string; mensagem: string }> | undefined)?.map((a, i) => (
              <Card key={i} className="border-amber-500/30 bg-amber-500/5">
                <CardContent className="flex items-start gap-3 p-4">
                  <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-amber-400">{a.tipo}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{a.mensagem}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
