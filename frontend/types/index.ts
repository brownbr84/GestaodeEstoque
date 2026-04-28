// ── Auth ──────────────────────────────────────────────────────────────────────
export interface User {
  nome: string
  perfil: 'Admin' | 'Gestor' | 'Operador'
  usuario: string
  access_token: string
}

// ── Configurações ─────────────────────────────────────────────────────────────
export interface Configuracoes {
  nome_empresa: string
  cnpj: string
  logo_base64: string
  categorias_produto: string[]
  tipos_material: string[]
  tipos_controle: string[]
  email_smtp: string
  smtp_host: string
  smtp_porta: number
  emails_destinatarios: string[]
  fiscal_habilitado: boolean
  fiscal_ambiente: string
  fiscal_serie: string
  fiscal_numeracao_atual: number
}

// ── Produto / Imobilizado ─────────────────────────────────────────────────────
export interface Produto {
  id?: number
  codigo: string
  descricao: string
  marca: string
  modelo: string
  categoria: string
  dimensoes: string
  capacidade: string
  valor_unitario: number | null
  tipo_material: string
  tipo_controle: string
  imagem?: string
  num_tag?: string
  quantidade?: number
  status?: string
  localizacao?: string
  ncm?: string
  c_ean?: string
  orig_icms?: string
  cest?: string
  localizacao_id?: number | null
  endereco_codigo?: string | null
  endereco_descricao?: string | null
}

// ── Parceiro ──────────────────────────────────────────────────────────────────
export interface Parceiro {
  id?: number
  tipo: 'CLIENTE' | 'FORNECEDOR' | 'AMBOS'
  razao_social: string
  nome_fantasia?: string
  cnpj: string
  ie?: string
  im?: string
  situacao_cadastral?: string
  cep?: string
  logradouro?: string
  numero?: string
  complemento?: string
  bairro?: string
  municipio?: string
  uf?: string
  codigo_ibge?: string
  telefone?: string
  email_contato?: string
  regime_tributario: string
  contribuinte_icms: number
  status: string
  status_consulta?: string
  origem_dados?: string
  criado_em?: string
  atualizado_em?: string
}

// ── Emitente ──────────────────────────────────────────────────────────────────
export interface Emitente {
  id?: number
  cnpj: string
  razao_social: string
  nome_fantasia?: string
  ie?: string
  im?: string
  cnae_principal?: string
  regime_tributario: string
  cep?: string
  logradouro?: string
  numero?: string
  complemento?: string
  bairro?: string
  municipio?: string
  uf?: string
  codigo_ibge?: string
  telefone?: string
  email?: string
  status_sinc?: string
  origem_dados?: string
}

// ── Usuário ───────────────────────────────────────────────────────────────────
export interface Usuario {
  id: number
  nome: string
  usuario: string
  perfil: string
  email: string
}

// ── Movimentação ──────────────────────────────────────────────────────────────
export interface Movimentacao {
  Data: string
  Serial: string
  'Operação': string
  'Doc/NF': string
  Agente: string
  Destino: string
}

// ── Manutenção ────────────────────────────────────────────────────────────────
export interface OrdemManutencao {
  id: number
  codigo_ferramenta: string
  motivo_falha: string
  solicitante: string
  status_ordem: string
  data_entrada: string
  data_saida?: string
  diagnostico?: string
  custo_reparo?: number
  mecanico_responsavel?: string
  empresa_reparo?: string
  num_orcamento?: string
  email_status?: string
}

// ── Requisição ────────────────────────────────────────────────────────────────
export interface Requisicao {
  id: number
  solicitante: string
  polo_origem: string
  destino_projeto: string
  status: string
  data_solicitacao: string
  email_status?: string
}

export interface RequisicaoItem {
  codigo_produto: string
  descricao_produto: string
  quantidade_solicitada: number
}

// ── Fiscal / NF-e ─────────────────────────────────────────────────────────────
export interface RascunhoNF {
  id: number
  tipo_operacao: string
  status: string
  criado_por: string
  criado_em: string
  aprovado_por?: string
  numero_nf?: string
  chave_acesso?: string
  payload?: Record<string, unknown>
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export interface MetricasDashboard {
  total_ativos: number
  total_polos: number
  em_manutencao: number
  requisicoes_pendentes: number
  produtos_em_falta: number
  [key: string]: unknown
}

// ── Localização ───────────────────────────────────────────────────────────────
export interface Localizacao {
  id: number
  codigo: string
  descricao: string
  tipo?: string
  ativo?: boolean
}

// ── Auditoria ─────────────────────────────────────────────────────────────────
export interface LogAuditoria {
  id: number
  data_hora: string
  usuario: string
  acao: string
  tabela: string
  registro_id: number
  detalhes: string
}
