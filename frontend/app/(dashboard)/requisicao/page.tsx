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
import { requisicao as reqApi, polos as polosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { formatDateTime } from '@/lib/utils'
import { ShoppingCart, Plus, Trash2, Mail } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Item = Record<string, unknown>
type CartItem = { codigo_produto: string; descricao_produto: string; quantidade_solicitada: number }

function statusBadge(s: string) {
  const m: Record<string, 'warning' | 'success' | 'destructive' | 'secondary'> = {
    'Pendente': 'warning', 'Aprovado': 'success', 'Cancelado': 'destructive', 'Despachado': 'secondary',
  }
  return <Badge variant={m[s] ?? 'secondary'}>{s}</Badge>
}

export default function RequisicaoPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [tab, setTab] = useState('historico')
  const [modalNova, setModalNova] = useState(false)
  const [poloAlvo, setPoloAlvo] = useState('')
  const [projeto, setProjeto] = useState('')
  const [carrinho, setCarrinho] = useState<CartItem[]>([])
  const [catalogo, setCatalogo] = useState<Item[]>([])
  const [loadingCat, setLoadingCat] = useState(false)

  const { data: polosData } = useQuery({ queryKey: ['polos'], queryFn: polosApi.emUso })
  const { data: historico = [] } = useQuery({
    queryKey: ['req-historico', user?.usuario],
    queryFn: () => reqApi.historico(user?.usuario ?? ''),
    enabled: !!user,
  })

  const polos = polosData?.polos ?? []

  async function buscarCatalogo() {
    if (!poloAlvo) { toast.error('Selecione o polo'); return }
    setLoadingCat(true)
    try {
      const data = await reqApi.catalogo({ polo_alvo: poloAlvo, carrinho_req: [], tipo_filtro: 'Todos' }) as Item[]
      setCatalogo(data)
    } catch (err: unknown) { toast.error((err as Error).message) } finally { setLoadingCat(false) }
  }

  function addToCart(item: Item) {
    const exist = carrinho.find(c => c.codigo_produto === item.codigo)
    if (exist) {
      setCarrinho(prev => prev.map(c => c.codigo_produto === item.codigo ? { ...c, quantidade_solicitada: c.quantidade_solicitada + 1 } : c))
    } else {
      setCarrinho(prev => [...prev, { codigo_produto: item.codigo as string, descricao_produto: item.descricao as string, quantidade_solicitada: 1 }])
    }
  }

  const salvarMut = useMutation<Record<string, unknown>>({
    mutationFn: async () => (await reqApi.salvar({ polo_alvo: poloAlvo, projeto, solicitante: user?.nome ?? '', df_carrinho: carrinho })) as Record<string, unknown>,
    onSuccess: (data: Record<string, unknown>) => {
      toast.success((data.mensagem as string) || 'Requisição criada!')
      qc.invalidateQueries({ queryKey: ['req-historico'] })
      setModalNova(false); setCarrinho([]); setCatalogo([]); setPoloAlvo(''); setProjeto('')
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const reenviarMut = useMutation({
    mutationFn: (req_id: number) => reqApi.reenviarEmail(req_id),
    onSuccess: () => toast.success('E-mail reenviado!'),
    onError: (err: Error) => toast.error(err.message),
  })

  const historicoCols: ColumnDef<Item>[] = [
    { accessorKey: 'id', header: 'REQ', size: 70, cell: ({ row }) => `REQ-${String(row.original.id).padStart(4, '0')}` },
    { accessorKey: 'destino_projeto', header: 'Projeto' },
    { accessorKey: 'polo_origem', header: 'Polo' },
    { accessorKey: 'data_solicitacao', header: 'Data', cell: ({ row }) => formatDateTime(row.original.data_solicitacao as string) },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => statusBadge(row.original.status as string) },
    {
      id: 'email', header: '', size: 60,
      cell: ({ row }) => (
        <Button size="sm" variant="ghost" title="Reenviar e-mail" onClick={() => reenviarMut.mutate(row.original.id as number)}>
          <Mail className="h-3.5 w-3.5" />
        </Button>
      ),
    },
  ]

  const catalogoCols: ColumnDef<Item>[] = [
    { accessorKey: 'codigo', header: 'Código', size: 100 },
    { accessorKey: 'descricao', header: 'Descrição' },
    { accessorKey: 'tipo_material', header: 'Tipo', size: 80 },
    { accessorKey: 'quantidade', header: 'Disp.', size: 60 },
    {
      id: 'add', header: '', size: 80,
      cell: ({ row }) => (
        <Button size="sm" variant="ghost" className="text-xs" onClick={() => addToCart(row.original)}>
          <Plus className="h-3.5 w-3.5 mr-1" /> Add
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Requisição" subtitle="Solicitação de materiais e produtos" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setModalNova(true)}>
            <Plus className="h-4 w-4 mr-1" /> Nova Requisição
          </Button>
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="historico" className="text-xs">
              <ShoppingCart className="h-3.5 w-3.5 mr-1" /> Histórico ({historico.length})
            </TabsTrigger>
          </TabsList>
          <TabsContent value="historico">
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Minhas Requisições</CardTitle></CardHeader>
              <CardContent><DataTable columns={historicoCols} data={historico} searchKey="destino_projeto" /></CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      <Dialog open={modalNova} onOpenChange={v => { setModalNova(v); if (!v) { setCarrinho([]); setCatalogo([]) } }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Nova Requisição</DialogTitle></DialogHeader>
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Polo de Destino</Label>
                <Select value={poloAlvo} onValueChange={setPoloAlvo}>
                  <SelectTrigger><SelectValue placeholder="Selecione…" /></SelectTrigger>
                  <SelectContent>{polos.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Projeto / Destino</Label>
                <Input value={projeto} onChange={e => setProjeto(e.target.value)} placeholder="Nome do projeto" />
              </div>
            </div>

            <Button size="sm" variant="outline" onClick={buscarCatalogo} disabled={loadingCat || !poloAlvo}>
              {loadingCat ? 'Buscando…' : 'Buscar Catálogo'}
            </Button>

            {catalogo.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Catálogo Disponível</p>
                <DataTable columns={catalogoCols} data={catalogo} searchKey="descricao" searchPlaceholder="Filtrar produto…" pageSize={8} />
              </div>
            )}

            {carrinho.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Carrinho ({carrinho.length})</p>
                <div className="space-y-2">
                  {carrinho.map((c, i) => (
                    <div key={i} className="flex items-center gap-3 bg-muted/30 rounded-lg px-3 py-2">
                      <span className="flex-1 text-xs">{c.codigo_produto} — {c.descricao_produto}</span>
                      <Input
                        type="number" min="1" value={c.quantidade_solicitada}
                        onChange={e => setCarrinho(prev => prev.map((it, idx) => idx === i ? { ...it, quantidade_solicitada: parseInt(e.target.value) || 1 } : it))}
                        className="w-16 h-7 text-xs"
                      />
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => setCarrinho(prev => prev.filter((_, idx) => idx !== i))}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalNova(false)}>Cancelar</Button>
            <Button onClick={() => salvarMut.mutate()} disabled={salvarMut.isPending || carrinho.length === 0 || !projeto}>
              {salvarMut.isPending ? 'Enviando…' : 'Enviar Requisição'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
