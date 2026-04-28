import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock
from services.cnpj_service import validar_cnpj, formatar_cnpj, CnpjService, BrasilAPIProvider
import services.cnpj_service as _mod


# CNPJ real de teste (Receita Federal — número amplamente usado em testes)
CNPJ_VALIDO     = "11222333000181"
CNPJ_INVALIDO   = "11111111111111"  # todos iguais
CNPJ_FORMATADO  = "11.222.333/0001-81"


class TestValidarCnpj:
    def test_cnpj_valido(self):
        assert validar_cnpj(CNPJ_VALIDO) is True

    def test_cnpj_formatado_valido(self):
        assert validar_cnpj(CNPJ_FORMATADO) is True

    def test_todos_iguais_invalido(self):
        assert validar_cnpj(CNPJ_INVALIDO) is False

    def test_digito_incorreto(self):
        assert validar_cnpj("11222333000182") is False

    def test_curto_invalido(self):
        assert validar_cnpj("1234567") is False

    def test_vazio_invalido(self):
        assert validar_cnpj("") is False


class TestFormatarCnpj:
    def test_formata_corretamente(self):
        assert formatar_cnpj(CNPJ_VALIDO) == CNPJ_FORMATADO

    def test_ja_formatado_retorna_igual(self):
        assert formatar_cnpj(CNPJ_FORMATADO) == CNPJ_FORMATADO

    def test_cnpj_curto_retorna_original(self):
        assert formatar_cnpj("123") == "123"


class TestCnpjServiceValidar:
    def test_valido(self):
        ok, msg = CnpjService.validar(CNPJ_VALIDO)
        assert ok is True

    def test_invalido_digito(self):
        ok, msg = CnpjService.validar("11222333000182")
        assert ok is False
        assert "inválido" in msg.lower()

    def test_comprimento_errado(self):
        ok, msg = CnpjService.validar("123")
        assert ok is False
        assert "14" in msg


class TestBrasilAPIProvider:
    def setup_method(self):
        CnpjService.limpar_cache()

    def test_sucesso(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "razao_social": "EMPRESA TESTE LTDA",
            "nome_fantasia": "TESTE",
            "descricao_situacao_cadastral": "ATIVA",
            "logradouro": "Rua A", "numero": "10", "complemento": "",
            "bairro": "Centro", "municipio": "São Paulo", "uf": "SP",
            "cep": "01310100", "codigo_municipio_ibge": "3550308",
            "ddd_telefone_1": "11999999999", "email": "teste@teste.com",
            "cnae_fiscal": "6201500", "descricao_porte": "DEMAIS",
            "capital_social": 10000, "data_inicio_atividade": "2000-01-01",
        }
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.return_value = mock_resp
            result = BrasilAPIProvider.consultar(CNPJ_VALIDO)

        assert result["status"] == "SUCESSO"
        assert result["razao_social"] == "EMPRESA TESTE LTDA"
        assert result["uf"] == "SP"

    def test_cache_hit(self):
        dados = {"status": "SUCESSO", "razao_social": "CACHED"}
        _mod._cache_set(CNPJ_VALIDO, dados)
        with patch("httpx.Client") as mock_client_cls:
            result = BrasilAPIProvider.consultar(CNPJ_VALIDO)
            mock_client_cls.assert_not_called()
        assert result["razao_social"] == "CACHED"

    def test_rate_limit(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.return_value = mock_resp
            result = BrasilAPIProvider.consultar(CNPJ_VALIDO)
        assert result["status"] == "RATE_LIMIT"

    def test_erro_http(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.return_value = mock_resp
            result = BrasilAPIProvider.consultar(CNPJ_VALIDO)
        assert result["status"] == "ERRO"

    def test_timeout(self):
        import httpx
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            result = BrasilAPIProvider.consultar(CNPJ_VALIDO)
        assert result["status"] == "ERRO"
        assert "Timeout" in result["erro"]


class TestCnpjServiceConsultar:
    def setup_method(self):
        CnpjService.limpar_cache()

    def test_cnpj_invalido_nao_consulta_api(self):
        result = CnpjService.consultar("123")
        assert result["status"] == "ERRO"

    def test_limpar_cache_especifico(self):
        _mod._cache_set(CNPJ_VALIDO, {"status": "SUCESSO"})
        CnpjService.limpar_cache(CNPJ_VALIDO)
        assert _mod._cache_get(CNPJ_VALIDO) is None

    def test_limpar_cache_tudo(self):
        _mod._cache_set(CNPJ_VALIDO, {"status": "SUCESSO"})
        CnpjService.limpar_cache()
        assert len(_mod._cache) == 0
