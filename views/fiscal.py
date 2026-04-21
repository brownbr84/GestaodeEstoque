# views/fiscal.py
"""
TraceBox WMS — Módulo Fiscal (NF-e)

VERDADE TÉCNICA:
  - Backend: pronto internamente (rascunho, payload, auditoria, aprovação humana)
  - Integração SEFAZ: pendente por design — exige Certificado A1 e infra paga
  - Este módulo NÃO emite NF-e real. Prepara e gerencia rascunhos.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from client.api_client import TraceBoxClient


# ── Helpers de status ──────────────────────────────────────────────────────
_STATUS_CONFIG = {
    "PENDENTE":   {"cor": "🟡", "label": "Pendente de Aprovação",  "badge": "orange"},
    "EMITIDA":    {"cor": "🟢", "label": "Emitida / Aprovada",     "badge": "green"},
    "CANCELADA":  {"cor": "🔴", "label": "Cancelada",              "badge": "red"},
    "REJEITADA":  {"cor": "🔴", "label": "Rejeitada",              "badge": "red"},
}

def _badge(status: str) -> str:
    cfg = _STATUS_CONFIG.get(status.upper(), {"cor": "⚪", "label": status})
    return f"{cfg['cor']} {cfg['label']}"


def tela_fiscal():
    st.title("🧾 Módulo Fiscal — NF-e")

    config = TraceBoxClient.get_config() or {}
    perfil = st.session_state.get("usuario_logado", {}).get("perfil", "")
    eh_aprovador = perfil in ["Admin", "Gestor", "Fiscal"]

    # ── Banner de status da integração SEFAZ ──────────────────────────────
    fiscal_hab = config.get("fiscal_habilitado", False)
    ambiente   = config.get("fiscal_ambiente", "homologacao").upper()

    if not fiscal_hab:
        st.warning(
            "⚠️ **Módulo Fiscal desabilitado.** "
            "Você pode criar e gerenciar rascunhos internamente, mas a emissão real está bloqueada. "
            "Acesse **Configurações → Módulo Fiscal** para habilitar.",
            icon="🔒"
        )
    else:
        if ambiente == "HOMOLOGACAO":
            st.info(
                "🧪 **Ambiente: HOMOLOGAÇÃO** — Nenhuma NF emitida aqui tem validade fiscal real. "
                "Para produção, configure em Configurações → Módulo Fiscal.",
                icon="ℹ️"
            )
        else:
            st.error(
                "🚨 **Ambiente: PRODUÇÃO** — As NF-e emitidas aqui têm validade fiscal real junto à SEFAZ. "
                "A emissão exige Certificado A1 configurado e aprovação de usuário autorizado.",
                icon="🚨"
            )

    st.caption(
        "**IMPORTANTE:** Este sistema prepara e audita rascunhos internamente. "
        "A emissão real de NF-e junto à SEFAZ requer Certificado Digital A1 (não incluído). "
        "Consulte Configurações → Módulo Fiscal."
    )
    st.divider()

    # ── Abas ──────────────────────────────────────────────────────────────
    abas = ["📋 Rascunhos / Painel", "➕ Nova NF-e"]
    if eh_aprovador:
        abas.append("✅ Aprovação")
    tabs = st.tabs(abas)

    # ══════════════════════════════════════════════════════════════════════
    # ABA 1: PAINEL DE RASCUNHOS
    # ══════════════════════════════════════════════════════════════════════
    with tabs[0]:
        st.subheader("Painel de Notas Fiscais")
        c_filtro1, c_filtro2, _ = st.columns([1, 1, 2])
        with c_filtro1:
            filtro_status = st.selectbox("Filtrar por Status", ["PENDENTE", "EMITIDA", "CANCELADA", "REJEITADA", "TODOS"])
        with c_filtro2:
            if st.button("🔄 Atualizar", use_container_width=True):
                st.rerun()

        status_busca = None if filtro_status == "TODOS" else filtro_status
        todos = []
        for s in (["PENDENTE", "EMITIDA", "CANCELADA", "REJEITADA"] if status_busca is None else [status_busca]):
            todos.extend(TraceBoxClient.listar_rascunhos_nf(s))

        if not todos:
            st.info("Nenhuma NF-e encontrada para o filtro selecionado.")
        else:
            # Tabela resumo
            df = pd.DataFrame([{
                "ID":        r["id"],
                "Tipo":      r["tipo_operacao"],
                "Status":    _badge(r["status"]),
                "Criado por": r["criado_por"],
                "Criado em": r["criado_em"][:16] if r.get("criado_em") else "",
                "Aprovado por": r.get("aprovado_por") or "—",
                "NF Nº":     r.get("numero_nf") or "—",
            } for r in todos])
            st.dataframe(df, hide_index=True, use_container_width=True)

            st.divider()
            st.subheader("Detalhe / Timeline")
            ids_disponiveis = [str(r["id"]) for r in todos]
            sel_id = st.selectbox("Selecione o Rascunho para ver detalhes", ids_disponiveis)

            rascunho = next((r for r in todos if str(r["id"]) == sel_id), None)
            if rascunho:
                _renderizar_detalhe(rascunho, eh_aprovador)

    # ══════════════════════════════════════════════════════════════════════
    # ABA 2: NOVA NF-e
    # ══════════════════════════════════════════════════════════════════════
    with tabs[1]:
        st.subheader("Criar Rascunho de NF-e")
        st.info(
            "Preencha os dados abaixo para criar um rascunho. "
            "O rascunho ficará com status **PENDENTE** até que um usuário autorizado (Admin / Gestor) "
            "o aprove na aba **Aprovação**. "
            "A emissão real junto à SEFAZ só ocorre após aprovação e com Certificado A1 configurado.",
            icon="📋"
        )

        with st.form("form_nova_nf"):
            st.write("#### 1. Tipo de Operação")
            tipo_op = st.radio("Tipo de NF-e", ["Saída (Venda / Remessa)", "Entrada (Compra / Devolução)"],
                               horizontal=True)
            tipo_op_api = "saida" if "Saída" in tipo_op else "entrada"

            st.write("#### 2. Destinatário / Remetente")
            c1, c2 = st.columns(2)
            with c1:
                dest_cnpj = st.text_input("CNPJ *", placeholder="00.000.000/0001-00")
                dest_nome = st.text_input("Razão Social *", placeholder="Nome da empresa")
                dest_logradouro = st.text_input("Logradouro", placeholder="Rua, número, complemento")
            with c2:
                dest_municipio = st.text_input("Município *", placeholder="São Paulo")
                dest_uf = st.selectbox("UF *", ["SP","RJ","MG","RS","PR","SC","BA","GO","PE","CE","PA","AM","ES","MS","MT","RN","PB","AL","SE","PI","MA","TO","RO","AC","RR","AP","DF"])
                dest_cep = st.text_input("CEP", placeholder="00000-000")

            st.write("#### 3. Mercadorias")
            st.caption("Adicione os itens da nota. NCM: 8 dígitos sem pontos.")
            num_itens = st.number_input("Quantidade de itens", min_value=1, max_value=50, value=1, step=1)

            itens = []
            for i in range(int(num_itens)):
                st.write(f"**Item {i+1}**")
                ci1, ci2, ci3, ci4, ci5 = st.columns([2, 3, 1, 1, 1])
                with ci1: cod = st.text_input("Código", key=f"cod_{i}", placeholder="SKU")
                with ci2: desc = st.text_input("Descrição", key=f"desc_{i}", placeholder="Nome do produto")
                with ci3: ncm = st.text_input("NCM", key=f"ncm_{i}", placeholder="00000000")
                with ci4: qtd = st.number_input("Qtd", key=f"qtd_{i}", min_value=0.001, value=1.0, format="%.3f")
                with ci5: vunit = st.number_input("Vl. Unit (R$)", key=f"vunit_{i}", min_value=0.0, value=0.0, format="%.2f")
                itens.append({"codigo": cod, "descricao": desc, "ncm": ncm, "quantidade": qtd, "valor_unitario": vunit})

            nf_ref = st.text_input("NF de Referência (opcional)", placeholder="Ex: 001234")

            st.divider()
            enviado = st.form_submit_button("📤 Criar Rascunho de NF-e", type="primary", use_container_width=True)

        if enviado:
            # Validações front-end
            erros = []
            import re
            cnpj_limpo = re.sub(r"\D", "", dest_cnpj)
            if len(cnpj_limpo) != 14:
                erros.append("CNPJ inválido — informe 14 dígitos.")
            if not dest_nome.strip():
                erros.append("Razão Social obrigatória.")
            if not dest_municipio.strip():
                erros.append("Município obrigatório.")
            itens_validos = [it for it in itens if it["codigo"] and it["descricao"]]
            if not itens_validos:
                erros.append("Adicione ao menos um item com código e descrição.")
            if any(it["valor_unitario"] <= 0 for it in itens_validos):
                erros.append("Valor unitário deve ser maior que zero em todos os itens.")

            if erros:
                for e in erros:
                    st.error(f"❌ {e}")
            else:
                with st.spinner("Validando dados e criando rascunho..."):
                    resultado = TraceBoxClient.preparar_nf(
                        tipo_operacao=tipo_op_api,
                        dados_mercadoria=itens_validos,
                        dados_destinatario_remetente={
                            "cnpj": dest_cnpj, "nome": dest_nome,
                            "logradouro": dest_logradouro, "municipio": dest_municipio,
                            "uf": dest_uf, "cep": dest_cep,
                        },
                        numero_nf_ref=nf_ref,
                    )

                if resultado.get("aviso"):
                    st.warning(resultado["aviso"])

                if resultado.get("sucesso"):
                    st.success(f"✅ {resultado['mensagem']}")
                    st.info(f"🔖 Rascunho **#{resultado['rascunho_id']}** criado. Aguardando aprovação na aba **Aprovação**.")
                else:
                    detalhe = resultado.get("mensagem", "Erro desconhecido.")
                    if not resultado.get("api_gratuita_disponivel"):
                        st.error("🚫 Emissão fiscal indisponível com APIs 100% gratuitas.")
                        with st.expander("Ver detalhe técnico"):
                            st.code(detalhe)
                    else:
                        st.error(f"❌ {detalhe}")

    # ══════════════════════════════════════════════════════════════════════
    # ABA 3: APROVAÇÃO (somente Admin / Gestor / Fiscal)
    # ══════════════════════════════════════════════════════════════════════
    if eh_aprovador and len(tabs) > 2:
        with tabs[2]:
            st.subheader("Aprovação de Rascunhos Pendentes")
            st.caption("Somente usuários com perfil Admin, Gestor ou Fiscal podem emitir ou cancelar rascunhos.")

            pendentes = TraceBoxClient.listar_rascunhos_nf("PENDENTE")
            if not pendentes:
                st.success("✅ Nenhum rascunho pendente de aprovação no momento.")
            else:
                for r in pendentes:
                    payload = r.get("payload", {})
                    valor_total = payload.get("vNF", 0)
                    with st.container(border=True):
                        col_info, col_acoes = st.columns([3, 1])
                        with col_info:
                            st.markdown(f"**Rascunho #{r['id']}** — {r['tipo_operacao'].upper()}")
                            st.caption(
                                f"Criado por **{r['criado_por']}** em {r['criado_em'][:16] if r.get('criado_em') else '?'} "
                                f"| Valor Total: **R$ {valor_total:,.2f}** | Itens: {len(payload.get('itens', []))}"
                            )
                            dest = payload.get("dest_rem", {})
                            st.caption(f"Destinatário: {dest.get('xNome', '?')} — CNPJ: {dest.get('CNPJ', '?')}")

                        with col_acoes:
                            with st.popover("✅ Emitir"):
                                st.warning(
                                    "**Atenção:** Marcar como EMITIDA confirma que esta nota foi "
                                    "processada. A transmissão real à SEFAZ requer Certificado A1.",
                                    icon="⚠️"
                                )
                                nf_num = st.text_input("Número da NF (opcional)", key=f"nf_num_{r['id']}")
                                chave  = st.text_input("Chave de Acesso (opcional)", key=f"chave_{r['id']}")
                                prot   = st.text_input("Protocolo SEFAZ (opcional)", key=f"prot_{r['id']}")
                                if st.button("Confirmar Emissão", key=f"emit_{r['id']}", type="primary"):
                                    ok, msg = TraceBoxClient.emitir_nf(r["id"], chave, prot, nf_num)
                                    if ok:
                                        st.success(msg)
                                        import time; time.sleep(1); st.rerun()
                                    else:
                                        st.error(msg)

                            with st.popover("❌ Cancelar"):
                                motivo_cancel = st.text_input("Motivo do cancelamento *", key=f"motivo_{r['id']}")
                                if st.button("Confirmar Cancelamento", key=f"cancel_{r['id']}", type="primary"):
                                    if not motivo_cancel.strip():
                                        st.error("Informe o motivo.")
                                    else:
                                        ok, msg = TraceBoxClient.cancelar_nf(r["id"], motivo_cancel)
                                        if ok:
                                            st.success(msg)
                                            import time; time.sleep(1); st.rerun()
                                        else:
                                            st.error(msg)


def _renderizar_detalhe(r: dict, eh_aprovador: bool):
    """Renderiza o detalhe e timeline de um rascunho."""
    payload = r.get("payload", {})
    status  = r.get("status", "")

    c1, c2, c3 = st.columns(3)
    c1.metric("Status", _badge(status))
    c2.metric("Tipo", r.get("tipo_operacao", ""))
    c3.metric("Valor Total", f"R$ {payload.get('vNF', 0):,.2f}")

    # Timeline
    st.write("**Timeline**")
    col_tl = st.columns(4)
    eventos = [
        ("Rascunho Criado", r.get("criado_em", ""), r.get("criado_por", ""), True),
        ("Aprovado / Emitido", r.get("aprovado_em") or r.get("criado_em", ""), r.get("aprovado_por", "—"), status == "EMITIDA"),
        ("Cancelado", r.get("aprovado_em") or "", r.get("aprovado_por", "—"), status == "CANCELADA"),
        ("Rejeitado", "", "—", status == "REJEITADA"),
    ]
    for col, (titulo, data, agente, ativo) in zip(col_tl, eventos):
        with col:
            cor = "✅" if ativo else "⬜"
            st.markdown(f"**{cor} {titulo}**")
            if ativo and data:
                st.caption(f"{data[:16] if data else ''}\n{agente}")

    # Destinatário
    dest = payload.get("dest_rem", {})
    if dest:
        st.write("**Destinatário / Remetente**")
        st.json(dest, expanded=False)

    # Itens
    itens = payload.get("itens", [])
    if itens:
        st.write(f"**Itens ({len(itens)})**")
        df_itens = pd.DataFrame([{
            "Item": it.get("nItem"), "Código": it.get("cProd"), "Descrição": it.get("xProd"),
            "NCM": it.get("NCM"), "Qtd": it.get("qCom"), "Vl. Unit": f"R$ {it.get('vUnCom', 0):.2f}",
            "Vl. Total": f"R$ {it.get('vProd', 0):.2f}",
        } for it in itens])
        st.dataframe(df_itens, hide_index=True, use_container_width=True)

    # NF emitida
    if status == "EMITIDA":
        st.success(f"**NF Nº:** {r.get('numero_nf') or '(não informado)'} | **Chave:** {r.get('chave_acesso') or '(pendente)'}")
