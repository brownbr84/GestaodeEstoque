# tracebox/main.py
import streamlit as st
import pandas as pd
from database.queries import executar_query, carregar_dados

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
from views.recebimento import tela_recebimento_projetos
from views.movimentacao import tela_movimentacao
from views.matriz_fisica import tela_matriz_fisica
from views.saidas import tela_saidas_requisicoes
from views.torre_controle import tela_torre_controle
from views.cadastro import tela_cadastro_produtos
from views.produto import tela_produto
from views.manutencao import tela_gestao_manutencao
from views.outbound import tela_logistica_outbound
from views.requisicao import tela_fazer_requisicao


# =====================================================================
# 3. MOTOR DE IGNIÇÃO (Injeta tabelas e dados de teste)
# =====================================================================
def inicializar_e_popular_banco():
    """Motor de Ignição: Cria o BD e garante que as colunas existam."""
    # 1. Tabela Imobilizado
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

    # 2. Tabela Movimentações (Corrigindo o nome da coluna de data)
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

    # RADAR DE SEGURANÇA: Garante as colunas em tabelas que já existiam
    try:
        df_mov = carregar_dados("PRAGMA table_info(movimentacoes)")
        cols_mov = df_mov['name'].str.lower().tolist()
        if 'data_movimentacao' not in cols_mov:
            executar_query("ALTER TABLE movimentacoes ADD COLUMN data_movimentacao DATETIME DEFAULT CURRENT_TIMESTAMP")
    except: pass

    # Injeção de Dados de Teste
    df_check = carregar_dados("SELECT COUNT(*) as total FROM imobilizado")
    if not df_check.empty and df_check.iloc[0]['total'] == 0:
        produtos_teste = [
            ("PRD-001", "Furadeira de Impacto", "Bosch", "GSB 16 RE", "TAG-1001", 1, "Disponível", "Filial CTG", "Elétrica", 450.00, "Ativo"),
            ("PRD-001", "Furadeira de Impacto", "Bosch", "GSB 16 RE", "TAG-1002", 1, "Disponível", "Filial CTG", "Elétrica", 450.00, "Ativo"),
            ("PRD-002", "Serra Mármore", "Makita", "4100NH2Z", "TAG-2001", 1, "Disponível", "Filial CTG", "Elétrica", 550.00, "Ativo"),
            ("CNS-001", "Parafuso Sextavado", "Gerdau", "8x40", "", 500, "Disponível", "Filial CTG", "Insumos", 0.50, "Consumo"),
            ("CNS-002", "Fita Isolante 3M", "3M", "20m", "", 50, "Disponível", "Filial CTG", "Insumos", 8.90, "Consumo")
        ]

        for p in produtos_teste:
            executar_query("""
                INSERT INTO imobilizado (codigo, descricao, marca, modelo, num_tag, quantidade, status, localizacao, categoria, valor_unitario, tipo_material)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, p)

# ==========================================
# 4. FUNÇÃO PRINCIPAL E ROTEAMENTO
# ==========================================
def main():
    # --- O MOTOR DE IGNIÇÃO RODA AQUI, ANTES DE TUDO ---
    inicializar_e_popular_banco()

    # 1. VALIDAÇÃO DE SESSÃO (A Fechadura)
    if st.session_state.get('usuario_logado') is None:
        tela_login()
        return # O return aqui é crítico: impede que o resto do código (o menu) carregue!

    # 2. DADOS DO USUÁRIO
    usuario = st.session_state['usuario_logado']
    
    # 3. SIDEBAR E NAVEGAÇÃO
    st.sidebar.markdown("<h2 style='color: #2563eb; text-align: center; margin-bottom:0;'>💠 TraceBox</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='text-align: center; color: gray; font-size: 0.9em;'>Credencial: {usuario['nome'].upper()} [{usuario['perfil']}]</p>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Encerrar Sessão", use_container_width=True): 
        st.session_state['usuario_logado'] = None
        st.rerun()
        
    st.sidebar.divider()
    
    opcoes_menu = [
        "📈 Torre de Controle", 
        "📦 Consulta de Matriz Física", 
        "➕ Cadastrar Novo Ativo",          
        "📋 Inventário Cíclico",
        "🛠️ Manutenção",
        "📝 Fazer Requisição (Solicitante)",
        "📤 Logística Outbound (Saída)",   
        "📥 Logística Inbound (Entrada)"   
    ]
    
    menu = st.sidebar.radio("Navegação", opcoes_menu)

    st.sidebar.divider()
    if st.sidebar.button("Sair (Logout)", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # 4. ROTEAMENTO PARA AS VIEWS
    # ==========================================
    if menu == "📈 Torre de Controle":
        st.session_state['produto_selecionado'] = None 
        tela_torre_controle()

    elif menu == "📦 Consulta de Matriz Física":
        # AQUI ESTÁ O GATILHO DA FICHA TÉCNICA
        if st.session_state.get('produto_selecionado'):
            tela_produto() # Mostra o Prontuário Médico
        else:
            tela_matriz_fisica() # Mostra a Tabela Limpa

    elif menu == "➕ Cadastrar Novo Ativo":
        st.session_state['produto_selecionado'] = None
        tela_cadastro_produtos()

    elif menu == "📤 Saídas (Fila de Requisições)":
        st.session_state['produto_selecionado'] = None
        tela_saidas_requisicoes()

    elif menu == "📥 Inbound (Recebimento)":
        st.session_state['produto_selecionado'] = None
        tela_recebimento_projetos()

    elif menu == "🔄 Transferências":
        st.session_state['produto_selecionado'] = None
        tela_movimentacao()
        
    elif menu == "📋 Inventário Cíclico":
        st.session_state['produto_selecionado'] = None
        tela_inventario_ciclico() 
    
    elif menu == "🛠️ Manutenção":
        st.session_state['produto_selecionado'] = None
        tela_gestao_manutencao()
    
    elif menu == "📤 Logística Outbound (Saída)":
        st.session_state['produto_selecionado'] = None
        tela_logistica_outbound()

    elif menu == "📥 Logística Inbound (Entrada)":
        st.session_state['produto_selecionado'] = None
        st.info("Módulo Inbound em construção...") # Rota provisória até criarmos a tela

    elif menu == "📝 Fazer Requisição (Solicitante)":
        st.session_state['produto_selecionado'] = None
        tela_fazer_requisicao()

if __name__ == "__main__":
    main()