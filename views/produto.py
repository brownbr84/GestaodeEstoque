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
    
    aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
        "📋 Saldos e Localizações", "📝 Prontuário Técnico",
        "🏷️ Gestão de Calibração", "📜 Auditoria",
        "📊 Estoque Min/Max", "🛡️ Estoque de Segurança",
    ])

    with aba1:
        col_list, col_print = st.columns([2, 1])

        with col_list:
            st.write("### 📍 Distribuição Física")
            if not inventario_fisico.empty:
                # garante coluna de endereço mesmo em respostas antigas da API
                if 'endereco_codigo' not in inventario_fisico.columns:
                    inventario_fisico['endereco_codigo'] = None
                if 'endereco_descricao' not in inventario_fisico.columns:
                    inventario_fisico['endereco_descricao'] = None

                def _fmt_end(row):
                    cod = row.get('endereco_codigo') or ''
                    desc = row.get('endereco_descricao') or ''
                    if cod:
                        return f"{cod} — {desc}" if desc else cod
                    return "—"

                inventario_fisico['Endereço'] = inventario_fisico.apply(_fmt_end, axis=1)

                df_com_tag = inventario_fisico[inventario_fisico['num_tag'].notna() & (inventario_fisico['num_tag'] != '')].copy()
                df_sem_tag = inventario_fisico[inventario_fisico['num_tag'].isna() | (inventario_fisico['num_tag'] == '')].copy()

                tabs_df = []
                if not df_sem_tag.empty:
                    # agrupa por polo + status + endereço para preservar o bin address
                    df_lotes = (
                        df_sem_tag.groupby(['localizacao', 'status', 'Endereço'], dropna=False)['quantidade']
                        .sum()
                        .reset_index()
                    )
                    df_lotes['Tipo'] = "📦 Lote"
                    df_lotes['ID/TAG'] = "N/A"
                    tabs_df.append(df_lotes[['Tipo', 'ID/TAG', 'localizacao', 'status', 'Endereço', 'quantidade']])

                if not df_com_tag.empty:
                    df_com_tag['Tipo'] = "🏷️ Item"
                    df_com_tag.rename(columns={'num_tag': 'ID/TAG'}, inplace=True)
                    tabs_df.append(df_com_tag[['Tipo', 'ID/TAG', 'localizacao', 'status', 'Endereço', 'quantidade']])

                if tabs_df:
                    df_final = pd.concat(tabs_df, ignore_index=True)
                    st.dataframe(
                        df_final.rename(columns={
                            'localizacao': 'Polo/Doca',
                            'status': 'Status',
                            'quantidade': 'Qtd',
                        }),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Endereço": st.column_config.TextColumn("📍 Endereço", width="medium"),
                        },
                    )
            else:
                st.info("Nenhum item físico deste produto em estoque no momento.")

            # ── Atribuição de endereço por item ───────────────────────────
            if is_admin_ou_gestor and not inventario_fisico.empty:
                st.divider()
                st.write("#### 🗂️ Endereçamento de Estoque")
                st.caption("Atribua um endereço físico (bin) a cada unidade. O Polo/Doca permanece inalterado.")

                filiais_no_produto = inventario_fisico['localizacao'].dropna().unique().tolist()
                locs_disponiveis = []
                for filial in filiais_no_produto:
                    locs_disponiveis += TraceBoxClient.listar_localizacoes(filial=filial, apenas_ativas=True)

                if locs_disponiveis:
                    opcoes_loc = {f"{l['codigo']} — {l['filial']} ({l['descricao']})": l for l in locs_disponiveis}
                    opcoes_loc_lista = ["(sem endereço)"] + list(opcoes_loc.keys())

                    with st.form("form_enderecamento"):
                        opcoes_item = inventario_fisico.apply(
                            lambda r: f"ID:{r['id']} | {r['num_tag'] if r['num_tag'] else 'Lote'} — {r['localizacao']}",
                            axis=1,
                        ).tolist()
                        item_end = st.selectbox("Item a endereçar:", opcoes_item, key="end_item_sel")
                        novo_end = st.selectbox("Novo endereço:", opcoes_loc_lista, key="end_loc_sel")
                        if st.form_submit_button("📌 Atribuir Endereço", type="primary"):
                            id_item = int(item_end.split("|")[0].replace("ID:", "").strip())
                            loc_id = opcoes_loc[novo_end]["id"] if novo_end != "(sem endereço)" else None
                            ok, msg = TraceBoxClient.atribuir_endereco(id_item, loc_id)
                            if ok:
                                st.success(msg)
                                import time; time.sleep(0.8); st.rerun()
                            else:
                                st.error(msg)
                else:
                    st.info("Nenhuma localização cadastrada para as filiais deste produto. Cadastre em ⚙️ Configurações → 📍 Localizações.")

        with col_print:
            st.write("### 🏷️ Impressão")
            st.caption("Gere a etiqueta QR Code de uma unidade específica.")

            if not inventario_fisico.empty:
                opcoes_print = inventario_fisico.apply(
                    lambda r: f"ID:{r['id']} | {r['num_tag'] if r['num_tag'] else 'Lote'} ({r['localizacao']})",
                    axis=1,
                ).tolist()
                item_selecionado = st.selectbox("Selecione a unidade:", [""] + opcoes_print)

                if item_selecionado:
                    id_alvo = int(item_selecionado.split("|")[0].replace("ID:", "").strip())
                    dados_item = inventario_fisico[inventario_fisico['id'] == id_alvo].iloc[0]
                    payload_etiqueta = {
                        'id': dados_item['id'], 'codigo': codigo_master, 'descricao': dados_mestre['descricao'],
                        'num_tag': dados_item['num_tag'], 'localizacao': dados_item['localizacao'],
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

    # ── ABA 5: ESTOQUE MIN/MAX ─────────────────────────────────────────────────
    with aba5:
        st.write("### 📊 Estoque Mínimo e Máximo")
        st.caption("Configure os limites de reposição por produto e filial. O sistema sinaliza quando o saldo sai da faixa ideal.")

        regras_mm = TraceBoxClient.listar_minmax(produto_codigo=codigo_master)

        if regras_mm:
            for r in regras_mm:
                alerta = r.get("alerta", "NORMAL")
                icone = {"ABAIXO_MINIMO": "🔴", "EXCESSO": "🟡", "NORMAL": "🟢"}.get(alerta, "⚪")
                filial_label = r["filial"] or "(Geral)"
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([2, 1.2, 1.2, 1.2, 0.8])
                    with c1:
                        st.markdown(f"{icone} **{filial_label}** &nbsp; _{r['unidade_medida']}_")
                        st.caption(f"Saldo atual: **{r['saldo_atual']:.0f}** | Alerta: {alerta}")
                    with c2:
                        st.metric("Mínimo", f"{r['estoque_minimo']:.0f}")
                    with c3:
                        st.metric("Máximo", f"{r['estoque_maximo']:.0f}")
                    with c4:
                        st.caption(f"Atualizado por: {r.get('updated_by', '—')}")
                        st.caption(f"{r.get('updated_at', '—')}")
                    with c5:
                        if is_admin_ou_gestor:
                            if st.button("🗑️", key=f"del_mm_{r['id']}", help="Remover regra"):
                                ok, msg = TraceBoxClient.excluir_minmax(r["id"])
                                if ok:
                                    st.toast(msg, icon="🗑️")
                                    import time; time.sleep(0.5); st.rerun()
                                else:
                                    st.error(msg)
        else:
            st.info("Nenhuma regra Min/Max cadastrada para este produto.")

        if is_admin_ou_gestor:
            st.divider()
            with st.expander("➕ Adicionar / Atualizar Regra Min/Max", expanded=not regras_mm):
                with st.form("form_minmax"):
                    c1, c2 = st.columns(2)
                    with c1:
                        mm_filial = st.text_input("Filial (deixe em branco para todas)", placeholder="Ex: Filial CTG")
                        mm_min = st.number_input("Estoque Mínimo", min_value=0.0, value=0.0, step=1.0)
                        mm_um = st.text_input("Unidade de Medida", value="UN")
                    with c2:
                        mm_max = st.number_input("Estoque Máximo", min_value=0.0, value=0.0, step=1.0)
                        mm_obs = st.text_input("Observação", placeholder="Ex: reposição semanal")
                        mm_ativo = st.toggle("Regra ativa", value=True)
                    if st.form_submit_button("💾 Salvar Regra Min/Max", type="primary", use_container_width=True):
                        ok, msg = TraceBoxClient.salvar_minmax(
                            produto_codigo=codigo_master,
                            filial=mm_filial.strip(),
                            estoque_minimo=mm_min,
                            estoque_maximo=mm_max,
                            unidade_medida=mm_um.strip() or "UN",
                            ativo=1 if mm_ativo else 0,
                            observacao=mm_obs.strip(),
                        )
                        if ok:
                            st.success(msg)
                            import time; time.sleep(0.8); st.rerun()
                        else:
                            st.error(msg)

    # ── ABA 6: ESTOQUE DE SEGURANÇA ───────────────────────────────────────────
    with aba6:
        st.write("### 🛡️ Estoque de Segurança")
        st.caption(
            "O estoque de segurança é calculado automaticamente a partir do histórico de saídas, "
            "variabilidade da demanda e lead time. Fórmula: `Z × σ × √lead_time`."
        )

        configs_seg = TraceBoxClient.listar_seguranca(produto_codigo=codigo_master)
        tipo_ctrl_seg = dados_mestre.get("tipo_controle", "")

        if configs_seg:
            for es in configs_seg:
                filial_label = es["filial"] or "(Geral)"
                ss = es.get("estoque_seguranca_calculado")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.markdown(f"**{filial_label}** — Nível de serviço: **{es['nivel_de_servico']*100:.0f}%**")
                        st.caption(
                            f"Janela: {es['janela_historica_dias']}d | "
                            f"Lead time: {es['lead_time_dias']}d | "
                            f"σ={es['desvio_padrao'] or '—'}"
                        )
                        ativo_lbl = "Lote" if es["controle_por_lote"] else ("Ativo" if es["controle_por_ativo"] else "Todos")
                        st.caption(f"Aplica-se a: {ativo_lbl}")
                    with c2:
                        if ss is not None:
                            st.metric("Estoque de Segurança", f"{ss:.2f} {tipo_ctrl_seg or 'un.'}")
                        else:
                            st.info("Não calculado ainda.")
                        if is_admin_ou_gestor:
                            if st.button("🔄 Calcular agora", key=f"calc_seg_{es['id']}"):
                                ok, msg, val = TraceBoxClient.calcular_seguranca(es["id"])
                                if ok:
                                    st.success(f"{msg}")
                                    import time; time.sleep(0.8); st.rerun()
                                else:
                                    st.warning(msg)
                    with c3:
                        if is_admin_ou_gestor:
                            if st.button("🗑️", key=f"del_seg_{es['id']}", help="Remover configuração"):
                                ok, msg = TraceBoxClient.excluir_seguranca(es["id"])
                                if ok:
                                    st.toast(msg, icon="🗑️")
                                    import time; time.sleep(0.5); st.rerun()
                                else:
                                    st.error(msg)
        else:
            st.info("Nenhuma configuração de estoque de segurança para este produto.")

        if is_admin_ou_gestor:
            st.divider()
            with st.expander("➕ Configurar Estoque de Segurança", expanded=not configs_seg):
                with st.form("form_seguranca"):
                    c1, c2 = st.columns(2)
                    with c1:
                        seg_filial = st.text_input("Filial (deixe em branco para todas)", placeholder="Ex: Filial CTG")
                        seg_janela = st.number_input("Janela Histórica (dias)", min_value=7, value=90, step=7)
                        seg_nivel  = st.select_slider(
                            "Nível de Serviço",
                            options=[0.80, 0.85, 0.90, 0.95, 0.99],
                            value=0.95,
                            format_func=lambda v: f"{v*100:.0f}%",
                        )
                    with c2:
                        seg_lead   = st.number_input("Lead Time (dias)", min_value=1, value=7, step=1)
                        seg_lote   = st.toggle("Prioridade: Lote", value=tipo_ctrl_seg == "LOTE",
                                               help="Marque para aplicar apenas a itens controlados por lote")
                        seg_ativo_ctrl = st.toggle("Prioridade: Ativo", value=tipo_ctrl_seg == "TAG",
                                                   help="Marque para aplicar apenas a itens controlados por TAG")
                        seg_hab    = st.toggle("Habilitado", value=True)
                    if st.form_submit_button("💾 Salvar Configuração", type="primary", use_container_width=True):
                        ok, msg, es_id = TraceBoxClient.salvar_seguranca(
                            produto_codigo=codigo_master,
                            filial=seg_filial.strip(),
                            controle_por_lote=1 if seg_lote else 0,
                            controle_por_ativo=1 if seg_ativo_ctrl else 0,
                            ativo=1 if seg_hab else 0,
                            janela_historica_dias=int(seg_janela),
                            lead_time_dias=int(seg_lead),
                            nivel_de_servico=seg_nivel,
                        )
                        if ok:
                            st.success(msg)
                            if es_id:
                                ok2, msg2, val = TraceBoxClient.calcular_seguranca(es_id)
                                if ok2:
                                    st.info(f"Calculado automaticamente: {msg2}")
                            import time; time.sleep(0.8); st.rerun()
                        else:
                            st.error(msg)