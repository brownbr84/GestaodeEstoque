import pandas as pd
from datetime import datetime
from database.queries import executar_query, carregar_dados

# 👉 NOVAS IMPORTAÇÕES DA ARQUITETURA
from database.conexao_orm import SessionLocal
from services.outbound_service import OutboundService

def setup_tabelas_outbound():
    pass

def carregar_fila_pedidos(polo):
    from database.models import Requisicao
    polo_upper = str(polo).strip().upper()

    with SessionLocal() as session:
        reqs = session.query(Requisicao).all()
        rows = []
        for req in reqs:
            polo_orig = str(req.polo_origem or '').strip()
            status    = str(req.status or '').strip()
            rows.append({
                'true_rowid':         req.id,
                'id':                 req.id,
                'id_num':             req.id,
                'solicitante':        req.solicitante or '',
                'polo_origem':        polo_orig,
                'polo_origem_clean':  polo_orig.upper(),
                'destino_projeto':    req.destino_projeto or '',
                'status':             status,
                'status_clean':       status.upper(),
                'data_solicitacao':   str(req.data_solicitacao or ''),
                'motivo_cancelamento': req.motivo_cancelamento or '',
                'cancelado_por':      req.cancelado_por or '',
                'email_status':       req.email_status or '',
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
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