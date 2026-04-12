# tracebox/controllers/outbound.py
import pandas as pd
import time
from datetime import datetime
from database.queries import executar_query, carregar_dados

def setup_tabelas_outbound():
    df_schema = carregar_dados("PRAGMA table_info(requisicoes)")
    if not df_schema.empty:
        colunas = df_schema['name'].str.lower().tolist()
        if 'motivo_cancelamento' not in colunas: executar_query("ALTER TABLE requisicoes ADD COLUMN motivo_cancelamento TEXT")
        if 'cancelado_por' not in colunas: executar_query("ALTER TABLE requisicoes ADD COLUMN cancelado_por TEXT")

def carregar_fila_pedidos(polo):
    agora_ms = int(time.time() * 1000) # ANTI-CACHE HACK
    query = f"SELECT rowid as true_rowid, * FROM requisicoes WHERE {agora_ms} = {agora_ms}"
    df = carregar_dados(query)
    
    if df.empty: return pd.DataFrame()
    
    df.columns = df.columns.str.lower()
    for col in ['status', 'polo_origem', 'destino_projeto', 'solicitante', 'data_solicitacao']:
        if col not in df.columns: df[col] = ""

    if 'numero sequencial' in df.columns: df['id_real'] = df['numero sequencial']
    elif 'id' in df.columns: df['id_real'] = df['id']
    else: df['id_real'] = df['true_rowid']

    df['id_num'] = df['id_real'].astype(str).str.replace(r'\D+', '', regex=True)
    df['id_num'] = pd.to_numeric(df['id_num'], errors='coerce').fillna(0).astype(int)
    df['id_num'] = df.apply(lambda r: r['true_rowid'] if r['id_num'] == 0 else r['id_num'], axis=1)
    
    df = df[df['id_num'] > 0]
    df['polo_origem_clean'] = df['polo_origem'].astype(str).str.strip().str.upper()
    df['status_clean'] = df['status'].astype(str).str.strip().str.upper()
    
    polo_upper = str(polo).strip().upper()
    df_polo = df[df['polo_origem_clean'] == polo_upper].copy()
    
    return df_polo

def cancelar_pedido(true_rowid, req_id_visual, motivo, usuario):
    try:
        executar_query(
            "UPDATE requisicoes SET status = 'Cancelada', motivo_cancelamento = ?, cancelado_por = ? WHERE rowid = ? OR id = ?", 
            (motivo, usuario, int(true_rowid), int(req_id_visual))
        )
        return True, "Pedido cancelado com sucesso."
    except Exception as e: return False, f"Erro ao cancelar: {str(e)}"

def carregar_detalhes_picking(req_id_visual, polo):
    query = """
        SELECT codigo_produto as codigo, MAX(descricao_produto) as descricao, SUM(quantidade_solicitada) as qtd 
        FROM requisicoes_itens 
        WHERE requisicao_id = ? 
        GROUP BY codigo_produto
    """
    df_itens = carregar_dados(query, (int(req_id_visual),))
    if df_itens.empty: return pd.DataFrame(columns=['codigo', 'descricao', 'qtd', 'exige_tag'])
    
    df_itens['exige_tag'] = True 
    for idx, row in df_itens.iterrows():
        df_tipo = carregar_dados("SELECT tipo_material FROM imobilizado WHERE codigo = ? LIMIT 1", (row['codigo'],))
        if not df_tipo.empty:
            if str(df_tipo.iloc[0]['tipo_material']).strip().upper() != 'ATIVO':
                df_itens.at[idx, 'exige_tag'] = False
                
    return df_itens

def obter_tags_disponiveis(codigo, polo):
    df = carregar_dados("SELECT num_tag FROM imobilizado WHERE codigo = ? AND localizacao = ? AND status = 'Disponível' AND num_tag IS NOT NULL AND trim(num_tag) != ''", (codigo, polo))
    return df['num_tag'].tolist() if not df.empty else []

def listar_itens_em_transito(polo_origem):
    query = "SELECT codigo, descricao, num_tag, quantidade, localizacao as destino, status FROM imobilizado WHERE status = 'Em Trânsito'"
    return carregar_dados(query)

def despachar_pedido_wms(true_rowid, req_id_visual, polo, destino, conferidos_tags, conferidos_lotes, itens_pedido, usuario):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    doc_ref = f"OUT-REQ{req_id_visual:04d}-{datetime.now().strftime('%H%M')}"
    
    is_transferencia = "FILIAL" in str(destino).strip().upper()
    novo_status_ativo = 'Em Trânsito' if is_transferencia else 'Em Uso'
    tipo_movimentacao = 'Envio Transferência' if is_transferencia else 'Saída Operação'
    
    try:
        executar_query(f"UPDATE requisicoes SET status = 'Concluída' WHERE rowid = {int(true_rowid)}")
        try: executar_query(f"UPDATE requisicoes SET status = 'Concluída' WHERE id = {int(req_id_visual)}")
        except: pass
        
        for _, row in itens_pedido.iterrows():
            codigo = row['codigo']
            qtd_pedida = int(row['qtd'])
            
            if row['exige_tag']: 
                # =================================================================
                # MÁGICA DO HÍBRIDO AQUI: Lê o dicionário com a TAG e o MÉTODO
                # =================================================================
                tags_info = conferidos_tags.get(codigo, []) 
                for info in tags_info:
                    tag_str = info['tag'].upper()
                    metodo = info['metodo'] # 'Coletor' ou 'Manual'
                    
                    executar_query("UPDATE imobilizado SET status = ?, localizacao = ? WHERE upper(num_tag) = ?", (novo_status_ativo, destino, tag_str))
                    df_id = carregar_dados("SELECT id FROM imobilizado WHERE upper(num_tag) = ?", (tag_str,))
                    
                    if not df_id.empty: 
                        # CARIMBO DE AUDITORIA: Salva o método exato no documento!
                        detalhes = f"Ref: {doc_ref} [Via {metodo}]"
                        executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, ?, ?, ?, ?)", (int(df_id.iloc[0]['id']), tipo_movimentacao, usuario, destino, detalhes))
            
            else: # --- CONSUMO (Lotes) ---
                qtd_separada = conferidos_lotes.get(codigo, qtd_pedida) 
                df_lote = carregar_dados("SELECT id, quantidade FROM imobilizado WHERE codigo = ? AND localizacao = ? AND status = 'Disponível' AND (num_tag IS NULL OR trim(num_tag) = '') LIMIT 1", (codigo, polo))
                if not df_lote.empty and qtd_separada > 0:
                    id_lote = int(df_lote.iloc[0]['id'])
                    executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_separada, id_lote))
                    
                    if is_transferencia:
                        executar_query(f"""
                            INSERT INTO imobilizado (codigo, descricao, marca, modelo, num_tag, quantidade, status, localizacao, categoria, valor_unitario, tipo_material) 
                            SELECT codigo, descricao, marca, modelo, num_tag, {qtd_separada}, 'Em Trânsito', '{destino}', categoria, valor_unitario, tipo_material 
                            FROM imobilizado WHERE id = {id_lote}
                        """)
                    
                    executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, ?, ?, ?, ?)", (id_lote, tipo_movimentacao, usuario, destino, f"Ref: {doc_ref} Qtd: {qtd_separada}"))
        
        msg_sucesso = "Carga em Trânsito enviada!" if is_transferencia else "Pedido de Obra despachado!"
        return True, doc_ref, msg_sucesso
    except Exception as e: return False, "", f"Erro ao despachar: {str(e)}"

# Adicione no final do seu tracebox/controllers/outbound.py

def buscar_item_para_baixa(pesquisa, polo):
    """Busca o item no estoque para baixa, seja por TAG (Ativo) ou Código (Lote/Consumo)."""
    pesquisa_limpa = str(pesquisa).strip().upper()
    
    # 1. Tenta encontrar exatamente pela TAG
    df_tag = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, tipo_material FROM imobilizado WHERE upper(num_tag) = ? AND localizacao = ? AND status = 'Disponível'", (pesquisa_limpa, polo))
    if not df_tag.empty:
        return df_tag.iloc[0], 'ATIVO'

    # 2. Se não achar por TAG, tenta por CÓDIGO do Produto (Para Lotes)
    df_lote = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, tipo_material FROM imobilizado WHERE upper(codigo) = ? AND localizacao = ? AND status = 'Disponível' AND (num_tag IS NULL OR trim(num_tag) = '') LIMIT 1", (pesquisa_limpa, polo))
    if not df_lote.empty:
        return df_lote.iloc[0], 'LOTE'

    return None, None

def realizar_baixa_excepcional(carrinho, motivo, documento, usuario, polo):
    """Executa a baixa no banco de dados e gera o log de auditoria pesado."""
    try:
        from datetime import datetime
        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tipo_mov = f"Baixa Excepcional - {motivo}"
        doc_ref = f"{documento} | BXA-{datetime.now().strftime('%H%M%S')}"

        for item in carrinho:
            id_item = int(item['id'])
            
            if item['tipo'] == 'ATIVO':
                # Remove do estoque alterando o status
                executar_query("UPDATE imobilizado SET status = 'Baixado' WHERE id = ?", (id_item,))
                # Carimbo de Auditoria
                executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, ?, ?, ?, ?)", 
                               (id_item, tipo_mov, usuario, 'Ajuste/Sucata', doc_ref))
            else:
                # É Consumo/Lote: Deduz a quantidade
                qtd_baixar = int(item['qtd_baixar'])
                executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_baixar, id_item))
                # Carimbo de Auditoria detalhando a quantidade
                detalhes_lote = f"{doc_ref} | Qtd Baixada: {qtd_baixar}"
                executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, ?, ?, ?, ?)", 
                               (id_item, tipo_mov, usuario, 'Ajuste/Sucata', detalhes_lote))

        return True, "✅ Baixa Excepcional registada e auditada com sucesso!"
    except Exception as e:
        return False, f"Erro no banco de dados: {str(e)}"