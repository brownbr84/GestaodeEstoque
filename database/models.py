from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, JSON
from database.conexao_orm import Base
from datetime import datetime
from sqlalchemy import Float, ForeignKey
from sqlalchemy.orm import relationship

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, unique=True)
    
class Fornecedor(Base):
    __tablename__ = 'fornecedores'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String)
    cnpj = Column(String, unique=True)

class Imobilizado(Base):
    __tablename__ = 'imobilizado'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, index=True)
    descricao = Column(String)
    marca = Column(String)
    modelo = Column(String)
    num_tag = Column(String)
    quantidade = Column(Integer, default=0)
    status = Column(String)
    localizacao = Column(String)
    categoria = Column(String)
    valor_unitario = Column(Float)
    data_aquisicao = Column(Date)
    dimensoes = Column(String)
    capacidade = Column(String)
    ultima_manutencao = Column(Date)
    proxima_manutencao = Column(Date)
    detalhes = Column(Text)
    imagem = Column(String)
    tipo_material = Column(String)
    alerta_falta = Column(Integer, default=0)
    tipo_controle = Column(String)
    
    ncm = Column(String)                       # NCM 8 dígitos (NF-e)
    c_ean = Column(String, default='SEM GTIN') # EAN/barcode
    orig_icms = Column(String, default='0')    # Origem ICMS 0=nacional
    cest = Column(String, default='')          # CEST 7 dígitos (ST)

    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'), nullable=True)
    localizacao_id = Column(Integer, ForeignKey('localizacoes.id'), nullable=True)

    categoria_rel = relationship("Categoria", backref="produtos")
    fornecedor_rel = relationship("Fornecedor", backref="produtos")
    localizacao_rel = relationship("Localizacao", backref="itens_imobilizado")

class Movimentacao(Base):
    __tablename__ = 'movimentacoes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # P2 FIX: ForeignKey formal — nullable=True preserva dados legados
    ferramenta_id = Column(Integer, ForeignKey('imobilizado.id', ondelete='SET NULL'), nullable=True)
    tipo = Column(String)
    responsavel = Column(String)
    destino_projeto = Column(String)
    documento = Column(String)
    data_movimentacao = Column(DateTime)

    imobilizado = relationship("Imobilizado", backref="movimentacoes")

class Requisicao(Base):
    __tablename__ = 'requisicoes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    solicitante = Column(String)
    polo_origem = Column(String)
    destino_projeto = Column(String)
    status = Column(String, default='Pendente')
    data_solicitacao = Column(DateTime)
    motivo_cancelamento = Column(String)
    cancelado_por = Column(String)
    email_status = Column(String, default='PENDENTE')   # PENDENTE | ENVIADO | FALHOU | N/A
    email_enviado_em = Column(DateTime, nullable=True)
    email_erro = Column(Text, nullable=True)

    # Relacionamento ORM com os itens da requisição
    itens = relationship("RequisicaoItem", backref="requisicao", lazy="select")


class RequisicaoItem(Base):
    __tablename__ = 'requisicoes_itens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # P2 FIX: ForeignKey formal — nullable=True preserva dados legados
    requisicao_id = Column(Integer, ForeignKey('requisicoes.id', ondelete='CASCADE'), nullable=True)
    codigo_produto = Column(String)
    descricao_produto = Column(String)
    quantidade_solicitada = Column(Integer)

class LogAuditoria(Base):
    __tablename__ = 'logs_auditoria'

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario = Column(String)
    tabela = Column(String)
    registro_id = Column(Integer)
    acao = Column(String)  # Ex: 'CANCELAMENTO', 'ENTRADA_COMPRA', 'SAIDA_ESTOQUE'
    detalhes = Column(Text)
    data_hora = Column(DateTime, default=datetime.now)

class ManutencaoOrdem(Base):
    __tablename__ = 'manutencao_ordens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ferramenta_id = Column(Integer)  # ForeignKey lógica para Imobilizado
    codigo_ferramenta = Column(String)
    data_entrada = Column(DateTime)
    data_saida = Column(DateTime)
    motivo_falha = Column(String)
    solicitante = Column(String)
    diagnostico = Column(String)
    custo_reparo = Column(Float, default=0.0)
    mecanico_responsavel = Column(String)
    empresa_reparo = Column(String)
    num_orcamento = Column(String)
    status_ordem = Column(String, default='Aberta')
    email_status = Column(String, default='PENDENTE')   # PENDENTE | ENVIADO | FALHOU | N/A
    email_enviado_em = Column(DateTime, nullable=True)
    email_erro = Column(Text, nullable=True)

class Configuracoes(Base):
    __tablename__ = 'configuracoes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome_empresa = Column(String)
    cnpj = Column(String)
    logo_base64 = Column(String)
    categorias_produto = Column(JSON, default=[])
    tipos_material = Column(JSON, default=[])
    tipos_controle = Column(JSON, default=[])
    email_smtp = Column(String)
    senha_smtp = Column(String)
    smtp_host = Column(String)
    smtp_porta = Column(Integer)
    emails_destinatarios = Column(JSON, default=[])
    # ── Módulo Fiscal ────────────────────────────────────────────
    fiscal_habilitado = Column(Integer, default=0)   # 0/1 — compatível com SQLite e PostgreSQL
    fiscal_ambiente = Column(String, default='homologacao')   # 'homologacao' | 'producao'
    fiscal_serie = Column(String, default='1')
    fiscal_numeracao_atual = Column(Integer, default=1)

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=False)
    usuario = Column(String, unique=True, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)
    email = Column(String, nullable=True)


class NotaFiscalRascunho(Base):
    """
    Tabela de trava de segurança fiscal.

    Rascunhos são criados pelo FiscalService com status='PENDENTE'.
    A emissão real só ocorre após aprovação humana (status -> 'EMITIDA').
    Nenhum código desta aplicação deve alterar status diretamente —
    apenas o endpoint POST /api/v1/fiscal/emitir pode fazer isso,
    e somente para usuários com perfil ADMIN ou FISCAL.
    """
    __tablename__ = 'notas_fiscais_rascunho'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    tipo_operacao   = Column(String, nullable=False)          # 'ENTRADA' | 'SAIDA'
    payload_json    = Column(Text, nullable=False)            # JSON do pacote fiscal
    status          = Column(String, default='PENDENTE')      # PENDENTE | EMITIDA | CANCELADA | REJEITADA
    criado_por      = Column(String, nullable=False)          # login do operador
    criado_em       = Column(DateTime, default=datetime.now)
    aprovado_por    = Column(String, nullable=True)           # login do aprovador
    aprovado_em     = Column(DateTime, nullable=True)
    chave_acesso    = Column(String, nullable=True)           # chNFe devolvida pela SEFAZ
    protocolo_sefaz = Column(String, nullable=True)           # nProt devolvido pela SEFAZ
    numero_nf       = Column(String, nullable=True)           # número da NF emitida
    motivo_rejeicao = Column(Text, nullable=True)             # motivo de rejeição/cancelamento


# ── Cadastro de Parceiros (Clientes / Fornecedores) ───────────────────────────
class Parceiro(Base):
    __tablename__ = 'parceiros'

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    tipo                = Column(String, nullable=False, default='CLIENTE')   # CLIENTE | FORNECEDOR | AMBOS
    razao_social        = Column(String, nullable=False)
    nome_fantasia       = Column(String)
    cnpj                = Column(String, index=True)
    ie                  = Column(String)   # Inscrição Estadual
    im                  = Column(String)   # Inscrição Municipal
    situacao_cadastral  = Column(String)   # ATIVA | INAPTA | BAIXADA | SUSPENSA
    cep                 = Column(String)
    logradouro          = Column(String)
    numero              = Column(String)
    complemento         = Column(String)
    bairro              = Column(String)
    municipio           = Column(String)
    uf                  = Column(String)
    codigo_ibge         = Column(String)
    telefone            = Column(String)
    email_contato       = Column(String)
    regime_tributario   = Column(String, default='REGIME_NORMAL')  # SIMPLES | REGIME_NORMAL | MEI
    contribuinte_icms   = Column(Integer, default=1)               # 1=contribuinte, 2=isento, 9=não contribuinte
    status              = Column(String, default='ATIVO')          # ATIVO | INATIVO
    status_consulta     = Column(String, default='NAO_CONSULTADO') # NAO_CONSULTADO | CONSULTADO | ERRO
    origem_dados        = Column(String)                           # MANUAL | BRASILAPI
    data_ultima_consulta = Column(DateTime, nullable=True)
    criado_em           = Column(DateTime, default=datetime.now)
    atualizado_em       = Column(DateTime, default=datetime.now)


# ── Empresa Emitente (dados fiscais do emitente das NF-e) ────────────────────
class EmpresaEmitente(Base):
    __tablename__ = 'empresa_emitente'

    id                = Column(Integer, primary_key=True, autoincrement=True)
    cnpj              = Column(String)
    razao_social      = Column(String)
    nome_fantasia     = Column(String)
    ie                = Column(String)   # Inscrição Estadual
    im                = Column(String)   # Inscrição Municipal
    cnae_principal    = Column(String)
    regime_tributario = Column(String, default='REGIME_NORMAL')  # SIMPLES | REGIME_NORMAL | MEI
    cep               = Column(String)
    logradouro        = Column(String)
    numero            = Column(String)
    complemento       = Column(String)
    bairro            = Column(String)
    municipio         = Column(String)
    uf                = Column(String)
    codigo_ibge       = Column(String)
    telefone          = Column(String)
    email             = Column(String)
    status_sinc       = Column(String, default='PENDENTE')       # PENDENTE | SINCRONIZADO | ERRO
    origem_dados      = Column(String)                           # MANUAL | BRASILAPI
    data_sincronizacao = Column(DateTime, nullable=True)
    ativo             = Column(Integer, default=1)


# ── Regras parametrizáveis de CFOP / natureza de operação ───────────────────
class RegraOperacaoFiscal(Base):
    __tablename__ = 'regras_operacao_fiscal'

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    nome                  = Column(String, nullable=False)
    tipo_operacao         = Column(String)   # REMESSA_CONSERTO | RETORNO_CONSERTO | SAIDA_GERAL | ENTRADA_GERAL
    cfop_interno          = Column(String)   # 5915, 5916, 5102 …
    cfop_interestadual    = Column(String)   # 6915, 6916, 6102 …
    natureza_operacao     = Column(String)
    cst_icms              = Column(String)   # 00, 10, 20, 40, 41 …
    csosn                 = Column(String)   # 101, 102, 400 … (Simples Nacional)
    cst_ipi               = Column(String)   # 50, 53, 99 …
    cst_pis               = Column(String)   # 01, 07, 08 …
    cst_cofins            = Column(String)   # 01, 07, 08 …
    permite_destaque_icms = Column(Integer, default=0)
    ativo                 = Column(Integer, default=1)


# ── Documento Fiscal (NF-e modelo 55 — rascunho estruturado) ────────────────
class DocumentoFiscal(Base):
    __tablename__ = 'documentos_fiscais'

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    subtipo             = Column(String, nullable=False)  # REMESSA_CONSERTO | RETORNO_CONSERTO | SAIDA_GERAL | ENTRADA_GERAL
    tipo_nf             = Column(String, default='1')     # 0=entrada, 1=saida (tpNF)
    numero              = Column(String)
    serie               = Column(String, default='1')
    natureza_operacao   = Column(String)
    cfop                = Column(String)
    modelo              = Column(String, default='55')
    versao_schema       = Column(String, default='4.00')
    parceiro_id         = Column(Integer, ForeignKey('parceiros.id', ondelete='SET NULL'), nullable=True)
    emitente_snapshot   = Column(Text)   # JSON snapshot do emitente no momento da emissão
    parceiro_snapshot   = Column(Text)   # JSON snapshot do parceiro no momento da emissão
    doc_vinculado_id    = Column(Integer, ForeignKey('documentos_fiscais.id'), nullable=True)  # remessa ↔ retorno
    chave_acesso        = Column(String, nullable=True)
    protocolo_sefaz     = Column(String, nullable=True)
    status              = Column(String, default='RASCUNHO')  # RASCUNHO | PRONTA_EMISSAO | EMITIDA | CANCELADA | REJEITADA
    criado_por          = Column(String, nullable=False)
    criado_em           = Column(DateTime, default=datetime.now)
    aprovado_por        = Column(String, nullable=True)
    aprovado_em         = Column(DateTime, nullable=True)
    motivo_rejeicao     = Column(Text, nullable=True)
    valor_total         = Column(Float, default=0.0)
    observacao          = Column(Text)
    # ── Informações operacionais (Remessa/Retorno Conserto) ──────────
    num_os              = Column(String, nullable=True)   # Número da OS de manutenção
    asset_tag           = Column(String, nullable=True)   # Tag/patrimônio do bem
    num_serie           = Column(String, nullable=True)   # Número de série do bem
    # ── infAdic / complementar ───────────────────────────────────────
    info_complementar   = Column(Text, nullable=True)     # infCpl — texto legal + OS/patrimônio/série
    # ── Transporte (transp.modFrete) ─────────────────────────────────
    mod_frete           = Column(String, default='9')     # 0=emit, 1=dest, 2=terceiros, 9=sem frete
    # ── ide adicionais ────────────────────────────────────────────────
    ind_final           = Column(Integer, default=0)      # 0=não consumidor final, 1=consumidor final
    ind_pres            = Column(Integer, default=0)      # 0=não se aplica, 1=presencial, 2=internet
    # ── Histórico de status ──────────────────────────────────────────
    status_historico    = Column(JSON, default=list)      # [{status, data, usuario, obs}]

    parceiro            = relationship("Parceiro", backref="documentos_fiscais")
    itens               = relationship("DocumentoFiscalItem", backref="documento",
                                       cascade="all, delete-orphan", lazy="select")


# ── Itens do Documento Fiscal ────────────────────────────────────────────────
class DocumentoFiscalItem(Base):
    __tablename__ = 'documentos_fiscais_itens'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    documento_id    = Column(Integer, ForeignKey('documentos_fiscais.id', ondelete='CASCADE'), nullable=False)
    sequencia       = Column(Integer, nullable=False)   # nItem
    codigo_produto  = Column(String)
    descricao       = Column(String)
    ncm             = Column(String)
    cfop            = Column(String)
    unidade         = Column(String, default='UN')
    quantidade      = Column(Float)
    valor_unitario  = Column(Float)
    valor_total     = Column(Float)
    cst_icms        = Column(String)
    csosn           = Column(String)
    # ── Campos NF-e completos (SEFAZ layout 4.00) ────────────────────
    c_ean           = Column(String, default='SEM GTIN')   # cEAN
    c_ean_trib      = Column(String, default='SEM GTIN')   # cEANTrib
    ind_tot         = Column(Integer, default=1)            # 1=compõe total NF
    x_ped           = Column(String, nullable=True)         # número do pedido
    n_item_ped      = Column(String, nullable=True)         # item do pedido
    orig_icms       = Column(String, default='0')           # origem: 0=Nacional, 4=Importado
    cest            = Column(String, nullable=True)         # CEST 7 dígitos (ST)
    ipi_cst         = Column(String, nullable=True)         # CST IPI: 50, 53, 99 …
    pis_cst         = Column(String, nullable=True)         # CST PIS: 01, 07, 08 …
    cofins_cst      = Column(String, nullable=True)         # CST COFINS: 01, 07, 08 …


# ── Log de consultas CNPJ ────────────────────────────────────────────────────
class CnpjQueryLog(Base):
    __tablename__ = 'cnpj_query_logs'

    id                = Column(Integer, primary_key=True, autoincrement=True)
    cnpj              = Column(String, nullable=False, index=True)
    status            = Column(String)          # SUCESSO | ERRO | RATE_LIMIT
    fonte_dados       = Column(String, default='BRASILAPI')
    tempo_resposta_ms = Column(Integer)
    mensagem_erro     = Column(Text, nullable=True)
    consultado_por    = Column(String)
    consultado_em     = Column(DateTime, default=datetime.now)


# ── Cadastro Mestre de Localizações (Bin Addresses) ─────────────────────────
class Localizacao(Base):
    __tablename__ = 'localizacoes'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    filial      = Column(String, nullable=False, index=True)
    codigo      = Column(String, nullable=False, index=True)
    descricao   = Column(String)
    zona        = Column(String)
    doca_polo   = Column(String)
    status      = Column(String, default='ATIVO')   # ATIVO | INATIVO
    created_at  = Column(DateTime, default=datetime.now)
    updated_at  = Column(DateTime, default=datetime.now)
    created_by  = Column(String)
    updated_by  = Column(String)


# ── Estoque Mínimo e Máximo por Produto/Filial ───────────────────────────────
class EstoqueMinMax(Base):
    __tablename__ = 'estoque_minmax'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    produto_codigo  = Column(String, nullable=False, index=True)
    filial          = Column(String)
    estoque_minimo  = Column(Float, default=0.0)
    estoque_maximo  = Column(Float, default=0.0)
    unidade_medida  = Column(String, default='UN')
    ativo           = Column(Integer, default=1)
    observacao      = Column(Text)
    created_at      = Column(DateTime, default=datetime.now)
    updated_at      = Column(DateTime, default=datetime.now)
    created_by      = Column(String)
    updated_by      = Column(String)


# ── Estoque de Segurança (Safety Stock) ─────────────────────────────────────
class EstoqueSeguranca(Base):
    __tablename__ = 'estoque_seguranca'

    id                          = Column(Integer, primary_key=True, autoincrement=True)
    produto_codigo              = Column(String, nullable=False, index=True)
    filial                      = Column(String)
    controle_por_lote           = Column(Integer, default=0)   # boolean
    controle_por_ativo          = Column(Integer, default=0)   # boolean
    ativo                       = Column(Integer, default=1)
    janela_historica_dias       = Column(Integer, default=90)
    lead_time_dias              = Column(Integer, default=7)
    nivel_de_servico            = Column(Float, default=0.95)  # ex: 0.95 = 95%
    desvio_padrao               = Column(Float, nullable=True)
    estoque_seguranca_calculado = Column(Float, nullable=True)
    created_at                  = Column(DateTime, default=datetime.now)
    updated_at                  = Column(DateTime, default=datetime.now)
    updated_by                  = Column(String)


# ── Configuração de CFOPs por tipo de operação (parametrizável) ──────────────
class FiscalCfopConfig(Base):
    __tablename__ = 'fiscal_cfop_config'

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    tipo_operacao       = Column(String, nullable=False)   # "Remessa Conserto", "Saída Geral" …
    grupo_operacao      = Column(String)                   # CONSERTO | GERAL | DEVOLUCAO | TRANSFERENCIA
    direcao             = Column(String, nullable=False)   # SAIDA | ENTRADA
    cfop_interno        = Column(String, nullable=False)   # "5915"
    cfop_interestadual  = Column(String, nullable=False)   # "6915"
    natureza_padrao     = Column(String)                   # "Remessa para conserto"
    ativo               = Column(Integer, default=1)
    criado_em           = Column(DateTime, default=datetime.now)
    atualizado_em       = Column(DateTime, default=datetime.now)