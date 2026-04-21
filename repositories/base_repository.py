from typing import TypeVar, Generic, Type, List, Optional
from sqlalchemy.orm import Session

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    def get_by_id(self, session: Session, id: int) -> Optional[T]:
        return session.query(self.model).filter(self.model.id == id).first()

    def get_all(self, session: Session) -> List[T]:
        return session.query(self.model).all()

    def create(self, session: Session, obj: T) -> T:
        session.add(obj)
        session.flush()
        return obj

    def update(self, session: Session, obj: T) -> T:
        session.merge(obj)
        session.flush()
        return obj

    def delete(self, session: Session, obj: T) -> None:
        session.delete(obj)
        session.flush()
