from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database.models import Localizacao, Imobilizado
from repositories.localizacao_repository import LocalizacaoRepository
from services.governance_service import GovernanceService

_repo = LocalizacaoRepository()


class LocalizacaoService:

    @staticmethod
    def criar(session: Session, dados: dict, usuario: str) -> tuple[bool, str, Optional[Localizacao]]:
        filial = (dados.get("filial") or "").strip()
        codigo = (dados.get("codigo") or "").strip()
        if not filial or not codigo:
            return False, "Filial e código são obrigatórios.", None

        if _repo.get_by_codigo(session, filial, codigo):
            return False, f"Localização '{codigo}' já existe na filial '{filial}'.", None

        loc = Localizacao(
            filial=filial,
            codigo=codigo,
            descricao=dados.get("descricao", ""),
            zona=dados.get("zona", ""),
            doca_polo=dados.get("doca_polo", ""),
            status="ATIVO",
            created_by=usuario,
            updated_by=usuario,
        )
        session.add(loc)
        session.flush()
        GovernanceService.registar_log(
            session, usuario, "localizacoes", loc.id,
            "LOCALIZACAO_CRIADA", f"{codigo} — {filial}",
        )
        session.commit()
        return True, "Localização criada com sucesso.", loc

    @staticmethod
    def atualizar(session: Session, loc_id: int, dados: dict, usuario: str) -> tuple[bool, str]:
        loc = _repo.get_by_id(session, loc_id)
        if not loc:
            return False, "Localização não encontrada."
        for campo in ("descricao", "zona", "doca_polo", "status"):
            if campo in dados:
                setattr(loc, campo, dados[campo])
        loc.updated_at = datetime.now()
        loc.updated_by = usuario
        GovernanceService.registar_log(
            session, usuario, "localizacoes", loc_id,
            "LOCALIZACAO_ATUALIZADA", str(dados),
        )
        session.commit()
        return True, "Localização atualizada."

    @staticmethod
    def inativar(session: Session, loc_id: int, usuario: str) -> tuple[bool, str]:
        loc = _repo.get_by_id(session, loc_id)
        if not loc:
            return False, "Localização não encontrada."
        loc.status = "INATIVO"
        loc.updated_at = datetime.now()
        loc.updated_by = usuario
        GovernanceService.registar_log(
            session, usuario, "localizacoes", loc_id, "LOCALIZACAO_INATIVADA", "",
        )
        session.commit()
        return True, "Localização inativada."

    @staticmethod
    def listar(session: Session, filial: str = "", apenas_ativas: bool = True) -> list:
        if apenas_ativas:
            return _repo.listar_ativas(session, filial)
        locs = session.query(Localizacao)
        if filial:
            locs = locs.filter(Localizacao.filial == filial)
        return locs.order_by(Localizacao.filial, Localizacao.codigo).all()

    @staticmethod
    def atribuir_a_item(
        session: Session, item_id: int, localizacao_id: Optional[int], usuario: str
    ) -> tuple[bool, str]:
        item = session.get(Imobilizado, item_id)
        if not item:
            return False, "Item não encontrado."
        if localizacao_id is not None:
            loc = _repo.get_by_id(session, localizacao_id)
            if not loc:
                return False, "Localização não encontrada."
            if loc.status != "ATIVO":
                return False, "Localização inativa."
            if loc.filial and item.localizacao and loc.filial != item.localizacao:
                return False, (
                    f"Localização '{loc.codigo}' pertence à filial '{loc.filial}', "
                    f"diferente da filial do item '{item.localizacao}'."
                )
        item.localizacao_id = localizacao_id
        GovernanceService.registar_log(
            session, usuario, "imobilizado", item_id,
            "ENDERECO_ATRIBUIDO", f"localizacao_id={localizacao_id}",
        )
        session.commit()
        return True, "Endereço atualizado."

    @staticmethod
    def serializar(loc: Localizacao) -> dict:
        return {
            "id": loc.id,
            "filial": loc.filial,
            "codigo": loc.codigo,
            "descricao": loc.descricao or "",
            "zona": loc.zona or "",
            "doca_polo": loc.doca_polo or "",
            "status": loc.status,
            "created_at": str(loc.created_at)[:16] if loc.created_at else None,
            "updated_at": str(loc.updated_at)[:16] if loc.updated_at else None,
            "created_by": loc.created_by,
            "updated_by": loc.updated_by,
        }
