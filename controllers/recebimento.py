# tracebox/controllers/recebimento.py
from database.queries import executar_query

def processar_retorno_projeto(selecoes, polo_destino, proj_origem, usuario_atual):
    """Processa o recebimento de itens voltando de uma obra/projeto."""
    houve_falta_neste_lote = False
    
    for id_item, d in selecoes.items():
        local_final = "Manutenção" if d['status'] == "Manutenção" else polo_destino

        if d['qtd'] == d['qtd_max']:
            executar_query("UPDATE imobilizado SET localizacao = ?, status = ?, alerta_falta = 0 WHERE id = ?", (local_final, d['status'], id_item))
            id_mov = id_item
        else:
            houve_falta_neste_lote = True
            executar_query("UPDATE imobilizado SET quantidade = quantidade - ?, alerta_falta = 1 WHERE id = ?", (d['qtd'], id_item))
            id_mov = executar_query(f"""
                INSERT INTO imobilizado (codigo, descricao, marca, modelo, num_tag, quantidade, status, localizacao, categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material, alerta_falta)
                SELECT codigo, descricao, marca, modelo, num_tag, {d['qtd']}, '{d['status']}', '{local_final}', categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material, 0
                FROM imobilizado WHERE id = {id_item}
            """)
        
        executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Devolução', ?, ?, ?)", 
                      (id_mov, usuario_atual, local_final, f"Retorno de {proj_origem}"))

    return 'parcial' if houve_falta_neste_lote else 'total'

def processar_recebimento_transferencia(selecoes_transito, polo_recebedor, usuario_atual):
    """Processa a chegada de uma carreta de transferência entre Polos."""
    for id_transf in selecoes_transito:
        executar_query("UPDATE imobilizado SET status = 'Disponível' WHERE id = ?", (id_transf,))
        executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Recebimento Transferência', ?, ?, 'Carga Recebida')", (id_transf, usuario_atual, polo_recebedor))
    return True

def processar_reintegracao_falta(id_db, qtd_encontrada, qtd_pendente, destino_retorno, usuario_atual):
    """Caso o Gestor encontre o item que estava faltando, ele volta para o estoque."""
    if qtd_encontrada == qtd_pendente:
        executar_query("UPDATE imobilizado SET localizacao = ?, status = 'Disponível', alerta_falta = 0 WHERE id = ?", (destino_retorno, id_db))
    else:
        executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_encontrada, id_db))
        executar_query(f"INSERT INTO imobilizado (codigo, descricao, quantidade, status, localizacao, alerta_falta) SELECT codigo, descricao, {qtd_encontrada}, 'Disponível', '{destino_retorno}', 0 FROM imobilizado WHERE id = {id_db}")
    
    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Material Localizado', ?, ?, 'Reintegração')", (id_db, usuario_atual, destino_retorno))
    return True

def processar_baixa_extravio(id_db, qtd_perda, qtd_pendente, projeto_origem, motivo, usuario_atual):
    """Caso o item tenha sido realmente roubado ou perdido na obra."""
    local_ext = f"Extravio: {projeto_origem}"
    
    if qtd_perda == qtd_pendente:
        executar_query("UPDATE imobilizado SET status = 'Extraviado', localizacao = ?, alerta_falta = 0 WHERE id = ?", (local_ext, id_db))
    else:
        executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_perda, id_db))
        executar_query(f"INSERT INTO imobilizado (codigo, descricao, quantidade, status, localizacao, alerta_falta) SELECT codigo, descricao, {qtd_perda}, 'Extraviado', '{local_ext}', 0 FROM imobilizado WHERE id = {id_db}")
    
    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Baixa por Perda', ?, ?, ?)", (id_db, usuario_atual, local_ext, motivo))
    return True

def processar_entrada_compra(codigo_produto, polo_destino, nf, valor_unit, quantidade, tags_str, usuario_atual):
    """
    Processa a entrada de uma nova compra via Nota Fiscal.
    Usa o código Master Data para clonar as características do produto.
    """
    from datetime import datetime
    
    # 1. Puxa as características "Molde" do Master Data
    df_molde = carregar_dados("SELECT * FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo_produto,))
    if df_molde.empty:
        return False, "Produto Master Data não encontrado."
    
    molde = df_molde.iloc[0]
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    
    # Prepara a query de inserção baseada no molde
    query_insert = """
        INSERT INTO imobilizado 
        (codigo, descricao, marca, modelo, categoria, dimensoes, capacidade, tipo_material, 
         num_tag, quantidade, status, localizacao, valor_unitario, data_aquisicao, alerta_falta) 
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 0)
    """
    
    lista_tags = [t.strip().upper() for t in tags_str.split(',')] if tags_str.strip() else []
    
    sucesso = False
    # 2A. Entrada com Rastreabilidade (TAGs)
    if lista_tags:
        for tag in lista_tags:
            if not tag: continue
            
            n_id = executar_query(query_insert, (
                molde['codigo'], molde['descricao'], molde['marca'], molde['modelo'], 
                molde['categoria'], molde['dimensoes'], molde['capacidade'], molde['tipo_material'],
                tag, 1, 'Disponível', polo_destino, valor_unit, data_hoje
            ))
            if n_id:
                executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Entrada via Compra', ?, ?, ?)", 
                              (n_id, usuario_atual, polo_destino, f"NF: {nf}"))
                sucesso = True
                
    # 2B. Entrada de Lote Volumétrico (Sem TAG)
    else:
        n_id = executar_query(query_insert, (
            molde['codigo'], molde['descricao'], molde['marca'], molde['modelo'], 
            molde['categoria'], molde['dimensoes'], molde['capacidade'], molde['tipo_material'],
            "", quantidade, 'Disponível', polo_destino, valor_unit, data_hoje
        ))
        if n_id:
            executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Entrada via Compra', ?, ?, ?)", 
                          (n_id, usuario_atual, polo_destino, f"NF: {nf}"))
            sucesso = True

    return sucesso, "Entrada processada com sucesso."