import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.danfe_pdf import _fmt_cnpj, _fmt_cep, _wrap_text, _limpa, gerar_danfe_rascunho


class TestFmtCnpj:
    def test_formata_14_digitos(self):
        assert _fmt_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_formata_com_pontuacao_existente(self):
        assert _fmt_cnpj("11.222.333/0001-81") == "11.222.333/0001-81"

    def test_vazio_retorna_travessao(self):
        assert _fmt_cnpj("") == "—"

    def test_none_retorna_travessao(self):
        assert _fmt_cnpj(None) == "—"

    def test_curto_retorna_original(self):
        result = _fmt_cnpj("123")
        assert result == "123"


class TestFmtCep:
    def test_formata_8_digitos(self):
        from utils.danfe_pdf import _fmt_cep
        assert _fmt_cep("01310100") == "01310-100"

    def test_vazio_retorna_vazio(self):
        from utils.danfe_pdf import _fmt_cep
        assert _fmt_cep("") == ""

    def test_curto_retorna_original(self):
        from utils.danfe_pdf import _fmt_cep
        assert _fmt_cep("123") == "123"


class TestWrapText:
    def test_texto_curto_sem_quebra(self):
        lines = _wrap_text("Texto curto", max_chars=50)
        assert lines == ["Texto curto"]

    def test_texto_vazio(self):
        assert _wrap_text("") == []

    def test_texto_longo_quebra_em_palavras(self):
        texto = "palavra " * 20
        lines = _wrap_text(texto.strip(), max_chars=30)
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 30

    def test_palavra_maior_que_max(self):
        # Uma palavra muito longa deve ficar sozinha na linha
        palavra = "X" * 150
        lines = _wrap_text(palavra, max_chars=50)
        assert len(lines) >= 1

    def test_none_retorna_lista_vazia(self):
        assert _wrap_text(None) == []


class TestLimpa:
    def test_retorna_string_limpa(self):
        assert _limpa("  Texto  ") == "Texto"

    def test_none_retorna_fallback(self):
        assert _limpa(None) == "—"

    def test_vazio_retorna_fallback(self):
        assert _limpa("") == "—"

    def test_fallback_customizado(self):
        assert _limpa("", fallback="N/A") == "N/A"


class TestGerarDanfeRascunho:
    """Smoke tests: verifica que o PDF é gerado sem erros e tem tamanho razoável."""

    def _doc_minimo(self):
        return {
            "id": 1,
            "subtipo": "REMESSA_CONSERTO",
            "tipo_nf": "1",
            "numero": "42",
            "serie": "1",
            "natureza_operacao": "Remessa para conserto",
            "cfop": "5915",
            "modelo": "55",
            "status": "RASCUNHO",
            "criado_por": "admin",
            "criado_em": "2025-01-01 10:00:00",
            "valor_total": 1500.00,
            "observacao": "Teste",
            "num_os": "OS-001",
            "asset_tag": "TAG-001",
            "num_serie": "SN-XYZ",
            "info_complementar": "",
            "mod_frete": "9",
            "ind_final": 0,
            "ind_pres": 0,
            "emitente_snapshot": {
                "cnpj": "11222333000181",
                "razao_social": "Emitente LTDA",
                "ie": "123456789",
                "logradouro": "Rua A",
                "numero": "10",
                "bairro": "Centro",
                "municipio": "São Paulo",
                "uf": "SP",
                "cep": "01310100",
                "telefone": "11999999999",
                "email": "emitente@test.com",
                "regime_tributario": "REGIME_NORMAL",
            },
            "parceiro_snapshot": {
                "razao_social": "Parceiro LTDA",
                "cnpj": "99887766000100",
                "ie": "",
                "logradouro": "Av B",
                "numero": "20",
                "bairro": "Vila",
                "municipio": "Campinas",
                "uf": "SP",
                "cep": "13000000",
                "contribuinte_icms": 1,
            },
            "itens": [
                {
                    "sequencia": 1,
                    "codigo_produto": "FER-001",
                    "descricao": "Furadeira de Impacto",
                    "ncm": "84672200",
                    "cfop": "5915",
                    "unidade": "UN",
                    "quantidade": 1,
                    "valor_unitario": 1500.00,
                    "valor_total": 1500.00,
                    "cst_icms": "41",
                    "csosn": "",
                    "orig_icms": "0",
                    "ipi_cst": "53",
                    "pis_cst": "07",
                    "cofins_cst": "07",
                    "c_ean": "SEM GTIN",
                    "c_ean_trib": "SEM GTIN",
                    "ind_tot": 1,
                    "x_ped": "",
                    "n_item_ped": "",
                },
            ],
            "status_historico": [{"status": "RASCUNHO", "data": "2025-01-01", "usuario": "admin"}],
            "aprovado_por": "",
            "aprovado_em": "",
            "motivo_rejeicao": "",
            "chave_acesso": "",
            "protocolo_sefaz": "",
            "doc_vinculado_id": None,
            "parceiro_id": 1,
        }

    def test_retorna_bytes(self):
        pdf = gerar_danfe_rascunho(self._doc_minimo())
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000  # PDF deve ter tamanho razoável

    def test_comeca_com_header_pdf(self):
        pdf = gerar_danfe_rascunho(self._doc_minimo())
        assert pdf[:4] == b"%PDF"

    def test_sem_logo(self):
        doc = self._doc_minimo()
        doc["logo_base64"] = ""
        pdf = gerar_danfe_rascunho(doc)
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_multiplos_itens(self):
        doc = self._doc_minimo()
        doc["itens"] = doc["itens"] * 5  # 5 itens iguais
        pdf = gerar_danfe_rascunho(doc)
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
