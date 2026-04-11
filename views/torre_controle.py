# tracebox/views/torre_controle.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database.queries import carregar_dados

def tela_torre_controle():
    st.markdown("<h2>📈 Torre de Controle <span style='color: #2563eb;'>Estratégica</span></h2>", unsafe_allow_html=True)
    
    # 1. EXTRAÇÃO E PREPARAÇÃO DE DADOS MESTRE
    query_base = """
        SELECT codigo, descricao, status, localizacao, quantidade, categoria, valor_unitario, alerta_falta 
        FROM imobilizado
    """
    df_raw = carregar_dados(query_base)

    if df_raw.empty:
        st.info("Aguardando dados para processamento de indicadores.")
        return

    # Cálculos Base
    df_raw['valor_unitario'] = df_raw['valor_unitario'].fillna(0)
    df_raw['Valor_Total_Estoque'] = df_raw['quantidade'] * df_raw['valor_unitario']
    
    # KPIs Rápidos
    total_capital = df_raw['Valor_Total_Estoque'].sum()
    total_sku = df_raw['codigo'].nunique()
    total_unidades = df_raw['quantidade'].sum()
    
    # ---------------------------------------------------------
    # 2. PAINEL DE MÉTRICAS SAP/TOTVS (KPIs DE PERFORMANCE)
    # ---------------------------------------------------------
    st.write("### 🎯 Performance e Disponibilidade")
    
    # Cálculo de Taxa de Utilização (Ativos em campo vs Total)
    ativos_totais = df_raw[df_raw['status'] != 'Sucateado']['quantidade'].sum()
    ativos_em_uso = df_raw[df_raw['status'] == 'Em Uso']['quantidade'].sum()
    taxa_utilizacao = (ativos_em_uso / ativos_totais * 100) if ativos_totais > 0 else 0
    
    # Fill Rate (Acuracidade de Atendimento)
    itens_com_falta = df_raw[df_raw['alerta_falta'] == 1]['quantidade'].sum()
    fill_rate = 100 - ((itens_com_falta / total_unidades * 100) if total_unidades > 0 else 0)

    # Giro de Estoque (Turnover) - Estimado
    giro_estoque = 1.2 

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Taxa de Utilização", f"{taxa_utilizacao:.1f}%", help="Percentual da frota que está gerando receita em obras.")
    kpi2.metric("Fill Rate (Nível de Serviço)", f"{fill_rate:.1f}%", help="Capacidade de atender pedidos sem rupturas.")
    kpi3.metric("Giro de Estoque", f"{giro_estoque}x", help="Velocidade de renovação do ativo circulante.")
    kpi4.metric("Capital Imobilizado", f"R$ {total_capital:,.2f}")

    st.divider()

    # ---------------------------------------------------------
    # 3. ANÁLISE DE COMPOSIÇÃO (TREEMAP FINANCEIRO)
    # ---------------------------------------------------------
    st.write("### 💎 Composição do Capital (Treemap)")
    st.caption("O tamanho do bloco representa o valor financeiro investido. Clique nos blocos para explorar.")
    
    # --- CORREÇÃO DO ERRO DO PLOTLY AQUI ---
    # Criamos uma cópia limpa só para o Treemap
    df_tree = df_raw[df_raw['Valor_Total_Estoque'] > 0].copy()
    
    # Substitui campos vazios (None/NaN) por textos padrão para o Plotly não quebrar
    df_tree['categoria'] = df_tree['categoria'].fillna("Não Categorizado")
    df_tree['codigo'] = df_tree['codigo'].fillna("Sem Código")
    # ---------------------------------------

    if not df_tree.empty:
        fig_tree = px.treemap(
            df_tree, 
            path=[px.Constant("Patrimônio Total"), 'categoria', 'codigo'], 
            values='Valor_Total_Estoque',
            color='categoria',
            hover_data=['descricao'],
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_tree.update_traces(root_color="lightgrey")
        fig_tree.update_layout(margin=dict(t=10, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)
    else:
        st.info("Não há itens com valor financeiro cadastrado para desenhar o mapa de capital.")

    # ---------------------------------------------------------
    # 4. CURVA ABC (PARETO) - INTELIGÊNCIA DE ESTOQUE
    # ---------------------------------------------------------
    st.write("### 📊 Classificação ABC (Curva de Pareto)")
    st.caption("Identifique os 20% de itens que representam 80% do valor do seu estoque.")

    df_abc = df_raw.groupby(['codigo', 'descricao'])['Valor_Total_Estoque'].sum().reset_index()
    df_abc = df_abc.sort_values(by='Valor_Total_Estoque', ascending=False)
    
    if total_capital > 0:
        df_abc['Soma_Acumulada'] = df_abc['Valor_Total_Estoque'].cumsum()
        df_abc['Perc_Acumulado'] = 100 * df_abc['Soma_Acumulada'] / total_capital
        
        def classificar_abc(p):
            if p <= 80: return 'A'
            elif p <= 95: return 'B'
            return 'C'
        
        df_abc['Classe'] = df_abc['Perc_Acumulado'].apply(classificar_abc)

        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(x=df_abc['codigo'], y=df_abc['Valor_Total_Estoque'], name="Valor Individual", marker_color='#2563eb'))
        fig_pareto.add_trace(go.Scatter(x=df_abc['codigo'], y=df_abc['Perc_Acumulado'], name="% Acumulado", yaxis="y2", line=dict(color="#e11d48", width=3)))

        fig_pareto.update_layout(
            title="Curva de Valor Acumulado",
            yaxis=dict(title="Valor em R$"),
            yaxis2=dict(title="Percentagem %", overlaying="y", side="right", range=[0, 110]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, l=10, r=10, b=10)
        )
        st.plotly_chart(fig_pareto, use_container_width=True)
    else:
        st.info("Cadastre os valores (R$) dos produtos para visualizar a curva ABC.")

    # ---------------------------------------------------------
    # 5. FILA WMS E OPERACIONAL
    # ---------------------------------------------------------
    st.divider()
    col_wms, col_man = st.columns(2)
    
    with col_wms:
        st.write("### 📦 Fila WMS (Logística)")
        transito = df_raw[df_raw['status'] == 'Em Trânsito']['quantidade'].sum()
        
        try:
            saidas_pendentes = carregar_dados("SELECT count(*) as total FROM movimentacoes WHERE tipo = 'Saída' AND data_movimentacao >= date('now', '-1 day')").iloc[0]['total']
        except:
            saidas_pendentes = 0
            
        st.info(f"🚚 **Itens em Trânsito:** {int(transito)} unidades")
        st.warning(f"⏳ **Saídas nas últimas 24h:** {int(saidas_pendentes)} requisições")
        
    with col_man:
        st.write("### 🛠️ Manutenção & Reparo")
        manutencao = df_raw[df_raw['status'] == 'Manutenção']['quantidade'].sum()
        st.error(f"🔧 **Itens Retidos na Oficina:** {int(manutencao)} unidades")
        
        try:
            # Tenta buscar os dados reais de MTTR da tabela que acabamos de criar!
            df_oficina = carregar_dados("SELECT data_entrada, data_saida FROM manutencao_ordens WHERE status_ordem = 'Concluída'")
            if not df_oficina.empty:
                df_oficina['entrada'] = pd.to_datetime(df_oficina['data_entrada'])
                df_oficina['saida'] = pd.to_datetime(df_oficina['data_saida'])
                mttr_real = (df_oficina['saida'] - df_oficina['entrada']).dt.days.mean()
                st.caption(f"⏱️ **MTTR Médio (Real):** {mttr_real:.1f} dias")
            else:
                st.caption("⏱️ **MTTR Médio:** Sem histórico suficiente")
        except:
            st.caption("⏱️ **MTTR Médio:** Aguardando OS Concluídas")

    # ---------------------------------------------------------
    # 6. FEED GLOBAL (AUDITORIA)
    # ---------------------------------------------------------
    st.divider()
    st.subheader("📜 Log Global de Auditoria (Compliance)")
    try:
        query_log = """
            SELECT m.data_movimentacao as Data, m.tipo as Operação, i.codigo as Código, 
                   m.responsavel as Usuário, m.destino_projeto as Rastreabilidade, m.documento as Detalhes
            FROM movimentacoes m 
            LEFT JOIN imobilizado i ON m.ferramenta_id = i.id 
            ORDER BY m.data_movimentacao DESC LIMIT 50
        """
        df_log = carregar_dados(query_log)
        if not df_log.empty:
            st.dataframe(df_log, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma movimentação registrada.")
    except:
        st.warning("Aguardando novas movimentações para exibir o log.")