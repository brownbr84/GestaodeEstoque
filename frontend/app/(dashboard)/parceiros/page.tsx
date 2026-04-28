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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { parceiros as parceiroApi } from '@/lib/api'
import { formatCNPJ } from '@/lib/utils'
import { Plus, Search, Building2 } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

interface PForm {
  tipo: string; razao_social: string; nome_fantasia: string; cnpj: string
  ie: string; cep: string; logradouro: string; numero: string; complemento: string
  bairro: string; municipio: string; uf: string; telefone: string; email_contato: string
  regime_tributario: string; contribuinte_icms: string; status: string
}
const EMPTY: PForm = {
  tipo: 'CLIENTE', razao_social: '', nome_fantasia: '', cnpj: '', ie: '',
  cep: '', logradouro: '', numero: '', complemento: '', bairro: '', municipio: '', uf: '',
  telefone: '', email_contato: '', regime_tributario: 'REGIME_NORMAL', contribuinte_icms: '1', status: 'ATIVO',
}

type Parceiro = Record<string, unknown>

export default function ParceirosPage() {
  const qc = useQueryClient()
  const [tipoFiltro, setTipoFiltro] = useState('todos')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Parceiro | null>(null)
  const [form, setForm] = useState<PForm>(EMPTY)
  const [loadingCnpj, setLoadingCnpj] = useState(false)

  const { data: lista = [], isLoading } = useQuery({
    queryKey: ['parceiros', tipoFiltro],
    queryFn: () => parceiroApi.listar(tipoFiltro === 'todos' ? undefined : tipoFiltro.toUpperCase()),
  })

  const saveMut = useMutation({
    mutationFn: async () => {
      const data = { ...form, contribuinte_icms: parseInt(form.contribuinte_icms) }
      if (editing) return parceiroApi.atualizar(editing.id as number, data)
      return parceiroApi.criar(data)
    },
    onSuccess: () => {
      toast.success(editing ? 'Parceiro atualizado!' : 'Parceiro cadastrado!')
      qc.invalidateQueries({ queryKey: ['parceiros'] })
      setOpen(false)
      setEditing(null)
      setForm(EMPTY)
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const delMut = useMutation({
    mutationFn: (id: number) => parceiroApi.excluir(id),
    onSuccess: () => { toast.success('Parceiro removido.'); qc.invalidateQueries({ queryKey: ['parceiros'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  const consultarCnpj = useMutation({
    mutationFn: (id: number) => parceiroApi.consultarCNPJ(id),
    onSuccess: () => { toast.success('CNPJ consultado!'); qc.invalidateQueries({ queryKey: ['parceiros'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  function openNew() { setEditing(null); setForm(EMPTY); setOpen(true) }
  function openEdit(p: Parceiro) {
    setEditing(p)
    setForm({
      tipo: (p.tipo as string) ?? 'CLIENTE', razao_social: (p.razao_social as string) ?? '',
      nome_fantasia: (p.nome_fantasia as string) ?? '', cnpj: (p.cnpj as string) ?? '',
      ie: (p.ie as string) ?? '', cep: (p.cep as string) ?? '', logradouro: (p.logradouro as string) ?? '',
      numero: (p.numero as string) ?? '', complemento: (p.complemento as string) ?? '',
      bairro: (p.bairro as string) ?? '', municipio: (p.municipio as string) ?? '', uf: (p.uf as string) ?? '',
      telefone: (p.telefone as string) ?? '', email_contato: (p.email_contato as string) ?? '',
      regime_tributario: (p.regime_tributario as string) ?? 'REGIME_NORMAL',
      contribuinte_icms: String(p.contribuinte_icms ?? 1), status: (p.status as string) ?? 'ATIVO',
    })
    setOpen(true)
  }
  function set(k: keyof PForm, v: string) { setForm(prev => ({ ...prev, [k]: v })) }

  async function buscarCEP() {
    const cep = form.cep.replace(/\D/g, '')
    if (cep.length !== 8) { toast.error('CEP inválido'); return }
    setLoadingCnpj(true)
    try {
      const r = await fetch(`https://viacep.com.br/ws/${cep}/json/`)
      const d = await r.json()
      if (d.erro) { toast.error('CEP não encontrado'); return }
      setForm(prev => ({ ...prev, logradouro: d.logradouro, bairro: d.bairro, municipio: d.localidade, uf: d.uf }))
    } catch { toast.error('Erro ao buscar CEP') } finally { setLoadingCnpj(false) }
  }

  const tipoBadge = (t: string) => {
    const m: Record<string, 'info' | 'success' | 'default'> = { CLIENTE: 'info' as never, FORNECEDOR: 'success', AMBOS: 'default' }
    return <Badge variant={m[t] ?? 'secondary'}>{t}</Badge>
  }

  const cols: ColumnDef<Parceiro>[] = [
    { accessorKey: 'razao_social', header: 'Razão Social' },
    { accessorKey: 'cnpj', header: 'CNPJ', cell: ({ row }) => formatCNPJ(row.original.cnpj as string ?? '') },
    { accessorKey: 'tipo', header: 'Tipo', cell: ({ row }) => tipoBadge(row.original.tipo as string) },
    { accessorKey: 'municipio', header: 'Cidade', cell: ({ row }) => `${row.original.municipio ?? '—'}/${row.original.uf ?? ''}` },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <Badge variant={(row.original.status as string) === 'ATIVO' ? 'success' : 'secondary'}>{row.original.status as string}</Badge> },
    {
      id: 'actions', header: '', size: 160,
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => openEdit(row.original)} className="text-xs">Editar</Button>
          {!!row.original.id && <Button size="sm" variant="ghost" onClick={() => consultarCnpj.mutate(row.original.id as number)} className="text-xs text-blue-400">CNPJ</Button>}
          <Button size="sm" variant="ghost" className="text-xs text-destructive" onClick={() => { if (confirm('Remover parceiro?')) delMut.mutate(row.original.id as number) }}>Excluir</Button>
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Parceiros" subtitle="Clientes e fornecedores cadastrados" />
      <main className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <Tabs value={tipoFiltro} onValueChange={setTipoFiltro} className="w-auto">
            <TabsList className="h-8">
              <TabsTrigger value="todos" className="text-xs px-3">Todos</TabsTrigger>
              <TabsTrigger value="cliente" className="text-xs px-3">Clientes</TabsTrigger>
              <TabsTrigger value="fornecedor" className="text-xs px-3">Fornecedores</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button size="sm" onClick={openNew}><Plus className="h-4 w-4 mr-1" /> Novo Parceiro</Button>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" /> {lista.length} parceiro(s)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable columns={cols} data={lista} searchKey="razao_social" searchPlaceholder="Filtrar por razão social…" />
          </CardContent>
        </Card>
      </main>

      <Dialog open={open} onOpenChange={v => { setOpen(v); if (!v) { setEditing(null); setForm(EMPTY) } }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar Parceiro' : 'Novo Parceiro'}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="space-y-1.5">
              <Label>Tipo</Label>
              <Select value={form.tipo} onValueChange={v => set('tipo', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="CLIENTE">Cliente</SelectItem>
                  <SelectItem value="FORNECEDOR">Fornecedor</SelectItem>
                  <SelectItem value="AMBOS">Ambos</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={form.status} onValueChange={v => set('status', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ATIVO">Ativo</SelectItem>
                  <SelectItem value="INATIVO">Inativo</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label>Razão Social <span className="text-destructive">*</span></Label>
              <Input value={form.razao_social} onChange={e => set('razao_social', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Nome Fantasia</Label>
              <Input value={form.nome_fantasia} onChange={e => set('nome_fantasia', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>CNPJ</Label>
              <Input value={form.cnpj} onChange={e => set('cnpj', e.target.value)} placeholder="00.000.000/0000-00" />
            </div>
            <div className="space-y-1.5">
              <Label>IE</Label>
              <Input value={form.ie} onChange={e => set('ie', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Regime Tributário</Label>
              <Select value={form.regime_tributario} onValueChange={v => set('regime_tributario', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="SIMPLES">Simples Nacional</SelectItem>
                  <SelectItem value="REGIME_NORMAL">Regime Normal</SelectItem>
                  <SelectItem value="MEI">MEI</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Contribuinte ICMS</Label>
              <Select value={form.contribuinte_icms} onValueChange={v => set('contribuinte_icms', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 — Contribuinte</SelectItem>
                  <SelectItem value="2">2 — Isento</SelectItem>
                  <SelectItem value="9">9 — Não Contribuinte</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Endereço */}
            <div className="col-span-2"><p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Endereço</p></div>
            <div className="space-y-1.5">
              <Label>CEP</Label>
              <div className="flex gap-2">
                <Input value={form.cep} onChange={e => set('cep', e.target.value)} placeholder="00000-000" className="flex-1" />
                <Button type="button" variant="outline" size="sm" onClick={buscarCEP} disabled={loadingCnpj}>
                  <Search className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Número</Label>
              <Input value={form.numero} onChange={e => set('numero', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Logradouro</Label>
              <Input value={form.logradouro} onChange={e => set('logradouro', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Complemento</Label>
              <Input value={form.complemento} onChange={e => set('complemento', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Bairro</Label>
              <Input value={form.bairro} onChange={e => set('bairro', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Município</Label>
              <Input value={form.municipio} onChange={e => set('municipio', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>UF</Label>
              <Input value={form.uf} onChange={e => set('uf', e.target.value)} maxLength={2} />
            </div>
            <div className="space-y-1.5">
              <Label>Telefone</Label>
              <Input value={form.telefone} onChange={e => set('telefone', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>E-mail</Label>
              <Input type="email" value={form.email_contato} onChange={e => set('email_contato', e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
              {saveMut.isPending ? 'Salvando…' : 'Salvar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
