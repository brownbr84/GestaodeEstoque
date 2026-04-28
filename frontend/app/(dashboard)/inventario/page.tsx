'use client'
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { inventario as inventarioApi, polos as polosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { ClipboardList, Play, CheckCircle } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>

const CLASSIFICACOES = [
  'Todos', 'Apenas Ativos (Máquinas com TAG)', 'Apenas Consumo (Lotes/Insumos)',
]

export default function InventarioPage() {
  const { user } = useAuthStore()
  const [polo, setPolo] = useState('')
  const [classificacao, setClassificacao] = useState('Todos')
  const [tagsBipadas, setTagsBipadas] = useState('')
  const [fase, setFase] = useState<'setup' | 'coleta' | 'resultado'>('setup')
  const [resultados, setResultados] = useState<Item[]>([])
  const [invId] = useState(() => `INV-${Date.now()}`)

  const { data: polosData } = useQuery({ queryKey: ['polos'], queryFn: polosApi.emUso })
  const polos = polosData?.polos ?? []

  const { data: esperados = [] } = useQuery({
    queryKey: ['inventario-esperado', polo, classificacao],
    queryFn: () => inventarioApi.esperado(polo, classificacao),
    enabled: !!polo && fase === 'coleta',
  })

  const cruzamentoMut = useMutation({
    mutationFn: () => {
      const tags = tagsBipadas.split('\n').map(t => t.trim()).filter(Boolean)
      return inventarioApi.cruzamento(polo, tags, {}) as Promise<{ resultados_finais: Item[]; divergencias: number }>
    },
    onSuccess: (data) => {
      setResultados(data.resultados_finais ?? [])
      setFase('resultado')
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const processarMut = useMutation({
    mutationFn: () => inventarioApi.processar({ resultados_finais: resultados, usuario: user?.usuario ?? '', polo, inv_id: invId }),
    onSuccess: () => {
      toast.success('Inventário processado com sucesso!')
      setFase('setup')
      setTagsBipadas('')
      setResultados([])
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const divergencias = resultados.filter(r => r.divergencia || r.status === 'Divergência').length

  const resultadosCols: ColumnDef<Item>[] = [
    { accessorKey: 'codigo', header: 'Código' },
    { accessorKey: 'descricao', header: 'Descrição' },
    { accessorKey: 'num_tag', header: 'TAG' },
    { accessorKey: 'qtd_esperada', header: 'Esperado', size: 80 },
    { accessorKey: 'qtd_contada', header: 'Contado', size: 80 },
    {
      accessorKey: 'status', header: 'Resultado', size: 120,
      cell: ({ row }) => {
        const s = row.original.status as string
        return <Badge variant={s === 'OK' ? 'success' : s?.includes('Falta') ? 'destructive' : 'warning'}>{s}</Badge>
      },
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Inventário" subtitle="Contagem e conciliação de estoque" />
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {fase === 'setup' && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <ClipboardList className="h-4 w-4 text-primary" /> Configurar Inventário
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>Polo <span className="text-destructive">*</span></Label>
                  <Select value={polo} onValueChange={setPolo}>
                    <SelectTrigger><SelectValue placeholder="Selecione o polo…" /></SelectTrigger>
                    <SelectContent>{polos.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Classificação</Label>
                  <Select value={classificacao} onValueChange={setClassificacao}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{CLASSIFICACOES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <Button onClick={() => setFase('coleta')} disabled={!polo}>
                <Play className="h-4 w-4 mr-2" /> Iniciar Inventário
              </Button>
            </CardContent>
          </Card>
        )}

        {fase === 'coleta' && (
          <div className="space-y-4">
            <Alert><AlertDescription>Inventário em andamento — Polo: <strong>{polo}</strong> | ID: {invId}</AlertDescription></Alert>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm">Estoque Esperado ({esperados.length})</CardTitle></CardHeader>
                <CardContent>
                  <DataTable
                    columns={[
                      { accessorKey: 'codigo', header: 'Código' },
                      { accessorKey: 'descricao', header: 'Descrição' },
                      { accessorKey: 'num_tag', header: 'TAG' },
                      { accessorKey: 'quantidade', header: 'Qtd', size: 60 },
                    ] as ColumnDef<Item>[]}
                    data={esperados as Item[]}
                    pageSize={10}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm">Bipagem de TAGs</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <Label className="text-xs text-muted-foreground">Cole ou digite as TAGs encontradas (uma por linha)</Label>
                  <textarea
                    className="w-full h-40 rounded-md border border-input bg-transparent px-3 py-2 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={tagsBipadas}
                    onChange={e => setTagsBipadas(e.target.value)}
                    placeholder="TAG-001&#10;TAG-002&#10;TAG-003"
                  />
                  <p className="text-xs text-muted-foreground">{tagsBipadas.split('\n').filter(t => t.trim()).length} TAGs informadas</p>
                </CardContent>
              </Card>
            </div>

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => { setFase('setup'); setTagsBipadas('') }}>← Cancelar</Button>
              <Button onClick={() => cruzamentoMut.mutate()} disabled={cruzamentoMut.isPending}>
                {cruzamentoMut.isPending ? 'Processando…' : 'Cruzar Dados'}
              </Button>
            </div>
          </div>
        )}

        {fase === 'resultado' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {divergencias > 0
                  ? <Badge variant="destructive">{divergencias} divergência(s)</Badge>
                  : <Badge variant="success">Sem divergências</Badge>}
                <span className="text-sm text-muted-foreground">{resultados.length} item(s) verificado(s)</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setFase('coleta')}>← Revisar</Button>
                <Button size="sm" onClick={() => processarMut.mutate()} disabled={processarMut.isPending}>
                  <CheckCircle className="h-4 w-4 mr-1" />
                  {processarMut.isPending ? 'Processando…' : 'Confirmar Inventário'}
                </Button>
              </div>
            </div>
            <DataTable columns={resultadosCols} data={resultados} searchKey="descricao" />
          </div>
        )}
      </main>
    </div>
  )
}
