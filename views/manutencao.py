# tracebox/views/manutencao.py
import streamlit as st
import pandas as pd
import time
from client.api_client import TraceBoxClient
from controllers.viabilidade import calcular_viabilidade

def tela_gestao_manutencao():
    import streamlit.components.v1 as components
    if 'ticket_os_html' in st.session_state:
        components.html(st.session_state['ticket_os_html'], height=850, scrolling=True)
        if st.button("⬅️ Fechar Ticket e Voltar para Manutenção", type="primary", use_container_width=True):
            del st.session_state['ticket_os_html']
            st.session_state['reset_abertura'] += 1
            st.rerun()
        return

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
        df_disp = pd.DataFrame(TraceBoxClient.carregar_ativos_para_manutencao())
        
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
                            
                            sucesso, msg = TraceBoxClient.abrir_ordem_manutencao(int(id_real), str(cod_real), str(motivo), str(solicitante), usuario_atual)
                            if sucesso:
                                msg_os = msg.split(" ⚠️")[0]
                                st.success(msg_os)
                                if "⚠️ E-mail não enviado" in msg:
                                    erro_email = msg.split("⚠️ E-mail não enviado: ")[-1]
                                    st.warning(f"⚠️ E-mail não enviado: {erro_email}")
                                    import re as _re
                                    match_id = _re.search(r'OS-(\d+)', msg_os)
                                    if match_id and st.session_state['usuario_logado'].get('perfil') in ['Admin', 'Gestor']:
                                        if st.button("📧 Reenviar E-mail da OS", key=f"reenvio_os_{match_id.group(1)}"):
                                            ok_r, msg_r = TraceBoxClient.reenviar_email_os(int(match_id.group(1)))
                                            st.success(msg_r) if ok_r else st.error(msg_r)
                                else:
                                    st.caption("📧 E-mail de notificação enviado aos responsáveis.")
                                import re
                                match = re.search(r'OS-(\d+)', msg)
                                if match:
                                    os_id = match.group(1)
                                    config_atual = TraceBoxClient.get_config() or {}
                                    empresa = config_atual.get('nome_empresa', 'TraceBox')
                                    logo = config_atual.get('logo_base64', '')
                                    logo_html = f'<img src="data:image/png;base64,{logo}" style="max-height: 40px; float: right;">' if logo else ''
                                    
                                    from datetime import datetime
                                    data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
                                    
                                    tag_val = 'S/N (Lote)'
                                    polo_val = 'Indefinido'
                                    if 'TAG:' in ativo_especifico:
                                        parts = ativo_especifico.split('|')
                                        tag_val = parts[0].split('TAG:')[1].strip()
                                        polo_val = parts[1].split('Polo:')[1].strip()
                                    elif 'Polo:' in ativo_especifico:
                                        parts = ativo_especifico.split('|')
                                        polo_val = parts[1].split('Polo:')[1].strip()
                                        
                                    html_ticket = f"""
                                    <html><head><style>
                                        body {{ font-family: 'Segoe UI', sans-serif; color: black !important; background-color: white !important; padding: 15px; font-size: 12px; }}
                                        .cabecalho {{ border: 2px solid #0f172a; padding: 10px 15px; margin-bottom: 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }}
                                        .cabecalho-info {{ flex: 1; }}
                                        .cabecalho-logo {{ text-align: right; margin-left: 20px; }}
                                        .secao {{ border: 1px solid #cbd5e1; padding: 10px 15px; border-radius: 5px; margin-bottom: 15px; page-break-inside: avoid; }}
                                        .titulo-secao {{ margin-top: 0; border-bottom: 2px solid #f1f5f9; padding-bottom: 5px; font-size: 14px; text-transform: uppercase; color: #0f172a; }}
                                        .tabela-info {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
                                        .tabela-info td {{ padding: 6px; border-bottom: 1px solid #eee; vertical-align: top; }}
                                        .tabela-info td:first-child {{ font-weight: bold; width: 25%; background: #f8fafc; }}
                                        .tabela-grid {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                                        .tabela-grid th, .tabela-grid td {{ border: 1px solid #cbd5e1; padding: 6px; text-align: left; }}
                                        .tabela-grid th {{ background-color: #f1f5f9; }}
                                        .checklist {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }}
                                        .check-item {{ display: flex; align-items: center; }}
                                        .box {{ width: 14px; height: 14px; border: 1px solid #000; margin-right: 8px; display: inline-block; }}
                                        .linha-assinatura {{ display: flex; justify-content: space-between; margin-top: 30px; text-align: center; page-break-inside: avoid; }}
                                        .linha-assinatura div {{ width: 30%; border-top: 1px solid #000; padding-top: 5px; font-weight: bold; font-size: 11px; }}
                                        @media print {{ #btn-imprimir {{ display: none; }} body {{ padding: 0; font-size: 11px; }} .secao {{ margin-bottom: 10px; padding: 8px 12px; }} }}
                                    </style></head><body>
                                        <button id="btn-imprimir" onclick="window.print()" style="padding: 10px 20px; margin-bottom: 15px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); width: 100%;">🖨️ Imprimir Ordem de Serviço</button>
                                        
                                        <div class="cabecalho">
                                            <div class="cabecalho-info">
                                                <h2 style="margin: 0 0 5px 0; color: #0f172a; font-size: 18px;">ORDEM DE SERVIÇO #{os_id}</h2>
                                                <p style="margin: 2px 0;"><strong>Abertura:</strong> {data_atual}</p>
                                                <p style="margin: 2px 0;"><strong>Solicitante:</strong> {solicitante}</p>
                                            </div>
                                            <div class="cabecalho-logo">
                                                {logo_html}
                                                <h3 style="margin: 5px 0 0 0; color: #0f172a; font-size: 14px;">{empresa}</h3>
                                            </div>
                                        </div>
                                        
                                        <div class="secao">
                                            <h3 class="titulo-secao">1. Identificação do Ativo</h3>
                                            <table class="tabela-info">
                                                <tr><td>Código / Descrição:</td><td>{produto_selecionado}</td></tr>
                                                <tr><td>Número da TAG:</td><td>{tag_val}</td></tr>
                                                <tr><td>Origem / Polo:</td><td>{polo_val}</td></tr>
                                            </table>
                                        </div>
                                        
                                        <div class="secao">
                                            <h3 class="titulo-secao">2. Relato da Avaria (Pelo Solicitante)</h3>
                                            <div style="padding: 8px; font-style: italic;">
                                                {motivo}
                                            </div>
                                        </div>

                                        <div class="secao">
                                            <h3 class="titulo-secao">3. Acompanhamento e Fluxo de Execução</h3>
                                            <div class="checklist">
                                                <div class="check-item"><span class="box"></span> Recebimento Físico na Oficina &nbsp; ___/___/___</div>
                                                <div class="check-item"><span class="box"></span> Diagnóstico Técnico &nbsp; ___/___/___</div>
                                                <div class="check-item"><span class="box"></span> Aguardando Peças / Orçamento? ( ) Sim ( ) Não</div>
                                                <div class="check-item"><span class="box"></span> Reparo em Execução &nbsp; ___/___/___</div>
                                                <div class="check-item"><span class="box"></span> Teste de Qualidade / Calibração &nbsp; ___/___/___</div>
                                                <div class="check-item"><span class="box"></span> Liberação para Estoque &nbsp; ___/___/___</div>
                                            </div>
                                        </div>

                                        <div class="secao">
                                            <h3 class="titulo-secao">4. Materiais e Peças Utilizadas</h3>
                                            <table class="tabela-grid">
                                                <tr><th style="width: 15%;">Qtd</th><th style="width: 25%;">Código</th><th>Descrição</th></tr>
                                                <tr><td>&nbsp;</td><td></td><td></td></tr>
                                                <tr><td>&nbsp;</td><td></td><td></td></tr>
                                                <tr><td>&nbsp;</td><td></td><td></td></tr>
                                            </table>
                                        </div>

                                        <div class="secao">
                                            <h3 class="titulo-secao">5. Parecer Técnico (Resolução)</h3>
                                            <div style="height: 60px; border-bottom: 1px dotted #ccc; margin-top: 15px;"></div>
                                            <div style="height: 60px; border-bottom: 1px dotted #ccc; margin-top: 15px;"></div>
                                        </div>
                                        
                                        <div class="linha-assinatura">
                                            <div>Solicitante<br><span style="font-size: 10px; font-weight: normal;">{solicitante}</span></div>
                                            <div>Técnico Responsável<br><span style="font-size: 10px; font-weight: normal;">Assinatura</span></div>
                                            <div>Aprovação Gestor<br><span style="font-size: 10px; font-weight: normal;">Data: ___/___/___</span></div>
                                        </div>
                                    </body></html>
                                    """
                                    st.session_state['ticket_os_html'] = html_ticket
                                    st.rerun()
                                else:
                                    time.sleep(1.5)
                                    st.session_state['reset_abertura'] += 1
                                    st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("Não há itens classificados como Ativos disponíveis para manutenção.")

    # === ABA 2: OFICINA (LANÇAR ORÇAMENTO EXTERNO/INTERNO) ===
    with aba2:
        st.subheader("Fila de Diagnóstico e Orçamento")
        df_abertas = pd.DataFrame(TraceBoxClient.carregar_ordens_abertas())
        
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
                            TraceBoxClient.lancar_orcamento_oficina(row['id'], diagnostico, custo, mecanico, empresa, num_orcamento, usuario_atual)
                            st.success("Enviado para viabilidade!")
                            time.sleep(1)
                            st.rerun()

    # === ABA 3: VIABILIDADE (COM GRID DE HISTÓRICO) ===
    with aba3:
        st.subheader("Aprovação Técnica e Financeira")
        df_aprov = pd.DataFrame(TraceBoxClient.carregar_ordens_aprovacao())
        
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
                
                df_hist = pd.DataFrame(TraceBoxClient.carregar_historico_concluidas(row['ferramenta_id']))
                if not df_hist.empty:
                    st.caption(f"📚 **Histórico de Reparos Anteriores**")
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
                else: st.caption("Primeira manutenção deste ativo.")

                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("✅ Aprovar Orçamento (Iniciar Reparo)", key=f"ap_{row['id']}", type="primary"):
                    TraceBoxClient.aprovar_manutencao(row['id'], "Aprovar",usuario_atual)
                    st.rerun()
                if col_btn2.button("🗑️ Reprovar e Sucatear Ativo", key=f"re_{row['id']}"):
                    TraceBoxClient.aprovar_manutencao(row['id'], "Reprovar",usuario_atual)
                    st.rerun()

    # === ABA 4: FINALIZAÇÃO E ESTOQUE ===
    with aba4:
        st.subheader("Liberação Pós-Reparo")
        df_exec = pd.DataFrame(TraceBoxClient.carregar_ordens_execucao())
        
        if df_exec.empty: st.success("✅ Nenhum conserto em execução no momento.")
        for _, row in df_exec.iterrows():
            tag_label = f" - TAG: {row['num_tag']}" if pd.notna(row['num_tag']) and str(row['num_tag']).strip() != "" else " - (Item de Lote)"
            with st.expander(f"OS-{row['id']} | {row['codigo_ferramenta']} - {row['descricao']}{tag_label} (EM REPARO)", expanded=True):
                st.warning("⚠️ Este ativo está aprovado e na posse da oficina/fornecedor.")
                destino = st.selectbox("Após conclusão, dar entrada em qual Polo?", ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO"], key=f"f_{row['id']}")
                if st.button("✅ Confirmar Recebimento e Disponibilizar", key=f"btn_f_{row['id']}", type="primary"):
                    TraceBoxClient.finalizar_reparo_oficina(row['id'], row['ferramenta_id'], destino, usuario_atual)
                    st.success("Estoque atualizado!")
                    time.sleep(1)
                    st.rerun()
                    