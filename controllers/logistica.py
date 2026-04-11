# Lógica de split de lotes, transferências
# tracebox/controllers/logistica.py
from database.queries import executar_query

def processar_transferencia(id_item, qtd_transferir, qtd_disponivel, destino, origem, usuario_atual):
    """
    Processa a regra de negócio de transferência de ativos.
    Lida automaticamente com a divisão de lotes (Split) se a transferência for parcial.
    Retorna True em caso de sucesso.
    """
    novo_status = 'Em Trânsito'
    
    try:
        # 1. Regra de Transferência Total
        if qtd_transferir == qtd_disponivel:
            executar_query("UPDATE imobilizado SET localizacao = ?, status = ? WHERE id = ?", (destino, novo_status, id_item))
            id_mov = id_item
            
        # 2. Regra de Transferência Parcial (Split de Lote)
        else:
            # Subtrai da origem
            executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_transferir, id_item))
            
            # Cria a nova "caixa" em trânsito com a quantidade exata
            id_mov = executar_query(f"""
                INSERT INTO imobilizado (codigo, descricao, marca, modelo, num_tag, quantidade, status, localizacao, categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material) 
                SELECT codigo, descricao, marca, modelo, num_tag, {qtd_transferir}, '{novo_status}', '{destino}', categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material 
                FROM imobilizado WHERE id = {id_item}
            """)
            
        # 3. Registo de Auditoria
        executar_query(
            "INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Envio para Transferência', ?, ?, ?)", 
            (id_mov, usuario_atual, destino, f"Origem: {origem}")
        )
        return True
        
    except Exception as e:
        # Se algo falhar (ex: falha na base de dados), o sistema não crasha.
        return False