import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock
import smtplib

from services.email_service import EmailService
from database.models import Configuracoes


def _inserir_config(session, porta=587):
    from cryptography.fernet import Fernet
    from utils.security import criptografar
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
    cfg = Configuracoes(
        email_smtp="remetente@test.com",
        senha_smtp=criptografar("senhateste"),
        smtp_host="smtp.test.com",
        smtp_porta=porta,
        emails_destinatarios=["dest@test.com"],
    )
    session.add(cfg)
    session.commit()
    return cfg


class TestObterConfigSmtp:
    def test_sem_config_retorna_erro(self, db_session):
        cfg, err = EmailService._obter_config_smtp(db_session)
        assert cfg is None
        assert "não encontradas" in err

    def test_sem_smtp_retorna_erro(self, db_session):
        session = db_session
        session.add(Configuracoes(email_smtp=None, senha_smtp=None))
        session.commit()
        cfg, err = EmailService._obter_config_smtp(session)
        assert cfg is None

    def test_config_completa_retorna_dict(self, db_session):
        _inserir_config(db_session)
        cfg, err = EmailService._obter_config_smtp(db_session)
        assert cfg is not None
        assert err == ""
        assert cfg["remetente"] == "remetente@test.com"
        assert cfg["host"] == "smtp.test.com"
        assert cfg["porta"] == 587


class TestEnviar:
    def test_sem_config_retorna_false(self, db_session):
        ok, msg = EmailService.enviar(db_session, "Assunto", "<p>corpo</p>")
        assert ok is False

    def test_sucesso_tls(self, db_session):
        _inserir_config(db_session, porta=587)
        mock_server = MagicMock()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.return_value = mock_server
            ok, msg = EmailService.enviar(db_session, "Teste", "<p>ok</p>")
        assert ok is True
        assert msg == ""
        mock_server.send_message.assert_called_once()

    def test_sucesso_ssl(self, db_session):
        _inserir_config(db_session, porta=465)
        mock_server = MagicMock()
        with patch("smtplib.SMTP_SSL") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.return_value = mock_server
            ok, msg = EmailService.enviar(db_session, "Teste SSL", "<p>ok</p>")
        assert ok is True

    def test_auth_error(self, db_session):
        _inserir_config(db_session)
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
            ok, msg = EmailService.enviar(db_session, "X", "y")
        assert ok is False
        assert "autenticação" in msg.lower()

    def test_connect_error(self, db_session):
        _inserir_config(db_session)
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.side_effect = smtplib.SMTPConnectError(421, b"unavail")
            ok, msg = EmailService.enviar(db_session, "X", "y")
        assert ok is False
        assert "conectar" in msg.lower()

    def test_generic_error(self, db_session):
        _inserir_config(db_session)
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.side_effect = RuntimeError("boom")
            ok, msg = EmailService.enviar(db_session, "X", "y")
        assert ok is False
        assert "inesperado" in msg.lower()


class TestTemplates:
    def test_abertura_os(self):
        assunto, corpo = EmailService.template_abertura_os(42, "FER-001", "Furadeira", "Carlos", "Não liga")
        assert "OS-42" in assunto
        assert "FER-001" in corpo
        assert "Carlos" in corpo

    def test_nova_requisicao(self):
        itens = [{"codigo_produto": "P1", "descricao_produto": "Produto 1", "quantidade_solicitada": 3}]
        assunto, corpo = EmailService.template_nova_requisicao(7, "Maria", "Obra Central", itens)
        assert "REQ-0007" in assunto
        assert "P1" in corpo
        assert "Maria" in corpo
