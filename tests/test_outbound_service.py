import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from database.models import Imobilizado, Requisicao, RequisicaoItem, LogAuditoria
from services.outbound_service import OutboundService
from datetime import datetime


def _criar_requisicao(session, status="Pendente", polo="Filial CTG"):
    req = Requisicao(
        solicitante="Fulano", polo_origem=polo, destino_projeto="Obra X",
        status=status, data_solicitacao=datetime.now()
    )
    session.add(req)
    session.flush()
    item = RequisicaoItem(
        requisicao_id=req.id, codigo_produto="P-001",
        descricao_produto="Parafuso", quantidade_solicitada=10
    )
    session.add(item)
    session.commit()
    return req


def _criar_lote(session, qtd=5, polo="Filial CTG", codigo="P-001"):
    lote = Imobilizado(
        codigo=codigo, descricao="Parafuso", quantidade=qtd,
        status="Disponível", localizacao=polo, tipo_material="Consumo",
        tipo_controle="LOTE", num_tag=None,
    )
    session.add(lote)
    session.commit()
    return lote


def _criar_ativo_tag(session, tag="TAG-5001", polo="Filial CTG"):
    item = Imobilizado(
        codigo="FER-002", descricao="Chave de Fenda", quantidade=1,
        num_tag=tag, status="Disponível", localizacao=polo,
        tipo_material="Ativo", tipo_controle="TAG"
    )
    session.add(item)
    session.commit()
    return item


class TestBloqueioSaldoNegativo:
    def test_bloqueio_saldo_negativo(self, db_session):
        lote = _criar_lote(db_session, qtd=5)
        carrinho = [{"id": lote.id, "codigo": "P-001", "tipo": "LOTE/CONSUMO", "qtd_baixar": 10}]
        ok, msg = OutboundService.realizar_baixa_excepcional(
            db_session, carrinho, "Perda", "DOC-001", "Admin", "Filial CTG", "ADMIN"
        )
        assert ok is False
        assert "Saldo insuficiente" in msg
        db_session.refresh(lote)
        assert lote.quantidade == 5


class TestTravaPerfil:
    def test_operador_bloqueado(self, db_session):
        ok, msg = OutboundService.realizar_baixa_excepcional(
            db_session, [], "Ajuste", "DOC-002", "João", "Filial CTG", "OPERADOR"
        )
        assert ok is False
        assert "Operação negada" in msg
        assert "administradores ou gestores" in msg

    def test_admin_autorizado(self, db_session):
        lote = _criar_lote(db_session, qtd=10)
        carrinho = [{"id": lote.id, "codigo": "P-001", "tipo": "LOTE/CONSUMO", "qtd_baixar": 3}]
        ok, msg = OutboundService.realizar_baixa_excepcional(
            db_session, carrinho, "Uso em campo", "DOC-003", "Admin", "Filial CTG", "ADMIN"
        )
        assert ok is True
        db_session.refresh(lote)
        assert lote.quantidade == 7

    def test_gestor_autorizado(self, db_session):
        lote = _criar_lote(db_session, qtd=10)
        carrinho = [{"id": lote.id, "codigo": "P-001", "tipo": "LOTE/CONSUMO", "qtd_baixar": 2}]
        ok, msg = OutboundService.realizar_baixa_excepcional(
            db_session, carrinho, "Ajuste", "DOC-004", "Gestor", "Filial CTG", "GESTOR"
        )
        assert ok is True


class TestCancelarPedido:
    def test_cancelar_pendente(self, db_session):
        req = _criar_requisicao(db_session)
        ok, msg = OutboundService.cancelar_pedido(db_session, req.id, "Motivo teste", "admin")
        assert ok is True
        db_session.refresh(req)
        assert req.status == "Cancelada"
        assert req.motivo_cancelamento == "Motivo teste"
        assert req.cancelado_por == "admin"

    def test_cancelar_inexistente(self, db_session):
        ok, msg = OutboundService.cancelar_pedido(db_session, 99999, "X", "admin")
        assert ok is False
        assert "não encontrado" in msg.lower()

    def test_log_auditoria_cancelamento(self, db_session):
        req = _criar_requisicao(db_session)
        OutboundService.cancelar_pedido(db_session, req.id, "Motivo log", "audit_user")
        log = db_session.query(LogAuditoria).filter_by(acao="CANCELAMENTO").first()
        assert log is not None
        assert log.usuario == "audit_user"


class TestDespachoPedidoWMS:
    def test_despachar_lote(self, db_session):
        req = _criar_requisicao(db_session)
        lote = _criar_lote(db_session, qtd=20)
        itens_pedido = pd.DataFrame([{"codigo": "P-001", "qtd": 5, "exige_tag": False}])
        conferidos_lotes = {"P-001": 5}
        ok, doc_ref, msg = OutboundService.despachar_pedido_wms(
            db_session, req.id, "Filial CTG", "Obra X",
            {}, conferidos_lotes, itens_pedido, "admin"
        )
        assert ok is True
        db_session.refresh(req)
        assert req.status == "Concluída"
        db_session.refresh(lote)
        assert lote.quantidade == 15

    def test_despachar_tag(self, db_session):
        req = _criar_requisicao(db_session)
        ativo = _criar_ativo_tag(db_session)
        itens_pedido = pd.DataFrame([{"codigo": "FER-002", "qtd": 1, "exige_tag": True}])
        conferidos_tags = {"FER-002": [{"tag": "TAG-5001", "metodo": "Sistema"}]}
        ok, doc_ref, msg = OutboundService.despachar_pedido_wms(
            db_session, req.id, "Filial CTG", "Obra X",
            conferidos_tags, {}, itens_pedido, "admin"
        )
        assert ok is True
        db_session.refresh(ativo)
        assert ativo.status in ("Em Uso", "Em Trânsito")

    def test_log_auditoria_despacho(self, db_session):
        req = _criar_requisicao(db_session)
        _criar_lote(db_session, qtd=10)
        itens = pd.DataFrame([{"codigo": "P-001", "qtd": 2, "exige_tag": False}])
        OutboundService.despachar_pedido_wms(
            db_session, req.id, "Filial CTG", "Obra X", {}, {"P-001": 2}, itens, "admin"
        )
        log = db_session.query(LogAuditoria).filter_by(acao="BAIXA_REQUISICAO").first()
        assert log is not None

    def test_saldo_insuficiente_despacho(self, db_session):
        req = _criar_requisicao(db_session)
        _criar_lote(db_session, qtd=1)
        itens = pd.DataFrame([{"codigo": "P-001", "qtd": 5, "exige_tag": False}])
        ok, _, msg = OutboundService.despachar_pedido_wms(
            db_session, req.id, "Filial CTG", "Obra X", {}, {"P-001": 5}, itens, "admin"
        )
        assert ok is False
        assert "Saldo insuficiente" in msg or "Erro" in msg
