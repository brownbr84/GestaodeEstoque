# tracebox/views/outbound.py
import pandas as pd
import streamlit as st
import time
import streamlit.components.v1 as components
from controllers.outbound import (
    setup_tabelas_outbound, carregar_fila_pedidos, cancelar_pedido, 
    carregar_detalhes_picking, obter_tags_disponiveis, despachar_pedido_wms,
    listar_itens_em_transito
)
from database.queries import carregar_dados

def gerar_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def tela_logistica_outbound():
    setup_tabelas_outbound()

    st.title("📤 Logística Outbound (Expedição)")
    st.caption("WMS Inteligente: Fila focada na operação, Coletor de Dados e Avanço Automático.")
    
    usuario_atual = st.session_state['usuario_logado']['nome']
    perfil_atual = st.session_state['usuario_logado'].get('perfil', 'Operador').upper()
    is_admin = "ADM" in perfil_atual or "GESTOR" in perfil_atual

    if 'wms_passo' not in st.session_state:
        st.session_state['wms_passo'] = 'fila' 
        st.session_state['wms_polo'] = "Filial CTG"

    aba_projetos, aba_transf, aba_baixa = st.tabs(["👷 Fila de Separação WMS", "🚚 Radar de Transferências", "🗑️ Baixa Excepcional"])

    with aba_projetos:
        # ==============================================================
        # PASSO 1: FILA DE PEDIDOS
        # ==============================================================
        if st.session_state['wms_passo'] == 'fila':
            c_polo, _ = st.columns([1, 2])
            opcoes_polo = ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"]
            
            with c_polo:
                polo_origem = st.selectbox("📍 Polo Atual:", opcoes_polo, index=opcoes_polo.index(st.session_state['wms_polo']) if st.session_state['wms_polo'] in opcoes_polo else 0)
                st.session_state['wms_polo'] = polo_origem
            
            df_fila = carregar_fila_pedidos(polo_origem)
            
            if df_fila.empty: 
                st.success(f"Nenhum pedido registado para {polo_origem}.")
            else:
                pendentes = len(df_fila[df_fila['status_clean'] == 'PENDENTE'])
                concluidas = len(df_fila[df_fila['status_clean'] == 'CONCLUÍDA'])
                canceladas = len(df_fila[df_fila['status_clean'] == 'CANCELADA'])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total de Pedidos", len(df_fila))
                c2.metric("Pendentes", pendentes)
                c3.metric("Concluídas", concluidas)
                c4.metric("Canceladas", canceladas)
                st.divider()

                st.subheader("📋 Fila de Operação")
                filtro_exibicao = st.radio(
                    "Filtro de Visão:",
                    ["🔥 Foco nos Pendentes", "📚 Histórico (Concluídas/Canceladas)", "📋 Mostrar Tudo"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

                if "Pendentes" in filtro_exibicao:
                    df_filtrada = df_fila[df_fila['status_clean'] == 'PENDENTE'].copy()
                elif "Histórico" in filtro_exibicao:
                    df_filtrada = df_fila[df_fila['status_clean'].isin(['CONCLUÍDA', 'CANCELADA'])].copy()
                else:
                    df_filtrada = df_fila.copy()

                if df_filtrada.empty:
                    st.info("Nenhuma requisição encontrada para o filtro selecionado.")
                else:
                    st.caption("Selecione uma linha abaixo para interagir com o pedido.")
                    
                    df_exibicao = df_filtrada[['id_num', 'solicitante', 'destino_projeto', 'status', 'data_solicitacao']].copy()
                    df_exibicao.columns = ['Nº Pedido', 'Solicitante', 'Destino', 'Status', 'Data da Solicitação']
                    df_exibicao['Nº Pedido'] = df_exibicao['Nº Pedido'].apply(lambda x: f"REQ-{x:04d}")
                    
                    evento_selecao = st.dataframe(
                        df_exibicao, 
                        use_container_width=True, hide_index=True, 
                        on_select="rerun", selection_mode="single-row"
                    )
                    
                    if len(evento_selecao.selection.rows) > 0:
                        idx_linha = evento_selecao.selection.rows[0]
                        req_selecionada = df_filtrada.iloc[idx_linha]
                        
                        req_id = req_selecionada['id_num']
                        true_id = req_selecionada['true_rowid']
                        status_pedido = req_selecionada['status_clean']
                        solicitante_nome = req_selecionada['solicitante']
                        destino = req_selecionada['destino_projeto']
                        
                        st.markdown(f"### 📦 Ação para REQ-{req_id:04d}")
                        st.write(f"**Solicitante:** {solicitante_nome} | **Destino:** {destino}")
                        
                        if status_pedido == 'PENDENTE':
                            c_acao, c_cancela = st.columns([3, 1])
                            with c_acao:
                                st.info("Este pedido está a aguardar separação de materiais.")
                                if st.button("🚀 Iniciar Separação WMS", key=f"btn_sep_{true_id}", use_container_width=True, type="primary"):
                                    st.session_state['wms_req_id'] = req_id
                                    st.session_state['wms_true_id'] = true_id
                                    st.session_state['wms_destino'] = destino
                                    st.session_state['wms_solicitante'] = solicitante_nome
                                    st.session_state['wms_tags_bipadas'] = {} 
                                    st.session_state['wms_tab_idx'] = 0 
                                    st.session_state['wms_passo'] = 'picking'
                                    st.rerun()
                                    
                            with c_cancela:
                                if usuario_atual == solicitante_nome or is_admin:
                                    with st.expander("❌ Cancelar Pedido"):
                                        motivo = st.text_input("Motivo:", key=f"mot_{true_id}")
                                        if st.button("Confirmar", key=f"cncl_{true_id}", use_container_width=True):
                                            if len(motivo) > 5:
                                                s, m = cancelar_pedido(true_id, req_id, motivo, usuario_atual)
                                                if s:
                                                    st.toast(m, icon="✅")
                                                    st.rerun() 
                                            else: st.error("Justifique o cancelamento.")
                                else:
                                    st.caption("🔒 Só o Solicitante ou Admin pode cancelar.")

                        elif status_pedido == 'CONCLUÍDA':
                            st.success("✅ Este pedido já foi processado, separado e despachado com sucesso!")
                        elif status_pedido == 'CANCELADA':
                            st.error("🚫 Pedido cancelado.")
                            if 'motivo_cancelamento' in req_selecionada and pd.notna(req_selecionada['motivo_cancelamento']):
                                st.warning(f"**Motivo:** {req_selecionada['motivo_cancelamento']} (por {req_selecionada.get('cancelado_por', 'Sistema')})")

        # ==============================================================
        # PASSO 2: WIZARD DE SEPARAÇÃO E IMPRESSÃO
        # ==============================================================
        elif st.session_state['wms_passo'] == 'picking':
            req_id = st.session_state['wms_req_id']
            true_id = st.session_state['wms_true_id']
            polo = st.session_state['wms_polo']
            destino = st.session_state['wms_destino']
            solicitante = st.session_state['wms_solicitante']
            
            if st.button("← Voltar para a Fila"):
                st.session_state['wms_passo'] = 'fila'
                st.rerun()
            
            st.subheader(f"🛒 Separando REQ-{req_id:04d}")
            st.info(f"**Destino:** {destino} | **Solicitante:** {solicitante}")
            
            df_itens = carregar_detalhes_picking(req_id, polo)

            with st.expander("🖨️ Imprimir / Exportar Folha de Separação (Picking List)"):
                df_print = df_itens[['codigo', 'descricao', 'qtd']].copy()
                df_print['CONFERÊNCIA (TAG)'] = "" 
                df_print = df_print.rename(columns={'codigo': 'CÓD', 'descricao': 'DESCRIÇÃO', 'qtd': 'QTD PEDIDA'})
                csv = gerar_csv(df_print)
                st.download_button(label="📥 Baixar Planilha (.csv)", data=csv, file_name=f"REQ_{req_id:04d}_Picking.csv", mime='text/csv')
                st.write("---")
                
                df_config = carregar_dados("SELECT nome_empresa, cnpj, logo_base64 FROM configuracoes WHERE id = 1")
                nome_empresa = "TraceBox WMS"
                cnpj_empresa = ""
                logo_html = ""
                if not df_config.empty:
                    config = df_config.iloc[0]
                    nome_empresa = config['nome_empresa'] or nome_empresa
                    cnpj_empresa = f"<p style='margin: 0; font-size: 11px; color: #475569;'>CNPJ: {config['cnpj']}</p>" if config['cnpj'] else ""
                    if config['logo_base64']:
                        logo_html = f'<img src="data:image/png;base64,{config["logo_base64"]}" style="max-height: 60px;">'

                html_table = df_print.to_html(index=False)
                html_print_view = f"""
                <html><head><style>
                    body {{ font-family: 'Segoe UI', sans-serif; color: black !important; background-color: white !important; padding: 10px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; color: black !important; font-size: 13px; }}
                    th, td {{ border: 1px solid #94a3b8; padding: 8px; text-align: left; }}
                    th {{ background-color: #f1f5f9; font-weight: bold; border-bottom: 2px solid #0f172a; text-transform: uppercase; }}
                    tr:nth-child(even) {{ background-color: #f8fafc; }}
                    .cabecalho {{ border: 2px solid #0f172a; padding: 15px; margin-bottom: 20px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }}
                    .cabecalho-info {{ flex: 1; }}
                    .cabecalho-logo {{ text-align: right; margin-left: 20px; }}
                    .linha-assinatura {{ display: flex; justify-content: space-between; margin-top: 40px; text-align: center; }}
                    .linha-assinatura div {{ width: 45%; border-top: 1px solid #000; padding-top: 5px; }}
                    @media print {{ #btn-imprimir {{ display: none; }} body {{ padding: 0; }} }}
                </style></head><body>
                    <button id="btn-imprimir" onclick="window.print()" style="padding: 10px 20px; margin-bottom: 15px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">🖨️ Imprimir Folha de Separação</button>
                    
                    <div class="cabecalho">
                        <div class="cabecalho-info">
                            <h2 style="margin: 0 0 10px 0; color: #0f172a;">Folha de Separação: REQ-{req_id:04d}</h2>
                            <p style="margin: 5px 0;"><strong>📍 Polo Origem:</strong> {polo}</p>
                            <p style="margin: 5px 0;"><strong>🎯 Destino da Carga:</strong> {destino}</p>
                            <p style="margin: 5px 0;"><strong>👤 Solicitante:</strong> {solicitante}</p>
                        </div>
                        <div class="cabecalho-logo">
                            {logo_html}
                            <h3 style="margin: 5px 0 0 0; color: #0f172a;">{nome_empresa}</h3>
                            {cnpj_empresa}
                        </div>
                    </div>
                    
                    {html_table}
                    
                    <div class="linha-assinatura">
                        <div>Almoxarife Responsável<br><br>Data: ____/____/20____</div>
                        <div>Assinatura Recebedor/Motorista<br><br>Data: ____/____/20____</div>
                    </div>
                </body></html>
                """
                components.html(html_print_view, height=600, scrolling=True)

            st.write("---")

            df_ativos = df_itens[df_itens['exige_tag'] == True]
            df_lotes = df_itens[df_itens['exige_tag'] == False]

            guias = []
            if not df_ativos.empty: guias.append("🔫 1. Ativos (Scanner/Lista)")
            if not df_lotes.empty: guias.append("📦 2. Consumo (Lotes)")
            guias.append("✅ 3. Revisão Final")
            
            if 'wms_tab_idx' not in st.session_state:
                st.session_state['wms_tab_idx'] = 0
            
            st.session_state['wms_tab_idx'] = min(st.session_state['wms_tab_idx'], len(guias) - 1)
            aba_selecionada = st.radio("Navegação do Pedido:", options=guias, horizontal=True, index=st.session_state['wms_tab_idx'])

            if aba_selecionada != guias[st.session_state['wms_tab_idx']]:
                st.session_state['wms_tab_idx'] = guias.index(aba_selecionada)
                st.rerun()

            aba_atual = guias[st.session_state['wms_tab_idx']]
            st.write("---")

            def checar_ativos_completos():
                for _, r in df_ativos.iterrows():
                    lidas = sum(1 for i in st.session_state['wms_tags_bipadas'].values() if i['codigo'] == r['codigo'])
                    if lidas < int(r['qtd']): return False
                return True

            # ---------------------------------------------------------
            # ETAPA 1: ATIVOS (SCANNER E A SOLUÇÃO INTELIGENTE DO USUÁRIO)
            # ---------------------------------------------------------
            if aba_atual == "🔫 1. Ativos (Scanner/Lista)":
                col_leitor, col_btn = st.columns([3, 1])
                with col_leitor: st.subheader("📷 1. Leitura via Scanner QR Code")
                with col_btn: 
                    if st.button("🧹 Resetar Leituras", use_container_width=True): 
                        st.session_state['wms_tags_bipadas'] = {}
                        st.rerun()

                with st.form("form_leitor_wms", clear_on_submit=True):
                    tag_lida = st.text_input("Bipe a etiqueta com o Leitor Laser:", key="input_leitor", placeholder="Ex: Bipe o QR Code TraceBox aqui...")
                    submit_leitor = st.form_submit_button("Registrar Leitura (Enter)", use_container_width=True, type="primary")
                    
                    if submit_leitor and tag_lida:
                        tag_crua = str(tag_lida).strip().upper()
                        tag_limpa = tag_crua
                        
                        if "TAG:" in tag_crua:
                            try:
                                for p in tag_crua.split("|"):
                                    if p.startswith("TAG:"):
                                        tag_limpa = p.replace("TAG:", "").strip()
                                        break
                            except: pass

                        df_check = carregar_dados("SELECT codigo FROM imobilizado WHERE upper(num_tag) = ? AND localizacao = ? AND status = 'Disponível'", (tag_limpa, polo))
                        
                        if df_check.empty: st.error(f"🚨 A TAG '{tag_limpa}' não foi encontrada ou não está disponível neste polo.")
                        else:
                            cod_da_tag = df_check.iloc[0]['codigo']
                            if cod_da_tag not in df_ativos['codigo'].values:
                                st.error(f"🚨 A TAG '{tag_limpa}' é do modelo {cod_da_tag}, que NÃO pertence a este pedido!")
                            else:
                                qtd_pedida = int(df_ativos[df_ativos['codigo'] == cod_da_tag]['qtd'].iloc[0])
                                lidas_deste_cod = sum(1 for info in st.session_state['wms_tags_bipadas'].values() if info['codigo'] == cod_da_tag)
                                
                                if tag_limpa in st.session_state['wms_tags_bipadas']: st.warning(f"⚠️ A TAG '{tag_limpa}' já foi separada na caixa.")
                                elif lidas_deste_cod >= qtd_pedida: st.error(f"⛔ Você já bipou todas as {qtd_pedida} unidades de {cod_da_tag}.")
                                else:
                                    st.session_state['wms_tags_bipadas'][tag_limpa] = {'codigo': cod_da_tag, 'metodo': 'Scanner'}
                                    if checar_ativos_completos():
                                        st.toast("🎉 Todos os ativos separados! Avançando...", icon="🚀")
                                        st.session_state['wms_tab_idx'] += 1
                                        time.sleep(0.6)
                                        st.rerun()
                                    else:
                                        st.success(f"✅ TAG {tag_limpa} capturada com sucesso!")

                st.divider()
                st.subheader("2. Seleção Manual em Lista (Contingência)")
                st.caption("O sistema listará todas as ferramentas e bloqueará caso tente selecionar a mesma TAG duas vezes.")
                
                # --- 🧠 A LÓGICA DO ENGENHEIRO (Validação no clique em vez de remoção da lista) ---
                for _, row in df_ativos.iterrows():
                    cod = row['codigo']
                    qtd_p = int(row['qtd'])
                    tags_separadas = {t: info for t, info in st.session_state['wms_tags_bipadas'].items() if info['codigo'] == cod}
                    lidas = len(tags_separadas)
                    
                    st.write(f"**{cod} - {row['descricao']}**")
                    if lidas > 0: 
                        detalhes = [f"{t} ({info['metodo']})" for t, info in tags_separadas.items()]
                        st.success(f"✅ {lidas}/{qtd_p} prontas: {', '.join(detalhes)}")
                    
                    faltam = qtd_p - lidas
                    if faltam > 0:
                        # Mantemos todas as TAGs visíveis sempre, garantindo que o Streamlit não quebre
                        todas_as_tags_disponiveis = obter_tags_disponiveis(cod, polo)
                        
                        with st.container(border=True):
                            col_sel, col_btn_man = st.columns([3, 1])
                            with col_sel:
                                selecionado = st.selectbox(
                                    f"🔎 Faltam {faltam} un. Selecione a TAG:", 
                                    [""] + todas_as_tags_disponiveis,
                                    key=f"sel_manual_{cod}" # Chave estática, inquebrável
                                )
                            with col_btn_man:
                                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("➕ Adicionar TAG", key=f"btn_add_{cod}", type="secondary", use_container_width=True):
                                    if not selecionado: 
                                        st.warning("Selecione uma TAG da lista para adicionar.")
                                    elif selecionado in st.session_state['wms_tags_bipadas']:
                                        # A VALIDAÇÃO DO USUÁRIO QUE SALVOU A UX:
                                        st.error(f"🚨 Ops! A TAG {selecionado} já foi adicionada ao pacote. Escolha outra.")
                                    else:
                                        st.session_state['wms_tags_bipadas'][selecionado] = {'codigo': cod, 'metodo': 'Lista Manual'}
                                        if checar_ativos_completos():
                                            st.toast("🎉 Todos os ativos separados! Avançando...", icon="🚀")
                                            st.session_state['wms_tab_idx'] += 1
                                        st.rerun() 
                    else: st.info(f"🎉 100% das unidades de {cod} foram separadas!")
                    st.write("---")

            elif aba_atual == "📦 2. Consumo (Lotes)":
                st.subheader("Contagem de Insumos")
                if 'wms_lotes_separados' not in st.session_state: st.session_state['wms_lotes_separados'] = {}
                    
                for _, row in df_lotes.iterrows():
                    c1, c2 = st.columns([3, 1])
                    with c1: st.write(f"**{row['codigo']}** - {row['descricao']} (Pedido: {row['qtd']})")
                    with c2: 
                        qtd_f = st.number_input("Qtd a Expedir", min_value=0, max_value=int(row['qtd']), value=int(row['qtd']), key=f"lote_{row['codigo']}")
                        st.session_state['wms_lotes_separados'][row['codigo']] = qtd_f
                    st.divider()
                
                if st.button("💾 Confirmar Lotes e Avançar ➔", type="primary", use_container_width=True):
                    st.session_state['wms_tab_idx'] = len(guias) - 1
                    st.rerun()

            elif aba_atual == "✅ 3. Revisão Final":
                st.subheader("Revisão Final e Despacho")
                erros = False
                
                dict_tags_final = {}
                for tag, info in st.session_state.get('wms_tags_bipadas', {}).items():
                    cod = info['codigo']
                    if cod not in dict_tags_final: dict_tags_final[cod] = []
                    dict_tags_final[cod].append({'tag': tag, 'metodo': info['metodo']})
                
                st.write("**Resumo da Separação:**")
                for _, row in df_ativos.iterrows():
                    cod = row['codigo']
                    qtd_p = int(row['qtd'])
                    lidas = len(dict_tags_final.get(cod, []))
                    if lidas != qtd_p:
                        erros = True
                        st.error(f"⚠️ O item {cod} está incompleto ({lidas}/{qtd_p}).")
                    else: st.write(f"- {cod}: **100% OK** ({qtd_p} itens ativos)")

                for _, row in df_lotes.iterrows():
                    st.write(f"- {row['codigo']}: **100% OK** ({st.session_state.get('wms_lotes_separados', {}).get(row['codigo'], row['qtd'])} consumíveis)")

                dict_lotes_final = st.session_state.get('wms_lotes_separados', {})
                
                if not erros:
                    st.success("✅ Carga validada e pronta para emissão!")
                    if st.button("🚀 Emitir Termo e Confirmar Saída", type="primary", use_container_width=True):
                        sucesso_sep, doc, msg = despachar_pedido_wms(
                            true_id, req_id, polo, destino, 
                            dict_tags_final, dict_lotes_final, df_itens, usuario_atual
                        )
                        if sucesso_sep:
                            st.session_state['wms_doc_final'] = doc
                            st.session_state['wms_passo'] = 'concluido'
                            st.rerun() 
                        else: st.error(msg)

        elif st.session_state['wms_passo'] == 'concluido':
            st.balloons()
            st.success(f"✅ Sucesso! O estoque foi deduzido e a carga despachada. Documento: {st.session_state.get('wms_doc_final')}")
            if st.button("🔄 Voltar para a Fila WMS", use_container_width=True):
                st.session_state['wms_passo'] = 'fila'
                st.rerun()

    # ==============================================================
    # ABA RADAR E BAIXA MANTIDOS INTACTOS
    # ==============================================================
    with aba_transf:
        st.subheader("🚚 Itens em Trânsito")
        df_transito = listar_itens_em_transito(st.session_state.get('wms_polo', 'Filial CTG'))
        if not df_transito.empty: st.dataframe(df_transito, use_container_width=True, hide_index=True)
        else: st.info("Nenhuma transferência ativa no momento.")

    with aba_baixa:
        st.subheader("🗑️ Módulo de Baixa Excepcional")
        st.write("Área restrita para ajuste de Furos de Inventário, Roubo/Extravio ou Consumo Interno.")
        if not is_admin:
            st.error("🔒 **Acesso Negado:** Apenas Gestores e Administradores podem realizar Baixas Excepcionais.")
        else:
            if 'carrinho_baixa' not in st.session_state: st.session_state['carrinho_baixa'] = {}
            if 'reset_baixa' not in st.session_state: st.session_state['reset_baixa'] = 0

            st.markdown("#### 🔍 1. Buscar Item para Baixa")
            with st.container(border=True):
                c_polo, c_tipo = st.columns(2)
                with c_polo:
                    opcoes_polo_baixa = ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"]
                    idx_polo = opcoes_polo_baixa.index(st.session_state.get('wms_polo', 'Filial CTG')) if st.session_state.get('wms_polo') in opcoes_polo_baixa else 0
                    polo_baixa = st.selectbox("📍 1. Confirmar Polo:", opcoes_polo_baixa, index=idx_polo, key="polo_baixa_sel")
                
                with c_tipo:
                    tipo_baixa = st.radio("🛠️ 2. Tipo de Material:", ["Ativo (Rastreável)", "Consumo (Lote)"], horizontal=True)

                agora = int(time.time() * 1000)
                filtro_sql = "upper(tipo_material) = 'ATIVO'" if "Ativo" in tipo_baixa else "upper(tipo_material) != 'ATIVO'"
                
                query_disp = f"SELECT id, codigo, descricao, num_tag, quantidade, localizacao FROM imobilizado WHERE localizacao = '{polo_baixa}' AND status = 'Disponível' AND quantidade > 0 AND {filtro_sql} /* {agora} */"
                df_disp = carregar_dados(query_disp)

                if df_disp.empty: st.warning(f"Não há estoque de '{tipo_baixa}' disponível em {polo_baixa}.")
                else:
                    df_disp['codigo_str'] = df_disp['codigo'].fillna("").astype(str).str.strip()
                    df_disp['descricao_str'] = df_disp['descricao'].fillna("").astype(str).str.strip()
                    df_disp = df_disp[df_disp['codigo_str'] != ""] 
                    
                    desc_map = df_disp.groupby('codigo_str')['descricao_str'].apply(lambda x: max(x, key=len)).to_dict()
                    df_disp['Produto_Consolidado'] = df_disp['codigo_str'] + " - " + df_disp['codigo_str'].map(desc_map)
                    lista_produtos = sorted(df_disp['Produto_Consolidado'].unique().tolist())
                    
                    produto_selecionado = st.selectbox("📦 3. Selecione o Produto Base:", [""] + lista_produtos, key=f"prod_base_baixa_{st.session_state['reset_baixa']}")

                    if produto_selecionado:
                        df_filtrado = df_disp[df_disp['Produto_Consolidado'] == produto_selecionado].copy()
                        st.divider()
                        
                        if "Ativo" in tipo_baixa:
                            df_filtrado['tag_str'] = df_filtrado['num_tag'].fillna("").astype(str).str.strip()