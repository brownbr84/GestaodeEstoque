# services/documento_fiscal_service.py
"""
Serviço de Documentos Fiscais (NF-e modelo 55).

Arquitetura de trava de segurança:
  1. Este serviço NUNCA emite NF-e diretamente.
  2. Cria o documento com status=RASCUNHO.
  3. A emissão real exige aprovação humana via endpoint dedicado.

CFOPs por tipo de operação (parametrizados via RegraOperacaoFiscal):
  REMESSA_CONSERTO  → 5915 (interna) / 6915 (interestadual)
  RETORNO_CONSERTO  → 5916 (interna) / 6916 (interestadual)
  SAIDA_GERAL       → 5102 (interna) / 6102 (interestadual)
  ENTRADA_GERAL     → 1102 (interna) / 2102 (interestadual)

CST ICMS para Remessa/Retorno Conserto: 41 (não tributada)
CST IPI  para Remessa/Retorno Conserto: 53 (nacional isento)
CST PIS/COFINS para Remessa/Retorno: 07 (isento)
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import (
    DocumentoFiscal, DocumentoFiscalItem, EmpresaEmitente, Parceiro,
    RegraOperacaoFiscal,
)
from repositories.documento_fiscal_repository import (
    DocumentoFiscalRepository, RegraOperacaoFiscalRepository,
)
from repositories.emitente_repository import EmitenteRepository
from repositories.parceiro_repository import ParceiroRepository
from services.governance_service import GovernanceService

_doc_repo   = DocumentoFiscalRepository()
_regra_repo = RegraOperacaoFiscalRepository()
_emit_repo  = EmitenteRepository()
_parc_repo  = ParceiroRepository()

MODELO_NF    = "55"
VERSAO_SCHEMA = "4.00"

# CST defaults para operações de conserto (isento/não tributado)
_CST_CONSERTO = {"icms": "41", "ipi": "53", "pis": "07", "cofins": "07"}


def _cfop_para_uf(regra: RegraOperacaoFiscal, uf_emitente: str, uf_destinatario: str) -> str:
    """Seleciona CFOP interno ou interestadual conforme UFs."""
    if uf_emitente and uf_destinatario and uf_emitente.upper() != uf_destinatario.upper():
        return regra.cfop_interestadual or regra.cfop_interno or ""
    return regra.cfop_interno or ""


def _snapshot_emitente(e: Optional[EmpresaEmitente]) -> dict:
    if not e:
        return {}
    return {
        "cnpj": e.cnpj or "",
        "razao_social": e.razao_social or "",
        "nome_fantasia": e.nome_fantasia or "",
        "ie": e.ie or "",
        "im": e.im or "",
        "cnae_principal": e.cnae_principal or "",
        "regime_tributario": e.regime_tributario or "REGIME_NORMAL",
        "logradouro": e.logradouro or "",
        "numero": e.numero or "",
        "complemento": e.complemento or "",
        "bairro": e.bairro or "",
        "municipio": e.municipio or "",
        "uf": e.uf or "",
        "cep": e.cep or "",
        "codigo_ibge": e.codigo_ibge or "",
        "telefone": e.telefone or "",
        "email": e.email or "",
    }


def _snapshot_parceiro(p: Optional[Parceiro]) -> dict:
    if not p:
        return {}
    return {
        "id": p.id,
        "razao_social": p.razao_social or "",
        "nome_fantasia": p.nome_fantasia or "",
        "cnpj": p.cnpj or "",
        "ie": p.ie or "",
        "logradouro": p.logradouro or "",
        "numero": p.numero or "",
        "complemento": p.complemento or "",
        "bairro": p.bairro or "",
        "municipio": p.municipio or "",
        "uf": p.uf or "",
        "cep": p.cep or "",
        "codigo_ibge": p.codigo_ibge or "",
        "contribuinte_icms": p.contribuinte_icms or 9,
    }


def _build_info_complementar(
    observacao: str,
    num_os: str,
    asset_tag: str,
    num_serie: str,
    subtipo: str,
) -> str:
    """Monta infCpl com dados operacionais conforme spec módulo 8."""
    partes = []
    if observacao:
        partes.append(observacao)
    if num_os:
        partes.append(f"OS: {num_os}")
    if asset_tag:
        partes.append(f"Tag/Patrimônio: {asset_tag}")
    if num_serie:
        partes.append(f"Série: {num_serie}")
    if subtipo in ("REMESSA_CONSERTO", "RETORNO_CONSERTO"):
        partes.append(
            "ICMS CST 41 - Operação não tributada. "
            "IPI CST 53 - Saída não tributada. "
            "PIS/COFINS CST 07 - Operação isenta."
        )
    return " | ".join(p for p in partes if p)


class DocumentoFiscalService:

    # ------------------------------------------------------------------
    # 1. CRIAÇÃO DE REMESSA PARA CONSERTO
    # ------------------------------------------------------------------
    @staticmethod
    def criar_remessa_conserto(
        session: Session,
        parceiro_id: int,
        itens: list[dict],
        serie: str,
        observacao: str,
        usuario: str,
        num_os: str = "",
        asset_tag: str = "",
        num_serie: str = "",
        mod_frete: str = "9",
        ind_final: int = 0,
        ind_pres: int = 0,
    ) -> tuple[bool, str, Optional[int]]:
        return DocumentoFiscalService._criar_documento(
            session=session,
            subtipo="REMESSA_CONSERTO",
            tipo_nf="1",
            parceiro_id=parceiro_id,
            itens=itens,
            serie=serie,
            observacao=observacao,
            doc_vinculado_id=None,
            usuario=usuario,
            num_os=num_os,
            asset_tag=asset_tag,
            num_serie=num_serie,
            mod_frete=mod_frete,
            ind_final=ind_final,
            ind_pres=ind_pres,
        )

    # ------------------------------------------------------------------
    # 2. CRIAÇÃO DE RETORNO DE CONSERTO
    # ------------------------------------------------------------------
    @staticmethod
    def criar_retorno_conserto(
        session: Session,
        parceiro_id: int,
        itens: list[dict],
        serie: str,
        observacao: str,
        remessa_id: Optional[int],
        usuario: str,
        num_os: str = "",
        asset_tag: str = "",
        num_serie: str = "",
        mod_frete: str = "9",
        ind_final: int = 0,
        ind_pres: int = 0,
    ) -> tuple[bool, str, Optional[int]]:
        return DocumentoFiscalService._criar_documento(
            session=session,
            subtipo="RETORNO_CONSERTO",
            tipo_nf="1",
            parceiro_id=parceiro_id,
            itens=itens,
            serie=serie,
            observacao=observacao,
            doc_vinculado_id=remessa_id,
            usuario=usuario,
            num_os=num_os,
            asset_tag=asset_tag,
            num_serie=num_serie,
            mod_frete=mod_frete,
            ind_final=ind_final,
            ind_pres=ind_pres,
        )

    # ------------------------------------------------------------------
    # 3. CRIAÇÃO GENÉRICA (SAÍDA / ENTRADA GERAL)
    # ------------------------------------------------------------------
    @staticmethod
    def criar_saida_geral(
        session: Session,
        parceiro_id: int,
        itens: list[dict],
        serie: str,
        observacao: str,
        usuario: str,
        num_os: str = "",
        asset_tag: str = "",
        num_serie: str = "",
        mod_frete: str = "9",
        ind_final: int = 0,
        ind_pres: int = 0,
    ) -> tuple[bool, str, Optional[int]]:
        return DocumentoFiscalService._criar_documento(
            session=session,
            subtipo="SAIDA_GERAL",
            tipo_nf="1",
            parceiro_id=parceiro_id,
            itens=itens,
            serie=serie,
            observacao=observacao,
            doc_vinculado_id=None,
            usuario=usuario,
            num_os=num_os,
            asset_tag=asset_tag,
            num_serie=num_serie,
            mod_frete=mod_frete,
            ind_final=ind_final,
            ind_pres=ind_pres,
        )

    @staticmethod
    def criar_entrada_geral(
        session: Session,
        parceiro_id: int,
        itens: list[dict],
        serie: str,
        observacao: str,
        usuario: str,
        num_os: str = "",
        asset_tag: str = "",
        num_serie: str = "",
        mod_frete: str = "9",
        ind_final: int = 0,
        ind_pres: int = 0,
    ) -> tuple[bool, str, Optional[int]]:
        return DocumentoFiscalService._criar_documento(
            session=session,
            subtipo="ENTRADA_GERAL",
            tipo_nf="0",
            parceiro_id=parceiro_id,
            itens=itens,
            serie=serie,
            observacao=observacao,
            doc_vinculado_id=None,
            usuario=usuario,
            num_os=num_os,
            asset_tag=asset_tag,
            num_serie=num_serie,
            mod_frete=mod_frete,
            ind_final=ind_final,
            ind_pres=ind_pres,
        )

    # ------------------------------------------------------------------
    # 4. MÉTODO CENTRAL DE CRIAÇÃO
    # ------------------------------------------------------------------
    @staticmethod
    def _criar_documento(
        session: Session,
        subtipo: str,
        tipo_nf: str,
        parceiro_id: int,
        itens: list[dict],
        serie: str,
        observacao: str,
        doc_vinculado_id: Optional[int],
        usuario: str,
        num_os: str = "",
        asset_tag: str = "",
        num_serie: str = "",
        mod_frete: str = "9",
        ind_final: int = 0,
        ind_pres: int = 0,
    ) -> tuple[bool, str, Optional[int]]:

        if not itens:
            return False, "Informe ao menos um item.", None

        # ── Numeração automática ───────────────────────────────────────
        from database.models import Configuracoes
        _config = session.query(Configuracoes).first()
        _numero_auto: Optional[str] = None
        if _config and _config.fiscal_numeracao_atual:
            _numero_auto = str(_config.fiscal_numeracao_atual)

        # ── Regra de operação ──────────────────────────────────────────
        regra = _regra_repo.get_by_tipo(session, subtipo)
        if not regra:
            return False, f"Regra fiscal não configurada para '{subtipo}'. Verifique as regras de operação.", None

        # ── Emitente ───────────────────────────────────────────────────
        emitente = _emit_repo.get_ativo(session)

        # ── Parceiro ───────────────────────────────────────────────────
        parceiro = _parc_repo.get_by_id(session, parceiro_id)
        if not parceiro:
            return False, "Parceiro não encontrado.", None

        # ── CFOP conforme UFs ──────────────────────────────────────────
        uf_emit = emitente.uf if emitente else ""
        uf_parc = parceiro.uf or ""
        cfop = _cfop_para_uf(regra, uf_emit, uf_parc)

        # ── CST codes: usar regra ou fallback para conserto ───────────
        _is_conserto = subtipo in ("REMESSA_CONSERTO", "RETORNO_CONSERTO")
        cst_icms_default  = regra.cst_icms  or (_CST_CONSERTO["icms"]  if _is_conserto else "00")
        cst_ipi_default   = regra.cst_ipi   or (_CST_CONSERTO["ipi"]   if _is_conserto else "50")
        cst_pis_default   = regra.cst_pis   or (_CST_CONSERTO["pis"]   if _is_conserto else "01")
        cst_cofins_default = regra.cst_cofins or (_CST_CONSERTO["cofins"] if _is_conserto else "01")

        # ── Itens ──────────────────────────────────────────────────────
        valor_total = 0.0
        itens_modelo: list[DocumentoFiscalItem] = []
        for seq, item in enumerate(itens, start=1):
            qtd   = float(item.get("quantidade", 1))
            vunit = float(item.get("valor_unitario", 0.0))
            vtot  = round(qtd * vunit, 2)
            valor_total += vtot
            itens_modelo.append(DocumentoFiscalItem(
                sequencia=seq,
                codigo_produto=item.get("codigo", ""),
                descricao=item.get("descricao", ""),
                ncm=re.sub(r"\D", "", item.get("ncm", "00000000")),
                cfop=cfop,
                unidade=item.get("unidade", "UN"),
                quantidade=qtd,
                valor_unitario=vunit,
                valor_total=vtot,
                cst_icms=item.get("cst_icms", cst_icms_default),
                csosn=item.get("csosn", regra.csosn or ""),
                orig_icms=item.get("orig_icms", "0"),
                cest=item.get("cest", "") or None,
                ipi_cst=item.get("ipi_cst", cst_ipi_default),
                pis_cst=item.get("pis_cst", cst_pis_default),
                cofins_cst=item.get("cofins_cst", cst_cofins_default),
                c_ean=item.get("c_ean", "SEM GTIN"),
                c_ean_trib=item.get("c_ean_trib", "SEM GTIN"),
                ind_tot=int(item.get("ind_tot", 1)),
                x_ped=item.get("x_ped", "") or None,
                n_item_ped=item.get("n_item_ped", "") or None,
            ))

        # ── info_complementar ──────────────────────────────────────────
        info_cpl = _build_info_complementar(observacao, num_os, asset_tag, num_serie, subtipo)

        # ── Histórico inicial de status ────────────────────────────────
        status_hist = [{"status": "RASCUNHO", "data": datetime.now().isoformat(), "usuario": usuario}]

        # ── Documento ─────────────────────────────────────────────────
        doc = DocumentoFiscal(
            subtipo=subtipo,
            tipo_nf=tipo_nf,
            numero=_numero_auto,
            serie=serie or "1",
            natureza_operacao=regra.natureza_operacao or "",
            cfop=cfop,
            modelo=MODELO_NF,
            versao_schema=VERSAO_SCHEMA,
            parceiro_id=parceiro_id,
            emitente_snapshot=json.dumps(_snapshot_emitente(emitente), ensure_ascii=False),
            parceiro_snapshot=json.dumps(_snapshot_parceiro(parceiro), ensure_ascii=False),
            doc_vinculado_id=doc_vinculado_id,
            status="RASCUNHO",
            criado_por=usuario,
            criado_em=datetime.now(),
            valor_total=round(valor_total, 2),
            observacao=observacao or "",
            num_os=num_os or None,
            asset_tag=asset_tag or None,
            num_serie=num_serie or None,
            info_complementar=info_cpl or None,
            mod_frete=mod_frete or "9",
            ind_final=ind_final,
            ind_pres=ind_pres,
            status_historico=status_hist,
        )
        session.add(doc)
        session.flush()

        # ── Incrementa numeração automática ───────────────────────────
        if _config and _config.fiscal_numeracao_atual:
            _config.fiscal_numeracao_atual = _config.fiscal_numeracao_atual + 1

        for item_obj in itens_modelo:
            item_obj.documento_id = doc.id
            session.add(item_obj)

        GovernanceService.registar_log(
            session, usuario, "documentos_fiscais", doc.id,
            "DOC_FISCAL_CRIADO",
            (
                f"Documento fiscal #{doc.id} criado | Subtipo: {subtipo} | "
                f"Parceiro: {parceiro.razao_social} | CFOP: {cfop} | "
                f"Valor: R$ {valor_total:.2f}"
                + (f" | OS: {num_os}" if num_os else "")
                + (f" | Tag: {asset_tag}" if asset_tag else "")
            ),
        )
        session.commit()
        return True, f"Documento #{doc.id} criado com status RASCUNHO.", doc.id

    # ------------------------------------------------------------------
    # 5. APROVAÇÃO (marca como EMITIDA)
    # ------------------------------------------------------------------
    @staticmethod
    def aprovar(
        session: Session,
        doc_id: int,
        numero_nf: str,
        chave_acesso: str,
        protocolo_sefaz: str,
        usuario: str,
    ) -> tuple[bool, str]:
        doc = _doc_repo.get_by_id(session, doc_id)
        if not doc:
            return False, "Documento não encontrado."
        if doc.status not in ("RASCUNHO", "PRONTA_EMISSAO"):
            return False, f"Documento com status '{doc.status}' não pode ser aprovado."

        hist = doc.status_historico or []
        hist.append({"status": "EMITIDA", "data": datetime.now().isoformat(), "usuario": usuario})

        doc.status          = "EMITIDA"
        doc.aprovado_por    = usuario
        doc.aprovado_em     = datetime.now()
        doc.numero          = numero_nf or doc.numero
        doc.chave_acesso    = chave_acesso or None
        doc.protocolo_sefaz = protocolo_sefaz or None
        doc.status_historico = hist

        GovernanceService.registar_log(
            session, usuario, "documentos_fiscais", doc_id,
            "DOC_FISCAL_EMITIDO",
            f"Documento #{doc_id} aprovado/emitido por {usuario}. NF: {numero_nf}"
        )
        session.commit()
        return True, f"Documento #{doc_id} marcado como EMITIDA."

    # ------------------------------------------------------------------
    # 6. CANCELAMENTO
    # ------------------------------------------------------------------
    @staticmethod
    def cancelar(
        session: Session,
        doc_id: int,
        motivo: str,
        usuario: str,
    ) -> tuple[bool, str]:
        doc = _doc_repo.get_by_id(session, doc_id)
        if not doc:
            return False, "Documento não encontrado."
        if doc.status not in ("RASCUNHO", "PRONTA_EMISSAO"):
            return False, f"Não é possível cancelar documento com status '{doc.status}'."

        hist = doc.status_historico or []
        if isinstance(hist, str):
            try:
                hist = json.loads(hist)
            except Exception:
                hist = []
        if not isinstance(hist, list):
            hist = []
        hist.append({"status": "CANCELADA", "data": datetime.now().isoformat(), "usuario": usuario, "obs": motivo})

        doc.status           = "CANCELADA"
        doc.motivo_rejeicao  = motivo
        doc.aprovado_por     = usuario
        doc.aprovado_em      = datetime.now()
        doc.status_historico = hist

        GovernanceService.registar_log(
            session, usuario, "documentos_fiscais", doc_id,
            "DOC_FISCAL_CANCELADO",
            f"Documento #{doc_id} cancelado. Motivo: {motivo}"
        )
        session.commit()
        return True, f"Documento #{doc_id} cancelado."

    # ------------------------------------------------------------------
    # 7. SERIALIZAÇÃO
    # ------------------------------------------------------------------
    @staticmethod
    def serializar(doc: DocumentoFiscal) -> dict:
        emitente_snap = {}
        parceiro_snap = {}
        try:
            emitente_snap = json.loads(doc.emitente_snapshot) if doc.emitente_snapshot else {}
        except Exception:
            pass
        try:
            parceiro_snap = json.loads(doc.parceiro_snapshot) if doc.parceiro_snapshot else {}
        except Exception:
            pass

        status_hist = doc.status_historico or []
        if isinstance(status_hist, str):
            try:
                status_hist = json.loads(status_hist)
            except Exception:
                status_hist = []

        return {
            "id":               doc.id,
            "subtipo":          doc.subtipo,
            "tipo_nf":          doc.tipo_nf,
            "numero":           doc.numero or "",
            "serie":            doc.serie or "1",
            "natureza_operacao": doc.natureza_operacao or "",
            "cfop":             doc.cfop or "",
            "modelo":           doc.modelo or "55",
            "parceiro_id":      doc.parceiro_id,
            "emitente_snapshot": emitente_snap,
            "parceiro_snapshot": parceiro_snap,
            "doc_vinculado_id": doc.doc_vinculado_id,
            "chave_acesso":     doc.chave_acesso or "",
            "protocolo_sefaz":  doc.protocolo_sefaz or "",
            "status":           doc.status,
            "criado_por":       doc.criado_por,
            "criado_em":        str(doc.criado_em) if doc.criado_em else "",
            "aprovado_por":     doc.aprovado_por or "",
            "aprovado_em":      str(doc.aprovado_em) if doc.aprovado_em else "",
            "motivo_rejeicao":  doc.motivo_rejeicao or "",
            "valor_total":      doc.valor_total or 0.0,
            "observacao":       doc.observacao or "",
            # Campos operacionais
            "num_os":           doc.num_os or "",
            "asset_tag":        doc.asset_tag or "",
            "num_serie":        doc.num_serie or "",
            "info_complementar": doc.info_complementar or "",
            "mod_frete":        doc.mod_frete or "9",
            "ind_final":        doc.ind_final or 0,
            "ind_pres":         doc.ind_pres or 0,
            "status_historico": status_hist,
            "itens": [
                {
                    "sequencia":      it.sequencia,
                    "codigo_produto": it.codigo_produto or "",
                    "descricao":      it.descricao or "",
                    "ncm":            it.ncm or "",
                    "cfop":           it.cfop or "",
                    "unidade":        it.unidade or "UN",
                    "quantidade":     it.quantidade or 0,
                    "valor_unitario": it.valor_unitario or 0,
                    "valor_total":    it.valor_total or 0,
                    "cst_icms":       it.cst_icms or "",
                    "csosn":          it.csosn or "",
                    "orig_icms":      it.orig_icms or "0",
                    "ipi_cst":        it.ipi_cst or "",
                    "pis_cst":        it.pis_cst or "",
                    "cofins_cst":     it.cofins_cst or "",
                    "c_ean":          it.c_ean or "SEM GTIN",
                    "c_ean_trib":     it.c_ean_trib or "SEM GTIN",
                    "ind_tot":        it.ind_tot if it.ind_tot is not None else 1,
                    "x_ped":          it.x_ped or "",
                    "n_item_ped":     it.n_item_ped or "",
                }
                for it in (doc.itens or [])
            ],
        }
