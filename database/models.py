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
    
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'), nullable=True)
    
    categoria_rel = relationship("Categoria", backref="produtos")
    fornecedor_rel = relationship("Fornecedor", backref="produtos")

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