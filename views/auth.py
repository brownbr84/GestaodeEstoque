# tracebox/views/auth.py
import streamlit as st
from database.queries import carregar_dados
from controllers.auth import autenticar_usuario

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
    df_config = carregar_dados("SELECT nome_empresa, logo_base64 FROM configuracoes WHERE id = 1")
    
    if not df_config.empty and df_config.iloc[0]['logo_base64']:
        config = df_config.iloc[0]
        st.write("<br>", unsafe_allow_html=True)
        col_logo1, col_logo2, col_logo3 = st.columns([1.2, 1, 1.2])
        
        with col_logo2:
            # Tudo que está dentro do 'with' precisa de 4 espaços de recuo
            st.image(f"data:image/png;base64,{config['logo_base64']}", use_container_width=True)
            st.markdown(f"<p style='text-align: center; font-weight: bold; color: #64748b; font-size: 1.1em;'>{config['nome_empresa']}</p>", unsafe_allow_html=True)
            
    st.write("<br>", unsafe_allow_html=True)

    # 4. FORMULÁRIO DE LOGIN CENTRALIZADO
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        with st.form("form_login_seguro", clear_on_submit=False):
            st.write("### 🔒 Acesso Restrito")
            
            # Campos de entrada
            usuario = st.text_input("Nome de Usuário", placeholder="Digite o seu ID")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            
            st.write("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")

            if submit:
                if not usuario or not senha:
                    st.error("⚠️ Por favor, preencha o usuário e a senha.")
                else:
                    # Validação via Controlador
                    dados_usuario = autenticar_usuario(usuario, senha)
                    
                    if dados_usuario:
                        # Sucesso: Grava na sessão e recarrega para abrir o Menu Lateral
                        st.session_state['usuario_logado'] = dados_usuario
                        st.rerun()
                    else:
                        st.error("❌ Credenciais inválidas. Tente novamente.")