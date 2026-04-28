'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { inbound as inboundApi, polos as polosApi, produtos as produtosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { ArrowDownToLine, AlertTriangle, Plus } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>

export default function InboundPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()

  const [poloAtual, setPoloAtual] = useState('')
  const [modalCompra, setModalCompra] = useState(false)
  const [formCompra, setFormCompra] = useState({ codigo_produto: '', polo_destino: '', nf: '', valor_unit: '', quantidade: '' })

  const { data: polosData } = useQuery({ queryKey: ['polos'], queryFn: polosApi.emUso })
  const { data: faltas = [], isLoading: loadFaltas } = useQuery({ queryKey: ['inbound-faltas'], queryFn: inboundApi.malhaFinaFaltas })
  const { data: catalogo = [] } = useQuery({ queryKey: ['catalogo'], queryFn: produtosApi.catalogo })

  const polos = polosData?.polos ?? []

  const comprarMut = useMutation<Record<string, unknown>>({
    mutationFn: async () => (await inboundApi.compras({
      codigo_produto: formCompra.codigo_produto,
      polo_destino: formCompra.polo_destino || poloAtual,
      nf: formCompra.nf,
      valor_unit: parseFloat(formCompra.valor_unit) || 0,
      quantidade: parseInt(formCompra.quantidade) || 1,
      usuario: user?.usuario ?? '',
    })) as Record<string, unknown>,
    onSuccess: (data: Record<string, unknown>) => {
      toast.success((data.mensagem as string) ?? 'Entrada registrada!')
      qc.invalidateQueries({ queryKey: ['inbound-faltas'] })
      setModalCompra(false)
      setFormCompra({ codigo_produto: '', polo_destino: '', nf: '', valor_unit: '', quantidade: '' })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const reintegrarMut = useMutation({
    mutationFn: (item: Item) => inboundApi.reintegrar({ id_db: item.id, qtd_enc: item.quantidade, qtd_pendente: 0, destino: poloAtual, usuario: user?.usuario ?? '' }),
    onSuccess: () => { toast.success('Item reintegrado!'); qc.invalidateQueries({ queryKey: ['inbound-faltas'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  const faltasCols: ColumnDef<Item>[] = [
    { accessorKey: 'codigo', header: 'Código' },
    { accessorKey: 'descricao', header: 'Descrição' },
    { accessorKey: 'num_tag', header: 'TAG/Serial' },
    { accessorKey: 'localizacao', header: 'Polo' },
    { accessorKey: 'quantidade', header: 'Qtd', size: 60 },
    { accessorKey: 'tipo_material', header: 'Material', size: 80 },
    {
      id: 'actions', header: '', size: 100,
      cell: ({ row }) => (
        <Button size="sm" variant="outline" onClick={() => reintegrarMut.mutate(row.original)} disabled={reintegrarMut.isPending}>
          Reintegrar
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Inbound" subtitle="Recebimento e entrada de mercadorias" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-48">
            <Select value={poloAtual} onValueChange={setPoloAtual}>
              <SelectTrigger className="h-8"><SelectValue placeholder="Selecione o polo…" /></SelectTrigger>
              <SelectContent>
                {polos.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button size="sm" onClick={() => setModalCompra(true)}>
            <Plus className="h-4 w-4 mr-1" /> Entrada por Compra
          </Button>
        </div>

        <Tabs defaultValue="faltas">
          <TabsList>
            <TabsTrigger value="faltas" className="text-xs">
              Malha Fina — Alertas de Falta
              {faltas.length > 0 && <Badge variant="destructive" className="ml-2 text-[10px]">{faltas.length}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="doca" className="text-xs">Recebimento em Doca</TabsTrigger>
          </TabsList>

          <TabsContent value="faltas">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400" /> Itens com Alerta de Falta
                </CardTitle>
              </CardHeader>
              <CardContent>
                {faltas.length === 0 && !loadFaltas ? (
                  <Alert variant="success"><AlertDescription>Nenhum alerta de falta registrado.</AlertDescription></Alert>
                ) : (
                  <DataTable columns={faltasCols} data={faltas} searchKey="descricao" searchPlaceholder="Filtrar…" />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="doca">
            <DocaRecebimento polo={poloAtual} usuario={user?.usuario ?? ''} />
          </TabsContent>
        </Tabs>
      </main>

      {/* Modal Entrada por Compra */}
      <Dialog open={modalCompra} onOpenChange={setModalCompra}>
        <DialogContent>
          <DialogHeader><DialogTitle>Entrada por Compra (NF)</DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label>Produto <span className="text-destructive">*</span></Label>
              <Select value={formCompra.codigo_produto} onValueChange={v => setFormCompra(p => ({ ...p, codigo_produto: v }))}>
                <SelectTrigger><SelectValue placeholder="Selecione o produto…" /></SelectTrigger>
                <SelectContent>
                  {(catalogo as { codigo: string; descricao: string }[]).map(c => (
                    <SelectItem key={c.codigo} value={c.codigo}>{c.codigo} — {c.descricao}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Polo Destino <span className="text-destructive">*</span></Label>
              <Select value={formCompra.polo_destino || poloAtual} onValueChange={v => setFormCompra(p => ({ ...p, polo_destino: v }))}>
                <SelectTrigger><SelectValue placeholder="Polo…" /></SelectTrigger>
                <SelectContent>{polos.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Nº NF</Label>
                <Input value={formCompra.nf} onChange={e => setFormCompra(p => ({ ...p, nf: e.target.value }))} placeholder="NF-00001" />
              </div>
              <div className="space-y-1.5">
                <Label>Quantidade</Label>
                <Input type="number" min="1" value={formCompra.quantidade} onChange={e => setFormCompra(p => ({ ...p, quantidade: e.target.value }))} placeholder="1" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Valor Unitário (R$)</Label>
              <Input type="number" step="0.01" min="0" value={formCompra.valor_unit} onChange={e => setFormCompra(p => ({ ...p, valor_unit: e.target.value }))} placeholder="0,00" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalCompra(false)}>Cancelar</Button>
            <Button onClick={() => comprarMut.mutate()} disabled={comprarMut.isPending}>
              {comprarMut.isPending ? 'Registrando…' : 'Registrar Entrada'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function DocaRecebimento({ polo, usuario }: { polo: string; usuario: string }) {
  const qc = useQueryClient()
  const [origem, setOrigem] = useState('')

  const { data: origensData } = useQuery({
    queryKey: ['doca-origens', polo],
    queryFn: () => inboundApi.docaOrigens(polo),
    enabled: !!polo,
  })

  const { data: esperados = [] } = useQuery({
    queryKey: ['doca-esperados', origem, polo],
    queryFn: () => inboundApi.docaEsperados(origem, polo),
    enabled: !!origem && !!polo,
  })

  const receberMut = useMutation<Record<string, unknown>, Error, Record<string, number>>({
    mutationFn: async (tagsBipadas: Record<string, number>) => (await inboundApi.docaReceber({
      origem, polo_atual: polo, dict_ativos: tagsBipadas, dict_lotes: {}, df_esperados_json: esperados, usuario,
    })) as Record<string, unknown>,
    onSuccess: (data: Record<string, unknown>) => {
      toast.success((data.mensagem as string) ?? 'Recebimento processado!')
      qc.invalidateQueries({ queryKey: ['doca-esperados'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const origens = origensData?.origens ?? []

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <ArrowDownToLine className="h-4 w-4 text-primary" /> Recebimento em Doca
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!polo && <Alert><AlertDescription>Selecione um polo para ver as origens disponíveis.</AlertDescription></Alert>}
        {polo && (
          <div className="space-y-1.5">
            <Label>Origem</Label>
            <Select value={origem} onValueChange={setOrigem}>
              <SelectTrigger className="w-64"><SelectValue placeholder="Selecione a origem…" /></SelectTrigger>
              <SelectContent>{origens.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        )}
        {origem && (
          <DataTable
            columns={[
              { accessorKey: 'codigo', header: 'Código' },
              { accessorKey: 'descricao', header: 'Descrição' },
              { accessorKey: 'num_tag', header: 'TAG' },
              { accessorKey: 'quantidade', header: 'Qtd Esperada', size: 80 },
            ] as ColumnDef<Record<string, unknown>>[]}
            data={esperados as Record<string, unknown>[]}
            emptyMessage="Nenhum item esperado desta origem."
          />
        )}
        {origem && esperados.length > 0 && (
          <Button size="sm" onClick={() => receberMut.mutate({})} disabled={receberMut.isPending}>
            {receberMut.isPending ? 'Processando…' : 'Confirmar Recebimento'}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
