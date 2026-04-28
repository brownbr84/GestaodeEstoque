# services/parceiro_service.py
"""Serviço de gestão de Parceiros (Clientes / Fornecedores)."""
from __future__ import annotations

import re
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Parceiro, CnpjQueryLog
from repositories.parceiro_repository import ParceiroRepository
from services.cnpj_service import CnpjService, validar_cnpj
from services.governance_service import GovernanceService

_repo = ParceiroRepository()


class ParceiroService:

    @staticmethod
    def criar(session: Session, dados: dict, usuario: str) -> tuple[bool, str, Optional[Parceiro]]:
        cnpj_raw = dados.get("cnpj", "")
        cnpj = re.sub(r"\D", "", cnpj_raw)

        if cnpj and not validar_cnpj(cnpj):
            return False, "CNPJ inválido (dígito verificador incorreto).", None

        if cnpj and _repo.get_by_cnpj(session, cnpj):
            return False, f"Já existe um parceiro com o CNPJ {cnpj}.", None

        parceiro = Parceiro(
            tipo=dados.get("tipo", "CLIENTE"),
            razao_social=dados["razao_social"],
            nome_fantasia=dados.get("nome_fantasia", ""),
            cnpj=cnpj or None,
            ie=dados.get("ie", ""),
            im=dados.get("im", ""),
            cep=dados.get("cep", ""),
            logradouro=dados.get("logradouro", ""),
            numero=dados.get("numero", ""),
            complemento=dados.get("complemento", ""),
            bairro=dados.get("bairro", ""),
            municipio=dados.get("municipio", ""),
            uf=dados.get("uf", ""),
            codigo_ibge=dados.get("codigo_ibge", ""),
            telefone=dados.get("telefone", ""),
            email_contato=dados.get("email_contato", ""),
            regime_tributario=dados.get("regime_tributario", "REGIME_NORMAL"),
            contribuinte_icms=int(dados.get("contribuinte_icms", 1)),
            status="ATIVO",
            status_consulta="NAO_CONSULTADO",
            origem_dados="MANUAL",
            criado_em=datetime.now(),
            atualizado_em=datetime.now(),
        )
        _repo.create(session, parceiro)
        GovernanceService.registar_log(
            session, usuario, "parceiros", parceiro.id,
            "PARCEIRO_CRIADO", f"Parceiro '{parceiro.razao_social}' criado manualmente."
        )
        session.commit()
        return True, "Parceiro criado com sucesso.", parceiro

    @staticmethod
    def atualizar(session: Session, parceiro_id: int, dados: dict, usuario: str) -> tuple[bool, str]:
        parceiro = _repo.get_by_id(session, parceiro_id)
        if not parceiro:
            return False, "Parceiro não encontrado."

        cnpj_raw = dados.get("cnpj", "")
        cnpj = re.sub(r"\D", "", cnpj_raw)
        if cnpj and not validar_cnpj(cnpj):
            return False, "CNPJ inválido."

        for campo in ("tipo", "razao_social", "nome_fantasia", "ie", "im",
                      "cep", "logradouro", "numero", "complemento", "bairro",
                      "municipio", "uf", "codigo_ibge", "telefone",
                      "email_contato", "regime_tributario"):
            if campo in dados:
                setattr(parceiro, campo, dados[campo])

        if "contribuinte_icms" in dados:
            parceiro.contribuinte_icms = int(dados["contribuinte_icms"])
        if cnpj:
            parceiro.cnpj = cnpj
        if "status" in dados:
            parceiro.status = dados["status"]

        parceiro.atualizado_em = datetime.now()
        GovernanceService.registar_log(
            session, usuario, "parceiros", parceiro_id,
            "PARCEIRO_ATUALIZADO", f"Parceiro #{parceiro_id} atualizado."
        )
        session.commit()
        return True, "Parceiro atualizado."

    @staticmethod
    def enriquecer_cnpj(session: Session, parceiro_id: int, usuario: str) -> tuple[bool, str, dict]:
        """Consulta BrasilAPI e atualiza dados do parceiro com as informações retornadas."""
        parceiro = _repo.get_by_id(session, parceiro_id)
        if not parceiro:
            return False, "Parceiro não encontrado.", {}
        if not parceiro.cnpj:
            return False, "Parceiro não possui CNPJ cadastrado.", {}

        resultado = CnpjService.consultar(parceiro.cnpj)

        log = CnpjQueryLog(
            cnpj=parceiro.cnpj,
            status=resultado.get("status", "ERRO"),
            fonte_dados="BRASILAPI",
            tempo_resposta_ms=resultado.get("tempo_resposta_ms"),
            mensagem_erro=resultado.get("erro") if resultado.get("status") != "SUCESSO" else None,
            consultado_por=usuario,
            consultado_em=datetime.now(),
        )
        session.add(log)

        if resultado.get("status") != "SUCESSO":
            parceiro.status_consulta = "ERRO"
            parceiro.atualizado_em = datetime.now()
            session.commit()
            return False, resultado.get("erro", "Erro na consulta CNPJ."), resultado

        for campo_modelo, campo_api in [
            ("razao_social", "razao_social"),
            ("nome_fantasia", "nome_fantasia"),
            ("situacao_cadastral", "situacao_cadastral"),
            ("logradouro", "logradouro"),
            ("numero", "numero"),
            ("complemento", "complemento"),
            ("bairro", "bairro"),
            ("municipio", "municipio"),
            ("uf", "uf"),
            ("cep", "cep"),
            ("codigo_ibge", "codigo_ibge"),
            ("telefone", "telefone"),
        ]:
            val = resultado.get(campo_api, "")
            if val:
                setattr(parceiro, campo_modelo, val)

        parceiro.status_consulta = "CONSULTADO"
        parceiro.origem_dados = "BRASILAPI"
        parceiro.data_ultima_consulta = datetime.now()
        parceiro.atualizado_em = datetime.now()

        GovernanceService.registar_log(
            session, usuario, "parceiros", parceiro_id,
            "CNPJ_ENRIQUECIDO",
            f"Dados do parceiro #{parceiro_id} atualizados via BrasilAPI."
        )
        session.commit()
        return True, "Dados atualizados via BrasilAPI.", resultado

    @staticmethod
    def excluir(session: Session, parceiro_id: int, usuario: str) -> tuple[bool, str]:
        parceiro = _repo.get_by_id(session, parceiro_id)
        if not parceiro:
            return False, "Parceiro não encontrado."
        parceiro.status = "INATIVO"
        parceiro.atualizado_em = datetime.now()
        GovernanceService.registar_log(
            session, usuario, "parceiros", parceiro_id,
            "PARCEIRO_INATIVADO", f"Parceiro '{parceiro.razao_social}' inativado."
        )
        session.commit()
        return True, "Parceiro inativado com sucesso."

    @staticmethod
    def serializar(p: Parceiro) -> dict:
        return {
            "id": p.id,
            "tipo": p.tipo,
            "razao_social": p.razao_social,
            "nome_fantasia": p.nome_fantasia or "",
            "cnpj": p.cnpj or "",
            "ie": p.ie or "",
            "im": p.im or "",
            "situacao_cadastral": p.situacao_cadastral or "",
            "cep": p.cep or "",
            "logradouro": p.logradouro or "",
            "numero": p.numero or "",
            "complemento": p.complemento or "",
            "bairro": p.bairro or "",
            "municipio": p.municipio or "",
            "uf": p.uf or "",
            "codigo_ibge": p.codigo_ibge or "",
            "telefone": p.telefone or "",
            "email_contato": p.email_contato or "",
            "regime_tributario": p.regime_tributario or "REGIME_NORMAL",
            "contribuinte_icms": p.contribuinte_icms or 1,
            "status": p.status or "ATIVO",
            "status_consulta": p.status_consulta or "NAO_CONSULTADO",
            "origem_dados": p.origem_dados or "MANUAL",
            "data_ultima_consulta": str(p.data_ultima_consulta) if p.data_ultima_consulta else "",
            "criado_em": str(p.criado_em) if p.criado_em else "",
        }
