# repositories/parceiro_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import Parceiro
from repositories.base_repository import BaseRepository


class ParceiroRepository(BaseRepository[Parceiro]):

    def __init__(self):
        super().__init__(Parceiro)

    def get_by_cnpj(self, session: Session, cnpj: str) -> Optional[Parceiro]:
        return session.query(Parceiro).filter(Parceiro.cnpj == cnpj).first()

    def listar_ativos(self, session: Session, tipo: str = "") -> List[Parceiro]:
        q = session.query(Parceiro).filter(Parceiro.status == "ATIVO")
        if tipo:
            q = q.filter(Parceiro.tipo.in_([tipo, "AMBOS"]))
        return q.order_by(Parceiro.razao_social).all()

    def buscar(self, session: Session, termo: str) -> List[Parceiro]:
        like = f"%{termo}%"
        return (
            session.query(Parceiro)
            .filter(
                (Parceiro.razao_social.ilike(like)) |
                (Parceiro.nome_fantasia.ilike(like)) |
                (Parceiro.cnpj.ilike(like))
            )
            .order_by(Parceiro.razao_social)
            .limit(50)
            .all()
        )
