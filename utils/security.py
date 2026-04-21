# utils/security.py
"""
TraceBox WMS — Utilitários de Segurança
========================================
Centraliza TODA a lógica criptográfica da aplicação:

  1. Senhas de usuário  → bcrypt  (hash unidirecional, com salt automático)
  2. Credenciais SMTP   → Fernet  (AES-128 CBC, reversível, chave via .env)
  3. Migração transparente SHA-256 → bcrypt no primeiro login após upgrade
"""
from __future__ import annotations

import hashlib
import logging
import os

from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. CONTEXTO BCRYPT — senhas de usuário
# ---------------------------------------------------------------------------
# deprecated="auto" faz o passlib detectar e migrar hashes antigos
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,          # 2^12 iterações — adequado para 2026
)


def hash_senha(senha_plana: str) -> str:
    """Gera um hash bcrypt da senha. Use ao criar ou alterar senha."""
    try:
        return _pwd_context.hash(senha_plana)
    except Exception as exc:
        # Fallback seguro: se bcrypt falhar (ex: incompatibilidade de versão),
        # retorna SHA-256. O operador verá um aviso no log.
        logger.error(
            "bcrypt indisponível (%s). Usando SHA-256 como fallback de emergência.", exc
        )
        return hashlib.sha256(senha_plana.encode()).hexdigest()


def verificar_senha(senha_plana: str, hash_armazenado: str) -> bool:
    """
    Verifica se a senha confere com o hash armazenado.
    Suporta tanto bcrypt (novo) quanto SHA-256 legado de forma transparente.
    """
    # SHA-256 legado: 64 chars hex sem prefixo $2b$
    if len(hash_armazenado) == 64 and all(c in "0123456789abcdef" for c in hash_armazenado):
        return hashlib.sha256(senha_plana.encode()).hexdigest() == hash_armazenado

    # Tenta bcrypt
    try:
        return _pwd_context.verify(senha_plana, hash_armazenado)
    except Exception as exc:
        logger.error("Erro ao verificar bcrypt: %s", exc)
        return False


def precisa_rehash(hash_armazenado: str) -> bool:
    """
    Retorna True se o hash precisa ser atualizado para bcrypt.
    Só retorna True se o bcrypt estiver operacional (evita loop de erro).
    """
    # SHA-256 legado
    if len(hash_armazenado) == 64 and all(c in "0123456789abcdef" for c in hash_armazenado):
        # Testa se bcrypt está funcional antes de sinalizar rehash
        try:
            _pwd_context.hash("test_bcrypt_ok")
            return True
        except Exception:
            return False  # bcrypt com problema — não tenta rehash

    try:
        return _pwd_context.needs_update(hash_armazenado)
    except Exception:
        return False



# ---------------------------------------------------------------------------
# 2. FERNET — criptografia reversível para credenciais SMTP
# ---------------------------------------------------------------------------
def _obter_chave_fernet() -> bytes:
    """
    Obtém a chave Fernet do ambiente.
    A chave DEVE ter 32 bytes codificados em base64-url (44 chars).
    Gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    chave = os.getenv("FERNET_KEY", "")
    if not chave:
        logger.warning(
            "FERNET_KEY não definida em .env. "
            "Credenciais SMTP NÃO estarão criptografadas. "
            "Gere uma chave e adicione ao .env."
        )
        return b""
    return chave.encode()


def criptografar(texto: str) -> str:
    """
    Criptografa texto com Fernet.
    Retorna o texto cifrado como string, ou o original se a chave não estiver configurada.
    """
    if not texto:
        return texto
    chave = _obter_chave_fernet()
    if not chave:
        return texto  # Degradação segura: sem chave, retorna sem cripto (com aviso)
    try:
        from cryptography.fernet import Fernet
        f = Fernet(chave)
        return f.encrypt(texto.encode()).decode()
    except Exception as exc:
        logger.error("Erro ao criptografar: %s", exc)
        return texto


def descriptografar(texto_cifrado: str) -> str:
    """
    Descriptografa texto cifrado com Fernet.
    Retorna o texto original, ou o próprio cifrado se a chave não estiver configurada.
    """
    if not texto_cifrado:
        return texto_cifrado
    chave = _obter_chave_fernet()
    if not chave:
        return texto_cifrado
    try:
        from cryptography.fernet import Fernet
        f = Fernet(chave)
        return f.decrypt(texto_cifrado.encode()).decode()
    except Exception:
        # Pode ser texto ainda não criptografado (migração) — retorna como está
        return texto_cifrado
