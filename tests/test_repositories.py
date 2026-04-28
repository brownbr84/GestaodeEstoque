import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.models import Imobilizado, Parceiro, EmpresaEmitente
from repositories.base_repository import BaseRepository
from repositories.parceiro_repository import ParceiroRepository
from repositories.emitente_repository import EmitenteRepository
from repositories.imobilizado_repository import ImobilizadoRepository


class TestBaseRepository:
    def _repo(self):
        return BaseRepository(Imobilizado)

    def test_get_by_id_existente(self, db_session):
        item = Imobilizado(codigo="TEST", descricao="Teste", quantidade=1, status="Disponível", localizacao="A")
        db_session.add(item)
        db_session.commit()
        repo = self._repo()
        found = repo.get_by_id(db_session, item.id)
        assert found is not None
        assert found.codigo == "TEST"

    def test_get_by_id_inexistente(self, db_session):
        repo = self._repo()
        assert repo.get_by_id(db_session, 99999) is None

    def test_get_all(self, db_session):
        db_session.add(Imobilizado(codigo="A", descricao="A", quantidade=1, status="Disponível", localizacao="X"))
        db_session.add(Imobilizado(codigo="B", descricao="B", quantidade=1, status="Disponível", localizacao="Y"))
        db_session.commit()
        repo = self._repo()
        all_items = repo.get_all(db_session)
        assert len(all_items) == 2

    def test_create(self, db_session):
        repo = self._repo()
        item = Imobilizado(codigo="C", descricao="C", quantidade=5, status="Disponível", localizacao="Z")
        repo.create(db_session, item)
        db_session.commit()
        assert item.id is not None

    def test_delete(self, db_session):
        item = Imobilizado(codigo="D", descricao="D", quantidade=1, status="Disponível", localizacao="W")
        db_session.add(item)
        db_session.commit()
        repo = self._repo()
        repo.delete(db_session, item)
        db_session.commit()
        assert repo.get_by_id(db_session, item.id) is None


class TestParceiroRepository:
    def test_get_by_cnpj_encontra(self, db_session):
        p = Parceiro(razao_social="Empresa X", cnpj="11222333000181", tipo="CLIENTE", status="ATIVO")
        db_session.add(p)
        db_session.commit()
        repo = ParceiroRepository()
        found = repo.get_by_cnpj(db_session, "11222333000181")
        assert found is not None
        assert found.razao_social == "Empresa X"

    def test_get_by_cnpj_nao_encontra(self, db_session):
        repo = ParceiroRepository()
        assert repo.get_by_cnpj(db_session, "00000000000000") is None

    def test_listar_ativos_filtra_inativos(self, db_session):
        db_session.add(Parceiro(razao_social="Ativo", tipo="CLIENTE", status="ATIVO"))
        db_session.add(Parceiro(razao_social="Inativo", tipo="CLIENTE", status="INATIVO"))
        db_session.commit()
        repo = ParceiroRepository()
        ativos = repo.listar_ativos(db_session)
        assert all(p.status == "ATIVO" for p in ativos)
        nomes = [p.razao_social for p in ativos]
        assert "Ativo" in nomes
        assert "Inativo" not in nomes

    def test_listar_ativos_filtra_tipo(self, db_session):
        db_session.add(Parceiro(razao_social="Cliente", tipo="CLIENTE", status="ATIVO"))
        db_session.add(Parceiro(razao_social="Fornecedor", tipo="FORNECEDOR", status="ATIVO"))
        db_session.add(Parceiro(razao_social="Ambos", tipo="AMBOS", status="ATIVO"))
        db_session.commit()
        repo = ParceiroRepository()
        clientes = repo.listar_ativos(db_session, tipo="CLIENTE")
        assert all(p.tipo in ("CLIENTE", "AMBOS") for p in clientes)

    def test_buscar_por_razao_social(self, db_session):
        db_session.add(Parceiro(razao_social="Construtora Alpha", tipo="CLIENTE", status="ATIVO"))
        db_session.commit()
        repo = ParceiroRepository()
        result = repo.buscar(db_session, "Alpha")
        assert len(result) == 1
        assert result[0].razao_social == "Construtora Alpha"


class TestEmitenteRepository:
    def test_get_ativo(self, db_session):
        e = EmpresaEmitente(razao_social="Emitente S.A.", ativo=1)
        db_session.add(e)
        db_session.commit()
        repo = EmitenteRepository()
        found = repo.get_ativo(db_session)
        assert found is not None
        assert found.razao_social == "Emitente S.A."

    def test_get_ativo_sem_registro(self, db_session):
        repo = EmitenteRepository()
        assert repo.get_ativo(db_session) is None

    def test_get_ativo_ignora_inativo(self, db_session):
        db_session.add(EmpresaEmitente(razao_social="Inativo", ativo=0))
        db_session.commit()
        repo = EmitenteRepository()
        assert repo.get_ativo(db_session) is None


class TestImobilizadoRepository:
    def test_get_by_codigo(self, db_session):
        db_session.add(Imobilizado(codigo="FER-001", descricao="Furadeira", quantidade=1, status="Disponível", localizacao="A"))
        db_session.commit()
        repo = ImobilizadoRepository()
        found = repo.get_by_codigo(db_session, "FER-001")
        assert found is not None

    def test_get_by_codigo_inexistente(self, db_session):
        repo = ImobilizadoRepository()
        assert repo.get_by_codigo(db_session, "INEXISTENTE") is None
