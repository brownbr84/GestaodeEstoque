import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.governance_service import GovernanceService
from database.models import LogAuditoria


class TestGovernanceService:
    def test_registar_log_cria_entrada(self, db_session):
        GovernanceService.registar_log(
            db_session, "user1", "imobilizado", 42, "ENTRADA_COMPRA", "Detalhe teste"
        )
        db_session.commit()
        log = db_session.query(LogAuditoria).filter_by(acao="ENTRADA_COMPRA").first()
        assert log is not None
        assert log.usuario == "user1"
        assert log.tabela == "imobilizado"
        assert log.registro_id == 42
        assert log.detalhes == "Detalhe teste"
        assert log.data_hora is not None

    def test_multiplos_logs_independentes(self, db_session):
        GovernanceService.registar_log(db_session, "u1", "t1", 1, "A1", "d1")
        GovernanceService.registar_log(db_session, "u2", "t2", 2, "A2", "d2")
        db_session.commit()
        total = db_session.query(LogAuditoria).count()
        assert total == 2

    def test_falha_na_sessao_propaga_excecao(self, db_session):
        """Se a sessão estiver corrompida, o serviço deve levantar a exceção (não engolir)."""
        from unittest.mock import patch, MagicMock
        bad_session = MagicMock()
        bad_session.add.side_effect = RuntimeError("DB boom")
        with pytest.raises(RuntimeError, match="DB boom"):
            GovernanceService.registar_log(bad_session, "u", "t", 1, "A", "d")
