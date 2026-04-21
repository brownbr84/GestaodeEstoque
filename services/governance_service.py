# services/governance_service.py
import logging
from sqlalchemy.orm import Session
from database.models import LogAuditoria
from datetime import datetime

logger = logging.getLogger(__name__)


class GovernanceService:
    @staticmethod
    def registar_log(session: Session, usuario: str, tabela: str, registro_id: int, acao: str, detalhes: str):
        """
        Grava um rastro de auditoria de forma padronizada.

        Interrompe o processo (raise) em caso de falha para garantir que
        nenhuma operação de estoque seja confirmada sem rastro de auditoria.
        """
        try:
            novo_log = LogAuditoria(
                usuario=usuario,
                tabela=tabela,
                registro_id=registro_id,
                acao=acao,
                detalhes=detalhes,
                data_hora=datetime.now()
            )
            session.add(novo_log)
        except Exception as e:
            # Loga o erro de forma independente do contexto de UI
            logger.critical(
                "FALHA CRÍTICA NA AUDITORIA | usuário=%s | ação=%s | erro=%s",
                usuario, acao, str(e)
            )
            # Interrompe o processo para não salvar no estoque sem auditoria
            raise e