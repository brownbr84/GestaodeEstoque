import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.inbound_service import InboundService
from database.models import Imobilizado, Movimentacao, LogAuditoria


def _criar_molde(session, tipo_controle="LOTE", tipo_material="Consumo"):
    molde = Imobilizado(
        codigo="PROD-001",
        descricao="Produto de Teste",
        tipo_controle=tipo_controle,
        tipo_material=tipo_material,
        status="Disponível",
        localizacao="Matriz",
        quantidade=100,
    )
    session.add(molde)
    session.commit()
    return molde


class TestObterProximasTags:
    def test_sem_tags_existentes_comeca_em_1001(self, db_session):
        tags = InboundService.obter_proximas_tags(db_session, 3)
        assert tags == ["TAG-1001", "TAG-1002", "TAG-1003"]

    def test_com_tags_existentes_continua_sequencia(self, db_session):
        db_session.add(Imobilizado(codigo="X", descricao="X", num_tag="TAG-1005", quantidade=1, status="Disponível", localizacao="A"))
        db_session.commit()
        tags = InboundService.obter_proximas_tags(db_session, 2)
        assert tags == ["TAG-1006", "TAG-1007"]


class TestProcessarEntradaCompra:
    def test_produto_nao_encontrado(self, db_session):
        ok, msg, tags = InboundService.processar_entrada_compra(
            db_session, "INEXISTENTE", "Polo A", "NF-001", 100.0, 1, "admin"
        )
        assert ok is False
        assert "não encontrado" in msg.lower()

    def test_entrada_lote(self, db_session):
        _criar_molde(db_session, tipo_controle="LOTE", tipo_material="Consumo")
        ok, msg, tags = InboundService.processar_entrada_compra(
            db_session, "PROD-001", "Polo B", "NF-100", 50.0, 10, "admin"
        )
        assert ok is True
        lote = db_session.query(Imobilizado).filter(
            Imobilizado.codigo == "PROD-001", Imobilizado.localizacao == "Polo B"
        ).first()
        assert lote is not None
        assert lote.quantidade == 10

    def test_entrada_tag_gera_tags_individuais(self, db_session):
        _criar_molde(db_session, tipo_controle="TAG", tipo_material="Ativo")
        ok, msg, tags = InboundService.processar_entrada_compra(
            db_session, "PROD-001", "Polo C", "NF-200", 200.0, 3, "admin"
        )
        assert ok is True
        assert len(tags) == 3
        ativos = db_session.query(Imobilizado).filter(
            Imobilizado.codigo == "PROD-001", Imobilizado.localizacao == "Polo C"
        ).all()
        assert len(ativos) == 3

    def test_auditoria_criada(self, db_session):
        _criar_molde(db_session)
        InboundService.processar_entrada_compra(
            db_session, "PROD-001", "Polo D", "NF-300", 10.0, 5, "usuario_teste"
        )
        log = db_session.query(LogAuditoria).filter_by(acao="ENTRADA_COMPRA").first()
        assert log is not None
        assert log.usuario == "usuario_teste"

    def test_movimentacao_criada(self, db_session):
        _criar_molde(db_session)
        InboundService.processar_entrada_compra(
            db_session, "PROD-001", "Polo E", "NF-400", 10.0, 2, "admin"
        )
        movs = db_session.query(Movimentacao).filter_by(tipo="Entrada via Compra").all()
        assert len(movs) >= 1


class TestEntradaExcepcional:
    def test_operador_bloqueado(self, db_session):
        ok, msg, tags = InboundService.realizar_entrada_excepcional(
            db_session, [], "Ajuste", "DOC-001", "joao", "Polo A", "OPERADOR"
        )
        assert ok is False
        assert "negada" in msg.lower()

    def test_admin_permitido(self, db_session):
        _criar_molde(db_session)
        carrinho = [{"codigo": "PROD-001", "qtd": 5, "valor": 10.0}]
        ok, msg, tags = InboundService.realizar_entrada_excepcional(
            db_session, carrinho, "Ajuste", "DOC-002", "admin", "Polo A", "ADMIN"
        )
        assert ok is True
