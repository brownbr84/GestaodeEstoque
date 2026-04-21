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

    abas = ["🏢 Identidade Visual", "📋 Parâmetros Dinâmicos", "📧 Automação de E-mails"]
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
    # ABA 4: GESTÃO DE USUÁRIOS (somente Admin)
    # ==========================================
    if eh_admin and len(tabs) > 3:
        with tabs[3]:
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
