# tracebox/views/manutencao.py
import streamlit as st
import pandas as pd
import time
from database.queries import carregar_dados, executar_query
from controllers.manutencao import *
from controllers.viabilidade import calcular_viabilidade

def tela_gestao_manutencao():
    # AUTO-SETUP E MIGRAÇÃO
    executar_query("""
        CREATE TABLE IF NOT EXISTS manutencao_ordens (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ferramenta_id INTEGER, codigo_ferramenta TEXT,
            data_entrada DATETIME, data_saida DATETIME, motivo_falha TEXT, diagnostico TEXT,
            custo_reparo REAL DEFAULT 0.0, mecanico_responsavel TEXT, status_ordem TEXT DEFAULT 'Aberta',
            FOREIGN KEY(ferramenta_id) REFERENCES imobilizado(id)
        )
    """)
    df_colunas = carregar_dados("PRAGMA table_info(manutencao_ordens)")
    colunas_existentes = df_colunas['name'].tolist() if not df_colunas.empty else []
    if 'solicitante' not in colunas_existentes: executar_query("ALTER TABLE manutencao_ordens ADD COLUMN solicitante TEXT")
    if 'empresa_reparo' not in colunas_existentes: executar_query("ALTER TABLE manutencao_ordens ADD COLUMN empresa_reparo TEXT")
    if 'num_orcamento' not in colunas_existentes: executar_query("ALTER TABLE manutencao_ordens ADD COLUMN num_orcamento TEXT")

    # TRUQUE DE UX: Gatilho para forçar a limpeza total da tela de Abertura
    if 'reset_abertura' not in st.session_state:
        st.session_state['reset_abertura'] = 0

    st.title("🛠️ Fluxo de Manutenção e Ativos")
    usuario_atual = st.session_state['usuario_logado']['nome']

    aba1, aba2, aba3, aba4 = st.tabs([
        "🚨 1. Abertura de Chamado", 
        "🔧 2. Oficina (Orçamentos)", 
        "⚖️ 3. Gestão (Viabilidade)", 
        "✅ 4. Finalização & Estoque"
    ])

    # === ABA 1: ABERTURA (CASCATA DE SELEÇÃO E CONSOLIDAÇÃO) ===
    with aba1:
        st.subheader("Entrada de Equipamento Avariado")
        st.caption("Selecione primeiro o modelo consolidado, depois identifique a TAG ou a Filial do Lote.")
        
        # REGRA DE NEGÓCIO: Apenas Ativos (Ignora tudo que tiver 'Consumo' ou 'Consumível' na categoria)
        query_disp = f"""
            SELECT id, codigo, descricao, num_tag, localizacao, quantidade, categoria 
            FROM imobilizado 
            WHERE status != 'Manutenção' AND status != 'Sucateado' 
            AND quantidade > 0 
            AND categoria NOT LIKE '%Consumo%' AND categoria != 'Consumíveis'
            /* {time.time()} */
        """
        df_disp = carregar_dados(query_disp)
        
        if not df_disp.empty:
            df_disp['codigo_str'] = df_disp['codigo'].fillna("").astype(str).str.strip()
            df_disp['descricao_str'] = df_disp['descricao'].fillna("").astype(str).str.strip()
            df_disp = df_disp[df_disp['codigo_str'] != ""] 
            
            desc_map = df_disp.groupby('codigo_str')['descricao_str'].apply(lambda x: max(x, key=len)).to_dict()
            df_disp['Produto_Consolidado'] = df_disp['codigo_str'] + " - " + df_disp['codigo_str'].map(desc_map)
            
            lista_produtos = sorted(df_disp['Produto_Consolidado'].unique().tolist())
            
            # O Segredo: A key usa o nosso gatilho. Quando o gatilho muda, o selectbox zera!
            produto_selecionado = st.selectbox(
                "📦 1. Pesquise e Selecione o Produto Base", 
                [""] + lista_produtos,
                key=f"pesquisa_base_{st.session_state['reset_abertura']}"
            )
            
            if produto_selecionado:
                df_filtrado = df_disp[df_disp['Produto_Consolidado'] == produto_selecionado].copy()
                df_filtrado['tag_str'] = df_filtrado['num_tag'].fillna("").astype(str).str.strip()
                
                with st.form("form_abertura", clear_on_submit=True):
                    opcoes_especificas = []
                    
                    df_com_tag = df_filtrado[df_filtrado['tag_str'] != ""]
                    df_sem_tag = df_filtrado[df_filtrado['tag_str'] == ""]
                    
                    for _, row in df_com_tag.iterrows():
                        label = f"📍 TAG: {row['tag_str']} | Polo: {row['localizacao']} | (1 unid)"
                        opcoes_especificas.append({"id": row['id'], "codigo": row['codigo_str'], "label": label})
                    
                    if not df_sem_tag.empty:
                        df_agrupado = df_sem_tag.groupby('localizacao').agg({
                            'quantidade': 'sum', 'id': 'first', 'codigo_str': 'first'
                        }).reset_index()
                        for _, row in df_agrupado.iterrows():
                            label = f"📦 Lote Consolidado | Polo: {row['localizacao']} | Disponível: {int(row['quantidade'])} unids"
                            opcoes_especificas.append({"id": row['id'], "codigo": row['codigo_str'], "label": label})
                    
                    lista_labels = sorted([opt['label'] for opt in opcoes_especificas])
                    ativo_especifico = st.selectbox("🏷️ 2. Selecione a Unidade Específica (TAG ou Polo) *", [""] + lista_labels)
                    
                    st.divider()
                    st.write("📋 **Detalhes da Avaria**")
                    c1, c2 = st.columns(2)
                    with c1: solicitante = st.text_input("Responsável pela Solicitação *", placeholder="Quem identificou a falha?")
                    with c2: motivo = st.text_area("Motivo da Falha / Relato *", placeholder="Ex: Equipamento não liga...")
                    
                    if st.form_submit_button("🚨 Abrir Ordem de Serviço", type="primary"):
                        if not ativo_especifico or not solicitante or len(motivo) < 3:
                            st.error("Preencha a unidade, o responsável e o motivo.")
                        else:
                            id_real = next(opt['id'] for opt in opcoes_especificas if opt['label'] == ativo_especifico)
                            cod_real = next(opt['codigo'] for opt in opcoes_especificas if opt['label'] == ativo_especifico)
                            
                            sucesso, msg = abrir_ordem_manutencao(int(id_real), str(cod_real), str(motivo), str(solicitante), usuario_atual)
                            if sucesso:
                                st.success(msg)
                                time.sleep(1.5)
                                # Incrementa o gatilho: A tela limpa inteiramente ao recarregar!
                                st.session_state['reset_abertura'] += 1
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("Não há itens classificados como Ativos disponíveis para manutenção.")

    # === ABA 2: OFICINA (LANÇAR ORÇAMENTO EXTERNO/INTERNO) ===
    with aba2:
        st.subheader("Fila de Diagnóstico e Orçamento")
        query_abertas = f"SELECT o.id, o.codigo_ferramenta, i.descricao, i.num_tag, o.motivo_falha, o.solicitante FROM manutencao_ordens o JOIN imobilizado i ON o.ferramenta_id = i.id WHERE o.status_ordem = 'Aberta' /* {time.time()} */"
        df_abertas = carregar_dados(query_abertas)
        
        if df_abertas.empty: st.success("✅ Nenhum item aguardando orçamento.")
        for _, row in df_abertas.iterrows():
            tag_label = f" - TAG: {row['num_tag']}" if pd.notna(row['num_tag']) and str(row['num_tag']).strip() != "" else " - (Item de Lote)"
            with st.expander(f"OS-{row['id']} | {row['codigo_ferramenta']} - {row['descricao']}{tag_label}", expanded=False):
                st.info(f"🗣️ **Reportado por:** {row['solicitante'] or 'Não informado'} | **Relato:** {row['motivo_falha']}")
                with st.form(f"orc_{row['id']}", clear_on_submit=True):
                    diagnostico = st.text_input("Diagnóstico Técnico *")
                    c1, c2, c3 = st.columns(3)
                    with c1: mecanico = st.text_input("Avaliador/Mecânico *", value=usuario_atual)
                    with c2: empresa = st.text_input("Empresa (Reparo Externo)", placeholder="Ex: Autorizada Bosch")
                    with c3: num_orcamento = st.text_input("Nº Orçamento / Pedido (Opcional)")
                    custo = st.number_input("Custo Estimado Total (R$) *", min_value=0.0, format="%.2f")
                    if st.form_submit_button("Enviar para Aprovação (Gestão)", type="primary"):
                        if not diagnostico or not mecanico: st.error("Preencha o diagnóstico e o avaliador.")
                        else:
                            lancar_orcamento_oficina(row['id'], diagnostico, custo, mecanico, empresa, num_orcamento)
                            st.success("Enviado para viabilidade!")
                            time.sleep(1)
                            st.rerun()

    # === ABA 3: VIABILIDADE (COM GRID DE HISTÓRICO) ===
    with aba3:
        st.subheader("Aprovação Técnica e Financeira")
        query_aprov = f"SELECT o.id, o.ferramenta_id, o.codigo_ferramenta, i.descricao, i.num_tag, i.valor_unitario, o.custo_reparo, o.diagnostico, o.empresa_reparo, o.num_orcamento FROM manutencao_ordens o JOIN imobilizado i ON o.ferramenta_id = i.id WHERE o.status_ordem = 'Aguardando Aprovação' /* {time.time()} */"
        df_aprov = carregar_dados(query_aprov)
        
        if df_aprov.empty: st.success("✅ Nenhuma pendência de aprovação.")
        for _, row in df_aprov.iterrows():
            with st.container(border=True):
                tag_label = f" - TAG: {row['num_tag']}" if pd.notna(row['num_tag']) and str(row['num_tag']).strip() != "" else " - (Item de Lote)"
                st.markdown(f"### ⚙️ {row['codigo_ferramenta']} - {row['descricao']}{tag_label}")
                st.write(f"**Diagnóstico:** {row['diagnostico']} | **Empresa:** {row['empresa_reparo'] or 'Interna'} | **Doc:** {row['num_orcamento'] or 'S/N'}")
                v_novo = float(row['valor_unitario'] or 0)
                v_reparo = float(row['custo_reparo'] or 0)
                v_atual, comp, viavel = calcular_viabilidade(v_novo, 2, 5, v_reparo)
                c1, c2 = st.columns(2)
                c1.metric("Custo do Orçamento", f"R$ {v_reparo:,.2f}")
                c2.metric("Índice de Comprometimento", f"{comp:.1f}%")
                if viavel: st.success("💡 **Laudo do Sistema:** REPARO VIÁVEL (Abaixo de 50% de risco).")
                else: st.error("🚨 **Laudo do Sistema:** INVIÁVEL. Sugestão de Sucateamento.")
                
                df_hist = carregar_dados(f"SELECT data_saida as Data, diagnostico as Serviço, empresa_reparo as Fornecedor, custo_reparo as 'Valor (R$)' FROM manutencao_ordens WHERE ferramenta_id = ? AND status_ordem = 'Concluída' ORDER BY data_saida DESC", (row['ferramenta_id'],))
                if not df_hist.empty:
                    st.caption(f"📚 **Histórico de Reparos Anteriores**")
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
                else: st.caption("Primeira manutenção deste ativo.")

                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("✅ Aprovar Orçamento (Iniciar Reparo)", key=f"ap_{row['id']}", type="primary"):
                    aprovar_manutencao(row['id'], "Aprovar")
                    st.rerun()
                if col_btn2.button("🗑️ Reprovar e Sucatear Ativo", key=f"re_{row['id']}"):
                    aprovar_manutencao(row['id'], "Reprovar")
                    st.rerun()

    # === ABA 4: FINALIZAÇÃO E ESTOQUE ===
    with aba4:
        st.subheader("Liberação Pós-Reparo")
        query_exec = f"SELECT o.id, o.ferramenta_id, o.codigo_ferramenta, i.descricao, i.num_tag FROM manutencao_ordens o JOIN imobilizado i ON o.ferramenta_id = i.id WHERE o.status_ordem = 'Em Execução' /* {time.time()} */"
        df_exec = carregar_dados(query_exec)
        
        if df_exec.empty: st.success("✅ Nenhum conserto em execução no momento.")
        for _, row in df_exec.iterrows():
            tag_label = f" - TAG: {row['num_tag']}" if pd.notna(row['num_tag']) and str(row['num_tag']).strip() != "" else " - (Item de Lote)"
            with st.expander(f"OS-{row['id']} | {row['codigo_ferramenta']} - {row['descricao']}{tag_label} (EM REPARO)", expanded=True):
                st.warning("⚠️ Este ativo está aprovado e na posse da oficina/fornecedor.")
                destino = st.selectbox("Após conclusão, dar entrada em qual Polo?", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO"], key=f"f_{row['id']}")
                if st.button("✅ Confirmar Recebimento e Disponibilizar", key=f"btn_f_{row['id']}", type="primary"):
                    finalizar_reparo_oficina(row['id'], row['ferramenta_id'], destino, usuario_atual)
                    st.success("Estoque atualizado!")
                    time.sleep(1)
                    st.rerun()
                    