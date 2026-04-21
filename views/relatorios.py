# tracebox/views/relatorios.py
import streamlit as st
import datetime
import pandas as pd
import streamlit.components.v1 as components
from client.api_client import TraceBoxClient
from controllers.relatorios import construir_html_impressao

def tela_central_relatorios():
    st.title("🖨️ Central de Relatórios e Auditoria")
    st.caption("Gere documentos consolidados em padrão de impressão (PDF).")
    
    usuario_atual = st.session_state['usuario_logado']['nome']

    # Adicionamos a terceira ABA aqui!
    aba_extrato, aba_consolidado, aba_manutencao = st.tabs([
        "🔎 Extrato (Kardex)", "🏢 Posição Consolidada", "🛠️ Histórico de Oficina"
    ])

    # =========================================================
    # RELATÓRIO 1: Extrato de Movimentações (O "Kardex")
    # =========================================================
    with aba_extrato:
        st.write("### Rastreabilidade Total de um Produto")
        lista_prod = TraceBoxClient.relatorios_produtos()
        
        c_prod, c_ini, c_fim = st.columns([2, 1, 1])
        with c_prod: produto_sel = st.selectbox("Selecione o Produto:", [""] + lista_prod)
        with c_ini: data_inicio_ex = st.date_input("Data Inicial:", datetime.date.today().replace(day=1), key="dt_ini_ex")
        with c_fim: data_fim_ex = st.date_input("Data Final:", datetime.date.today(), key="dt_fim_ex")

        if st.button("Gerar Extrato Kardex", type="primary"):
            if not produto_sel: st.warning("Selecione um produto primeiro.")
            elif data_inicio_ex > data_fim_ex: st.error("A Data Inicial não pode ser maior que a Data Final.")
            else:
                with st.spinner("Compilando histórico..."):
                    df_extrato_raw, cod_puro = TraceBoxClient.relatorios_extrato(produto_sel, data_inicio_ex.strftime("%Y-%m-%d"), data_fim_ex.strftime("%Y-%m-%d"))
                    df_extrato = pd.DataFrame(df_extrato_raw)
                    titulo = "Extrato de Movimentações Logísticas (Kardex)"
                    filtros = f"Produto: {cod_puro} | Período: {data_inicio_ex.strftime('%d/%m/%Y')} a {data_fim_ex.strftime('%d/%m/%Y')}"
                    html_pronto = construir_html_impressao(titulo, usuario_atual, filtros, df_extrato)
                    st.divider()
                    components.html(html_pronto, height=600, scrolling=True)

    # =========================================================
    # RELATÓRIO 2: Posição Consolidada de Estoque
    # =========================================================
    with aba_consolidado:
        st.write("### Auditoria de Saldos Físicos")
        if st.button("Gerar Relatório de Posição Consolidada", type="primary"):
            with st.spinner("Calculando saldos e valores..."):
                df_consolidado = pd.DataFrame(TraceBoxClient.relatorios_posicao())
                titulo = "Posição Consolidada de Estoque Geral"
                filtros = "Filtro Aplicado: Todos os Polos Ativos | Ignorando Sucata e Extravio"
                html_pronto = construir_html_impressao(titulo, usuario_atual, filtros, df_consolidado)
                st.divider()
                components.html(html_pronto, height=600, scrolling=True)

    # =========================================================
    # RELATÓRIO 3: Desempenho e Viabilidade da Manutenção
    # =========================================================
    with aba_manutencao:
        st.write("### Gestão de Ordens de Serviço (Oficina)")
        st.write("Analise as manutenções em aberto, custos de reparo e indicadores de viabilidade.")

        c_stat, c_ini_man, c_fim_man = st.columns([2, 1, 1])
        with c_stat:
            status_os = st.selectbox("Status da Ordem de Serviço:", ["Todas", "Em Aberto", "Realizadas/Concluídas", "Reprovadas"])
        with c_ini_man:
            data_inicio_man = st.date_input("Abertura (A partir de):", datetime.date.today().replace(day=1), key="dt_ini_man")
        with c_fim_man:
            data_fim_man = st.date_input("Abertura (Até):", datetime.date.today(), key="dt_fim_man")

        if st.button("Gerar Relatório da Oficina", type="primary"):
            if data_inicio_man > data_fim_man: 
                st.error("A Data Inicial não pode ser maior que a Data Final.")
            else:
                with st.spinner("Avaliando custos e viabilidades..."):
                    df_manut = pd.DataFrame(TraceBoxClient.relatorios_manutencao(data_inicio_man.strftime("%Y-%m-%d"), data_fim_man.strftime("%Y-%m-%d"), status_os))
                    
                    titulo = "Relatório de Desempenho da Oficina (Ordens de Serviço)"
                    filtros = f"Status: {status_os} | Período de Abertura: {data_inicio_man.strftime('%d/%m/%Y')} a {data_fim_man.strftime('%d/%m/%Y')}"
                    
                    html_pronto = construir_html_impressao(titulo, usuario_atual, filtros, df_manut)
                    
                    st.divider()
                    st.success("✅ Relatório gerado! Verifique a coluna de viabilidade para tomar decisões de descarte.")
                    components.html(html_pronto, height=600, scrolling=True)