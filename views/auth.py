# tracebox/views/auth.py
import streamlit as st
from controllers.auth import autenticar_usuario

def tela_login():
    # Removemos a barra lateral para o utilizador não espiar o menu antes do login
    st.markdown(
        """
        <style>
            [data-testid="collapsedControl"] {display: none;}
            section[data-testid="stSidebar"] {display: none;}
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.write("<br><br><br>", unsafe_allow_html=True) # Dá um espaço no topo
    st.markdown("<h1 style='text-align: center; color: #2563eb;'>💠 TraceBox</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Autenticação Corporativa</h4>", unsafe_allow_html=True)
    st.write("<br>", unsafe_allow_html=True)

    # Centraliza o formulário no ecrã (1 coluna vazia, 1 para o form, 1 vazia)
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
                    # A Mágica do MVC: A tela pede ao Controlador para validar!
                    dados_usuario = autenticar_usuario(usuario, senha)
                    
                    if dados_usuario:
                        # Sucesso! Grava na memória e recarrega a página
                        st.session_state['usuario_logado'] = dados_usuario
                        st.rerun()
                    else:
                        st.error("❌ Credenciais inválidas. Tente novamente.")