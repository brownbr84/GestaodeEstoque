# tracebox/views/etiquetas.py
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from client.api_client import TraceBoxClient
from controllers.etiquetas import formatar_etiqueta_html

def tela_gerador_etiquetas():
    st.markdown("<h2>🏷️ Gerador de Etiquetas <span style='color: #2563eb;'>QR Code</span></h2>", unsafe_allow_html=True)
    st.caption("Filtre por produto e gere etiquetas sob medida para Ativos ou Consumíveis.")

    # ==========================================
    # 1. FILTRO DE TIPO (Ativo vs Consumo)
    # ==========================================
    tipo_selecionado = st.radio("Selecione a Categoria:", ["Ativo", "Consumo"], horizontal=True)

    # ==========================================
    # 2. FILTRO DE PRODUTO
    # ==========================================
    # Busca apenas os produtos que têm saldo físico em estoque para não poluir a lista
    df_produtos = pd.DataFrame(TraceBoxClient.etiquetas_produtos(tipo_selecionado))

    if df_produtos.empty:
        st.warning(f"Nenhum produto do tipo '{tipo_selecionado}' encontrado no estoque no momento.")
        return

    lista_produtos = df_produtos.apply(lambda r: f"{r['codigo']} - {r['descricao']}", axis=1).tolist()
    produto_selecionado = st.selectbox("📦 Pesquise e Selecione o Produto Base:", [""] + lista_produtos)

    # ==========================================
    # 3. MOTOR DE IMPRESSÃO INTELIGENTE
    # ==========================================
    if produto_selecionado:
        codigo_puro = produto_selecionado.split(" - ")[0].strip()

        # Busca o inventário físico exato desse código
        df_inventario = pd.DataFrame(TraceBoxClient.etiquetas_inventario(codigo_puro))

        st.divider()
        st.write("### Seleção de Unidades/Lotes para Impressão")

        # Separa o que é rastreado (TAG) do que é Volume (Lote/Consumível)
        df_com_tag = df_inventario[df_inventario['num_tag'].notna() & (df_inventario['num_tag'] != '')]
        df_sem_tag = df_inventario[df_inventario['num_tag'].isna() | (df_inventario['num_tag'] == '')]

        etiquetas_para_imprimir = []

        # --- CENÁRIO A: ITENS COM TAG ---
        if not df_com_tag.empty:
            st.markdown("#### 🏷️ Itens Rastreados (Individuais)")
            st.caption("Selecione as TAGs específicas que deseja imprimir:")
            
            # Tabela interativa para seleção de linhas
            selecao_tags = st.dataframe(
                df_com_tag[['num_tag', 'localizacao', 'quantidade']],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="sel_tags"
            )
            
            linhas_tags = selecao_tags.selection.rows
            for r in linhas_tags:
                item_real = df_com_tag.iloc[r]
                etiquetas_para_imprimir.append({
                    'id': item_real['id'],
                    'codigo': codigo_puro,
                    'descricao': item_real['descricao'],
                    'num_tag': item_real['num_tag'],
                    'localizacao': item_real['localizacao'],
                    'qtd_imprimir': 1  # 1 TAG = 1 Etiqueta
                })

        # --- CENÁRIO B: LOTES E CONSUMÍVEIS (SEM TAG) ---
        if not df_sem_tag.empty:
            st.markdown("#### 📦 Lotes Consolidados (Sem TAG)")
            st.caption("Informe quantas etiquetas deseja gerar para colar nas prateleiras ou caixas deste lote.")

            for _, row in df_sem_tag.iterrows():
                # Layout elegante em colunas para os inputs
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.info(f"📍 Polo: {row['localizacao']} | Saldo: {int(row['quantidade'])} un.")
                with c2:
                    qtd_labels = st.number_input(
                        "Qtd de Etiquetas", 
                        min_value=0, 
                        max_value=int(row['quantidade']), 
                        value=0, 
                        step=1, 
                        key=f"qtd_{row['id']}"
                    )
                with c3:
                    if qtd_labels > 0:
                        st.success(f"🖨️ {qtd_labels} prontas.")
                        etiquetas_para_imprimir.append({
                            'id': row['id'],
                            'codigo': codigo_puro,
                            'descricao': row['descricao'],
                            'num_tag': "LOTE / VOLUME", # Identificação visual na etiqueta
                            'localizacao': row['localizacao'],
                            'qtd_imprimir': qtd_labels
                        })

        # ==========================================
        # 4. BOTÃO FINAL E RENDERIZAÇÃO
        # ==========================================
        if etiquetas_para_imprimir:
            st.divider()
            total_etiquetas = sum(e['qtd_imprimir'] for e in etiquetas_para_imprimir)
            
            st.markdown(f"### 🖨️ Resumo: {total_etiquetas} etiqueta(s) na fila")

            if st.button("Gerar Folha de Impressão", type="primary", use_container_width=True):
                html_etiquetas = ""
                
                # O motor duplica a etiqueta HTML baseado na quantidade que o usuário escolheu (qtd_imprimir)
                for item in etiquetas_para_imprimir:
                    for _ in range(item['qtd_imprimir']):
                        html_etiquetas += formatar_etiqueta_html(item)

                html_final = f"""
                <html><body style="margin:0; padding:10px; display:flex; flex-wrap:wrap;">
                    <div style="width:100%; margin-bottom:10px; font-family:sans-serif;" class="no-print">
                        <button onclick="window.print()" style="padding:10px 20px; background:#2563eb; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">🖨️ Confirmar Impressão</button>
                    </div>
                    {html_etiquetas}
                    <style> @media print {{ .no-print {{ display: none; }} }} </style>
                </body></html>
                """
                components.html(html_final, height=600, scrolling=True)