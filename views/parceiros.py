# views/parceiros.py
"""Tela de gestão de Parceiros (Clientes / Fornecedores)."""
import re
import streamlit as st
from client.api_client import TraceBoxClient
from utils.danfe_pdf import _fmt_cnpj


_REGIMES = {
    "SIMPLES":      "Simples Nacional",
    "REGIME_NORMAL": "Regime Normal (Lucro Real / Presumido)",
    "MEI":          "MEI",
}

_CONTRIBUINTE = {
    1: "Contribuinte ICMS",
    2: "Contribuinte Isento",
    9: "Não Contribuinte",
}

_TIPOS = ["CLIENTE", "FORNECEDOR", "AMBOS"]

UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
       "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]


def tela_parceiros():
    st.title("👥 Parceiros — Clientes & Fornecedores")
    st.caption("Cadastro de empresas parceiras para uso nos documentos fiscais.")

    perfil = st.session_state.get("usuario_logado", {}).get("perfil", "")
    pode_editar = perfil in ["Admin", "Gestor"]

    abas = ["🔍 Consulta & Listagem", "➕ Novo Parceiro"]
    tabs = st.tabs(abas)

    # ══════════════════════════════════════════════════════════════════
    # ABA 1: LISTAGEM
    # ══════════════════════════════════════════════════════════════════
    with tabs[0]:
        c_busca, c_filtro, c_btn = st.columns([3, 1, 1])
        with c_busca:
            termo = st.text_input("Buscar por razão social, fantasia ou CNPJ", placeholder="Digite para buscar…")
        with c_filtro:
            tipo_filtro = st.selectbox("Tipo", ["TODOS", "CLIENTE", "FORNECEDOR", "AMBOS"])
        with c_btn:
            st.write("")
            if st.button("🔄 Atualizar", use_container_width=True):
                st.rerun()

        parceiros = TraceBoxClient.listar_parceiros(tipo=tipo_filtro if tipo_filtro != "TODOS" else "")

        if termo:
            t = termo.lower()
            parceiros = [
                p for p in parceiros
                if t in (p.get("razao_social") or "").lower()
                or t in (p.get("nome_fantasia") or "").lower()
                or t in (p.get("cnpj") or "").lower()
            ]

        if not parceiros:
            st.info("Nenhum parceiro encontrado.")
        else:
            for p in parceiros:
                icone_tipo = {"CLIENTE": "🔵", "FORNECEDOR": "🟠", "AMBOS": "🟣"}.get(p.get("tipo", ""), "⚪")
                icone_st = "✅" if p.get("status") == "ATIVO" else "🔴"
                cnpj_fmt = _fmt_cnpj(p.get("cnpj", ""))
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(
                            f"{icone_tipo} **{p['razao_social']}**"
                            + (f" &nbsp; *{p['nome_fantasia']}*" if p.get("nome_fantasia") else "")
                        )
                        st.caption(
                            f"CNPJ: {cnpj_fmt or '—'} &nbsp;|&nbsp; "
                            f"IE: {p.get('ie') or '—'} &nbsp;|&nbsp; "
                            f"Município: {p.get('municipio') or '—'}/{p.get('uf') or '—'}"
                        )
                    with c2:
                        st.caption(
                            f"{icone_st} {p.get('status')} &nbsp;|&nbsp; "
                            f"{p.get('tipo')} &nbsp;|&nbsp; "
                            f"{_REGIMES.get(p.get('regime_tributario', ''), p.get('regime_tributario', ''))}"
                        )
                        consul = p.get("status_consulta", "NAO_CONSULTADO")
                        consul_label = {"NAO_CONSULTADO": "⬜ Não consultado", "CONSULTADO": "✅ CNPJ consultado", "ERRO": "❌ Erro"}.get(consul, consul)
                        st.caption(consul_label)
                    with c3:
                        if pode_editar:
                            with st.popover("✏️ Editar"):
                                _form_editar(p)
                            if p.get("cnpj"):
                                if st.button("🔄 Sincronizar CNPJ", key=f"sinc_{p['id']}", use_container_width=True):
                                    ok, msg = TraceBoxClient.enriquecer_parceiro(p["id"])
                                    if ok:
                                        st.success(msg)
                                        import time; time.sleep(1); st.rerun()
                                    else:
                                        st.error(msg)

    # ══════════════════════════════════════════════════════════════════
    # ABA 2: NOVO PARCEIRO
    # ══════════════════════════════════════════════════════════════════
    with tabs[1]:
        if not pode_editar:
            st.warning("Somente Admin ou Gestor podem cadastrar parceiros.")
            return

        st.subheader("Cadastrar Novo Parceiro")

        cnpj_busca = st.text_input(
            "CNPJ (opcional — preencha para enriquecer automaticamente via BrasilAPI)",
            placeholder="00.000.000/0001-00",
            key="novo_cnpj_busca",
        )

        dados_api: dict = {}
        if cnpj_busca:
            cnpj_limpo = re.sub(r"\D", "", cnpj_busca)
            if len(cnpj_limpo) == 14:
                if st.button("🔍 Consultar CNPJ na BrasilAPI", use_container_width=False):
                    with st.spinner("Consultando…"):
                        resultado = TraceBoxClient.consultar_cnpj(cnpj_limpo)
                    if resultado.get("status") == "SUCESSO":
                        st.success("CNPJ encontrado! Campos preenchidos automaticamente.")
                        dados_api = resultado
                        st.session_state["_cnpj_api_cache"] = dados_api
                    else:
                        st.error(resultado.get("erro", "Erro na consulta."))

        cached = st.session_state.get("_cnpj_api_cache", {})

        with st.form("form_novo_parceiro"):
            c1, c2 = st.columns(2)
            with c1:
                tipo       = st.selectbox("Tipo", _TIPOS)
                razao      = st.text_input("Razão Social *", value=cached.get("razao_social", ""))
                fantasia   = st.text_input("Nome Fantasia", value=cached.get("nome_fantasia", ""))
                cnpj_f     = st.text_input("CNPJ", value=cnpj_busca or "")
                ie         = st.text_input("Inscrição Estadual (IE)", value="")
                im         = st.text_input("Inscrição Municipal (IM)", value="")
            with c2:
                regime     = st.selectbox("Regime Tributário", list(_REGIMES.keys()),
                                          format_func=lambda k: _REGIMES[k])
                contrib    = st.selectbox("Contribuinte ICMS", list(_CONTRIBUINTE.keys()),
                                          format_func=lambda k: _CONTRIBUINTE[k])
                tel        = st.text_input("Telefone", value=cached.get("telefone", ""))
                email_c    = st.text_input("E-mail de Contato", value=cached.get("email", ""))

            st.write("**Endereço**")
            ca, cb, cc = st.columns([2, 1, 1])
            with ca:
                logradouro = st.text_input("Logradouro", value=cached.get("logradouro", ""))
            with cb:
                numero     = st.text_input("Número", value=cached.get("numero", ""))
            with cc:
                complemento = st.text_input("Complemento", value=cached.get("complemento", ""))

            cd, ce, cf, cg = st.columns([2, 2, 1, 2])
            with cd:
                bairro     = st.text_input("Bairro", value=cached.get("bairro", ""))
            with ce:
                municipio  = st.text_input("Município", value=cached.get("municipio", ""))
            with cf:
                uf_idx = UFS.index(cached["uf"]) if cached.get("uf") in UFS else UFS.index("SP")
                uf     = st.selectbox("UF", UFS, index=uf_idx)
            with cg:
                cep    = st.text_input("CEP", value=cached.get("cep", ""))

            submit = st.form_submit_button("✅ Cadastrar Parceiro", type="primary", use_container_width=True)

        if submit:
            if not razao.strip():
                st.error("Razão Social é obrigatória.")
            else:
                payload = {
                    "tipo": tipo,
                    "razao_social": razao.strip(),
                    "nome_fantasia": fantasia.strip(),
                    "cnpj": cnpj_f,
                    "ie": ie.strip(),
                    "im": im.strip(),
                    "regime_tributario": regime,
                    "contribuinte_icms": contrib,
                    "telefone": tel,
                    "email_contato": email_c,
                    "logradouro": logradouro,
                    "numero": numero,
                    "complemento": complemento,
                    "bairro": bairro,
                    "municipio": municipio,
                    "uf": uf,
                    "cep": cep,
                }
                ok, msg = TraceBoxClient.criar_parceiro(payload)
                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state.pop("_cnpj_api_cache", None)
                    import time; time.sleep(1); st.rerun()
                else:
                    st.error(f"❌ {msg}")


def _form_editar(p: dict):
    """Formulário inline de edição de parceiro dentro de um popover."""
    with st.form(f"form_edit_parceiro_{p['id']}"):
        st.write(f"**Editar: {p['razao_social']}**")
        razao   = st.text_input("Razão Social", value=p.get("razao_social", ""))
        fantasia = st.text_input("Nome Fantasia", value=p.get("nome_fantasia", ""))
        ie      = st.text_input("IE", value=p.get("ie", ""))
        im_val  = st.text_input("IM", value=p.get("im", ""))
        tipo    = st.selectbox("Tipo", _TIPOS, index=_TIPOS.index(p.get("tipo", "CLIENTE")) if p.get("tipo") in _TIPOS else 0)
        regime  = st.selectbox("Regime", list(_REGIMES.keys()), format_func=lambda k: _REGIMES[k],
                               index=list(_REGIMES.keys()).index(p.get("regime_tributario", "REGIME_NORMAL"))
                               if p.get("regime_tributario") in _REGIMES else 1)
        status_opts = ["ATIVO", "INATIVO"]
        status  = st.selectbox("Status", status_opts, index=status_opts.index(p.get("status", "ATIVO")) if p.get("status") in status_opts else 0)
        if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
            ok, msg = TraceBoxClient.atualizar_parceiro(p["id"], {
                "razao_social": razao, "nome_fantasia": fantasia,
                "ie": ie, "im": im_val, "tipo": tipo,
                "regime_tributario": regime, "status": status,
            })
            if ok:
                st.success(msg)
                import time; time.sleep(1); st.rerun()
            else:
                st.error(msg)


