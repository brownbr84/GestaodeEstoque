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
import { fiscal as fiscalApi, parceiros as parceiroApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { formatDateTime } from '@/lib/utils'
import { FileText, CheckCircle, XCircle, Plus, Download } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Rascunho = {
  id: number
  tipo_operacao: string
  status: string
  criado_por: string
  criado_em: string
  numero_nf?: string
  chave_acesso?: string
  [key: string]: unknown
}

function statusBadge(s: string) {
  const m: Record<string, 'warning' | 'success' | 'destructive' | 'secondary'> = {
    PENDENTE: 'warning', EMITIDA: 'success', CANCELADA: 'destructive', REJEITADA: 'destructive',
  }
  return <Badge variant={m[s] ?? 'secondary'}>{s}</Badge>
}

const TAB_STATUSES = ['PENDENTE', 'EMITIDA', 'CANCELADA']

interface ItemNF { codigo: string; descricao: string; ncm: string; quantidade: number; valor_unitario: number }

export default function FiscalPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [tabStatus, setTabStatus] = useState('PENDENTE')
  const [modalNovo, setModalNovo] = useState(false)
  const [modalAprovar, setModalAprovar] = useState<Rascunho | null>(null)
  const [tipoOp, setTipoOp] = useState('saida')
  const [parcId, setParcId] = useState('')
  const [itens, setItens] = useState<ItemNF[]>([{ codigo: '', descricao: '', ncm: '', quantidade: 1, valor_unitario: 0 }])
  const [aprInfo, setAprInfo] = useState({ chave_acesso: '', protocolo_sefaz: '', numero_nf: '' })

  const { data: rascunhos = [], isLoading } = useQuery({
    queryKey: ['fiscal-rascunhos', tabStatus],
    queryFn: () => fiscalApi.rascunhos(tabStatus) as Promise<Rascunho[]>,
    refetchInterval: 30_000,
  })

  const { data: parcs = [] } = useQuery({
    queryKey: ['parceiros', 'todos'],
    queryFn: () => parceiroApi.listar(),
  })

  const prepararMut = useMutation<Record<string, unknown>>({
    mutationFn: async () => {
      const parc = (parcs as Rascunho[]).find(p => String(p.id) === parcId)
      const result = await fiscalApi.preparar({
        tipo_operacao: tipoOp,
        dados_mercadoria: itens,
        dados_destinatario_remetente: parc ? {
          cnpj: parc.cnpj, nome: parc.razao_social, logradouro: parc.logradouro,
          municipio: parc.municipio, uf: parc.uf, cep: parc.cep,
        } : {},
      })
      return result as Record<string, unknown>
    },
    onSuccess: (data: Record<string, unknown>) => {
      toast.success(`Rascunho #${data.rascunho_id} criado — aguardando aprovação.`)
      if (data.aviso) toast.warning(data.aviso as string)
      qc.invalidateQueries({ queryKey: ['fiscal-rascunhos'] })
      setModalNovo(false)
      setItens([{ codigo: '', descricao: '', ncm: '', quantidade: 1, valor_unitario: 0 }])
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const emitirMut = useMutation({
    mutationFn: () => fiscalApi.emitir({
      rascunho_id: modalAprovar!.id,
      ...aprInfo,
    }),
    onSuccess: () => {
      toast.success('NF-e marcada como EMITIDA!')
      qc.invalidateQueries({ queryKey: ['fiscal-rascunhos'] })
      setModalAprovar(null)
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const cancelarMut = useMutation({
    mutationFn: (id: number) => fiscalApi.cancelar({ rascunho_id: id, motivo: 'Cancelado pelo usuário' }),
    onSuccess: () => { toast.success('Rascunho cancelado.'); qc.invalidateQueries({ queryKey: ['fiscal-rascunhos'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  function addItem() { setItens(prev => [...prev, { codigo: '', descricao: '', ncm: '', quantidade: 1, valor_unitario: 0 }]) }
  function removeItem(i: number) { setItens(prev => prev.filter((_, idx) => idx !== i)) }
  function setItem(i: number, k: keyof ItemNF, v: string | number) {
    setItens(prev => prev.map((item, idx) => idx === i ? { ...item, [k]: v } : item))
  }

  const canEmit = user?.perfil === 'Admin' || user?.perfil === 'Gestor'

  const cols: ColumnDef<Rascunho>[] = [
    { accessorKey: 'id', header: '#', size: 50 },
    { accessorKey: 'tipo_operacao', header: 'Tipo', size: 80 },
    { accessorKey: 'criado_por', header: 'Criado por' },
    { accessorKey: 'criado_em', header: 'Data', cell: ({ row }) => formatDateTime(row.original.criado_em as string) },
    { accessorKey: 'numero_nf', header: 'Nº NF', cell: ({ row }) => row.original.numero_nf || '—' },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => statusBadge(row.original.status as string) },
    {
      id: 'actions', header: '', size: 160,
      cell: ({ row }) => (
        <div className="flex gap-1">
          {row.original.status === 'PENDENTE' && canEmit && (
            <Button size="sm" variant="ghost" className="text-xs text-emerald-400" onClick={() => { setModalAprovar(row.original); setAprInfo({ chave_acesso: '', protocolo_sefaz: '', numero_nf: '' }) }}>
              <CheckCircle className="h-3.5 w-3.5 mr-1" /> Emitir
            </Button>
          )}
          {row.original.status === 'PENDENTE' && (
            <Button size="sm" variant="ghost" className="text-xs text-destructive" onClick={() => { if (confirm('Cancelar este rascunho?')) cancelarMut.mutate(row.original.id as number) }}>
              <XCircle className="h-3.5 w-3.5 mr-1" /> Cancelar
            </Button>
          )}
          {row.original.status === 'EMITIDA' && (
            <Button size="sm" variant="ghost" className="text-xs" onClick={async () => {
              const res = await fiscalApi.danfePdf(row.original.id as number)
              if (res.ok) {
                const blob = await res.blob()
                const url = URL.createObjectURL(blob)
                window.open(url, '_blank')
              } else { toast.error('Falha ao baixar DANFE') }
            }}>
              <Download className="h-3.5 w-3.5 mr-1" /> DANFE
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Fiscal — NF-e" subtitle="Gestão de notas fiscais com trava de segurança" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="flex justify-between items-center">
          <Alert className="flex-1 mr-4 py-2">
            <AlertDescription className="text-xs">
              <strong>Trava de segurança ativa:</strong> toda NF-e passa por rascunho (PENDENTE) e requer aprovação de Admin/Gestor antes da emissão.
            </AlertDescription>
          </Alert>
          <Button size="sm" onClick={() => setModalNovo(true)}>
            <Plus className="h-4 w-4 mr-1" /> Nova NF-e
          </Button>
        </div>

        <Tabs value={tabStatus} onValueChange={setTabStatus}>
          <TabsList>
            {TAB_STATUSES.map(s => (
              <TabsTrigger key={s} value={s} className="text-xs">{s}</TabsTrigger>
            ))}
          </TabsList>
          {TAB_STATUSES.map(s => (
            <TabsContent key={s} value={s}>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileText className="h-4 w-4 text-primary" /> Rascunhos — {s}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable columns={cols} data={rascunhos} emptyMessage={`Nenhuma NF-e com status ${s}.`} />
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      </main>

      {/* Modal Novo NF-e */}
      <Dialog open={modalNovo} onOpenChange={setModalNovo}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Preparar Nova NF-e</DialogTitle></DialogHeader>
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Tipo de Operação</Label>
                <Select value={tipoOp} onValueChange={setTipoOp}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="saida">Saída</SelectItem>
                    <SelectItem value="entrada">Entrada</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Destinatário / Remetente</Label>
                <Select value={parcId} onValueChange={setParcId}>
                  <SelectTrigger><SelectValue placeholder="Selecione o parceiro…" /></SelectTrigger>
                  <SelectContent>
                    {(parcs as Rascunho[]).map(p => (
                      <SelectItem key={String(p.id)} value={String(p.id)}>{p.razao_social as string}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Itens da NF-e</Label>
                <Button size="sm" variant="outline" onClick={addItem} type="button">+ Item</Button>
              </div>
              <div className="space-y-2">
                {itens.map((item, i) => (
                  <div key={i} className="grid grid-cols-5 gap-2 p-3 bg-muted/30 rounded-lg">
                    <div className="space-y-1">
                      <Label className="text-xs">Código</Label>
                      <Input value={item.codigo} onChange={e => setItem(i, 'codigo', e.target.value)} className="h-7 text-xs" />
                    </div>
                    <div className="col-span-2 space-y-1">
                      <Label className="text-xs">Descrição</Label>
                      <Input value={item.descricao} onChange={e => setItem(i, 'descricao', e.target.value)} className="h-7 text-xs" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">NCM</Label>
                      <Input value={item.ncm} onChange={e => setItem(i, 'ncm', e.target.value)} className="h-7 text-xs" maxLength={8} />
                    </div>
                    <div className="grid grid-cols-2 gap-1">
                      <div className="space-y-1">
                        <Label className="text-xs">Qtd</Label>
                        <Input type="number" min="1" value={item.quantidade} onChange={e => setItem(i, 'quantidade', parseInt(e.target.value) || 1)} className="h-7 text-xs" />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Val. Unit.</Label>
                        <Input type="number" step="0.01" min="0" value={item.valor_unitario} onChange={e => setItem(i, 'valor_unitario', parseFloat(e.target.value) || 0)} className="h-7 text-xs" />
                      </div>
                    </div>
                    {itens.length > 1 && (
                      <Button size="sm" variant="ghost" className="text-destructive col-span-5 h-6 text-xs" onClick={() => removeItem(i)}>Remover item</Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalNovo(false)}>Cancelar</Button>
            <Button onClick={() => prepararMut.mutate()} disabled={prepararMut.isPending}>
              {prepararMut.isPending ? 'Preparando…' : 'Criar Rascunho'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Aprovar/Emitir */}
      <Dialog open={!!modalAprovar} onOpenChange={v => { if (!v) setModalAprovar(null) }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Emitir NF-e — Rascunho #{String(modalAprovar?.id ?? '')}</DialogTitle></DialogHeader>
          <Alert variant="warning">
            <AlertDescription className="text-xs">Esta ação marcará a NF-e como EMITIDA no sistema. Certifique-se de que a emissão foi aprovada pela SEFAZ antes de confirmar.</AlertDescription>
          </Alert>
          <div className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label>Chave de Acesso (chNFe)</Label>
              <Input value={aprInfo.chave_acesso} onChange={e => setAprInfo(p => ({ ...p, chave_acesso: e.target.value }))} placeholder="44 dígitos" />
            </div>
            <div className="space-y-1.5">
              <Label>Protocolo SEFAZ</Label>
              <Input value={aprInfo.protocolo_sefaz} onChange={e => setAprInfo(p => ({ ...p, protocolo_sefaz: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Número da NF</Label>
              <Input value={aprInfo.numero_nf} onChange={e => setAprInfo(p => ({ ...p, numero_nf: e.target.value }))} placeholder="000000001" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalAprovar(null)}>Cancelar</Button>
            <Button onClick={() => emitirMut.mutate()} disabled={emitirMut.isPending}>
              {emitirMut.isPending ? 'Emitindo…' : 'Confirmar Emissão'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
