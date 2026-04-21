# services/inventario_service.py
from sqlalchemy.orm import Session
from datetime import datetime
from database.models import Imobilizado, Movimentacao
from services.governance_service import GovernanceService

class InventarioService:

    @staticmethod
    def processar_resultados_inventario(session: Session, resultados: list, usuario_atual: str, polo: str, inventario_id: str):
        erros = []
        agora = datetime.now()

        # 1. Validação de Regra de Negócio (Antes de tocar no banco)
        for res in resultados:
            if res['qtd_fisica'] != res['qtd_sistema'] and len(res.get('justificativa', '')) < 4:
                erros.append(f"Atenção: Justificativa obrigatória para divergência no item {res['ids_originais']}")
                
        if erros:
            return False, erros

        try:
            # 2. Processamento Transacional
            for res in resultados:
                qtd_fisica = res['qtd_fisica']
                qtd_sistema = res['qtd_sistema']
                justificativa = res.get('justificativa', '')
                
                # Garante que ids_originais seja uma lista para podermos iterar
                ids_originais = res['ids_originais'] if isinstance(res['ids_originais'], list) else [res['ids_originais']]
                
                # A. Tratamento de Lotes (Consumo)
                if res['is_lote'] and qtd_fisica != qtd_sistema:
                    total_contado = qtd_fisica
                    for i, id_origem in enumerate(ids_originais):
                        nova_qtd = total_contado if i == 0 else 0
                        status_n = 'Disponível' if nova_qtd > 0 else 'Extraviado'
                        
                        item = session.query(Imobilizado).filter(Imobilizado.id == id_origem).first()
                        if item:
                            item.quantidade = nova_qtd
                            item.status = status_n
                
                # B. Tratamento de Unitários (Ativos/TAGs)
                elif not res['is_lote'] and qtd_fisica != qtd_sistema:
                    status_t = 'Disponível' if qtd_fisica == 1 else 'Extraviado'
                    item = session.query(Imobilizado).filter(Imobilizado.id == ids_originais[0]).first()
                    if item:
                        item.quantidade = qtd_fisica
                        item.status = status_t

                # 3. Rastreabilidade Logística (Movimentações Visíveis)
                tipo_log = "Auditoria Cíclica OK" if qtd_fisica == qtd_sistema else "Ajuste de Inventário"
                msg_movimentacao = f"[{inventario_id}] Físico: {qtd_fisica}. Just: {justificativa}"
                
                for id_log in ids_originais:
                    mov = Movimentacao(
                        ferramenta_id=id_log, tipo=tipo_log, responsavel=usuario_atual, 
                        destino_projeto=polo, documento=msg_movimentacao, data_movimentacao=agora
                    )
                    session.add(mov)

                    # 👉 4. GOVERNANÇA: Auditoria Oculta (Apenas quando há divergência)
                    if qtd_fisica != qtd_sistema:
                        # Puxa a TAG para o log se ela existir
                        tag_str = f" [TAG: {item.num_tag}]" if item and item.num_tag else ""
                        detalhes_audit = f"Ajuste de Inventário {inventario_id}. Sistema esperava {qtd_sistema}, Operador contou {qtd_fisica}. Motivo: {justificativa}{tag_str}"
                        GovernanceService.registar_log(session, usuario_atual, 'imobilizado', id_log, 'AJUSTE_ESTOQUE', detalhes_audit)

            # Grava tudo de uma vez
            session.commit()
            return True, []
            
        except Exception as e:
            session.rollback()
            return False, [f"Erro interno no banco de dados ao salvar inventário: {str(e)}"]

    @staticmethod
    def reativar_tag_extraviada(session: Session, tag: str, polo: str, motivo: str, usuario: str):
        try:
            # Procura exatamente a TAG que está dada como perdida
            item = session.query(Imobilizado).filter(
                Imobilizado.num_tag.ilike(tag), 
                Imobilizado.status == 'Extraviado'
            ).first()
            
            if not item:
                return False, f"A TAG '{tag}' não foi encontrada com status 'Extraviado'."
            
            # Ressuscita o item
            item.status = 'Disponível'
            item.localizacao = polo
            item.quantidade = 1

            # Log Logístico (Movimentação)
            mov = Movimentacao(
                ferramenta_id=item.id, tipo='Reativação de Ativo', 
                responsavel=usuario, destino_projeto=polo, 
                documento=f"Item Encontrado: {motivo}", data_movimentacao=datetime.now()
            )
            session.add(mov)

            # Log de Compliance (Auditoria)
            GovernanceService.registar_log(
                session, usuario, 'imobilizado', item.id, 'REATIVACAO_TAG', 
                f"A TAG {tag} foi reativada e retornou ao estoque de {polo}. Relato: {motivo}"
            )

            session.commit()
            return True, f"✅ TAG {tag} reativada com sucesso no polo {polo}!"
        except Exception as e:
            session.rollback()
            return False, f"Erro interno: {str(e)}"