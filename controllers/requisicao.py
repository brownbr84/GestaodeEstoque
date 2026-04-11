# tracebox/controllers/requisicao.py
import pandas as pd
from datetime import datetime
import time
from database.queries import executar_query, carregar_dados

def setup_tabelas_requisicao():
    executar_query("""
        CREATE TABLE IF NOT EXISTS requisicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitante TEXT,
            polo_origem TEXT,
            destino_projeto TEXT,
            status TEXT DEFAULT 'Pendente',
            data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            motivo_cancelamento TEXT,
            cancelado_por TEXT
        )
    """)
    executar_query("""
        CREATE TABLE IF NOT EXISTS requisicoes_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requisicao_id INTEGER,
            codigo_produto TEXT,
            descricao_produto TEXT,
            quantidade_solicitada INTEGER
        )
    """)

def obter_catalogo_disponivel(polo, carrinho, tipo_filtro):
    # O Anti-Cache Hack não é necessário aqui porque o estoque muda constantemente na memória
    query = """
        SELECT codigo, MAX(descricao) as descricao, SUM(quantidade) as saldo, MAX(tipo_material) as tipo
        FROM imobilizado
        WHERE localizacao = ? AND status = 'Disponível' AND upper(tipo_material) = ?
        GROUP BY codigo
    """
    df = carregar_dados(query, (polo, str(tipo_filtro).strip().upper()))
    
    if df.empty: return pd.DataFrame()
        
    df['saldo'] = pd.to_numeric(df['saldo'], errors='coerce').fillna(0).astype(int)
    
    for item in carrinho:
        idx = df.index[df['codigo'] == item.get('codigo', '')].tolist()
        if idx:
            i = idx[0]
            qtd_txt = str(item.get('quantidade', '0')).strip()
            qtd_carrinho = int(qtd_txt) if qtd_txt.isnumeric() else 0
            df.at[i, 'saldo'] -= qtd_carrinho
            
    df = df[df['saldo'] > 0].copy()
    if df.empty: return pd.DataFrame()
        
    df['label'] = df['codigo'].astype(str) + " - " + df['descricao'].astype(str) + " (Disp: " + df['saldo'].astype(str) + ")"
    df['saldo_real'] = df['saldo']
    return df

def salvar_nova_requisicao(polo_origem, destino, solicitante, itens):
    try:
        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. Cria a requisição
        executar_query(
            "INSERT INTO requisicoes (solicitante, polo_origem, destino_projeto, status, data_solicitacao) VALUES (?, ?, ?, 'Pendente', ?)",
            (solicitante, polo_origem, destino, agora)
        )
        
        # 2. A CURA DO REQ-001: Captura o ID exato usando a data e hora que acabamos de gerar
        df_id = carregar_dados("SELECT id FROM requisicoes WHERE solicitante = ? AND data_solicitacao = ? ORDER BY id DESC LIMIT 1", (solicitante, agora))
        
        if df_id.empty:
            df_id = carregar_dados("SELECT MAX(id) as id FROM requisicoes")
            
        id_txt = str(df_id.iloc[0]['id']).strip()
        novo_id = int(float(id_txt)) if id_txt and id_txt.lower() != 'none' else 1
        
        # 3. Insere os Itens vinculados ao ID CORRETO
        for item in itens:
            cod = item.get('codigo', item.get('CÓD', ''))
            desc = item.get('descricao', item.get('ITEM', ''))
            qtd_raw = item.get('quantidade', item.get('QTD', 1))
            
            qtd_txt = str(qtd_raw).strip()
            qtd_int = int(float(qtd_txt)) if qtd_txt and qtd_txt.lower() != 'none' else 1
            
            executar_query(
                "INSERT INTO requisicoes_itens (requisicao_id, codigo_produto, descricao_produto, quantidade_solicitada) VALUES (?, ?, ?, ?)",
                (novo_id, cod, desc, qtd_int)
            )
            
        return True, f"Requisição REQ-{novo_id:04d} gerada com sucesso!"
    except Exception as e:
        return False, f"Erro no banco de dados: {str(e)}"

def listar_historico_solicitante(solicitante):
    agora_ms = int(time.time() * 1000) # ANTI-CACHE HACK: Força o Streamlit a ler o banco sempre!
    query = f"""
        SELECT id, polo_origem, destino_projeto, status, data_solicitacao, 
               motivo_cancelamento, cancelado_por 
        FROM requisicoes 
        WHERE solicitante = ? AND {agora_ms} = {agora_ms} 
        ORDER BY data_solicitacao DESC
    """
    df = carregar_dados(query, (solicitante,))
    
    if df.empty: return pd.DataFrame()
    
    df['id_clean'] = df['id'].astype(str).str.replace(r'\D+', '', regex=True)
    df['id_clean'] = pd.to_numeric(df['id_clean'], errors='coerce').fillna(0).astype(int)
    
    return df

def listar_itens_da_requisicao(req_id):
    agora_ms = int(time.time() * 1000) # ANTI-CACHE HACK
    query = f"""
        SELECT codigo_produto as 'Código', descricao_produto as 'Descrição', quantidade_solicitada as 'Qtd' 
        FROM requisicoes_itens 
        WHERE requisicao_id = ? AND {agora_ms} = {agora_ms}
    """
    return carregar_dados(query, (int(req_id),))