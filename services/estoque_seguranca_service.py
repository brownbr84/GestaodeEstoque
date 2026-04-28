import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database.models import EstoqueSeguranca, Movimentacao, Imobilizado
from repositories.estoque_seguranca_repository import EstoqueSegurancaRepository
from services.governance_service import GovernanceService

_repo = EstoqueSegurancaRepository()

# Tabela Z para níveis de serviço comuns
_Z = {0.80: 0.842, 0.85: 1.036, 0.90: 1.282, 0.95: 1.645, 0.99: 2.326}


def _z_score(nivel: float) -> float:
    for k in sorted(_Z):
        if nivel <= k:
            return _Z[k]
    return _Z[max(_Z)]


class EstoqueSegurancaService:

    @staticmethod
    def salvar(session: Session, dados: dict, usuario: str) -> tuple[bool, str, Optional[EstoqueSeguranca]]:
        produto_codigo = (dados.get("produto_codigo") or "").strip()
        if not produto_codigo:
            return False, "Código do produto é obrigatório.", None

        filial = (dados.get("filial") or "").strip()
        existente = _repo.get_by_produto_filial(session, produto_codigo, filial)

        if existente:
            for campo in ("controle_por_lote", "controle_por_ativo", "ativo",
                          "janela_historica_dias", "lead_time_dias", "nivel_de_servico"):
                if campo in dados:
                    setattr(existente, campo, dados[campo])
            existente.updated_at = datetime.now()
            existente.updated_by = usuario
            GovernanceService.registar_log(
                session, usuario, "estoque_seguranca", existente.id,
                "SEG_ATUALIZADO", produto_codigo,
            )
            session.commit()
            return True, "Configuração atualizada.", existente

        es = EstoqueSeguranca(
            produto_codigo=produto_codigo,
            filial=filial,
            controle_por_lote=int(dados.get("controle_por_lote", 0)),
            controle_por_ativo=int(dados.get("controle_por_ativo", 0)),
            ativo=int(dados.get("ativo", 1)),
            janela_historica_dias=int(dados.get("janela_historica_dias", 90)),
            lead_time_dias=int(dados.get("lead_time_dias", 7)),
            nivel_de_servico=float(dados.get("nivel_de_servico", 0.95)),
            updated_by=usuario,
        )
        session.add(es)
        session.flush()
        GovernanceService.registar_log(
            session, usuario, "estoque_seguranca", es.id,
            "SEG_CRIADO", produto_codigo,
        )
        session.commit()
        return True, "Configuração criada.", es

    @staticmethod
    def calcular(session: Session, es_id: int, usuario: str) -> tuple[bool, str, Optional[float]]:
        es = _repo.get_by_id(session, es_id)
        if not es:
            return False, "Configuração não encontrada.", None

        desde = datetime.now() - timedelta(days=es.janela_historica_dias)

        movs = (
            session.query(Movimentacao)
            .join(Imobilizado, Movimentacao.ferramenta_id == Imobilizado.id)
            .filter(
                Imobilizado.codigo == es.produto_codigo,
                Movimentacao.tipo == "Saída",
                Movimentacao.data_movimentacao >= desde,
            )
            .all()
        )

        if len(movs) < 2:
            return False, "Histórico insuficiente para cálculo (mínimo 2 movimentos de saída).", None

        consumo_por_dia: dict = defaultdict(float)
        for m in movs:
            dia = str(m.data_movimentacao)[:10]
            consumo_por_dia[dia] += 1.0

        valores = list(consumo_por_dia.values())
        n = len(valores)
        media = sum(valores) / n
        variancia = sum((v - media) ** 2 for v in valores) / max(n - 1, 1)
        desvio_padrao = math.sqrt(variancia)

        z = _z_score(es.nivel_de_servico)
        estoque_seg = round(z * desvio_padrao * math.sqrt(es.lead_time_dias), 2)

        es.desvio_padrao = round(desvio_padrao, 4)
        es.estoque_seguranca_calculado = estoque_seg
        es.updated_at = datetime.now()
        es.updated_by = usuario
        GovernanceService.registar_log(
            session, usuario, "estoque_seguranca", es_id,
            "SEG_CALCULADO", f"SS={estoque_seg} σ={desvio_padrao:.4f}",
        )
        session.commit()
        return True, f"Estoque de segurança: {estoque_seg} unidades.", estoque_seg

    @staticmethod
    def excluir(session: Session, es_id: int, usuario: str) -> tuple[bool, str]:
        es = _repo.get_by_id(session, es_id)
        if not es:
            return False, "Configuração não encontrada."
        GovernanceService.registar_log(
            session, usuario, "estoque_seguranca", es_id,
            "SEG_EXCLUIDO", es.produto_codigo,
        )
        session.delete(es)
        session.commit()
        return True, "Configuração removida."

    @staticmethod
    def serializar(es: EstoqueSeguranca) -> dict:
        return {
            "id": es.id,
            "produto_codigo": es.produto_codigo,
            "filial": es.filial or "",
            "controle_por_lote": es.controle_por_lote,
            "controle_por_ativo": es.controle_por_ativo,
            "ativo": es.ativo,
            "janela_historica_dias": es.janela_historica_dias,
            "lead_time_dias": es.lead_time_dias,
            "nivel_de_servico": es.nivel_de_servico,
            "desvio_padrao": es.desvio_padrao,
            "estoque_seguranca_calculado": es.estoque_seguranca_calculado,
            "updated_at": str(es.updated_at)[:16] if es.updated_at else None,
            "updated_by": es.updated_by,
        }
