# traceback/views/configuracoes.py
import streamlit as st
import base64
from client.api_client import TraceBoxClient

def tela_configuracoes_globais():
    st.title("⚙️ Configurações Globais do Sistema")
    st.caption("Central de gestão de parâmetros, identidade visual e regras de negócio do TraceBox.")

    config_atual = TraceBoxClient.get_config()
    if not config_atual:
        st.error("Erro ao carregar configurações globais. O servidor API pode estar offline.")
        return

    perfil_logado = st.session_state.get("usuario_logado", {}).get("perfil", "")
    eh_admin = perfil_logado == "Admin"

    abas = ["🏢 Identidade Visual", "📋 Parâmetros Dinâmicos", "📧 Automação de E-mails",
            "🏭 Empresa Emitente", "🧾 Módulo Fiscal", "📍 Localizações"]
    if eh_admin:
        abas.append("👥 Gestão de Usuários")

    tabs = st.tabs(abas)

    # ==========================================
    # ABA 1: IDENTIDADE VISUAL
    # ==========================================
    with tabs[0]:
        st.write("### Dados da Empresa nos Relatórios e Etiquetas")
        with st.form("form_identidade"):
            c1, c2 = st.columns(2)
            with c1:
                novo_nome = st.text_input("Nome da Empresa / Razão Social", value=config_atual.get('nome_empresa', ''))
            with c2:
                novo_cnpj = st.text_input("CNPJ / Documento Base", value=config_atual.get('cnpj', ''))
            st.write("#### Upload de Logotipo")
            st.caption("Envie uma imagem PNG ou JPG (Fundo transparente recomendado). Ela aparecerá em PDFs e Etiquetas.")
            arquivo_logo = st.file_uploader("Selecionar nova imagem", type=["png", "jpg", "jpeg"])
            if config_atual.get('logo_base64'):
                st.write("Logotipo Atual:")
                st.markdown(f'<img src="data:image/png;base64,{config_atual["logo_base64"]}" height="60">', unsafe_allow_html=True)
            if st.form_submit_button("💾 Salvar Identidade Visual", type="primary"):
                logo_b64 = config_atual.get('logo_base64', '')
                if arquivo_logo is not None:
                    logo_b64 = base64.b64encode(arquivo_logo.getvalue()).decode()
                if TraceBoxClient.update_config(nome_empresa=novo_nome, cnpj=novo_cnpj, logo_base64=logo_b64):
                    st.toast("✅ Configurações salvas!", icon="💾")
                    import time; time.sleep(1); st.rerun()
                else:
                    st.error("❌ Falha ao salvar configurações na API.")

    # ==========================================
    # ABA 2: PARÂMETROS DINÂMICOS
    # ==========================================
    with tabs[1]:
        st.write("### Parâmetros Dinâmicos das Telas de Cadastro")
        st.caption("Adicione ou remova opções que aparecerão nos formulários de todo o sistema.")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Categorias de Ativos/Produtos**")
            cat_list = config_atual.get('categorias_produto', [])
            if not isinstance(cat_list, list): cat_list = []
            df_cat = st.data_editor({"Categorias": cat_list}, num_rows="dynamic", key="edit_cat")
            st.write("**Tipos de Controle**")
            ctrl_list = config_atual.get('tipos_controle', [])
            if not isinstance(ctrl_list, list): ctrl_list = []
            df_ctrl = st.data_editor({"Tipos": ctrl_list}, num_rows="dynamic", key="edit_ctrl")
        with c2:
            st.write("**Tipos de Material**")
            mat_list = config_atual.get('tipos_material', [])
            if not isinstance(mat_list, list): mat_list = []
            df_mat = st.data_editor({"Materiais": mat_list}, num_rows="dynamic", key="edit_mat")
        if st.button("💾 Salvar Parâmetros", type="primary", use_container_width=True):
            novas_cat = df_cat['Categorias'].dropna().tolist()
            novas_ctrl = df_ctrl['Tipos'].dropna().tolist()
            novos_mat = df_mat['Materiais'].dropna().tolist()
            if TraceBoxClient.update_config(categorias_produto=novas_cat, tipos_controle=novas_ctrl, tipos_material=novos_mat):
                st.toast("Parâmetros atualizados!", icon="✅")
                import time; time.sleep(1); st.rerun()
            else:
                st.error("Falha ao salvar parâmetros.")

    # ==========================================
    # ABA 3: EMAILS E AUTOMAÇÃO
    # ==========================================
    with tabs[2]:
        st.write("### 📧 Servidor de Disparo de E-mails")
        st.caption("Configure as credenciais SMTP para envio de e-mails automáticos (recuperação de senha, alertas, OS).")
        with st.form("form_email"):
            c_email, c_senha = st.columns(2)
            with c_email:
                email_smtp = st.text_input("E-mail Remetente", value=config_atual.get('email_smtp', ''),
                                           placeholder="remetente@empresa.com")
            with c_senha:
                senha_smtp = st.text_input("Senha de Aplicativo (App Password)", value="", type="password",
                                           placeholder="Deixe em branco para não alterar")
            c_host, c_porta = st.columns([2, 1])
            with c_host:
                smtp_host = st.text_input("Servidor SMTP",
                                          value=config_atual.get('smtp_host', '') or 'smtp.gmail.com',
                                          placeholder="Ex: smtp.gmail.com  /  smtp.office365.com")
            with c_porta:
                smtp_porta = st.number_input("Porta", value=int(config_atual.get('smtp_porta') or 587),
                                             min_value=1, max_value=65535,
                                             help="587 = TLS (recomendado)  |  465 = SSL  |  25 = sem criptografia")
            st.info("💡 Gmail: use 'Senha de App' (não a senha da conta). Outlook/Office365: smtp.office365.com porta 587.")
            st.divider()
            st.write("### Destinatários de Ordens de Serviço")
            lista_emails_str = "\n".join(config_atual.get('emails_destinatarios', [])) if isinstance(config_atual.get('emails_destinatarios', []), list) else ""
            destinatarios = st.text_area("Lista de E-mails (um por linha)", value=lista_emails_str, height=120)
            if st.form_submit_button("💾 Salvar Configurações de E-mail", type="primary"):
                lista_limpa = [e.strip() for e in destinatarios.split("\n") if e.strip()]
                payload = {"email_smtp": email_smtp, "emails_destinatarios": lista_limpa,
                           "smtp_host": smtp_host, "smtp_porta": smtp_porta}
                if senha_smtp:
                    payload["senha_smtp"] = senha_smtp
                if TraceBoxClient.update_config(**payload):
                    st.toast("Configurações de e-mail salvas!", icon="📧")
                    import time; time.sleep(1); st.rerun()
                else:
                    st.error("Erro ao salvar configurações de e-mail.")

    # ==========================================
    # ABA 4: EMPRESA EMITENTE
    # ==========================================
    with tabs[3]:
        st.write("### 🏭 Dados da Empresa Emitente (NF-e)")
        st.caption("Informações fiscais do emitente. Aparecem nas NF-e como dados do remetente.")

        emitente = TraceBoxClient.get_emitente() or {}

        with st.form("form_emitente"):
            c1, c2 = st.columns(2)
            with c1:
                emit_cnpj    = st.text_input("CNPJ *", value=emitente.get("cnpj", ""),
                                             placeholder="00.000.000/0001-00")
                emit_razao   = st.text_input("Razão Social *", value=emitente.get("razao_social", ""))
                emit_fantasia = st.text_input("Nome Fantasia", value=emitente.get("nome_fantasia", ""))
                emit_ie      = st.text_input("Inscrição Estadual (IE)", value=emitente.get("ie", ""))
                emit_im      = st.text_input("Inscrição Municipal (IM)", value=emitente.get("im", ""))
                emit_cnae    = st.text_input("CNAE Principal", value=emitente.get("cnae_principal", ""),
                                             help="Código CNAE da atividade principal (sem pontos ou hífen)")
            with c2:
                regimes = {
                    "SIMPLES":       "Simples Nacional",
                    "REGIME_NORMAL": "Regime Normal",
                    "MEI":           "MEI",
                }
                regime_atual = emitente.get("regime_tributario", "REGIME_NORMAL")
                regime_idx   = list(regimes.keys()).index(regime_atual) if regime_atual in regimes else 1
                emit_regime  = st.selectbox("Regime Tributário", list(regimes.keys()),
                                            format_func=lambda k: regimes[k], index=regime_idx)
                emit_cep     = st.text_input("CEP", value=emitente.get("cep", ""), placeholder="00000-000")
                emit_logr    = st.text_input("Logradouro", value=emitente.get("logradouro", ""))
                emit_num     = st.text_input("Número", value=emitente.get("numero", ""))
                emit_compl   = st.text_input("Complemento", value=emitente.get("complemento", ""))

            c3, c4, c5 = st.columns([2, 1, 2])
            with c3:
                emit_bairro  = st.text_input("Bairro", value=emitente.get("bairro", ""))
            with c4:
                ufs = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
                       "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]
                uf_atual = emitente.get("uf", "SP")
                uf_idx   = ufs.index(uf_atual) if uf_atual in ufs else ufs.index("SP")
                emit_uf  = st.selectbox("UF", ufs, index=uf_idx)
            with c5:
                emit_mun = st.text_input("Município", value=emitente.get("municipio", ""))

            c6, c7 = st.columns(2)
            with c6:
                emit_tel   = st.text_input("Telefone", value=emitente.get("telefone", ""))
            with c7:
                emit_email = st.text_input("E-mail", value=emitente.get("email", ""))

            st.divider()
            col_save, col_sinc = st.columns(2)
            with col_save:
                salvo = st.form_submit_button("💾 Salvar Emitente", type="primary", use_container_width=True)
            with col_sinc:
                sincronizar = st.form_submit_button("🔄 Sincronizar via CNPJ (BrasilAPI)",
                                                    use_container_width=True)

        if salvo:
            ok, msg = TraceBoxClient.atualizar_emitente({
                "cnpj": emit_cnpj, "razao_social": emit_razao, "nome_fantasia": emit_fantasia,
                "ie": emit_ie, "im": emit_im, "cnae_principal": emit_cnae,
                "regime_tributario": emit_regime, "cep": emit_cep,
                "logradouro": emit_logr, "numero": emit_num, "complemento": emit_compl,
                "bairro": emit_bairro, "uf": emit_uf, "municipio": emit_mun,
                "telefone": emit_tel, "email": emit_email,
            })
            if ok:
                st.toast("✅ Emitente salvo!", icon="🏭")
                import time; time.sleep(1); st.rerun()
            else:
                st.error(f"❌ {msg}")

        if sincronizar:
            if not emit_cnpj.strip():
                st.error("Informe o CNPJ antes de sincronizar.")
            else:
                with st.spinner("Consultando BrasilAPI…"):
                    ok, msg, dados_api = TraceBoxClient.sincronizar_emitente()
                if ok:
                    st.toast("✅ Dados sincronizados!", icon="🔄")
                    import time; time.sleep(1); st.rerun()
                else:
                    st.error(f"❌ {msg}")

        status_sinc = emitente.get("status_sinc", "PENDENTE")
        sinc_icons  = {"PENDENTE": "⚪", "SINCRONIZADO": "✅", "ERRO": "❌"}
        st.caption(
            f"Status sincronização: {sinc_icons.get(status_sinc, '⬜')} {status_sinc} "
            + (f"(última: {emitente['data_sincronizacao'][:16]})" if emitente.get("data_sincronizacao") else "")
        )

    # ==========================================
    # ABA 5: MÓDULO FISCAL
    # ==========================================
    with tabs[4]:
        st.write("### 🧾 Configurações do Módulo Fiscal")
        st.caption("Habilite e configure a emissão de NF-e. A emissão real exige Certificado Digital A1.")

        st.warning(
            "**Estado atual da integração SEFAZ:** Não operacional por design. "
            "O sistema gerencia rascunhos internamente. "
            "A transmissão real à SEFAZ requer: Certificado A1 (.pfx) + PyNFe ou serviço homologado.",
            icon="🔒"
        )

        with st.form("form_fiscal"):
            c1, c2 = st.columns(2)
            with c1:
                fiscal_hab = st.toggle(
                    "Habilitar Módulo Fiscal",
                    value=bool(config_atual.get("fiscal_habilitado", False)),
                    help="Habilita a tela de NF-e no menu. A emissão real ainda depende do Certificado A1."
                )
                fiscal_serie = st.text_input(
                    "Série da NF-e",
                    value=config_atual.get("fiscal_serie") or "1",
                    help="Série padrão: 1. Série 9xx geralmente usada em homologação."
                )
            with c2:
                fiscal_amb = st.selectbox(
                    "Ambiente",
                    ["homologacao", "producao"],
                    index=0 if (config_atual.get("fiscal_ambiente") or "homologacao") == "homologacao" else 1,
                    help="Homologação: sem validade fiscal. Produção: NF-e com valor legal — requer certificado."
                )
                fiscal_num = st.number_input(
                    "Numeração Atual da NF",
                    value=int(config_atual.get("fiscal_numeracao_atual") or 1),
                    min_value=1,
                    help="Próximo número a ser usado na emissão."
                )

            st.info(
                "**Certificado A1 e API SEFAZ:** Não configuráveis nesta versão. "
                "A emissão via WebService SEFAZ será habilitada em versão futura. "
                "Consulte o suporte TraceBox para viabilidade de integração.",
                icon="ℹ️"
            )

            if st.form_submit_button("💾 Salvar Configurações Fiscais", type="primary"):
                ok = TraceBoxClient.update_config(
                    fiscal_habilitado=fiscal_hab,
                    fiscal_ambiente=fiscal_amb,
                    fiscal_serie=fiscal_serie,
                    fiscal_numeracao_atual=fiscal_num,
                )
                if ok:
                    st.toast("Configurações fiscais salvas!", icon="🧾")
                    import time; time.sleep(1); st.rerun()
                else:
                    st.error("Falha ao salvar configurações fiscais.")

        st.divider()
        st.write("#### Parametrização de CFOPs")
        st.caption(
            "Configure os CFOPs disponíveis para Saída e Entrada. "
            "Estes valores populam o seletor de CFOP nas abas de emissão."
        )

        cfop_lista = TraceBoxClient.listar_cfop_configs()

        if cfop_lista:
            import pandas as pd
            df_cfop = pd.DataFrame([{
                "ID": r["id"],
                "Operação": r["tipo_operacao"],
                "Direção": r["direcao"],
                "CFOP Interno": r["cfop_interno"],
                "CFOP Interestadual": r["cfop_interestadual"],
                "Natureza Padrão": r["natureza_padrao"] or "—",
            } for r in cfop_lista])
            st.dataframe(df_cfop, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhum CFOP configurado. Rode a aplicação para aplicar os seeds padrão.")

        if eh_admin:
            with st.expander("➕ Adicionar / ✏️ Editar CFOP"):
                cfop_ids = {f"#{r['id']} — {r['direcao']} {r['tipo_operacao']}": r for r in cfop_lista}
                modo = st.radio("Ação", ["Novo", "Editar existente"], horizontal=True, key="cfop_modo")

                if modo == "Editar existente" and cfop_ids:
                    sel_label = st.selectbox("Selecione", list(cfop_ids.keys()), key="cfop_sel")
                    sel = cfop_ids[sel_label]
                    cfg_id = sel["id"]
                    default_tipo = sel["tipo_operacao"]
                    default_dir  = sel["direcao"]
                    default_ci   = sel["cfop_interno"]
                    default_ce   = sel["cfop_interestadual"]
                    default_nat  = sel["natureza_padrao"] or ""
                else:
                    cfg_id = None
                    default_tipo = ""
                    default_dir  = "SAIDA"
                    default_ci   = ""
                    default_ce   = ""
                    default_nat  = ""

                with st.form("form_cfop_config"):
                    c1, c2 = st.columns(2)
                    with c1:
                        f_tipo = st.text_input("Tipo de Operação", value=default_tipo,
                                               placeholder="Ex: Remessa Conserto")
                        f_dir  = st.selectbox("Direção", ["SAIDA", "ENTRADA"],
                                              index=0 if default_dir == "SAIDA" else 1)
                        f_nat  = st.text_input("Natureza Padrão", value=default_nat,
                                               placeholder="Ex: Remessa para conserto")
                    with c2:
                        f_ci = st.text_input("CFOP Interno", value=default_ci,
                                             placeholder="Ex: 5915")
                        f_ce = st.text_input("CFOP Interestadual", value=default_ce,
                                             placeholder="Ex: 6915")

                    col_salvar, col_del = st.columns(2)
                    with col_salvar:
                        if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                            if not f_tipo or not f_ci or not f_ce:
                                st.error("Preencha Tipo de Operação, CFOP Interno e CFOP Interestadual.")
                            elif cfg_id:
                                ok2, msg2 = TraceBoxClient.atualizar_cfop_config(
                                    cfg_id, f_tipo, "", f_dir, f_ci, f_ce, f_nat)
                                st.toast(msg2, icon="✅" if ok2 else "❌")
                                if ok2:
                                    import time; time.sleep(1); st.rerun()
                            else:
                                ok2, msg2 = TraceBoxClient.criar_cfop_config(
                                    f_tipo, "", f_dir, f_ci, f_ce, f_nat)
                                st.toast(msg2, icon="✅" if ok2 else "❌")
                                if ok2:
                                    import time; time.sleep(1); st.rerun()
                    with col_del:
                        if cfg_id and st.form_submit_button("🗑️ Remover", use_container_width=True):
                            ok3, msg3 = TraceBoxClient.deletar_cfop_config(cfg_id)
                            st.toast(msg3, icon="✅" if ok3 else "❌")
                            if ok3:
                                import time; time.sleep(1); st.rerun()

    # ==========================================
    # ABA 6: LOCALIZAÇÕES (Bin Addresses)
    # ==========================================
    with tabs[5]:
        st.write("### 📍 Cadastro Mestre de Localizações")
        st.caption("Defina os endereços físicos (bins) por filial. Esses endereços serão usados no Inbound e na Consulta de Matriz Física.")

        locs = TraceBoxClient.listar_localizacoes(apenas_ativas=False)
        import pandas as pd

        filiais_disponiveis = sorted({l["filial"] for l in locs}) if locs else []

        col_filtro, col_nova = st.columns([2, 2])
        with col_filtro:
            filial_filtro = st.selectbox("Filtrar por filial", ["(todas)"] + filiais_disponiveis, key="loc_filial_filtro")

        locs_exibir = locs if filial_filtro == "(todas)" else [l for l in locs if l["filial"] == filial_filtro]

        if locs_exibir:
            df_locs = pd.DataFrame([{
                "ID": l["id"], "Filial": l["filial"], "Código": l["codigo"],
                "Descrição": l["descricao"], "Zona": l["zona"],
                "Status": l["status"],
            } for l in locs_exibir])
            st.dataframe(df_locs, hide_index=True, use_container_width=True,
                         column_config={"ID": st.column_config.NumberColumn(width="small")})
        else:
            st.info("Nenhuma localização cadastrada para a filial selecionada.")

        st.divider()

        if eh_admin or perfil_logado == "Gestor":
            col_add, col_edit = st.columns(2)

            with col_add:
                with st.expander("➕ Nova Localização", expanded=not locs_exibir):
                    with st.form("form_nova_loc"):
                        c1, c2 = st.columns(2)
                        with c1:
                            nova_filial = st.text_input("Filial *", placeholder="Ex: Filial CTG")
                            novo_codigo = st.text_input("Código *", placeholder="Ex: A-01-N2-P04")
                        with c2:
                            nova_desc   = st.text_input("Descrição", placeholder="Ex: Corredor A, Nível 2")
                            nova_zona   = st.text_input("Zona", placeholder="Ex: Almoxarifado")
                        novo_doca = st.text_input("Polo/Doca (referência legada)", placeholder="Ex: Filial CTG")
                        if st.form_submit_button("✅ Criar Localização", type="primary", use_container_width=True):
                            if not nova_filial.strip() or not novo_codigo.strip():
                                st.error("Filial e Código são obrigatórios.")
                            else:
                                ok, msg = TraceBoxClient.criar_localizacao(
                                    nova_filial.strip(), novo_codigo.strip(),
                                    nova_desc.strip(), nova_zona.strip(), novo_doca.strip()
                                )
                                if ok:
                                    st.success(msg)
                                    import time; time.sleep(0.8); st.rerun()
                                else:
                                    st.error(msg)

            with col_edit:
                if locs_exibir:
                    with st.expander("✏️ Editar / Inativar", expanded=False):
                        opcoes_loc = {f"#{l['id']} — {l['filial']} / {l['codigo']}": l for l in locs_exibir}
                        sel_label = st.selectbox("Selecione a localização", list(opcoes_loc.keys()), key="loc_sel_edit")
                        sel = opcoes_loc[sel_label]
                        with st.form("form_edit_loc"):
                            c1, c2 = st.columns(2)
                            with c1:
                                e_desc = st.text_input("Descrição", value=sel["descricao"])
                                e_zona = st.text_input("Zona", value=sel["zona"])
                            with c2:
                                e_doca   = st.text_input("Polo/Doca", value=sel.get("doca_polo", ""))
                                e_status = st.selectbox("Status", ["ATIVO", "INATIVO"],
                                                        index=0 if sel["status"] == "ATIVO" else 1)
                            c_salvar, c_del = st.columns(2)
                            with c_salvar:
                                if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                                    ok, msg = TraceBoxClient.atualizar_localizacao(
                                        sel["id"], e_desc, e_zona, e_doca, e_status
                                    )
                                    if ok:
                                        st.toast(msg, icon="✅")
                                        import time; time.sleep(0.8); st.rerun()
                                    else:
                                        st.error(msg)
                            with c_del:
                                if st.form_submit_button("🗑️ Inativar", use_container_width=True):
                                    ok, msg = TraceBoxClient.inativar_localizacao(sel["id"])
                                    if ok:
                                        st.toast(msg, icon="🗑️")
                                        import time; time.sleep(0.8); st.rerun()
                                    else:
                                        st.error(msg)
        else:
            st.info("Somente Administradores e Gestores podem criar ou editar localizações.")

    # ==========================================
    # ABA 7: GESTÃO DE USUÁRIOS (somente Admin)
    # ==========================================
    if eh_admin and len(tabs) > 6:
        with tabs[6]:
            st.write("### 👥 Gestão de Usuários do Sistema")
            st.caption("Crie, altere senhas e remova usuários. Somente Administradores têm acesso a esta aba.")

            # ── Criar novo usuário ──────────────────────────
            with st.expander("➕ Criar Novo Usuário", expanded=True):
                with st.form("form_criar_usuario"):
                    c1, c2 = st.columns(2)
                    with c1:
                        novo_nome_u = st.text_input("Nome Completo", placeholder="Ex: João Silva")
                        novo_login  = st.text_input("Login (username)", placeholder="Ex: joao.silva")
                        novo_email_u = st.text_input("E-mail de Recuperação", placeholder="Ex: joao@empresa.com")
                    with c2:
                        novo_perfil = st.selectbox("Nível de Acesso", ["Operador", "Gestor", "Admin"],
                                                   help="Operador: acesso básico | Gestor: aprova processos | Admin: acesso total")
                        nova_senha  = st.text_input("Senha Inicial", type="password", placeholder="Mínimo 6 caracteres")

                    st.caption("⚠️ O usuário deverá alterar a senha no primeiro acesso.")

                    if st.form_submit_button("✅ Criar Usuário", type="primary", use_container_width=True):
                        if not novo_nome_u or not novo_login or not nova_senha:
                            st.error("Preencha todos os campos obrigatórios.")
                        elif len(nova_senha) < 6:
                            st.error("A senha deve ter pelo menos 6 caracteres.")
                        else:
                            ok, msg = TraceBoxClient.criar_usuario(novo_nome_u, novo_login, nova_senha, novo_perfil, novo_email_u)
                            if ok:
                                st.success(f"✅ {msg}")
                                import time; time.sleep(1); st.rerun()
                            else:
                                st.error(f"❌ {msg}")

            st.divider()

            # ── Lista de usuários existentes ────────────────
            st.write("#### 👤 Usuários Cadastrados")
            usuarios = TraceBoxClient.listar_usuarios()

            if not usuarios:
                st.info("Nenhum usuário encontrado ou erro ao carregar.")
            else:
                usuario_logado = st.session_state.get("usuario_logado", {}).get("usuario", "")
                for u in usuarios:
                    icone = {"Admin": "🔴", "Gestor": "🟡", "Operador": "🟢"}.get(u.get("perfil"), "⚪")
                    email_u = u.get("email") or ""
                    with st.container(border=True):
                        col_info, col_senha, col_email, col_del = st.columns([2.5, 1.2, 1.5, 0.8])

                        with col_info:
                            st.markdown(f"{icone} **{u.get('nome')}** &nbsp;&nbsp; `{u.get('usuario')}` &nbsp;&nbsp; *{u.get('perfil')}*")
                            if email_u:
                                st.caption(f"📧 {email_u}")

                        with col_senha:
                            with st.popover("🔑 Senha"):
                                with st.form(f"form_senha_{u.get('usuario')}"):
                                    nova = st.text_input("Nova Senha", type="password")
                                    if st.form_submit_button("Confirmar", type="primary", use_container_width=True):
                                        if len(nova) < 6:
                                            st.error("Mínimo 6 caracteres")
                                        else:
                                            ok, msg = TraceBoxClient.alterar_senha_usuario(u.get('usuario'), nova)
                                            if ok:
                                                st.success(msg)
                                                import time; time.sleep(1); st.rerun()
                                            else:
                                                st.error(msg)

                        with col_email:
                            with st.popover("📧 E-mail"):
                                with st.form(f"form_email_{u.get('usuario')}"):
                                    novo_email = st.text_input("E-mail de Recuperação", value=email_u)
                                    if st.form_submit_button("Salvar", type="primary", use_container_width=True):
                                        ok_e, msg_e = TraceBoxClient.atualizar_email_usuario(u.get('usuario'), novo_email)
                                        if ok_e:
                                            st.success(msg_e)
                                            import time; time.sleep(1); st.rerun()
                                        else:
                                            st.error(msg_e)

                        with col_del:
                            if u.get("usuario") != usuario_logado:
                                if st.button("🗑️", key=f"del_{u.get('usuario')}", help=f"Excluir {u.get('usuario')}"):
                                    ok, msg = TraceBoxClient.excluir_usuario(u.get("usuario"))
                                    if ok:
                                        st.toast(f"✅ {msg}", icon="🗑️")
                                        import time; time.sleep(1); st.rerun()
                                    else:
                                        st.error(msg)
                            else:
                                st.caption("(você)")
