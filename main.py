# tracebox/main.py
import streamlit as st

# 1. Configuração global da página (DEVE ser a primeira linha do Streamlit)
st.set_page_config(
    page_title="TraceBox | Torre de Controle",
    layout="wide",
    initial_sidebar_state="expanded"
)

from database.conexao_orm import engine, Base, SessionLocal
from database.models import Configuracoes  # importar o módulo registra todos os modelos no Base
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

        import os as _os
        _ts = "TIMESTAMP" if _os.getenv("DB_TYPE", "sqlite").lower() == "postgres" else "DATETIME"

        cols_config = [c["name"] for c in inspector.get_columns("configuracoes")]
        for col, tipo in [
            ("smtp_host",             "TEXT"),
            ("smtp_porta",            "INTEGER"),
            ("fiscal_habilitado",     "INTEGER DEFAULT 0"),
            ("fiscal_ambiente",       "TEXT DEFAULT 'homologacao'"),
            ("fiscal_serie",          "TEXT DEFAULT '1'"),
            ("fiscal_numeracao_atual","INTEGER DEFAULT 1"),
        ]:
            if col not in cols_config:
                _conn.execute(_sa.text(f"ALTER TABLE configuracoes ADD COLUMN {col} {tipo}"))
                _conn.commit()

        cols_os = [c["name"] for c in inspector.get_columns("manutencao_ordens")]
        for col, tipo in [("email_status", "TEXT"), ("email_enviado_em", _ts), ("email_erro", "TEXT")]:
            if col not in cols_os:
                _conn.execute(_sa.text(f"ALTER TABLE manutencao_ordens ADD COLUMN {col} {tipo}"))
                _conn.commit()

        cols_req = [c["name"] for c in inspector.get_columns("requisicoes")]
        for col, tipo in [("email_status", "TEXT"), ("email_enviado_em", _ts), ("email_erro", "TEXT")]:
            if col not in cols_req:
                _conn.execute(_sa.text(f"ALTER TABLE requisicoes ADD COLUMN {col} {tipo}"))
                _conn.commit()

        # Migração incremental — regras_operacao_fiscal (CST IPI/PIS/COFINS)
        cols_regras = [c["name"] for c in inspector.get_columns("regras_operacao_fiscal")]
        for col, tipo in [("cst_ipi", "TEXT"), ("cst_pis", "TEXT"), ("cst_cofins", "TEXT")]:
            if col not in cols_regras:
                _conn.execute(_sa.text(f"ALTER TABLE regras_operacao_fiscal ADD COLUMN {col} {tipo}"))
                _conn.commit()

        # Migração incremental — documentos_fiscais (campos operacionais + infAdic)
        cols_df = [c["name"] for c in inspector.get_columns("documentos_fiscais")]
        for col, tipo in [
            ("num_os",            "TEXT"),
            ("asset_tag",         "TEXT"),
            ("num_serie",         "TEXT"),
            ("info_complementar", "TEXT"),
            ("mod_frete",         "TEXT DEFAULT '9'"),
            ("ind_final",         "INTEGER DEFAULT 0"),
            ("ind_pres",          "INTEGER DEFAULT 0"),
            ("status_historico",  "TEXT"),
        ]:
            if col not in cols_df:
                _conn.execute(_sa.text(f"ALTER TABLE documentos_fiscais ADD COLUMN {col} {tipo}"))
                _conn.commit()

        # Migração incremental — imobilizado (campos fiscais NF-e + endereçamento)
        cols_imob = [c["name"] for c in inspector.get_columns("imobilizado")]
        for col, tipo in [
            ("ncm",            "TEXT"),
            ("c_ean",          "TEXT DEFAULT 'SEM GTIN'"),
            ("orig_icms",      "TEXT DEFAULT '0'"),
            ("cest",           "TEXT DEFAULT ''"),
            ("localizacao_id", "INTEGER"),
        ]:
            if col not in cols_imob:
                _conn.execute(_sa.text(f"ALTER TABLE imobilizado ADD COLUMN {col} {tipo}"))
                _conn.commit()

        # Migração incremental — documentos_fiscais_itens (campos NF-e layout 4.00)
        cols_dfi = [c["name"] for c in inspector.get_columns("documentos_fiscais_itens")]
        for col, tipo in [
            ("c_ean",      "TEXT DEFAULT 'SEM GTIN'"),
            ("c_ean_trib", "TEXT DEFAULT 'SEM GTIN'"),
            ("ind_tot",    "INTEGER DEFAULT 1"),
            ("x_ped",      "TEXT"),
            ("n_item_ped", "TEXT"),
            ("orig_icms",  "TEXT DEFAULT '0'"),
            ("cest",       "TEXT"),
            ("ipi_cst",    "TEXT"),
            ("pis_cst",    "TEXT"),
            ("cofins_cst", "TEXT"),
        ]:
            if col not in cols_dfi:
                _conn.execute(_sa.text(f"ALTER TABLE documentos_fiscais_itens ADD COLUMN {col} {tipo}"))
                _conn.commit()

        # Seed fiscal_cfop_config (tabela já criada pelo create_all acima)
        _CFOP_SEEDS = [
            ("Remessa Conserto",  "CONSERTO",      "SAIDA",   "5915", "6915", "Remessa para conserto"),
            ("Saída Geral",       "GERAL",          "SAIDA",   "5101", "6101", "Venda de mercadoria"),
            ("Devolução",         "DEVOLUCAO",      "SAIDA",   "5921", "6921", "Devolução de mercadoria"),
            ("Transferência",     "TRANSFERENCIA",  "SAIDA",   "5150", "6150", "Transferência"),
            ("Retorno Conserto",  "CONSERTO",      "ENTRADA",  "5916", "6916", "Retorno de conserto"),
            ("Entrada Geral",     "GERAL",          "ENTRADA", "1101", "2101", "Compra de mercadoria"),
            ("Devolução",         "DEVOLUCAO",      "ENTRADA", "5922", "6922", "Devolução recebida"),
            ("Transferência",     "TRANSFERENCIA",  "ENTRADA", "1150", "2150", "Transferência"),
        ]
        for tipo_op, grupo, direcao, cfop_int, cfop_inter, nat in _CFOP_SEEDS:
            existe = _conn.execute(
                _sa.text("SELECT id FROM fiscal_cfop_config WHERE tipo_operacao=:t AND direcao=:d"),
                {"t": tipo_op, "d": direcao}
            ).fetchone()
            if not existe:
                _conn.execute(
                    _sa.text(
                        "INSERT INTO fiscal_cfop_config "
                        "(tipo_operacao, grupo_operacao, direcao, cfop_interno, cfop_interestadual, "
                        "natureza_padrao, ativo) VALUES (:t, :g, :d, :ci, :ce, :n, 1)"
                    ),
                    {"t": tipo_op, "g": grupo, "d": direcao,
                     "ci": cfop_int, "ce": cfop_inter, "n": nat},
                )
        _conn.commit()

        # Seed regras fiscais com CST codes
        _REGRAS_SEED = [
            ("Remessa para Conserto — Interna/Interestadual", "REMESSA_CONSERTO", "5915", "6915", "Remessa para conserto", "41", "53", "07", "07"),
            ("Retorno de Conserto — Interna/Interestadual",  "RETORNO_CONSERTO", "5916", "6916", "Retorno de conserto",   "41", "53", "07", "07"),
            ("Saída Geral — Interna/Interestadual",          "SAIDA_GERAL",      "5102", "6102", "Saída de mercadorias",  "00", "50", "01", "01"),
            ("Entrada Geral — Interna/Interestadual",        "ENTRADA_GERAL",    "1102", "2102", "Entrada de mercadorias","00", "50", "01", "01"),
        ]
        for nome, tipo_op, cfop_int, cfop_inter, nat_op, cst_icms, cst_ipi, cst_pis, cst_cofins in _REGRAS_SEED:
            row = _conn.execute(
                _sa.text("SELECT id FROM regras_operacao_fiscal WHERE tipo_operacao = :t"),
                {"t": tipo_op}
            ).fetchone()
            if not row:
                _conn.execute(
                    _sa.text(
                        "INSERT INTO regras_operacao_fiscal "
                        "(nome, tipo_operacao, cfop_interno, cfop_interestadual, natureza_operacao, "
                        "cst_icms, cst_ipi, cst_pis, cst_cofins, ativo) "
                        "VALUES (:nome, :tipo, :cfop_int, :cfop_inter, :nat_op, "
                        ":cst_icms, :cst_ipi, :cst_pis, :cst_cofins, 1)"
                    ),
                    {"nome": nome, "tipo": tipo_op, "cfop_int": cfop_int,
                     "cfop_inter": cfop_inter, "nat_op": nat_op,
                     "cst_icms": cst_icms, "cst_ipi": cst_ipi,
                     "cst_pis": cst_pis, "cst_cofins": cst_cofins},
                )
            else:
                _conn.execute(
                    _sa.text(
                        "UPDATE regras_operacao_fiscal SET "
                        "cst_icms=:cst_icms, cst_ipi=:cst_ipi, cst_pis=:cst_pis, cst_cofins=:cst_cofins "
                        "WHERE tipo_operacao=:tipo AND (cst_ipi IS NULL OR cst_ipi='')"
                    ),
                    {"tipo": tipo_op, "cst_icms": cst_icms, "cst_ipi": cst_ipi,
                     "cst_pis": cst_pis, "cst_cofins": cst_cofins},
                )
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

    # 1. VALIDAÇÃO DE SESSÃO (restaura após F5 via query_params)
    if st.session_state.get('usuario_logado') is None:
        _token = st.query_params.get("t", "")
        if _token:
            _user = TraceBoxClient.get_me(_token)
            if _user:
                _user['access_token'] = _token
                st.session_state['usuario_logado'] = _user
                st.session_state['last_activity'] = __import__('datetime').datetime.now()
            else:
                st.query_params.clear()
        if st.session_state.get('usuario_logado') is None:
            from views.auth import tela_login
            tela_login()
            return

    # 1b. TIMEOUT DE INATIVIDADE (10 minutos)
    from datetime import datetime, timedelta
    _TIMEOUT = timedelta(minutes=10)
    _now = datetime.now()
    _last = st.session_state.get('last_activity')
    if _last and (_now - _last) > _TIMEOUT:
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()
    st.session_state['last_activity'] = _now
    
    # 2. BUSCA DA IDENTIDADE VISUAL E USUÁRIO
    id_visual = obter_identidade_visual()
    usuario = st.session_state['usuario_logado']

    # Injeção de CSS para Light Mode — zinc palette, seletores cirúrgicos
    if st.session_state.get('light_mode'):
        st.markdown("""
        <style>
        /* Zinc palette
           z50 #fafafa · z100 #f4f4f5 · z200 #e4e4e7 · z300 #d4d4d8 · z800 #27272a */

        /* Fundo da página */
        [data-testid="stApp"],
        [data-testid="stHeader"],
        section[data-testid="stMain"],
        .main .block-container          { background:#f4f4f5 !important; }

        /* Sidebar */
        [data-testid="stSidebar"]       { background:#e4e4e7 !important; }
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span  { color:#27272a !important; }
        [data-testid="stSidebar"] hr    { border-color:#d4d4d8 !important; }

        /* Campos de input / textarea */
        input, textarea                 { background:#fafafa !important; color:#27272a !important; border:1px solid #d4d4d8 !important; }
        [data-baseweb="input"],
        [data-baseweb="base-input"]     { background:#fafafa !important; border:1px solid #d4d4d8 !important; }
        [data-baseweb="textarea"]       { background:#fafafa !important; border:1px solid #d4d4d8 !important; }
        label, p, span, li              { color:#27272a !important; }

        /* Selects */
        [data-baseweb="select"] > div   { background:#fafafa !important; border:1px solid #d4d4d8 !important; color:#27272a !important; }
        [data-baseweb="popover"]        { background:#fafafa !important; border:1px solid #d4d4d8 !important; }
        [data-baseweb="option"],
        [data-baseweb="menu"] li        { background:#fafafa !important; color:#27272a !important; }
        [data-baseweb="option"]:hover,
        [data-baseweb="menu"] li:hover  { background:#e4e4e7 !important; }

        /* Botões secundários */
        .stButton > button:not([kind="primary"]) { background:#fafafa !important; color:#27272a !important; border:1px solid #d4d4d8 !important; }
        .stButton > button:not([kind="primary"]):hover { background:#e4e4e7 !important; }

        /* Métricas */
        [data-testid="stMetric"]        { background:#fafafa !important; border:1px solid #d4d4d8 !important; border-radius:8px !important; padding:14px !important; }

        /* Dataframe — canvas renderiza em dark (cores via JS, não CSS)
           deixamos o grid com tema escuro como "card" dentro da página clara */
        [data-testid="stDataFrame"]     { border-radius:8px !important; overflow:hidden !important; border:1px solid #d4d4d8 !important; }

        /* Tabs */
        [data-baseweb="tab-list"]       { background:#e4e4e7 !important; border-bottom:2px solid #d4d4d8 !important; }

        /* Expanders */
        [data-testid="stExpander"]      { background:#fafafa !important; border:1px solid #d4d4d8 !important; border-radius:6px !important; }

        /* Divisores */
        hr                              { border-color:#d4d4d8 !important; opacity:1 !important; }
        </style>
        """, unsafe_allow_html=True)

   # ==========================================
    # 3. CONSTRUÇÃO DO MENU LATERAL (CO-BRANDING)
    # ==========================================

    st.sidebar.markdown("<h2 style='color: #2563eb; text-align: center; margin-bottom:0;'>💠 TraceBox</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='text-align: center; color: gray; font-size: 0.8em; margin-top: -5px;'>WMS Enterprise Solution &nbsp;·&nbsp; <span style='color:#4b5563;'>By Operis Tech</span></p>", unsafe_allow_html=True)

    if id_visual is not None and id_visual['logo_base64']:
        st.sidebar.write("<br>", unsafe_allow_html=True)
        st.sidebar.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='data:image/png;base64,{id_visual['logo_base64']}' style='height:52px;width:auto;object-fit:contain;'/>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.sidebar.markdown(f"""
            <div style='text-align: center; padding-top: 5px; border-bottom: 1px solid #4b5563; padding-bottom: 10px; margin-bottom: 5px;'>
                <span style='font-size: 0.85em; color: #9ca3af; font-weight: bold;'>{id_visual['nome_empresa'].upper()}</span>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.divider()

    st.sidebar.markdown(f"<p style='text-align: center; color: gray; font-size: 0.9em; margin-top: 10px;'>👤 {usuario['nome'].upper()} [{usuario['perfil']}]</p>", unsafe_allow_html=True)
    st.sidebar.divider()

    config_nav = TraceBoxClient.get_config() or {}
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
        "👥 Parceiros",
        "🛡️ Auditoria e Compliance",
        "⚙️ Configurações do Sistema"
    ]
    if config_nav.get("fiscal_habilitado"):
        opcoes_menu.insert(-1, "🧾 Módulo Fiscal")

    menu = st.sidebar.radio("Navegação", opcoes_menu)

    st.sidebar.divider()

    # — Tema ——————————————————————————————
    _dark = not st.session_state.get('light_mode', False)
    _label_tema = "☀️ Light" if _dark else "🌙 Dark"
    if st.sidebar.button(_label_tema, use_container_width=True, help="Alternar tema claro/escuro"):
        st.session_state['light_mode'] = _dark
        st.rerun()

    # — Ações rápidas —————————————————————
    col_ref, col_sair = st.sidebar.columns(2, gap="small")
    with col_ref:
        if st.button("🔄 Refresh", use_container_width=True, help="Limpa o cache e recarrega os dados"):
            st.cache_data.clear()
            st.rerun()
    with col_sair:
        if st.button("🚪 Sair", use_container_width=True):
            st.query_params.clear()
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

    elif menu == "🧾 Módulo Fiscal":
        st.session_state['produto_selecionado'] = None
        from views.fiscal import tela_fiscal
        tela_fiscal()

    elif menu == "👥 Parceiros":
        st.session_state['produto_selecionado'] = None
        from views.parceiros import tela_parceiros
        tela_parceiros()

    elif menu == "🛡️ Auditoria e Compliance":
        st.session_state['produto_selecionado'] = None
        from views.auditoria import tela_auditoria
        tela_auditoria()

if __name__ == "__main__":
    main()