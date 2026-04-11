# tracebox/views/produto.py
import streamlit as st
import pandas as pd
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
    
    # --- CABEÇALHO ISOLADO ---
    st.write("<br>", unsafe_allow_html=True)
    col_topo1, col_topo2 = st.columns([5, 1])
    with col_topo1:
        st.markdown(f"<h2 style='color: #2563eb;'>📦 {dados_mestre['descricao']}</h2>", unsafe_allow_html=True)
        st.caption(f"**Cód. TraceBox:** {codigo_master} | **Volume Sistêmico:** {inventario_fisico['quantidade'].sum()} un.")
    with col_topo2:
        if st.button("⬅️ Voltar ao Dashboard", use_container_width=True, type="primary"): 
            st.session_state['produto_selecionado'] = None
            st.rerun()
    
    aba1, aba2, aba3 = st.tabs(["📋 Saldos e Localizações", "📝 Prontuário Técnico (Master Data)", "📜 Auditoria (Trace)"])

    # === ABA 1: VISUALIZAÇÃO DE SALDOS (S/ EDIÇÃO) ===
    with aba1:
        st.write("### 📍 Distribuição Física")
        st.caption("Visão de apenas leitura. Para movimentar saldos, utilize as telas de Logística.")
        
        if not inventario_fisico.empty:
            # 1. Separa o que tem TAG e o que não tem
            df_com_tag = inventario_fisico[inventario_fisico['num_tag'].notna() & (inventario_fisico['num_tag'] != '')].copy()
            df_sem_tag = inventario_fisico[inventario_fisico['num_tag'].isna() | (inventario_fisico['num_tag'] == '')].copy()
            
            tabelas_para_exibir = []
            
            # 2. Consolida os Lotes (Soma as quantidades que estão no mesmo polo e status)
            if not df_sem_tag.empty:
                df_lotes = df_sem_tag.groupby(['localizacao', 'status'])['quantidade'].sum().reset_index()
                df_lotes['Tipo'] = "📦 Lote Consolidado"
                df_lotes['Identificação'] = "N/A"
                tabelas_para_exibir.append(df_lotes[['Tipo', 'Identificação', 'localizacao', 'status', 'quantidade']])
                
            # 3. Mantém as TAGs individuais
            if not df_com_tag.empty:
                df_com_tag['Tipo'] = "🏷️ Item Rastreado"
                df_com_tag.rename(columns={'num_tag': 'Identificação'}, inplace=True)
                tabelas_para_exibir.append(df_com_tag[['Tipo', 'Identificação', 'localizacao', 'status', 'quantidade']])
            
            # Junta tudo numa tabela final bonita
            df_final = pd.concat(tabelas_para_exibir, ignore_index=True)
            df_final.rename(columns={'localizacao': 'Polo/Destino', 'status': 'Status', 'quantidade': 'Qtd'}, inplace=True)
            
            st.dataframe(df_final, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum item físico em estoque para este produto.")

    # === ABA 2: PRONTUÁRIO COM "CADEADO" DE SEGURANÇA ===
    with aba2:
        st.write("### ⚙️ Características do Produto")
        
        # O Cadeado: Exige que o utilizador clique aqui para liberar a edição
        modo_edicao = st.toggle("🔓 Habilitar Modo de Edição de Cadastro")
        
        with st.form("form_mestre"):
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                nova_desc = st.text_input("Nomenclatura Padrão", value=dados_mestre['descricao'], disabled=not modo_edicao)
                nova_marca = st.text_input("Fabricante", value=dados_mestre['marca'] if dados_mestre['marca'] else "", disabled=not modo_edicao)
                novo_modelo = st.text_input("Modelo/Série", value=dados_mestre['modelo'] if dados_mestre['modelo'] else "", disabled=not modo_edicao)
                
                cat_index = CATEGORIAS_OFICIAIS.index(dados_mestre['categoria']) if dados_mestre['categoria'] in CATEGORIAS_OFICIAIS else 0
                nova_cat = st.selectbox("Grupo Lógico", CATEGORIAS_OFICIAIS, index=cat_index, disabled=not modo_edicao)
                novo_valor = st.number_input("Custo de Reposição (R$)", value=float(dados_mestre['valor_unitario']) if dados_mestre['valor_unitario'] else 0.0, disabled=not modo_edicao)
            with c_f2:
                nova_dim = st.text_input("Gabarito (Dimensões)", value=dados_mestre['dimensoes'] if dados_mestre['dimensoes'] else "", disabled=not modo_edicao)
                nova_cap = st.text_input("Carga/Capacidade", value=dados_mestre['capacidade'] if dados_mestre['capacidade'] else "", disabled=not modo_edicao)
                nova_ult_man = st.text_input("Registro Última Manutenção", value=dados_mestre['ultima_manutencao'] if dados_mestre['ultima_manutencao'] else "", disabled=not modo_edicao)
                nova_prox_man = st.text_input("Vencimento Calibração", value=dados_mestre['proxima_manutencao'] if dados_mestre['proxima_manutencao'] else "", disabled=not modo_edicao)
            
            novos_detalhes = st.text_area("Laudos e Observações", value=dados_mestre['detalhes'] if dados_mestre['detalhes'] else "", disabled=not modo_edicao)
            
            if st.form_submit_button("💾 Salvar Alterações no Master Data", type="primary", disabled=not modo_edicao):
                dados_atualizados = {
                    'descricao': nova_desc, 'marca': nova_marca, 'modelo': novo_modelo, 'categoria': nova_cat,
                    'valor_unitario': novo_valor, 'dimensoes': nova_dim, 'capacidade': nova_cap,
                    'ultima_manutencao': nova_ult_man, 'proxima_manutencao': nova_prox_man, 'detalhes': novos_detalhes
                }
                atualizar_ficha_tecnica(codigo_master, dados_atualizados)
                st.success("Ficha atualizada com sucesso!")
                st.rerun()
                
        # Área de Perigo (Exclusão)
        if usuario_atual['perfil'] == 'Admin':
            st.divider()
            st.markdown("#### ⚠️ Zona de Perigo")
            st.caption("A exclusão apagará o Master Data e todos os registros físicos de estoque permanentemente.")
            confirmar_exclusao = st.checkbox(f"Declaro ciente a exclusão do produto: {codigo_master}")
            
            if st.button("🗑️ Deletar Registro (Ação Irreversível)", disabled=not confirmar_exclusao):
                deletar_produto_master(codigo_master)
                st.success("Exclusão executada.")
                st.session_state['produto_selecionado'] = None
                st.rerun()

    # === ABA 3: AUDITORIA (CORRIGIDA) ===
    with aba3:
        ids_produto = tuple(inventario_fisico['id'].tolist())
        if ids_produto:
            # Correção: O campo no seu banco original chama-se 'data_movimentacao'
            query_hist = f"""
                SELECT m.data_movimentacao as Data, i.num_tag as Serial, m.tipo as Operação, 
                       m.documento as 'NF/DOC', m.responsavel as Agente, m.destino_projeto as Destino 
                FROM movimentacoes m 
                JOIN imobilizado i ON m.ferramenta_id = i.id 
                WHERE m.ferramenta_id IN ({','.join('?' for _ in ids_produto)}) 
                ORDER BY m.data_movimentacao DESC
            """
            hist = carregar_dados(query_hist, ids_produto)
            if not hist.empty: 
                st.dataframe(hist, use_container_width=True, hide_index=True)
            else: 
                st.info("Sem registro de logs para este produto.")