# tracebox/views/saidas.py
import streamlit as st
from database.queries import carregar_dados, executar_query

def tela_saidas_requisicoes():
    st.title("📤 Saídas (Fila de Requisições)")
    st.caption("Despache ferramentas das Filiais diretamente para as Obras/Projetos.")
    
    usuario_atual = st.session_state['usuario_logado']['nome']

    # Busca apenas locais que sejam Filiais e tenham saldo disponível
    df_locais = carregar_dados("SELECT DISTINCT localizacao FROM imobilizado WHERE quantidade > 0 AND status = 'Disponível' AND localizacao LIKE 'Filial%'")
    filiais = sorted(df_locais['localizacao'].tolist()) if not df_locais.empty else []
    
    st.write("### 1. Dados da Requisição")
    c1, c2 = st.columns(2)
    with c1: 
        origem = st.selectbox("📍 Polo de Saída (Estoque)", filiais)
    with c2: 
        # Traz projetos já existentes ou permite digitar um novo
        df_projetos = carregar_dados("SELECT DISTINCT localizacao FROM imobilizado WHERE status = 'Em Uso'")
        projetos_ativos = sorted(df_projetos['localizacao'].tolist()) if not df_projetos.empty else []
        destino = st.selectbox("🏗️ Obra/Projeto de Destino", ["Nova Obra/Projeto..."] + projetos_ativos)

    if destino == "Nova Obra/Projeto...":
        destino = st.text_input("Digite o nome da Nova Obra:")

    if not origem or not destino:
        st.warning("Selecione a origem e digite/selecione o projeto de destino.")
        return

    # Busca os itens disponíveis no polo de origem
    df_itens = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade FROM imobilizado WHERE localizacao = ? AND status = 'Disponível' AND quantidade > 0", (origem,))
    
    if df_itens.empty:
        st.info(f"O estoque de '{origem}' está vazio ou sem itens disponíveis.")
        return

    st.write("### 2. Separação de Materiais (Picking)")
    with st.form("form_saida_obras"):
        selecoes = {}
        for index, row in df_itens.iterrows():
            id_db, cod, desc, tag, qtd_disp = row['id'], row['codigo'], row['descricao'], row['num_tag'], int(row['quantidade'])
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1: 
                st.write(f"**{cod}** - {desc}")
                if tag: st.caption(f"TAG: `{tag}`")
            with col2: 
                enviar = st.checkbox(f"Adicionar à Carga", key=f"chk_out_{id_db}")
            with col3: 
                qtd_enviar = 1 if tag else st.number_input("Qtd", min_value=1, max_value=qtd_disp, value=1, key=f"qtd_out_{id_db}")
            
            if enviar: 
                selecoes[id_db] = {'qtd': qtd_enviar, 'qtd_disp': qtd_disp}
            st.divider()

        if st.form_submit_button("📤 Atender Requisição e Despachar para Obra", type="primary"):
            if not selecoes: st.stop()

            for id_item, dados in selecoes.items():
                qtd_req = dados['qtd']
                
                if qtd_req == dados['qtd_disp']:
                    # Envio Total
                    executar_query("UPDATE imobilizado SET localizacao = ?, status = 'Em Uso' WHERE id = ?", (destino, id_item))
                    id_mov = id_item
                else:
                    # Envio Parcial (Split)
                    executar_query("UPDATE imobilizado SET quantidade = quantidade - ? WHERE id = ?", (qtd_req, id_item))
                    id_mov = executar_query(f"""
                        INSERT INTO imobilizado (codigo, descricao, marca, modelo, num_tag, quantidade, status, localizacao, categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material) 
                        SELECT codigo, descricao, marca, modelo, num_tag, {qtd_req}, 'Em Uso', '{destino}', categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material 
                        FROM imobilizado WHERE id = {id_item}
                    """)
                    
                # Regista o log
                executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Saída para Obra', ?, ?, ?)", (id_mov, usuario_atual, destino, f"Saída de: {origem}"))

            st.success(f"✅ Saída registada! Ferramentas alocadas na obra '{destino}' com status 'Em Uso'.")
            st.rerun()