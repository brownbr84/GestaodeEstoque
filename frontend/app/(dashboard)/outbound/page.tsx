'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Header } from '@/components/layout/Header'
import { DataTable } from '@/components/data-table/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { outbound as outboundApi, polos as polosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { ArrowUpFromLine, Truck, X } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>

function statusBadge(status: string) {
  const m: Record<string, 'warning' | 'success' | 'secondary'> = { 'Pendente': 'warning', 'Despachado': 'success', 'Cancelado': 'secondary' }
  return <Badge variant={m[status] ?? 'secondary'}>{status}</Badge>
}

export default function OutboundPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [polo, setPolo] = useState('')
  const [cancelModal, setCancelModal] = useState<Item | null>(null)
  const [motivoCancel, setMotivoCancel] = useState('')

  const { data: polosData } = useQuery({ queryKey: ['polos'], queryFn: polosApi.emUso })
  const { data: pedidos = [], isLoading } = useQuery({
    queryKey: ['outbound-pedidos', polo],
    queryFn: () => outboundApi.pedidos(polo),
    enabled: !!polo,
  })
  const { data: transito = [] } = useQuery({
    queryKey: ['outbound-transito', polo],
    queryFn: () => outboundApi.transito(polo),
    enabled: !!polo,
  })

  const polos = polosData?.polos ?? []

  const cancelarMut = useMutation({
    mutationFn: () => outboundApi.cancelar({
      true_id: cancelModal!.id, req_id: cancelModal!.req_id, motivo: motivoCancel, usuario: user?.usuario ?? '',
    }),
    onSuccess: () => {
      toast.success('Pedido cancelado.')
      qc.invalidateQueries({ queryKey: ['outbound-pedidos'] })
      setCancelModal(null)
      setMotivoCancel('')
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const pedidosCols: ColumnDef<Item>[] = [
    { accessorKey: 'req_id', header: 'REQ', size: 70, cell: ({ row }) => `REQ-${String(row.original.req_id ?? '').padStart(4, '0')}` },
    { accessorKey: 'solicitante', header: 'Solicitante' },
    { accessorKey: 'destino_projeto', header: 'Destino' },
    { accessorKey: 'data_solicitacao', header: 'Data', size: 110 },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => statusBadge(row.original.status as string) },
    {
      id: 'actions', header: '', size: 120,
      cell: ({ row }) => row.original.status === 'Pendente' ? (
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" className="text-xs text-destructive" onClick={() => { setCancelModal(row.original); setMotivoCancel('') }}>
            <X className="h-3.5 w-3.5 mr-1" /> Cancelar
          </Button>
        </div>
      ) : null,
    },
  ]

  const transitoCols: ColumnDef<Item>[] = [
    { accessorKey: 'codigo', header: 'Código' },
    { accessorKey: 'descricao', header: 'Descrição' },
    { accessorKey: 'num_tag', header: 'TAG' },
    { accessorKey: 'destino_projeto', header: 'Destino' },
    { accessorKey: 'data_movimentacao', header: 'Data Saída', size: 110 },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Outbound" subtitle="Gestão de pedidos e despacho" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="w-56">
          <Select value={polo} onValueChange={setPolo}>
            <SelectTrigger className="h-8"><SelectValue placeholder="Selecione o polo…" /></SelectTrigger>
            <SelectContent>{polos.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
          </Select>
        </div>

        <Tabs defaultValue="pedidos">
          <TabsList>
            <TabsTrigger value="pedidos" className="text-xs flex items-center gap-1">
              <ArrowUpFromLine className="h-3.5 w-3.5" /> Fila de Pedidos
              {(pedidos as Item[]).filter(p => p.status === 'Pendente').length > 0 && (
                <Badge variant="warning" className="ml-1 text-[10px]">{(pedidos as Item[]).filter(p => p.status === 'Pendente').length}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="transito" className="text-xs flex items-center gap-1">
              <Truck className="h-3.5 w-3.5" /> Em Trânsito ({transito.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pedidos">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Pedidos — {polo || 'Selecione um polo'}</CardTitle>
              </CardHeader>
              <CardContent>
                {!polo ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">Selecione um polo para ver os pedidos.</p>
                ) : (
                  <DataTable columns={pedidosCols} data={pedidos as Item[]} searchKey="solicitante" searchPlaceholder="Filtrar por solicitante…" />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="transito">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Itens em Trânsito — {polo}</CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable columns={transitoCols} data={transito as Item[]} searchKey="descricao" />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      <Dialog open={!!cancelModal} onOpenChange={v => { if (!v) setCancelModal(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancelar Pedido REQ-{String(cancelModal?.req_id ?? '').padStart(4, '0')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Motivo do Cancelamento <span className="text-destructive">*</span></Label>
              <Textarea value={motivoCancel} onChange={e => setMotivoCancel(e.target.value)} rows={3} placeholder="Descreva o motivo…" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelModal(null)}>Voltar</Button>
            <Button variant="destructive" onClick={() => cancelarMut.mutate()} disabled={cancelarMut.isPending || !motivoCancel}>
              {cancelarMut.isPending ? 'Cancelando…' : 'Confirmar Cancelamento'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
