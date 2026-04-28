'use client'
import { useState, useEffect } from 'react'
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
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { config as configApi, usuarios as usuariosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { Settings, Users, Plus, Trash2 } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'

type Cfg = Record<string, unknown>
type Usuario = { id: number; nome: string; usuario: string; perfil: string; email: string }

export default function ConfiguracoesPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const isAdmin = user?.perfil === 'Admin'

  const { data: cfg, isLoading } = useQuery({
    queryKey: ['configuracoes'],
    queryFn: () => configApi.get() as Promise<Cfg>,
  })
  const { data: listaUsuarios = [] } = useQuery({
    queryKey: ['usuarios'],
    queryFn: usuariosApi.listar,
    enabled: isAdmin,
  })

  const [empresa, setEmpresa] = useState({ nome_empresa: '', cnpj: '' })
  const [fiscal, setFiscal] = useState({ fiscal_habilitado: false, fiscal_ambiente: 'homologacao', fiscal_serie: '1', fiscal_numeracao_atual: 1 })
  const [smtp, setSmtp] = useState({ email_smtp: '', smtp_host: '', smtp_porta: '587', senha_smtp: '' })
  const [emails, setEmails] = useState<string[]>([])
  const [novoEmail, setNovoEmail] = useState('')
  const [logoB64, setLogoB64] = useState('')
  const [modalUser, setModalUser] = useState(false)
  const [formUser, setFormUser] = useState({ nome: '', usuario: '', senha: '', perfil: 'Operador', email: '' })
  const [modalSenha, setModalSenha] = useState<Usuario | null>(null)
  const [novaSenha, setNovaSenha] = useState('')

  useEffect(() => {
    if (!cfg) return
    setEmpresa({ nome_empresa: (cfg.nome_empresa as string) ?? '', cnpj: (cfg.cnpj as string) ?? '' })
    setFiscal({
      fiscal_habilitado: !!(cfg.fiscal_habilitado),
      fiscal_ambiente: (cfg.fiscal_ambiente as string) ?? 'homologacao',
      fiscal_serie: (cfg.fiscal_serie as string) ?? '1',
      fiscal_numeracao_atual: (cfg.fiscal_numeracao_atual as number) ?? 1,
    })
    setSmtp({ email_smtp: (cfg.email_smtp as string) ?? '', smtp_host: (cfg.smtp_host as string) ?? '', smtp_porta: String(cfg.smtp_porta ?? 587), senha_smtp: '' })
    setEmails((cfg.emails_destinatarios as string[]) ?? [])
    setLogoB64((cfg.logo_base64 as string) ?? '')
  }, [cfg])

  const saveCfgMut = useMutation({
    mutationFn: () => configApi.update({
      ...empresa, ...fiscal,
      ...smtp, smtp_porta: parseInt(smtp.smtp_porta),
      emails_destinatarios: emails,
      logo_base64: logoB64,
    }),
    onSuccess: () => { toast.success('Configurações salvas!'); qc.invalidateQueries({ queryKey: ['configuracoes'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  const criarUserMut = useMutation({
    mutationFn: () => usuariosApi.criar(formUser),
    onSuccess: () => { toast.success('Usuário criado!'); qc.invalidateQueries({ queryKey: ['usuarios'] }); setModalUser(false); setFormUser({ nome: '', usuario: '', senha: '', perfil: 'Operador', email: '' }) },
    onError: (err: Error) => toast.error(err.message),
  })

  const excluirUserMut = useMutation({
    mutationFn: (u: string) => usuariosApi.excluir(u),
    onSuccess: () => { toast.success('Usuário removido.'); qc.invalidateQueries({ queryKey: ['usuarios'] }) },
    onError: (err: Error) => toast.error(err.message),
  })

  const alterarSenhaMut = useMutation({
    mutationFn: () => usuariosApi.alterarSenha(modalSenha!.usuario, novaSenha),
    onSuccess: () => { toast.success('Senha alterada!'); setModalSenha(null); setNovaSenha('') },
    onError: (err: Error) => toast.error(err.message),
  })

  function handleLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setLogoB64((reader.result as string).split(',')[1])
    reader.readAsDataURL(file)
  }

  function addEmail() {
    if (!novoEmail || emails.includes(novoEmail)) return
    setEmails(prev => [...prev, novoEmail])
    setNovoEmail('')
  }

  const perfilBadge = (p: string) => {
    const m: Record<string, 'destructive' | 'warning' | 'secondary'> = { Admin: 'destructive', Gestor: 'warning', Operador: 'secondary' }
    return <Badge variant={m[p] ?? 'secondary'}>{p}</Badge>
  }

  const userCols: ColumnDef<Usuario>[] = [
    { accessorKey: 'nome', header: 'Nome' },
    { accessorKey: 'usuario', header: 'Login', size: 100 },
    { accessorKey: 'perfil', header: 'Perfil', size: 80, cell: ({ row }) => perfilBadge(row.original.perfil) },
    { accessorKey: 'email', header: 'E-mail de Recuperação' },
    {
      id: 'actions', header: '', size: 160,
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" className="text-xs" onClick={() => { setModalSenha(row.original); setNovaSenha('') }}>Senha</Button>
          {row.original.usuario !== user?.usuario && (
            <Button size="sm" variant="ghost" className="text-xs text-destructive" onClick={() => { if (confirm(`Excluir usuário ${row.original.usuario}?`)) excluirUserMut.mutate(row.original.usuario) }}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Configurações" subtitle="Parâmetros do sistema e gestão de usuários" />
      <main className="flex-1 overflow-y-auto p-4">
        <Tabs defaultValue="empresa" className="space-y-4">
          <TabsList>
            <TabsTrigger value="empresa" className="text-xs"><Settings className="h-3.5 w-3.5 mr-1" />Empresa</TabsTrigger>
            <TabsTrigger value="fiscal" className="text-xs">Fiscal</TabsTrigger>
            <TabsTrigger value="email" className="text-xs">E-mail / SMTP</TabsTrigger>
            {isAdmin && <TabsTrigger value="usuarios" className="text-xs"><Users className="h-3.5 w-3.5 mr-1" />Usuários</TabsTrigger>}
          </TabsList>

          {/* Empresa */}
          <TabsContent value="empresa">
            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-sm">Dados da Empresa</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label>Nome da Empresa</Label>
                    <Input value={empresa.nome_empresa} onChange={e => setEmpresa(p => ({ ...p, nome_empresa: e.target.value }))} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>CNPJ</Label>
                    <Input value={empresa.cnpj} onChange={e => setEmpresa(p => ({ ...p, cnpj: e.target.value }))} placeholder="00.000.000/0000-00" />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Logo da Empresa</Label>
                  <div className="flex items-center gap-4">
                    {logoB64 && <img src={`data:image/png;base64,${logoB64}`} alt="Logo" className="h-12 object-contain border border-border rounded-lg" />}
                    <input type="file" accept="image/*" id="logo-upload" className="hidden" onChange={handleLogo} />
                    <Button type="button" variant="outline" size="sm" onClick={() => document.getElementById('logo-upload')?.click()}>
                      {logoB64 ? 'Trocar Logo' : 'Carregar Logo'}
                    </Button>
                  </div>
                </div>
                <Button size="sm" onClick={() => saveCfgMut.mutate()} disabled={saveCfgMut.isPending}>
                  {saveCfgMut.isPending ? 'Salvando…' : 'Salvar Configurações'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Fiscal */}
          <TabsContent value="fiscal">
            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-sm">Módulo Fiscal (NF-e)</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                  <Switch checked={fiscal.fiscal_habilitado} onCheckedChange={v => setFiscal(p => ({ ...p, fiscal_habilitado: v }))} />
                  <Label>Módulo Fiscal Habilitado</Label>
                </div>
                <Separator />
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label>Ambiente</Label>
                    <Select value={fiscal.fiscal_ambiente} onValueChange={v => setFiscal(p => ({ ...p, fiscal_ambiente: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="homologacao">Homologação</SelectItem>
                        <SelectItem value="producao">Produção</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Série da NF</Label>
                    <Input value={fiscal.fiscal_serie} onChange={e => setFiscal(p => ({ ...p, fiscal_serie: e.target.value }))} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Numeração Atual</Label>
                    <Input type="number" min="1" value={fiscal.fiscal_numeracao_atual} onChange={e => setFiscal(p => ({ ...p, fiscal_numeracao_atual: parseInt(e.target.value) || 1 }))} />
                  </div>
                </div>
                <Button size="sm" onClick={() => saveCfgMut.mutate()} disabled={saveCfgMut.isPending}>
                  {saveCfgMut.isPending ? 'Salvando…' : 'Salvar Configurações Fiscais'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* E-mail / SMTP */}
          <TabsContent value="email">
            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-sm">Automação de E-mails (SMTP)</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label>Servidor SMTP</Label>
                    <Input value={smtp.smtp_host} onChange={e => setSmtp(p => ({ ...p, smtp_host: e.target.value }))} placeholder="smtp.gmail.com" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Porta</Label>
                    <Input value={smtp.smtp_porta} onChange={e => setSmtp(p => ({ ...p, smtp_porta: e.target.value }))} placeholder="587" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>E-mail Remetente</Label>
                    <Input type="email" value={smtp.email_smtp} onChange={e => setSmtp(p => ({ ...p, email_smtp: e.target.value }))} placeholder="sistema@empresa.com" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Senha (App Password)</Label>
                    <Input type="password" value={smtp.senha_smtp} onChange={e => setSmtp(p => ({ ...p, senha_smtp: e.target.value }))} placeholder="Deixe em branco para manter" />
                  </div>
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label>E-mails Destinatários (notificações)</Label>
                  <div className="flex gap-2">
                    <Input value={novoEmail} onChange={e => setNovoEmail(e.target.value)} placeholder="email@empresa.com" onKeyDown={e => e.key === 'Enter' && addEmail()} />
                    <Button type="button" variant="outline" size="sm" onClick={addEmail}>Add</Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {emails.map(e => (
                      <Badge key={e} variant="secondary" className="gap-1 cursor-pointer" onClick={() => setEmails(prev => prev.filter(x => x !== e))}>
                        {e} <span className="text-destructive ml-1">×</span>
                      </Badge>
                    ))}
                  </div>
                </div>
                <Button size="sm" onClick={() => saveCfgMut.mutate()} disabled={saveCfgMut.isPending}>
                  {saveCfgMut.isPending ? 'Salvando…' : 'Salvar Configurações de E-mail'}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Usuários */}
          {isAdmin && (
            <TabsContent value="usuarios">
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2"><Users className="h-4 w-4 text-primary" />Gestão de Usuários</CardTitle>
                    <Button size="sm" onClick={() => setModalUser(true)}><Plus className="h-4 w-4 mr-1" /> Novo Usuário</Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <DataTable columns={userCols} data={listaUsuarios} searchKey="nome" searchPlaceholder="Filtrar por nome…" />
                </CardContent>
              </Card>
            </TabsContent>
          )}
        </Tabs>
      </main>

      {/* Modal Novo Usuário */}
      <Dialog open={modalUser} onOpenChange={setModalUser}>
        <DialogContent>
          <DialogHeader><DialogTitle>Novo Usuário</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="col-span-2 space-y-1.5"><Label>Nome Completo</Label><Input value={formUser.nome} onChange={e => setFormUser(p => ({ ...p, nome: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>Login</Label><Input value={formUser.usuario} onChange={e => setFormUser(p => ({ ...p, usuario: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>Senha Inicial</Label><Input type="password" value={formUser.senha} onChange={e => setFormUser(p => ({ ...p, senha: e.target.value }))} /></div>
            <div className="space-y-1.5">
              <Label>Perfil</Label>
              <Select value={formUser.perfil} onValueChange={v => setFormUser(p => ({ ...p, perfil: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Admin">Admin</SelectItem>
                  <SelectItem value="Gestor">Gestor</SelectItem>
                  <SelectItem value="Operador">Operador</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5"><Label>E-mail</Label><Input type="email" value={formUser.email} onChange={e => setFormUser(p => ({ ...p, email: e.target.value }))} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalUser(false)}>Cancelar</Button>
            <Button onClick={() => criarUserMut.mutate()} disabled={criarUserMut.isPending}>{criarUserMut.isPending ? 'Criando…' : 'Criar Usuário'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Alterar Senha */}
      <Dialog open={!!modalSenha} onOpenChange={v => { if (!v) { setModalSenha(null); setNovaSenha('') } }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Alterar Senha — {String(modalSenha?.nome ?? '')}</DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label>Nova Senha</Label>
              <Input type="password" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} placeholder="Mínimo 6 caracteres" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalSenha(null)}>Cancelar</Button>
            <Button onClick={() => alterarSenhaMut.mutate()} disabled={alterarSenhaMut.isPending || novaSenha.length < 6}>
              {alterarSenhaMut.isPending ? 'Alterando…' : 'Alterar Senha'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
