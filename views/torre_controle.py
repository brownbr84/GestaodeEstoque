# tracebox/views/torre_controle.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from controllers.torre import (
    carregar_dados_mestre, calcular_kpis_principais, processar_curva_abc, 
    obter_metricas_operacionais, obter_log_auditoria
)

def tela_torre_controle():
    st.markdown("<h2>📈 Torre de Controle <span style='color: #2563eb;'>Estratégica</span></h2>", unsafe_allow_html=True)
    
    # 1. Busca Cérebro
    df_raw = carregar_dados_mestre()
    if df_raw.empty:
        st.info("Aguardando dados para processamento de indicadores.")
        return

    total_capital, total_unidades, taxa_utilizacao, fill_rate, giro_estoque = calcular_kpis_principais(df_raw)
    
    # ---------------------------------------------------------
    # 2. PAINEL DE MÉTRICAS SAP/TOTVS 
    # ---------------------------------------------------------
    st.write("### 🎯 Performance e Disponibilidade")
    
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
    
    df_tree = df_raw[df_raw['Valor_Total_Estoque'] > 0].copy()
    df_tree['categoria'] = df_tree['categoria'].fillna("Não Categorizado")
    df_tree['codigo'] = df_tree['codigo'].fillna("Sem Código")

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
    # 4. CURVA ABC (PARETO) 
    # ---------------------------------------------------------
    st.write("### 📊 Classificação ABC (Curva de Pareto)")
    st.caption("Identifique os 20% de itens que representam 80% do valor do seu estoque.")

    df_abc = processar_curva_abc(df_raw, total_capital)
    
    if not df_abc.empty:
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
    transito, manutencao, saidas_pendentes, mttr_real = obter_metricas_operacionais(df_raw)
    
    with col_wms:
        st.write("### 📦 Fila WMS (Logística)")
        st.info(f"🚚 **Itens em Trânsito:** {int(transito)} unidades")
        st.warning(f"⏳ **Saídas nas últimas 24h:** {int(saidas_pendentes)} requisições")
        
    with col_man:
        st.write("### 🛠️ Manutenção & Reparo")
        st.error(f"🔧 **Itens Retidos na Oficina:** {int(manutencao)} unidades")
        if mttr_real > 0:
            st.caption(f"⏱️ **MTTR Médio (Real):** {mttr_real:.1f} dias")
        else:
            st.caption("⏱️ **MTTR Médio:** Aguardando histórico")

    # ---------------------------------------------------------
    # 6. FEED GLOBAL (AUDITORIA)
    # ---------------------------------------------------------
    st.divider()
    st.subheader("📜 Log Global de Auditoria (Compliance)")
    df_log = obter_log_auditoria()
    
    if not df_log.empty:
        st.dataframe(df_log, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma movimentação registrada até o momento.")