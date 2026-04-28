import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.documento_fiscal_service import DocumentoFiscalService
from services.emitente_service import EmitenteService
from services.parceiro_service import ParceiroService
from database.models import RegraOperacaoFiscal, Configuracoes, DocumentoFiscal, LogAuditoria


CNPJ_PARCEIRO = "11222333000181"

def _seed_regras(session):
    regras = [
        RegraOperacaoFiscal(nome="Remessa Conserto", tipo_operacao="REMESSA_CONSERTO",
                            cfop_interno="5915", cfop_interestadual="6915",
                            natureza_operacao="Remessa para conserto",
                            cst_icms="41", cst_ipi="53", cst_pis="07", cst_cofins="07", ativo=1),
        RegraOperacaoFiscal(nome="Retorno Conserto", tipo_operacao="RETORNO_CONSERTO",
                            cfop_interno="5916", cfop_interestadual="6916",
                            natureza_operacao="Retorno de conserto",
                            cst_icms="41", cst_ipi="53", cst_pis="07", cst_cofins="07", ativo=1),
        RegraOperacaoFiscal(nome="Saida Geral", tipo_operacao="SAIDA_GERAL",
                            cfop_interno="5102", cfop_interestadual="6102",
                            natureza_operacao="Saida de mercadorias",
                            cst_icms="00", cst_ipi="50", cst_pis="01", cst_cofins="01", ativo=1),
    ]
    for r in regras:
        session.add(r)
    session.add(Configuracoes(fiscal_numeracao_atual=1, fiscal_serie="1"))
    session.commit()


def _criar_parceiro(session):
    dados = {
        "razao_social": "Parceiro NF Teste", "cnpj": CNPJ_PARCEIRO,
        "tipo": "CLIENTE", "uf": "SP",
    }
    _, _, p = ParceiroService.criar(session, dados, "admin")
    return p


def _item_base():
    return [{
        "codigo": "FER-001", "descricao": "Furadeira",
        "ncm": "84672200", "quantidade": 1, "valor_unitario": 500.0,
        "unidade": "UN",
    }]


class TestCriarRemessaConserto:
    def test_cria_com_sucesso(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        ok, msg, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "Teste remessa", "admin",
            num_os="OS-001", asset_tag="TAG-001"
        )
        assert ok is True
        assert doc_id is not None
        assert "RASCUNHO" in msg

    def test_sem_itens_rejeitado(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        ok, msg, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, [], "1", "", "admin"
        )
        assert ok is False
        assert doc_id is None

    def test_parceiro_inexistente(self, db_session):
        _seed_regras(db_session)
        ok, msg, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, 99999, _item_base(), "1", "", "admin"
        )
        assert ok is False

    def test_sem_regra_retorna_erro(self, db_session):
        p = _criar_parceiro(db_session)
        ok, msg, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "admin"
        )
        assert ok is False
        assert "Regra fiscal" in msg

    def test_cfop_interestadual(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        EmitenteService.atualizar(db_session, {"uf": "RJ"}, "admin")
        ok, _, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "admin"
        )
        assert ok is True
        doc = db_session.query(DocumentoFiscal).get(doc_id)
        assert doc.cfop == "6915"  # SP ≠ RJ → interestadual

    def test_numeracao_auto_incrementa(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "admin"
        )
        DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "admin"
        )
        docs = db_session.query(DocumentoFiscal).order_by(DocumentoFiscal.id).all()
        assert docs[0].numero == "1"
        assert docs[1].numero == "2"

    def test_log_auditoria_criado(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "audit_user"
        )
        log = db_session.query(LogAuditoria).filter_by(acao="DOC_FISCAL_CRIADO").first()
        assert log is not None
        assert log.usuario == "audit_user"


class TestAprovar:
    def _criar_doc(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        _, _, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "admin"
        )
        return doc_id

    def test_aprovar_rascunho(self, db_session):
        doc_id = self._criar_doc(db_session)
        ok, msg = DocumentoFiscalService.aprovar(
            db_session, doc_id, "NF-00001", "CHAVE123", "PROT456", "gestor"
        )
        assert ok is True
        doc = db_session.query(DocumentoFiscal).get(doc_id)
        assert doc.status == "EMITIDA"
        assert doc.aprovado_por == "gestor"
        assert doc.numero == "NF-00001"

    def test_aprovar_cancelado_bloqueado(self, db_session):
        doc_id = self._criar_doc(db_session)
        DocumentoFiscalService.cancelar(db_session, doc_id, "Motivo", "admin")
        ok, msg = DocumentoFiscalService.aprovar(db_session, doc_id, "", "", "", "gestor")
        assert ok is False

    def test_aprovar_inexistente(self, db_session):
        _seed_regras(db_session)
        ok, msg = DocumentoFiscalService.aprovar(db_session, 99999, "", "", "", "gestor")
        assert ok is False


class TestCancelar:
    def _criar_doc(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        _, _, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "", "admin"
        )
        return doc_id

    def test_cancelar_rascunho(self, db_session):
        doc_id = self._criar_doc(db_session)
        ok, msg = DocumentoFiscalService.cancelar(db_session, doc_id, "Cancelamento de teste", "admin")
        assert ok is True
        doc = db_session.query(DocumentoFiscal).get(doc_id)
        assert doc.status == "CANCELADA"
        assert doc.motivo_rejeicao == "Cancelamento de teste"

    def test_cancelar_emitida_bloqueado(self, db_session):
        doc_id = self._criar_doc(db_session)
        DocumentoFiscalService.aprovar(db_session, doc_id, "NF-001", "", "", "admin")
        ok, msg = DocumentoFiscalService.cancelar(db_session, doc_id, "motivo", "admin")
        assert ok is False

    def test_cancelar_inexistente(self, db_session):
        _seed_regras(db_session)
        ok, msg = DocumentoFiscalService.cancelar(db_session, 99999, "motivo", "admin")
        assert ok is False


class TestSerializar:
    def test_serializar_completo(self, db_session):
        _seed_regras(db_session)
        p = _criar_parceiro(db_session)
        _, _, doc_id = DocumentoFiscalService.criar_remessa_conserto(
            db_session, p.id, _item_base(), "1", "Obs test", "admin",
            num_os="OS-99", asset_tag="TAG-99"
        )
        doc = db_session.query(DocumentoFiscal).get(doc_id)
        d = DocumentoFiscalService.serializar(doc)
        assert d["subtipo"] == "REMESSA_CONSERTO"
        assert d["status"] == "RASCUNHO"
        assert len(d["itens"]) == 1
        assert d["itens"][0]["codigo_produto"] == "FER-001"
        assert d["num_os"] == "OS-99"
        assert d["asset_tag"] == "TAG-99"
        assert len(d["status_historico"]) >= 1
