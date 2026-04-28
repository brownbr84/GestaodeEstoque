# repositories/documento_fiscal_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import DocumentoFiscal, RegraOperacaoFiscal
from repositories.base_repository import BaseRepository


class DocumentoFiscalRepository(BaseRepository[DocumentoFiscal]):

    def __init__(self):
        super().__init__(DocumentoFiscal)

    def listar_por_status(self, session: Session, status: str, limit: int = 100) -> List[DocumentoFiscal]:
        return (
            session.query(DocumentoFiscal)
            .filter(DocumentoFiscal.status == status.upper())
            .order_by(DocumentoFiscal.criado_em.desc())
            .limit(limit)
            .all()
        )

    def listar_todos(self, session: Session, limit: int = 200) -> List[DocumentoFiscal]:
        return (
            session.query(DocumentoFiscal)
            .order_by(DocumentoFiscal.criado_em.desc())
            .limit(limit)
            .all()
        )

    def listar_remessas_abertas(self, session: Session) -> List[DocumentoFiscal]:
        """Remessas sem retorno vinculado — candidatas a vincular em um Retorno de Conserto."""
        return (
            session.query(DocumentoFiscal)
            .filter(
                DocumentoFiscal.subtipo == "REMESSA_CONSERTO",
                DocumentoFiscal.status.in_(["RASCUNHO", "PRONTA_EMISSAO", "EMITIDA"]),
                DocumentoFiscal.doc_vinculado_id.is_(None),
            )
            .order_by(DocumentoFiscal.criado_em.desc())
            .all()
        )


class RegraOperacaoFiscalRepository(BaseRepository[RegraOperacaoFiscal]):

    def __init__(self):
        super().__init__(RegraOperacaoFiscal)

    def listar_ativas(self, session: Session) -> List[RegraOperacaoFiscal]:
        return (
            session.query(RegraOperacaoFiscal)
            .filter(RegraOperacaoFiscal.ativo == 1)
            .order_by(RegraOperacaoFiscal.nome)
            .all()
        )

    def get_by_tipo(self, session: Session, tipo_operacao: str) -> Optional[RegraOperacaoFiscal]:
        return (
            session.query(RegraOperacaoFiscal)
            .filter(
                RegraOperacaoFiscal.tipo_operacao == tipo_operacao,
                RegraOperacaoFiscal.ativo == 1,
            )
            .first()
        )
