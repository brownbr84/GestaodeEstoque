# tracebox/controllers/inbound.py
import pandas as pd
from datetime import datetime
from database.queries import executar_query, carregar_dados

def configurar_tabela_inbound():
    """Garante que a coluna de alerta de falta existe na base, de forma silenciosa e segura."""
    df_schema = carregar_dados("PRAGMA table_info(imobilizado)")
    
    if not df_schema.empty:
        colunas = df_schema['name'].str.lower().tolist()
        if 'alerta_falta' not in colunas:
            executar_query("ALTER TABLE imobilizado ADD COLUMN alerta_falta INTEGER DEFAULT 0")

# ==========================================
# MÓDULO 1: COMPRAS (ENTRADA DE NOTA FISCAL)
# ==========================================
def processar_entrada_compra(codigo_produto, polo_destino, nf, valor_unit, quantidade, tags_str, usuario):
    df_molde = carregar_dados("SELECT * FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo_produto,))
    if df_molde.empty: return False, "Produto Master Data não encontrado."
    
    molde = df_molde.iloc[0]
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    lista_tags = [t.strip().upper() for t in tags_str.split(',')] if tags_str.strip() else []
    sucesso = False
    
    query_insert = """
        INSERT INTO imobilizado 
        (codigo, descricao, marca, modelo, categoria, dimensoes, capacidade, tipo_material, 
         num_tag, quantidade, status, localizacao, valor_unitario, data_aquisicao, alerta_falta) 
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 0)
    """

    if lista_tags: # Ativos com TAG
        for tag in lista_tags:
            if not tag: continue
            n_id = executar_query(query_insert, (
                molde['codigo'], molde['descricao'], molde['marca'], molde['modelo'], 
                molde['categoria'], molde['dimensoes'], molde['capacidade'], molde['tipo_material'],
                tag, 1, 'Disponível', polo_destino, valor_unit, data_hoje
            ))
            if n_id:
                executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Entrada via Compra', ?, ?, ?)", (n_id, usuario, polo_destino, f"NF: {nf}"))
                sucesso = True
    else: # Lote Consumível
        n_id = executar_query(query_insert, (
            molde['codigo'], molde['descricao'], molde['marca'], molde['modelo'], 
            molde['categoria'], molde['dimensoes'], molde['capacidade'], molde['tipo_material'],
            "", quantidade, 'Disponível', polo_destino, valor_unit, data_hoje
        ))
        if n_id:
            executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Entrada via Compra', ?, ?, ?)", (n_id, usuario, polo_destino, f"NF: {nf}"))
            sucesso = True

    return sucesso, "Entrada processada com sucesso!"

# ==========================================
# MÓDULO 2: DOCA DE DESCARGA WMS
# ==========================================
def obter_origens_esperadas(polo_atual):
    df_obras = carregar_dados("SELECT DISTINCT localizacao FROM imobilizado WHERE status = 'Em Uso' AND quantidade > 0")
    obras = [f"🏗️ Obra: {loc}" for loc in df_obras['localizacao'].tolist() if str(loc).strip()]
    
    df_transf = carregar_dados("SELECT COUNT(id) as qtd FROM imobilizado WHERE status = 'Em Trânsito' AND localizacao = ? AND quantidade > 0", (polo_atual,))
    if not df_transf.empty and df_transf.iloc[0]['qtd'] > 0:
        obras.insert(0, "🚚 Carga de Transferência")
    return obras

def carregar_itens_esperados(origem, polo):
    if "Carga de Transferência" in origem:
        return carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, tipo_material FROM imobilizado WHERE status = 'Em Trânsito' AND localizacao = ? AND quantidade > 0", (polo,))
    else:
        nome_obra = origem.replace("🏗️ Obra: ", "").strip()
        return carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, tipo_material FROM imobilizado WHERE status = 'Em Uso' AND localizacao = ? AND quantidade > 0", (nome_obra,))

def processar_recebimento_doca(origem, polo_atual, dict_ativos, dict_lotes, df_esperados, usuario):
    from datetime import datetime
    doc_ref = f"INB-{datetime.now().strftime('%H%M%S')}"
    houve_falta = False
    
    try:
        for _, row in df_esperados.iterrows():
            id_db, cod, qtd_esp = int(row['id']), row['codigo'], int(row['quantidade'])
            is_ativo = str(row['tipo_material']).strip().upper() == 'ATIVO'
            
            if is_ativo:
                tag = str(row['num_tag']).upper()
                if tag in dict_ativos:
                    status_q = dict_ativos[tag]['status_qualidade']
                    metodo = dict_ativos[tag].get('metodo', 'Sistema') # Puxa se foi Coletor ou Manual
                    
                    executar_query("UPDATE imobilizado SET localizacao = ?, status = ?, alerta_falta = 0 WHERE id = ?", (polo_atual, status_q, id_db))
                    
                    # Carimbo de Auditoria completo!
                    doc_auditoria = f"{doc_ref} | {status_q} [Via {metodo}]"
                    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Recebimento Inbound', ?, ?, ?)", (id_db, usuario, polo_atual, doc_auditoria))
                else:
                    houve_falta = True
                    executar_query("UPDATE imobilizado SET alerta_falta = 1 WHERE id = ?", (id_db,))
            else:
                if id_db in dict_lotes:
                    dl = dict_lotes[id_db]
                    total_rec = dl['disponivel'] + dl['manutencao'] + dl['sucata']
                    if total_rec < qtd_esp:
                        houve_falta = True
                        executar_query("UPDATE imobilizado SET quantidade = ?, alerta_falta = 1 WHERE id = ?", (qtd_esp - total_rec, id_db))
                    else:
                        executar_query("UPDATE imobilizado SET quantidade = 0, alerta_falta = 0 WHERE id = ?", (id_db,))
                    
                    for qtd, stat in [(dl['disponivel'], 'Disponível'), (dl['manutencao'], 'Manutenção'), (dl['sucata'], 'Sucateado')]:
                        if qtd > 0:
                            id_novo = executar_query(f"INSERT INTO imobilizado (codigo, descricao, quantidade, status, localizacao, categoria, valor_unitario, tipo_material, alerta_falta) SELECT codigo, descricao, {qtd}, '{stat}', '{polo_atual}', categoria, valor_unitario, tipo_material, 0 FROM imobilizado WHERE id = {id_db}")
                            executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Recebimento Lote', ?, ?, ?)", (id_novo, usuario, polo_atual, f"{doc_ref} | {stat}"))
                else:
                    houve_falta = True
                    executar_query("UPDATE imobilizado SET alerta_falta = 1 WHERE id = ?", (id_db,))

        msg = "⚠️ Recebimento PARCIAL! Faltas enviadas para a Malha Fina." if houve_falta else "✅ Recebimento TOTAL concluído!"
        return True, msg, houve_falta
    except Exception as e: return False, str(e), False

# ==========================================
# MÓDULO 3: MALHA FINA (FALTAS)
# ==========================================
def processar_reintegracao_falta(id_db, qtd_enc, qtd_pendente, destino, usuario):
    if qtd_enc == qtd_pendente:
        executar_query("UPDATE imobilizado SET localizacao = ?, status = 'Disponível', alerta_falta = 0 WHERE id = ?", (destino, id_db))
    else:
        executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_enc, id_db))
        executar_query(f"INSERT INTO imobilizado (codigo, descricao, num_tag, quantidade, status, localizacao, alerta_falta, tipo_material) SELECT codigo, descricao, num_tag, {qtd_enc}, 'Disponível', '{destino}', 0, tipo_material FROM imobilizado WHERE id = {id_db}")
    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Material Localizado', ?, ?, 'Reintegração')", (id_db, usuario, destino))
    return True

def processar_baixa_extravio(id_db, qtd_perda, qtd_pendente, origem, motivo, usuario):
    local_ext = f"Extravio: {origem}"
    if qtd_perda == qtd_pendente:
        executar_query("UPDATE imobilizado SET status = 'Extraviado', localizacao = ?, alerta_falta = 0 WHERE id = ?", (local_ext, id_db))
    else:
        executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_perda, id_db))
        executar_query(f"INSERT INTO imobilizado (codigo, descricao, num_tag, quantidade, status, localizacao, alerta_falta, tipo_material) SELECT codigo, descricao, num_tag, {qtd_perda}, 'Extraviado', '{local_ext}', 0, tipo_material FROM imobilizado WHERE id = {id_db}")
    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Baixa por Perda', ?, ?, ?)", (id_db, usuario, local_ext, motivo))
    return True