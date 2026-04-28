'use client'
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { matrizFisica } from '@/lib/api'
import { MapPin } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>

function statusBadge(status: string) {
  const m: Record<string, 'success' | 'warning' | 'destructive' | 'secondary'> = {
    'Disponível': 'success', 'Manutenção': 'warning', 'Extraviado': 'destructive',
    'Em Uso': 'info' as never, 'Catálogo': 'secondary',
  }
  return <Badge variant={m[status] ?? 'secondary'}>{status}</Badge>
}

export default function MatrizFisicaPage() {
  const [poloFiltro, setPoloFiltro] = useState('todos')

  const { data: raw = [], isLoading } = useQuery({
    queryKey: ['matriz-fisica'],
    queryFn: matrizFisica.raw,
    staleTime: 60_000,
  })

  const polos = useMemo(() => {
    const set = new Set((raw as Item[]).map(r => r.localizacao as string).filter(Boolean))
    return Array.from(set).sort()
  }, [raw])

  const dados = useMemo(() => {
    if (poloFiltro === 'todos') return raw as Item[]
    return (raw as Item[]).filter(r => r.localizacao === poloFiltro)
  }, [raw, poloFiltro])

  // Agrupa por código para exibir consolidado
  const consolidado = useMemo(() => {
    const map = new Map<string, { codigo: string; descricao: string; por_polo: Record<string, number>; total: number }>()
    for (const item of dados) {
      const cod = item.codigo as string
      const polo = (item.localizacao as string) || 'Sem Polo'
      const qtd = (item.quantidade as number) || 0
      if (!map.has(cod)) {
        map.set(cod, { codigo: cod, descricao: item.descricao as string, por_polo: {}, total: 0 })
      }
      const entry = map.get(cod)!
      entry.por_polo[polo] = (entry.por_polo[polo] || 0) + qtd
      entry.total += qtd
    }
    return Array.from(map.values())
  }, [dados])

  const cols: ColumnDef<Item>[] = [
    { accessorKey: 'codigo', header: 'Código', size: 120 },
    { accessorKey: 'descricao', header: 'Descrição' },
    { accessorKey: 'localizacao', header: 'Polo', size: 120 },
    { accessorKey: 'status', header: 'Status', size: 110, cell: ({ row }) => statusBadge(row.original.status as string) },
    { accessorKey: 'quantidade', header: 'Qtd', size: 60 },
  ]

  const colsConsolidado: ColumnDef<{ codigo: string; descricao: string; total: number; por_polo: Record<string, number> }>[] = [
    { accessorKey: 'codigo', header: 'Código', size: 120 },
    { accessorKey: 'descricao', header: 'Descrição' },
    {
      accessorKey: 'total', header: 'Total', size: 70,
      cell: ({ row }) => <span className="font-semibold">{row.original.total}</span>,
    },
    {
      id: 'polos', header: 'Por Polo',
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {Object.entries(row.original.por_polo).map(([p, q]) => (
            <span key={p} className="text-xs bg-muted px-1.5 py-0.5 rounded text-muted-foreground">{p}: {q}</span>
          ))}
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Matriz Física" subtitle="Distribuição do estoque por polo e produto" />
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="flex items-center gap-3">
          <Select value={poloFiltro} onValueChange={setPoloFiltro}>
            <SelectTrigger className="w-48 h-8"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Todos os Polos</SelectItem>
              {polos.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
            </SelectContent>
          </Select>
          <span className="text-xs text-muted-foreground">{dados.length} linha(s) · {consolidado.length} produto(s) distinto(s)</span>
        </div>

        {isLoading ? (
          <Skeleton className="h-96 w-full" />
        ) : (
          <div className="space-y-4">
            {/* Visão consolidada */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-primary" /> Visão Consolidada por Produto
                </CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable columns={colsConsolidado} data={consolidado} searchKey="descricao" searchPlaceholder="Filtrar produto…" />
              </CardContent>
            </Card>

            {/* Visão detalhada */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Visão Detalhada — todos os registros</CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable columns={cols} data={dados} searchKey="descricao" searchPlaceholder="Filtrar…" pageSize={30} />
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  )
}
