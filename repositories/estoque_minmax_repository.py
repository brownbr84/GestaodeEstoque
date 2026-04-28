from typing import List, Optional
from sqlalchemy.orm import Session
from repositories.base_repository import BaseRepository
from database.models import EstoqueMinMax


class EstoqueMinMaxRepository(BaseRepository[EstoqueMinMax]):
    def __init__(self):
        super().__init__(EstoqueMinMax)

    def get_by_produto_filial(self, session: Session, produto_codigo: str, filial: str = "") -> Optional[EstoqueMinMax]:
        q = session.query(EstoqueMinMax).filter(EstoqueMinMax.produto_codigo == produto_codigo)
        if filial:
            q = q.filter(EstoqueMinMax.filial == filial)
        else:
            q = q.filter((EstoqueMinMax.filial == None) | (EstoqueMinMax.filial == ""))
        return q.first()

    def listar_por_produto(self, session: Session, produto_codigo: str) -> List[EstoqueMinMax]:
        return session.query(EstoqueMinMax).filter(
            EstoqueMinMax.produto_codigo == produto_codigo
        ).order_by(EstoqueMinMax.filial).all()

    def listar_ativos(self, session: Session) -> List[EstoqueMinMax]:
        return session.query(EstoqueMinMax).filter(EstoqueMinMax.ativo == 1).all()
