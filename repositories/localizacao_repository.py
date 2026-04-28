from typing import List, Optional
from sqlalchemy.orm import Session
from repositories.base_repository import BaseRepository
from database.models import Localizacao


class LocalizacaoRepository(BaseRepository[Localizacao]):
    def __init__(self):
        super().__init__(Localizacao)

    def listar_ativas(self, session: Session, filial: str = "") -> List[Localizacao]:
        q = session.query(Localizacao).filter(Localizacao.status == "ATIVO")
        if filial:
            q = q.filter(Localizacao.filial == filial)
        return q.order_by(Localizacao.filial, Localizacao.codigo).all()

    def get_by_codigo(self, session: Session, filial: str, codigo: str) -> Optional[Localizacao]:
        return session.query(Localizacao).filter(
            Localizacao.filial == filial,
            Localizacao.codigo == codigo,
        ).first()

    def listar_por_filial(self, session: Session, filial: str, apenas_ativas: bool = True) -> List[Localizacao]:
        q = session.query(Localizacao).filter(Localizacao.filial == filial)
        if apenas_ativas:
            q = q.filter(Localizacao.status == "ATIVO")
        return q.order_by(Localizacao.codigo).all()
