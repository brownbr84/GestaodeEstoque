# services/fiscal_service.py
"""
TraceBox WMS — Serviço Fiscal (NF-e)
=====================================
Arquitetura de Trava de Segurança:
  1. Este serviço NUNCA emite uma NF-e diretamente.
  2. Ele prepara e valida o "rascunho" (payload) da nota.
  3. O rascunho é salvo no BD com status='PENDENTE'.
  4. A emissão real exige aprovação explícita de um humano autorizado
     via o endpoint POST /api/v1/fiscal/emitir, que chama o backend
     de assinatura com o certificado digital A1 da empresa.

Conformidade: SEFAZ SP / Receita Federal — diretrizes vigentes em 2026.
"""
from __future__ import annotations

import re
import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from database.models import NotaFiscalRascunho
from services.governance_service import GovernanceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONSTANTES FISCAIS — 2026
# ---------------------------------------------------------------------------
NATUREZA_ENTRADA  = "Entrada de Mercadorias"
NATUREZA_SAIDA    = "Saída de Mercadorias"
CFOP_ENTRADA_SP   = "1102"   # Compra para uso/consumo dentro do estado
CFOP_SAIDA_SP     = "5102"   # Venda de produto industrializado dentro do estado
MODELO_NF         = "55"     # NF-e padrão
SERIE_PADRAO      = "1"
VERSAO_SCHEMA     = "4.00"   # leiaute NF-e vigente

# ---------------------------------------------------------------------------
# AVISO SOBRE APIS GRATUITAS — 2026
# ---------------------------------------------------------------------------
_AVISO_APIS = """
⚠️  AVISO DE VIABILIDADE FISCAL — SEFAZ SP / Receita Federal 2026
─────────────────────────────────────────────────────────────────
A validação fiscal completa para emissão de NF-e NÃO pode ser feita
100% com APIs gratuitas. Veja abaixo:

GRATUITO (disponível):
  • BrasilAPI     — Consulta CNPJ/CEP (sem SLA, rate-limit implícito)
  • IBGE API      — Código de município (cMun)
  • Tabela NCM    — MDIC (CSV público, download local)
  • SEFAZ SVRS    — Autorização NF-e via WebService (EXIGE cert. A1)

REQUER PAGAMENTO / INFRAESTRUTURA:
  • Certificado Digital A1 (.pfx) — R$ 200–600/ano — OBRIGATÓRIO
  • Assinatura XML (xmlsec ou PyNFe) — Open source, mas infra interna
  • Consulta CNPJ em volume      — ReceitaWS pago ou SERPRO API paga
  • Validação CEST/ICMS-ST       — Tabelas SP exigem atualização mensal

DECISÃO NECESSÁRIA ANTES DE EMITIR:
  1. A empresa possui Certificado Digital A1 (.pfx)?
  2. O ambiente é homologação ou produção?
  3. Qual o volume de NF-e/mês esperado?
─────────────────────────────────────────────────────────────────
"""


class FiscalService:
    """
    Serviço de preparação fiscal do TraceBox WMS.

    IMPORTANTE: Este serviço apenas PREPARA e VALIDA o rascunho da NF-e.
    A emissão real é feita por um módulo separado de assinatura digital,
    acionado somente após aprovação humana explícita.
    """

    # ------------------------------------------------------------------
    # 1. MÉTODO PRINCIPAL — preparar_emissao_nf_sefaz
    # ------------------------------------------------------------------
    @staticmethod
    def preparar_emissao_nf_sefaz(
        session: Session,
        tipo_operacao: str,
        dados_mercadoria: list[dict],
        dados_destinatario_remetente: dict,
        usuario: str,
        numero_nf: Optional[str] = None,
    ) -> dict:
        """
        Prepara o pacote de dados para emissão de NF-e (entrada ou saída).

        Parâmetros
        ----------
        session                    : Sessão do banco de dados (SQLAlchemy).
        tipo_operacao              : 'entrada' ou 'saida'.
        dados_mercadoria           : Lista de itens com codigo, descricao,
                                     ncm, quantidade e valor_unitario.
        dados_destinatario_remetente: Dict com cnpj, nome, logradouro,
                                      municipio, uf, cep.
        usuario                    : Login do operador que originou o pedido.
        numero_nf                  : Número da NF referência (opcional).

        Retorna
        -------
        dict com:
            - sucesso (bool)
            - api_gratuita_disponivel (bool)
            - aviso (str | None) — aviso obrigatório ao usuário
            - rascunho_id (int | None)
            - payload (dict | None)
            - mensagem (str)
        """
        # ── Passo 0: Verificar disponibilidade de APIs gratuitas ───────
        api_gratuita_ok, aviso_apis = FiscalService._verificar_viabilidade_apis()

        if not api_gratuita_ok:
            # TRAVA: informar o usuário antes de qualquer tentativa
            return {
                "sucesso": False,
                "api_gratuita_disponivel": False,
                "aviso": _AVISO_APIS,
                "rascunho_id": None,
                "payload": None,
                "mensagem": (
                    "❌ Não é possível completar as validações fiscais com APIs "
                    "100% gratuitas. Leia o aviso acima e tome uma decisão antes "
                    "de prosseguir."
                ),
            }

        # ── Passo 1: Validações básicas ────────────────────────────────
        tipo_op = tipo_operacao.strip().lower()
        if tipo_op not in ("entrada", "saida"):
            return {
                "sucesso": False,
                "api_gratuita_disponivel": True,
                "aviso": None,
                "rascunho_id": None,
                "payload": None,
                "mensagem": "tipo_operacao deve ser 'entrada' ou 'saida'.",
            }

        cnpj = dados_destinatario_remetente.get("cnpj", "")
        cnpj_limpo = re.sub(r"\D", "", cnpj)
        if len(cnpj_limpo) != 14:
            return {
                "sucesso": False,
                "api_gratuita_disponivel": True,
                "aviso": None,
                "rascunho_id": None,
                "payload": None,
                "mensagem": f"CNPJ inválido: '{cnpj}'. Informe 14 dígitos.",
            }

        if not dados_mercadoria:
            return {
                "sucesso": False,
                "api_gratuita_disponivel": True,
                "aviso": None,
                "rascunho_id": None,
                "payload": None,
                "mensagem": "dados_mercadoria está vazio.",
            }

        # ── Passo 2: Consulta de CNPJ via BrasilAPI (gratuita) ────────
        dados_cnpj = FiscalService._consultar_cnpj_brasilapi(cnpj_limpo)

        # ── Passo 3: Montagem do payload fiscal ────────────────────────
        payload = FiscalService._montar_payload(
            tipo_op,
            dados_mercadoria,
            dados_destinatario_remetente,
            dados_cnpj,
            numero_nf,
        )

        # ── Passo 4: Salvar rascunho no BD (TRAVA — status PENDENTE) ──
        rascunho_id = FiscalService._salvar_rascunho(
            session, tipo_op, payload, usuario
        )

        # ── Passo 5: Log de auditoria ──────────────────────────────────
        GovernanceService.registar_log(
            session,
            usuario,
            "notas_fiscais_rascunho",
            rascunho_id,
            "NF_RASCUNHO_CRIADO",
            (
                f"Rascunho #{rascunho_id} criado para operação de "
                f"{tipo_op.upper()} | CNPJ: {cnpj_limpo} | "
                f"Itens: {len(dados_mercadoria)}"
            ),
        )
        session.commit()

        return {
            "sucesso": True,
            "api_gratuita_disponivel": True,
            "aviso": aviso_apis,  # pode ter avisos parciais mesmo quando ok=True
            "rascunho_id": rascunho_id,
            "payload": payload,
            "mensagem": (
                f"✅ Rascunho #{rascunho_id} criado com sucesso e aguarda "
                "aprovação de um usuário autorizado para emissão."
            ),
        }

    # ------------------------------------------------------------------
    # 2. VERIFICAÇÃO DE VIABILIDADE DE APIs GRATUITAS
    # ------------------------------------------------------------------
    @staticmethod
    def _verificar_viabilidade_apis() -> tuple[bool, Optional[str]]:
        """
        Verifica se as APIs gratuitas disponíveis são suficientes para
        as validações fiscais mínimas exigidas.

        Retorna (api_gratuita_disponivel: bool, aviso: str | None).
        A função sempre retorna True com aviso parcial, pois o conjunto
        gratuito cobre a montagem do rascunho — mas não a assinatura.
        """
        aviso = (
            "⚠️  ATENÇÃO: As APIs gratuitas (BrasilAPI, IBGE) cobrem apenas "
            "a validação de CNPJ e municípios. A EMISSÃO REAL exige "
            "Certificado Digital A1 e acesso aos WebServices SEFAZ — "
            "ambos FORA do escopo gratuito. O rascunho será salvo, mas "
            "a emissão depende de infraestrutura paga."
        )
        return True, aviso

    # ------------------------------------------------------------------
    # 3. CONSULTA DE CNPJ — BrasilAPI (gratuita, sem autenticação)
    # ------------------------------------------------------------------
    @staticmethod
    def _consultar_cnpj_brasilapi(cnpj_limpo: str) -> dict:
        """
        Consulta dados cadastrais via BrasilAPI.
        Em caso de falha (rate-limit, timeout), retorna dict vazio
        e registra o aviso no log — NÃO bloqueia a operação.
        """
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    "BrasilAPI retornou %s para CNPJ %s", resp.status_code, cnpj_limpo
                )
        except Exception as exc:
            logger.warning("Falha na consulta BrasilAPI: %s", exc)
        return {}

    # ------------------------------------------------------------------
    # 4. MONTAGEM DO PAYLOAD FISCAL
    # ------------------------------------------------------------------
    @staticmethod
    def _montar_payload(
        tipo_op: str,
        itens: list[dict],
        dest_rem: dict,
        dados_cnpj: dict,
        numero_nf: Optional[str],
    ) -> dict:
        """
        Monta o pacote de dados estruturado para geração do XML NF-e.
        Este payload espelha os grupos do leiaute 4.00 da NF-e.
        """
        cfop    = CFOP_ENTRADA_SP if tipo_op == "entrada" else CFOP_SAIDA_SP
        nat_op  = NATUREZA_ENTRADA if tipo_op == "entrada" else NATUREZA_SAIDA
        agora   = datetime.now()

        # ── Destinatário / Remetente ───────────────────────────────────
        cnpj_limpo = re.sub(r"\D", "", dest_rem.get("cnpj", ""))
        nome_fantasia = dados_cnpj.get("nome_fantasia") or dest_rem.get("nome", "")
        razao_social  = dados_cnpj.get("razao_social")  or dest_rem.get("nome", "")
        municipio_api = dados_cnpj.get("municipio")     or dest_rem.get("municipio", "")
        uf_api        = dados_cnpj.get("uf")            or dest_rem.get("uf", "SP")
        cep_api       = re.sub(r"\D", "", dados_cnpj.get("cep") or dest_rem.get("cep", ""))
        logradouro    = dados_cnpj.get("logradouro")    or dest_rem.get("logradouro", "")

        # ── Itens ──────────────────────────────────────────────────────
        itens_payload = []
        valor_total = 0.0
        for idx, item in enumerate(itens, start=1):
            qtd    = float(item.get("quantidade", 1))
            vunit  = float(item.get("valor_unitario", 0.0))
            vtotal = round(qtd * vunit, 2)
            valor_total += vtotal
            itens_payload.append({
                "nItem":    idx,
                "cProd":    item.get("codigo", ""),
                "xProd":    item.get("descricao", ""),
                "NCM":      re.sub(r"\D", "", item.get("ncm", "00000000")),
                "CFOP":     cfop,
                "uCom":     item.get("unidade", "UN"),
                "qCom":     qtd,
                "vUnCom":   vunit,
                "vProd":    vtotal,
            })

        return {
            "versao":       VERSAO_SCHEMA,
            "modelo":       MODELO_NF,
            "serie":        SERIE_PADRAO,
            "dhEmi":        agora.isoformat(),
            "tpNF":         "0" if tipo_op == "entrada" else "1",
            "natOp":        nat_op,
            "numero_nf_ref": numero_nf or "",
            "dest_rem": {
                "CNPJ":       cnpj_limpo,
                "xNome":      razao_social,
                "xFant":      nome_fantasia,
                "logradouro": logradouro,
                "xMun":       municipio_api,
                "UF":         uf_api,
                "CEP":        cep_api,
            },
            "itens":        itens_payload,
            "vNF":          round(valor_total, 2),
            "status_emissao": "RASCUNHO",
            "observacao":   (
                "Rascunho gerado pelo TraceBox WMS. "
                "Pendente de assinatura digital e autorização SEFAZ."
            ),
        }

    # ------------------------------------------------------------------
    # 5. SALVAR RASCUNHO NO BD (TRAVA DE SEGURANÇA)
    # ------------------------------------------------------------------
    @staticmethod
    def _salvar_rascunho(
        session: Session, tipo_op: str, payload: dict, usuario: str
    ) -> int:
        """
        Persiste o rascunho no banco com status='PENDENTE'.
        A NF-e só pode ser emitida após a aprovação via endpoint dedicado.
        """
        rascunho = NotaFiscalRascunho(
            tipo_operacao=tipo_op.upper(),
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            status="PENDENTE",
            criado_por=usuario,
            criado_em=datetime.now(),
        )
        session.add(rascunho)
        session.flush()  # gera o ID sem commitar
        return rascunho.id
