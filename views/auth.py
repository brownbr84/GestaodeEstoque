# tracebox/views/auth.py
import streamlit as st
from client.api_client import TraceBoxClient

def tela_login():
    # 1. Esconde a barra lateral para foco total no login
    st.markdown(
        """
        <style>
            [data-testid="collapsedControl"] {display: none;}
            section[data-testid="stSidebar"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True
    )

    st.write("<br><br>", unsafe_allow_html=True)

    # 2. IDENTIDADE TRACEBOX (Sempre fixa no topo)
    st.markdown("<h1 style='text-align: center; color: #2563eb; margin-bottom: 0;'>💠 TraceBox</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray; margin-top: -10px;'>WMS • Autenticação Corporativa</h4>", unsafe_allow_html=True)

    # 3. IDENTIDADE DO CLIENTE (Co-branding abaixo do TraceBox)
    config = TraceBoxClient.get_config()

    if config and config.get('logo_base64'):
        st.write("<br>", unsafe_allow_html=True)
        col_logo1, col_logo2, col_logo3 = st.columns([1.2, 1, 1.2])
        with col_logo2:
            st.image(f"data:image/png;base64,{config['logo_base64']}", use_container_width=True)
            st.markdown(f"<p style='text-align: center; font-weight: bold; color: #64748b; font-size: 1.1em;'>{config['nome_empresa']}</p>", unsafe_allow_html=True)

    st.write("<br>", unsafe_allow_html=True)

    # Estado do fluxo: 'login' | 'recuperar_solicitar' | 'recuperar_confirmar'
    if 'auth_modo' not in st.session_state:
        st.session_state['auth_modo'] = 'login'

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        # ──────────────────────────────────────────
        # MODO 1: LOGIN NORMAL
        # ──────────────────────────────────────────
        if st.session_state['auth_modo'] == 'login':
            with st.form("form_login_seguro", clear_on_submit=False):
                st.write("### 🔒 Acesso Restrito")
                usuario = st.text_input("Nome de Usuário", placeholder="Digite o seu ID")
                senha = st.text_input("Senha", type="password", placeholder="••••••••")
                st.write("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")

                if submit:
                    if not usuario or not senha:
                        st.error("⚠️ Por favor, preencha o usuário e a senha.")
                    else:
                        dados_usuario = TraceBoxClient.login(usuario, senha)
                        if dados_usuario:
                            st.session_state['usuario_logado'] = dados_usuario
                            st.rerun()
                        else:
                            st.error("❌ Credenciais inválidas ou Servidor API offline.")

            st.write("<br>", unsafe_allow_html=True)
            if st.button("🔑 Esqueci minha senha", use_container_width=True):
                st.session_state['auth_modo'] = 'recuperar_solicitar'
                st.rerun()

        # ──────────────────────────────────────────
        # MODO 2: SOLICITAR RECUPERAÇÃO
        # ──────────────────────────────────────────
        elif st.session_state['auth_modo'] == 'recuperar_solicitar':
            st.write("### 🔑 Recuperação de Senha")
            st.info("Informe seu usuário e o e-mail de recuperação cadastrado. Você receberá um código de 6 dígitos.")
            with st.form("form_recuperar"):
                rec_usuario = st.text_input("Nome de Usuário", placeholder="Seu login")
                rec_email = st.text_input("E-mail de Recuperação", placeholder="email@empresa.com")
                c_vol, c_env = st.columns(2)
                with c_vol:
                    if st.form_submit_button("← Voltar"):
                        st.session_state['auth_modo'] = 'login'
                        st.rerun()
                with c_env:
                    enviar = st.form_submit_button("Enviar Código", type="primary", use_container_width=True)

            if enviar:
                if not rec_usuario or not rec_email:
                    st.error("Preencha todos os campos.")
                else:
                    ok, msg = TraceBoxClient.solicitar_recuperacao_senha(rec_usuario, rec_email)
                    if ok:
                        st.session_state['rec_usuario'] = rec_usuario
                        st.session_state['auth_modo'] = 'recuperar_confirmar'
                        st.success(msg)
                        import time; time.sleep(1); st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # ──────────────────────────────────────────
        # MODO 3: CONFIRMAR CÓDIGO E NOVA SENHA
        # ──────────────────────────────────────────
        elif st.session_state['auth_modo'] == 'recuperar_confirmar':
            rec_user = st.session_state.get('rec_usuario', '')
            st.write(f"### 🔑 Redefinir Senha — `{rec_user}`")
            st.info("Digite o código de 6 dígitos recebido no e-mail e escolha uma nova senha.")
            with st.form("form_confirmar_recuperacao"):
                codigo = st.text_input("Código de Verificação", placeholder="000000", max_chars=6)
                nova_senha = st.text_input("Nova Senha", type="password", placeholder="Mínimo 6 caracteres")
                confirmar = st.text_input("Confirmar Nova Senha", type="password", placeholder="Repita a nova senha")
                c_vol2, c_conf = st.columns(2)
                with c_vol2:
                    if st.form_submit_button("← Voltar"):
                        st.session_state['auth_modo'] = 'recuperar_solicitar'
                        st.rerun()
                with c_conf:
                    confirmar_btn = st.form_submit_button("Redefinir Senha", type="primary", use_container_width=True)

            if confirmar_btn:
                if not codigo or not nova_senha:
                    st.error("Preencha todos os campos.")
                elif nova_senha != confirmar:
                    st.error("As senhas não coincidem.")
                elif len(nova_senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                else:
                    ok, msg = TraceBoxClient.confirmar_recuperacao_senha(rec_user, codigo, nova_senha)
                    if ok:
                        st.success(f"✅ {msg} Faça o login com a nova senha.")
                        st.session_state['auth_modo'] = 'login'
                        st.session_state.pop('rec_usuario', None)
                        import time; time.sleep(2); st.rerun()
                    else:
                        st.error(f"❌ {msg}")