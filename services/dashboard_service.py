# services/dashboard_service.py
"""
TraceBox WMS — DashboardService
=================================
Extrai toda a lógica de negócio do endpoint /api/v1/dashboard/metricas
para um service testável e reutilizável (P3 — Escalabilidade).

Antes essa lógica estava inline no endpoint FastAPI, o que impedia
testes unitários e dificultava o reuso em outros contextos.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class DashboardService:

    @staticmethod
    def obter_metricas_completas() -> dict:
        """
        Consolida todos os KPIs, curva ABC, métricas operacionais e
        log de auditoria em um único payload serializável.

        Retorna dict com chave "status" = "vazio" | "ok".
        Em caso de erro, retorna "status" = "erro" com "detalhe".
        """
        try:
            from controllers.torre import (
                carregar_dados_mestre,
                calcular_kpis_principais,
                processar_curva_abc,
                obter_metricas_operacionais,
                obter_log_auditoria,
            )

            df_raw = carregar_dados_mestre()
            if df_raw.empty:
                return {"status": "vazio"}

            # ── KPIs principais ────────────────────────────────────────
            total_cap, total_un, tx_util, fill, tx_perda, cap_ofic, giro = (
                calcular_kpis_principais(df_raw)
            )

            # ── Curva ABC ──────────────────────────────────────────────
            df_abc = processar_curva_abc(df_raw, total_cap)

            # ── Métricas operacionais ──────────────────────────────────
            transito, manutencao, saidas_pend, mttr, custo_mes = (
                obter_metricas_operacionais(df_raw)
            )

            # ── Log de auditoria ───────────────────────────────────────
            df_log = obter_log_auditoria()

            # ── Composição de capital por categoria (Treemap) ──────────
            df_tree = df_raw[df_raw["Valor_Total_Estoque"] > 0].copy()
            df_tree["categoria"] = df_tree["categoria"].fillna("Outros")
            composicao = (
                df_tree.groupby("categoria")["Valor_Total_Estoque"]
                .sum()
                .reset_index()
                .to_dict(orient="records")
            )

            return {
                "status": "ok",
                "kpis": {
                    "total_capital":    float(total_cap),
                    "total_unidades":   float(total_un),
                    "taxa_utilizacao":  float(tx_util),
                    "fill_rate":        float(fill),
                    "taxa_perda":       float(tx_perda),
                    "capital_oficina":  float(cap_ofic),
                },
                "composicao_capital": composicao,
                "curva_abc_top10": (
                    df_abc.head(10)[["codigo", "Valor_Total_Estoque"]].to_dict(orient="records")
                    if not df_abc.empty
                    else []
                ),
                "operacional": {
                    "transito":          float(transito),
                    "manutencao":        float(manutencao),
                    "saidas_pendentes":  int(saidas_pend),
                    "mttr_real":         float(mttr),
                    "custo_manut_mes":   float(custo_mes),
                },
                "logs": (
                    df_log.to_dict(orient="records") if not df_log.empty else []
                ),
            }

        except Exception as exc:
            logger.exception("Erro ao calcular métricas do dashboard: %s", exc)
            return {"status": "erro", "detalhe": str(exc)}
