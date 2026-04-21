import pandas as pd
import time
from datetime import datetime
from database.queries import executar_query, carregar_dados

# 👉 NOVAS IMPORTAÇÕES DA ARQUITETURA
from database.conexao_orm import SessionLocal
from services.outbound_service import OutboundService

def setup_tabelas_outbound():
    pass

def carregar_fila_pedidos(polo):
    agora_ms = int(time.time() * 1000)
    query = "SELECT id as true_rowid, * FROM requisicoes"
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
    return df[df['polo_origem_clean'] == polo_upper].copy()

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

def buscar_item_para_baixa(pesquisa, polo):
    pesquisa_limpa = str(pesquisa).strip().upper()
    df_tag = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, tipo_material FROM imobilizado WHERE upper(num_tag) = ? AND localizacao = ? AND status = 'Disponível'", (pesquisa_limpa, polo))
    if not df_tag.empty:
        return df_tag.iloc[0], 'ATIVO'

    df_lote = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, tipo_material FROM imobilizado WHERE upper(codigo) = ? AND localizacao = ? AND status = 'Disponível' AND (num_tag IS NULL OR trim(num_tag) = '') LIMIT 1", (pesquisa_limpa, polo))
    if not df_lote.empty:
        return df_lote.iloc[0], 'LOTE'
    return None, None

# =====================================================================
# FUNÇÕES BLINDADAS COM SERVIÇO (ACID)
# =====================================================================

def cancelar_pedido(true_rowid, req_id_visual, motivo, usuario):
    # Usa o id_visual pois é ele que mapeamos no model Requisicao
    with SessionLocal() as session:
        return OutboundService.cancelar_pedido(session, int(req_id_visual), motivo, usuario)

def despachar_pedido_wms(true_rowid, req_id_visual, polo, destino, conferidos_tags, conferidos_lotes, itens_pedido, usuario):
    with SessionLocal() as session:
        return OutboundService.despachar_pedido_wms(
            session, int(req_id_visual), polo, destino, conferidos_tags, conferidos_lotes, itens_pedido, usuario
        )

def realizar_baixa_excepcional(carrinho, motivo, documento, usuario, polo, perfil_usuario="Operador"):
    with SessionLocal() as session:
        return OutboundService.realizar_baixa_excepcional(session, carrinho, motivo, documento, usuario, polo, perfil_usuario)