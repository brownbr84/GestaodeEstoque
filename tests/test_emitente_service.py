import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from services.emitente_service import EmitenteService
from database.models import EmpresaEmitente

CNPJ_VALIDO = "11222333000181"


class TestGetOuCriar:
    def test_cria_quando_nao_existe(self, db_session):
        e = EmitenteService.get_ou_criar(db_session)
        assert e is not None
        assert e.id is not None
        assert e.ativo == 1

    def test_retorna_existente(self, db_session):
        e1 = EmitenteService.get_ou_criar(db_session)
        e2 = EmitenteService.get_ou_criar(db_session)
        assert e1.id == e2.id

    def test_nao_duplica(self, db_session):
        EmitenteService.get_ou_criar(db_session)
        EmitenteService.get_ou_criar(db_session)
        total = db_session.query(EmpresaEmitente).count()
        assert total == 1


class TestAtualizar:
    def test_atualiza_campos(self, db_session):
        dados = {
            "cnpj": CNPJ_VALIDO,
            "razao_social": "Emitente Teste LTDA",
            "uf": "SP",
            "municipio": "São Paulo",
        }
        ok, msg = EmitenteService.atualizar(db_session, dados, "admin")
        assert ok is True
        e = EmitenteService.get_ou_criar(db_session)
        assert e.razao_social == "Emitente Teste LTDA"
        assert e.cnpj == CNPJ_VALIDO

    def test_cnpj_invalido_rejeitado(self, db_session):
        ok, msg = EmitenteService.atualizar(db_session, {"cnpj": "99999999999999"}, "admin")
        assert ok is False
        assert "inválido" in msg.lower()

    def test_sem_cnpj_atualiza_outros_campos(self, db_session):
        ok, msg = EmitenteService.atualizar(db_session, {"razao_social": "Nova Razão"}, "admin")
        assert ok is True

    def test_audit_log_criado(self, db_session):
        from database.models import LogAuditoria
        EmitenteService.atualizar(db_session, {"razao_social": "Com Log"}, "tester")
        log = db_session.query(LogAuditoria).filter_by(acao="EMITENTE_ATUALIZADO").first()
        assert log is not None
        assert log.usuario == "tester"


class TestSerializar:
    def test_serializar_retorna_dict(self, db_session):
        e = EmitenteService.get_ou_criar(db_session)
        d = EmitenteService.serializar(e)
        assert isinstance(d, dict)
        assert "cnpj" in d
        assert "razao_social" in d
        assert "uf" in d
        assert d["ativo"] == 1


class TestSincronizarCnpj:
    def test_sem_cnpj_retorna_erro(self, db_session):
        ok, msg, dados = EmitenteService.sincronizar_cnpj(db_session, "admin")
        assert ok is False
        assert "CNPJ" in msg

    def test_sucesso_sincronizacao(self, db_session):
        EmitenteService.atualizar(db_session, {"cnpj": CNPJ_VALIDO}, "admin")
        resultado_mock = {
            "status": "SUCESSO",
            "razao_social": "EMPRESA API LTDA",
            "municipio": "Recife",
            "uf": "PE",
            "logradouro": "Rua X",
            "numero": "1",
            "complemento": "",
            "bairro": "Centro",
            "cep": "50000000",
            "codigo_ibge": "2611606",
            "telefone": "81999999999",
            "cnae_principal": "6201500",
            "nome_fantasia": "",
        }
        with patch("services.emitente_service.CnpjService.consultar", return_value=resultado_mock):
            ok, msg, dados = EmitenteService.sincronizar_cnpj(db_session, "admin")
        assert ok is True
        e = EmitenteService.get_ou_criar(db_session)
        assert e.razao_social == "EMPRESA API LTDA"
        assert e.status_sinc == "SINCRONIZADO"
