# tracebox/controllers/requisicao.py
import pandas as pd
import time
from database.queries import carregar_dados
from database.conexao_orm import SessionLocal
from services.requisicao_service import RequisicaoService

def obter_catalogo_disponivel(polo, carrinho, tipo_filtro):
    # O motor de busca em memória continua igual, pois é super rápido
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
    # Agora acionamos a transação blindada
    with SessionLocal() as session:
        return RequisicaoService.salvar_nova_requisicao(session, polo_origem, destino, solicitante, itens)

def listar_historico_solicitante(solicitante):
    agora_ms = int(time.time() * 1000)
    query = f"""
        SELECT id, polo_origem, destino_projeto, status, data_solicitacao,
               motivo_cancelamento, cancelado_por,
               email_status, email_enviado_em, email_erro
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
    agora_ms = int(time.time() * 1000)
    query = f"""
        SELECT codigo_produto as "Código", descricao_produto as "Descrição", quantidade_solicitada as "Qtd" 
        FROM requisicoes_itens 
        WHERE requisicao_id = ? AND {agora_ms} = {agora_ms}
    """
    return carregar_dados(query, (int(req_id),))