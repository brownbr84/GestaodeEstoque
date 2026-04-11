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
    st.caption("WMS Inteligente: Fluxo Passo a Passo (Wizard) com Avanço Automático.")
    
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
            
            if not df_fila.empty:
                df_pendentes = df_fila[df_fila['status_clean'] == 'PENDENTE']
                if df_pendentes.empty: st.success(f"Nenhum pedido pendente para {polo_origem}.")
                else:
                    for _, req in df_pendentes.iterrows():
                        req_id = req['id_num']
                        true_id = req['true_rowid']
                        
                        is_transfer = "FILIAL" in str(req['destino_projeto']).upper()
                        icone = "🚚" if is_transfer else "👷"
                        
                        with st.container(border=True):
                            col_info, col_btn = st.columns([3, 1])
                            with col_info:
                                st.markdown(f"### {icone} REQ-{req_id:04d}")
                                st.write(f"**Destino:** {req['destino_projeto']} | **Solicitante:** {req['solicitante']}")
                            
                            with col_btn:
                                if st.button("📦 Separar", key=f"btn_sep_{true_id}", use_container_width=True, type="primary"):
                                    st.session_state['wms_req_id'] = req_id
                                    st.session_state['wms_true_id'] = true_id
                                    st.session_state['wms_destino'] = req['destino_projeto']
                                    st.session_state['wms_solicitante'] = req['solicitante']
                                    
                                    # Zera a memória de separação para o novo pedido
                                    st.session_state['wms_tags_bipadas'] = {} 
                                    st.session_state['wms_tab_idx'] = 0 # O TRUQUE DE DESACOPLAMENTO (Aba Zero)
                                    st.session_state['wms_passo'] = 'picking'
                                    st.rerun()
                                    
                            if usuario_atual == req['solicitante'] or is_admin:
                                with st.expander("❌ Cancelar"):
                                    motivo = st.text_input("Motivo:", key=f"mot_{true_id}")
                                    if st.button("Confirmar Cancelamento", key=f"cncl_{true_id}"):
                                        if len(motivo) > 5:
                                            s, m = cancelar_pedido(true_id, req_id, motivo, usuario_atual)
                                            if s:
                                                st.toast(m, icon="✅")
                                                st.rerun() 
                                        else: st.error("Justifique o cancelamento.")

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
                st.download_button(label="📥 Baixar Planilha (.csv Excel)", data=csv, file_name=f"REQ_{req_id:04d}_Picking.csv", mime='text/csv')
                st.write("---")
                
                html_table = df_print.to_html(index=False)
                html_print_view = f"""
                <html><head><style>
                    body {{ font-family: sans-serif; color: black !important; background-color: white !important; padding: 10px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; color: black !important; }}
                    th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
                    th {{ background-color: #e2e8f0; font-weight: bold; }}
                    .cabecalho {{ border: 2px solid #000; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                    .linha-assinatura {{ display: flex; justify-content: space-between; margin-top: 20px; }}
                    @media print {{ #btn-imprimir {{ display: none; }} body {{ padding: 0; }} }}
                </style></head><body>
                    <button id="btn-imprimir" onclick="window.print()" style="padding: 10px 15px; margin-bottom: 15px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">🖨️ Imprimir Folha de Separação</button>
                    <div class="cabecalho">
                        <h2 style="margin: 0 0 10px 0;">Folha de Separação: REQ-{req_id:04d}</h2>
                        <p style="margin: 5px 0;"><strong>📍 Polo / Docas:</strong> {polo}</p>
                        <p style="margin: 5px 0;"><strong>🎯 Destino da Carga:</strong> {destino}</p>
                        <p style="margin: 5px 0;"><strong>👤 Solicitante:</strong> {solicitante}</p>
                        <div class="linha-assinatura"><span><strong>Almoxarife:</strong> _________________________________________</span><span><strong>Data:</strong> ____/____/20____</span></div>
                        <p style="margin: 20px 0 5px 0;"><strong>Assinatura Recebedor/Motorista:</strong> _________________________________________</p>
                    </div>
                    {html_table}
                </body></html>
                """
                components.html(html_print_view, height=500, scrolling=True)

            st.write("---")

            df_ativos = df_itens[df_itens['exige_tag'] == True]
            df_lotes = df_itens[df_itens['exige_tag'] == False]

            guias = []
            if not df_ativos.empty: guias.append("🔫 1. Ativos (Bipar/Manual)")
            if not df_lotes.empty: guias.append("📦 2. Consumo (Lotes)")
            guias.append("✅ 3. Revisão Final")
            
            # --- O TRUQUE DE DESACOPLAMENTO PARA NÃO DAR ERRO DE WIDGET ---
            if 'wms_tab_idx' not in st.session_state:
                st.session_state['wms_tab_idx'] = 0
            
            # Garante que o índice não quebra se houver menos abas num pedido diferente
            st.session_state['wms_tab_idx'] = min(st.session_state['wms_tab_idx'], len(guias) - 1)

            # Usa apenas o INDEX, sem o parâmetro "key", assim podemos modificá-lo livremente
            aba_selecionada = st.radio("Navegação do Pedido:", options=guias, horizontal=True, index=st.session_state['wms_tab_idx'])

            # Se o utilizador clicou numa aba diferente, nós atualizamos o índice e reiniciamos
            if aba_selecionada != guias[st.session_state['wms_tab_idx']]:
                st.session_state['wms_tab_idx'] = guias.index(aba_selecionada)
                st.rerun()

            aba_atual = guias[st.session_state['wms_tab_idx']]
            st.write("---")

            # Função de gatilho inteligente
            def checar_ativos_completos():
                for _, r in df_ativos.iterrows():
                    lidas = sum(1 for i in st.session_state['wms_tags_bipadas'].values() if i['codigo'] == r['codigo'])
                    if lidas < int(r['qtd']): return False
                return True

            # -------------------------------------------------------------
            # ETAPA 1: ATIVOS (COLETOR + MANUAL)
            # -------------------------------------------------------------
            if aba_atual == "🔫 1. Ativos (Bipar/Manual)":
                col_leitor, col_btn = st.columns([3, 1])
                with col_leitor: st.subheader("1. Leitura Rápida via Coletor")
                with col_btn: 
                    if st.button("🧹 Resetar Leituras", use_container_width=True): 
                        st.session_state['wms_tags_bipadas'] = {}
                        st.rerun()

                with st.form("form_leitor_wms", clear_on_submit=True):
                    tag_lida = st.text_input("Bipe a TAG aqui e aperte Enter:", key="input_leitor")
                    if st.form_submit_button("Registrar TAG", use_container_width=True) and tag_lida:
                        tag_limpa = str(tag_lida).strip().upper()
                        df_check = carregar_dados("SELECT codigo FROM imobilizado WHERE upper(num_tag) = ? AND localizacao = ? AND status = 'Disponível'", (tag_limpa, polo))
                        
                        if df_check.empty: st.error(f"🚨 A TAG '{tag_limpa}' não foi encontrada ou não está disponível neste polo.")
                        else:
                            cod_da_tag = df_check.iloc[0]['codigo']
                            if cod_da_tag not in df_ativos['codigo'].values:
                                st.error(f"🚨 A TAG '{tag_limpa}' é do modelo {cod_da_tag}, que NÃO pertence a este pedido!")
                            else:
                                qtd_pedida = int(df_ativos[df_ativos['codigo'] == cod_da_tag]['qtd'].iloc[0])
                                lidas_deste_cod = sum(1 for info in st.session_state['wms_tags_bipadas'].values() if info['codigo'] == cod_da_tag)
                                
                                if tag_limpa in st.session_state['wms_tags_bipadas']: st.warning(f"⚠️ A TAG '{tag_limpa}' já foi separada.")
                                elif lidas_deste_cod >= qtd_pedida: st.error(f"⛔ Você já bipou todas as {qtd_pedida} unidades de {cod_da_tag}.")
                                else:
                                    st.session_state['wms_tags_bipadas'][tag_limpa] = {'codigo': cod_da_tag, 'metodo': 'Coletor'}
                                    
                                    # PULA PARA A PRÓXIMA ABA LIVRE DE ERROS
                                    if checar_ativos_completos():
                                        st.toast("🎉 Todos os ativos separados! Avançando...", icon="🚀")
                                        st.session_state['wms_tab_idx'] += 1
                                        time.sleep(0.6)
                                        st.rerun()
                                    else:
                                        st.success(f"✅ TAG {tag_limpa} separada via Coletor!")

                st.divider()
                st.subheader("2. Painel de Status & Seleção Manual")
                
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
                        tags_disp = obter_tags_disponiveis(cod, polo)
                        opcoes_manuais = [t for t in tags_disp if t not in tags_separadas]
                        
                        col_multi, col_btn_man = st.columns([3, 1])
                        with col_multi:
                            selecionados = st.multiselect(f"Faltam {faltam} un. Selecione na lista:", options=opcoes_manuais, key=f"manual_{cod}")
                        with col_btn_man:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            if st.button("Salvar Seleção", key=f"btn_man_{cod}", type="secondary", use_container_width=True):
                                if len(selecionados) > faltam: st.error(f"Selecione apenas {faltam} opções!")
                                elif len(selecionados) == 0: st.warning("Selecione ao menos uma TAG.")
                                else:
                                    for t in selecionados: st.session_state['wms_tags_bipadas'][t] = {'codigo': cod, 'metodo': 'Manual'}
                                    
                                    # PULA PARA A PRÓXIMA ABA LIVRE DE ERROS
                                    if checar_ativos_completos():
                                        st.toast("🎉 Todos os ativos separados! Avançando...", icon="🚀")
                                        st.session_state['wms_tab_idx'] += 1
                                    st.rerun() 
                    else: st.info(f"🎉 100% das unidades de {cod} foram separadas!")
                    st.write("---")

            # -------------------------------------------------------------
            # ETAPA 2: LOTES DE CONSUMO
            # -------------------------------------------------------------
            elif aba_atual == "📦 2. Consumo (Lotes)":
                st.subheader("Contagem de Insumos")
                if 'wms_lotes_separados' not in st.session_state: st.session_state['wms_lotes_separados'] = {}
                    
                for _, row in df_lotes.iterrows():
                    c1, c2 = st.columns([3, 1])
                    with c1: st.write(f"**{row['codigo']}** - {row['descricao']} (Pedido: {row['qtd']})")
                    with c2: 
                        qtd_f = st.number_input("Qtd", min_value=0, max_value=int(row['qtd']), value=int(row['qtd']), key=f"lote_{row['codigo']}")
                        st.session_state['wms_lotes_separados'][row['codigo']] = qtd_f
                    st.divider()
                
                # Botão Explicito para empurrar o utilizador para a tela final
                if st.button("💾 Confirmar Lotes e Avançar ➔", type="primary", use_container_width=True):
                    st.session_state['wms_tab_idx'] = len(guias) - 1 # Pula para a última aba garantido
                    st.rerun()

            # -------------------------------------------------------------
            # ETAPA 3: REVISÃO E FECHAMENTO
            # -------------------------------------------------------------
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

        # ==============================================================
        # PASSO 3: CONCLUSÃO
        # ==============================================================
        elif st.session_state['wms_passo'] == 'concluido':
            st.balloons()
            st.success(f"✅ Sucesso! O estoque foi deduzido e a carga despachada. Documento: {st.session_state.get('wms_doc_final')}")
            if st.button("🔄 Voltar para a Fila WMS", use_container_width=True):
                st.session_state['wms_passo'] = 'fila'
                st.rerun()

    with aba_transf:
        st.subheader("🚚 Itens em Trânsito")
        df_transito = listar_itens_em_transito(st.session_state['wms_polo'])
        if not df_transito.empty: st.dataframe(df_transito, use_container_width=True, hide_index=True)
        else: st.info("Nenhuma transferência ativa no momento.")

    with aba_baixa: st.info("Módulo em desenvolvimento.")