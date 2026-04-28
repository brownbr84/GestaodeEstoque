# views/fiscal.py
"""
TraceBox WMS — Módulo Fiscal (NF-e modelo 55)

Suporta:
  • Remessa para Conserto  (CFOP 5915 / 6915)
  • Retorno de Conserto    (CFOP 5916 / 6916)
  • Saída Geral            (CFOP 5102 / 6102)
  • Entrada Geral          (CFOP 1102 / 2102)

CFOPs são parametrizados via tabela regras_operacao_fiscal — nunca hardcoded.

VERDADE TÉCNICA: este módulo prepara rascunhos internamente.
A emissão real junto à SEFAZ exige Certificado A1 (não incluso).
"""
import streamlit as st
import pandas as pd
from client.api_client import TraceBoxClient
from utils.danfe_pdf import _fmt_cnpj, _SUBTIPO_LABEL as _SUBTIPOS

_STATUS_CFG = {
    "RASCUNHO":       ("🟡", "Rascunho"),
    "PRONTA_EMISSAO": ("🔵", "Pronta para Emissão"),
    "PENDENTE":       ("🟡", "Pendente de Aprovação"),
    "EMITIDA":        ("🟢", "Emitida"),
    "CANCELADA":      ("🔴", "Cancelada"),
    "REJEITADA":      ("🔴", "Rejeitada"),
}

UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
       "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]


def _badge(status: str) -> str:
    icone, label = _STATUS_CFG.get(status.upper(), ("⚪", status))
    return f"{icone} {label}"


def tela_fiscal():
    st.title("🧾 Módulo Fiscal — NF-e Modelo 55")

    config  = TraceBoxClient.get_config() or {}
    perfil  = st.session_state.get("usuario_logado", {}).get("perfil", "")
    eh_aprovador = perfil in ["Admin", "Gestor"]

    fiscal_hab = config.get("fiscal_habilitado", False)
    ambiente   = (config.get("fiscal_ambiente") or "homologacao").upper()

    if not fiscal_hab:
        st.warning(
            "⚠️ **Módulo Fiscal desabilitado.** "
            "Você pode criar e gerenciar rascunhos internamente, mas a emissão real está bloqueada. "
            "Acesse **Configurações → Módulo Fiscal** para habilitar.",
            icon="🔒",
        )
    elif ambiente == "HOMOLOGACAO":
        st.info(
            "🧪 **Ambiente: HOMOLOGAÇÃO** — Nenhuma NF emitida aqui tem validade fiscal real.",
            icon="ℹ️",
        )
    else:
        st.error(
            "🚨 **Ambiente: PRODUÇÃO** — As NF-e emitidas aqui têm validade fiscal real junto à SEFAZ. "
            "A emissão exige Certificado A1 configurado e aprovação de usuário autorizado.",
            icon="🚨",
        )

    st.caption(
        "**IMPORTANTE:** Este sistema prepara e audita rascunhos internamente. "
        "A emissão real de NF-e junto à SEFAZ requer Certificado Digital A1 (não incluso). "
        "Consulte **Configurações → Módulo Fiscal**."
    )
    st.divider()

    abas = ["📋 Painel de Documentos", "📤 Saída NF-e", "📥 Entrada NF-e", "📊 Relatório de NF-e"]
    if eh_aprovador:
        abas.append("✅ Aprovação")
    tabs = st.tabs(abas)

    # ══════════════════════════════════════════════════════════════════
    # ABA 0 — PAINEL
    # ══════════════════════════════════════════════════════════════════
    with tabs[0]:
        _aba_painel(eh_aprovador)

    # ══════════════════════════════════════════════════════════════════
    # ABA 1 — SAÍDA NF-e (Remessa Conserto ou Saída Geral)
    # ══════════════════════════════════════════════════════════════════
    with tabs[1]:
        subtipo_saida = st.radio(
            "Tipo de Saída",
            ["REMESSA_CONSERTO", "SAIDA_GERAL"],
            format_func=lambda s: _SUBTIPOS.get(s, s),
            horizontal=True,
            key="radio_subtipo_saida",
        )
        st.divider()
        _aba_nova_nf(subtipo=subtipo_saida, config=config)

    # ══════════════════════════════════════════════════════════════════
    # ABA 2 — ENTRADA NF-e (Retorno Conserto ou Entrada Geral)
    # ══════════════════════════════════════════════════════════════════
    with tabs[2]:
        subtipo_entrada = st.radio(
            "Tipo de Entrada",
            ["RETORNO_CONSERTO", "ENTRADA_GERAL"],
            format_func=lambda s: _SUBTIPOS.get(s, s),
            horizontal=True,
            key="radio_subtipo_entrada",
        )
        st.divider()
        _aba_nova_nf(subtipo=subtipo_entrada, config=config)

    # ══════════════════════════════════════════════════════════════════
    # ABA 3 — RELATÓRIO DE NF-e
    # ══════════════════════════════════════════════════════════════════
    with tabs[3]:
        _aba_relatorio()

    # ══════════════════════════════════════════════════════════════════
    # ABA 4 — APROVAÇÃO (somente Admin / Gestor)
    # ══════════════════════════════════════════════════════════════════
    if eh_aprovador and len(tabs) > 4:
        with tabs[4]:
            _aba_aprovacao()


# ─────────────────────────────────────────────────────────────────────────────
# PAINEL DE DOCUMENTOS
# ─────────────────────────────────────────────────────────────────────────────

def _aba_painel(_eh_aprovador: bool):
    st.subheader("Documentos Fiscais")
    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        filtro = st.selectbox("Status", ["RASCUNHO", "EMITIDA", "CANCELADA", "REJEITADA", "TODOS"])
    with c2:
        st.write("")
        if st.button("🔄 Atualizar", use_container_width=True):
            st.rerun()

    todos = TraceBoxClient.listar_documentos_fiscais("TODOS" if filtro == "TODOS" else filtro)

    if not todos:
        st.info("Nenhum documento encontrado.")
        return

    df = pd.DataFrame([{
        "ID":           d["id"],
        "Subtipo":      _SUBTIPOS.get(d.get("subtipo", ""), d.get("subtipo", "")),
        "CFOP":         d.get("cfop", ""),
        "Status":       _badge(d.get("status", "")),
        "Parceiro":     (d.get("parceiro_snapshot") or {}).get("razao_social", "—"),
        "Valor Total":  f"R$ {d.get('valor_total', 0):,.2f}",
        "Criado por":   d.get("criado_por", ""),
        "Criado em":    (d.get("criado_em") or "")[:16],
    } for d in todos])
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()
    c_sel, c_pdf = st.columns([3, 1])
    with c_sel:
        sel_id = st.selectbox("Selecione para ver detalhes", [str(d["id"]) for d in todos])
    doc = next((d for d in todos if str(d["id"]) == sel_id), None)
    if doc:
        with c_pdf:
            st.write("")
            _botao_pdf(doc["id"])


# ─────────────────────────────────────────────────────────────────────────────
# FORMULÁRIO DE NOVA NF-e (por subtipo)
# ─────────────────────────────────────────────────────────────────────────────

def _aba_nova_nf(subtipo: str, config: dict):
    titulo = _SUBTIPOS.get(subtipo, subtipo)
    st.subheader(f"Nova NF-e — {titulo}")

    # ── Painel do último documento criado nesta aba ───────────────────
    _ultimo_key = f"nf_ultimo_doc_{subtipo}"
    ultimo_doc_id = st.session_state.get(_ultimo_key)
    if ultimo_doc_id:
        with st.container(border=True):
            st.success(f"✅ Documento **#{ultimo_doc_id}** criado com sucesso!")
            pa, pb, pc = st.columns(3)
            with pa:
                _botao_pdf(ultimo_doc_id, ctx="_pos")
            with pb:
                if st.button("📧 Enviar por E-mail", key=f"nf_sendemail_{ultimo_doc_id}",
                             use_container_width=True):
                    with st.spinner("Enviando e-mail…"):
                        ok_e, msg_e = TraceBoxClient.enviar_email_nf(ultimo_doc_id)
                    if ok_e:
                        st.success(msg_e)
                    else:
                        st.error(f"Erro: {msg_e}")
            with pc:
                if st.button("✏️ Criar Nova NF-e", key=f"nf_nova_btn_{subtipo}",
                             use_container_width=True):
                    st.session_state.pop(_ultimo_key, None)
                    st.rerun()
        st.divider()

    cfop_info = {
        "REMESSA_CONSERTO": "CFOP **5915** (interna) / **6915** (interestadual) — parametrizado automaticamente",
        "RETORNO_CONSERTO": "CFOP **5916** (interna) / **6916** (interestadual) — parametrizado automaticamente",
        "SAIDA_GERAL":      "CFOP **5102** / **6102** — parametrizado conforme regra cadastrada",
        "ENTRADA_GERAL":    "CFOP **1102** / **2102** — parametrizado conforme regra cadastrada",
    }
    st.info(cfop_info.get(subtipo, ""), icon="📋")

    # ── Parceiro ──────────────────────────────────────────────────────
    st.write("#### 1. Parceiro")
    parceiros = TraceBoxClient.listar_parceiros()
    if not parceiros:
        st.warning("Nenhum parceiro cadastrado. Acesse o menu **👥 Parceiros** para cadastrar.")
        return

    tipo_parceiro = "FORNECEDOR" if subtipo == "ENTRADA_GERAL" else "CLIENTE"
    opcoes_parceiros = [
        p for p in parceiros
        if p.get("tipo") in (tipo_parceiro, "AMBOS") or True  # mostra todos
    ]

    parc_labels = {
        p["id"]: f"{p['razao_social']}" + (f" ({_fmt_cnpj(p.get('cnpj',''))})" if p.get("cnpj") else "")
        for p in opcoes_parceiros
    }
    parc_ids = list(parc_labels.keys())
    parc_sel = st.selectbox(
        "Selecione o Parceiro *",
        parc_ids,
        format_func=lambda i: parc_labels.get(i, str(i)),
        key=f"parc_{subtipo}",
    )
    parceiro_sel = next((p for p in opcoes_parceiros if p["id"] == parc_sel), {})

    if parceiro_sel:
        st.caption(
            f"📍 {parceiro_sel.get('municipio', '—')}/{parceiro_sel.get('uf', '—')} &nbsp;|&nbsp; "
            f"IE: {parceiro_sel.get('ie') or '—'} &nbsp;|&nbsp; "
            f"Regime: {parceiro_sel.get('regime_tributario', '')}"
        )

    # ── Remessa vinculada (somente Retorno de Conserto) ────────────────
    remessa_vinculada_id = None
    if subtipo == "RETORNO_CONSERTO":
        st.write("#### 2. Remessa para Conserto de Origem (opcional)")
        remessas = TraceBoxClient.listar_remessas_abertas()
        if remessas:
            rem_labels = {
                r["id"]: (
                    f"Doc #{r['id']} — "
                    f"{(r.get('parceiro_snapshot') or {}).get('razao_social', '?')} — "
                    f"R$ {r.get('valor_total', 0):,.2f} — {(r.get('criado_em') or '')[:10]}"
                )
                for r in remessas
            }
            rem_ids = [None] + list(rem_labels.keys())
            rem_sel = st.selectbox(
                "Vincular à Remessa para Conserto",
                rem_ids,
                format_func=lambda i: "— Nenhuma (retorno sem vínculo) —" if i is None else rem_labels.get(i, str(i)),
                key=f"remessa_{subtipo}",
            )
            remessa_vinculada_id = rem_sel
        else:
            st.caption("Nenhuma remessa em aberto para vincular.")

    # ── Informações operacionais (OS / Patrimônio / Série) ────────────
    _is_conserto = subtipo in ("REMESSA_CONSERTO", "RETORNO_CONSERTO")
    _sec_bem = "3" if subtipo == "RETORNO_CONSERTO" else "2"
    num_os = ""
    asset_tag = ""
    num_serie = ""
    if _is_conserto:
        st.write(f"#### {_sec_bem}. Identificação do Bem")
        co1, co2, co3 = st.columns(3)
        with co1:
            num_os    = st.text_input("Nº da OS", key=f"os_{subtipo}",
                                      placeholder="Ex: OS-2024-001")
        with co2:
            asset_tag = st.text_input("Tag / Patrimônio", key=f"tag_{subtipo}",
                                      placeholder="Ex: PAT-00123")
        with co3:
            num_serie = st.text_input("Nº de Série", key=f"serie_bem_{subtipo}",
                                      placeholder="Ex: SN123456789")
        st.caption(
            "ℹ️ Estes campos serão incluídos nas informações complementares (infCpl) da NF-e. "
            "ICMS CST 41 · IPI CST 53 · PIS/COFINS CST 07 aplicados automaticamente."
        )

    # ── Configurações da NF ────────────────────────────────────────────
    _sec_conf = str(int(_sec_bem) + 1) if _is_conserto else "2"
    st.write(f"#### {_sec_conf}. Configuração e Itens")

    serie_conf = config.get("fiscal_serie", "1")
    c_serie, c_frete, c_obs = st.columns([1, 1, 3])
    with c_serie:
        serie = st.text_input("Série", value=serie_conf, key=f"serie_{subtipo}")
    with c_frete:
        mod_frete = st.selectbox(
            "Frete",
            options=["9", "0", "1", "2"],
            format_func=lambda x: {"9": "9 - Sem frete", "0": "0 - Por conta emitente",
                                    "1": "1 - Por conta destinatário", "2": "2 - Terceiros"}.get(x, x),
            key=f"frete_{subtipo}",
        )
    with c_obs:
        observacao = st.text_input(
            "Observação / Referência",
            key=f"obs_{subtipo}",
            placeholder="Referência interna, nota de origem, etc.",
        )

    # ── Seleção de itens (estilo outbound) ────────────────────────────
    _cart_key    = f"nf_carrinho_{subtipo}"
    _results_key = f"nf_resultados_{subtipo}"
    if _cart_key not in st.session_state:
        st.session_state[_cart_key] = []
    if _results_key not in st.session_state:
        st.session_state[_results_key] = []

    st.write(f"#### {str(int(_sec_conf) + 1) if _is_conserto else '3'}. Produtos da Nota Fiscal")

    # Busca
    col_busca, col_btn_busca = st.columns([4, 1])
    with col_busca:
        termo_busca = st.text_input(
            "Buscar produto do catálogo",
            key=f"nf_termo_{subtipo}",
            placeholder="Digite código ou descrição…",
        )
    with col_btn_busca:
        st.write("")
        if st.button("🔍 Buscar", key=f"nf_buscar_{subtipo}", use_container_width=True):
            with st.spinner("Buscando…"):
                st.session_state[_results_key] = TraceBoxClient.buscar_produtos_fiscal(termo_busca)

    resultados = st.session_state[_results_key]

    if resultados:
        prod_labels = {
            p["codigo"]: (
                f"{p['codigo']} — {p['descricao']}"
                + (f"  [NCM: {p['ncm']}]" if p.get("ncm") else "")
                + (f"  R$ {p['valor_unitario']:.2f}" if p.get("valor_unitario") else "")
            )
            for p in resultados
        }
        prod_sel_cod = st.selectbox(
            "Produto encontrado",
            list(prod_labels.keys()),
            format_func=lambda c: prod_labels.get(c, c),
            key=f"nf_prod_sel_{subtipo}",
        )
        prod_sel = next((p for p in resultados if p["codigo"] == prod_sel_cod), None)

        if prod_sel:
            cp1, cp2, cp3, cp4, cp5 = st.columns([2, 2, 2, 1, 1])
            with cp1:
                is_tag = "TAG" in (prod_sel.get("tipo_controle") or "").upper()
                tags_disp = prod_sel.get("tags_disponiveis") or []
                if is_tag and tags_disp:
                    tag_item = st.selectbox(
                        "TAG disponível",
                        ["(sem TAG)"] + tags_disp,
                        key=f"nf_tag_{subtipo}",
                    )
                    tag_item = "" if tag_item == "(sem TAG)" else tag_item
                else:
                    tag_item = ""
                    st.caption(f"Tipo: {prod_sel.get('tipo_controle','—')} · "
                               f"{len(tags_disp)} TAG(s) disponível(is)" if is_tag else
                               f"Tipo: {prod_sel.get('tipo_controle','—')}")
            with cp2:
                ncm_item = st.text_input(
                    "NCM",
                    value=prod_sel.get("ncm") or "",
                    key=f"nf_ncm_{subtipo}",
                    placeholder="00000000",
                )
            with cp3:
                cest_item = st.text_input(
                    "CEST",
                    value=prod_sel.get("cest") or "",
                    key=f"nf_cest_{subtipo}",
                    placeholder="0000000",
                    help="Obrigatório apenas quando há Substituição Tributária",
                )
            with cp4:
                qty_item = st.number_input(
                    "Qtd",
                    min_value=0.001,
                    value=1.0,
                    format="%.3f",
                    key=f"nf_qty_{subtipo}",
                )
            with cp5:
                vu_item = st.number_input(
                    "Vl. Unit. (R$)",
                    min_value=0.0,
                    value=float(prod_sel.get("valor_unitario") or 0.0),
                    format="%.2f",
                    key=f"nf_vu_{subtipo}",
                )

            if st.button("➕ Adicionar ao Carrinho", key=f"nf_add_{subtipo}"):
                if not prod_sel_cod:
                    st.warning("Selecione um produto antes de adicionar.")
                elif vu_item <= 0:
                    st.warning("Informe o valor unitário do item.")
                else:
                    st.session_state[_cart_key].append({
                        "codigo":       prod_sel_cod,
                        "descricao":    prod_sel["descricao"],
                        "ncm":          ncm_item.strip(),
                        "cest":         cest_item.strip(),
                        "quantidade":   qty_item,
                        "valor_unitario": vu_item,
                        "orig_icms":    prod_sel.get("orig_icms", "0"),
                        "c_ean":        prod_sel.get("c_ean", "SEM GTIN"),
                        "num_tag":      tag_item,
                    })
                    st.rerun()
    elif termo_busca:
        st.caption("Nenhum produto encontrado. Verifique o código ou descrição.")
    else:
        st.caption("Use a busca acima para encontrar produtos do catálogo.")

    # Carrinho
    carrinho = st.session_state[_cart_key]
    if carrinho:
        st.write(f"**🛒 Itens no carrinho: {len(carrinho)}**")
        for i, item in enumerate(carrinho):
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.5, 3, 1, 1.5, 0.5])
            with cc1:
                tag_label = f" [{item['num_tag']}]" if item.get("num_tag") else ""
                st.caption(f"**{item['codigo']}**{tag_label}")
            with cc2:
                st.caption(item["descricao"][:50])
            with cc3:
                st.caption(f"Qtd: {item['quantidade']:.3f}")
            with cc4:
                vt = item["quantidade"] * item["valor_unitario"]
                st.caption(f"R$ {vt:,.2f}")
            with cc5:
                if st.button("🗑️", key=f"nf_rm_{subtipo}_{i}", help="Remover item"):
                    st.session_state[_cart_key].pop(i)
                    st.rerun()
        vl_cart = sum(it["quantidade"] * it["valor_unitario"] for it in carrinho)
        st.caption(f"**Total estimado: R$ {vl_cart:,.2f}**")
    else:
        st.info("Carrinho vazio. Adicione produtos usando a busca acima.")

    # Importar itens de OS ou Requisição concluída (apenas conserto)
    if _is_conserto:
        with st.expander("📦 Importar de OS / Requisição concluída"):
            fonte = st.radio(
                "Fonte de importação",
                ["OS Concluída", "Requisição Concluída (Outbound)"],
                horizontal=True,
                key=f"import_fonte_{subtipo}",
            )

            if fonte == "OS Concluída":
                with st.spinner("Carregando OS…"):
                    lista_os = TraceBoxClient.listar_os_para_nf()
                if not lista_os:
                    st.info("Nenhuma OS com status 'Concluída' encontrada.")
                else:
                    os_labels = {
                        o["id"]: (
                            f"OS #{o['num_os']} — {o['descricao'][:40]}"
                            + (f" [{o['asset_tag']}]" if o.get("asset_tag") else "")
                            + f" — R$ {o['custo_reparo']:,.2f}"
                        )
                        for o in lista_os
                    }
                    os_sel_id = st.selectbox(
                        "Selecionar OS",
                        list(os_labels.keys()),
                        format_func=lambda i: os_labels.get(i, str(i)),
                        key=f"os_import_sel_{subtipo}",
                    )
                    os_sel = next((o for o in lista_os if o["id"] == os_sel_id), None)
                    if os_sel:
                        col_oi1, col_oi2 = st.columns(2)
                        with col_oi1:
                            oi_vu = st.number_input(
                                "Valor unitário (R$)",
                                value=float(os_sel.get("custo_reparo") or os_sel.get("valor_unitario") or 0.0),
                                min_value=0.0, format="%.2f",
                                key=f"os_vu_{subtipo}",
                            )
                        with col_oi2:
                            oi_ncm = st.text_input(
                                "NCM",
                                value=os_sel.get("ncm") or "",
                                placeholder="00000000",
                                key=f"os_ncm_{subtipo}",
                            )
                        if st.button("➕ Importar OS para o carrinho", key=f"os_import_add_{subtipo}"):
                            st.session_state[_cart_key].append({
                                "codigo":         os_sel.get("codigo_ferramenta") or f"OS-{os_sel['num_os']}",
                                "descricao":      os_sel["descricao"],
                                "ncm":            oi_ncm.strip(),
                                "cest":           os_sel.get("cest") or "",
                                "quantidade":     1.0,
                                "valor_unitario": oi_vu,
                                "orig_icms":      os_sel.get("orig_icms", "0"),
                                "c_ean":          os_sel.get("c_ean", "SEM GTIN"),
                                "num_tag":        os_sel.get("asset_tag", ""),
                                "_os_id":         os_sel["id"],
                            })
                            st.rerun()

            else:  # Requisição Concluída
                with st.spinner("Carregando requisições…"):
                    lista_reqs = TraceBoxClient.listar_requisicoes_para_nf()
                if not lista_reqs:
                    st.info("Nenhuma requisição com status 'Concluída' encontrada.")
                else:
                    req_labels = {
                        r["id"]: (
                            f"REQ-{r['id']:04d} — {r['solicitante']} → {r['destino_projeto']}"
                            + (f" ({(r.get('data_solicitacao') or '')[:10]})" if r.get("data_solicitacao") else "")
                            + f" [{len(r.get('itens', []))} item(ns)]"
                        )
                        for r in lista_reqs
                    }
                    req_sel_id = st.selectbox(
                        "Selecionar Requisição",
                        list(req_labels.keys()),
                        format_func=lambda i: req_labels.get(i, str(i)),
                        key=f"req_import_sel_{subtipo}",
                    )
                    req_sel = next((r for r in lista_reqs if r["id"] == req_sel_id), None)
                    if req_sel and req_sel.get("itens"):
                        st.caption(f"**{len(req_sel['itens'])} item(ns) nesta requisição:**")
                        for it in req_sel["itens"]:
                            st.caption(
                                f"• {it['codigo']} — {it['descricao']} "
                                f"(Qtd: {it['quantidade']:.0f} | R$ {it['valor_unitario']:.2f})"
                            )
                        if st.button("➕ Importar todos os itens da requisição", key=f"req_import_add_{subtipo}"):
                            for it in req_sel["itens"]:
                                st.session_state[_cart_key].append({
                                    "codigo":         it["codigo"],
                                    "descricao":      it["descricao"],
                                    "ncm":            it.get("ncm") or "",
                                    "cest":           it.get("cest") or "",
                                    "quantidade":     float(it.get("quantidade") or 1),
                                    "valor_unitario": float(it.get("valor_unitario") or 0),
                                    "orig_icms":      it.get("orig_icms", "0"),
                                    "c_ean":          it.get("c_ean", "SEM GTIN"),
                                    "num_tag":        "",
                                    "_req_id":        req_sel["id"],
                                })
                            st.rerun()

    # Importar itens de XML de NF-e (apenas entrada)
    if subtipo in ("RETORNO_CONSERTO", "ENTRADA_GERAL"):
        with st.expander("📂 Importar itens de XML de NF-e"):
            xml_file = st.file_uploader(
                "Selecione o arquivo XML da NF-e",
                type=["xml"],
                key=f"xml_upload_{subtipo}",
            )
            if xml_file is not None:
                try:
                    import xml.etree.ElementTree as _ET
                    tree = _ET.parse(xml_file)
                    root = tree.getroot()
                    itens_xml = []
                    for det in root.iter("{http://www.portalfiscal.inf.br/nfe}det"):
                        prod = det.find("{http://www.portalfiscal.inf.br/nfe}prod")
                        if prod is None:
                            continue
                        def _txt(tag: str) -> str:
                            el = prod.find(f"{{http://www.portalfiscal.inf.br/nfe}}{tag}")
                            return (el.text or "") if el is not None else ""
                        itens_xml.append({
                            "codigo":         _txt("cProd"),
                            "descricao":      _txt("xProd"),
                            "ncm":            _txt("NCM"),
                            "cest":           _txt("CEST"),
                            "c_ean":          _txt("cEAN") or "SEM GTIN",
                            "quantidade":     float(_txt("qCom") or 1),
                            "valor_unitario": float(_txt("vUnCom") or 0),
                            "orig_icms":      "0",
                            "num_tag":        "",
                        })
                    if itens_xml:
                        st.success(f"{len(itens_xml)} item(ns) encontrado(s) no XML.")
                        if st.button("➕ Adicionar todos ao carrinho", key=f"xml_add_{subtipo}"):
                            st.session_state[_cart_key].extend(itens_xml)
                            st.rerun()
                    else:
                        st.warning("Nenhum item encontrado no XML.")
                except Exception as _e:
                    st.error(f"Erro ao processar XML: {_e}")

    # Entrada manual (produtos não cadastrados)
    with st.expander("✏️ Adicionar item sem cadastro (manual)"):
        cm1, cm2, cm3, cm4, cm5 = st.columns([2, 3, 1, 1, 1])
        with cm1: m_cod  = st.text_input("Código",    key=f"m_cod_{subtipo}",  placeholder="SKU")
        with cm2: m_desc = st.text_input("Descrição", key=f"m_dsc_{subtipo}",  placeholder="Nome do produto")
        with cm3: m_ncm  = st.text_input("NCM",       key=f"m_ncm_{subtipo}",  placeholder="00000000")
        with cm4: m_qty  = st.number_input("Qtd",     key=f"m_qty_{subtipo}",  min_value=0.001, value=1.0, format="%.3f")
        with cm5: m_vu   = st.number_input("Vl. Unit",key=f"m_vu_{subtipo}",   min_value=0.0,   value=0.0, format="%.2f")
        if st.button("➕ Adicionar manual", key=f"nf_add_manual_{subtipo}"):
            if not m_cod or not m_desc:
                st.warning("Código e descrição são obrigatórios.")
            elif m_vu <= 0:
                st.warning("Informe o valor unitário.")
            else:
                st.session_state[_cart_key].append({
                    "codigo": m_cod.strip(), "descricao": m_desc.strip(),
                    "ncm": m_ncm.strip(), "quantidade": m_qty, "valor_unitario": m_vu,
                    "orig_icms": "0", "c_ean": "SEM GTIN", "num_tag": "",
                })
                st.rerun()

    st.divider()
    if st.button(f"📤 Criar Rascunho — {titulo}", type="primary",
                 use_container_width=True, key=f"btn_{subtipo}"):
        erros = []
        if not parc_sel:
            erros.append("Selecione um parceiro.")
        if not carrinho:
            erros.append("Adicione ao menos um item ao carrinho.")

        if erros:
            for e in erros:
                st.error(f"❌ {e}")
        else:
            itens_api = [
                {
                    "codigo":         it["codigo"],
                    "descricao":      it["descricao"],
                    "ncm":            it.get("ncm", ""),
                    "cest":           it.get("cest", ""),
                    "quantidade":     it["quantidade"],
                    "valor_unitario": it["valor_unitario"],
                    "orig_icms":      it.get("orig_icms", "0"),
                    "c_ean":          it.get("c_ean", "SEM GTIN"),
                }
                for it in carrinho
            ]
            with st.spinner("Criando rascunho…"):
                ok, msg, doc_id = TraceBoxClient.criar_documento_fiscal(
                    subtipo=subtipo,
                    parceiro_id=parc_sel,
                    itens=itens_api,
                    serie=serie,
                    observacao=observacao,
                    doc_vinculado_id=remessa_vinculada_id,
                    num_os=num_os,
                    asset_tag=asset_tag,
                    num_serie=num_serie,
                    mod_frete=mod_frete,
                )
            if ok:
                st.session_state[_cart_key] = []
                st.session_state[_results_key] = []
                st.session_state[_ultimo_key] = doc_id
                st.rerun()
            else:
                st.error(f"❌ {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# APROVAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def _aba_aprovacao():
    st.subheader("Aprovação de Documentos Fiscais")
    st.caption("Somente Admin e Gestor podem emitir ou cancelar rascunhos.")

    rascunhos = TraceBoxClient.listar_documentos_fiscais("RASCUNHO")
    if not rascunhos:
        st.success("✅ Nenhum rascunho pendente de aprovação.")
        return

    for doc in rascunhos:
        parc_snap = doc.get("parceiro_snapshot") or {}
        with st.container(border=True):
            col_info, col_acoes = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f"**Doc #{doc['id']}** — "
                    f"{_SUBTIPOS.get(doc.get('subtipo',''), doc.get('subtipo',''))} — "
                    f"CFOP {doc.get('cfop','?')}"
                )
                st.caption(
                    f"Parceiro: **{parc_snap.get('razao_social','?')}** — "
                    f"CNPJ: {_fmt_cnpj(parc_snap.get('cnpj',''))} | "
                    f"Valor: **R$ {doc.get('valor_total', 0):,.2f}** | "
                    f"Criado por {doc.get('criado_por','?')} em {(doc.get('criado_em') or '')[:16]}"
                )
                if doc.get("doc_vinculado_id"):
                    st.caption(f"🔗 Vinculado à Remessa #{doc['doc_vinculado_id']}")
                nat = doc.get("natureza_operacao")
                if nat:
                    st.caption(f"Natureza: {nat}")

            with col_acoes:
                with st.popover("✅ Emitir"):
                    st.warning(
                        "Confirme que esta NF foi processada. "
                        "A transmissão real à SEFAZ requer Certificado A1.",
                        icon="⚠️",
                    )
                    nf_num = st.text_input("Número da NF", key=f"nf_{doc['id']}")
                    chave  = st.text_input("Chave de Acesso", key=f"chave_{doc['id']}")
                    prot   = st.text_input("Protocolo SEFAZ", key=f"prot_{doc['id']}")
                    if st.button("Confirmar Emissão", key=f"emit_{doc['id']}", type="primary"):
                        ok, msg = TraceBoxClient.aprovar_documento_fiscal(
                            doc["id"], nf_num, chave, prot
                        )
                        if ok:
                            st.success(msg)
                            import time; time.sleep(1); st.rerun()
                        else:
                            st.error(msg)

                with st.popover("❌ Cancelar"):
                    motivo = st.text_input("Motivo *", key=f"mot_{doc['id']}")
                    if st.button("Confirmar Cancelamento", key=f"cancel_{doc['id']}", type="primary"):
                        if not motivo.strip():
                            st.error("Informe o motivo.")
                        else:
                            ok, msg = TraceBoxClient.cancelar_documento_fiscal(doc["id"], motivo)
                            if ok:
                                st.success(msg)
                                import time; time.sleep(1); st.rerun()
                            else:
                                st.error(msg)


def _aba_relatorio():
    st.subheader("Relatório de Notas Fiscais")

    from datetime import date as _date
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        filtro_status = st.multiselect(
            "Status",
            ["RASCUNHO", "EMITIDA", "CANCELADA", "REJEITADA"],
            default=["RASCUNHO", "EMITIDA", "CANCELADA", "REJEITADA"],
            key="rel_status",
        )
    with c2:
        dt_inicio = st.date_input("De", value=None, key="rel_dt_ini")
    with c3:
        dt_fim = st.date_input("Até", value=None, key="rel_dt_fim")
    with c4:
        st.write("")
        carregar = st.button("🔍 Carregar", use_container_width=True, key="rel_carregar")

    if not carregar:
        st.caption("Selecione os filtros e clique em **Carregar** para exibir os documentos.")
        return

    if not filtro_status:
        st.warning("Selecione ao menos um status.")
        return

    with st.spinner("Carregando documentos…"):
        if len(filtro_status) == 4:
            todos = TraceBoxClient.listar_documentos_fiscais("TODOS")
        else:
            todos = []
            for s in filtro_status:
                todos.extend(TraceBoxClient.listar_documentos_fiscais(s))

    # Filtro por data (client-side)
    if dt_inicio:
        todos = [d for d in todos if (d.get("criado_em") or "")[:10] >= str(dt_inicio)]
    if dt_fim:
        todos = [d for d in todos if (d.get("criado_em") or "")[:10] <= str(dt_fim)]

    if not todos:
        st.info("Nenhum documento encontrado com os filtros selecionados.")
        return

    # Métricas resumo
    m1, m2, m3, m4 = st.columns(4)
    emitidas   = [d for d in todos if d.get("status") == "EMITIDA"]
    canceladas = [d for d in todos if d.get("status") == "CANCELADA"]
    vl_emitido = sum(d.get("valor_total", 0) for d in emitidas)
    m1.metric("Total de documentos", len(todos))
    m2.metric("Emitidas",            len(emitidas))
    m3.metric("Canceladas",          len(canceladas))
    m4.metric("Valor total emitido",  f"R$ {vl_emitido:,.2f}")

    df = pd.DataFrame([{
        "ID":          d["id"],
        "Subtipo":     _SUBTIPOS.get(d.get("subtipo", ""), d.get("subtipo", "")),
        "CFOP":        d.get("cfop", ""),
        "Status":      _badge(d.get("status", "")),
        "Parceiro":    (d.get("parceiro_snapshot") or {}).get("razao_social", "—"),
        "Valor Total": f"R$ {d.get('valor_total', 0):,.2f}",
        "NF Nº":       d.get("numero") or "—",
        "OS":          d.get("num_os") or "—",
        "Tag":         d.get("asset_tag") or "—",
        "Criado por":  d.get("criado_por", ""),
        "Criado em":   (d.get("criado_em") or "")[:16],
        "Aprovado por": d.get("aprovado_por") or "—",
    } for d in todos])
    st.dataframe(df, hide_index=True, use_container_width=True)


def _botao_pdf(doc_id: int, ctx: str = ""):
    """Botão de download do DANFE-Rascunho em PDF. ctx evita chave duplicada entre contextos."""
    key = f"pdf_btn_{doc_id}{ctx}"
    if st.button("🖨️ Baixar PDF (DANFE)", key=key, use_container_width=True):
        with st.spinner("Gerando PDF…"):
            pdf_bytes = TraceBoxClient.baixar_pdf_documento_fiscal(doc_id)
        if pdf_bytes:
            st.download_button(
                label="⬇️ Clique para salvar",
                data=pdf_bytes,
                file_name=f"DANFE_Rascunho_{doc_id:05d}.pdf",
                mime="application/pdf",
                key=f"dl_{doc_id}",
                use_container_width=True,
            )
        else:
            st.error("Falha ao gerar o PDF.")


