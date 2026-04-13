# tracebox/views/produto.py
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from controllers.etiquetas import formatar_etiqueta_html
from database.queries import carregar_dados
from controllers.produto import atualizar_ficha_tecnica, deletar_produto_master

def tela_produto():
    codigo_master = st.session_state['produto_selecionado']
    usuario_atual = st.session_state['usuario_logado']
    
    CATEGORIAS_OFICIAIS = ["Ferramentas Elétricas", "Ferramentas Manuais", "EPIs", "Consumíveis", "Máquinas Pesadas", "Outros"]
    
    # Busca o "Molde" do produto
    df_mestre = carregar_dados("SELECT descricao, marca, modelo, categoria, valor_unitario, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo_master,))
    
    if df_mestre.empty:
        st.session_state['produto_selecionado'] = None
        st.rerun()
        
    dados_mestre = df_mestre.iloc[0]
    
    # Busca todo o inventário físico
    inventario_fisico = carregar_dados("SELECT id, num_tag, localizacao, status, quantidade FROM imobilizado WHERE codigo = ?", (codigo_master,))
    
    # --- CABEÇALHO ---
    st.write("<br>", unsafe_allow_html=True)
    col_topo1, col_topo2 = st.columns([5, 1])
    with col_topo1:
        st.markdown(f"<h2 style='color: #2563eb;'>📦 {dados_mestre['descricao']}</h2>", unsafe_allow_html=True)
        st.caption(f"**Cód. TraceBox:** {codigo_master} | **Volume Sistêmico:** {inventario_fisico['quantidade'].sum()} un.")
    with col_topo2:
        if st.button("⬅️ Voltar", use_container_width=True, type="primary"): 
            st.session_state['produto_selecionado'] = None
            st.rerun()
    
    aba1, aba2, aba3 = st.tabs(["📋 Saldos e Localizações", "📝 Prontuário Técnico", "📜 Auditoria"])

    # === ABA 1: VISUALIZAÇÃO E ETIQUETAGEM ===
    with aba1:
        col_list, col_print = st.columns([2, 1])
        
        with col_list:
            st.write("### 📍 Distribuição Física")
            if not inventario_fisico.empty:
                # Lógica de exibição da tabela consolidada
                df_com_tag = inventario_fisico[inventario_fisico['num_tag'].notna() & (inventario_fisico['num_tag'] != '')].copy()
                df_sem_tag = inventario_fisico[inventario_fisico['num_tag'].isna() | (inventario_fisico['num_tag'] == '')].copy()
                
                tabs_df = []
                if not df_sem_tag.empty:
                    df_lotes = df_sem_tag.groupby(['localizacao', 'status'])['quantidade'].sum().reset_index()
                    df_lotes['Tipo'] = "📦 Lote"
                    df_lotes['ID/TAG'] = "N/A"
                    tabs_df.append(df_lotes[['Tipo', 'ID/TAG', 'localizacao', 'status', 'quantidade']])
                    
                if not df_com_tag.empty:
                    df_com_tag['Tipo'] = "🏷️ Item"
                    df_com_tag.rename(columns={'num_tag': 'ID/TAG'}, inplace=True)
                    tabs_df.append(df_com_tag[['Tipo', 'ID/TAG', 'localizacao', 'status', 'quantidade']])
                
                df_final = pd.concat(tabs_df, ignore_index=True)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum item físico em estoque.")

        with col_print:
            st.write("### 🏷️ Impressão")
            st.caption("Gere a etiqueta QR Code de uma unidade específica.")
            
            # Criamos uma lista amigável para o selectbox
            opcoes_print = inventario_fisico.apply(
                lambda r: f"ID:{r['id']} | {r['num_tag'] if r['num_tag'] else 'Lote'} ({r['localizacao']})", 
                axis=1
            ).tolist()
            
            item_selecionado = st.selectbox("Selecione a unidade:", [""] + opcoes_print)
            
            if item_selecionado:
                # Extraímos o ID real para buscar os dados
                id_alvo = int(item_selecionado.split("|")[0].replace("ID:", "").strip())
                dados_item = inventario_fisico[inventario_fisico['id'] == id_alvo].iloc[0]
                
                # Montamos o dicionário que o formatador de etiquetas espera
                payload_etiqueta = {
                    'id': dados_item['id'],
                    'codigo': codigo_master,
                    'descricao': dados_mestre['descricao'],
                    'num_tag': dados_item['num_tag'],
                    'localizacao': dados_item['localizacao']
                }
                
                if st.button("🖨️ Imprimir Etiqueta", use_container_width=True, type="primary"):
                    html_content = formatar_etiqueta_html(payload_etiqueta)
                    # O script onload="window.print()" faz o navegador abrir a caixa de impressão automaticamente
                    html_final = f"<html><body onload='window.print()'>{html_content}</body></html>"
                    components.html(html_final, height=200)

    # === ABA 2: PRONTUÁRIO TÉCNICO ===
    with aba2:
        st.write("### ⚙️ Características do Produto")
        modo_edicao = st.toggle("🔓 Habilitar Edição")
        
        with st.form("form_mestre"):
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                nova_desc = st.text_input("Nomenclatura", value=dados_mestre['descricao'], disabled=not modo_edicao)
                nova_marca = st.text_input("Fabricante", value=dados_mestre['marca'] or "", disabled=not modo_edicao)
                novo_modelo = st.text_input("Modelo", value=dados_mestre['modelo'] or "", disabled=not modo_edicao)
                nova_cat = st.selectbox("Categoria", CATEGORIAS_OFICIAIS, index=CATEGORIAS_OFICIAIS.index(dados_mestre['categoria']) if dados_mestre['categoria'] in CATEGORIAS_OFICIAIS else 0, disabled=not modo_edicao)
                novo_valor = st.number_input("Valor Unitário (R$)", value=float(dados_mestre['valor_unitario'] or 0.0), disabled=not modo_edicao)
            with c_f2:
                nova_dim = st.text_input("Dimensões", value=dados_mestre['dimensoes'] or "", disabled=not modo_edicao)
                nova_cap = st.text_input("Capacidade", value=dados_mestre['capacidade'] or "", disabled=not modo_edicao)
                nova_ult_man = st.text_input("Última Manutenção", value=dados_mestre['ultima_manutencao'] or "", disabled=not modo_edicao)
                nova_prox_man = st.text_input("Próxima Manutenção", value=dados_mestre['proxima_manutencao'] or "", disabled=not modo_edicao)
            
            novos_detalhes = st.text_area("Notas Adicionais", value=dados_mestre['detalhes'] or "", disabled=not modo_edicao)
            
            if st.form_submit_button("💾 Atualizar Master Data", type="primary", disabled=not modo_edicao):
                dados_up = {
                    'descricao': nova_desc, 'marca': nova_marca, 'modelo': novo_modelo, 'categoria': nova_cat,
                    'valor_unitario': novo_valor, 'dimensoes': nova_dim, 'capacidade': nova_cap,
                    'ultima_manutencao': nova_ult_man, 'proxima_manutencao': nova_prox_man, 'detalhes': novos_detalhes
                }
                atualizar_ficha_tecnica(codigo_master, dados_up)
                st.success("Dados atualizados!")
                st.rerun()

    # === ABA 3: AUDITORIA ===
    with aba3:
        ids_produto = tuple(inventario_fisico['id'].tolist())
        if ids_produto:
            # Query com suporte a múltiplos IDs para pegar o rastro de todas as unidades desse código
            placeholders = ','.join('?' for _ in ids_produto)
            query_hist = f"""
                SELECT m.data_movimentacao as Data, i.num_tag as Serial, m.tipo as Operação, 
                       m.documento as 'Doc/NF', m.responsavel as Agente, m.destino_projeto as Destino 
                FROM movimentacoes m 
                JOIN imobilizado i ON m.ferramenta_id = i.id 
                WHERE m.ferramenta_id IN ({placeholders}) 
                ORDER BY m.data_movimentacao DESC
            """
            hist = carregar_dados(query_hist, ids_produto)
            if not hist.empty: 
                st.dataframe(hist, use_container_width=True, hide_index=True)
            else: 
                st.info("Nenhum histórico de movimentação encontrado.")