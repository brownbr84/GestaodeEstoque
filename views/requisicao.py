# tracebox/views/requisicao.py
import pandas as pd
import streamlit as st
import time
from client.api_client import TraceBoxClient

def tela_fazer_requisicao():
    st.title("🛒 Requisição de Materiais")
    st.caption("Solicite materiais ou acompanhe o status dos seus pedidos.")
    
    usuario_atual = st.session_state['usuario_logado']['nome']

    # CRIA AS DUAS ABAS
    aba_nova, aba_historico = st.tabs(["➕ Nova Solicitação", "🔍 Meu Histórico"])

    # =========================================================
    # ABA 1: NOVA REQUISIÇÃO (O seu código já perfeito)
    # =========================================================
    with aba_nova:
        if 'reset_req' not in st.session_state: st.session_state['reset_req'] = 0
        if 'carrinho_req' not in st.session_state:
            st.session_state['carrinho_req'] = []
            st.session_state['req_polo_atual'] = ""

        with st.container(border=True):
            st.subheader("1. Dados da Solicitação")
            tipo_destino = st.radio("Qual é o destino dos materiais?", ["🏗️ Obra / Centro de Custo", "🏢 Transferência para outra Filial"], horizontal=True)
            
            c1, c2, c3 = st.columns(3)
            with c1: 
                polo_alvo = st.selectbox("📍 Retirar de qual Polo (Origem)?", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"])
            with c2: 
                if "Obra" in tipo_destino:
                    projeto = st.text_input("Nome da Obra/Projeto *", key=f"req_projeto_input_{st.session_state['reset_req']}")
                else:
                    filiais_destino = [f for f in ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO"] if f != polo_alvo]
                    projeto = st.selectbox("🎯 Filial de Destino *", filiais_destino, key=f"req_filial_dest_{st.session_state['reset_req']}")
            with c3: 
                solicitante = st.text_input("👷 Solicitante *", value=usuario_atual, disabled=True)

        if st.session_state['req_polo_atual'] != polo_alvo:
            st.session_state['carrinho_req'] = []
            st.session_state['req_polo_atual'] = polo_alvo

        st.write("---")
        col_catalogo, col_carrinho = st.columns([1.2, 1], gap="large")

        with col_catalogo:
            st.subheader("2. Catálogo Disponível")
            tipo_filtro = st.radio("Filtrar Categoria:", ["Ativo", "Consumo"], horizontal=True)
            
            df_estoque = pd.DataFrame(TraceBoxClient.obter_catalogo_disponivel_req(polo_alvo, st.session_state['carrinho_req'], tipo_filtro))

            if df_estoque.empty:
                st.warning(f"Não há itens de '{tipo_filtro}' disponíveis ou estão todos reservados neste polo.")
            else:
                with st.form("form_add_carrinho", clear_on_submit=True):
                    item_sel = st.selectbox("Selecione o material:", [""] + df_estoque['label'].tolist())
                    qtd = st.number_input("Quantidade", min_value=1, value=1)
                    
                    if st.form_submit_button("➕ Adicionar"):
                        if item_sel:
                            linha = df_estoque[df_estoque['label'] == item_sel].iloc[0]
                            cod = linha['codigo']
                            disp = int(linha['saldo_real'])
                            qtd_ja_pedida = sum(i['quantidade'] for i in st.session_state['carrinho_req'] if i['codigo'] == cod)
                            
                            if (qtd_ja_pedida + qtd) > disp: st.error(f"Estoque insuficiente! Saldo disponível: {disp}.")
                            else:
                                st.session_state['carrinho_req'].append({'codigo': cod, 'descricao': linha['descricao'], 'quantidade': qtd, 'tipo': tipo_filtro})
                                st.rerun()

        with col_carrinho:
            st.subheader("🛒 Seu Pedido")
            if not st.session_state['carrinho_req']: st.info("Seu carrinho está vazio.")
            else:
                df_carrinho = pd.DataFrame(st.session_state['carrinho_req']).groupby(['codigo', 'descricao', 'tipo'], as_index=False).sum()
                st.dataframe(df_carrinho[['codigo', 'descricao', 'tipo', 'quantidade']].rename(columns={'codigo':'CÓD', 'descricao':'ITEM', 'tipo':'TIPO', 'quantidade':'QTD'}), hide_index=True, use_container_width=True)
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("🗑️ Esvaziar", use_container_width=True):
                    st.session_state['carrinho_req'] = []
                    st.rerun()
                    
                if c_btn2.button("✅ Enviar Requisição", type="primary", use_container_width=True):
                    if projeto:
                        s, msg = TraceBoxClient.salvar_nova_requisicao(polo_alvo, projeto, solicitante, df_carrinho.to_dict('records'))
                        if s:
                            st.success(msg)
                            st.session_state['carrinho_req'] = []
                            st.session_state['reset_req'] += 1 
                            time.sleep(1.5)
                            st.rerun()
                        else: st.error(msg)
                    else: st.error("Informe o destino corretamente no topo da tela.")

    # =========================================================
    # ABA 2: O HISTÓRICO DO UTILIZADOR
    # =========================================================
    with aba_historico:
        st.subheader(f"📜 Histórico de Pedidos de {usuario_atual}")
        df_hist = pd.DataFrame(TraceBoxClient.listar_historico_solicitante(usuario_atual))
        
        if df_hist.empty:
            st.info("Você ainda não fez nenhuma requisição no sistema.")
        else:
            for _, req in df_hist.iterrows():
                req_id = req['id_clean']
                status = str(req['status']).strip().upper()
                
                # Define a cor da borda com base no status (Semáforo visual)
                cor_status = "blue" if status == 'PENDENTE' else "green" if status == 'CONCLUÍDA' else "red"
                icone_status = "⏳" if status == 'PENDENTE' else "✅" if status == 'CONCLUÍDA' else "❌"
                
                with st.expander(f"{icone_status} REQ-{req_id:04d} | Status: {status} | Data: {req['data_solicitacao']}"):
                    st.write(f"**📍 Origem:** {req['polo_origem']} ➔ **🎯 Destino:** {req['destino_projeto']}")
                    
                    if status == 'CANCELADA':
                        st.error(f"**Motivo do Cancelamento:** {req['motivo_cancelamento']}")
                        st.caption(f"Cancelado por: {req['cancelado_por']}")
                    
                    df_itens = pd.DataFrame(TraceBoxClient.listar_itens_da_requisicao(req_id))
                    if not df_itens.empty:
                        st.dataframe(df_itens, hide_index=True, use_container_width=True)
                    else:
                        st.caption("Nenhum item encontrado para esta requisição.")