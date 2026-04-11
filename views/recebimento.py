# tracebox/views/recebimento.py
import streamlit as st
from database.queries import carregar_dados, executar_query

# IMPORTAÇÕES DOS NOSSOS CONTROLADORES (Com a vírgula correta!)
from controllers.recebimento import (
    processar_retorno_projeto, 
    processar_recebimento_transferencia, 
    processar_reintegracao_falta, 
    processar_baixa_extravio,
    processar_entrada_compra
)

def tela_recebimento_projetos():
    st.title("📥 Central de Recebimento (Inbound)")
    usuario_atual = st.session_state['usuario_logado']['nome']
    perfil_usuario = st.session_state['usuario_logado']['perfil']

    if 'recebimento_status' not in st.session_state:
        st.session_state['recebimento_status'] = None

    if st.session_state['recebimento_status']:
        if st.session_state['recebimento_status'] == 'parcial':
            st.warning("⚠️ **Recebimento PARCIAL Concluído!**\n\nAs ferramentas faltantes foram carimbadas com 'Alerta de Falta' e enviadas para a aba de Gestão de Faltas.")
        else:
            st.success("✅ **Recebimento TOTAL Concluído!**")
        
        if st.button("Entendido - Limpar e Voltar"):
            st.session_state['recebimento_status'] = None
            st.rerun()
        return

    # AQUI ESTÁ O SEGREDO: CRIAR AS 4 ABAS CORRETAMENTE
    tab_compras, tab_projetos, tab_transito, tab_extravios = st.tabs([
        "🧾 Compras (NF)", "📥 Retorno de Projetos", "🚚 Receber Transferências", "🚨 Gestão de Faltas"
    ])

    # === ABA 1: ENTRADA DE COMPRAS (NF) ===
    with tab_compras:
        st.write("### 🧾 Entrada de Estoque via Nota Fiscal")
        st.caption("Recebimento de novos ativos baseados no catálogo Master Data.")
        
        df_catalogo = carregar_dados("SELECT DISTINCT codigo, descricao FROM imobilizado")
        lista_catalogo = df_catalogo.apply(lambda r: f"{r['codigo']} - {r['descricao']}", axis=1).tolist() if not df_catalogo.empty else []
        
        with st.form("form_entrada_nf", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                produto_selecionado = st.selectbox("Selecione o Produto (Master Data)", [""] + lista_catalogo)
            with col2:
                polo_destino = st.selectbox("Polo Recebedor", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"])
                
            c1, c2, c3 = st.columns(3)
            with c1: nf = st.text_input("Número da NF / DI *")
            with c2: valor_unit = st.number_input("Valor Unitário (R$)", min_value=0.0, format="%.2f")
            with c3: quantidade = st.number_input("Quantidade Chegou", min_value=1, value=1)
            
            st.write("---")
            tags_str = st.text_area("Injetar Seriais / TAGs (Opcional - Separado por vírgula)")
            st.caption("Se preencher as TAGs, a 'Quantidade Chegou' será ignorada e o sistema criará um item para cada TAG.")
            
            if st.form_submit_button("💾 Processar Entrada de NF", type="primary"):
                if not produto_selecionado or not nf.strip():
                    st.error("⚠️ O Produto e a Nota Fiscal são obrigatórios.")
                else:
                    codigo_puro = produto_selecionado.split(" - ")[0]
                    sucesso, msg = processar_entrada_compra(codigo_puro, polo_destino, nf, valor_unit, quantidade, tags_str, usuario_atual)
                    
                    if sucesso:
                        st.success(f"✅ {msg}")
                        st.session_state['recebimento_status'] = None 
                    else:
                        st.error(f"❌ {msg}")

    # === ABA 2: RETORNO DE PROJETOS ===
    with tab_projetos:
        df_proj = carregar_dados("SELECT DISTINCT localizacao FROM imobilizado WHERE status = 'Em Uso' AND quantidade > 0")
        projetos = df_proj['localizacao'].tolist() if not df_proj.empty else []
        
        c1, c2 = st.columns(2)
        with c1: proj_origem = st.selectbox("Projeto de Origem", [""] + projetos)
        with c2: polo_destino_proj = st.selectbox("Polo Recebedor (Retorno)", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO"])

        if proj_origem:
            df_itens = carregar_dados("SELECT * FROM imobilizado WHERE localizacao = ? AND status = 'Em Uso' AND quantidade > 0", (proj_origem,))
            with st.form("form_rec_proj"):
                selecoes = {}
                for idx, row in df_itens.iterrows():
                    id_db, cod, desc, tag, qtd_max = row['id'], row['codigo'], row['descricao'], row['num_tag'], int(row['quantidade'])
                    
                    st.markdown(f"**{cod} - {desc}**")
                    col1, col2, col3 = st.columns([1,1,2])
                    with col1: chk = st.checkbox("Chegou?", key=f"rp_{id_db}")
                    with col2: 
                        if tag:
                            st.write(f"TAG: `{tag}`")
                            qtd = 1 if chk else 0
                        else:
                            qtd = st.number_input("Qtd", min_value=0, max_value=qtd_max, value=qtd_max, key=f"q_{id_db}")
                    with col3: stt = st.selectbox("Estado", ["Disponível", "Manutenção", "Sucateado"], key=f"st_{id_db}")
                    
                    if chk and qtd > 0: 
                        selecoes[id_db] = {'qtd': qtd, 'qtd_max': qtd_max, 'status': stt, 'codigo': cod}
                
                if st.form_submit_button("📥 Confirmar Recebimento de Projeto", type="primary"):
                    if not selecoes:
                        st.error("Marque ao menos um item.")
                    else:
                        status_final = processar_retorno_projeto(selecoes, polo_destino_proj, proj_origem, usuario_atual)
                        st.session_state['recebimento_status'] = status_final
                        st.rerun()

    # === ABA 3: RECEBER TRANSFERÊNCIAS ===
    with tab_transito:
        df_transito = carregar_dados("SELECT id, codigo, descricao, quantidade, localizacao as destino_esperado FROM imobilizado WHERE status = 'Em Trânsito' AND quantidade > 0")
        if df_transito.empty:
            st.info("Nenhuma carga em trânsito no momento.")
        else:
            polo_recebedor_transf = st.selectbox("Selecione o Polo onde a carreta chegou:", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO"])
            df_carga = df_transito[df_transito['destino_esperado'] == polo_recebedor_transf]
            
            if df_carga.empty:
                st.warning(f"Não há cargas em trânsito destinadas para {polo_recebedor_transf}.")
            else:
                with st.form("form_receber_transito"):
                    selecoes_transito = []
                    for idx, row in df_carga.iterrows():
                        if st.checkbox(f"📦 Receber: {row['codigo']} - {row['descricao']} ({row['quantidade']} un.)", key=f"tr_{row['id']}"): 
                            selecoes_transito.append(row['id'])
                    
                    if st.form_submit_button("✅ Concluir Recebimento Logístico", type="primary"):
                        if selecoes_transito:
                            processar_recebimento_transferencia(selecoes_transito, polo_recebedor_transf, usuario_atual)
                            st.success("Carga recebida com sucesso!")
                            st.rerun()

    # === ABA 4: GESTÃO DE FALTAS ===
    with tab_extravios:
        if "ADM" not in usuario_atual.upper() and "ADMIN" not in perfil_usuario.upper():
            st.error("🔒 Acesso restrito a Gestores.")
        else:
            st.subheader("🚨 Painel de Conciliação de Pendências")
            df_faltas = carregar_dados("SELECT id, codigo, descricao, quantidade, localizacao as projeto FROM imobilizado WHERE alerta_falta = 1 AND quantidade > 0")

            if df_faltas.empty:
                st.success("✅ Nenhuma pendência em aberto.")
            else:
                st.dataframe(df_faltas[['projeto', 'codigo', 'descricao', 'quantidade']], use_container_width=True, hide_index=True)
                st.write("---")
                
                opcoes_faltas = df_faltas.apply(lambda r: f"ID:{r['id']} | {r['projeto']} | {r['codigo']} ({r['quantidade']} un.)", axis=1).tolist()
                item_pendente = st.selectbox("Selecione a Pendência para Resolver", [""] + opcoes_faltas)

                if item_pendente:
                    id_db = int(item_pendente.split("|")[0].replace("ID:", "").strip())
                    dados_origem = df_faltas[df_faltas['id'] == id_db].iloc[0]
                    qtd_pendente = int(dados_origem['quantidade'])

                    acao = st.radio("O que deseja fazer?", ["🔎 Material Localizado (Total ou Parcial)", "❌ Confirmar Extravio/Perda"], horizontal=True)

                    with st.form("form_resolucao_pendencia"):
                        if "Localizado" in acao:
                            st.markdown("#### ✅ Registrar Encontro de Material")
                            c1, c2 = st.columns(2)
                            with c1:
                                qtd_encontrada = st.number_input("Quantidade Localizada", min_value=1, max_value=qtd_pendente, value=qtd_pendente)
                            with c2:
                                destino_retorno = st.selectbox("Devolver para qual Polo?", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO"])
                            
                            if st.form_submit_button("Confirmar Reintegração"):
                                processar_reintegracao_falta(id_db, qtd_encontrada, qtd_pendente, destino_retorno, usuario_atual)
                                st.success(f"Itens reintegrados à {destino_retorno}!")
                                st.rerun()

                        else:
                            st.markdown("#### 🟥 Confirmar Baixa por Extravio")
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                qtd_perda = st.number_input("Quantidade Perdida", min_value=1, max_value=qtd_pendente, value=qtd_pendente)
                            with c2:
                                motivo = st.text_input("Justificativa", placeholder="Ex: Confirmado furto...")
                            
                            if st.form_submit_button("Confirmar Baixa", type="primary"):
                                if len(motivo) < 5:
                                    st.error("Descreva o motivo da perda.")
                                else:
                                    processar_baixa_extravio(id_db, qtd_perda, qtd_pendente, dados_origem['projeto'], motivo, usuario_atual)
                                    st.success("Baixa confirmada.")
                                    st.rerun()