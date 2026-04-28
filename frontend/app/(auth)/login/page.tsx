'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Eye, EyeOff, Lock, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/store'

type Mode = 'login' | 'recuperar' | 'confirmar'

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuthStore()
  const [mode, setMode] = useState<Mode>('login')
  const [loading, setLoading] = useState(false)
  const [showPass, setShowPass] = useState(false)

  // login
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')

  // recuperar
  const [recUser, setRecUser] = useState('')
  const [recEmail, setRecEmail] = useState('')

  // confirmar
  const [codigo, setCodigo] = useState('')
  const [novaSenha, setNovaSenha] = useState('')
  const [confirmar, setConfirmar] = useState('')

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!usuario || !senha) { toast.error('Preencha usuário e senha.'); return }
    setLoading(true)
    try {
      const data = await auth.login(usuario, senha)
      login(data.access_token, {
        nome: data.nome,
        perfil: data.perfil as 'Admin' | 'Gestor' | 'Operador',
        usuario: data.usuario ?? usuario,
      })
      router.push('/')
    } catch (err: unknown) {
      toast.error((err as Error).message || 'Credenciais inválidas.')
    } finally {
      setLoading(false)
    }
  }

  async function handleRecuperar(e: React.FormEvent) {
    e.preventDefault()
    if (!recUser || !recEmail) { toast.error('Preencha todos os campos.'); return }
    setLoading(true)
    try {
      await auth.recuperarSenha(recUser, recEmail)
      toast.success('Código enviado! Verifique seu e-mail.')
      setMode('confirmar')
    } catch (err: unknown) {
      toast.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirmar(e: React.FormEvent) {
    e.preventDefault()
    if (!codigo || !novaSenha) { toast.error('Preencha todos os campos.'); return }
    if (novaSenha !== confirmar) { toast.error('As senhas não coincidem.'); return }
    if (novaSenha.length < 6) { toast.error('Senha deve ter ao menos 6 caracteres.'); return }
    setLoading(true)
    try {
      await auth.confirmarRecuperacao(recUser, codigo, novaSenha)
      toast.success('Senha redefinida! Faça login.')
      setMode('login')
    } catch (err: unknown) {
      toast.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Brand */}
        <div className="text-center">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mx-auto mb-4">
            <span className="text-white text-lg font-bold">TB</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">TraceBox</h1>
          <p className="text-sm text-muted-foreground mt-1">WMS Enterprise Solution · By Operis Tech</p>
        </div>

        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">
              {mode === 'login' && '🔒 Acesso Restrito'}
              {mode === 'recuperar' && '🔑 Recuperação de Senha'}
              {mode === 'confirmar' && '✅ Redefinir Senha'}
            </CardTitle>
            {mode === 'recuperar' && (
              <CardDescription>Informe seu usuário e o e-mail de recuperação cadastrado.</CardDescription>
            )}
            {mode === 'confirmar' && (
              <CardDescription>Digite o código recebido no e-mail e escolha uma nova senha.</CardDescription>
            )}
          </CardHeader>

          <CardContent>
            {mode === 'login' && (
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="usuario">Usuário</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="usuario" value={usuario} onChange={e => setUsuario(e.target.value)} placeholder="Digite seu ID" className="pl-9" autoComplete="username" />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="senha">Senha</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input id="senha" type={showPass ? 'text' : 'password'} value={senha} onChange={e => setSenha(e.target.value)} placeholder="••••••••" className="pl-9 pr-9" autoComplete="current-password" />
                    <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                      {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? 'Entrando…' : 'Entrar no Sistema'}
                </Button>
                <Button type="button" variant="ghost" className="w-full text-xs" onClick={() => setMode('recuperar')}>
                  Esqueci minha senha
                </Button>
              </form>
            )}

            {mode === 'recuperar' && (
              <form onSubmit={handleRecuperar} className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Usuário</Label>
                  <Input value={recUser} onChange={e => setRecUser(e.target.value)} placeholder="Seu login" />
                </div>
                <div className="space-y-1.5">
                  <Label>E-mail de Recuperação</Label>
                  <Input type="email" value={recEmail} onChange={e => setRecEmail(e.target.value)} placeholder="email@empresa.com" />
                </div>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" className="flex-1" onClick={() => setMode('login')}>← Voltar</Button>
                  <Button type="submit" className="flex-1" disabled={loading}>{loading ? 'Enviando…' : 'Enviar Código'}</Button>
                </div>
              </form>
            )}

            {mode === 'confirmar' && (
              <form onSubmit={handleConfirmar} className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Código de Verificação</Label>
                  <Input value={codigo} onChange={e => setCodigo(e.target.value)} placeholder="000000" maxLength={6} />
                </div>
                <div className="space-y-1.5">
                  <Label>Nova Senha</Label>
                  <Input type="password" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} placeholder="Mínimo 6 caracteres" />
                </div>
                <div className="space-y-1.5">
                  <Label>Confirmar Nova Senha</Label>
                  <Input type="password" value={confirmar} onChange={e => setConfirmar(e.target.value)} placeholder="Repita a nova senha" />
                </div>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" className="flex-1" onClick={() => setMode('recuperar')}>← Voltar</Button>
                  <Button type="submit" className="flex-1" disabled={loading}>{loading ? 'Redefinindo…' : 'Redefinir Senha'}</Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          TraceBox WMS v1.0 · Operis Tech
        </p>
      </div>
    </div>
  )
}
