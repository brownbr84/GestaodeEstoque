# tracebox/views/movimentacao.py
import streamlit as st

from database.queries import carregar_dados
# IMPORTAMOS O NOSSO NOVO CONTROLADOR!
from controllers.logistica import processar_transferencia

def tela_movimentacao():
    st.title("🔄 Logística de Transferência (Emissão)")
    st.caption("Transfira ativos entre polos. O saldo ficará 'Em Trânsito' até ser recebido no destino.")
    
    usuario_atual = st.session_state['usuario_logado']['nome']

    df_locais = carregar_dados("SELECT DISTINCT localizacao FROM imobilizado WHERE quantidade > 0 AND status NOT IN ('Extraviado', 'Em Trânsito', 'Sucateado')")
    todos_locais = sorted(df_locais['localizacao'].tolist()) if not df_locais.empty else []
    
    st.write("### 1. Definir Rota")
    c1, c2 = st.columns(2)
    with c1: 
        poregem = st.selectbox("📍 Origem (Onde o item está)", todos_locais)
    with c2: 
        destino = st.selectbox("🎯 Destino", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Outro Projeto..."])

    if destino == "Outro Projeto...":
        destino = st.text_input("Digite o nome do Projeto destino:")

    if poregem == destino or not destino:
        st.warning("A origem e o destino devem ser diferentes e válidos.")
        return

    df_itens = carregar_dados("SELECT id, codigo, descricao, num_tag, status, quantidade FROM imobilizado WHERE localizacao = ? AND quantidade > 0 AND status NOT IN ('Em Trânsito', 'Sucateado', 'Extraviado')", (poregem,))
    
    if df_itens.empty:
        st.info(f"Nenhum item físico apto para transferência em '{poregem}'.")
        return

    st.write("### 2. Selecionar Itens para a Carga")
    with st.form("form_transferencia_livre"):
        selecoes = {}
        for index, row in df_itens.iterrows():
            id_db, cod, desc, tag, qtd_disp, st_atual = row['id'], row['codigo'], row['descricao'], row['num_tag'], int(row['quantidade']), row['status']
            st.markdown(f"**{cod} - {desc}** | Status: `{st_atual}`")
            
            col_sel, col_qtd = st.columns([1, 2])
            with col_sel: mover = st.checkbox(f"Mover", key=f"chk_{id_db}")
            with col_qtd: 
                if tag:
                    st.caption(f"TAG: {tag}")
                    qtd_mover = 1 if mover else 0
                else:
                    qtd_mover = st.number_input("Qtd", min_value=1, max_value=qtd_disp, value=1, key=f"qtd_{id_db}")
            
            if mover: selecoes[id_db] = {'qtd': qtd_mover, 'qtd_disp': qtd_disp}
            st.divider()

        # OLHE COMO FICOU LIMPO O PROCESSAMENTO AQUI!
        if st.form_submit_button("🚀 Despachar Carga (Colocar em Trânsito)", type="primary"):
            if not selecoes: st.stop()
            
            sucesso_total = True
            for id_item, dados in selecoes.items():
                # A TELA PEDE AO CONTROLADOR PARA FAZER O TRABALHO PESADO
                resultado = processar_transferencia(
                    id_item=id_item, 
                    qtd_transferir=dados['qtd'], 
                    qtd_disponivel=dados['qtd_disp'], 
                    destino=destino, 
                    origem=poregem, 
                    usuario_atual=usuario_atual
                )
                if not resultado: sucesso_total = False

            if sucesso_total:
                st.success(f"✅ Transferência emitida! Ferramentas estão a caminho de '{destino}' e bloqueadas como 'Em Trânsito'.")
            else:
                st.error("⚠️ Houve um erro ao processar alguns itens. Verifique o log.")
                
            st.rerun()