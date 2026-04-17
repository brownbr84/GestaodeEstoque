# tracebox/views/inbound.py
import streamlit as st
import time
import pandas as pd
import streamlit.components.v1 as components
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
    # ABA 1: ENTRADA DE COMPRAS E IMPRESSÃO DE ETIQUETAS
    # ==============================================================
    with tab_compras:
        if 'carrinho_compras' not in st.session_state:
            st.session_state['carrinho_compras'] = []
        if 'compra_sucesso' not in st.session_state:
            st.session_state['compra_sucesso'] = False
            st.session_state['itens_para_impressao'] = []
        if 'mostrar_pdf_etiquetas' not in st.session_state:
            st.session_state['mostrar_pdf_etiquetas'] = False

        if st.session_state['compra_sucesso']:
            # ---------------------------------------------------------
            # TELA DE SUCESSO E CENTRAL DE IMPRESSÃO INLINE
            # ---------------------------------------------------------
            st.balloons()
            st.success("✅ **Nota Fiscal processada com sucesso no Estoque!**")
            
            st.markdown("### 🖨️ Central de Impressão de Etiquetas")
            st.caption("Selecione os itens recém-chegados para gerar e imprimir os QR Codes antes de armazenar na prateleira.")

            if st.session_state['itens_para_impressao']:
                df_print = pd.DataFrame(st.session_state['itens_para_impressao'])
                # Adiciona coluna de checkbox (True por defeito)
                df_print.insert(0, "Imprimir", True)

                # Tabela editável inteligente
                df_editado = st.data_editor(
                    df_print,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Imprimir": st.column_config.CheckboxColumn("🖨️ Selecionar", default=True),
                        "codigo": st.column_config.TextColumn("Cód. Produto", disabled=True),
                        "descricao": st.column_config.TextColumn("Descrição", disabled=True),
                        "tag": st.column_config.TextColumn("TAG / Lote", disabled=True),
                        "tipo": st.column_config.TextColumn("Classificação", disabled=True)
                    }
                )

                c_print, c_nova = st.columns(2)
                with c_print:
                    if st.button("🖨️ Gerar Etiquetas Selecionadas", type="primary", use_container_width=True):
                        itens_selecionados = df_editado[df_editado["Imprimir"] == True]
                        if itens_selecionados.empty:
                            st.warning("⚠️ Selecione pelo menos um item para imprimir.")
                        else:
                            st.session_state['mostrar_pdf_etiquetas'] = True
                            st.session_state['df_selecionados_final'] = itens_selecionados
                            st.rerun()

                with c_nova:
                    if st.button("🔄 Concluir e Lançar Nova NF", use_container_width=True):
                        st.session_state['compra_sucesso'] = False
                        st.session_state['carrinho_compras'] = []
                        st.session_state['itens_para_impressao'] = []
                        st.session_state['mostrar_pdf_etiquetas'] = False
                        st.rerun()

                # --- MOTOR DE RENDERIZAÇÃO DO QR CODE ---
                if st.session_state['mostrar_pdf_etiquetas']:
                    st.divider()
                    st.subheader("Visualização de Impressão")
                    
                    df_sel = st.session_state['df_selecionados_final']
                    
                    html_etiquetas = """
                    <html><head><style>
                        body { font-family: 'Segoe UI', sans-serif; background: #f8fafc; padding: 20px;}
                        .etiqueta { background: white; border: 2px dashed #94a3b8; width: 340px; height: 160px; padding: 15px; margin: 10px; display: inline-block; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); page-break-inside: avoid;}
                        .qr { float: left; width: 110px; height: 110px; margin-right: 15px;}
                        .info { float: left; width: 200px; }
                        .title { font-size: 14px; font-weight: bold; color: #2563eb; margin: 0 0 5px 0; text-transform: uppercase;}
                        .tag { font-size: 22px; font-weight: 900; color: #0f172a; margin: 0 0 5px 0; }
                        .desc { font-size: 11px; color: #475569; margin: 0; line-height: 1.3;}
                        .footer { font-size: 9px; color: #94a3b8; margin-top: 10px; border-top: 1px solid #e2e8f0; padding-top: 5px;}
                        @media print { 
                            body { background: white; padding: 0; }
                            button { display: none; } 
                            .etiqueta { border: 1px solid #000; box-shadow: none; margin: 5px; } 
                        }
                    </style></head><body>
                    <button onclick="window.print()" style="padding: 10px 20px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; margin-bottom: 20px;">🖨️ Imprimir Todas</button>
                    <br>
                    """
                    
                    for _, row in df_sel.iterrows():
                        # A string oficial do TraceBox (compatível com os nossos scanners!)
                        qr_data = f"COD:{row['codigo']}|TAG:{row['tag']}"
                        # Usa a API pública e segura do QRServer para renderização rápida sem bibliotecas pesadas
                        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={qr_data}"
                        
                        html_etiquetas += f"""
                        <div class="etiqueta">
                            <img class="qr" src="{qr_url}" alt="QR">
                            <div class="info">
                                <p class="title">TraceBox WMS</p>
                                <p class="tag">{row['tag']}</p>
                                <p class="desc"><b>CÓD: {row['codigo']}</b><br>{row['descricao'][:45]}...</p>
                                <p class="footer">{row['tipo'].upper()} • WMS Enterprise</p>
                            </div>
                        </div>
                        """
                    html_etiquetas += "</body></html>"
                    
                    components.html(html_etiquetas, height=500, scrolling=True)

            else:
                st.info("Nenhuma etiqueta necessária para esta entrada.")
                if st.button("🔄 Lançar Nova NF", use_container_width=True):
                    st.session_state['compra_sucesso'] = False
                    st.session_state['carrinho_compras'] = []
                    st.rerun()

        else:
            # ---------------------------------------------------------
            # TELA DE LANÇAMENTO DA NF (CARRINHO MÚLTIPLO)
            # ---------------------------------------------------------
            st.subheader("Entrada de Estoque via Nota Fiscal")
            st.caption("Monte o carrinho com todos os produtos da NF antes de processar a entrada.")
            
            # Cabeçalho da Nota
            with st.container(border=True):
                st.write("📄 **Dados do Documento Fiscal**")
                c1, c2 = st.columns([2, 1])
                with c1: 
                    nf_input = st.text_input("Número da NF / DI *", placeholder="Ex: NF-12345")
                with c2:
                    opcoes_polo = ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"]
                    idx_polo = opcoes_polo.index(st.session_state['inb_polo']) if st.session_state['inb_polo'] in opcoes_polo else 0
                    polo_destino = st.selectbox("Polo Recebedor da Carga:", opcoes_polo, index=idx_polo)

            # Injetar o Tipo_Material direto na string para não ter de ir à base de dados a cada clique!
            df_catalogo = carregar_dados("SELECT DISTINCT codigo, descricao, tipo_material FROM imobilizado")
            lista_catalogo = df_catalogo.apply(lambda r: f"{r['codigo']} - {r['descricao']} [{r['tipo_material']}]", axis=1).tolist() if not df_catalogo.empty else []
            
            col_form, col_cart = st.columns([1.2, 1])
            
            with col_form:
                with st.form("form_add_item_nf", clear_on_submit=True):
                    st.write("📦 **Adicionar Produto à Nota**")
                    produto_selecionado = st.selectbox("Selecione o Produto (Master Data):", [""] + lista_catalogo)
                    
                    c_val, c_qtd = st.columns(2)
                    with c_val: valor_unit = st.number_input("Valor Unit. (R$)", min_value=0.0, format="%.2f")
                    with c_qtd: quantidade = st.number_input("Qtd Recebida", min_value=1, value=1)
                    
                    st.info("🤖 **Automação:** Ativos ganham TAGs sequenciais exclusivas. Lotes recebem etiqueta de caixa.")
                    
                    if st.form_submit_button("➕ Adicionar Produto ao Lote", use_container_width=True):
                        if not produto_selecionado:
                            st.error("Selecione um produto para adicionar.")
                        else:
                            cod_puro = produto_selecionado.split(" - ")[0]
                            desc_pura = produto_selecionado.split(" - ")[1].split(" [")[0]
                            tipo_mat = produto_selecionado.split(" [")[1].replace("]", "")
                            
                            # Verifica duplicidade no carrinho e soma a QTD se for o mesmo valor
                            ja_existe = False
                            for i in st.session_state['carrinho_compras']:
                                if i['codigo'] == cod_puro and i['valor'] == valor_unit:
                                    i['qtd'] += quantidade
                                    ja_existe = True
                                    break
                            
                            if not ja_existe:
                                st.session_state['carrinho_compras'].append({
                                    'codigo': cod_puro, 'descricao': desc_pura, 'valor': valor_unit, 'qtd': quantidade, 'tipo': tipo_mat
                                })
                            st.rerun()

            with col_cart:
                st.write("🛒 **Itens na Nota Fiscal**")
                if not st.session_state['carrinho_compras']:
                    st.info("A nota fiscal está vazia.")
                else:
                    df_cart = pd.DataFrame(st.session_state['carrinho_compras'])
                    df_cart['Total'] = df_cart['valor'] * df_cart['qtd']
                    
                    st.dataframe(
                        df_cart[['codigo', 'qtd', 'Total']].rename(columns={'codigo':'Cód.', 'qtd':'Qtd', 'Total':'R$ Total'}), 
                        hide_index=True, use_container_width=True
                    )
                    
                    valor_total_nf = df_cart['Total'].sum()
                    st.markdown(f"<h4 style='text-align: right; color: #2563eb;'>Total NF: R$ {valor_total_nf:,.2f}</h4>", unsafe_allow_html=True)
                    
                    c_limpar, c_fechar = st.columns([1, 2])
                    with c_limpar:
                        if st.button("🗑️ Esvaziar"):
                            st.session_state['carrinho_compras'] = []
                            st.rerun()
                    with c_fechar:
                        if st.button("💾 Processar Nota", type="primary", use_container_width=True):
                            if not nf_input.strip():
                                st.error("⚠️ Preencha o Número da NF no topo da tela!")
                            else:
                                erro_ocorrido = False
                                todas_tags_geradas = []
                                itens_para_print = []
                                
                                with st.spinner("A guardar os ativos e a gerar o rastreio (TAGs)..."):
                                    for item in st.session_state['carrinho_compras']:
                                        sucesso, msg, tags_novas = processar_entrada_compra(
                                            item['codigo'], polo_destino, nf_input, 
                                            item['valor'], item['qtd'], usuario_atual
                                        )
                                        if sucesso:
                                            if tags_novas:
                                                # São Ativos, guarda as TAGs criadas
                                                for t in tags_novas:
                                                    itens_para_print.append({'codigo': t['codigo'], 'descricao': t['descricao'], 'tag': t['tag'], 'tipo': 'Ativo'})
                                            else:
                                                # É Consumo/Lote
                                                itens_para_print.append({'codigo': item['codigo'], 'descricao': item['descricao'], 'tag': 'LOTE / CAIXA', 'tipo': 'Consumo'})
                                        else:
                                            st.error(f"Falha ao inserir {item['codigo']}: {msg}")
                                            erro_ocorrido = True
                                
                                if not erro_ocorrido:
                                    st.session_state['itens_para_impressao'] = itens_para_print
                                    st.session_state['compra_sucesso'] = True
                                    st.rerun()

    # ==============================================================
    # ABA 2: DOCA DE DESCARGA (INTACTA E BLINDADA)
    # ==============================================================
    with tab_doca:
        if 'inb_passo' not in st.session_state: st.session_state['inb_passo'] = 'selecao'

        if st.session_state['inb_passo'] == 'selecao':
            st.subheader("1. Identificação da Carga")
            c_polo, c_origem = st.columns(2)
            with c_polo:
                opcoes_polo_doca = ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"]
                idx_polo_doca = opcoes_polo_doca.index(st.session_state['inb_polo']) if st.session_state['inb_polo'] in opcoes_polo_doca else 0
                polo_atual = st.selectbox("📍 Polo Atual:", opcoes_polo_doca, index=idx_polo_doca, key="doca_polo")
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
            if not df_ativos.empty: guias.append("🔫 1. Ativos (Scanner/Lista)")
            if not df_lotes.empty: guias.append("📦 2. Lotes (Triagem)")
            guias.append("✅ 3. Fechar Romaneio")
            
            st.session_state['inb_tab_idx'] = min(st.session_state.get('inb_tab_idx', 0), len(guias) - 1)
            aba_selecionada = st.radio("Navegação do Recebimento:", options=guias, horizontal=True, index=st.session_state['inb_tab_idx'])
            if aba_selecionada != guias[st.session_state['inb_tab_idx']]:
                st.session_state['inb_tab_idx'] = guias.index(aba_selecionada); st.rerun()

            aba_atual = guias[st.session_state['inb_tab_idx']]
            st.write("---")

            def checar_ativos_inb_completos():
                return len(st.session_state['inb_tags_bipadas']) == len(df_ativos)

            if aba_atual == "🔫 1. Ativos (Scanner/Lista)":
                col_leitor, col_btn = st.columns([3, 1])
                with col_leitor: st.subheader("📷 1. Leitura via Scanner QR Code")
                with col_btn: 
                    if st.button("🧹 Resetar Leituras", use_container_width=True): 
                        st.session_state['inb_tags_bipadas'] = {}
                        st.rerun()

                with st.form("form_inb_leitor", clear_on_submit=True):
                    tag_lida = st.text_input("Bipe o QR Code ou digite a TAG manualmente:", key="inb_leitor", placeholder="Ex: TAG-1001 ou bipar etiqueta...")
                    if st.form_submit_button("Registrar TAG", use_container_width=True, type="primary") and tag_lida:
                        
                        tag_crua = str(tag_lida).strip().upper()
                        tag_limpa = tag_crua
                        
                        if "TAG:" in tag_crua:
                            try:
                                for p in tag_crua.split("|"):
                                    if p.startswith("TAG:"):
                                        tag_limpa = p.replace("TAG:", "").strip()
                                        break
                            except: pass

                        if tag_limpa not in df_ativos['num_tag'].str.upper().values: 
                            st.error(f"🚨 A TAG '{tag_limpa}' NÃO pertence a esta carga!")
                        elif tag_limpa in st.session_state['inb_tags_bipadas']:
                            st.warning(f"⚠️ A TAG '{tag_limpa}' já foi recebida.")
                        else:
                            cod_da_tag = df_ativos[df_ativos['num_tag'].str.upper() == tag_limpa].iloc[0]['codigo']
                            st.session_state['inb_tags_bipadas'][tag_limpa] = {'codigo': cod_da_tag, 'status_qualidade': 'Disponível', 'metodo': 'Scanner'}
                            
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
                        with st.container(border=True):
                            col_sel, col_btn_man = st.columns([3, 1])
                            with col_sel:
                                selecionado = st.selectbox(f"Faltam {faltam} un. Selecione as que chegaram:", [""] + tags_esperadas, key=f"manual_{cod}")
                            with col_btn_man:
                                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("➕ Adicionar TAG", key=f"btn_man_{cod}", type="secondary", use_container_width=True):
                                    if not selecionado: 
                                        st.warning("Selecione uma TAG da lista.")
                                    elif selecionado in st.session_state['inb_tags_bipadas']:
                                        st.error(f"A TAG {selecionado} já foi recebida!")
                                    elif selecionado not in opcoes_manuais:
                                        st.error(f"A TAG {selecionado} não é esperada para este produto.")
                                    else:
                                        st.session_state['inb_tags_bipadas'][selecionado] = {'codigo': cod, 'status_qualidade': 'Disponível', 'metodo': 'Manual'}
                                        if checar_ativos_inb_completos():
                                            st.toast("🎉 Todos os ativos recebidos! Avançando...", icon="🚀")
                                            st.session_state['inb_tab_idx'] += 1
                                        st.rerun() 
                    else: st.info(f"🎉 100% das unidades de {cod} foram recebidas!")
                    st.write("---")

                if st.button("💾 Confirmar Ativos Lidos e Avançar ➔", type="primary", use_container_width=True):
                    st.session_state['inb_tab_idx'] += 1
                    st.rerun()

            elif aba_atual == "📦 2. Lotes (Triagem)":
                st.subheader("Triagem de Qualidade de Consumíveis")
                if 'inb_lotes' not in st.session_state: st.session_state['inb_lotes'] = {}

                for _, row in df_lotes.iterrows():
                    id_db = int(row['id'])
                    cod, qtd_esperada = row['codigo'], int(row['quantidade'])
                    
                    st.markdown(f"**{cod} - {row['descricao']}** (Esperado: {qtd_esperada} un | Lote ID: {id_db})")
                    c1, c2, c3 = st.columns(3)
                    with c1: q_disp = st.number_input("✅ Bons", min_value=0, max_value=qtd_esperada, value=qtd_esperada, key=f"d_{id_db}")
                    with c2: q_man = st.number_input("🔧 Quebrados", min_value=0, max_value=qtd_esperada, value=0, key=f"m_{id_db}")
                    with c3: q_suc = st.number_input("🗑️ Lixo", min_value=0, max_value=qtd_esperada, value=0, key=f"s_{id_db}")
                    
                    st.session_state['inb_lotes'][id_db] = {'disponivel': q_disp, 'manutencao': q_man, 'sucata': q_suc}
                    
                    total = q_disp + q_man + q_suc
                    if total > qtd_esperada: st.error("🚨 Mais itens do que o esperado!")
                    elif total < qtd_esperada: st.warning(f"⚠️ Faltam {qtd_esperada - total} un. (Cairão na Malha Fina)")
                    st.divider()

                if st.button("Ir para Fechamento ➔", type="primary", use_container_width=True): 
                    st.session_state['inb_tab_idx'] = len(guias) - 1
                    st.rerun()

            elif aba_atual == "✅ 3. Fechar Romaneio":
                st.subheader("Resumo do Recebimento")
                faltas = 0
                
                for _, row in df_ativos.iterrows():
                    if str(row['num_tag']).upper() not in st.session_state['inb_tags_bipadas']: faltas += 1
                
                for _, row in df_lotes.iterrows():
                    id_db = int(row['id'])
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
    # ABA 3: MALHA FINA (GESTÃO DE FALTAS - INTACTA)
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