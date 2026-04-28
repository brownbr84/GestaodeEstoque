import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.models import Usuario, Configuracoes
from utils.security import hash_senha


def _criar_usuario(session, usuario="admin", perfil="Admin", senha="senha123"):
    u = Usuario(nome=usuario.capitalize(), usuario=usuario, senha=hash_senha(senha), perfil=perfil)
    session.add(u)
    session.commit()
    return u


def _token(client, db_session, usuario="admin", senha="senha123", perfil="Admin"):
    _criar_usuario(db_session, usuario=usuario, senha=senha, perfil=perfil)
    resp = client.post("/api/v1/auth/login", json={"usuario": usuario, "senha": senha})
    return resp.json()["access_token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


class TestConfiguracoes:
    def test_get_404_sem_config(self, client, db_session):
        token = _token(client, db_session)
        resp = client.get("/api/v1/configuracoes", headers=_hdr(token))
        assert resp.status_code == 404

    def test_get_config_existente(self, client, db_session):
        token = _token(client, db_session)
        db_session.add(Configuracoes(nome_empresa="Empresa", cnpj="", fiscal_numeracao_atual=1))
        db_session.commit()
        resp = client.get("/api/v1/configuracoes", headers=_hdr(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["nome_empresa"] == "Empresa"
        assert "senha_smtp" not in body  # nunca exposta

    def test_put_config(self, client, db_session):
        token = _token(client, db_session)
        db_session.add(Configuracoes(nome_empresa="Old", cnpj="", fiscal_numeracao_atual=1))
        db_session.commit()
        resp = client.put(
            "/api/v1/configuracoes",
            json={"nome_empresa": "New Corp", "cnpj": "", "logo_base64": ""},
            headers=_hdr(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sucesso"


class TestGestaoUsuariosRBAC:
    def test_admin_lista_usuarios(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        resp = client.get("/api/v1/usuarios", headers=_hdr(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_operador_nao_lista_usuarios(self, client, db_session):
        token = _token(client, db_session, usuario="op", perfil="Operador")
        resp = client.get("/api/v1/usuarios", headers=_hdr(token))
        assert resp.status_code == 403

    def test_admin_cria_usuario(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        resp = client.post(
            "/api/v1/usuarios",
            json={"nome": "Novo", "usuario": "novo_user", "senha": "pass123", "perfil": "Operador"},
            headers=_hdr(token),
        )
        assert resp.status_code == 200

    def test_usuario_duplicado_409(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        dados = {"nome": "Admin", "usuario": "admin", "senha": "x", "perfil": "Admin"}
        resp = client.post("/api/v1/usuarios", json=dados, headers=_hdr(token))
        assert resp.status_code == 409

    def test_perfil_invalido_400(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        dados = {"nome": "X", "usuario": "x_user", "senha": "x", "perfil": "SuperUser"}
        resp = client.post("/api/v1/usuarios", json=dados, headers=_hdr(token))
        assert resp.status_code == 400

    def test_operador_nao_cria_usuario(self, client, db_session):
        token = _token(client, db_session, usuario="op", perfil="Operador")
        dados = {"nome": "X", "usuario": "x_user", "senha": "x", "perfil": "Operador"}
        resp = client.post("/api/v1/usuarios", json=dados, headers=_hdr(token))
        assert resp.status_code == 403

    def test_admin_deleta_outro_usuario(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        # Cria um segundo usuário para deletar
        resp = client.post(
            "/api/v1/usuarios",
            json={"nome": "ToDelete", "usuario": "todel", "senha": "x", "perfil": "Operador"},
            headers=_hdr(token),
        )
        resp = client.delete("/api/v1/usuarios/todel", headers=_hdr(token))
        assert resp.status_code == 200

    def test_admin_nao_deleta_a_si_mesmo(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        resp = client.delete("/api/v1/usuarios/admin", headers=_hdr(token))
        assert resp.status_code == 400

    def test_alterar_senha_propria(self, client, db_session):
        token = _token(client, db_session, usuario="admin", perfil="Admin")
        resp = client.put(
            "/api/v1/usuarios/senha",
            json={"usuario_alvo": "admin", "nova_senha": "novasenha"},
            headers=_hdr(token),
        )
        assert resp.status_code == 200
