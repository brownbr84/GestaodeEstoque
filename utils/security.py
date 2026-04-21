# utils/security.py
"""
TraceBox WMS — Utilitários de Segurança

  1. Senhas de usuário  → bcrypt  (hash unidirecional, salt automático)
  2. Credenciais SMTP   → Fernet  (AES-128 CBC, reversível, chave via .env)
  3. Migração transparente SHA-256 → bcrypt no primeiro login após upgrade
"""
from __future__ import annotations

import hashlib
import logging
import os

import bcrypt as _bcrypt

logger = logging.getLogger(__name__)

_BCRYPT_ROUNDS = 12


# ---------------------------------------------------------------------------
# 1. BCRYPT — senhas de usuário
# ---------------------------------------------------------------------------

def hash_senha(senha_plana: str) -> str:
    """Gera um hash bcrypt da senha. Use ao criar ou alterar senha."""
    return _bcrypt.hashpw(senha_plana.encode(), _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verificar_senha(senha_plana: str, hash_armazenado: str) -> bool:
    """
    Verifica se a senha confere com o hash armazenado.
    Suporta bcrypt (novo) e SHA-256 legado de forma transparente.
    """
    # SHA-256 legado: 64 chars hex sem prefixo $2b$
    if len(hash_armazenado) == 64 and all(c in "0123456789abcdef" for c in hash_armazenado):
        return hashlib.sha256(senha_plana.encode()).hexdigest() == hash_armazenado

    try:
        return _bcrypt.checkpw(senha_plana.encode(), hash_armazenado.encode())
    except Exception as exc:
        logger.error("Erro ao verificar bcrypt: %s", exc)
        return False


def precisa_rehash(hash_armazenado: str) -> bool:
    """Retorna True se o hash precisa ser migrado de SHA-256 para bcrypt."""
    return len(hash_armazenado) == 64 and all(c in "0123456789abcdef" for c in hash_armazenado)


# ---------------------------------------------------------------------------
# 2. FERNET — criptografia reversível para credenciais SMTP
# ---------------------------------------------------------------------------

def _obter_chave_fernet() -> bytes:
    chave = os.getenv("FERNET_KEY", "")
    if not chave:
        logger.warning(
            "FERNET_KEY não definida em .env. "
            "Credenciais SMTP NÃO estarão criptografadas."
        )
        return b""
    return chave.encode()


def criptografar(texto: str) -> str:
    """Criptografa texto com Fernet. Retorna o original se a chave não estiver configurada."""
    if not texto:
        return texto
    chave = _obter_chave_fernet()
    if not chave:
        return texto
    try:
        from cryptography.fernet import Fernet
        return Fernet(chave).encrypt(texto.encode()).decode()
    except Exception as exc:
        logger.error("Erro ao criptografar: %s", exc)
        return texto


def descriptografar(texto_cifrado: str) -> str:
    """Descriptografa texto Fernet. Retorna o original se a chave não estiver configurada."""
    if not texto_cifrado:
        return texto_cifrado
    chave = _obter_chave_fernet()
    if not chave:
        return texto_cifrado
    try:
        from cryptography.fernet import Fernet
        return Fernet(chave).decrypt(texto_cifrado.encode()).decode()
    except Exception:
        # Pode ser texto ainda não criptografado (migração)
        return texto_cifrado
