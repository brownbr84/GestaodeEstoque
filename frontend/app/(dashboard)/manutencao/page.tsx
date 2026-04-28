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
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { manutencao as manutApi, produtos as produtosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Wrench, Plus, Mail } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>

function osBadge(status: string) {
  const m: Record<string, 'warning' | 'success' | 'destructive' | 'secondary' | 'info'> = {
    'Aberta': 'warning', 'Em Orçamento': 'info' as never, 'Aprovada': 'info' as never,
    'Em Reparo': 'info' as never, 'Concluída': 'success', 'Cancelada': 'destructive',
  }
  return <Badge variant={m[status] ?? 'secondary'}>{status}</Badge>
}

export default function ManutencaoPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [modalAbrir, setModalAbrir] = useState(false)
  const [modalOrc, setModalOrc] = useState<Item | null>(null)
  const [formAbrir, setFormAbrir] = useState({ codigo: '', motivo: '' })
  const [formOrc, setFormOrc] = useState({ diagnostico: '', custo: '', mecanico: '', empresa: '', num_orcamento: '' })
  const [decisao, setDecisao] = useState<string | null>(null)
  const [orcAprovar, setOrcAprovar] = useState<Item | null>(null)

  const { data: ativos = [] } = useQuery({ queryKey: ['manut-ativos'], queryFn: manutApi.ativos })
  const { data: abertas = [] } = useQuery({ queryKey: ['manut-abertas'], queryFn: manutApi.abertas })
  const { data: aprovacao = [] } = useQuery({ queryKey: ['manut-aprovacao'], queryFn: manutApi.aprovacao })
  const { data: execucao = [] } = useQuery({ queryKey: ['manut-execucao'], queryFn: manutApi.execucao })
  const { data: catalogo = [] } = useQuery({ queryKey: ['catalogo'], queryFn: produtosApi.catalogo })

  const abrirMut = useMutation<Record<string, unknown>>({
    mutationFn: async () => (await manutApi.abrir({
      ferramenta_id: (ativos as Item[]).find(a => a.codigo === formAbrir.codigo)?.id ?? 0,
      codigo: formAbrir.codigo, motivo: formAbrir.motivo,
      solicitante: user?.nome ?? '', usuario: user?.usuario ?? '',
    })) as Record<string, unknown>,
    onSuccess: (data: Record<string, unknown>) => {
      toast.success((data.mensagem as string) || 'OS aberta!')
      qc.invalidateQueries({ queryKey: ['manut-abertas'] })
      setModalAbrir(false)
      setFormAbrir({ codigo: '', motivo: '' })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const orcMut = useMutation({
    mutationFn: () => manutApi.orcamento({
      ordem_id: modalOrc!.id, diagnostico: formOrc.diagnostico,
      custo: parseFloat(formOrc.custo) || 0, mecanico: formOrc.mecanico,
      empresa: formOrc.empresa, num_orcamento: formOrc.num_orcamento, usuario: user?.usuario ?? '',
    }),
    onSuccess: () => { toast.success('Orçamento lançado!'); qc.invalidateQueries({ queryKey: ['manut-abertas', 'manut-aprovacao'] }); setModalOrc(null) },
    onError: (err: Error) => toast.error(err.message),
  })

  const aprovarMut = useMutation({
    mutationFn: () => manutApi.aprovar((orcAprovar!.id as number), decisao!, user?.usuario ?? ''),
    onSuccess: () => {
      toast.success(decisao === 'aprovar' ? 'OS aprovada para reparo!' : 'OS cancelada.')
      qc.invalidateQueries({ queryKey: ['manut-aprovacao', 'manut-execucao'] })
      setOrcAprovar(null); setDecisao(null)
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const reenviarMut = useMutation({
    mutationFn: (os_id: number) => manutApi.reenviarEmail(os_id),
    onSuccess: () => toast.success('E-mail reenviado!'),
    onError: (err: Error) => toast.error(err.message),
  })

  const finalizarMut = useMutation({
    mutationFn: (item: Item) => manutApi.finalizar({ ordem_id: item.id, ferramenta_id: item.ferramenta_id ?? 0, destino: item.localizacao ?? '', usuario: user?.usuario ?? '' }),
    onSuccess: () => { toast.success('OS finalizada!'); qc.invalidateQueries({ queryKey: ['manut-execucao', 'manut-abertas'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  const abertasCols: ColumnDef<Item>[] = [
    { accessorKey: 'id', header: 'OS', size: 60, cell: ({ row }) => `OS-${row.original.id}` },
    { accessorKey: 'codigo_ferramenta', header: 'Código' },
    { accessorKey: 'motivo_falha', header: 'Motivo' },
    { accessorKey: 'solicitante', header: 'Solicitante' },
    { accessorKey: 'data_entrada', header: 'Abertura', cell: ({ row }) => formatDateTime(row.original.data_entrada as string) },
    { accessorKey: 'status_ordem', header: 'Status', cell: ({ row }) => osBadge(row.original.status_ordem as string) },
    {
      id: 'actions', header: '', size: 150,
      cell: ({ row }) => (
        <div className="flex gap-1">
          {row.original.status_ordem === 'Aberta' && (
            <Button size="sm" variant="ghost" className="text-xs" onClick={() => { setModalOrc(row.original); setFormOrc({ diagnostico: '', custo: '', mecanico: '', empresa: '', num_orcamento: '' }) }}>Orçamento</Button>
          )}
          <Button size="sm" variant="ghost" className="text-xs" onClick={() => reenviarMut.mutate(row.original.id as number)}>
            <Mail className="h-3 w-3" />
          </Button>
        </div>
      ),
    },
  ]

  const aprovacaoCols: ColumnDef<Item>[] = [
    { accessorKey: 'id', header: 'OS', size: 60, cell: ({ row }) => `OS-${row.original.id}` },
    { accessorKey: 'codigo_ferramenta', header: 'Código' },
    { accessorKey: 'diagnostico', header: 'Diagnóstico' },
    { accessorKey: 'custo_reparo', header: 'Custo', cell: ({ row }) => formatCurrency(row.original.custo_reparo as number) },
    { accessorKey: 'empresa_reparo', header: 'Empresa' },
    {
      id: 'actions', header: '', size: 160,
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" className="text-xs text-emerald-400" onClick={() => { setOrcAprovar(row.original); setDecisao('aprovar') }}>Aprovar</Button>
          <Button size="sm" variant="ghost" className="text-xs text-destructive" onClick={() => { setOrcAprovar(row.original); setDecisao('cancelar') }}>Cancelar</Button>
        </div>
      ),
    },
  ]

  const execucaoCols: ColumnDef<Item>[] = [
    { accessorKey: 'id', header: 'OS', size: 60, cell: ({ row }) => `OS-${row.original.id}` },
    { accessorKey: 'codigo_ferramenta', header: 'Código' },
    { accessorKey: 'mecanico_responsavel', header: 'Mecânico' },
    { accessorKey: 'empresa_reparo', header: 'Empresa' },
    { accessorKey: 'status_ordem', header: 'Status', cell: ({ row }) => osBadge(row.original.status_ordem as string) },
    {
      id: 'actions', header: '', size: 100,
      cell: ({ row }) => (
        <Button size="sm" variant="ghost" className="text-xs text-emerald-400" onClick={() => finalizarMut.mutate(row.original)} disabled={finalizarMut.isPending}>Finalizar</Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Manutenção" subtitle="Gestão de ordens de serviço" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setModalAbrir(true)}>
            <Plus className="h-4 w-4 mr-1" /> Abrir OS
          </Button>
        </div>

        <Tabs defaultValue="abertas">
          <TabsList>
            <TabsTrigger value="abertas" className="text-xs">Abertas ({abertas.length})</TabsTrigger>
            <TabsTrigger value="aprovacao" className="text-xs">
              Aprovação
              {aprovacao.length > 0 && <Badge variant="warning" className="ml-1 text-[10px]">{aprovacao.length}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="execucao" className="text-xs">Em Reparo ({execucao.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="abertas">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Wrench className="h-4 w-4 text-primary" />OS Abertas</CardTitle></CardHeader>
              <CardContent><DataTable columns={abertasCols} data={abertas} searchKey="codigo_ferramenta" /></CardContent></Card>
          </TabsContent>
          <TabsContent value="aprovacao">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Aguardando Aprovação</CardTitle></CardHeader>
              <CardContent><DataTable columns={aprovacaoCols} data={aprovacao} /></CardContent></Card>
          </TabsContent>
          <TabsContent value="execucao">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Em Reparo</CardTitle></CardHeader>
              <CardContent><DataTable columns={execucaoCols} data={execucao} /></CardContent></Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* Modal Abrir OS */}
      <Dialog open={modalAbrir} onOpenChange={setModalAbrir}>
        <DialogContent>
          <DialogHeader><DialogTitle>Abrir Ordem de Serviço</DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label>Código do Equipamento</Label>
              <Select value={formAbrir.codigo} onValueChange={v => setFormAbrir(p => ({ ...p, codigo: v }))}>
                <SelectTrigger><SelectValue placeholder="Selecione…" /></SelectTrigger>
                <SelectContent>
                  {(ativos as Item[]).map(a => <SelectItem key={String(a.id)} value={a.codigo as string}>{a.codigo as string} — {a.descricao as string}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Motivo da Falha</Label>
              <Textarea value={formAbrir.motivo} onChange={e => setFormAbrir(p => ({ ...p, motivo: e.target.value }))} rows={3} placeholder="Descreva o problema…" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalAbrir(false)}>Cancelar</Button>
            <Button onClick={() => abrirMut.mutate()} disabled={abrirMut.isPending || !formAbrir.codigo || !formAbrir.motivo}>
              {abrirMut.isPending ? 'Abrindo…' : 'Abrir OS'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Orçamento */}
      <Dialog open={!!modalOrc} onOpenChange={v => { if (!v) setModalOrc(null) }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Lançar Orçamento — OS-{String(modalOrc?.id ?? '')}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="col-span-2 space-y-1.5"><Label>Diagnóstico</Label><Textarea value={formOrc.diagnostico} onChange={e => setFormOrc(p => ({ ...p, diagnostico: e.target.value }))} rows={2} /></div>
            <div className="space-y-1.5"><Label>Custo (R$)</Label><Input type="number" step="0.01" value={formOrc.custo} onChange={e => setFormOrc(p => ({ ...p, custo: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>Nº Orçamento</Label><Input value={formOrc.num_orcamento} onChange={e => setFormOrc(p => ({ ...p, num_orcamento: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>Mecânico</Label><Input value={formOrc.mecanico} onChange={e => setFormOrc(p => ({ ...p, mecanico: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>Empresa</Label><Input value={formOrc.empresa} onChange={e => setFormOrc(p => ({ ...p, empresa: e.target.value }))} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOrc(null)}>Cancelar</Button>
            <Button onClick={() => orcMut.mutate()} disabled={orcMut.isPending}>{orcMut.isPending ? 'Salvando…' : 'Salvar Orçamento'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Aprovar */}
      <Dialog open={!!orcAprovar} onOpenChange={v => { if (!v) { setOrcAprovar(null); setDecisao(null) } }}>
        <DialogContent>
          <DialogHeader><DialogTitle>{decisao === 'aprovar' ? 'Aprovar' : 'Cancelar'} OS-{String(orcAprovar?.id ?? '')}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">
            {decisao === 'aprovar'
              ? 'Confirmar aprovação do orçamento e enviar para reparo?'
              : 'Confirmar cancelamento desta OS?'}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOrcAprovar(null)}>Voltar</Button>
            <Button variant={decisao === 'aprovar' ? 'default' : 'destructive'} onClick={() => aprovarMut.mutate()} disabled={aprovarMut.isPending}>
              {aprovarMut.isPending ? '…' : decisao === 'aprovar' ? 'Confirmar Aprovação' : 'Cancelar OS'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
