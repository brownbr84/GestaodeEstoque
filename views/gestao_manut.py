# Gestão de Manutenção
import streamlit as st
import pandas as pd
from datetime import datetime

# Importa o nosso motor de banco de dados
from database.queries import carregar_dados, executar_query

def tela_gestao_manutencao():
    st.title("🛠️ Gestão de Manutenção e Viabilidade")
    st.caption("Analise reparos e acompanhe a matriz consolidada de disponibilidade dos Polos.")
    
    usuario_logado = st.session_state['usuario_logado']['nome']
    
    # --- 1. MATRIZ CONSOLIDADA DE ESTOQUE (POLO X STATUS) ---
    st.write("### 📊 Matriz Consolidada de Estoque (Por Polo)")
    df_matriz = carregar_dados("""
        SELECT localizacao as Polo, status, SUM(quantidade) as Qtd 
        FROM imobilizado 
        WHERE localizacao LIKE 'Filial%' 
        GROUP BY localizacao, status
    """)
    
    if not df_matriz.empty:
        # Cria uma tabela Pivot (Linhas = Filiais, Colunas = Status)
        df_pivot = df_matriz.pivot_table(index='Polo', columns='status', values='Qtd', fill_value=0).reset_index()
        st.dataframe(df_pivot, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum dado de estoque nas filiais para consolidar.")
        
    st.divider()

    # --- 2. GESTÃO DOS ATIVOS QUEBRADOS ---
    st.write("### ⚠️ Ativos Aguardando Análise de Reparo")
    df_manut = carregar_dados("""
        SELECT id, codigo, descricao, localizacao, ultima_manutencao, 
               COALESCE(qtd_manutencoes, 0) as qtd_manutencoes, 
               COALESCE(custo_reparo_estimado, 0.0) as custo_reparo, 
               COALESCE(valor_unitario, 0.0) as valor_unitario 
        FROM imobilizado 
        WHERE status = 'Manutenção' AND quantidade > 0
    """)

    if df_manut.empty:
        st.success("🎉 Não há nenhum ativo parado em manutenção no momento.")
        return
    
    for index, row in df_manut.iterrows():
        id_item = row['id']
        cod = row['codigo']
        polo_atual = row['localizacao']
        
        with st.expander(f"🔧 {cod} - {row['descricao']} | Polo Físico: {polo_atual}"):
            c1, c2, c3 = st.columns(3)
            valor_novo_calc = float(row['valor_unitario']) if float(row['valor_unitario']) > 0 else 0.01
            
            with c1:
                st.metric("Valor do Ativo (Novo)", f"R$ {float(row['valor_unitario']):,.2f}")
            with c2:
                with st.form(f"form_orcamento_{id_item}"):
                    novo_custo = st.number_input("Orçamento do Reparo (R$)", value=float(row['custo_reparo']))
                    if st.form_submit_button("💾 Salvar Orçamento"):
                        executar_query("UPDATE imobilizado SET custo_reparo_estimado = ? WHERE id = ?", (novo_custo, id_item))
                        st.rerun()
            with c3:
                pct_reparo = (float(row['custo_reparo']) / valor_novo_calc) * 100
                st.info(f"O reparo custa **{pct_reparo:.1f}%** de um novo.")
                    
            if float(row['custo_reparo']) > 0:
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("✅ Aprovar Reparo (Volta a Disponível)", key=f"aprovar_{id_item}", type="primary"):
                        nova_qtd = row['qtd_manutencoes'] + 1
                        hoje = datetime.now().strftime('%Y-%m-%d')
                        
                        # Altera apenas o status. A localização (Polo) continua a mesma!
                        executar_query("UPDATE imobilizado SET status = 'Disponível', qtd_manutencoes = ?, custo_reparo_estimado = 0, ultima_manutencao = ? WHERE id = ?", (nova_qtd, hoje, id_item))
                        executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Retorno de Manutenção', ?, ?, 'Reparo Aprovado')", (id_item, usuario_logado, polo_atual))
                        st.rerun()
                with col_act2:
                    if st.button("🗑️ Sucatear", key=f"sucata_{id_item}"):
                        executar_query("UPDATE imobilizado SET status = 'Sucateado', quantidade = 0 WHERE id = ?", (id_item,))
                        executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Baixa por Sucata', ?, ?, 'Custo de reparo inviável')", (id_item, usuario_logado, polo_atual))
                        st.rerun()