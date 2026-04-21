from sqlalchemy.orm import Session
from database.models import Imobilizado
from repositories.base_repository import BaseRepository
from typing import List, Optional

class ImobilizadoRepository(BaseRepository[Imobilizado]):
    def __init__(self):
        super().__init__(Imobilizado)
        
    def get_by_codigo(self, session: Session, codigo: str) -> Optional[Imobilizado]:
        return session.query(Imobilizado).filter(Imobilizado.codigo == codigo).first()
        
    def get_by_tag(self, session: Session, tag: str) -> Optional[Imobilizado]:
        return session.query(Imobilizado).filter(Imobilizado.num_tag == tag).first()
        
    def find_tags_like(self, session: Session, prefix: str) -> List[str]:
        resultados = session.query(Imobilizado.num_tag).filter(Imobilizado.num_tag.like(f'{prefix}%')).all()
        return [r[0] for r in resultados if r[0]]
        
    def get_in_use_locations(self, session: Session) -> List[str]:
        resultados = session.query(Imobilizado.localizacao).filter(
            Imobilizado.status == 'Em Uso',
            Imobilizado.quantidade > 0
        ).distinct().all()
        return [r[0] for r in resultados if r[0] and str(r[0]).strip()]
        
    def count_in_transit(self, session: Session, polo: str) -> int:
        return session.query(Imobilizado).filter(
            Imobilizado.status == 'Em Trânsito',
            Imobilizado.localizacao == polo,
            Imobilizado.quantidade > 0
        ).count()
