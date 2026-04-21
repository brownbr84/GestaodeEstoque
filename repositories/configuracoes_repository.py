from sqlalchemy.orm import Session
from database.models import Configuracoes
from repositories.base_repository import BaseRepository
from typing import Optional

class ConfiguracoesRepository(BaseRepository[Configuracoes]):
    def __init__(self):
        super().__init__(Configuracoes)
        
    def get_config(self, session: Session) -> Optional[Configuracoes]:
        return session.query(Configuracoes).filter(Configuracoes.id == 1).first()
