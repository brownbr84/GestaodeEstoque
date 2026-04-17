# tracebox/main.py
import streamlit as st
import pandas as pd
from database.queries import executar_query, carregar_dados

def obter_identidade_visual():
    """Busca nome e logo da empresa no banco para aplicar o branding."""
    from database.queries import carregar_dados
    try:
        df = carregar_dados("SELECT nome_empresa, logo_base64 FROM configuracoes WHERE id = 1")
        if not df.empty:
            return df.iloc[0]
    except:
        pass
    return None

# 1. Configuração global da página (DEVE ser a primeira linha do Streamlit)
st.set_page_config(
    page_title="TraceBox | Torre de Controle", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. IMPORTAÇÃO DAS TELAS (VIEWS)
# ==========================================
from views.auth import tela_login
from views.inventario import tela_inventario_ciclico
from views.inbound import tela_logistica_inbound
from views.matriz_fisica import tela_matriz_fisica
from views.torre_controle import tela_torre_controle
from views.cadastro import tela_cadastro_produtos
from views.produto import tela_produto
from views.manutencao import tela_gestao_manutencao
from views.outbound import tela_logistica_outbound
from views.requisicao import tela_fazer_requisicao
from views.relatorios import tela_central_relatorios # <-- Importação do Relatório aqui!

# =====================================================================
# 3. MOTOR DE IGNIÇÃO
# =====================================================================

@st.cache_resource 
def inicializar_e_popular_banco():
    """Motor de Ignição PROD: Cria o BD e garante que as colunas existam, mas SEM DADOS FALSOS."""
    
    # 1. Cria Tabela Imobilizado
    executar_query("""
        CREATE TABLE IF NOT EXISTS imobilizado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT, descricao TEXT, marca TEXT, modelo TEXT,
            num_tag TEXT, quantidade INTEGER, status TEXT DEFAULT 'Disponível',
            localizacao TEXT, categoria TEXT, valor_unitario REAL,
            data_aquisicao DATE, dimensoes TEXT, capacidade TEXT,
            ultima_manutencao DATE, proxima_manutencao DATE, detalhes TEXT,
            imagem TEXT, tipo_material TEXT DEFAULT 'Ativo', alerta_falta INTEGER DEFAULT 0
        )
    """)

    # 2. Cria Tabela Movimentações
    executar_query("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ferramenta_id INTEGER, 
            tipo TEXT, 
            responsavel TEXT,
            destino_projeto TEXT, 
            documento TEXT, 
            data_movimentacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Cria Tabela Requisições
    executar_query("""
        CREATE TABLE IF NOT EXISTS requisicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitante TEXT, polo_origem TEXT, destino_projeto TEXT,
            status TEXT DEFAULT 'Pendente', data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            motivo_cancelamento TEXT, cancelado_por TEXT
        )
    """)
    
    # 4. Cria Tabela de Manutenção
    executar_query("""
        CREATE TABLE IF NOT EXISTS manutencao_ordens (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ferramenta_id INTEGER, codigo_ferramenta TEXT,
            data_entrada DATETIME, data_saida DATETIME, motivo_falha TEXT, diagnostico TEXT,
            custo_reparo REAL DEFAULT 0.0, mecanico_responsavel TEXT, status_ordem TEXT DEFAULT 'Aberta',
            solicitante TEXT, empresa_reparo TEXT, num_orcamento TEXT,
            FOREIGN KEY(ferramenta_id) REFERENCES imobilizado(id)
        )
    """)

    # 5. 🎨 CRIA A TABELA DE CONFIGURAÇÕES (WHITE-LABEL)
    executar_query("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_empresa TEXT,
            cnpj TEXT,
            logo_base64 TEXT
        )
    """)

    # Se a tabela de configurações estiver vazia, cria a linha base
    df_config = carregar_dados("SELECT COUNT(*) as total FROM configuracoes")
    if not df_config.empty and df_config.iloc[0]['total'] == 0:
        executar_query("INSERT INTO configuracoes (nome_empresa, cnpj, logo_base64) VALUES ('TraceBox WMS', '', '')")

    # Atualizações de Schema (Migrações Automáticas Seguras)
    try:
        df_mov = carregar_dados("PRAGMA table_info(movimentacoes)")
        cols_mov = df_mov['name'].str.lower().tolist()
        if 'data_movimentacao' not in cols_mov:
            executar_query("ALTER TABLE movimentacoes ADD COLUMN data_movimentacao DATETIME DEFAULT CURRENT_TIMESTAMP")
    except: pass

    return True

# ==========================================
# 4. FUNÇÃO PRINCIPAL E ROTEAMENTO
# ==========================================
def main():
    inicializar_e_popular_banco()

    # 1. VALIDAÇÃO DE SESSÃO
    if st.session_state.get('usuario_logado') is None:
        tela_login()
        return 
    
    # 2. BUSCA DA IDENTIDADE VISUAL E USUÁRIO
    id_visual = obter_identidade_visual()
    usuario = st.session_state['usuario_logado']
    
   # ==========================================
    # 3. CONSTRUÇÃO DO MENU LATERAL (CO-BRANDING)
    # ==========================================
    
    # 3.1 TOPO: MARCA DO SISTEMA (TRACEBOX - SEMPRE PRESENTE)
    st.sidebar.markdown("<h2 style='color: #2563eb; text-align: center; margin-bottom:0;'>💠 TraceBox</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='text-align: center; color: gray; font-size: 0.8em; margin-top: -5px;'>WMS Enterprise Solution</p>", unsafe_allow_html=True)

    # 3.2 MEIO: MARCA DO CLIENTE (DINÂMICO)
    if id_visual is not None and id_visual['logo_base64']:
        st.sidebar.write("<br>", unsafe_allow_html=True)
        # Exibe o logo do cliente
        st.sidebar.image(f"data:image/png;base64,{id_visual['logo_base64']}", use_container_width=True)
        # Exibe o nome do cliente com uma linha separadora elegante
        st.sidebar.markdown(f"""
            <div style='text-align: center; padding-top: 5px; border-bottom: 1px solid #4b5563; padding-bottom: 10px; margin-bottom: 5px;'>
                <span style='font-size: 0.85em; color: #9ca3af; font-weight: bold;'>{id_visual['nome_empresa'].upper()}</span>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Se não tiver logo de cliente, põe apenas um divisor para manter a elegância
        st.sidebar.divider()

    # 3.3 Identificação do usuário logado
    st.sidebar.markdown(f"<p style='text-align: center; color: gray; font-size: 0.9em; margin-top: 10px;'>👤 {usuario['nome'].upper()} [{usuario['perfil']}]</p>", unsafe_allow_html=True)
    st.sidebar.divider()
    
    # 4. OPÇÕES DO MENU
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
        "⚙️ Configurações do Sistema"
    ]
    
    menu = st.sidebar.radio("Navegação", opcoes_menu)

    st.sidebar.divider()
    if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # 5. ROTEAMENTO PARA AS VIEWS
    # ==========================================
    if menu == "📈 Torre de Controle":
        st.session_state['produto_selecionado'] = None 
        tela_torre_controle()
    elif menu == "📦 Consulta de Matriz Física":
        if st.session_state.get('produto_selecionado'):
            tela_produto() 
        else:
            tela_matriz_fisica() 
    elif menu == "➕ Cadastrar Novo Ativo":
        st.session_state['produto_selecionado'] = None
        tela_cadastro_produtos()
    elif menu == "📋 Inventário Cíclico":
        st.session_state['produto_selecionado'] = None
        tela_inventario_ciclico() 
    elif menu == "🛠️ Manutenção":
        st.session_state['produto_selecionado'] = None
        tela_gestao_manutencao()
    elif menu == "📝 Fazer Requisição (Solicitante)":
        st.session_state['produto_selecionado'] = None
        tela_fazer_requisicao()
    elif menu == "📤 Logística Outbound (Saída)":
        st.session_state['produto_selecionado'] = None
        tela_logistica_outbound()
    elif menu == "📥 Logística Inbound (Entrada)":
        st.session_state['produto_selecionado'] = None
        tela_logistica_inbound()
    elif menu == "🏷️ Etiquetas QR Code":
        st.session_state['produto_selecionado'] = None
        from views.etiquetas import tela_gerador_etiquetas
        tela_gerador_etiquetas()
    elif menu == "🖨️ Central de Relatórios":
        st.session_state['produto_selecionado'] = None
        tela_central_relatorios()
    elif menu == "⚙️ Configurações do Sistema":
        st.session_state['produto_selecionado'] = None
        from views.configuracoes import tela_configuracoes_globais
        tela_configuracoes_globais()

if __name__ == "__main__":
    main()