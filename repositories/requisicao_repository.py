from sqlalchemy.orm import Session
from database.models import Requisicao, RequisicaoItem
from repositories.base_repository import BaseRepository
from typing import List, Optional

class RequisicaoRepository(BaseRepository[Requisicao]):
    def __init__(self):
        super().__init__(Requisicao)
        
    def get_by_status(self, session: Session, status: str) -> List[Requisicao]:
        return session.query(Requisicao).filter(Requisicao.status == status).all()

    def get_itens_by_requisicao(self, session: Session, requisicao_id: int) -> List[RequisicaoItem]:
        return session.query(RequisicaoItem).filter(RequisicaoItem.requisicao_id == requisicao_id).all()
