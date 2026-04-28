'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { produtos as produtosApi } from '@/lib/api'
import { formatCurrency, formatDate } from '@/lib/utils'
import { Search, ChevronLeft, Package } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

function statusBadge(status: string) {
  const map: Record<string, 'success' | 'warning' | 'destructive' | 'secondary'> = {
    'Disponível': 'success', 'Em Uso': 'info' as never, 'Manutenção': 'warning',
    'Extraviado': 'destructive', 'Catálogo': 'secondary',
  }
  return <Badge variant={map[status] ?? 'secondary'}>{status}</Badge>
}

type CatItem = { codigo: string; descricao: string; tipo_material: string }

const catalogoCols: ColumnDef<CatItem>[] = [
  { accessorKey: 'codigo', header: 'Código', size: 120 },
  { accessorKey: 'descricao', header: 'Descrição' },
  { accessorKey: 'tipo_material', header: 'Material', size: 100 },
]

export default function ProdutosPage() {
  const [selected, setSelected] = useState<string | null>(null)

  const { data: catalogo = [], isLoading } = useQuery({
    queryKey: ['catalogo'],
    queryFn: produtosApi.catalogo,
  })

  const { data: detalhes, isLoading: loadDetalhes } = useQuery({
    queryKey: ['produto-detalhes', selected],
    queryFn: () => produtosApi.detalhes(selected!),
    enabled: !!selected,
  })

  if (selected) {
    const mestre = detalhes?.mestre as Record<string, unknown> | undefined
    const inventario = detalhes?.inventario as Record<string, unknown>[] | undefined
    const historico = detalhes?.historico as Record<string, unknown>[] | undefined
    const tags = detalhes?.tags as Record<string, unknown>[] | undefined

    return (
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header title={`Produto — ${selected}`} />
        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
            <ChevronLeft className="h-4 w-4 mr-1" /> Voltar ao catálogo
          </Button>

          {loadDetalhes ? (
            <div className="space-y-3">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-60 w-full" />
            </div>
          ) : (
            <Tabs defaultValue="mestre">
              <TabsList>
                <TabsTrigger value="mestre">Ficha Técnica</TabsTrigger>
                <TabsTrigger value="inventario">Inventário ({inventario?.length ?? 0})</TabsTrigger>
                <TabsTrigger value="historico">Histórico ({historico?.length ?? 0})</TabsTrigger>
                {(tags?.length ?? 0) > 0 && <TabsTrigger value="calibracao">Calibração ({tags?.length})</TabsTrigger>}
              </TabsList>

              <TabsContent value="mestre">
                <Card>
                  <CardContent className="pt-4">
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {mestre && Object.entries(mestre).filter(([k]) => !['imagem'].includes(k)).map(([k, v]) => (
                        <div key={k}>
                          <p className="text-xs text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</p>
                          <p className="text-sm font-medium text-foreground mt-0.5">
                            {v == null ? '—' : k.includes('valor') ? formatCurrency(v as number) : k.includes('data') || k.includes('manutencao') ? formatDate(v as string) : String(v)}
                          </p>
                        </div>
                      ))}
                    </div>
                    {(mestre?.imagem as string) && (
                      <img src={`data:image/jpeg;base64,${mestre?.imagem}`} alt="Produto" className="mt-4 h-32 object-contain rounded-lg border border-border" />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="inventario">
                {inventario && (
                  <DataTable
                    columns={[
                      { accessorKey: 'num_tag', header: 'TAG/Serial' },
                      { accessorKey: 'localizacao', header: 'Polo' },
                      { accessorKey: 'endereco_codigo', header: 'Endereço', cell: ({ row }) => row.original.endereco_codigo || '—' },
                      { accessorKey: 'quantidade', header: 'Qtd', size: 60 },
                      { accessorKey: 'status', header: 'Status', cell: ({ row }) => statusBadge(row.original.status as string) },
                    ] as ColumnDef<Record<string, unknown>>[]}
                    data={inventario}
                  />
                )}
              </TabsContent>

              <TabsContent value="historico">
                {historico && (
                  <DataTable
                    columns={[
                      { accessorKey: 'Data', header: 'Data', cell: ({ row }) => formatDate(row.original['Data'] as string) },
                      { accessorKey: 'Serial', header: 'Serial/TAG' },
                      { accessorKey: 'Operação', header: 'Operação' },
                      { accessorKey: 'Doc/NF', header: 'Documento' },
                      { accessorKey: 'Agente', header: 'Responsável' },
                      { accessorKey: 'Destino', header: 'Destino' },
                    ] as ColumnDef<Record<string, unknown>>[]}
                    data={historico}
                    pageSize={50}
                  />
                )}
              </TabsContent>

              {(tags?.length ?? 0) > 0 && (
                <TabsContent value="calibracao">
                  <DataTable
                    columns={[
                      { accessorKey: 'TAG', header: 'TAG' },
                      { accessorKey: 'Localização', header: 'Polo' },
                      { accessorKey: 'Status', header: 'Status', cell: ({ row }) => statusBadge(row.original['Status'] as string) },
                      { accessorKey: 'Última Inspeção', header: 'Última Inspeção', cell: ({ row }) => formatDate(row.original['Última Inspeção'] as string) },
                      { accessorKey: 'Deadline Calibração', header: 'Próxima Calibração', cell: ({ row }) => formatDate(row.original['Deadline Calibração'] as string) },
                    ] as ColumnDef<Record<string, unknown>>[]}
                    data={tags ?? []}
                  />
                </TabsContent>
              )}
            </Tabs>
          )}
        </main>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Produtos" subtitle="Consulta do catálogo de produtos" />
      <main className="flex-1 overflow-y-auto p-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Package className="h-4 w-4 text-primary" />
              Catálogo — {catalogo.length} produto(s)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : (
              <DataTable
                columns={[
                  ...catalogoCols,
                  {
                    id: 'actions',
                    header: '',
                    size: 80,
                    cell: ({ row }) => (
                      <Button size="sm" variant="ghost" onClick={() => setSelected(row.original.codigo)}>
                        <Search className="h-3.5 w-3.5 mr-1" /> Ver
                      </Button>
                    ),
                  },
                ]}
                data={catalogo}
                searchKey="descricao"
                searchPlaceholder="Filtrar por descrição…"
              />
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
