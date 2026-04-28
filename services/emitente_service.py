# services/emitente_service.py
"""Serviço de gestão da Empresa Emitente das NF-e."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import EmpresaEmitente
from repositories.emitente_repository import EmitenteRepository
from services.cnpj_service import CnpjService, validar_cnpj
from services.governance_service import GovernanceService

_repo = EmitenteRepository()


class EmitenteService:

    @staticmethod
    def get_ou_criar(session: Session) -> EmpresaEmitente:
        """Retorna o emitente ativo ou cria um registro vazio."""
        e = _repo.get_ativo(session)
        if not e:
            e = EmpresaEmitente(ativo=1)
            _repo.create(session, e)
            session.commit()
        return e

    @staticmethod
    def atualizar(session: Session, dados: dict, usuario: str) -> tuple[bool, str]:
        cnpj_raw = dados.get("cnpj", "")
        cnpj = re.sub(r"\D", "", cnpj_raw)
        if cnpj and not validar_cnpj(cnpj):
            return False, "CNPJ inválido (dígito verificador incorreto)."

        emitente = EmitenteService.get_ou_criar(session)

        for campo in ("razao_social", "nome_fantasia", "ie", "im", "cnae_principal",
                      "regime_tributario", "cep", "logradouro", "numero", "complemento",
                      "bairro", "municipio", "uf", "codigo_ibge", "telefone", "email"):
            if campo in dados:
                setattr(emitente, campo, dados[campo])

        if cnpj:
            emitente.cnpj = cnpj

        GovernanceService.registar_log(
            session, usuario, "empresa_emitente", emitente.id,
            "EMITENTE_ATUALIZADO", "Dados do emitente atualizados."
        )
        session.commit()
        return True, "Dados do emitente salvos com sucesso."

    @staticmethod
    def sincronizar_cnpj(session: Session, usuario: str) -> tuple[bool, str, dict]:
        """Consulta BrasilAPI com o CNPJ do emitente e sincroniza os dados."""
        emitente = EmitenteService.get_ou_criar(session)
        if not emitente.cnpj:
            return False, "CNPJ do emitente não cadastrado.", {}

        resultado = CnpjService.consultar(emitente.cnpj)
        if resultado.get("status") != "SUCESSO":
            emitente.status_sinc = "ERRO"
            session.commit()
            return False, resultado.get("erro", "Erro na consulta."), resultado

        for campo_modelo, campo_api in [
            ("razao_social", "razao_social"),
            ("nome_fantasia", "nome_fantasia"),
            ("logradouro", "logradouro"),
            ("numero", "numero"),
            ("complemento", "complemento"),
            ("bairro", "bairro"),
            ("municipio", "municipio"),
            ("uf", "uf"),
            ("cep", "cep"),
            ("codigo_ibge", "codigo_ibge"),
            ("telefone", "telefone"),
            ("cnae_principal", "cnae_principal"),
        ]:
            val = resultado.get(campo_api, "")
            if val:
                setattr(emitente, campo_modelo, val)

        emitente.status_sinc = "SINCRONIZADO"
        emitente.origem_dados = "BRASILAPI"
        emitente.data_sincronizacao = datetime.now()

        GovernanceService.registar_log(
            session, usuario, "empresa_emitente", emitente.id,
            "EMITENTE_SINCRONIZADO", "Dados do emitente sincronizados via BrasilAPI."
        )
        session.commit()
        return True, "Dados sincronizados com sucesso.", resultado

    @staticmethod
    def serializar(e: EmpresaEmitente) -> dict:
        return {
            "id": e.id,
            "cnpj": e.cnpj or "",
            "razao_social": e.razao_social or "",
            "nome_fantasia": e.nome_fantasia or "",
            "ie": e.ie or "",
            "im": e.im or "",
            "cnae_principal": e.cnae_principal or "",
            "regime_tributario": e.regime_tributario or "REGIME_NORMAL",
            "cep": e.cep or "",
            "logradouro": e.logradouro or "",
            "numero": e.numero or "",
            "complemento": e.complemento or "",
            "bairro": e.bairro or "",
            "municipio": e.municipio or "",
            "uf": e.uf or "",
            "codigo_ibge": e.codigo_ibge or "",
            "telefone": e.telefone or "",
            "email": e.email or "",
            "status_sinc": e.status_sinc or "PENDENTE",
            "origem_dados": e.origem_dados or "MANUAL",
            "data_sincronizacao": str(e.data_sincronizacao) if e.data_sincronizacao else "",
            "ativo": e.ativo,
        }
