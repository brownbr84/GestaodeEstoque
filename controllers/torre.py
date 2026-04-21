# tracebox/controllers/torre.py
import pandas as pd
from database.conexao_orm import engine

def carregar_dados_mestre():
    """Busca a base completa usando o motor otimizado do Pandas via ORM."""
    query_base = """
        SELECT codigo, descricao, status, localizacao, quantidade, categoria, valor_unitario, alerta_falta 
        FROM imobilizado
    """
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text(query_base)).mappings().all()
            df_raw = pd.DataFrame([dict(row) for row in result])
        if not df_raw.empty:
            df_raw['valor_unitario'] = pd.to_numeric(df_raw['valor_unitario'], errors='coerce').fillna(0)
            df_raw['quantidade'] = pd.to_numeric(df_raw['quantidade'], errors='coerce').fillna(0)
            df_raw['Valor_Total_Estoque'] = df_raw['quantidade'] * df_raw['valor_unitario']
        return df_raw
    except Exception as e:
        print(f"Erro ao carregar mestre: {e}")
        return pd.DataFrame()

def calcular_kpis_principais(df_raw):
    """Calcula os indicadores vitais (SAP/TOTVS style)."""
    if df_raw.empty:
        return 0, 0, 0, 0, 0, 0, 1.2
        
    total_capital = df_raw['Valor_Total_Estoque'].sum()
    total_unidades = df_raw['quantidade'].sum()
    
    ativos_totais = df_raw[~df_raw['status'].isin(['Sucateado', 'Baixado', 'Extraviado'])]['quantidade'].sum()
    ativos_em_uso = df_raw[df_raw['status'] == 'Em Uso']['quantidade'].sum()
    taxa_utilizacao = (ativos_em_uso / ativos_totais * 100) if ativos_totais > 0 else 0
    
    itens_com_falta = df_raw[df_raw['alerta_falta'] == True]['quantidade'].sum()

    fill_rate = 100 - ((itens_com_falta / total_unidades * 100) if total_unidades > 0 else 0)
    
    # 🚨 NOVO KPI: Índice de Extravio Financeiro
    capital_perdido = df_raw[df_raw['status'] == 'Extraviado']['Valor_Total_Estoque'].sum()
    taxa_perda = (capital_perdido / total_capital * 100) if total_capital > 0 else 0

    # 🚨 NOVO KPI: Capital Retido em Manutenção
    capital_oficina = df_raw[df_raw['status'] == 'Manutenção']['Valor_Total_Estoque'].sum()
    
    giro_estoque = 1.2 # Fixo conforme regra de negócio original
    
    return total_capital, total_unidades, taxa_utilizacao, fill_rate, taxa_perda, capital_oficina, giro_estoque

def processar_curva_abc(df_raw, total_capital):
    if df_raw.empty or total_capital <= 0:
        return pd.DataFrame()
        
    df_abc = df_raw.groupby(['codigo', 'descricao'])['Valor_Total_Estoque'].sum().reset_index()
    df_abc = df_abc.sort_values(by='Valor_Total_Estoque', ascending=False)
    
    df_abc['Soma_Acumulada'] = df_abc['Valor_Total_Estoque'].cumsum()
    df_abc['Perc_Acumulado'] = 100 * df_abc['Soma_Acumulada'] / total_capital
    
    def classificar_abc(p):
        if p <= 80: return 'A'
        elif p <= 95: return 'B'
        return 'C'
        
    df_abc['Classe'] = df_abc['Perc_Acumulado'].apply(classificar_abc)
    return df_abc

def obter_metricas_operacionais(df_raw):
    if df_raw.empty: return 0, 0, 0, 0, 0
    
    transito = df_raw[df_raw['status'] == 'Em Trânsito']['quantidade'].sum()
    manutencao = df_raw[df_raw['status'] == 'Manutenção']['quantidade'].sum()
    
    try:
        from datetime import datetime, timedelta
        import os
        db_type = os.getenv("DB_TYPE", "sqlite")
        ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        query_saidas = f"SELECT count(*) as total FROM requisicoes WHERE status = 'Concluída' AND data_solicitacao >= '{ontem}'"
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text(query_saidas)).mappings().all()
            df_saidas = pd.DataFrame([dict(row) for row in result])
        saidas_pend = df_saidas.iloc[0]['total'] if not df_saidas.empty else 0
    except: saidas_pend = 0
    
    mttr_real = 0
    custo_manut_mes = 0
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT data_entrada, data_saida, custo_reparo FROM manutencao_ordens WHERE status_ordem = 'Concluída'")).mappings().all()
            df_oficina = pd.DataFrame([dict(row) for row in result])
        if not df_oficina.empty:
            df_oficina['entrada'] = pd.to_datetime(df_oficina['data_entrada'])
            df_oficina['saida'] = pd.to_datetime(df_oficina['data_saida'])
            mttr_real = (df_oficina['saida'] - df_oficina['entrada']).dt.days.mean()
            
            # Custo do mês atual
            df_oficina_mes = df_oficina[df_oficina['saida'].dt.month == pd.Timestamp.now().month]
            custo_manut_mes = df_oficina_mes['custo_reparo'].sum()
    except: pass
    
    return transito, manutencao, saidas_pend, mttr_real, custo_manut_mes

def obter_log_auditoria():
    """Busca o feed global da NOVA tabela de Governança."""
    query = """
        SELECT data_hora as Data, usuario as Responsável, acao as Evento, detalhes as Detalhes
        FROM logs_auditoria 
        ORDER BY data_hora DESC LIMIT 100
    """
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text(query)).mappings().all()
            return pd.DataFrame([dict(row) for row in result])
    except:
        return pd.DataFrame()