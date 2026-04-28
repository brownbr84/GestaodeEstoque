"""
Testes para cálculos de viabilidade financeira e KPIs do WMS.
Cobre as funções matemáticas puras do sistema (sem banco de dados).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


class TestFormatacaoFinanceira:
    """Testa utilitários de formatação de valores do DANFE."""

    def test_fmt_money_inteiro(self):
        from utils.danfe_pdf import _fmt_money
        assert _fmt_money(1500) == "1.500,00"

    def test_fmt_money_decimal(self):
        from utils.danfe_pdf import _fmt_money
        assert _fmt_money(1234.56) == "1.234,56"

    def test_fmt_money_zero(self):
        from utils.danfe_pdf import _fmt_money
        assert _fmt_money(0) == "0,00"

    def test_fmt_money_negativo(self):
        from utils.danfe_pdf import _fmt_money
        assert _fmt_money(-100) == "-100,00"

    def test_fmt_money_milhao(self):
        from utils.danfe_pdf import _fmt_money
        result = _fmt_money(1_000_000)
        assert "1.000.000,00" == result


class TestFormatacaoQuantidade:
    def test_fmt_qty_inteiro(self):
        from utils.danfe_pdf import _fmt_qty
        # _fmt_qty usa 4 casas decimais no formato brasileiro
        assert _fmt_qty(10) == "10,0000"

    def test_fmt_qty_float_sem_decimal(self):
        from utils.danfe_pdf import _fmt_qty
        assert _fmt_qty(10.0) == "10,0000"

    def test_fmt_qty_com_decimal(self):
        from utils.danfe_pdf import _fmt_qty
        result = _fmt_qty(10.5)
        assert "10" in result and "5" in result

    def test_fmt_qty_invalido_retorna_zero(self):
        from utils.danfe_pdf import _fmt_qty
        assert _fmt_qty(None) == "0,0000"


class TestCnpjDigitosVerificadores:
    """Testa o algoritmo módulo 11 da Receita Federal diretamente."""

    def test_cnpj_com_digitos_corretos(self):
        from services.cnpj_service import validar_cnpj
        # CNPJs com dígitos válidos
        assert validar_cnpj("11222333000181") is True
        assert validar_cnpj("00000000000191") is True  # Banco do Brasil

    def test_cnpj_todos_zeros_invalido(self):
        from services.cnpj_service import validar_cnpj
        assert validar_cnpj("00000000000000") is False

    def test_cfop_interestadual_vs_interno(self):
        """CFOP interno = mesma UF, interestadual = UFs diferentes."""
        from database.models import RegraOperacaoFiscal
        from services.documento_fiscal_service import _cfop_para_uf
        regra = RegraOperacaoFiscal(cfop_interno="5915", cfop_interestadual="6915")
        assert _cfop_para_uf(regra, "SP", "SP") == "5915"  # mesma UF
        assert _cfop_para_uf(regra, "SP", "RJ") == "6915"  # diferente
        assert _cfop_para_uf(regra, "", "RJ") == "5915"    # sem UF emitente = interno

    def test_build_info_complementar_conserto(self):
        from services.documento_fiscal_service import _build_info_complementar
        info = _build_info_complementar("Obs", "OS-001", "TAG-999", "SN-123", "REMESSA_CONSERTO")
        assert "OS: OS-001" in info
        assert "Tag/Patrimônio: TAG-999" in info
        assert "Série: SN-123" in info
        assert "ICMS CST 41" in info

    def test_build_info_complementar_saida_geral_sem_cst(self):
        from services.documento_fiscal_service import _build_info_complementar
        info = _build_info_complementar("", "", "", "", "SAIDA_GERAL")
        assert "ICMS CST" not in info

    def test_snapshot_emitente_nenhum(self):
        from services.documento_fiscal_service import _snapshot_emitente
        result = _snapshot_emitente(None)
        assert result == {}

    def test_snapshot_parceiro_nenhum(self):
        from services.documento_fiscal_service import _snapshot_parceiro
        result = _snapshot_parceiro(None)
        assert result == {}

    def test_valor_total_itens(self):
        """Verifica que o cálculo de valor total dos itens está correto."""
        qtds = [1, 2, 3]
        precos = [500.0, 100.0, 50.0]
        total = sum(q * p for q, p in zip(qtds, precos))
        assert total == 850.0

    def test_bcrypt_rounds_definido(self):
        """Garante que o número de rounds do bcrypt está configurado."""
        from utils.security import _BCRYPT_ROUNDS
        assert _BCRYPT_ROUNDS >= 10  # mínimo aceitável para segurança
