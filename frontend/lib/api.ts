const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem('tracebox-auth')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.state?.token ?? null
  } catch {
    return null
  }
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof body.detail === 'string'
      ? body.detail
      : JSON.stringify(body.detail)
    throw new ApiError(res.status, msg)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  login: (usuario: string, senha: string) =>
    request<{ access_token: string; nome: string; perfil: string; usuario?: string }>(
      '/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ usuario, senha }) }
    ),
  me: (token: string) =>
    fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(r => r.ok ? r.json() : null) as Promise<{ nome: string; perfil: string; usuario: string } | null>,
  recuperarSenha: (usuario: string, email: string) =>
    request('/api/v1/auth/recuperar-senha', { method: 'POST', body: JSON.stringify({ usuario, email }) }),
  confirmarRecuperacao: (usuario: string, codigo: string, nova_senha: string) =>
    request('/api/v1/auth/confirmar-recuperacao', { method: 'POST', body: JSON.stringify({ usuario, codigo, nova_senha }) }),
}

// ── Config ────────────────────────────────────────────────────────────────────
export const config = {
  get: () => request('/api/v1/configuracoes'),
  update: (data: Record<string, unknown>) =>
    request('/api/v1/configuracoes', { method: 'PUT', body: JSON.stringify(data) }),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboard = {
  metricas: () => request('/api/v1/dashboard/metricas'),
}

// ── Usuários ──────────────────────────────────────────────────────────────────
export const usuarios = {
  listar: () => request<{ id: number; nome: string; usuario: string; perfil: string; email: string }[]>('/api/v1/usuarios'),
  criar: (data: { nome: string; usuario: string; senha: string; perfil: string; email?: string }) =>
    request('/api/v1/usuarios', { method: 'POST', body: JSON.stringify(data) }),
  alterarSenha: (usuario_alvo: string, nova_senha: string) =>
    request('/api/v1/usuarios/senha', { method: 'PUT', body: JSON.stringify({ usuario_alvo, nova_senha }) }),
  atualizarEmail: (usuario_alvo: string, email: string) =>
    request('/api/v1/usuarios/email', { method: 'PUT', body: JSON.stringify({ usuario_alvo, email }) }),
  excluir: (usuario_alvo: string) =>
    request(`/api/v1/usuarios/${usuario_alvo}`, { method: 'DELETE' }),
}

// ── Produtos ──────────────────────────────────────────────────────────────────
export const produtos = {
  catalogo: () => request<{ codigo: string; descricao: string; tipo_material: string }[]>('/api/v1/imobilizado/catalogo/simples'),
  detalhes: (codigo: string) => request<{ mestre: Record<string, unknown>; inventario: Record<string, unknown>[]; tags: Record<string, unknown>[]; historico: Record<string, unknown>[] }>(`/api/v1/produtos/${codigo}/detalhes`),
  criar: (data: Record<string, unknown>) =>
    request('/api/v1/produtos', { method: 'POST', body: JSON.stringify(data) }),
  atualizarMestre: (codigo: string, data: Record<string, unknown>) =>
    request(`/api/v1/produtos/${codigo}/mestre`, { method: 'PUT', body: JSON.stringify(data) }),
  atualizarCalibracao: (codigo: string, itens: unknown[], usuario: string) =>
    request(`/api/v1/produtos/${codigo}/calibracao`, { method: 'PUT', body: JSON.stringify({ itens, usuario }) }),
}

// ── Parceiros ─────────────────────────────────────────────────────────────────
export const parceiros = {
  listar: (tipo?: string, status?: string) => {
    const p = new URLSearchParams()
    if (tipo) p.set('tipo', tipo)
    if (status) p.set('status', status)
    return request<Record<string, unknown>[]>(`/api/v1/parceiros?${p}`)
  },
  buscar: (id: number) => request<Record<string, unknown>>(`/api/v1/parceiros/${id}`),
  criar: (data: Record<string, unknown>) =>
    request('/api/v1/parceiros', { method: 'POST', body: JSON.stringify(data) }),
  atualizar: (id: number, data: Record<string, unknown>) =>
    request(`/api/v1/parceiros/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  excluir: (id: number) =>
    request(`/api/v1/parceiros/${id}`, { method: 'DELETE' }),
  consultarCNPJ: (id: number) =>
    request(`/api/v1/parceiros/${id}/consultar-cnpj`, { method: 'POST' }),
}

// ── Emitente ──────────────────────────────────────────────────────────────────
export const emitente = {
  get: () => request('/api/v1/emitente'),
  salvar: (data: Record<string, unknown>) =>
    request('/api/v1/emitente', { method: 'POST', body: JSON.stringify(data) }),
  sincronizarCNPJ: () =>
    request('/api/v1/emitente/sincronizar-cnpj', { method: 'POST' }),
}

// ── Inbound ───────────────────────────────────────────────────────────────────
export const inbound = {
  compras: (data: Record<string, unknown>) =>
    request('/api/v1/inbound/compras', { method: 'POST', body: JSON.stringify(data) }),
  docaOrigens: (polo: string) =>
    request<{ origens: string[] }>(`/api/v1/inbound/doca/origens?polo=${polo}`),
  docaEsperados: (origem: string, polo: string) =>
    request<Record<string, unknown>[]>(`/api/v1/inbound/doca/esperados?origem=${origem}&polo=${polo}`),
  docaReceber: (data: Record<string, unknown>) =>
    request('/api/v1/inbound/doca/receber', { method: 'POST', body: JSON.stringify(data) }),
  entradaExcepcional: (data: Record<string, unknown>) =>
    request('/api/v1/inbound/entrada-excepcional', { method: 'POST', body: JSON.stringify(data) }),
  malhaFinaFaltas: () =>
    request<Record<string, unknown>[]>('/api/v1/inbound/malha-fina/faltas'),
  reintegrar: (data: Record<string, unknown>) =>
    request('/api/v1/inbound/malha-fina/reintegrar', { method: 'POST', body: JSON.stringify(data) }),
  extravio: (data: Record<string, unknown>) =>
    request('/api/v1/inbound/malha-fina/extravio', { method: 'POST', body: JSON.stringify(data) }),
}

// ── Outbound ──────────────────────────────────────────────────────────────────
export const outbound = {
  pedidos: (polo: string) =>
    request<Record<string, unknown>[]>(`/api/v1/outbound/pedidos?polo=${polo}`),
  cancelar: (data: Record<string, unknown>) =>
    request('/api/v1/outbound/pedidos/cancelar', { method: 'POST', body: JSON.stringify(data) }),
  picking: (req_id: string, polo: string) =>
    request<Record<string, unknown>[]>(`/api/v1/outbound/pedidos/${req_id}/picking?polo=${polo}`),
  tags: (codigo: string, polo: string) =>
    request<{ tags: string[] }>(`/api/v1/outbound/tags?codigo=${codigo}&polo=${polo}`),
  despachar: (data: Record<string, unknown>) =>
    request('/api/v1/outbound/pedidos/despachar', { method: 'POST', body: JSON.stringify(data) }),
  transito: (polo: string) =>
    request<Record<string, unknown>[]>(`/api/v1/outbound/transito?polo=${polo}`),
  baixaExcepcional: (data: Record<string, unknown>) =>
    request('/api/v1/outbound/baixa-excepcional', { method: 'POST', body: JSON.stringify(data) }),
}

// ── Polos ─────────────────────────────────────────────────────────────────────
export const polos = {
  emUso: () => request<{ polos: string[] }>('/api/v1/polos/em-uso'),
}

// ── Inventário ────────────────────────────────────────────────────────────────
export const inventario = {
  esperado: (polo: string, classificacao: string) =>
    request<Record<string, unknown>[]>(`/api/v1/inventario/esperado?polo=${polo}&classificacao=${encodeURIComponent(classificacao)}`),
  cruzamento: (polo: string, tags_bipadas: string[], lotes_contados: Record<string, number>) =>
    request('/api/v1/inventario/cruzamento', { method: 'POST', body: JSON.stringify({ polo, tags_bipadas, lotes_contados }) }),
  processar: (data: Record<string, unknown>) =>
    request('/api/v1/inventario/processar', { method: 'POST', body: JSON.stringify(data) }),
}

// ── Matriz Física ─────────────────────────────────────────────────────────────
export const matrizFisica = {
  checarCodigo: (codigo: string) =>
    request<{ encontrado: boolean }>(`/api/v1/matriz-fisica/checar-codigo?codigo=${codigo}`),
  raw: () =>
    request<Record<string, unknown>[]>('/api/v1/matriz-fisica/raw'),
}

// ── Etiquetas ─────────────────────────────────────────────────────────────────
export const etiquetas = {
  produtos: (tipo_material: string) =>
    request<{ codigo: string; descricao: string }[]>(`/api/v1/etiquetas/produtos?tipo_material=${encodeURIComponent(tipo_material)}`),
  inventario: (codigo: string) =>
    request<Record<string, unknown>[]>(`/api/v1/etiquetas/inventario?codigo=${codigo}`),
}

// ── Relatórios ────────────────────────────────────────────────────────────────
export const relatorios = {
  produtos: () => request<{ produtos: string[] }>('/api/v1/relatorios/produtos'),
  extrato: (produto: string, inicio: string, fim: string) =>
    request<{ dados: Record<string, unknown>[]; codigo: string }>(`/api/v1/relatorios/extrato?produto=${encodeURIComponent(produto)}&inicio=${inicio}&fim=${fim}`),
  posicao: () => request<Record<string, unknown>[]>('/api/v1/relatorios/posicao'),
  manutencao: (inicio: string, fim: string, status: string) =>
    request<Record<string, unknown>[]>(`/api/v1/relatorios/manutencao?inicio=${inicio}&fim=${fim}&status=${status}`),
}

// ── Auditoria ─────────────────────────────────────────────────────────────────
export const auditoria = {
  logs: (filtro_acao: string, filtro_usuario: string, filtro_data: string) =>
    request('/api/v1/auditoria/logs', { method: 'POST', body: JSON.stringify({ filtro_acao, filtro_usuario, filtro_data }) }),
  reativar: (tag: string, polo: string, motivo: string, usuario: string) =>
    request('/api/v1/auditoria/reativar', { method: 'POST', body: JSON.stringify({ tag, polo, motivo, usuario }) }),
}

// ── Manutenção ────────────────────────────────────────────────────────────────
export const manutencao = {
  ativos: () => request<Record<string, unknown>[]>('/api/v1/manutencao/ativos'),
  abrir: (data: Record<string, unknown>) =>
    request('/api/v1/manutencao/abrir', { method: 'POST', body: JSON.stringify(data) }),
  abertas: () => request<Record<string, unknown>[]>('/api/v1/manutencao/abertas'),
  orcamento: (data: Record<string, unknown>) =>
    request('/api/v1/manutencao/orcamento', { method: 'POST', body: JSON.stringify(data) }),
  aprovacao: () => request<Record<string, unknown>[]>('/api/v1/manutencao/aprovacao'),
  aprovar: (ordem_id: number, decisao: string, usuario: string) =>
    request('/api/v1/manutencao/aprovar', { method: 'POST', body: JSON.stringify({ ordem_id, decisao, usuario }) }),
  execucao: () => request<Record<string, unknown>[]>('/api/v1/manutencao/execucao'),
  finalizar: (data: Record<string, unknown>) =>
    request('/api/v1/manutencao/finalizar', { method: 'POST', body: JSON.stringify(data) }),
  historico: (ferramenta_id: string) =>
    request<Record<string, unknown>[]>(`/api/v1/manutencao/historico/${ferramenta_id}`),
  reenviarEmail: (os_id: number) =>
    request(`/api/v1/manutencao/${os_id}/reenviar-email`, { method: 'POST' }),
}

// ── Requisição ────────────────────────────────────────────────────────────────
export const requisicao = {
  catalogo: (data: Record<string, unknown>) =>
    request('/api/v1/requisicao/catalogo', { method: 'POST', body: JSON.stringify(data) }),
  salvar: (data: Record<string, unknown>) =>
    request('/api/v1/requisicao/salvar', { method: 'POST', body: JSON.stringify(data) }),
  historico: (usuario: string) =>
    request<Record<string, unknown>[]>(`/api/v1/requisicao/historico?usuario=${usuario}`),
  itens: (req_id: string) =>
    request<Record<string, unknown>[]>(`/api/v1/requisicao/${req_id}/itens`),
  reenviarEmail: (req_id: number) =>
    request(`/api/v1/requisicao/${req_id}/reenviar-email`, { method: 'POST' }),
}

// ── Fiscal ────────────────────────────────────────────────────────────────────
export const fiscal = {
  preparar: (data: Record<string, unknown>) =>
    request('/api/v1/fiscal/preparar', { method: 'POST', body: JSON.stringify(data) }),
  rascunhos: (status = 'PENDENTE') =>
    request<Record<string, unknown>[]>(`/api/v1/fiscal/rascunhos?status=${status}`),
  emitir: (data: Record<string, unknown>) =>
    request('/api/v1/fiscal/emitir', { method: 'POST', body: JSON.stringify(data) }),
  cancelar: (data: Record<string, unknown>) =>
    request('/api/v1/fiscal/cancelar', { method: 'POST', body: JSON.stringify(data) }),
  documentos: (params?: Record<string, string>) => {
    const p = new URLSearchParams(params)
    return request<Record<string, unknown>[]>(`/api/v1/fiscal/documentos?${p}`)
  },
  danfePdf: (doc_id: number) =>
    fetch(`${API_BASE}/api/v1/fiscal/danfe/${doc_id}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    }),
}

// ── Localização ───────────────────────────────────────────────────────────────
export const localizacao = {
  listar: () => request<Record<string, unknown>[]>('/api/v1/localizacoes'),
  criar: (data: Record<string, unknown>) =>
    request('/api/v1/localizacoes', { method: 'POST', body: JSON.stringify(data) }),
  atualizar: (id: number, data: Record<string, unknown>) =>
    request(`/api/v1/localizacoes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  excluir: (id: number) =>
    request(`/api/v1/localizacoes/${id}`, { method: 'DELETE' }),
  vincular: (data: Record<string, unknown>) =>
    request('/api/v1/localizacoes/vincular-item', { method: 'POST', body: JSON.stringify(data) }),
}

export { ApiError }
