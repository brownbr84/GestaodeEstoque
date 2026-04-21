# services/requisicao_service.py
from sqlalchemy.orm import Session
from datetime import datetime
from database.models import Requisicao, RequisicaoItem
from services.governance_service import GovernanceService

class RequisicaoService:
    @staticmethod
    def salvar_nova_requisicao(session: Session, polo_origem: str, destino: str, solicitante: str, itens: list):
        try:
            agora = datetime.now()

            # 1. Cria a requisição (ORM garante a captura do ID sem race conditions)
            nova_req = Requisicao(
                solicitante=solicitante,
                polo_origem=polo_origem,
                destino_projeto=destino,
                status='Pendente',
                data_solicitacao=agora
            )
            session.add(nova_req)
            session.flush() # 🚀 A MÁGICA: Salva no cache do banco e já pega o ID exato gerado!

            # 2. Insere os itens vinculados ao ID exato
            for item in itens:
                cod = item.get('codigo', item.get('CÓD', ''))
                desc = item.get('descricao', item.get('ITEM', ''))
                qtd_raw = item.get('quantidade', item.get('QTD', 1))
                
                # Tratamento de segurança para números
                qtd_txt = str(qtd_raw).strip()
                qtd_int = int(float(qtd_txt)) if qtd_txt and qtd_txt.lower() != 'none' else 1

                novo_item = RequisicaoItem(
                    requisicao_id=nova_req.id,
                    codigo_produto=cod,
                    descricao_produto=desc,
                    quantidade_solicitada=qtd_int
                )
                session.add(novo_item)

            # 3. Log de Auditoria (Compliance Oculto)
            detalhes_log = f"Nova requisição (REQ-{nova_req.id}) criada para {destino}. Contém {len(itens)} item(ns)."
            GovernanceService.registar_log(session, solicitante, 'requisicoes', nova_req.id, 'NOVA_REQUISICAO', detalhes_log)

            session.commit()
            return True, f"Requisição REQ-{nova_req.id:04d} gerada com sucesso!"
            
        except Exception as e:
            session.rollback()
            return False, f"Erro interno ao salvar requisição: {str(e)}"