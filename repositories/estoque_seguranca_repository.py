from typing import List, Optional
from sqlalchemy.orm import Session
from repositories.base_repository import BaseRepository
from database.models import EstoqueSeguranca


class EstoqueSegurancaRepository(BaseRepository[EstoqueSeguranca]):
    def __init__(self):
        super().__init__(EstoqueSeguranca)

    def get_by_produto_filial(self, session: Session, produto_codigo: str, filial: str = "") -> Optional[EstoqueSeguranca]:
        q = session.query(EstoqueSeguranca).filter(EstoqueSeguranca.produto_codigo == produto_codigo)
        if filial:
            q = q.filter(EstoqueSeguranca.filial == filial)
        else:
            q = q.filter((EstoqueSeguranca.filial == None) | (EstoqueSeguranca.filial == ""))
        return q.first()

    def listar_ativos(self, session: Session) -> List[EstoqueSeguranca]:
        return session.query(EstoqueSeguranca).filter(EstoqueSeguranca.ativo == 1).all()

    def listar_por_produto(self, session: Session, produto_codigo: str) -> List[EstoqueSeguranca]:
        return session.query(EstoqueSeguranca).filter(
            EstoqueSeguranca.produto_codigo == produto_codigo
        ).order_by(EstoqueSeguranca.filial).all()
