# tracebox/views/matriz_fisica.py
import streamlit as st
import pandas as pd
from database.queries import carregar_dados
 
def tela_matriz_fisica():
    COLUNAS_FIXAS = ["CTG", "ITJ", "REC", "SAO", "Manutenção", "Transferência", "Operação"]
    
    st.markdown("<h2>📦 Consulta de <span style='color: #2563eb;'>Matriz Física</span></h2>", unsafe_allow_html=True)
    st.caption("Visão consolidada de saldos em tempo real. Utilize o leitor QR Code ou clique num item para abrir a Ficha Técnica.")
    
    # ==========================================
    # 1. CABEÇALHO DE BUSCA DUPLA (Scanner + Manual)
    # ==========================================
    col_scan, col_busca = st.columns(2)
    
    with col_scan:
        codigo_bipado = st.text_input(
            "📷 Scanner de QR Code", 
            placeholder="Bipe a etiqueta ou digite o código..."
        )
        
    if codigo_bipado:
        codigo_alvo = codigo_bipado.strip()
        
        # Descasca a string se for o nosso QR Code oficial
        if "COD:" in codigo_bipado:
            try:
                for p in codigo_bipado.split("|"):
                    if p.startswith("COD:"):
                        codigo_alvo = p.replace("COD:", "").strip()
                        break
            except:
                pass 
        
        df_check = carregar_dados("SELECT codigo FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo_alvo,))
        if not df_check.empty:
            st.success(f"✅ **{codigo_alvo}** localizado! Abrindo ficha...")
            st.session_state['produto_selecionado'] = codigo_alvo
            import time
            time.sleep(0.6)
            st.rerun()
        else:
            st.error(f"❌ Código '{codigo_alvo}' não encontrado.")

    # ==========================================
    # 2. MOTOR DA MATRIZ (Lógica Original Restaurada)
    # ==========================================
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
 
    with col_busca:
        # A sua Busca Rápida original, colocada estrategicamente ao lado do Scanner
        opcoes_busca = df_pivot.apply(lambda r: f"{r['codigo']} | {r['descricao']}", axis=1).tolist()
        busca = st.selectbox("🔍 Pesquisa Manual", [None] + opcoes_busca)
        
        if busca:
            st.session_state['produto_selecionado'] = busca.split(" | ")[0]
            st.rerun()
 
    st.write("---")

    # ==========================================
    # 3. TABELA INTERATIVA LIMPA
    # ==========================================
    selecao = st.dataframe(
        df_pivot.rename(columns={'codigo': 'Cód.', 'descricao': 'Descrição'}), 
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
    )
    
    if len(selecao.selection.rows) > 0:
        index_selecionado = selecao.selection.rows[0]
        codigo_clicado = df_pivot.iloc[index_selecionado]['codigo']
        st.session_state['produto_selecionado'] = codigo_clicado
        st.rerun()