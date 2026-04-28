# services/cnpj_service.py
"""
Serviço de consulta e validação de CNPJ.

Provider pattern:
  NullProvider    — estado não configurado (retorna erro imediato)
  BrasilAPIProvider — API pública gratuita, sem autenticação, cache TTL 24h

Validação por dígito verificador: algoritmo módulo 11 (Receita Federal).
"""
from __future__ import annotations

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Cache em memória: {cnpj_limpo: {"dados": dict, "ts": datetime}}
_cache: dict[str, dict] = {}
_CACHE_TTL_H = 24


def _cache_get(cnpj: str) -> Optional[dict]:
    entry = _cache.get(cnpj)
    if entry and datetime.now() - entry["ts"] < timedelta(hours=_CACHE_TTL_H):
        return entry["dados"]
    return None


def _cache_set(cnpj: str, dados: dict) -> None:
    _cache[cnpj] = {"dados": dados, "ts": datetime.now()}


# ---------------------------------------------------------------------------
# Validação por dígito verificador (módulo 11)
# ---------------------------------------------------------------------------

def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ pelo formato E pelo algoritmo módulo 11."""
    n = re.sub(r"\D", "", cnpj)
    if len(n) != 14 or len(set(n)) == 1:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(n[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if d1 != int(n[12]):
        return False

    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(n[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    return d2 == int(n[13])


def formatar_cnpj(cnpj: str) -> str:
    n = re.sub(r"\D", "", cnpj)
    if len(n) == 14:
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    return cnpj


# ---------------------------------------------------------------------------
# Provider BrasilAPI
# ---------------------------------------------------------------------------

class BrasilAPIProvider:
    """Consulta CNPJ via BrasilAPI (gratuita, sem autenticação)."""

    BASE_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

    @classmethod
    def consultar(cls, cnpj_limpo: str) -> dict:
        """
        Retorna dict com dados da empresa ou {"erro": str, "status": "ERRO"}.
        Usa cache em memória com TTL de 24 h para evitar rate-limit.
        """
        cached = _cache_get(cnpj_limpo)
        if cached is not None:
            return cached

        inicio = time.monotonic()
        url = cls.BASE_URL.format(cnpj=cnpj_limpo)
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
            elapsed_ms = int((time.monotonic() - inicio) * 1000)

            if resp.status_code == 200:
                dados = resp.json()
                resultado = {
                    "status": "SUCESSO",
                    "cnpj": cnpj_limpo,
                    "razao_social": dados.get("razao_social") or dados.get("nome", ""),
                    "nome_fantasia": dados.get("nome_fantasia", ""),
                    "situacao_cadastral": (dados.get("descricao_situacao_cadastral") or
                                           dados.get("situacao_cadastral", "")),
                    "logradouro": dados.get("logradouro", ""),
                    "numero": dados.get("numero", ""),
                    "complemento": dados.get("complemento", ""),
                    "bairro": dados.get("bairro", ""),
                    "municipio": dados.get("municipio", ""),
                    "uf": dados.get("uf", ""),
                    "cep": re.sub(r"\D", "", dados.get("cep", "")),
                    "codigo_ibge": dados.get("codigo_municipio_ibge", "") or dados.get("codigo_ibge", ""),
                    "telefone": dados.get("ddd_telefone_1", ""),
                    "email": dados.get("email", ""),
                    "cnae_principal": str(dados.get("cnae_fiscal", "") or ""),
                    "porte": dados.get("descricao_porte", ""),
                    "capital_social": dados.get("capital_social", 0),
                    "data_inicio_atividade": dados.get("data_inicio_atividade", ""),
                    "tempo_resposta_ms": elapsed_ms,
                }
                _cache_set(cnpj_limpo, resultado)
                return resultado

            if resp.status_code == 429:
                return {"status": "RATE_LIMIT", "erro": "Rate limit da BrasilAPI atingido. Tente novamente em instantes."}

            return {"status": "ERRO", "erro": f"BrasilAPI retornou HTTP {resp.status_code}"}

        except httpx.TimeoutException:
            return {"status": "ERRO", "erro": "Timeout na consulta BrasilAPI (>10 s)"}
        except Exception as exc:
            logger.warning("Falha BrasilAPIProvider: %s", exc)
            return {"status": "ERRO", "erro": str(exc)}


# ---------------------------------------------------------------------------
# Fachada pública
# ---------------------------------------------------------------------------

class CnpjService:

    @staticmethod
    def validar(cnpj: str) -> tuple[bool, str]:
        """Valida CNPJ. Retorna (valido, mensagem)."""
        n = re.sub(r"\D", "", cnpj)
        if len(n) != 14:
            return False, "CNPJ deve ter 14 dígitos."
        if not validar_cnpj(n):
            return False, "CNPJ inválido (dígito verificador incorreto)."
        return True, "CNPJ válido."

    @staticmethod
    def consultar(cnpj: str) -> dict:
        """
        Consulta CNPJ. Sempre valida dígitos antes de consultar a API.
        Retorna dict com status: SUCESSO | ERRO | RATE_LIMIT.
        """
        n = re.sub(r"\D", "", cnpj)
        valido, msg = CnpjService.validar(n)
        if not valido:
            return {"status": "ERRO", "erro": msg}
        return BrasilAPIProvider.consultar(n)

    @staticmethod
    def limpar_cache(cnpj: str = "") -> None:
        """Remove entrada do cache. Sem argumento limpa tudo."""
        if cnpj:
            _cache.pop(re.sub(r"\D", "", cnpj), None)
        else:
            _cache.clear()
