# tracebox/views/auditoria.py
import streamlit as st
import pandas as pd
from client.api_client import TraceBoxClient
import streamlit.components.v1 as components
from datetime import datetime

def tela_auditoria():
    st.title("🛡️ Auditoria e Compliance")
    st.caption("Registo inalterável de atividades, alterações e eventos críticos do sistema.")

    perfil_atual = st.session_state['usuario_logado'].get('perfil', 'Operador').upper()
    if "ADM" not in perfil_atual and "GESTOR" not in perfil_atual:
        st.error("🔒 Acesso restrito a Gestores e Administradores. A sua tentativa de acesso foi registada.")
        return

    # 2. PAINEL DE FILTROS COM A DATA DE VOLTA
    with st.expander("🔎 Filtros de Pesquisa", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            opcoes_acao = [
                "Todas", "ENTRADA_COMPRA", "ENTRADA_EXCEPCIONAL", "RECEBIMENTO_DOCA",
                "CANCELAMENTO", "REINTEGRACAO_MALHA", "EXTRAVIO_MALHA",
                "BAIXA_EXCEPCIONAL", "REATIVACAO_TAG", "AJUSTE_ESTOQUE"
            ]
            filtro_acao = st.selectbox("Filtrar por Ação:", opcoes_acao)
        with c2:
            filtro_usuario = st.text_input("Filtrar por Usuário (Nome):", placeholder="Ex: João")
        with c3:
            # O Filtro de Data voltou!
            filtro_data = st.date_input("Data do Evento:", value=None)

    try:
        filtro_data_str = filtro_data.strftime("%Y-%m-%d") if filtro_data else ""
        df_logs = pd.DataFrame(TraceBoxClient.auditoria_logs(filtro_acao, filtro_usuario, filtro_data_str))

        if df_logs.empty:
            st.info("Nenhum registo de auditoria encontrado na base de dados com estes filtros.")
        else:
            st.write(f"**Exibindo os últimos {len(df_logs)} registos:**")
            st.dataframe(
                df_logs,
                column_config={
                    "id": st.column_config.NumberColumn("ID Log", format="%d"),
                    "data_hora": "Data/Hora",
                    "usuario": "Usuário/Responsável",
                    "acao": "Ação Executada",
                    "tabela": "Módulo (BD)",
                    "registro_id": "ID Reg.",
                    "detalhes": "Detalhes Técnicos"
                },
                hide_index=True,
                use_container_width=True
            )

            # MÓDULO DE IMPRESSÃO / EXPORTAÇÃO (COMPLIANCE)
            # ==============================================================
            st.write("---")
            with st.expander("🖨️ Imprimir / Exportar Relatório de Auditoria"):
                # 1. Preparar os dados para ficarem bonitos no Excel/PDF
                df_print = df_logs.copy()
                df_print = df_print.rename(columns={
                    'id': 'ID', 'data_hora': 'DATA/HORA', 'usuario': 'USUÁRIO',
                    'acao': 'AÇÃO', 'tabela': 'MÓDULO (BD)', 
                    'registro_id': 'ID REGISTRO', 'detalhes': 'DETALHES'
                })

                # 2. Botão de Download CSV Nativo
                csv = df_print.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar Planilha (.csv Excel)", 
                    data=csv, 
                    file_name=f"Auditoria_TraceBox_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", 
                    mime='text/csv'
                )
                
                st.write("---")
                
                # 3. View HTML Blindada para Impressão
                html_table = df_print.to_html(index=False)
                data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                usuario_solicitante = st.session_state['usuario_logado'].get('nome', 'Usuário Logado')
                
                html_print_view = f"""
                <html>
                <head>
                <style>
                    body {{ font-family: sans-serif; color: black !important; background-color: white !important; padding: 10px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; color: black !important; font-size: 11px; }}
                    th, td {{ border: 1px solid #000; padding: 8px; text-align: left; word-wrap: break-word; }}
                    th {{ background-color: #e2e8f0; font-weight: bold; }}
                    .cabecalho {{ border: 2px solid #000; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                    .linha-assinatura {{ display: flex; justify-content: space-between; margin-top: 30px; }}
                    @media print {{
                        #btn-imprimir {{ display: none; }}
                        body {{ padding: 0; }}
                    }}
                </style>
                </head>
                <body>
                    <button id="btn-imprimir" onclick="window.print()" style="padding: 10px 15px; margin-bottom: 15px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
                        🖨️ Imprimir Relatório Oficial
                    </button>
                    
                    <div class="cabecalho">
                        <h2 style="margin: 0 0 10px 0;">Relatório Oficial de Auditoria (Compliance)</h2>
                        <p style="margin: 5px 0;"><strong>Gerado por:</strong> {usuario_solicitante}</p>
                        <p style="margin: 5px 0;"><strong>Data da Emissão:</strong> {data_hoje}</p>
                        <p style="margin: 5px 0;"><strong>Filtros Aplicados:</strong> Ação: {filtro_acao} | Usuário: {filtro_usuario if filtro_usuario else 'Todos'} </p>
                        
                        <div class="linha-assinatura">
                            <span><strong>Visto do Gestor de Operações:</strong> _________________________________________</span>
                        </div>
                    </div>
                    
                    {html_table}
                </body>
                </html>
                """
                components.html(html_print_view, height=600, scrolling=True)
                
    except Exception as e:
        st.error(f"Erro fatal ao ler o banco de dados. A tabela foi criada? Erro: {e}")