'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { auditoria as auditApi } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'
import { Shield, Search } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Log = Record<string, unknown>

const ACOES = ['Todas', 'ENTRADA_COMPRA', 'SAIDA_ESTOQUE', 'CANCELAMENTO', 'INVENTARIO', 'MANUTENCAO', 'REQUISICAO', 'CONFIGURACAO', 'USUARIO']

const acaoBadge = (acao: string) => {
  const m: Record<string, 'success' | 'destructive' | 'warning' | 'secondary' | 'info'> = {
    'ENTRADA_COMPRA': 'success', 'SAIDA_ESTOQUE': 'info' as never,
    'CANCELAMENTO': 'destructive', 'INVENTARIO': 'warning',
  }
  return <Badge variant={m[acao] ?? 'secondary'} className="text-[10px]">{acao}</Badge>
}

export default function AuditoriaPage() {
  const [filtroAcao, setFiltroAcao] = useState('Todas')
  const [filtroUsuario, setFiltroUsuario] = useState('')
  const [filtroData, setFiltroData] = useState('')
  const [buscar, setBuscar] = useState(false)

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['auditoria-logs', filtroAcao, filtroUsuario, filtroData, buscar],
    queryFn: () => auditApi.logs(filtroAcao, filtroUsuario, filtroData) as Promise<Log[]>,
    enabled: true,
  })

  const cols: ColumnDef<Log>[] = [
    { accessorKey: 'id', header: '#', size: 60 },
    { accessorKey: 'data_hora', header: 'Data/Hora', size: 140, cell: ({ row }) => formatDateTime(row.original.data_hora as string) },
    { accessorKey: 'usuario', header: 'Usuário', size: 100 },
    { accessorKey: 'acao', header: 'Ação', size: 160, cell: ({ row }) => acaoBadge(row.original.acao as string) },
    { accessorKey: 'tabela', header: 'Tabela', size: 120 },
    { accessorKey: 'registro_id', header: 'Reg. ID', size: 70 },
    { accessorKey: 'detalhes', header: 'Detalhes', cell: ({ row }) => <span className="text-xs text-muted-foreground truncate max-w-xs block">{row.original.detalhes as string}</span> },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Auditoria & Compliance" subtitle="Rastreabilidade completa de todas as operações" />
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Filtros */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield className="h-4 w-4 text-primary" /> Filtros de Auditoria
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="space-y-1.5 w-48">
                <Label>Ação</Label>
                <Select value={filtroAcao} onValueChange={setFiltroAcao}>
                  <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                  <SelectContent>{ACOES.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Usuário</Label>
                <Input className="h-8 w-36" value={filtroUsuario} onChange={e => setFiltroUsuario(e.target.value)} placeholder="Filtrar por usuário…" />
              </div>
              <div className="space-y-1.5">
                <Label>Data</Label>
                <Input className="h-8" type="date" value={filtroData} onChange={e => setFiltroData(e.target.value)} />
              </div>
              <Button size="sm" onClick={() => setBuscar(b => !b)}>
                <Search className="h-4 w-4 mr-1" /> Buscar
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{isLoading ? 'Carregando…' : `${logs.length} registro(s) encontrado(s)`}</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable columns={cols} data={logs} pageSize={30} emptyMessage="Nenhum log encontrado com os filtros aplicados." />
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
