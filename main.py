# tracebox/main.py
import streamlit as st
import pandas as pd

# 1. Configuração global da página (DEVE ser a primeira linha do Streamlit)
st.set_page_config(
    page_title="TraceBox | Torre de Controle", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

from database.conexao_orm import engine, Base, SessionLocal
from database.models import Imobilizado, Movimentacao, Requisicao, RequisicaoItem, LogAuditoria, ManutencaoOrdem, Configuracoes, Usuario, Categoria, Fornecedor
from repositories.configuracoes_repository import ConfiguracoesRepository
from client.api_client import TraceBoxClient

def obter_identidade_visual():
    """Busca nome e logo da empresa via API para aplicar o branding."""
    try:
        config = TraceBoxClient.get_config()
        if config:
            return config
    except Exception as e:
        pass
    return None

# =====================================================================
# 2. MOTOR DE IGNIÇÃO
# =====================================================================

@st.cache_resource
def inicializar_e_popular_banco():
    """Motor de Ignição PROD: Cria o BD via SQLAlchemy ORM."""
    Base.metadata.create_all(bind=engine)

    # Migração incremental: garante colunas adicionadas após a criação inicial do banco
    import sqlalchemy as _sa
    with engine.connect() as _conn:
        inspector = _sa.inspect(engine)
        cols_usuarios = [c["name"] for c in inspector.get_columns("usuarios")]
        if "email" not in cols_usuarios:
            _conn.execute(_sa.text("ALTER TABLE usuarios ADD COLUMN email TEXT"))
            _conn.commit()

        cols_config = [c["name"] for c in inspector.get_columns("configuracoes")]
        if "smtp_host" not in cols_config:
            _conn.execute(_sa.text("ALTER TABLE configuracoes ADD COLUMN smtp_host TEXT"))
            _conn.commit()
        if "smtp_porta" not in cols_config:
            _conn.execute(_sa.text("ALTER TABLE configuracoes ADD COLUMN smtp_porta INTEGER"))
            _conn.commit()

    try:
        with SessionLocal() as db:
            repo = ConfiguracoesRepository()
            config = repo.get_config(db)
            if not config:
                novo_config = Configuracoes(nome_empresa='TraceBox WMS', cnpj='', logo_base64='')
                db.add(novo_config)
                db.commit()
    except:
        pass

    return True

# ==========================================
# 3. FUNÇÃO PRINCIPAL E ROTEAMENTO
# ==========================================
def main():
    inicializar_e_popular_banco()

    # 1. VALIDAÇÃO DE SESSÃO COM IMPORTAÇÃO DINÂMICA
    if st.session_state.get('usuario_logado') is None:
        from views.auth import tela_login
        tela_login()
        return 
    
    # 2. BUSCA DA IDENTIDADE VISUAL E USUÁRIO
    id_visual = obter_identidade_visual()
    usuario = st.session_state['usuario_logado']
    
   # ==========================================
    # 3. CONSTRUÇÃO DO MENU LATERAL (CO-BRANDING)
    # ==========================================
    
    st.sidebar.markdown("<h2 style='color: #2563eb; text-align: center; margin-bottom:0;'>💠 TraceBox</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='text-align: center; color: gray; font-size: 0.8em; margin-top: -5px;'>WMS Enterprise Solution</p>", unsafe_allow_html=True)

    if id_visual is not None and id_visual['logo_base64']:
        st.sidebar.write("<br>", unsafe_allow_html=True)
        st.sidebar.image(f"data:image/png;base64,{id_visual['logo_base64']}", use_container_width=True)
        st.sidebar.markdown(f"""
            <div style='text-align: center; padding-top: 5px; border-bottom: 1px solid #4b5563; padding-bottom: 10px; margin-bottom: 5px;'>
                <span style='font-size: 0.85em; color: #9ca3af; font-weight: bold;'>{id_visual['nome_empresa'].upper()}</span>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.divider()

    st.sidebar.markdown(f"<p style='text-align: center; color: gray; font-size: 0.9em; margin-top: 10px;'>👤 {usuario['nome'].upper()} [{usuario['perfil']}]</p>", unsafe_allow_html=True)
    st.sidebar.divider()
    
    opcoes_menu = [
        "📈 Torre de Controle", 
        "📦 Consulta de Matriz Física", 
        "➕ Cadastrar Novo Ativo",          
        "📋 Inventário Cíclico",
        "🛠️ Manutenção",
        "📝 Fazer Requisição (Solicitante)",
        "📤 Logística Outbound (Saída)",   
        "📥 Logística Inbound (Entrada)",
        "🏷️ Etiquetas QR Code",
        "🖨️ Central de Relatórios",
        "🛡️ Auditoria e Compliance",
        "⚙️ Configurações do Sistema"
    ]
    
    menu = st.sidebar.radio("Navegação", opcoes_menu)

    st.sidebar.divider()
    if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # 5. ROTEAMENTO PARA AS VIEWS (AS IMPORTAÇÕES FICAM AQUI DENTRO AGORA)
    # ==========================================
    if menu == "📈 Torre de Controle":
        st.session_state['produto_selecionado'] = None 
        from views.torre_controle import tela_torre_controle
        tela_torre_controle()
        
    elif menu == "📦 Consulta de Matriz Física":
        from views.matriz_fisica import tela_matriz_fisica
        from views.produto import tela_produto
        if st.session_state.get('produto_selecionado'):
            tela_produto() 
        else:
            tela_matriz_fisica() 
            
    elif menu == "➕ Cadastrar Novo Ativo":
        st.session_state['produto_selecionado'] = None
        from views.cadastro import tela_cadastro_produtos
        tela_cadastro_produtos()
        
    elif menu == "📋 Inventário Cíclico":
        st.session_state['produto_selecionado'] = None
        from views.inventario import tela_inventario_ciclico
        tela_inventario_ciclico() 
        
    elif menu == "🛠️ Manutenção":
        st.session_state['produto_selecionado'] = None
        from views.manutencao import tela_gestao_manutencao
        tela_gestao_manutencao()
        
    elif menu == "📝 Fazer Requisição (Solicitante)":
        st.session_state['produto_selecionado'] = None
        from views.requisicao import tela_fazer_requisicao
        tela_fazer_requisicao()
        
    elif menu == "📤 Logística Outbound (Saída)":
        st.session_state['produto_selecionado'] = None
        from views.outbound import tela_logistica_outbound
        tela_logistica_outbound()
        
    elif menu == "📥 Logística Inbound (Entrada)":
        st.session_state['produto_selecionado'] = None
        from views.inbound import tela_logistica_inbound
        tela_logistica_inbound()
        
    elif menu == "🏷️ Etiquetas QR Code":
        st.session_state['produto_selecionado'] = None
        from views.etiquetas import tela_gerador_etiquetas
        tela_gerador_etiquetas()
        
    elif menu == "🖨️ Central de Relatórios":
        st.session_state['produto_selecionado'] = None
        from views.relatorios import tela_central_relatorios
        tela_central_relatorios()
        
    elif menu == "⚙️ Configurações do Sistema":
        st.session_state['produto_selecionado'] = None
        from views.configuracoes import tela_configuracoes_globais
        tela_configuracoes_globais()
    
    elif menu == "🛡️ Auditoria e Compliance":
        st.session_state['produto_selecionado'] = None
        from views.auditoria import tela_auditoria
        tela_auditoria()

if __name__ == "__main__":
    main()