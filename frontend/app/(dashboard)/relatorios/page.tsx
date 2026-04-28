'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { relatorios as relApi } from '@/lib/api'
import { formatDate, formatCurrency } from '@/lib/utils'
import { BarChart3, Download } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>

export default function RelatoriosPage() {
  const today = new Date().toISOString().split('T')[0]
  const [produtoSel, setProdutoSel] = useState('')
  const [dataIni, setDataIni] = useState(new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0])
  const [dataFim, setDataFim] = useState(today)
  const [statusManut, setStatusManut] = useState('Concluída')
  const [buscarExtrato, setBuscarExtrato] = useState(false)
  const [buscarManut, setBuscarManut] = useState(false)

  const { data: produtosData } = useQuery({ queryKey: ['rel-produtos'], queryFn: relApi.produtos })
  const { data: posicao = [] } = useQuery({ queryKey: ['rel-posicao'], queryFn: relApi.posicao })
  const { data: extrato } = useQuery({
    queryKey: ['rel-extrato', produtoSel, dataIni, dataFim, buscarExtrato],
    queryFn: () => relApi.extrato(produtoSel, dataIni, dataFim),
    enabled: !!produtoSel && buscarExtrato,
  })
  const { data: manutRel = [] } = useQuery({
    queryKey: ['rel-manutencao', dataIni, dataFim, statusManut, buscarManut],
    queryFn: () => relApi.manutencao(dataIni, dataFim, statusManut),
    enabled: buscarManut,
  })

  const produtos = produtosData?.produtos ?? []
  const extratoData = extrato?.dados ?? []

  function downloadCSV(data: Item[], filename: string) {
    if (!data.length) return
    const headers = Object.keys(data[0])
    const rows = data.map(r => headers.map(h => `"${String(r[h] ?? '').replace(/"/g, '""')}"`).join(','))
    const csv = [headers.join(','), ...rows].join('\n')
    const a = document.createElement('a')
    a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent('﻿' + csv)
    a.download = filename
    a.click()
  }

  const posicaoCols: ColumnDef<Item>[] = [
    { accessorKey: 'codigo', header: 'Código', size: 100 },
    { accessorKey: 'descricao', header: 'Descrição' },
    { accessorKey: 'categoria', header: 'Categoria', size: 100 },
    { accessorKey: 'tipo_material', header: 'Material', size: 80 },
    { accessorKey: 'localizacao', header: 'Polo', size: 100 },
    { accessorKey: 'status', header: 'Status', size: 100 },
    { accessorKey: 'quantidade', header: 'Qtd', size: 60 },
    { accessorKey: 'valor_unitario', header: 'Valor Unit.', cell: ({ row }) => formatCurrency(row.original.valor_unitario as number) },
  ]

  const extratoCols: ColumnDef<Item>[] = [
    { accessorKey: 'Data', header: 'Data', cell: ({ row }) => formatDate(row.original['Data'] as string) },
    { accessorKey: 'Serial', header: 'Serial / TAG' },
    { accessorKey: 'Operação', header: 'Operação' },
    { accessorKey: 'Doc/NF', header: 'Documento' },
    { accessorKey: 'Agente', header: 'Responsável' },
    { accessorKey: 'Destino', header: 'Destino' },
  ]

  const manutCols: ColumnDef<Item>[] = [
    { accessorKey: 'id', header: 'OS', size: 60 },
    { accessorKey: 'codigo_ferramenta', header: 'Código' },
    { accessorKey: 'motivo_falha', header: 'Motivo' },
    { accessorKey: 'data_entrada', header: 'Abertura', cell: ({ row }) => formatDate(row.original.data_entrada as string) },
    { accessorKey: 'data_saida', header: 'Fechamento', cell: ({ row }) => formatDate(row.original.data_saida as string) },
    { accessorKey: 'custo_reparo', header: 'Custo', cell: ({ row }) => formatCurrency(row.original.custo_reparo as number) },
    { accessorKey: 'status_ordem', header: 'Status' },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Relatórios" subtitle="Extratos, posição de estoque e manutenção" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <Tabs defaultValue="posicao">
          <TabsList>
            <TabsTrigger value="posicao" className="text-xs">Posição de Estoque</TabsTrigger>
            <TabsTrigger value="extrato" className="text-xs">Extrato de Movimentações</TabsTrigger>
            <TabsTrigger value="manutencao" className="text-xs">Relatório de Manutenção</TabsTrigger>
          </TabsList>

          <TabsContent value="posicao">
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-primary" /> Posição Atual do Estoque ({posicao.length} itens)
                  </CardTitle>
                  <Button size="sm" variant="outline" onClick={() => downloadCSV(posicao as Item[], 'posicao_estoque.csv')}>
                    <Download className="h-3.5 w-3.5 mr-1" /> CSV
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <DataTable columns={posicaoCols} data={posicao as Item[]} searchKey="descricao" pageSize={25} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="extrato">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Extrato de Movimentações</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="space-y-1.5 w-60">
                    <Label>Produto</Label>
                    <Select value={produtoSel} onValueChange={setProdutoSel}>
                      <SelectTrigger className="h-8"><SelectValue placeholder="Selecione…" /></SelectTrigger>
                      <SelectContent>{produtos.map((p: string) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Data Início</Label>
                    <Input className="h-8 w-36" type="date" value={dataIni} onChange={e => setDataIni(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Data Fim</Label>
                    <Input className="h-8 w-36" type="date" value={dataFim} onChange={e => setDataFim(e.target.value)} />
                  </div>
                  <Button size="sm" onClick={() => setBuscarExtrato(b => !b)} disabled={!produtoSel}>Gerar Extrato</Button>
                  {extratoData.length > 0 && (
                    <Button size="sm" variant="outline" onClick={() => downloadCSV(extratoData as Item[], `extrato_${produtoSel}.csv`)}>
                      <Download className="h-3.5 w-3.5 mr-1" /> CSV
                    </Button>
                  )}
                </div>
                <DataTable columns={extratoCols} data={extratoData as Item[]} emptyMessage="Selecione um produto e clique em Gerar Extrato." />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="manutencao">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Relatório de Manutenção</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="space-y-1.5">
                    <Label>Data Início</Label>
                    <Input className="h-8 w-36" type="date" value={dataIni} onChange={e => setDataIni(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Data Fim</Label>
                    <Input className="h-8 w-36" type="date" value={dataFim} onChange={e => setDataFim(e.target.value)} />
                  </div>
                  <div className="space-y-1.5 w-40">
                    <Label>Status</Label>
                    <Select value={statusManut} onValueChange={setStatusManut}>
                      <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {['Concluída', 'Cancelada', 'Todas'].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button size="sm" onClick={() => setBuscarManut(b => !b)}>Gerar Relatório</Button>
                  {(manutRel as Item[]).length > 0 && (
                    <Button size="sm" variant="outline" onClick={() => downloadCSV(manutRel as Item[], 'manutencao.csv')}>
                      <Download className="h-3.5 w-3.5 mr-1" /> CSV
                    </Button>
                  )}
                </div>
                <DataTable columns={manutCols} data={manutRel as Item[]} emptyMessage="Clique em Gerar Relatório para buscar os dados." />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
