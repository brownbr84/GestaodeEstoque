from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import EstoqueMinMax, Imobilizado
from repositories.estoque_minmax_repository import EstoqueMinMaxRepository
from services.governance_service import GovernanceService

_repo = EstoqueMinMaxRepository()


class EstoqueMinMaxService:

    @staticmethod
    def salvar(session: Session, dados: dict, usuario: str) -> tuple[bool, str, Optional[EstoqueMinMax]]:
        produto_codigo = (dados.get("produto_codigo") or "").strip()
        if not produto_codigo:
            return False, "Código do produto é obrigatório.", None

        filial = (dados.get("filial") or "").strip()
        minimo = float(dados.get("estoque_minimo", 0))
        maximo = float(dados.get("estoque_maximo", 0))

        if maximo > 0 and minimo > maximo:
            return False, "Estoque mínimo não pode ser maior que o máximo.", None

        existente = _repo.get_by_produto_filial(session, produto_codigo, filial)
        if existente:
            existente.estoque_minimo = minimo
            existente.estoque_maximo = maximo
            existente.unidade_medida = dados.get("unidade_medida", existente.unidade_medida) or "UN"
            existente.ativo = int(dados.get("ativo", existente.ativo))
            existente.observacao = dados.get("observacao", existente.observacao) or ""
            existente.updated_at = datetime.now()
            existente.updated_by = usuario
            GovernanceService.registar_log(
                session, usuario, "estoque_minmax", existente.id,
                "MINMAX_ATUALIZADO", f"{produto_codigo} min={minimo} max={maximo}",
            )
            session.commit()
            return True, "Parâmetros atualizados.", existente

        mm = EstoqueMinMax(
            produto_codigo=produto_codigo,
            filial=filial,
            estoque_minimo=minimo,
            estoque_maximo=maximo,
            unidade_medida=dados.get("unidade_medida", "UN") or "UN",
            ativo=int(dados.get("ativo", 1)),
            observacao=dados.get("observacao", "") or "",
            created_by=usuario,
            updated_by=usuario,
        )
        session.add(mm)
        session.flush()
        GovernanceService.registar_log(
            session, usuario, "estoque_minmax", mm.id,
            "MINMAX_CRIADO", f"{produto_codigo} min={minimo} max={maximo}",
        )
        session.commit()
        return True, "Parâmetros criados.", mm

    @staticmethod
    def excluir(session: Session, mm_id: int, usuario: str) -> tuple[bool, str]:
        mm = _repo.get_by_id(session, mm_id)
        if not mm:
            return False, "Registro não encontrado."
        GovernanceService.registar_log(
            session, usuario, "estoque_minmax", mm_id,
            "MINMAX_EXCLUIDO", mm.produto_codigo,
        )
        session.delete(mm)
        session.commit()
        return True, "Parâmetros removidos."

    @staticmethod
    def listar_com_status(session: Session, produto_codigo: str = "", filial: str = "") -> list:
        q = session.query(EstoqueMinMax)
        if produto_codigo:
            q = q.filter(EstoqueMinMax.produto_codigo == produto_codigo)
        if filial:
            q = q.filter(EstoqueMinMax.filial == filial)
        regras = q.all()

        result = []
        for r in regras:
            q_saldo = session.query(func.sum(Imobilizado.quantidade)).filter(
                Imobilizado.codigo == r.produto_codigo,
                Imobilizado.status == "Disponível",
            )
            if r.filial:
                q_saldo = q_saldo.filter(Imobilizado.localizacao == r.filial)
            saldo = q_saldo.scalar() or 0

            if r.estoque_maximo > 0 and saldo >= r.estoque_maximo:
                alerta = "EXCESSO"
            elif r.estoque_minimo > 0 and saldo <= r.estoque_minimo:
                alerta = "ABAIXO_MINIMO"
            else:
                alerta = "NORMAL"

            result.append({
                "id": r.id,
                "produto_codigo": r.produto_codigo,
                "filial": r.filial or "",
                "estoque_minimo": r.estoque_minimo,
                "estoque_maximo": r.estoque_maximo,
                "unidade_medida": r.unidade_medida or "UN",
                "ativo": r.ativo,
                "observacao": r.observacao or "",
                "saldo_atual": float(saldo),
                "alerta": alerta,
                "updated_by": r.updated_by,
                "updated_at": str(r.updated_at)[:16] if r.updated_at else None,
            })
        return result

    @staticmethod
    def serializar(mm: EstoqueMinMax) -> dict:
        return {
            "id": mm.id,
            "produto_codigo": mm.produto_codigo,
            "filial": mm.filial or "",
            "estoque_minimo": mm.estoque_minimo,
            "estoque_maximo": mm.estoque_maximo,
            "unidade_medida": mm.unidade_medida or "UN",
            "ativo": mm.ativo,
            "observacao": mm.observacao or "",
            "created_by": mm.created_by,
            "updated_by": mm.updated_by,
            "updated_at": str(mm.updated_at)[:16] if mm.updated_at else None,
        }
