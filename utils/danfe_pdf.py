# utils/danfe_pdf.py
"""
Gerador de DANFE-Rascunho — NF-e Modelo 55 (layout SEFAZ 4.00).

Produz PDF com marca d'água "RASCUNHO / SEM VALOR FISCAL".
Não tem valor fiscal — apenas para visualização e conferência interna.
"""
from __future__ import annotations

import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _limpa(v: object, fallback: str = "—") -> str:
    s = str(v or "").strip()
    return s if s else fallback


def _wrap_text(text: str, max_chars: int = 112) -> list[str]:
    """Quebra texto longo em linhas de até max_chars caracteres, sem cortar palavras."""
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fmt_cnpj(cnpj: str) -> str:
    n = re.sub(r"\D", "", cnpj or "")
    if len(n) == 14:
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    return cnpj or "—"


def _fmt_cep(cep: str) -> str:
    n = re.sub(r"\D", "", cep or "")
    if len(n) == 8:
        return f"{n[:5]}-{n[5:]}"
    return cep or ""


def _fmt_money(val: object) -> str:
    try:
        v = float(val)
        # Format as BR: 1.234,56
        s = f"{v:,.2f}"
        # swap , and .
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def _fmt_qty(val: object) -> str:
    try:
        v = float(val)
        s = f"{v:,.4f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,0000"


_MOD_FRETE_LABEL = {
    "0": "0-Emitente", "1": "1-Destinatário",
    "2": "2-Terceiros", "9": "9-Sem frete",
}

_SUBTIPO_LABEL = {
    "REMESSA_CONSERTO": "Remessa para Conserto",
    "RETORNO_CONSERTO": "Retorno de Conserto",
    "SAIDA_GERAL":      "Saída Geral",
    "ENTRADA_GERAL":    "Entrada Geral",
}


# ---------------------------------------------------------------------------
# Gerador principal
# ---------------------------------------------------------------------------

def gerar_danfe_rascunho(doc: dict) -> bytes:
    """
    Gera PDF DANFE-Rascunho a partir do dict serializado pelo DocumentoFiscalService.
    Retorna bytes prontos para download.
    """
    buf = BytesIO()
    W, H = A4          # 595.27 × 841.89 pt
    M = 5 * mm         # margem

    c = _canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"DANFE Rascunho - Doc #{doc.get('id', '?')}")

    emit  = doc.get("emitente_snapshot") or {}
    parc  = doc.get("parceiro_snapshot") or {}
    itens = doc.get("itens") or []
    body_w = W - 2 * M

    # ── Helpers locais ──────────────────────────────────────────────────

    def rect(x, y, w, h, fill_rgb=None):
        r, g, b = fill_rgb if fill_rgb else (1, 1, 1)
        c.setFillColorRGB(r, g, b)
        c.rect(x, y, w, h, fill=1, stroke=1)
        c.setFillColorRGB(0, 0, 0)

    def label(x, y, txt_s, size=4.5):
        c.setFont("Helvetica", size)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        # size * 0.85 posiciona o topo do glifo ~0.5 mm abaixo da borda superior
        c.drawString(x + 1 * mm, y - size * 1.0, str(txt_s))
        c.setFillColorRGB(0, 0, 0)

    def txt(x, y, s, size=7, bold=False, align="left", color=(0, 0, 0)):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColorRGB(*color)
        s = str(s or "")
        if align == "center":
            c.drawCentredString(x, y, s)
        elif align == "right":
            c.drawRightString(x, y, s)
        else:
            c.drawString(x, y, s)
        c.setFillColorRGB(0, 0, 0)

    def cell(x, y, w, h, lbl, val, val_size=7, val_bold=False):
        rect(x, y, w, h)
        label(x + 0.5 * mm, y + h - 0.3 * mm, lbl)
        txt(x + 1.5 * mm, y + 2.2 * mm, val, size=val_size, bold=val_bold)

    # ── Marca d'água ────────────────────────────────────────────────────
    c.saveState()
    c.setFont("Helvetica-Bold", 52)
    c.setFillColorRGB(0.90, 0.90, 0.90)
    c.translate(W / 2, H / 2)
    c.rotate(38)
    c.drawCentredString(0, 30, "RASCUNHO")
    c.drawCentredString(0, -40, "SEM VALOR FISCAL")
    c.restoreState()

    y = H - M   # cursor descendo

    # ===================================================================
    # CANHOTO — Recibo destacável (topo da página)
    # ===================================================================
    can_h   = 28 * mm
    right_w = body_w * 0.20   # alinha com info_w do BLOCO 1 (emit 0.55 + danfe 0.25 = 0.80)
    left_w  = body_w - right_w
    top_h   = 16 * mm   # área de texto "Recebemos de..."
    bot_h   = can_h - top_h  # 12 mm — faixa de campos

    def _dashed_line(yy):
        c.saveState()
        c.setDash(3, 2)
        c.setLineWidth(0.4)
        c.setStrokeColorRGB(0.45, 0.45, 0.45)
        c.line(M, yy, M + body_w, yy)
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawString(M + body_w - 6 * mm, yy + 0.8 * mm, "✂")
        c.restoreState()

    y -= can_h

    # ── Área superior esquerda: texto "Recebemos de..." ──────────────
    rect(M, y + bot_h, left_w, top_h)

    nome_emit_can = _limpa(emit.get("razao_social") or emit.get("nome_fantasia"), "")
    txt(M + 2 * mm, y + can_h - 5 * mm,
        f"RECEBEMOS DE {nome_emit_can[:45]} OS PRODUTOS E/OU SERVIÇOS",
        size=5.5)
    txt(M + 2 * mm, y + can_h - 8.5 * mm,
        f"CONSTANTES DA NOTA FISCAL INDICADA AO LADO.  CNPJ: {_fmt_cnpj(emit.get('cnpj', ''))}",
        size=5.5)

    # ── Faixa de campos inferior esquerda ────────────────────────────
    data_w  = left_w * 0.17
    nome_w  = left_w * 0.45
    rg_w    = left_w * 0.19
    asin_w  = left_w - data_w - nome_w - rg_w   # ~19%

    cell(M,                              y, data_w, bot_h, "DATA DE RECEBIMENTO", "")
    cell(M + data_w,                     y, nome_w, bot_h, "NOME DO RECEBEDOR",   "")
    cell(M + data_w + nome_w,            y, rg_w,   bot_h, "RG",                  "")
    cell(M + data_w + nome_w + rg_w,     y, asin_w, bot_h, "ASSINATURA",          "")

    # ── Caixa direita: identificação da NF ───────────────────────────
    rx = M + left_w
    rect(rx, y, right_w, can_h)
    label(rx + 0.5 * mm, y + can_h - 0.3 * mm, "NF-e")
    txt(rx + right_w / 2, y + can_h - 6.5 * mm,
        f"Nº  {_limpa(doc.get('numero'), '—')}",
        size=8, bold=True, align="center")
    txt(rx + right_w / 2, y + can_h - 11 * mm,
        f"SÉRIE  {_limpa(doc.get('serie'), '1')}",
        size=6.5, align="center")
    txt(rx + right_w / 2, y + can_h - 15.5 * mm,
        "DATA DE EMISSÃO", size=4.5, align="center", color=(0.4, 0.4, 0.4))
    txt(rx + right_w / 2, y + can_h - 19 * mm,
        (doc.get("criado_em") or "")[:10],
        size=6.5, bold=True, align="center")

    _dashed_line(y)   # linha tracejada de separação do corpo do DANFE
    y -= 5            # gap de 5pt entre o canhoto e o início da NF

    # ===================================================================
    # BLOCO 1 — CABEÇALHO: Emitente | DANFE | Info
    # ===================================================================
    bh = 38 * mm
    y -= bh
    emit_w  = body_w * 0.55
    danfe_w = body_w * 0.25
    info_w  = body_w * 0.20

    # Emitente
    rect(M, y, emit_w, bh)

    # ── Logo (lateral esquerda, calculado primeiro para definir ex) ───
    import base64 as _b64
    from reportlab.lib.utils import ImageReader as _IR
    logo_col_w = 0
    logo_b64 = doc.get('logo_base64', '')
    if logo_b64:
        try:
            _img_bytes = _b64.b64decode(logo_b64)
            _img_reader = _IR(BytesIO(_img_bytes))
            _iw, _ih = _img_reader.getSize()
            _aspect = (_iw / _ih) if _ih else 1
            _logo_h = bh - 2.5 * mm
            _logo_w = min(_logo_h * _aspect, emit_w * 0.38)
            c.drawImage(_img_reader, M + 1 * mm, y + 1.2 * mm,
                        width=_logo_w, height=_logo_h,
                        preserveAspectRatio=True, anchor='c', mask='auto')
            c.saveState()
            c.setStrokeColorRGB(0.78, 0.78, 0.78)
            c.line(M + _logo_w + 2 * mm, y + 1 * mm,
                   M + _logo_w + 2 * mm, y + bh - 1 * mm)
            c.restoreState()
            logo_col_w = _logo_w + 3.5 * mm
        except Exception:
            logo_col_w = 0

    # ── Label e dados à direita do logo ──────────────────────────────
    ex = M + logo_col_w + 2 * mm
    label(ex, y + bh - 0.3 * mm, "IDENTIFICAÇÃO DO EMITENTE")

    txt(ex, y + 30 * mm,
        _limpa(emit.get("razao_social") or emit.get("nome_fantasia")),
        size=7, bold=True)
    if emit.get("nome_fantasia") and emit.get("razao_social"):
        txt(ex, y + 26.5 * mm, _limpa(emit.get("nome_fantasia")), size=6)
    logr_emit = _limpa(emit.get("logradouro", ""), "")
    if emit.get("numero"):
        logr_emit += f", {emit['numero']}"
    if emit.get("complemento"):
        logr_emit += f" – {emit['complemento']}"
    txt(ex, y + 22.5 * mm, logr_emit[:45], size=6)
    txt(ex, y + 18.5 * mm,
        f"{_limpa(emit.get('bairro'), '')} – {_limpa(emit.get('municipio'), '')}/"
        f"{_limpa(emit.get('uf'), '')}  CEP: {_fmt_cep(emit.get('cep', ''))}",
        size=6)
    txt(ex, y + 14.5 * mm, f"CNPJ: {_fmt_cnpj(emit.get('cnpj', ''))}", size=6)
    txt(ex, y + 10.5 * mm,
        f"IE: {_limpa(emit.get('ie'))}   IM: {_limpa(emit.get('im'))}",
        size=6)
    txt(ex, y + 6.5 * mm,
        f"Fone: {_limpa(emit.get('telefone'))}   CNAE: {_limpa(emit.get('cnae_principal'))}",
        size=5.5)
    txt(ex, y + 2.5 * mm,
        f"Regime: {_limpa(emit.get('regime_tributario'))}",
        size=5.5)

    # DANFE centre
    dx = M + emit_w
    rect(dx, y, danfe_w, bh)
    txt(dx + danfe_w / 2, y + 31 * mm, "DANFE", size=16, bold=True, align="center")
    txt(dx + danfe_w / 2, y + 26.5 * mm, "Documento Auxiliar da", size=6, align="center")
    txt(dx + danfe_w / 2, y + 23.5 * mm, "Nota Fiscal Eletrônica", size=6, align="center")
    txt(dx + danfe_w / 2, y + 19 * mm,
        "0 - ENTRADA    1 - SAÍDA", size=6, align="center", color=(0.4, 0.4, 0.4))
    tipo_nf = doc.get("tipo_nf", "1")
    txt(dx + danfe_w / 2, y + 15 * mm,
        f"[  {tipo_nf}  ]", size=10, bold=True, align="center")
    txt(dx + danfe_w / 2, y + 10 * mm,
        f"Nº  {_limpa(doc.get('numero'), '—')}",
        size=7, bold=True, align="center")
    txt(dx + danfe_w / 2, y + 6.5 * mm,
        f"Série  {_limpa(doc.get('serie'), '1')}",
        size=7, align="center")
    txt(dx + danfe_w / 2, y + 3 * mm,
        f"Modelo  {_limpa(doc.get('modelo'), '55')}",
        size=6.5, align="center")

    # Info direita
    ix = dx + danfe_w
    rect(ix, y, info_w, bh)
    txt(ix + info_w / 2, y + 29 * mm, "⚠ RASCUNHO", size=8, bold=True,
        align="center", color=(0.7, 0.1, 0.1))
    txt(ix + info_w / 2, y + 25 * mm, "SEM VALOR FISCAL", size=6,
        align="center", color=(0.5, 0.5, 0.5))
    txt(ix + info_w / 2, y + 20 * mm,
        f"Status: {_limpa(doc.get('status'))}",
        size=6.5, align="center")
    subtipo_label = _SUBTIPO_LABEL.get(doc.get("subtipo", ""), doc.get("subtipo", ""))
    words = subtipo_label.split()
    mid = len(words) // 2 or 1
    txt(ix + info_w / 2, y + 16 * mm, " ".join(words[:mid]), size=6, align="center")
    txt(ix + info_w / 2, y + 13 * mm, " ".join(words[mid:]), size=6, align="center")
    criado = (doc.get("criado_em") or "")[:16]
    txt(ix + info_w / 2, y + 8.5 * mm, f"Emitido: {criado}", size=5.5, align="center")
    txt(ix + info_w / 2, y + 5.5 * mm, f"Por: {_limpa(doc.get('criado_por'))}", size=5.5, align="center")
    # Frete
    frete_label = _MOD_FRETE_LABEL.get(str(doc.get("mod_frete", "9")), "9-Sem frete")
    txt(ix + info_w / 2, y + 2 * mm, f"Frete: {frete_label}", size=5, align="center", color=(0.4, 0.4, 0.4))

    # ===================================================================
    # BLOCO 2 — CHAVE DE ACESSO + representação de barcode
    # ===================================================================
    ch = 14 * mm
    y -= ch
    rect(M, y, body_w, ch)
    label(M + 0.5 * mm, y + ch - 0.3 * mm, "CHAVE DE ACESSO")
    chave_txt = _limpa(doc.get("chave_acesso"), "")
    n44 = re.sub(r"\D", "", chave_txt)
    if len(n44) == 44:
        chave_fmt = " ".join(n44[i:i+4] for i in range(0, 44, 4))
        txt(M + body_w / 2, y + 8 * mm, chave_fmt, size=7, bold=True, align="center")
        # Representação visual do barcode (linhas verticais alternadas)
        _draw_barcode_repr(c, M + body_w * 0.15, y + 1 * mm, body_w * 0.70, 4.5 * mm)
    else:
        txt(M + body_w / 2, y + 8 * mm,
            "(Rascunho — chave gerada após autorização SEFAZ)", size=6.5,
            align="center", color=(0.5, 0.5, 0.5))
        txt(M + body_w / 2, y + 3.5 * mm,
            "CONSULTE A AUTENTICIDADE NO PORTAL DA SEFAZ", size=5.5,
            align="center", color=(0.4, 0.4, 0.4))

    # ===================================================================
    # BLOCO 3 — NATUREZA / PROTOCOLO
    # ===================================================================
    nh = 9 * mm
    y -= nh
    nat_w  = body_w * 0.60
    prot_w = body_w * 0.40
    cell(M, y, nat_w, nh, "NATUREZA DA OPERAÇÃO",
         _limpa(doc.get("natureza_operacao")), val_bold=True)
    cell(M + nat_w, y, prot_w, nh, "PROTOCOLO DE AUTORIZAÇÃO DE USO / DATA",
         _limpa(doc.get("protocolo_sefaz"), "—") +
         (f"  {(doc.get('aprovado_em') or '')[:16]}" if doc.get("aprovado_em") else ""))

    # ===================================================================
    # BLOCO 4 — CFOP / SÉRIE / DATA EMISSÃO / STATUS / VALOR TOTAL
    # ===================================================================
    rh = 9 * mm
    y -= rh
    cfop_w  = body_w * 0.10
    serie_w = body_w * 0.08
    emis_w  = body_w * 0.18
    stat_w  = body_w * 0.20
    vlt_w   = body_w - cfop_w - serie_w - emis_w - stat_w
    cell(M,                                  y, cfop_w,  rh, "CFOP",               _limpa(doc.get("cfop")), val_bold=True)
    cell(M + cfop_w,                         y, serie_w, rh, "SÉRIE",              _limpa(doc.get("serie"), "1"))
    cell(M + cfop_w + serie_w,               y, emis_w,  rh, "DATA EMISSÃO",       (doc.get("criado_em") or "")[:10])
    cell(M + cfop_w + serie_w + emis_w,      y, stat_w,  rh, "STATUS",             _limpa(doc.get("status")), val_bold=True)
    cell(M + cfop_w + serie_w + emis_w + stat_w, y, vlt_w, rh,
         "VALOR TOTAL DA NF (R$)", _fmt_money(doc.get("valor_total", 0)),
         val_size=8, val_bold=True)

    # ===================================================================
    # BLOCO 5 — DESTINATÁRIO / REMETENTE
    # ===================================================================
    dh = 22 * mm
    y -= dh
    rect(M, y, body_w, dh)
    label(M + 0.5 * mm, y + dh - 0.3 * mm, "DESTINATÁRIO / REMETENTE")
    nome_parc = _limpa(parc.get("razao_social"))
    txt(M + 2 * mm, y + 17 * mm, nome_parc[:60], size=8, bold=True)
    txt(M + 2 * mm, y + 13 * mm, f"CNPJ/CPF: {_fmt_cnpj(parc.get('cnpj', ''))}", size=7)
    txt(M + 2 * mm, y + 9.5 * mm,
        f"IE: {_limpa(parc.get('ie'))}   Contribuinte ICMS: {_limpa(parc.get('contribuinte_icms'), '9')}",
        size=6.5)
    logr_parc = _limpa(parc.get("logradouro", ""), "")
    if parc.get("numero"):
        logr_parc += f", {parc['numero']}"
    if parc.get("complemento"):
        logr_parc += f" – {parc['complemento']}"
    txt(M + 2 * mm, y + 6 * mm, logr_parc[:75], size=6.5)
    txt(M + 2 * mm, y + 2.5 * mm,
        f"{_limpa(parc.get('bairro'), '')}  "
        f"{_limpa(parc.get('municipio'), '')}/"
        f"{_limpa(parc.get('uf'), '')}  "
        f"CEP: {_fmt_cep(parc.get('cep', ''))}",
        size=6.5)

    # ===================================================================
    # BLOCO 6 — TABELA DE ITENS
    # ===================================================================
    # col_defs: (label, fração_largura, alinhamento_valor, max_chars_valor)
    # As frações somam exatamente 1.000 — garantia de alinhamento perfeito.
    col_defs = [
        ("#",                    0.030, "center",  3),
        ("CÓD",                  0.070, "left",    9),
        ("DESCRIÇÃO DO PRODUTO", 0.270, "left",   46),
        ("NCM/SH",               0.070, "left",    9),
        ("CST\nICMS",            0.045, "center",  3),
        ("CFOP",                 0.045, "center",  4),
        ("UN",                   0.035, "center",  3),
        ("QUANT.",               0.070, "right",  12),
        ("VL. UNIT.",            0.085, "right",  12),
        ("VL. TOTAL",            0.085, "right",  12),
        ("CST\nIPI",             0.040, "center",  3),
        ("CST\nPIS",             0.040, "center",  3),
        ("CST\nCOF.",            0.040, "center",  3),
        ("RESERV.\nFISCO",       0.075, "left",    8),
    ]
    # Verificação: sum(frac) deve ser 1.000
    # 0.030+0.070+0.270+0.070+0.045+0.045+0.035+0.070+0.085+0.085+0.040+0.040+0.040+0.075 = 1.000

    ih = 7.5 * mm   # altura cabeçalho
    ir = 5.5 * mm   # altura item

    y -= ih
    x0 = M
    for col_lbl, frac, _align, _mc in col_defs:
        cw = body_w * frac
        rect(x0, y, cw, ih, fill_rgb=(0.82, 0.82, 0.82))
        lines = col_lbl.split("\n")
        cx = x0 + cw / 2
        for li, line in enumerate(lines):
            txt(cx, y + ih - 2.5 * mm - li * 3 * mm, line, size=4.5, bold=True, align="center")
        x0 += cw

    for idx, item in enumerate(itens):
        if y - ir < M + 38 * mm:
            y -= ir * 0.7
            txt(M + 2 * mm, y + 1 * mm,
                f"[+{len(itens) - idx} item(ns) restante(s) — ver sistema TraceBox]",
                size=5.5, color=(0.6, 0.2, 0.2))
            break

        y -= ir
        row_vals = [
            str(item.get("sequencia", idx + 1)),
            str(item.get("codigo_produto") or ""),
            str(item.get("descricao") or ""),
            str(item.get("ncm") or ""),
            str(item.get("cst_icms") or item.get("csosn") or "—"),
            str(item.get("cfop") or ""),
            str(item.get("unidade") or "UN"),
            _fmt_qty(item.get("quantidade", 0)),
            _fmt_money(item.get("valor_unitario", 0)),
            _fmt_money(item.get("valor_total", 0)),
            str(item.get("ipi_cst") or "—"),
            str(item.get("pis_cst") or "—"),
            str(item.get("cofins_cst") or "—"),
            "",
        ]
        x0 = M
        for val, (_, frac, col_align, max_c) in zip(row_vals, col_defs):
            cw = body_w * frac
            rect(x0, y, cw, ir)
            v = val[:max_c]
            if col_align == "right":
                txt(x0 + cw - 0.7 * mm, y + 1.6 * mm, v, size=5, align="right")
            elif col_align == "center":
                txt(x0 + cw / 2, y + 1.6 * mm, v, size=5, align="center")
            else:
                txt(x0 + 0.7 * mm, y + 1.6 * mm, v, size=5)
            x0 += cw

    # ===================================================================
    # BLOCO 7 — TRANSPORTE
    # ===================================================================
    tr_h = 9 * mm
    if y - tr_h > M + 30 * mm:
        y -= tr_h
        mod_frete = str(doc.get("mod_frete", "9"))
        frete_desc = _MOD_FRETE_LABEL.get(mod_frete, mod_frete)
        mf_w   = body_w * 0.25
        esp_w  = body_w * 0.25
        peso_w = body_w * 0.25
        vol_w  = body_w - mf_w - esp_w - peso_w
        cell(M,                   y, mf_w,  tr_h, "MODALIDADE DO FRETE", frete_desc)
        cell(M + mf_w,            y, esp_w, tr_h, "QUANTIDADE VOLUMES",  "—")
        cell(M + mf_w + esp_w,    y, peso_w, tr_h, "PESO BRUTO (kg)",    "—")
        cell(M + mf_w + esp_w + peso_w, y, vol_w, tr_h, "PESO LÍQUIDO (kg)", "—")

    # ===================================================================
    # BLOCO 8 — TOTAIS
    # ===================================================================
    tot_h = 10 * mm
    if y - tot_h > M + 20 * mm:
        y -= tot_h
        tot_cols = [
            ("BASE CÁLC. ICMS (R$)", "—",                                     0.18),
            ("VALOR ICMS (R$)",      "—",                                     0.18),
            ("BASE ICMS ST (R$)",    "—",                                     0.18),
            ("VALOR ICMS ST (R$)",   "—",                                     0.18),
            ("VALOR IPI (R$)",       "—",                                     0.13),
            ("VALOR TOTAL NF (R$)", _fmt_money(doc.get("valor_total", 0)),   0.15),
        ]
        x0 = M
        for lbl, val, frac in tot_cols:
            cw = body_w * frac
            cell(x0, y, cw, tot_h, lbl, val,
                 val_size=8 if "TOTAL NF" in lbl else 7,
                 val_bold="TOTAL NF" in lbl)
            x0 += cw

    # ===================================================================
    # BLOCO 9 — VÍNCULO REMESSA (apenas Retorno de Conserto)
    # ===================================================================
    if doc.get("doc_vinculado_id"):
        vl_h = 8 * mm
        if y - vl_h > M + 20 * mm:
            y -= vl_h
            rect(M, y, body_w, vl_h)
            label(M + 0.5 * mm, y + vl_h - 0.3 * mm, "DOCUMENTO VINCULADO (REMESSA DE ORIGEM)")
            txt(M + 2 * mm, y + 2.5 * mm,
                f"Retorno referente à Remessa para Conserto Doc # {doc['doc_vinculado_id']}",
                size=7)

    # ===================================================================
    # BLOCO 10 — INFORMAÇÕES COMPLEMENTARES / infCpl
    # ===================================================================
    obs_h = min(max(20 * mm, y - M - 6 * mm), 38 * mm)
    if y - obs_h > M + 2 * mm:
        y -= obs_h
        rect(M, y, body_w, obs_h)
        label(M + 0.5 * mm, y + obs_h - 0.3 * mm, "INFORMAÇÕES COMPLEMENTARES / DADOS ADICIONAIS (infCpl)")

        info_cpl = doc.get("info_complementar") or doc.get("observacao") or ""
        linhas_brutas = [info_cpl] if info_cpl else []
        linhas_brutas.extend([
            f"Rascunho TraceBox WMS — gerado em {(doc.get('criado_em') or '')[:16]}",
            f"Criado por: {_limpa(doc.get('criado_por'))}",
        ])
        if doc.get("aprovado_por"):
            linhas_brutas.append(
                f"Aprovado por: {_limpa(doc.get('aprovado_por'))} em {(doc.get('aprovado_em') or '')[:16]}"
            )
        if doc.get("motivo_rejeicao"):
            linhas_brutas.append(f"Cancelamento: {doc['motivo_rejeicao']}")

        seen: set = set()
        dedup: list = []
        for l in linhas_brutas:
            if l and l not in seen:
                seen.add(l)
                dedup.append(l)

        # Expande cada linha longa em sub-linhas com quebra de palavras
        display_lines: list[str] = []
        for linha in dedup:
            display_lines.extend(_wrap_text(linha))

        max_linhas = int((obs_h - 6 * mm) / 3.5 / mm)
        for i, linha in enumerate(display_lines[:max_linhas]):
            txt(M + 2 * mm, y + obs_h - 5.5 * mm - i * 3.5 * mm, linha, size=5.5)

    # ===================================================================
    # RODAPÉ
    # ===================================================================
    c.setFont("Helvetica", 4.5)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(
        W / 2, M * 0.5,
        "RASCUNHO — SEM VALOR FISCAL — NÃO SUBSTITUI NF-e AUTORIZADA PELA SEFAZ — TraceBox WMS"
    )
    c.setFillColorRGB(0, 0, 0)

    c.save()
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Representação visual da chave de acesso (pseudo-barcode)
# ---------------------------------------------------------------------------

def _draw_barcode_repr(c, x: float, y: float, w: float, h: float):
    """Desenha linhas verticais simulando a área de código de barras."""
    import random as _rnd
    _rnd.seed(42)
    num_bars = 80
    bar_w_unit = w / num_bars
    bx = x
    c.setFillColorRGB(0, 0, 0)
    for i in range(num_bars):
        bar_w = bar_w_unit * (_rnd.choice([0.4, 0.6, 0.8, 1.0]))
        if i % 3 != 1:
            c.rect(bx, y, bar_w, h, fill=1, stroke=0)
        bx += bar_w_unit
    c.setFillColorRGB(0, 0, 0)
