from sqlalchemy.orm import Session
from datetime import datetime
import pandas as pd
from database.models import Imobilizado, Movimentacao, Requisicao
from services.governance_service import GovernanceService

class OutboundService:

    @staticmethod
    def cancelar_pedido(session: Session, req_id: int, motivo: str, usuario: str):
        try:
            req = session.query(Requisicao).filter(Requisicao.id == req_id).first()
            if not req:
                return False, "Pedido não encontrado."
            
            # 1. Prepara o rastro antes da alteração
            detalhes_log = f"Pedido cancelado. Motivo informado: {motivo}"
            
            # 2. Realiza a alteração no pedido
            req.status = 'Cancelada'
            req.motivo_cancelamento = motivo
            req.cancelado_por = usuario

            # 3. Regista na auditoria (na mesma transação!)
            GovernanceService.registar_log(
                session, usuario, 'requisicoes', req_id, 'CANCELAMENTO', detalhes_log
            )

            session.commit()
            return True, "Pedido cancelado com sucesso."
        except Exception as e:
            session.rollback()
            return False, f"Erro ao cancelar: {str(e)}"

    @staticmethod
    def despachar_pedido_wms(session: Session, req_id: int, polo: str, destino: str, conferidos_tags: dict, conferidos_lotes: dict, itens_pedido: pd.DataFrame, usuario: str):
        agora = datetime.now()
        doc_ref = f"OUT-REQ{req_id:04d}-{agora.strftime('%H%M')}"
        
        is_transferencia = "FILIAL" in str(destino).strip().upper()
        novo_status_ativo = 'Em Trânsito' if is_transferencia else 'Em Uso'
        tipo_mov = 'Envio Transferência' if is_transferencia else 'Saída Operação'

        try:
            # 1. Atualiza status do pedido
            req = session.query(Requisicao).filter(Requisicao.id == req_id).first()
            if req: req.status = 'Concluída'

            # 2. Processa cada item do romaneio
            for _, row in itens_pedido.iterrows():
                codigo = row['codigo']
                qtd_pedida = int(row['qtd'])

                if row['exige_tag']:
                    # É ATIVO: processa cada TAG individual
                    tags_info = conferidos_tags.get(codigo, [])
                    for info in tags_info:
                        tag_str = info['tag'].upper()
                        metodo = info['metodo']

                        # Busca e atualiza a ferramenta específica
                        item = session.query(Imobilizado).filter(Imobilizado.num_tag.ilike(tag_str)).first()
                        if item:
                            item.status = novo_status_ativo
                            item.localizacao = destino
                            
                            detalhes = f"Ref: {doc_ref} [Via {metodo}]"
                            mov = Movimentacao(ferramenta_id=item.id, tipo=tipo_mov, responsavel=usuario, destino_projeto=destino, documento=detalhes, data_movimentacao=agora)
                            session.add(mov)
                else:
                    # É LOTE/CONSUMO: Deduz quantidade do bolo
                    qtd_separada = conferidos_lotes.get(codigo, qtd_pedida)
                    if qtd_separada > 0:
                        lote = session.query(Imobilizado).filter(
                            Imobilizado.codigo == codigo, Imobilizado.localizacao == polo, 
                            Imobilizado.status == 'Disponível', 
                            (Imobilizado.num_tag == None) | (Imobilizado.num_tag == '')
                        ).first()
                        
                        if lote:
                            if lote.quantidade < qtd_separada:
                                raise ValueError(f"Saldo insuficiente para o item {codigo}. Disponível: {lote.quantidade}, Solicitado: {qtd_separada}")
                            lote.quantidade -= qtd_separada
                            id_alvo_mov = lote.id

                            # Se for transferência, cria uma "cópia" do lote no caminhão (Em Trânsito)
                            if is_transferencia:
                                novo_lote = Imobilizado(
                                    codigo=lote.codigo, descricao=lote.descricao, marca=lote.marca, modelo=lote.modelo,
                                    num_tag="", quantidade=qtd_separada, status='Em Trânsito', localizacao=destino,
                                    categoria=lote.categoria, valor_unitario=lote.valor_unitario, tipo_material=lote.tipo_material,
                                    alerta_falta=0, tipo_controle=lote.tipo_controle
                                )
                                session.add(novo_lote)
                                session.flush()
                                id_alvo_mov = novo_lote.id

                            mov = Movimentacao(ferramenta_id=id_alvo_mov, tipo=tipo_mov, responsavel=usuario, destino_projeto=destino, documento=f"Ref: {doc_ref} Qtd: {qtd_separada}", data_movimentacao=agora)
                            session.add(mov)

            # 👉 LOG DE AUDITORIA PARA A BAIXA DA REQUISIÇÃO
            detalhes_log = f"Saída concluída para a REQ-{req_id:04d}. Destino: {destino}. Doc Ref: {doc_ref}"
            GovernanceService.registar_log(
                session, usuario, 'requisicoes', req_id, 'BAIXA_REQUISICAO', detalhes_log
            )

            # 3. Confirma tudo atômicamente
            session.commit()
            msg = "Carga em Trânsito enviada!" if is_transferencia else "Pedido de Obra despachado!"
            return True, doc_ref, msg

        except Exception as e:
            session.rollback()
            return False, "", f"Erro ao despachar: {str(e)}"

    @staticmethod
    def realizar_baixa_excepcional(session: Session, carrinho: list, motivo: str, documento: str, usuario: str, polo: str, perfil_usuario: str = "Operador"):
        try:
            if perfil_usuario.upper() not in ["ADMIN", "ADM", "GESTOR"]:
                return False, "Operação negada: Apenas administradores ou gestores podem realizar baixas excepcionais."
            agora = datetime.now()
            tipo_mov = f"Baixa Excepcional - {motivo}"
            doc_ref = f"{documento} | BXA-{agora.strftime('%H%M%S')}"

            for item in carrinho:
                id_item = int(item['id'])
                db_item = session.query(Imobilizado).filter(Imobilizado.id == id_item).first()
                if not db_item: continue

                if item['tipo'] == 'ATIVO':
                    db_item.status = 'Baixado'
                    mov = Movimentacao(ferramenta_id=id_item, tipo=tipo_mov, responsavel=usuario, destino_projeto='Ajuste/Sucata', documento=doc_ref, data_movimentacao=agora)
                    session.add(mov)
                else:
                    qtd_baixar = int(item['qtd_baixar'])
                    if db_item.quantidade < qtd_baixar:
                        raise ValueError(f"Saldo insuficiente para baixar o lote {db_item.codigo}.")
                    db_item.quantidade -= qtd_baixar
                    detalhes_lote = f"{doc_ref} | Qtd Baixada: {qtd_baixar}"
                    mov = Movimentacao(ferramenta_id=id_item, tipo=tipo_mov, responsavel=usuario, destino_projeto='Ajuste/Sucata', documento=detalhes_lote, data_movimentacao=agora)
                    session.add(mov)

            # 👉 LOG DE AUDITORIA PARA A BAIXA EXCEPCIONAL
            detalhes_log = f"Baixa Excepcional realizada no polo {polo}. Motivo: {motivo}. Documento de Ref: {doc_ref}"
            GovernanceService.registar_log(
                session, usuario, 'imobilizado', 0, 'BAIXA_EXCEPCIONAL', detalhes_log
            )

            session.commit()
            return True, "✅ Baixa Excepcional registada e auditada com sucesso!"
        except Exception as e:
            session.rollback()
            return False, f"Erro no banco de dados: {str(e)}"