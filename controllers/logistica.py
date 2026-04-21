# Lógica de split de lotes, transferências
# tracebox/controllers/logistica.py
from database.conexao_orm import SessionLocal
from database.models import Imobilizado, Movimentacao
from repositories.imobilizado_repository import ImobilizadoRepository

def processar_transferencia(id_item, qtd_transferir, qtd_disponivel, destino, origem, usuario_atual):
    """
    Processa a regra de negócio de transferência de ativos.
    Lida automaticamente com a divisão de lotes (Split) se a transferência for parcial.
    Retorna True em caso de sucesso.
    """
    novo_status = 'Em Trânsito'
    
    try:
        with SessionLocal() as db:
            repo = ImobilizadoRepository()
            item = repo.get_by_id(db, id_item)
            if not item: return False
            
            # 1. Regra de Transferência Total
            if qtd_transferir == qtd_disponivel:
                item.localizacao = destino
                item.status = novo_status
                id_mov = item.id
                
            # 2. Regra de Transferência Parcial (Split de Lote)
            else:
                item.quantidade -= qtd_transferir
                
                novo_item = Imobilizado(
                    codigo=item.codigo, descricao=item.descricao, marca=item.marca,
                    modelo=item.modelo, num_tag=item.num_tag, quantidade=qtd_transferir,
                    status=novo_status, localizacao=destino, categoria=item.categoria,
                    valor_unitario=item.valor_unitario, data_aquisicao=item.data_aquisicao,
                    dimensoes=item.dimensoes, capacidade=item.capacidade,
                    ultima_manutencao=item.ultima_manutencao, proxima_manutencao=item.proxima_manutencao,
                    detalhes=item.detalhes, imagem=item.imagem, tipo_material=item.tipo_material,
                    categoria_id=item.categoria_id, fornecedor_id=item.fornecedor_id
                )
                db.add(novo_item)
                db.flush()
                id_mov = novo_item.id
                
            # 3. Registo de Auditoria
            nova_mov = Movimentacao(
                ferramenta_id=id_mov, tipo='Envio para Transferência',
                responsavel=usuario_atual, destino_projeto=destino,
                documento=f"Origem: {origem}"
            )
            db.add(nova_mov)
            db.commit()
            return True
            
    except Exception as e:
        return False