from sqlalchemy.orm import Session
from database.models import Usuario
from repositories.base_repository import BaseRepository
from typing import Optional

class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self):
        super().__init__(Usuario)
        
    def get_by_username(self, session: Session, username: str) -> Optional[Usuario]:
        return session.query(Usuario).filter(Usuario.usuario == username).first()
