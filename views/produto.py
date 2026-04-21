# tracebox/views/produto.py
import streamlit as st
import pandas as pd
import base64
import streamlit.components.v1 as components
from controllers.etiquetas import formatar_etiqueta_html
from client.api_client import TraceBoxClient

def tela_produto():
    codigo_master = st.session_state.get('produto_selecionado')
    if not codigo_master:
        st.error("Nenhum produto selecionado.")
        if st.button("Voltar"): st.rerun()
        return

    usuario_atual = st.session_state['usuario_logado']
    perfil_atual = usuario_atual.get('perfil', 'Operador').upper()
    is_admin_ou_gestor = "ADM" in perfil_atual or "GESTOR" in perfil_atual
    
    config_atual = TraceBoxClient.get_config() or {}
    CATEGORIAS_OFICIAIS = config_atual.get('categorias_produto', [])
    if not CATEGORIAS_OFICIAIS:
        CATEGORIAS_OFICIAIS = ["Elétrica", "Mecânica", "Hidráulica", "EPI", "Insumos", "Outros", "Ferramentas Elétricas", "Ferramentas Manuais", "Máquinas Pesadas", "Consumíveis"]
    
    dados_produto = TraceBoxClient.get_produto_detalhes(codigo_master)
    
    if not dados_produto:
        st.error("Produto não encontrado ou API offline.")
        st.session_state['produto_selecionado'] = None
        if st.button("Voltar"): st.rerun()
        return
        
    dados_mestre = dados_produto['mestre']
    inventario_fisico = pd.DataFrame(dados_produto['inventario'])
    df_tags = pd.DataFrame(dados_produto['tags'])
    hist = pd.DataFrame(dados_produto['historico'])
    
    st.write("<br>", unsafe_allow_html=True)
    col_topo1, col_topo2 = st.columns([5, 1])
    with col_topo1:
        st.markdown(f"<h2 style='color: #2563eb;'>📦 {dados_mestre['descricao']}</h2>", unsafe_allow_html=True)
        volume_total = inventario_fisico['quantidade'].sum() if not inventario_fisico.empty else 0
        tipo_mat = dados_mestre.get('tipo_material', 'N/A')
        tipo_ctrl = dados_mestre.get('tipo_controle', 'N/A')
        st.caption(f"**Cód. TraceBox:** {codigo_master} | **Volume Sistêmico:** {int(volume_total)} un. | **Classificação:** {tipo_mat} ({tipo_ctrl})")
    with col_topo2:
        if st.button("⬅️ Voltar", use_container_width=True, type="primary"): 
            st.session_state['produto_selecionado'] = None
            st.rerun()
    
    aba1, aba2, aba3, aba4 = st.tabs(["📋 Saldos e Localizações", "📝 Prontuário Técnico", "🏷️ Gestão de Calibração", "📜 Auditoria"])

    with aba1:
        col_list, col_print = st.columns([2, 1])
        
        with col_list:
            st.write("### 📍 Distribuição Física")
            if not inventario_fisico.empty:
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
                
                if tabs_df:
                    df_final = pd.concat(tabs_df, ignore_index=True)
                    st.dataframe(df_final.rename(columns={'localizacao': 'Polo/Doca', 'status': 'Status', 'quantidade': 'Qtd'}), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum item físico deste produto em estoque no momento.")

        with col_print:
            st.write("### 🏷️ Impressão")
            st.caption("Gere a etiqueta QR Code de uma unidade específica.")
            
            if not inventario_fisico.empty:
                opcoes_print = inventario_fisico.apply(
                    lambda r: f"ID:{r['id']} | {r['num_tag'] if r['num_tag'] else 'Lote'} ({r['localizacao']})", 
                    axis=1
                ).tolist()
                item_selecionado = st.selectbox("Selecione a unidade:", [""] + opcoes_print)
                
                if item_selecionado:
                    id_alvo = int(item_selecionado.split("|")[0].replace("ID:", "").strip())
                    dados_item = inventario_fisico[inventario_fisico['id'] == id_alvo].iloc[0]
                    
                    payload_etiqueta = {
                        'id': dados_item['id'], 'codigo': codigo_master, 'descricao': dados_mestre['descricao'],
                        'num_tag': dados_item['num_tag'], 'localizacao': dados_item['localizacao']
                    }
                    if st.button("🖨️ Imprimir Etiqueta", use_container_width=True, type="primary"):
                        html_content = formatar_etiqueta_html(payload_etiqueta)
                        html_final = f"<html><body onload='window.print()'>{html_content}</body></html>"
                        components.html(html_final, height=200)
            else:
                st.warning("Não há itens para imprimir.")

    with aba2:
        st.write("### ⚙️ Características do Produto (Master Data)")
        if is_admin_ou_gestor:
            modo_edicao = st.toggle("🔓 Habilitar Edição")
            if not modo_edicao: st.info("Ative a edição no botão acima para alterar os dados da Ficha Técnica.")
        else:
            modo_edicao = False
            st.error("🔒 **Acesso Restrito:** Apenas Gestores e Administradores podem editar a Ficha Técnica Base.")
        
        with st.form("form_mestre"):
            c_img, c_f1, c_f2 = st.columns([1, 2, 2])
            
            with c_img:
                if dados_mestre.get('imagem') and dados_mestre['imagem'].strip() != "":
                    st.image(f"data:image/png;base64,{dados_mestre['imagem']}", use_container_width=True)
                else:
                    st.info("Sem imagem cadastrada.")
                nova_imagem_file = st.file_uploader("Alterar Foto", type=['png', 'jpg', 'jpeg'], disabled=not modo_edicao)
                
            with c_f1:
                nova_desc = st.text_input("Nomenclatura", value=dados_mestre['descricao'], disabled=not modo_edicao)
                nova_marca = st.text_input("Fabricante", value=dados_mestre['marca'] or "", disabled=not modo_edicao)
                novo_modelo = st.text_input("Modelo", value=dados_mestre['modelo'] or "", disabled=not modo_edicao)
                
                cat_atual = dados_mestre['categoria']
                idx_cat = CATEGORIAS_OFICIAIS.index(cat_atual) if cat_atual in CATEGORIAS_OFICIAIS else 0
                nova_cat = st.selectbox("Categoria", CATEGORIAS_OFICIAIS, index=idx_cat, disabled=not modo_edicao)
                novo_valor = st.number_input("Valor Unitário (R$)", value=float(dados_mestre['valor_unitario'] or 0.0), disabled=not modo_edicao)
            with c_f2:
                nova_dim = st.text_input("Dimensões / Peso", value=dados_mestre['dimensoes'] or "", disabled=not modo_edicao)
                nova_cap = st.text_input("Capacidade / Vida Útil", value=dados_mestre['capacidade'] or "", disabled=not modo_edicao)
                
                if tipo_ctrl == "TAG":
                    st.text_input("Última Manutenção Base", value="Variável (Ver aba Gestão de Calibração)", disabled=True)
                    st.text_input("Próxima Manutenção Base", value="Variável (Ver aba Gestão de Calibração)", disabled=True)
                    nova_ult_man = dados_mestre.get('ultima_manutencao', '') or ''
                    nova_prox_man = dados_mestre.get('proxima_manutencao', '') or ''
                else:
                    nova_ult_man = st.text_input("Última Inspeção do Lote (AAAA-MM-DD)", value=str(dados_mestre.get('ultima_manutencao', '') or "")[:10], disabled=not modo_edicao)
                    nova_prox_man = st.text_input("Próxima Inspeção do Lote (AAAA-MM-DD)", value=str(dados_mestre.get('proxima_manutencao', '') or "")[:10], disabled=not modo_edicao)
            
            novos_detalhes = st.text_area("Notas Adicionais", value=dados_mestre['detalhes'] or "", disabled=not modo_edicao)
            
            if is_admin_ou_gestor:
                if st.form_submit_button("💾 Atualizar Master Data", type="primary", disabled=not modo_edicao):
                    imagem_final = dados_mestre.get('imagem', '')
                    if nova_imagem_file is not None:
                        bytes_da_foto = nova_imagem_file.getvalue()
                        if bytes_da_foto:
                            imagem_final = base64.b64encode(bytes_da_foto).decode('utf-8')
                        
                    dados_up = {
                        'descricao': nova_desc, 'marca': nova_marca, 'modelo': novo_modelo, 'categoria': nova_cat,
                        'valor_unitario': novo_valor, 'dimensoes': nova_dim, 'capacidade': nova_cap,
                        'ultima_manutencao': nova_ult_man, 'proxima_manutencao': nova_prox_man, 'detalhes': novos_detalhes,
                        'imagem': imagem_final
                    }
                    sucesso = TraceBoxClient.update_produto_mestre(codigo_master, dados_up)
                    if sucesso:
                        st.success("Ficha Técnica atualizada com sucesso!")
                        import time; time.sleep(1); st.rerun()
                    else:
                        st.error("Erro ao atualizar Ficha Técnica.")
            else:
                st.form_submit_button("💾 Atualizar Master Data", type="primary", disabled=True)

    with aba3:
        st.subheader("Controle Individual de TAGs e Calibração")
        if tipo_ctrl != "TAG":
            st.info("Este produto é controlado por **Lote**. As datas de inspeção são geridas globalmente na aba 'Prontuário Técnico'.")
        else:
            if not is_admin_ou_gestor:
                st.error("🔒 **Acesso Restrito:** Apenas Gestores e Administradores podem alterar os calendários de calibração das TAGs.")
            
            st.write("Edite as datas nos campos com ✏️ na tabela abaixo e clique em Salvar.")
            if df_tags.empty:
                st.info("Não há patrimónios físicos rastreáveis (TAGs) registados para este produto no momento.")
            else:
                df_tags['Última Inspeção'] = pd.to_datetime(df_tags['Última Inspeção'], errors='coerce')
                df_tags['Deadline Calibração'] = pd.to_datetime(df_tags['Deadline Calibração'], errors='coerce')
                
                with st.form("form_calibracao"):
                    df_editado = st.data_editor(
                        df_tags, hide_index=True, use_container_width=True, disabled=not is_admin_ou_gestor,
                        column_config={
                            "ID_DB": None,
                            "TAG": st.column_config.TextColumn(disabled=True),
                            "Localização": st.column_config.TextColumn(disabled=True),
                            "Status": st.column_config.TextColumn(disabled=True),
                            "Última Inspeção": st.column_config.DateColumn("✏️ Última Inspeção", format="YYYY-MM-DD"),
                            "Deadline Calibração": st.column_config.DateColumn("✏️ Prazo Calibração", format="YYYY-MM-DD")
                        }
                    )
                    
                    if is_admin_ou_gestor:
                        if st.form_submit_button("💾 Salvar Calendários de Calibração", type="primary"):
                            itens_calibracao = []
                            for _, row in df_editado.iterrows():
                                itens_calibracao.append({
                                    "ID_DB": int(row['ID_DB']),
                                    "ultima_inspecao": str(row['Última Inspeção'])[:10] if pd.notna(row['Última Inspeção']) else "",
                                    "deadline_calibracao": str(row['Deadline Calibração'])[:10] if pd.notna(row['Deadline Calibração']) else ""
                                })
                            
                            sucesso, msg = TraceBoxClient.update_produto_calibracao(codigo_master, itens_calibracao, usuario_atual['nome'])
                            if sucesso:
                                st.success(msg)
                                import time; time.sleep(1); st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.form_submit_button("💾 Salvar Calendários de Calibração", type="primary", disabled=True)

    with aba4:
        st.write("### 📜 Histórico de Vida do Produto")
        if not hist.empty: 
            st.dataframe(hist, use_container_width=True, hide_index=True)
        else: 
            st.info("Nenhum histórico de movimentação encontrado.")