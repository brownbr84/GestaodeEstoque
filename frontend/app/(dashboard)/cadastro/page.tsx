'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { config as configApi, produtos as produtosApi } from '@/lib/api'
import { useAuthStore } from '@/store'
import { PackagePlus } from 'lucide-react'

const TIPO_CONTROLE = ['TAG', 'Lote', 'Unitário']

interface FormState {
  codigo: string; descricao: string; marca: string; modelo: string
  categoria: string; dimensoes: string; capacidade: string
  valor_unitario: string; tipo_material: string; tipo_controle: string
  ncm: string; c_ean: string; orig_icms: string; cest: string
  imagem_b64: string
}

const EMPTY: FormState = {
  codigo: '', descricao: '', marca: '', modelo: '', categoria: '',
  dimensoes: '', capacidade: '', valor_unitario: '', tipo_material: '',
  tipo_controle: 'Lote', ncm: '', c_ean: 'SEM GTIN', orig_icms: '0', cest: '',
  imagem_b64: '',
}

export default function CadastroPage() {
  const { user } = useAuthStore()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [loading, setLoading] = useState(false)

  const { data: cfg } = useQuery({
    queryKey: ['configuracoes'],
    queryFn: () => configApi.get() as Promise<{ categorias_produto: string[]; tipos_material: string[]; tipos_controle: string[] }>,
  })

  function set(k: keyof FormState, v: string) {
    setForm(prev => ({ ...prev, [k]: v }))
  }

  function handleImagem(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 2_000_000) { toast.error('Imagem muito grande (máx 2MB).'); return }
    const reader = new FileReader()
    reader.onload = () => set('imagem_b64', (reader.result as string).split(',')[1])
    reader.readAsDataURL(file)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const { codigo, descricao, categoria, tipo_material, tipo_controle } = form
    if (!codigo || !descricao || !categoria || !tipo_material || !tipo_controle) {
      toast.error('Preencha os campos obrigatórios: código, descrição, categoria, tipo material e controle.')
      return
    }
    setLoading(true)
    try {
      await produtosApi.criar({
        ...form,
        valor_unitario: parseFloat(form.valor_unitario) || 0,
        usuario_atual: user?.usuario ?? '',
      })
      toast.success(`Produto ${form.codigo} cadastrado com sucesso!`)
      setForm(EMPTY)
    } catch (err: unknown) {
      toast.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const categorias = cfg?.categorias_produto ?? []
  const tiposMaterial = cfg?.tipos_material ?? []

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <Header title="Cadastro de Produto" subtitle="Registrar novo produto no catálogo" />
      <main className="flex-1 overflow-y-auto p-4">
        <form onSubmit={handleSubmit}>
          <div className="max-w-4xl mx-auto space-y-4">
            {/* Identificação */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <PackagePlus className="h-4 w-4 text-primary" /> Identificação
                </CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label>Código <span className="text-destructive">*</span></Label>
                  <Input value={form.codigo} onChange={e => set('codigo', e.target.value.toUpperCase())} placeholder="Ex: PROD-001" />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label>Descrição <span className="text-destructive">*</span></Label>
                  <Input value={form.descricao} onChange={e => set('descricao', e.target.value)} placeholder="Descrição completa do produto" />
                </div>
                <div className="space-y-1.5">
                  <Label>Marca</Label>
                  <Input value={form.marca} onChange={e => set('marca', e.target.value)} placeholder="Fabricante" />
                </div>
                <div className="space-y-1.5">
                  <Label>Modelo</Label>
                  <Input value={form.modelo} onChange={e => set('modelo', e.target.value)} placeholder="Modelo" />
                </div>
                <div className="space-y-1.5">
                  <Label>Categoria <span className="text-destructive">*</span></Label>
                  <Select value={form.categoria} onValueChange={v => set('categoria', v)}>
                    <SelectTrigger><SelectValue placeholder="Selecione…" /></SelectTrigger>
                    <SelectContent>
                      {categorias.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Características */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Características Físicas</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="space-y-1.5">
                  <Label>Tipo de Material <span className="text-destructive">*</span></Label>
                  <Select value={form.tipo_material} onValueChange={v => set('tipo_material', v)}>
                    <SelectTrigger><SelectValue placeholder="Selecione…" /></SelectTrigger>
                    <SelectContent>
                      {tiposMaterial.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Tipo de Controle <span className="text-destructive">*</span></Label>
                  <Select value={form.tipo_controle} onValueChange={v => set('tipo_controle', v)}>
                    <SelectTrigger><SelectValue placeholder="Selecione…" /></SelectTrigger>
                    <SelectContent>
                      {TIPO_CONTROLE.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Dimensões</Label>
                  <Input value={form.dimensoes} onChange={e => set('dimensoes', e.target.value)} placeholder="Ex: 10x20x5cm" />
                </div>
                <div className="space-y-1.5">
                  <Label>Capacidade</Label>
                  <Input value={form.capacidade} onChange={e => set('capacidade', e.target.value)} placeholder="Ex: 100A" />
                </div>
                <div className="space-y-1.5">
                  <Label>Valor Unitário (R$)</Label>
                  <Input type="number" step="0.01" min="0" value={form.valor_unitario} onChange={e => set('valor_unitario', e.target.value)} placeholder="0,00" />
                </div>
              </CardContent>
            </Card>

            {/* Fiscal */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Dados Fiscais (NF-e)</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="space-y-1.5">
                  <Label>NCM (8 dígitos)</Label>
                  <Input value={form.ncm} onChange={e => set('ncm', e.target.value)} placeholder="00000000" maxLength={8} />
                </div>
                <div className="space-y-1.5">
                  <Label>EAN / GTIN</Label>
                  <Input value={form.c_ean} onChange={e => set('c_ean', e.target.value)} placeholder="SEM GTIN" />
                </div>
                <div className="space-y-1.5">
                  <Label>Orig. ICMS</Label>
                  <Select value={form.orig_icms} onValueChange={v => set('orig_icms', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">0 — Nacional</SelectItem>
                      <SelectItem value="1">1 — Estrangeira (importação direta)</SelectItem>
                      <SelectItem value="2">2 — Estrangeira (adq. mercado interno)</SelectItem>
                      <SelectItem value="3">3 — Nacional — conteúdo import. {'>'} 40%</SelectItem>
                      <SelectItem value="4">4 — Nacional — processos produtivos básicos</SelectItem>
                      <SelectItem value="5">5 — Nacional — conteúdo import. ≤ 40%</SelectItem>
                      <SelectItem value="6">6 — Estrangeira (import. direta) sem similar</SelectItem>
                      <SelectItem value="7">7 — Estrangeira (merc. interno) sem similar</SelectItem>
                      <SelectItem value="8">8 — Nacional — 70% {'<'} import. ≤ 40%</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>CEST (7 dígitos)</Label>
                  <Input value={form.cest} onChange={e => set('cest', e.target.value)} placeholder="Opcional" maxLength={7} />
                </div>
              </CardContent>
            </Card>

            {/* Imagem */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Imagem do Produto</CardTitle>
              </CardHeader>
              <CardContent className="flex items-center gap-4">
                {form.imagem_b64 && (
                  <img src={`data:image/jpeg;base64,${form.imagem_b64}`} alt="Preview" className="w-20 h-20 object-cover rounded-lg border border-border" />
                )}
                <div>
                  <input type="file" accept="image/*" id="img-upload" className="hidden" onChange={handleImagem} />
                  <Label htmlFor="img-upload" className="cursor-pointer">
                    <Button type="button" variant="outline" size="sm" onClick={() => document.getElementById('img-upload')?.click()}>
                      Selecionar Imagem
                    </Button>
                  </Label>
                  <p className="text-xs text-muted-foreground mt-1">PNG, JPG ou WEBP — máx 2MB</p>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end gap-3 pb-4">
              <Button type="button" variant="outline" onClick={() => setForm(EMPTY)}>Limpar</Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Cadastrando…' : '+ Cadastrar Produto'}
              </Button>
            </div>
          </div>
        </form>
      </main>
    </div>
  )
}
