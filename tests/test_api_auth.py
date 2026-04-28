import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import jwt as pyjwt
from database.models import Usuario
from utils.security import hash_senha


def _criar_usuario(session, nome="Admin", usuario="admin", perfil="ADMIN", senha="senha123"):
    u = Usuario(nome=nome, usuario=usuario, senha=hash_senha(senha), perfil=perfil)
    session.add(u)
    session.commit()
    return u


class TestLogin:
    def test_login_sucesso(self, client, db_session):
        _criar_usuario(db_session)
        resp = client.post("/api/v1/auth/login", json={"usuario": "admin", "senha": "senha123"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["perfil"] == "ADMIN"

    def test_login_credenciais_invalidas(self, client, db_session):
        _criar_usuario(db_session)
        resp = client.post("/api/v1/auth/login", json={"usuario": "admin", "senha": "errada"})
        assert resp.status_code == 401

    def test_login_usuario_inexistente(self, client, db_session):
        resp = client.post("/api/v1/auth/login", json={"usuario": "naoexiste", "senha": "qualquer"})
        assert resp.status_code == 401

    def test_token_contem_sub_e_perfil(self, client, db_session):
        _criar_usuario(db_session)
        resp = client.post("/api/v1/auth/login", json={"usuario": "admin", "senha": "senha123"})
        token = resp.json()["access_token"]
        from api.endpoints import SECRET_KEY, ALGORITHM
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin"
        assert payload["perfil"] == "ADMIN"

    def test_rehash_sha256_no_login(self, client, db_session):
        import hashlib
        sha_hash = hashlib.sha256("senha123".encode()).hexdigest()
        u = Usuario(nome="Legado", usuario="legado", senha=sha_hash, perfil="OPERADOR")
        db_session.add(u)
        db_session.commit()
        resp = client.post("/api/v1/auth/login", json={"usuario": "legado", "senha": "senha123"})
        assert resp.status_code == 200
        # Após login, hash deve ter sido migrado para bcrypt
        db_session.refresh(u)
        assert u.senha.startswith("$2b$")


class TestRotasProtegidas:
    def _token(self, client, db_session):
        _criar_usuario(db_session)
        resp = client.post("/api/v1/auth/login", json={"usuario": "admin", "senha": "senha123"})
        return resp.json()["access_token"]

    def test_sem_token_retorna_401(self, client, db_session):
        resp = client.get("/api/v1/configuracoes")
        assert resp.status_code == 401

    def test_token_invalido_retorna_401(self, client, db_session):
        resp = client.get("/api/v1/configuracoes", headers={"Authorization": "Bearer token_invalido"})
        assert resp.status_code == 401

    def test_com_token_valido_passa(self, client, db_session):
        from database.models import Configuracoes
        db_session.add(Configuracoes(nome_empresa="Empresa", cnpj="", fiscal_numeracao_atual=1))
        db_session.commit()
        token = self._token(client, db_session)
        resp = client.get("/api/v1/configuracoes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
