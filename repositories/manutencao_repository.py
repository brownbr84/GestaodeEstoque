from sqlalchemy.orm import Session
from database.models import ManutencaoOrdem, Imobilizado
from repositories.base_repository import BaseRepository
from typing import List, Tuple

class ManutencaoRepository(BaseRepository[ManutencaoOrdem]):
    def __init__(self):
        super().__init__(ManutencaoOrdem)
        
    def get_ordens_abertas(self, session: Session) -> List[Tuple[ManutencaoOrdem, Imobilizado]]:
        return session.query(ManutencaoOrdem, Imobilizado).join(
            Imobilizado, ManutencaoOrdem.ferramenta_id == Imobilizado.id
        ).filter(ManutencaoOrdem.status_ordem == 'Aberta').all()

    def get_ordens_aguardando_aprovacao(self, session: Session) -> List[Tuple[ManutencaoOrdem, Imobilizado]]:
        return session.query(ManutencaoOrdem, Imobilizado).join(
            Imobilizado, ManutencaoOrdem.ferramenta_id == Imobilizado.id
        ).filter(ManutencaoOrdem.status_ordem == 'Aguardando Aprovação').all()

    def get_ordens_em_execucao(self, session: Session) -> List[Tuple[ManutencaoOrdem, Imobilizado]]:
        return session.query(ManutencaoOrdem, Imobilizado).join(
            Imobilizado, ManutencaoOrdem.ferramenta_id == Imobilizado.id
        ).filter(ManutencaoOrdem.status_ordem == 'Em Execução').all()

    def get_historico_concluidas(self, session: Session, ferramenta_id: int) -> List[ManutencaoOrdem]:
        return session.query(ManutencaoOrdem).filter(
            ManutencaoOrdem.ferramenta_id == ferramenta_id,
            ManutencaoOrdem.status_ordem == 'Concluída'
        ).order_by(ManutencaoOrdem.data_saida.desc()).all()
