# tracebox/views/inventario.py
import pandas as pd
import streamlit as st
import time
from datetime import datetime
import streamlit.components.v1 as components
from database.queries import carregar_dados
from controllers.auditoria import processar_resultados_inventario, processar_cruzamento_wms

@st.cache_data
def gerar_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def tela_inventario_ciclico():
    st.title("📋 Inventário Cíclico (WMS Integrado)")
    st.caption("Auditoria rastreável com leitura de códigos e consolidação de lotes.")
    usuario_atual = st.session_state['usuario_logado']['nome']

    # 1. MEMÓRIA DA SESSÃO
    if 'inv_ativo' not in st.session_state:
        st.session_state['inv_ativo'] = False
        st.session_state['polo_alvo'] = ""
        st.session_state['inv_id'] = "" 
        st.session_state['df_esperado'] = pd.DataFrame()
        st.session_state['tags_bipadas'] = set() 
        st.session_state['lotes_contados'] = {}

    # 2. TELA INICIAL (PARAMETRIZAÇÃO)
    if not st.session_state['inv_ativo']:
        st.write("### ⚙️ Iniciar Nova Sessão de Auditoria")
        
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                polo = st.selectbox("📍 Polo / Almoxarifado Alvo", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"])
            with c2:
                # Nomes mais claros e alinhados com a operação
                classificacao = st.selectbox("🏷️ Escopo da Contagem", ["Inventário Total (Todos)", "Apenas Ativos (Máquinas com TAG)", "Apenas Consumo (Lotes/Insumos)"])

            if st.button("🚀 Gerar Lista e Iniciar Inventário", type="primary", use_container_width=True):
                query = "SELECT id, codigo, descricao, num_tag, quantidade, categoria FROM imobilizado WHERE localizacao = ? AND status IN ('Disponível', 'Manutenção')"
                
                # REGRA DE PROTEÇÃO: O filtro atua DIRETAMENTE no banco de dados.
                if classificacao == "Apenas Ativos (Máquinas com TAG)":
                    query += " AND num_tag IS NOT NULL AND trim(num_tag) != ''"
                elif classificacao == "Apenas Consumo (Lotes/Insumos)":
                    query += " AND (num_tag IS NULL OR trim(num_tag) = '')"
                
                df_esperado = carregar_dados(query, (polo,))
                
                if df_esperado.empty:
                    st.warning("Nenhum item esperado para este filtro. O estoque consta como zerado.")
                else:
                    st.session_state['inv_ativo'] = True
                    st.session_state['polo_alvo'] = polo
                    st.session_state['inv_id'] = f"INV-{datetime.now().strftime('%Y%m%d-%H%M')}"
                    st.session_state['df_esperado'] = df_esperado
                    st.session_state['tags_bipadas'] = set()
                    st.session_state['lotes_contados'] = {}
                    st.rerun()
                    
    # 3. MODO DE EXECUÇÃO
    else:
        st.success(f"📌 **Sessão Ativa: {st.session_state['inv_id']}** | Polo: {st.session_state['polo_alvo']}")
        df_esp = st.session_state['df_esperado']
        
        df_tags = df_esp[df_esp['num_tag'].notna() & (df_esp['num_tag'] != '')]
        df_lotes = df_esp[~(df_esp['num_tag'].notna() & (df_esp['num_tag'] != ''))]
        
        if not df_lotes.empty:
            df_lotes_agg = df_lotes.groupby(['codigo', 'descricao']).agg({'quantidade': 'sum', 'id': lambda x: list(x)}).reset_index()
        else:
            df_lotes_agg = pd.DataFrame()

        # O NOVO MÓDULO DE IMPRESSÃO (CSS BLINDADO + ASSINATURAS)
        with st.expander("🖨️ Imprimir / Exportar Folha de Contagem Cega"):
            df_print = df_esp[['codigo', 'descricao', 'num_tag']].copy()
            df_print['num_tag'] = df_print['num_tag'].fillna("LOTE")
            df_print['CONTAGEM FÍSICA'] = "" 
            df_print = df_print.rename(columns={'codigo': 'CÓD', 'descricao': 'DESCRIÇÃO', 'num_tag': 'TAG'})
            
            csv = gerar_csv(df_print)
            st.download_button(label="📥 Baixar Planilha (.csv Excel)", data=csv, file_name=f"{st.session_state['inv_id']}_Folha.csv", mime='text/csv')
            
            st.write("---")
            
            html_table = df_print.to_html(index=False)
            html_print_view = f"""
            <html>
            <head>
            <style>
                body {{ font-family: sans-serif; color: black !important; background-color: white !important; padding: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; color: black !important; }}
                th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
                th {{ background-color: #e2e8f0; font-weight: bold; }}
                .cabecalho {{ border: 2px solid #000; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                .linha-assinatura {{ display: flex; justify-content: space-between; margin-top: 20px; }}
                @media print {{
                    #btn-imprimir {{ display: none; }}
                    body {{ padding: 0; }}
                }}
            </style>
            </head>
            <body>
                <button id="btn-imprimir" onclick="window.print()" style="padding: 10px 15px; margin-bottom: 15px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
                    🖨️ Imprimir Folha de Auditoria
                </button>
                
                <div class="cabecalho">
                    <h2 style="margin: 0 0 10px 0;">Folha de Contagem: {st.session_state['inv_id']}</h2>
                    <p style="margin: 5px 0;"><strong>📍 Polo / Local:</strong> {st.session_state['polo_alvo']}</p>
                    <div class="linha-assinatura">
                        <span><strong>Auditor(a):</strong> _________________________________________</span>
                        <span><strong>Data:</strong> ____/____/20____</span>
                    </div>
                    <p style="margin: 20px 0 5px 0;"><strong>Assinatura:</strong> _________________________________________</p>
                </div>
                
                {html_table}
            </body>
            </html>
            """
            components.html(html_print_view, height=500, scrolling=True)

        st.write("---")
        
        # -------------------------------------------------------------
        # O TRUQUE DE UX: ABAS DINÂMICAS (MATA O ERRO "FANTASMA")
        # -------------------------------------------------------------
        guias = []
        if not df_tags.empty: guias.append("🔫 Bipar TAGs (Ativos)")
        if not df_lotes_agg.empty: guias.append("📦 Contar Lotes (Consumo)")
        guias.append("✅ Revisão e Fechamento")
        
        tabs = st.tabs(guias)
        idx = 0

        # ABA 1: SÓ APARECE SE HOUVER ATIVOS PARA BIPAR
        if not df_tags.empty:
            with tabs[idx]:
                st.subheader("Leitura de Ativos (Rastreáveis)")
                with st.form("form_leitor", clear_on_submit=True):
                    tag_lida = st.text_input("Bipe o Código de Barras / TAG aqui:", key="leitor_wms")
                    btn_bipar = st.form_submit_button("Registrar (Ou aperte Enter)", use_container_width=True)
                    
                    if btn_bipar and tag_lida:
                        # Força maiúsculo e remove espaços nas pontas
                        tag_limpa = str(tag_lida).strip().upper()
                        mapa_tags = {str(t).strip().upper(): str(t) for t in df_tags['num_tag'].values if pd.notna(t)}
                        
                        if tag_limpa in mapa_tags:
                            tag_real = mapa_tags[tag_limpa]
                            st.session_state['tags_bipadas'].add(tag_real)
                            st.success(f"✅ TAG {tag_real} registrada!")
                        else: 
                            st.error(f"🚨 A TAG {tag_limpa} NÃO pertence a esta lista!")
                
                total_tags = len(df_tags)
                tags_lidas = len(st.session_state['tags_bipadas'])
                if total_tags > 0:
                    st.progress(tags_lidas / total_tags, text=f"Progresso: {tags_lidas} de {total_tags} ativos encontrados.")
                    tags_faltantes = set(df_tags['num_tag'].tolist()) - st.session_state['tags_bipadas']
                    with st.expander(f"👀 Ver ativos ainda não encontrados ({len(tags_faltantes)})"):
                        st.dataframe(df_tags[df_tags['num_tag'].isin(tags_faltantes)][['codigo', 'descricao', 'num_tag']], hide_index=True)
            idx += 1

        # ABA 2: SÓ APARECE SE HOUVER LOTES PARA CONTAR
        if not df_lotes_agg.empty:
            with tabs[idx]:
                st.subheader("Digitação de Materiais em Lote")
                for _, row in df_lotes_agg.iterrows():
                    c1, c2 = st.columns([3, 1])
                    with c1: st.write(f"**{row['codigo']}** - {row['descricao']}")
                    with c2: 
                        qtd_f = st.number_input("Qtd", min_value=0, value=int(row['quantidade']), key=f"lote_{row['codigo']}")
                        st.session_state['lotes_contados'][row['codigo']] = qtd_f
            idx += 1

        # ABA FINAL
        with tabs[idx]:
            st.subheader("Resumo de Divergências")
            resultados_finais, divergencias = processar_cruzamento_wms(
                st.session_state['polo_alvo'], st.session_state['tags_bipadas'], st.session_state['lotes_contados']
            )

            if divergencias > 0: st.error(f"⚠️ Atenção: Detectadas {divergencias} divergências. Ajustes automáticos serão aplicados.")
            else: st.success("✅ Inventário 100% exato.")

            if st.button("💾 Finalizar Inventário e Salvar Protocolo", type="primary", use_container_width=True):
                erros = processar_resultados_inventario(resultados_finais, usuario_atual, st.session_state['polo_alvo'], st.session_state['inv_id'])
                if erros:
                    for e in erros: st.error(e)
                else:
                    st.success(f"✅ Protocolo {st.session_state['inv_id']} processado! Movimentações registradas.")
                    del st.session_state['inv_ativo']
                    time.sleep(2)
                    st.rerun()

        st.divider()
        if st.button("❌ Cancelar Sessão Atual e Sair", type="secondary"):
            del st.session_state['inv_ativo']
            st.rerun()