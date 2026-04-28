import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.parceiro_service import ParceiroService
from repositories.parceiro_repository import ParceiroRepository

CNPJ_VALIDO = "11222333000181"
DADOS_BASE = {
    "razao_social": "Empresa Teste LTDA",
    "nome_fantasia": "Teste",
    "cnpj": CNPJ_VALIDO,
    "tipo": "CLIENTE",
    "municipio": "São Paulo",
    "uf": "SP",
}


class TestParceiroServiceCriar:
    def test_criar_sem_cnpj(self, db_session):
        dados = {"razao_social": "Sem CNPJ SA", "tipo": "FORNECEDOR"}
        ok, msg, p = ParceiroService.criar(db_session, dados, "admin")
        assert ok is True
        assert p is not None
        assert p.id is not None

    def test_criar_com_cnpj_valido(self, db_session):
        ok, msg, p = ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        assert ok is True
        assert p.cnpj == CNPJ_VALIDO
        assert p.status == "ATIVO"

    def test_cnpj_invalido_rejeitado(self, db_session):
        dados = {**DADOS_BASE, "cnpj": "99999999999999"}
        ok, msg, p = ParceiroService.criar(db_session, dados, "admin")
        assert ok is False
        assert p is None
        assert "inválido" in msg.lower()

    def test_cnpj_duplicado_rejeitado(self, db_session):
        ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        ok, msg, p = ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        assert ok is False
        assert "já existe" in msg.lower()

    def test_origem_manual(self, db_session):
        ok, _, p = ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        assert p.origem_dados == "MANUAL"


class TestParceiroServiceAtualizar:
    def test_atualizar_existente(self, db_session):
        _, _, p = ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        ok, msg = ParceiroService.atualizar(db_session, p.id, {"municipio": "Campinas"}, "admin")
        assert ok is True
        db_session.refresh(p)
        assert p.municipio == "Campinas"

    def test_atualizar_inexistente(self, db_session):
        ok, msg = ParceiroService.atualizar(db_session, 99999, {"municipio": "X"}, "admin")
        assert ok is False
        assert "não encontrado" in msg.lower()


class TestParceiroServiceExcluir:
    def test_soft_delete(self, db_session):
        _, _, p = ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        ok, msg = ParceiroService.excluir(db_session, p.id, "admin")
        assert ok is True
        db_session.refresh(p)
        assert p.status == "INATIVO"

    def test_excluir_inexistente(self, db_session):
        ok, msg = ParceiroService.excluir(db_session, 99999, "admin")
        assert ok is False


class TestParceiroRepository:
    def test_get_by_cnpj(self, db_session):
        ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        repo = ParceiroRepository()
        p = repo.get_by_cnpj(db_session, CNPJ_VALIDO)
        assert p is not None
        assert p.razao_social == "Empresa Teste LTDA"

    def test_listar_ativos(self, db_session):
        ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        dados2 = {**DADOS_BASE, "cnpj": "", "razao_social": "Outro Parceiro"}
        ParceiroService.criar(db_session, dados2, "admin")
        repo = ParceiroRepository()
        ativos = repo.listar_ativos(db_session)
        assert len(ativos) >= 2

    def test_listar_filtro_tipo(self, db_session):
        ParceiroService.criar(db_session, DADOS_BASE.copy(), "admin")
        repo = ParceiroRepository()
        clientes = repo.listar_ativos(db_session, tipo="CLIENTE")
        assert all(p.tipo in ("CLIENTE", "AMBOS") for p in clientes)
