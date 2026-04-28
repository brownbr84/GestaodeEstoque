# repositories/emitente_repository.py
from typing import Optional
from sqlalchemy.orm import Session
from database.models import EmpresaEmitente
from repositories.base_repository import BaseRepository


class EmitenteRepository(BaseRepository[EmpresaEmitente]):

    def __init__(self):
        super().__init__(EmpresaEmitente)

    def get_ativo(self, session: Session) -> Optional[EmpresaEmitente]:
        return (
            session.query(EmpresaEmitente)
            .filter(EmpresaEmitente.ativo == 1)
            .first()
        )
