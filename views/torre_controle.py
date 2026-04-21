# tracebox/views/torre_controle.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from client.api_client import TraceBoxClient

def tela_torre_controle():
    st.markdown("<h2>📈 Torre de Controle <span style='color: #2563eb;'>Estratégica</span></h2>", unsafe_allow_html=True)
    
    dados = TraceBoxClient.get_dashboard_metrics()
    if not dados or dados.get("status") == "vazio":
        st.info("Aguardando dados ou API offline.")
        return

    kpis = dados.get("kpis", {})
    total_capital = kpis.get("total_capital", 0)
    taxa_utilizacao = kpis.get("taxa_utilizacao", 0)
    fill_rate = kpis.get("fill_rate", 0)
    taxa_perda = kpis.get("taxa_perda", 0)
    capital_oficina = kpis.get("capital_oficina", 0)
    
    # ---------------------------------------------------------
    # 2. PAINEL DE MÉTRICAS SAP/TOTVS (Com novos KPIs)
    # ---------------------------------------------------------
    st.write("### 🎯 Performance e Disponibilidade")
    
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Capital Imobilizado", f"R$ {total_capital/1000:,.1f}K", help=f"Valor exato: R$ {total_capital:,.2f}")
    k2.metric("Taxa de Utilização", f"{taxa_utilizacao:.1f}%", help="Percentual da frota gerando receita em obras.")
    k3.metric("Fill Rate", f"{fill_rate:.1f}%", help="Capacidade de atender pedidos sem rupturas.")
    
    cor_perda = "normal" if taxa_perda < 5 else "inverse"
    k4.metric("Índice de Extravio", f"{taxa_perda:.1f}%", delta="- Risco" if taxa_perda > 5 else "Controlado", delta_color=cor_perda, help="Percentual financeiro de itens perdidos/extraviados.")
    
    k5.metric("Capital em Reparo", f"R$ {capital_oficina/1000:,.1f}K", help="Capital indisponível por estar na oficina.")

    st.divider()

    # ---------------------------------------------------------
    # 3. ANÁLISE DE COMPOSIÇÃO E CURVA ABC (LADO A LADO)
    # ---------------------------------------------------------
    c_graf1, c_graf2 = st.columns(2)
    
    with c_graf1:
        st.write("### 💎 Composição do Capital")
        comp = dados.get("composicao_capital", [])
        if comp:
            df_tree = pd.DataFrame(comp)
            fig_tree = px.treemap(
                df_tree, path=[px.Constant("Patrimônio"), 'categoria'], 
                values='Valor_Total_Estoque', color='categoria',
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_tree.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=350)
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.info("Sem valores cadastrados.")

    with c_graf2:
        st.write("### 📊 Curva ABC (Pareto)")
        abc = dados.get("curva_abc_top10", [])
        if abc:
            df_abc_top = pd.DataFrame(abc)
            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(x=df_abc_top['codigo'], y=df_abc_top['Valor_Total_Estoque'], name="Valor (Top 10)", marker_color='#2563eb'))
            fig_pareto.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=350, yaxis=dict(title="Valor R$"))
            st.plotly_chart(fig_pareto, use_container_width=True)
        else:
            st.info("Sem valores cadastrados.")

    # ---------------------------------------------------------
    # 5. FILA WMS E OPERACIONAL (Com Custos de Oficina)
    # ---------------------------------------------------------
    st.divider()
    col_wms, col_man = st.columns(2)
    operacional = dados.get("operacional", {})
    transito = operacional.get("transito", 0)
    manutencao = operacional.get("manutencao", 0)
    saidas_pendentes = operacional.get("saidas_pendentes", 0)
    mttr_real = operacional.get("mttr_real", 0)
    custo_manut_mes = operacional.get("custo_manut_mes", 0)
    
    with col_wms:
        st.write("### 📦 Fila WMS (Logística)")
        st.info(f"🚚 **Itens em Trânsito:** {int(transito)} unidades")
        st.success(f"✅ **Requisições Despachadas (24h):** {int(saidas_pendentes)}")
        
    with col_man:
        st.write("### 🛠️ Inteligência de Manutenção")
        st.error(f"🔧 **Itens na Oficina:** {int(manutencao)} unidades")
        st.caption(f"⏱️ **MTTR Médio (Tempo de Reparo):** {mttr_real:.1f} dias" if mttr_real > 0 else "⏱️ Aguardando histórico")
        st.caption(f"💸 **Custo Acumulado de Reparos (Mês):** R$ {custo_manut_mes:,.2f}")

    # ---------------------------------------------------------
    # 6. FEED GLOBAL (COMPLIANCE OFICIAL)
    # ---------------------------------------------------------
    st.divider()
    st.subheader("📜 Feed Oficial de Auditoria (Live Compliance)")
    logs = dados.get("logs", [])
    
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum evento de auditoria registrado no sistema.")