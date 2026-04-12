# tracebox/views/inbound.py
import streamlit as st
import time
import pandas as pd
from database.queries import carregar_dados
from controllers.inbound import (
    configurar_tabela_inbound, processar_entrada_compra, obter_origens_esperadas, 
    carregar_itens_esperados, processar_recebimento_doca, processar_reintegracao_falta, processar_baixa_extravio
)

def tela_logistica_inbound():
    configurar_tabela_inbound()
    
    st.title("📥 Logística Inbound (Recebimento)")
    st.caption("Doca de Descarga WMS Híbrida e Malha Fina de Pendências.")
    
    usuario_atual = st.session_state['usuario_logado']['nome']
    perfil_atual = st.session_state['usuario_logado'].get('perfil', 'Operador').upper()
    is_admin = "ADM" in perfil_atual or "GESTOR" in perfil_atual

    if 'inb_polo' not in st.session_state: st.session_state['inb_polo'] = "Filial CTG"

    tab_compras, tab_doca, tab_malha = st.tabs(["🧾 Compras (NF)", "🚛 Doca de Descarga WMS", "🚨 Malha Fina (Faltas)"])

    # ==============================================================
    # ABA 1: ENTRADA DE COMPRAS (NF)
    # ==============================================================
    with tab_compras:
        st.subheader("Entrada de Estoque via Nota Fiscal")
        st.caption("Recebimento de novos ativos baseados no catálogo Master Data.")
        
        df_catalogo = carregar_dados("SELECT DISTINCT codigo, descricao FROM imobilizado")
        lista_catalogo = df_catalogo.apply(lambda r: f"{r['codigo']} - {r['descricao']}", axis=1).tolist() if not df_catalogo.empty else []
        
        with st.form("form_entrada_nf", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1: produto_selecionado = st.selectbox("Selecione o Produto (Master Data)", [""] + lista_catalogo)
            with col2:
                opcoes_polo = ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"]
                idx_polo = opcoes_polo.index(st.session_state['inb_polo']) if st.session_state['inb_polo'] in opcoes_polo else 0
                polo_destino = st.selectbox("Polo Recebedor", opcoes_polo, index=idx_polo)
                
            c1, c2, c3 = st.columns(3)
            with c1: nf = st.text_input("Número da NF / DI *")
            with c2: valor_unit = st.number_input("Valor Unitário (R$)", min_value=0.0, format="%.2f")
            with c3: quantidade = st.number_input("Quantidade Chegou", min_value=1, value=1)
            
            st.write("---")
            tags_str = st.text_area("Injetar Seriais / TAGs (Opcional - Separado por vírgula)")
            st.caption("Se preencher as TAGs, a 'Quantidade' acima será ignorada e o sistema criará um item para cada TAG informada.")
            
            if st.form_submit_button("💾 Processar Entrada de NF", type="primary", use_container_width=True):
                if not produto_selecionado or not nf.strip():
                    st.error("⚠️ O Produto e a Nota Fiscal são obrigatórios.")
                else:
                    codigo_puro = produto_selecionado.split(" - ")[0]
                    sucesso, msg = processar_entrada_compra(codigo_puro, polo_destino, nf, valor_unit, quantidade, tags_str, usuario_atual)
                    if sucesso: st.success(f"✅ {msg}")
                    else: st.error(f"❌ {msg}")

    # ==============================================================
    # ABA 2: DOCA DE DESCARGA (WMS WIZARD HÍBRIDO)
    # ==============================================================
    with tab_doca:
        if 'inb_passo' not in st.session_state: st.session_state['inb_passo'] = 'selecao'

        if st.session_state['inb_passo'] == 'selecao':
            st.subheader("1. Identificação da Carga")
            c_polo, c_origem = st.columns(2)
            with c_polo:
                polo_atual = st.selectbox("📍 Polo Atual:", opcoes_polo, index=idx_polo, key="doca_polo")
                st.session_state['inb_polo'] = polo_atual
            
            with c_origem:
                origens_disp = obter_origens_esperadas(polo_atual)
                if not origens_disp: st.info("Nenhuma carga em trânsito ou retorno esperado."); origem_sel = None
                else: origem_sel = st.selectbox("🚚 Carga vinda de:", [""] + origens_disp)

            if origem_sel:
                st.divider()
                st.subheader(f"📋 Manifesto de Carga: {origem_sel}")
                df_esperados = carregar_itens_esperados(origem_sel, polo_atual)
                if df_esperados.empty: st.warning("Carga vazia no banco de dados.")
                else:
                    st.dataframe(df_esperados[['codigo', 'descricao', 'num_tag', 'quantidade', 'tipo_material']], hide_index=True, use_container_width=True)
                    if st.button("📦 Iniciar Descarregamento / Conferência", type="primary", use_container_width=True):
                        st.session_state['inb_origem'] = origem_sel
                        st.session_state['inb_df_esperados'] = df_esperados
                        st.session_state['inb_tags_bipadas'] = {}
                        st.session_state['inb_lotes'] = {}
                        st.session_state['inb_tab_idx'] = 0
                        st.session_state['inb_passo'] = 'conferencia'
                        st.rerun()

        elif st.session_state['inb_passo'] == 'conferencia':
            origem = st.session_state['inb_origem']
            polo = st.session_state['inb_polo']
            df_esperados = st.session_state['inb_df_esperados']
            
            if st.button("← Cancelar e Voltar"): st.session_state['inb_passo'] = 'selecao'; st.rerun()
            st.subheader(f"🔎 Conferência: {origem}")
            st.info("Itens não bipados ou não contados cairão na Malha Fina (Alerta de Falta).")

            df_ativos = df_esperados[df_esperados['tipo_material'].str.upper() == 'ATIVO']
            df_lotes = df_esperados[df_esperados['tipo_material'].str.upper() != 'ATIVO']

            guias = []
            if not df_ativos.empty: guias.append("🔫 1. Ativos (Bipar/Manual)")
            if not df_lotes.empty: guias.append("📦 2. Lotes (Triagem)")
            guias.append("✅ 3. Fechar Romaneio")
            
            st.session_state['inb_tab_idx'] = min(st.session_state.get('inb_tab_idx', 0), len(guias) - 1)
            aba_selecionada = st.radio("Navegação do Recebimento:", options=guias, horizontal=True, index=st.session_state['inb_tab_idx'])
            if aba_selecionada != guias[st.session_state['inb_tab_idx']]:
                st.session_state['inb_tab_idx'] = guias.index(aba_selecionada); st.rerun()

            aba_atual = guias[st.session_state['inb_tab_idx']]
            st.write("---")

            # Gatilho Inteligente do Foguete 🚀
            def checar_ativos_inb_completos():
                return len(st.session_state['inb_tags_bipadas']) == len(df_ativos)

            # =========================================================
            # ETAPA 1: ATIVOS
            # =========================================================
            if aba_atual == "🔫 1. Ativos (Bipar/Manual)":
                col_leitor, col_btn = st.columns([3, 1])
                with col_leitor: st.subheader("1. Leitura Rápida via Coletor")
                with col_btn: 
                    if st.button("🧹 Resetar Leituras", use_container_width=True): 
                        st.session_state['inb_tags_bipadas'] = {}
                        st.rerun()

                with st.form("form_inb_leitor", clear_on_submit=True):
                    tag_lida = st.text_input("Bipe a TAG aqui e aperte Enter:", key="inb_leitor")
                    if st.form_submit_button("Registrar TAG", use_container_width=True) and tag_lida:
                        tag_limpa = str(tag_lida).strip().upper()
                        if tag_limpa not in df_ativos['num_tag'].str.upper().values: 
                            st.error(f"🚨 A TAG '{tag_limpa}' NÃO pertence a esta carga!")
                        elif tag_limpa in st.session_state['inb_tags_bipadas']:
                            st.warning(f"⚠️ A TAG '{tag_limpa}' já foi recebida.")
                        else:
                            cod_da_tag = df_ativos[df_ativos['num_tag'].str.upper() == tag_limpa].iloc[0]['codigo']
                            st.session_state['inb_tags_bipadas'][tag_limpa] = {'codigo': cod_da_tag, 'status_qualidade': 'Disponível', 'metodo': 'Coletor'}
                            
                            if checar_ativos_inb_completos():
                                st.toast("🎉 Todos os ativos recebidos! Avançando...", icon="🚀")
                                st.session_state['inb_tab_idx'] += 1
                                time.sleep(0.6)
                                st.rerun()
                            else:
                                st.success(f"✅ TAG {tag_limpa} recebida via Coletor!")

                st.divider()
                st.subheader("2. Painel de Qualidade e Seleção Manual")
                
                codigos_ativos = df_ativos['codigo'].unique()
                
                for cod in codigos_ativos:
                    df_cod = df_ativos[df_ativos['codigo'] == cod]
                    qtd_p = len(df_cod)
                    desc = df_cod.iloc[0]['descricao']
                    tags_esperadas = df_cod['num_tag'].str.upper().tolist()
                    
                    tags_separadas = {t: info for t, info in st.session_state['inb_tags_bipadas'].items() if info['codigo'] == cod}
                    lidas = len(tags_separadas)
                    
                    st.write(f"**{cod} - {desc}**")
                    
                    if lidas > 0:
                        for t, info in tags_separadas.items():
                            c_info, c_status = st.columns([2, 1])
                            with c_info: st.success(f"✅ TAG: {t} ({info['metodo']})")
                            with c_status:
                                status_atual = info['status_qualidade']
                                novo_status = st.selectbox("Condição:", ["Disponível", "Manutenção", "Sucateado"], index=["Disponível", "Manutenção", "Sucateado"].index(status_atual), key=f"qual_{t}")
                                st.session_state['inb_tags_bipadas'][t]['status_qualidade'] = novo_status
                    
                    faltam = qtd_p - lidas
                    if faltam > 0:
                        opcoes_manuais = [t for t in tags_esperadas if t not in tags_separadas]
                        col_multi, col_btn_man = st.columns([3, 1])
                        with col_multi:
                            selecionados = st.multiselect(f"Faltam {faltam} un. Selecione as que chegaram:", options=opcoes_manuais, key=f"manual_{cod}")
                        with col_btn_man:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            if st.button("Salvar Seleção", key=f"btn_man_{cod}", type="secondary", use_container_width=True):
                                if len(selecionados) > faltam: st.error(f"Selecione apenas {faltam} opções!")
                                elif len(selecionados) == 0: st.warning("Selecione ao menos uma TAG.")
                                else:
                                    for t in selecionados: st.session_state['inb_tags_bipadas'][t] = {'codigo': cod, 'status_qualidade': 'Disponível', 'metodo': 'Manual'}
                                    if checar_ativos_inb_completos():
                                        st.toast("🎉 Todos os ativos recebidos! Avançando...", icon="🚀")
                                        st.session_state['inb_tab_idx'] += 1
                                    st.rerun() 
                    else: st.info(f"🎉 100% das unidades de {cod} foram recebidas!")
                    st.write("---")

                # =======================================================
                # O BOTÃO SALVA-VIDAS (ANTI-USB E PARA FALTAS)
                # =======================================================
                if st.button("💾 Confirmar Ativos Lidos e Avançar ➔", type="primary", use_container_width=True):
                    st.session_state['inb_tab_idx'] += 1
                    st.rerun()

# =========================================================
            # ETAPA 2: LOTES
            # =========================================================
            elif aba_atual == "📦 2. Lotes (Triagem)":
                st.subheader("Triagem de Qualidade de Consumíveis")
                if 'inb_lotes' not in st.session_state: st.session_state['inb_lotes'] = {}

                for _, row in df_lotes.iterrows():
                    id_db = int(row['id']) # A SOLUÇÃO: Garante uma chave única no Streamlit
                    cod, qtd_esperada = row['codigo'], int(row['quantidade'])
                    
                    st.markdown(f"**{cod} - {row['descricao']}** (Esperado: {qtd_esperada} un | Lote ID: {id_db})")
                    c1, c2, c3 = st.columns(3)
                    with c1: q_disp = st.number_input("✅ Bons", min_value=0, max_value=qtd_esperada, value=qtd_esperada, key=f"d_{id_db}")
                    with c2: q_man = st.number_input("🔧 Quebrados", min_value=0, max_value=qtd_esperada, value=0, key=f"m_{id_db}")
                    with c3: q_suc = st.number_input("🗑️ Lixo", min_value=0, max_value=qtd_esperada, value=0, key=f"s_{id_db}")
                    
                    # Salva no dicionário usando o ID do Banco, e não o código!
                    st.session_state['inb_lotes'][id_db] = {'disponivel': q_disp, 'manutencao': q_man, 'sucata': q_suc}
                    
                    total = q_disp + q_man + q_suc
                    if total > qtd_esperada: st.error("🚨 Mais itens do que o esperado!")
                    elif total < qtd_esperada: st.warning(f"⚠️ Faltam {qtd_esperada - total} un. (Cairão na Malha Fina)")
                    st.divider()

                if st.button("Ir para Fechamento ➔", type="primary", use_container_width=True): 
                    st.session_state['inb_tab_idx'] = len(guias) - 1
                    st.rerun()

            # =========================================================
            # ETAPA 3: FECHAMENTO
            # =========================================================
            elif aba_atual == "✅ 3. Fechar Romaneio":
                st.subheader("Resumo do Recebimento")
                faltas = 0
                
                for _, row in df_ativos.iterrows():
                    if str(row['num_tag']).upper() not in st.session_state['inb_tags_bipadas']: faltas += 1
                
                for _, row in df_lotes.iterrows():
                    id_db = int(row['id'])
                    # Busca a contagem usando o ID único
                    d = st.session_state['inb_lotes'].get(id_db, {'disponivel':0, 'manutencao':0, 'sucata':0})
                    if sum(d.values()) < int(row['quantidade']): faltas += 1

                if faltas > 0: st.error(f"🚨 Foram detetados {faltas} itens/lotes com faltas. Serão enviados para a Malha Fina.")
                else: st.success("✅ Carga 100% batida! Nenhum item em falta.")

                if st.button("📥 Confirmar Entrada no Estoque", type="primary", use_container_width=True):
                    sucesso, msg, alerta = processar_recebimento_doca(origem, polo, st.session_state['inb_tags_bipadas'], st.session_state['inb_lotes'], df_esperados, usuario_atual)
                    if sucesso:
                        st.session_state['inb_passo'] = 'selecao'
                        if alerta: st.warning(msg)
                        else: st.success(msg)
                        time.sleep(2); st.rerun()
                    else: st.error(msg)

    # ==============================================================
    # ABA 3: MALHA FINA (GESTÃO DE FALTAS)
    # ==============================================================
    with tab_malha:
        st.subheader("🚨 Malha Fina de Pendências")
        st.write("Resolva os itens que não retornaram da Obra ou Transferência.")
        
        if not is_admin: st.error("🔒 Acesso restrito a Gestores.")
        else:
            df_faltas = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, localizacao, tipo_material FROM imobilizado WHERE alerta_falta = 1 AND quantidade > 0")
            if df_faltas.empty: st.success("✅ O seu estoque está limpo! Nenhuma pendência em aberto.")
            else:
                st.dataframe(df_faltas[['localizacao', 'codigo', 'descricao', 'num_tag', 'quantidade']], hide_index=True, use_container_width=True)
                st.write("---")
                
                opcoes_f = df_faltas.apply(lambda r: f"ID:{r['id']} | {r['localizacao']} | {r['codigo']} ({r['quantidade']} un)", axis=1).tolist()
                item_pendente = st.selectbox("Selecione a Pendência para Resolver:", [""] + opcoes_f)

                if item_pendente:
                    id_db = int(item_pendente.split("|")[0].replace("ID:", "").strip())
                    dados_origem = df_faltas[df_faltas['id'] == id_db].iloc[0]
                    qtd_pendente = int(dados_origem['quantidade'])

                    acao = st.radio("O que deseja fazer?", ["🔎 Material Localizado (Devolver ao Estoque)", "❌ Confirmar Extravio (Baixa Definitiva)"], horizontal=True)

                    with st.form("form_malha_fina"):
                        if "Localizado" in acao:
                            c1, c2 = st.columns(2)
                            with c1: qtd_enc = st.number_input("Quantidade Localizada", min_value=1, max_value=qtd_pendente, value=qtd_pendente)
                            with c2: destino_retorno = st.selectbox("Dar entrada em qual Polo?", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"])
                            
                            if st.form_submit_button("✅ Reintegrar ao Estoque", type="primary"):
                                processar_reintegracao_falta(id_db, qtd_enc, qtd_pendente, destino_retorno, usuario_atual)
                                st.success("Material reintegrado com sucesso!"); time.sleep(1); st.rerun()
                        else:
                            c1, c2 = st.columns([1, 2])
                            with c1: qtd_perda = st.number_input("Quantidade Perdida", min_value=1, max_value=qtd_pendente, value=qtd_pendente)
                            with c2: motivo = st.text_input("Justificativa (Nº B.O. ou Relato)")
                            
                            if st.form_submit_button("🔥 Confirmar Baixa por Extravio", type="primary"):
                                if len(motivo) < 5: st.error("Descreva a justificativa para a auditoria.")
                                else:
                                    processar_baixa_extravio(id_db, qtd_perda, qtd_pendente, dados_origem['localizacao'], motivo, usuario_atual)
                                    st.success("Extravio formalizado no sistema."); time.sleep(1); st.rerun()