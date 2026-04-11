# tracebox/controllers/manutencao.py
from database.queries import executar_query, carregar_dados
from datetime import datetime

def abrir_ordem_manutencao(ferramenta_id, codigo, motivo, solicitante, usuario_atual):
    # Regra: Impede duplicidade na oficina
    check = carregar_dados("SELECT id FROM manutencao_ordens WHERE ferramenta_id = ? AND status_ordem NOT IN ('Concluída', 'Sucateado')", (ferramenta_id,))
    if not check.empty:
        return False, "Este item específico já está na oficina."

    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Busca informações do item para saber se é Lote (>1) ou Único (1)
    df_item = carregar_dados("SELECT quantidade FROM imobilizado WHERE id = ?", (ferramenta_id,))
    qtd_atual = float(df_item.iloc[0]['quantidade']) if not df_item.empty else 0

    id_para_oficina = ferramenta_id

    # LÓGICA DE SPLIT (DIVISÃO DE LOTE)
    if qtd_atual > 1:
        # 1. Tira 1 unidade do estoque principal
        executar_query("UPDATE imobilizado SET quantidade = quantidade - 1 WHERE id = ?", (ferramenta_id,))
        
        # 2. Clona o item criando um novo registro só para a unidade avariada
        query_dup = """
            INSERT INTO imobilizado (codigo, descricao, categoria, valor_unitario, num_tag, status, localizacao, quantidade, alerta_falta)
            SELECT codigo, descricao, categoria, valor_unitario, num_tag, 'Manutenção', 'Oficina', 1, alerta_falta
            FROM imobilizado WHERE id = ?
        """
        executar_query(query_dup, (ferramenta_id,))
        
        # 3. Descobre o ID desse novo item clonado
        df_novo = carregar_dados("SELECT id FROM imobilizado ORDER BY id DESC LIMIT 1")
        id_para_oficina = int(df_novo.iloc[0]['id'])
    else:
        # Se for unidade única (TAG), só atualiza o status
        executar_query("UPDATE imobilizado SET status = 'Manutenção', localizacao = 'Oficina' WHERE id = ?", (ferramenta_id,))

    # Cria a OS com o ID correto (seja o original ou o clonado)
    query_os = """
        INSERT INTO manutencao_ordens 
        (ferramenta_id, codigo_ferramenta, data_entrada, motivo_falha, solicitante, status_ordem) 
        VALUES (?, ?, ?, ?, ?, 'Aberta')
    """
    executar_query(query_os, (id_para_oficina, codigo, agora, motivo, solicitante))
    
    # Log de Auditoria
    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Envio Manutenção', ?, 'Oficina', ?)", 
                  (id_para_oficina, usuario_atual, f"Avaria reportada por {solicitante}"))
    
    return True, "Chamado aberto com sucesso! Estoque atualizado."

def lancar_orcamento_oficina(ordem_id, diagnostico, custo_estimado, mecanico, empresa, num_orcamento):
    query = """
        UPDATE manutencao_ordens 
        SET diagnostico = ?, custo_reparo = ?, mecanico_responsavel = ?, 
            empresa_reparo = ?, num_orcamento = ?, status_ordem = 'Aguardando Aprovação' 
        WHERE id = ?
    """
    executar_query(query, (diagnostico, custo_estimado, mecanico, empresa, num_orcamento, ordem_id))
    return True

def aprovar_manutencao(ordem_id, decisao):
    if decisao == "Aprovar":
        executar_query("UPDATE manutencao_ordens SET status_ordem = 'Em Execução' WHERE id = ?", (ordem_id,))
    else:
        df_os = carregar_dados("SELECT ferramenta_id FROM manutencao_ordens WHERE id = ?", (ordem_id,))
        if not df_os.empty:
            id_f = int(df_os.iloc[0]['ferramenta_id'])
            executar_query("UPDATE imobilizado SET status = 'Sucateado', quantidade = 0 WHERE id = ?", (id_f,))
            executar_query("UPDATE manutencao_ordens SET status_ordem = 'Sucateado', data_saida = date('now') WHERE id = ?", (ordem_id,))
    return True

def finalizar_reparo_oficina(ordem_id, ferramenta_id, polo_destino, usuario_atual):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    executar_query("UPDATE manutencao_ordens SET data_saida = ?, status_ordem = 'Concluída' WHERE id = ?", (agora, ordem_id))
    executar_query("UPDATE imobilizado SET status = 'Disponível', localizacao = ? WHERE id = ?", (polo_destino, ferramenta_id))
    
    df_os = carregar_dados("SELECT empresa_reparo FROM manutencao_ordens WHERE id = ?", (ordem_id,))
    empresa = df_os.iloc[0]['empresa_reparo'] if not df_os.empty and df_os.iloc[0]['empresa_reparo'] else "Oficina Interna"
    
    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Retorno Manutenção', ?, ?, ?)", 
                  (ferramenta_id, usuario_atual, polo_destino, f"OS-{ordem_id} concluída por {empresa}"))
    return True