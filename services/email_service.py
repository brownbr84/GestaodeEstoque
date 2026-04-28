# services/email_service.py
"""
TraceBox WMS — Serviço Central de E-mail

Responsabilidades:
  - Ler configurações SMTP do banco de dados
  - Descriptografar a senha SMTP (Fernet)
  - Enviar e-mails com suporte a TLS (587) e SSL (465)
  - Retornar (ok: bool, mensagem: str) — NUNCA falha silenciosamente
"""
from __future__ import annotations

import logging
import smtplib
from email import encoders as _encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailService:

    @staticmethod
    def _obter_config_smtp(session) -> tuple[dict | None, str]:
        """Lê e valida as configurações SMTP do banco. Retorna (config_dict, erro)."""
        from database.models import Configuracoes
        from utils.security import descriptografar

        config = session.query(Configuracoes).first()
        if not config:
            return None, "Configurações do sistema não encontradas."
        if not config.email_smtp:
            return None, "E-mail SMTP não configurado. Acesse Configurações → Automação de E-mails."
        if not config.senha_smtp:
            return None, "Senha SMTP não configurada. Acesse Configurações → Automação de E-mails."
        if not config.emails_destinatarios:
            return None, "Nenhum destinatário configurado. Acesse Configurações → Automação de E-mails."

        senha_plain = descriptografar(config.senha_smtp)

        return {
            "remetente":     config.email_smtp,
            "senha":         senha_plain,
            "host":          (config.smtp_host or "smtp.gmail.com").strip(),
            "porta":         config.smtp_porta or 587,
            "destinatarios": config.emails_destinatarios,
        }, ""

    @staticmethod
    def enviar(session, assunto: str, corpo_html: str) -> tuple[bool, str]:
        """
        Envia e-mail para os destinatários configurados no sistema.
        Retorna (True, "") em sucesso ou (False, motivo) em falha.
        """
        cfg, erro = EmailService._obter_config_smtp(session)
        if not cfg:
            logger.warning("E-mail não enviado: %s", erro)
            return False, erro

        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = cfg["remetente"]
        msg["To"]      = ", ".join(cfg["destinatarios"])
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        try:
            if cfg["porta"] == 465:
                with smtplib.SMTP_SSL(cfg["host"], cfg["porta"]) as server:
                    server.login(cfg["remetente"], cfg["senha"])
                    server.send_message(msg)
            else:
                with smtplib.SMTP(cfg["host"], cfg["porta"]) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(cfg["remetente"], cfg["senha"])
                    server.send_message(msg)

            logger.info("E-mail enviado: '%s' → %s", assunto, cfg["destinatarios"])
            return True, ""

        except smtplib.SMTPAuthenticationError:
            msg_erro = "Falha de autenticação SMTP. Verifique o e-mail e a senha do remetente."
            logger.error(msg_erro)
            return False, msg_erro
        except smtplib.SMTPConnectError:
            msg_erro = f"Não foi possível conectar ao servidor {cfg['host']}:{cfg['porta']}."
            logger.error(msg_erro)
            return False, msg_erro
        except Exception as exc:
            msg_erro = f"Erro inesperado ao enviar e-mail: {exc}"
            logger.error(msg_erro)
            return False, msg_erro

    @staticmethod
    def enviar_com_anexos(
        session,
        assunto: str,
        corpo_html: str,
        destinatarios_extra: list,
        anexos: list,
    ) -> tuple[bool, str]:
        """
        Envia e-mail com anexos binários (PDF, XML, etc.).

        anexos: lista de dicts {"nome": str, "dados": bytes, "tipo": str}
        destinatarios_extra: e-mails adicionais além dos configurados no sistema
        """
        cfg, erro = EmailService._obter_config_smtp(session)
        if not cfg:
            logger.warning("E-mail não enviado: %s", erro)
            return False, erro

        todos_dest = list(dict.fromkeys(
            cfg["destinatarios"] + [e.strip() for e in destinatarios_extra if e and e.strip()]
        ))

        msg = MIMEMultipart()
        msg["Subject"] = assunto
        msg["From"]    = cfg["remetente"]
        msg["To"]      = ", ".join(todos_dest)
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        for anexo in anexos:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(anexo["dados"])
            _encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{anexo["nome"]}"',
            )
            part.add_header("Content-Type", anexo.get("tipo", "application/octet-stream"))
            msg.attach(part)

        try:
            if cfg["porta"] == 465:
                with smtplib.SMTP_SSL(cfg["host"], cfg["porta"]) as server:
                    server.login(cfg["remetente"], cfg["senha"])
                    server.send_message(msg)
            else:
                with smtplib.SMTP(cfg["host"], cfg["porta"]) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(cfg["remetente"], cfg["senha"])
                    server.send_message(msg)

            logger.info("E-mail c/ anexos enviado: '%s' → %s", assunto, todos_dest)
            return True, ""

        except smtplib.SMTPAuthenticationError:
            msg_erro = "Falha de autenticação SMTP. Verifique o e-mail e a senha do remetente."
            logger.error(msg_erro)
            return False, msg_erro
        except smtplib.SMTPConnectError:
            msg_erro = f"Não foi possível conectar ao servidor {cfg['host']}:{cfg['porta']}."
            logger.error(msg_erro)
            return False, msg_erro
        except Exception as exc:
            msg_erro = f"Erro inesperado ao enviar e-mail: {exc}"
            logger.error(msg_erro)
            return False, msg_erro

    @staticmethod
    def enviar_fiscal_com_anexos(
        session,
        assunto: str,
        corpo_html: str,
        destinatarios: list,
        anexos: list,
    ) -> tuple[bool, str]:
        """
        Envia e-mail fiscal com anexos diretamente para os destinatários explícitos.

        Diferente de enviar_com_anexos, não exige emails_destinatarios configurados no sistema —
        o parceiro fiscal é o destinatário principal.  O remetente/credenciais SMTP são lidas
        das configurações, mas a lista de destinatários é a fornecida pelo chamador.

        destinatarios: lista de e-mails (ex: [parceiro.email_contato])
        anexos: lista de dicts {"nome": str, "dados": bytes, "tipo": str}
        """
        from database.models import Configuracoes
        from utils.security import descriptografar

        config = session.query(Configuracoes).first()
        if not config or not config.email_smtp or not config.senha_smtp:
            return False, "SMTP não configurado. Acesse Configurações → Automação de E-mails."

        destinatarios_validos = [e.strip() for e in destinatarios if e and e.strip()]
        if not destinatarios_validos:
            return False, "Nenhum e-mail de destinatário fornecido."

        senha_plain = descriptografar(config.senha_smtp)
        host   = (config.smtp_host or "smtp.gmail.com").strip()
        porta  = config.smtp_porta or 587

        msg = MIMEMultipart()
        msg["Subject"] = assunto
        msg["From"]    = config.email_smtp
        msg["To"]      = ", ".join(destinatarios_validos)
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        for anexo in anexos:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(anexo["dados"])
            _encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{anexo["nome"]}"')
            part.add_header("Content-Type", anexo.get("tipo", "application/octet-stream"))
            msg.attach(part)

        try:
            if porta == 465:
                with smtplib.SMTP_SSL(host, porta) as server:
                    server.login(config.email_smtp, senha_plain)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, porta) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(config.email_smtp, senha_plain)
                    server.send_message(msg)

            logger.info("E-mail fiscal enviado: '%s' → %s", assunto, destinatarios_validos)
            return True, ""

        except smtplib.SMTPAuthenticationError:
            msg_erro = "Falha de autenticação SMTP. Verifique o e-mail e a senha do remetente."
            logger.error(msg_erro)
            return False, msg_erro
        except smtplib.SMTPConnectError:
            msg_erro = f"Não foi possível conectar ao servidor {host}:{porta}."
            logger.error(msg_erro)
            return False, msg_erro
        except Exception as exc:
            msg_erro = f"Erro inesperado ao enviar e-mail: {exc}"
            logger.error(msg_erro)
            return False, msg_erro

    # ─────────────────────────────────────────────────────────────
    # Templates
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def template_abertura_os(os_id: int, codigo: str, descricao: str, solicitante: str, motivo: str) -> tuple[str, str]:
        """Retorna (assunto, corpo_html) para e-mail de abertura de OS."""
        assunto = f"TraceBox WMS — Nova OS Aberta: OS-{os_id} | {codigo}"
        corpo = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
          <div style="background:#1e40af;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="color:white;margin:0;">🚨 Nova Ordem de Serviço Aberta</h2>
          </div>
          <div style="border:1px solid #e2e8f0;padding:24px;border-radius:0 0 8px 8px;">
            <table style="width:100%;border-collapse:collapse;">
              <tr><td style="padding:8px;color:#64748b;width:40%;">Número da OS</td>
                  <td style="padding:8px;font-weight:bold;">OS-{os_id}</td></tr>
              <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;">Produto</td>
                  <td style="padding:8px;">{codigo} — {descricao}</td></tr>
              <tr><td style="padding:8px;color:#64748b;">Solicitante</td>
                  <td style="padding:8px;">{solicitante}</td></tr>
              <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;">Motivo / Relato</td>
                  <td style="padding:8px;">{motivo}</td></tr>
            </table>
            <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0;">
            <p style="color:#64748b;font-size:12px;">
              Este é um e-mail automático do sistema TraceBox WMS.<br>
              Acesse o sistema para lançar o orçamento e dar andamento à OS.
            </p>
          </div>
        </div>
        """
        return assunto, corpo

    @staticmethod
    def template_nova_requisicao(req_id: int, solicitante: str, destino: str, itens: list) -> tuple[str, str]:
        """Retorna (assunto, corpo_html) para e-mail de nova requisição."""
        assunto = f"TraceBox WMS — Nova Requisição: REQ-{req_id:04d} | {destino}"
        linhas_itens = "".join(
            f"<tr style='background:{'#f8fafc' if i % 2 == 0 else 'white'};'>"
            f"<td style='padding:8px;'>{item.get('codigo_produto', '')}</td>"
            f"<td style='padding:8px;'>{item.get('descricao_produto', '')}</td>"
            f"<td style='padding:8px;text-align:center;'>{item.get('quantidade_solicitada', '')}</td>"
            f"</tr>"
            for i, item in enumerate(itens)
        )
        corpo = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
          <div style="background:#0f766e;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="color:white;margin:0;">📋 Nova Requisição de Material</h2>
          </div>
          <div style="border:1px solid #e2e8f0;padding:24px;border-radius:0 0 8px 8px;">
            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
              <tr><td style="padding:8px;color:#64748b;width:40%;">Número</td>
                  <td style="padding:8px;font-weight:bold;">REQ-{req_id:04d}</td></tr>
              <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;">Solicitante</td>
                  <td style="padding:8px;">{solicitante}</td></tr>
              <tr><td style="padding:8px;color:#64748b;">Destino / Projeto</td>
                  <td style="padding:8px;">{destino}</td></tr>
            </table>
            <h4 style="color:#374151;margin-bottom:8px;">Itens Solicitados</h4>
            <table style="width:100%;border-collapse:collapse;">
              <thead>
                <tr style="background:#1e40af;color:white;">
                  <th style="padding:8px;text-align:left;">Código</th>
                  <th style="padding:8px;text-align:left;">Descrição</th>
                  <th style="padding:8px;text-align:center;">Qtd</th>
                </tr>
              </thead>
              <tbody>{linhas_itens}</tbody>
            </table>
            <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0;">
            <p style="color:#64748b;font-size:12px;">
              Este é um e-mail automático do sistema TraceBox WMS.<br>
              Acesse o sistema para analisar e atender a requisição.
            </p>
          </div>
        </div>
        """
        return assunto, corpo
