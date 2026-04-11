# tracebox/views/matriz_fisica.py
import streamlit as st
import pandas as pd
from database.queries import carregar_dados

def tela_matriz_fisica():
    COLUNAS_FIXAS = ["CTG", "ITJ", "REC", "SAO", "Manutenção", "Transferência", "Operação"]
    
    st.markdown("<h2>📦 Consulta de <span style='color: #2563eb;'>Matriz Física</span></h2>", unsafe_allow_html=True)
    st.caption("Visão consolidada de saldos em tempo real. Clique num item para abrir a Ficha Técnica.")
    
    df_raw = carregar_dados("SELECT codigo, descricao, status, localizacao, quantidade FROM imobilizado")
    
    if df_raw.empty:
        st.info("Nenhum dado encontrado para gerar a matriz.")
        return

    def mapear_coluna_logistica(row):
        loc = str(row['localizacao']).upper()
        status = str(row['status'])
        if status == "Manutenção" or loc == "MANUTENÇÃO": return "Manutenção"
        if status == "Em Trânsito": return "Transferência"
        if status == "Em Uso": return "Operação"
        if "CTG" in loc: return "CTG"
        if "ITJ" in loc: return "ITJ"
        if "REC" in loc: return "REC"
        if "SAO" in loc: return "SAO"
        if "SÃO" in loc: return "SAO"
        return "Outros"

    df_raw['Eixo_Logistico'] = df_raw.apply(mapear_coluna_logistica, axis=1)

    df_pivot = df_raw.pivot_table(
        index=['codigo', 'descricao'], columns='Eixo_Logistico', values='quantidade', aggfunc='sum', fill_value=0
    ).reset_index()

    for col in COLUNAS_FIXAS:
        if col not in df_pivot.columns: df_pivot[col] = 0

    colunas_finais = ['codigo', 'descricao'] + COLUNAS_FIXAS
    df_pivot = df_pivot[colunas_finais]
    df_pivot['Saldo Total'] = df_pivot[COLUNAS_FIXAS].sum(axis=1)

    # Busca rápida
    opcoes_busca = df_pivot.apply(lambda r: f"{r['codigo']} | {r['descricao']}", axis=1).tolist()
    busca = st.selectbox("🔍 Pesquisar Produto Direto", [None] + opcoes_busca, label_visibility="collapsed", key="busca_matriz_unica")
    
    if busca:
        st.session_state['produto_selecionado'] = busca.split(" | ")[0]
        st.rerun()

    # Tabela Interativa Limpa
    selecao = st.dataframe(
        df_pivot.rename(columns={'codigo': 'Cód.', 'descricao': 'Descrição'}), 
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
    )
    
    if len(selecao.selection.rows) > 0:
        index_selecionado = selecao.selection.rows[0]
        codigo_clicado = df_pivot.iloc[index_selecionado]['codigo']
        st.session_state['produto_selecionado'] = codigo_clicado
        st.rerun()