import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from services.manutencao_service import ManutencaoService
from database.models import Imobilizado, ManutencaoOrdem, LogAuditoria


def _criar_ativo(session, qtd=1, status="Disponível"):
    item = Imobilizado(
        codigo="FER-001", descricao="Furadeira", tipo_material="Ativo",
        tipo_controle="TAG", num_tag="TAG-9001",
        quantidade=qtd, status=status, localizacao="Filial A",
    )
    session.add(item)
    session.commit()
    return item


class TestAbrirOrdemManutencao:
    def _abrir(self, db_session, item, motivo="Não liga"):
        with patch("services.manutencao_service.EmailService.enviar", return_value=(False, "SMTP off")):
            return ManutencaoService.abrir_ordem_manutencao(
                db_session, item.id, item.codigo, motivo, "Carlos", "admin"
            )

    def test_abre_os_com_sucesso(self, db_session):
        item = _criar_ativo(db_session)
        ok, msg = self._abrir(db_session, item)
        assert ok is True
        assert "OS-" in msg

    def test_item_nao_encontrado(self, db_session):
        with patch("services.manutencao_service.EmailService.enviar", return_value=(False, "")):
            ok, msg = ManutencaoService.abrir_ordem_manutencao(
                db_session, 9999, "FER-X", "motivo", "Carlos", "admin"
            )
        assert ok is False
        assert "não encontrado" in msg.lower()

    def test_ja_na_oficina_bloqueado(self, db_session):
        item = _criar_ativo(db_session)
        self._abrir(db_session, item)
        ok, msg = self._abrir(db_session, item)
        assert ok is False
        assert "oficina" in msg.lower()

    def test_split_lote_decrementa(self, db_session):
        item = _criar_ativo(db_session, qtd=5)
        self._abrir(db_session, item)
        db_session.refresh(item)
        assert item.quantidade == 4

    def test_unidade_unica_muda_status(self, db_session):
        item = _criar_ativo(db_session, qtd=1)
        self._abrir(db_session, item)
        db_session.refresh(item)
        assert item.status == "Manutenção"
        assert item.localizacao == "Oficina"

    def test_log_auditoria_criado(self, db_session):
        item = _criar_ativo(db_session)
        self._abrir(db_session, item)
        log = db_session.query(LogAuditoria).filter_by(acao="ABERTURA_OS").first()
        assert log is not None


class TestLancarOrcamento:
    def test_lanca_orcamento(self, db_session):
        item = _criar_ativo(db_session)
        with patch("services.manutencao_service.EmailService.enviar", return_value=(False, "")):
            ManutencaoService.abrir_ordem_manutencao(db_session, item.id, item.codigo, "quebrou", "X", "admin")
        os_obj = db_session.query(ManutencaoOrdem).first()
        result = ManutencaoService.lancar_orcamento(
            db_session, os_obj.id, "Diagnóstico OK", 350.0, "Mecânico", "Oficina X", "ORC-001", "admin"
        )
        assert result is True
        db_session.refresh(os_obj)
        assert os_obj.status_ordem == "Aguardando Aprovação"
        assert os_obj.custo_reparo == 350.0

    def test_ordem_inexistente_retorna_false(self, db_session):
        result = ManutencaoService.lancar_orcamento(db_session, 9999, "x", 0, "", "", "", "admin")
        assert result is False


class TestAprovarManutencao:
    def _setup_ordem(self, db_session):
        item = _criar_ativo(db_session)
        with patch("services.manutencao_service.EmailService.enviar", return_value=(False, "")):
            ManutencaoService.abrir_ordem_manutencao(db_session, item.id, item.codigo, "quebrou", "X", "admin")
        return db_session.query(ManutencaoOrdem).first(), item

    def test_aprovar(self, db_session):
        os_obj, _ = self._setup_ordem(db_session)
        result = ManutencaoService.aprovar_manutencao(db_session, os_obj.id, "Aprovar", "gestor")
        assert result is True
        db_session.refresh(os_obj)
        assert os_obj.status_ordem == "Em Execução"

    def test_reprovar_sucateia(self, db_session):
        os_obj, item = self._setup_ordem(db_session)
        result = ManutencaoService.aprovar_manutencao(db_session, os_obj.id, "Reprovar", "gestor")
        assert result is True
        db_session.refresh(os_obj)
        assert os_obj.status_ordem == "Sucateado"
        # Verifica que o item foi sucateado (pode ser o clone ou o original)
        sucateados = db_session.query(Imobilizado).filter_by(status="Sucateado").all()
        assert len(sucateados) >= 1


class TestFinalizarReparo:
    def test_finalizar_retorna_disponivel(self, db_session):
        item = _criar_ativo(db_session)
        with patch("services.manutencao_service.EmailService.enviar", return_value=(False, "")):
            ManutencaoService.abrir_ordem_manutencao(db_session, item.id, item.codigo, "quebrou", "X", "admin")
        os_obj = db_session.query(ManutencaoOrdem).first()
        result = ManutencaoService.finalizar_reparo(
            db_session, os_obj.id, os_obj.ferramenta_id, "Filial A", "admin"
        )
        assert result is True
        item_db = db_session.query(Imobilizado).filter_by(id=os_obj.ferramenta_id).first()
        assert item_db.status == "Disponível"
        assert item_db.localizacao == "Filial A"
