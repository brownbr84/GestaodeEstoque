# tracebox/controllers/torre.py
import pandas as pd
from database.queries import carregar_dados

def carregar_dados_mestre():
    """Busca a base completa e prepara os cálculos financeiros brutos."""
    query_base = """
        SELECT codigo, descricao, status, localizacao, quantidade, categoria, valor_unitario, alerta_falta 
        FROM imobilizado
    """
    df_raw = carregar_dados(query_base)
    if not df_raw.empty:
        df_raw['valor_unitario'] = df_raw['valor_unitario'].fillna(0)
        df_raw['Valor_Total_Estoque'] = df_raw['quantidade'] * df_raw['valor_unitario']
    return df_raw

def calcular_kpis_principais(df_raw):
    """Calcula os indicadores vitais (SAP/TOTVS style)."""
    if df_raw.empty:
        return 0, 0, 0, 0, 1.2
        
    total_capital = df_raw['Valor_Total_Estoque'].sum()
    total_unidades = df_raw['quantidade'].sum()
    
    ativos_totais = df_raw[df_raw['status'] != 'Sucateado']['quantidade'].sum()
    ativos_em_uso = df_raw[df_raw['status'] == 'Em Uso']['quantidade'].sum()
    taxa_utilizacao = (ativos_em_uso / ativos_totais * 100) if ativos_totais > 0 else 0
    
    itens_com_falta = df_raw[df_raw['alerta_falta'] == 1]['quantidade'].sum()
    fill_rate = 100 - ((itens_com_falta / total_unidades * 100) if total_unidades > 0 else 0)
    
    giro_estoque = 1.2 # Fixo conforme regra de negócio original
    
    return total_capital, total_unidades, taxa_utilizacao, fill_rate, giro_estoque

def processar_curva_abc(df_raw, total_capital):
    """Gera o dataframe classificado com a Curva de Pareto."""
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
    """Calcula filas WMS e dados de Manutenção."""
    if df_raw.empty: return 0, 0, 0, 0
    
    transito = df_raw[df_raw['status'] == 'Em Trânsito']['quantidade'].sum()
    manutencao = df_raw[df_raw['status'] == 'Manutenção']['quantidade'].sum()
    
    try:
        saidas_pend = carregar_dados("SELECT count(*) as total FROM movimentacoes WHERE tipo = 'Saída' AND data_movimentacao >= date('now', '-1 day')").iloc[0]['total']
    except: saidas_pend = 0
    
    mttr_real = 0
    try:
        df_oficina = carregar_dados("SELECT data_entrada, data_saida FROM manutencao_ordens WHERE status_ordem = 'Concluída'")
        if not df_oficina.empty:
            df_oficina['entrada'] = pd.to_datetime(df_oficina['data_entrada'])
            df_oficina['saida'] = pd.to_datetime(df_oficina['data_saida'])
            mttr_real = (df_oficina['saida'] - df_oficina['entrada']).dt.days.mean()
    except: pass
    
    return transito, manutencao, saidas_pend, mttr_real

def obter_log_auditoria():
    """Busca as últimas 50 movimentações."""
    query = """
        SELECT m.data_movimentacao as Data, m.tipo as Operação, i.codigo as Código, 
               m.responsavel as Usuário, m.destino_projeto as Rastreabilidade, m.documento as Detalhes
        FROM movimentacoes m 
        LEFT JOIN imobilizado i ON m.ferramenta_id = i.id 
        ORDER BY m.data_movimentacao DESC LIMIT 50
    """
    return carregar_dados(query)