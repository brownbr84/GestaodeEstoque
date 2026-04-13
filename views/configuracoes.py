# tracebox/views/configuracoes.py
import streamlit as st
import base64
from database.queries import carregar_dados, executar_query

# tracebox/views/configuracoes.py

def auto_migrar_configuracoes():
    """Garante que a tabela exista e que o Registro Mestre (ID=1) esteja criado."""
    # 1. Cria a tabela se não existir
    executar_query("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome_empresa TEXT DEFAULT 'TraceBox Logística',
            cnpj TEXT DEFAULT '00.000.000/0001-00',
            logo_base64 TEXT,
            limite_viabilidade REAL DEFAULT 50.0,
            anos_depreciacao INTEGER DEFAULT 5
        )
    """)
    
    executar_query("INSERT OR IGNORE INTO configuracoes (id) VALUES (1)")
    
    df_check = carregar_dados("SELECT id FROM configuracoes WHERE id = 1")
    if df_check.empty:
        executar_query("INSERT INTO configuracoes (nome_empresa) VALUES ('TraceBox')")

def tela_configuracoes_globais():
    auto_migrar_configuracoes()
    
    st.title("⚙️ Configurações Globais do Sistema")
    st.caption("Central de gestão de parâmetros, identidade visual e regras de negócio do TraceBox.")

    # Carrega as configurações atuais
    df_config = carregar_dados("SELECT * FROM configuracoes WHERE id = 1")
    config_atual = df_config.iloc[0] if not df_config.empty else None

    aba1, aba2, aba3 = st.tabs(["🏢 Identidade Visual", "⚙️ Parâmetros do Sistema", "👥 Usuários (Em Breve)"])

   # ==========================================
    # ABA 1: IDENTIDADE VISUAL E LOGOTIPO
    # ==========================================
    with aba1:
        st.write("### Dados da Empresa nos Relatórios e Etiquetas")
        
        with st.form("form_identidade"):
            c1, c2 = st.columns(2)
            with c1:
                novo_nome = st.text_input("Nome da Empresa / Razão Social", value=config_atual['nome_empresa'] if config_atual is not None else "")
            with c2:
                novo_cnpj = st.text_input("CNPJ / Documento Base", value=config_atual['cnpj'] if config_atual is not None else "")
                
            st.write("#### Upload de Logotipo")
            st.caption("Envie uma imagem PNG ou JPG (Fundo transparente recomendado). Ela aparecerá em PDFs e Etiquetas.")
            arquivo_logo = st.file_uploader("Selecionar nova imagem", type=["png", "jpg", "jpeg"])
            
            # Se já existir um logo salvo, mostra uma pré-visualização
            if config_atual is not None and config_atual['logo_base64']:
                st.write("Logotipo Atual:")
                st.markdown(f'<img src="data:image/png;base64,{config_atual["logo_base64"]}" height="60">', unsafe_allow_html=True)
            
            if st.form_submit_button("💾 Salvar Identidade Visual", type="primary"):
                # 1. Recupera o logo atual para não apagar caso o usuário só mude o nome
                logo_b64 = config_atual['logo_base64'] if config_atual is not None else ""
                
                # 2. Se o usuário enviou uma imagem nova, converte para base64
                if arquivo_logo is not None:
                    bytes_data = arquivo_logo.getvalue()
                    import base64 # Garantindo que a biblioteca está disponível
                    logo_b64 = base64.b64encode(bytes_data).decode()
                
                # 3. Grava tudo no banco de dados
                executar_query("""
                    UPDATE configuracoes 
                    SET nome_empresa = ?, cnpj = ?, logo_base64 = ? 
                    WHERE id = 1
                """, (novo_nome, novo_cnpj, logo_b64))
                
                st.toast("✅ Configurações salvas com sucesso!", icon="💾")
                import time
                time.sleep(1)
                st.rerun()

    # ==========================================
    # ABA 2: REGRAS DE NEGÓCIO
    # ==========================================
    with aba2:
        st.write("### Motor Matemático e Logístico")
        st.warning("⚠️ Alterar estes parâmetros afetará os laudos automáticos da oficina.")
        
        with st.form("form_parametros"):
            c1, c2 = st.columns(2)
            with c1:
                novo_limite = st.number_input(
                    "Limite de Viabilidade de Reparo (%)", 
                    value=float(config_atual['limite_viabilidade']) if config_atual is not None else 50.0,
                    help="Se o conserto custar mais que esta % do valor de um novo, será sugerido sucateamento."
                )
            with c2:
                novos_anos = st.number_input(
                    "Anos para Depreciação Contábil", 
                    value=int(config_atual['anos_depreciacao']) if config_atual is not None else 5,
                    help="Tempo padrão para calcular a perda de valor das ferramentas com o tempo."
                )
                
            if st.form_submit_button("💾 Atualizar Motor de Regras", type="primary"):
                executar_query("UPDATE configuracoes SET limite_viabilidade = ?, anos_depreciacao = ? WHERE id = 1", (novo_limite, novos_anos))
                st.success("Parâmetros operacionais atualizados!")
                st.rerun()

    # ==========================================
    # ABA 3: USUÁRIOS
    # ==========================================
    with aba3:
        st.write("### Gestão de Acessos e Perfis")
        st.info("O módulo de criação de utilizadores, redefinição de senhas e atribuição de perfis (Admin, Operador, Oficina) será alocado aqui.")