import pytest
import os
import hashlib
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.security import hash_senha, verificar_senha, precisa_rehash, criptografar, descriptografar


class TestHashSenha:
    def test_retorna_hash_bcrypt(self):
        h = hash_senha("minhasenha")
        assert h.startswith("$2b$")

    def test_hashes_diferentes_para_mesma_senha(self):
        h1 = hash_senha("abc123")
        h2 = hash_senha("abc123")
        assert h1 != h2  # salt aleatório por design

    def test_hash_nao_expoe_senha(self):
        h = hash_senha("segredo")
        assert "segredo" not in h


class TestVerificarSenha:
    def test_bcrypt_correto(self):
        h = hash_senha("senha_teste")
        assert verificar_senha("senha_teste", h) is True

    def test_bcrypt_incorreto(self):
        h = hash_senha("senha_certa")
        assert verificar_senha("senha_errada", h) is False

    def test_sha256_legado_correto(self):
        sha = hashlib.sha256("legado123".encode()).hexdigest()
        assert verificar_senha("legado123", sha) is True

    def test_sha256_legado_incorreto(self):
        sha = hashlib.sha256("legado123".encode()).hexdigest()
        assert verificar_senha("outrasenha", sha) is False

    def test_hash_invalido_retorna_false(self):
        assert verificar_senha("qualquer", "hash_invalido_curto") is False

    def test_string_vazia_como_hash(self):
        result = verificar_senha("algo", "")
        assert result is False


class TestPrecisaRehash:
    def test_sha256_precisa_rehash(self):
        sha = hashlib.sha256("senha".encode()).hexdigest()
        assert precisa_rehash(sha) is True

    def test_bcrypt_nao_precisa_rehash(self):
        h = hash_senha("senha")
        assert precisa_rehash(h) is False

    def test_string_curta_nao_precisa_rehash(self):
        assert precisa_rehash("abc") is False


class TestFernet:
    def setup_method(self):
        from cryptography.fernet import Fernet
        self._chave = Fernet.generate_key().decode()

    def test_criptografar_descriptografar(self):
        os.environ["FERNET_KEY"] = self._chave
        cifrado = criptografar("senha_smtp_secreta")
        assert cifrado != "senha_smtp_secreta"
        claro = descriptografar(cifrado)
        assert claro == "senha_smtp_secreta"

    def test_sem_chave_retorna_original(self):
        os.environ.pop("FERNET_KEY", None)
        assert criptografar("texto") == "texto"
        assert descriptografar("texto") == "texto"

    def test_criptografar_string_vazia(self):
        os.environ["FERNET_KEY"] = self._chave
        assert criptografar("") == ""

    def test_descriptografar_texto_nao_cifrado(self):
        os.environ["FERNET_KEY"] = self._chave
        # Texto sem cifrar deve retornar o próprio texto (fallback de migração)
        result = descriptografar("texto_plano_sem_cifrar")
        assert result == "texto_plano_sem_cifrar"

    def teardown_method(self):
        os.environ.pop("FERNET_KEY", None)
