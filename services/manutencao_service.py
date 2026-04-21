# services/manutencao_service.py
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from database.models import Imobilizado, Movimentacao, ManutencaoOrdem
from services.governance_service import GovernanceService

class ManutencaoService:

    @staticmethod
    def abrir_ordem_manutencao(session: Session, ferramenta_id: int, codigo: str, motivo: str, solicitante: str, usuario: str):
        try:
            # 1. Validação: Já está na oficina?
            em_aberto = session.query(ManutencaoOrdem).filter(
                ManutencaoOrdem.ferramenta_id == ferramenta_id,
                ManutencaoOrdem.status_ordem.notin_(['Concluída', 'Sucateado'])
            ).first()
            
            if em_aberto:
                return False, "Este item específico já está na oficina."

            agora = datetime.now()
            item = session.query(Imobilizado).filter(Imobilizado.id == ferramenta_id).first()
            if not item:
                return False, "Ativo não encontrado."

            id_para_oficina = ferramenta_id

            # 2. LÓGICA DE SPLIT SEGURO (Lotes)
            if item.quantidade > 1:
                item.quantidade -= 1
                
                # Clona a unidade avariada
                novo_item = Imobilizado(
                    codigo=item.codigo, descricao=item.descricao, categoria=item.categoria,
                    valor_unitario=item.valor_unitario, num_tag=item.num_tag, status='Manutenção',
                    localizacao='Oficina', quantidade=1, alerta_falta=item.alerta_falta,
                    tipo_material=item.tipo_material, tipo_controle=item.tipo_controle
                )
                session.add(novo_item)
                session.flush() # Salva temporariamente para pegar o ID
                id_para_oficina = novo_item.id
            else:
                # É unidade única
                item.status = 'Manutenção'
                item.localizacao = 'Oficina'

            # 3. Cria a Ordem de Serviço
            nova_os = ManutencaoOrdem(
                ferramenta_id=id_para_oficina, codigo_ferramenta=codigo, data_entrada=agora,
                motivo_falha=motivo, solicitante=solicitante, status_ordem='Aberta'
            )
            session.add(nova_os)
            session.flush()

            # 4. Movimentação Logística e Auditoria (Compliance)
            doc_mov = f"Avaria reportada por {solicitante}"
            mov = Movimentacao(ferramenta_id=id_para_oficina, tipo='Envio Manutenção', responsavel=usuario, destino_projeto='Oficina', documento=doc_mov, data_movimentacao=agora)
            session.add(mov)

            detalhes_log = f"Abertura de OS-{nova_os.id} para avaria do ativo {codigo} ({id_para_oficina})"
            GovernanceService.registar_log(session, usuario, 'manutencao_ordens', nova_os.id, 'ABERTURA_OS', detalhes_log)

            session.commit()
            
            # 5. E-MAIL AUTOMÁTICO
            try:
                from database.models import Configuracoes
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                import threading
                
                config = session.query(Configuracoes).first()
                if config and config.email_smtp and config.senha_smtp and config.emails_destinatarios:
                    def disparar_email(smtp_user, smtp_pass, dests, os_id, cod, desc, sol, mot):
                        try:
                            msg = MIMEMultipart()
                            msg['From'] = smtp_user
                            msg['To'] = ", ".join(dests)
                            msg['Subject'] = f"🚨 TraceBox: Nova OS Abertura - {cod}"
                            
                            corpo = f"""
                            <h2>Nova Ordem de Serviço (OS-{os_id})</h2>
                            <p><strong>Produto:</strong> {cod} - {desc}</p>
                            <p><strong>Solicitante:</strong> {sol}</p>
                            <p><strong>Motivo/Relato:</strong> {mot}</p>
                            <hr>
                            <p><em>Este é um e-mail automático do sistema TraceBox.</em></p>
                            """
                            msg.attach(MIMEText(corpo, 'html'))
                            
                            # Supondo Gmail SMTP
                            server = smtplib.SMTP('smtp.gmail.com', 587)
                            server.starttls()
                            server.login(smtp_user, smtp_pass)
                            server.send_message(msg)
                            server.quit()
                        except Exception as e:
                            print(f"Erro ao enviar email OS-{os_id}: {e}")
                    
                    threading.Thread(target=disparar_email, args=(
                        config.email_smtp, config.senha_smtp, config.emails_destinatarios,
                        nova_os.id, item.codigo, item.descricao, solicitante, motivo
                    )).start()
            except Exception as e:
                print(f"Erro ao inicializar thread de email: {e}")
            
            return True, f"OS-{nova_os.id} aberta com sucesso! Estoque atualizado."
        except Exception as e:
            session.rollback()
            return False, f"Erro ao abrir OS: {str(e)}"

    @staticmethod
    def lancar_orcamento(session: Session, ordem_id: int, diagnostico: str, custo: float, mecanico: str, empresa: str, num_orcamento: str, usuario: str):
        try:
            os = session.query(ManutencaoOrdem).filter(ManutencaoOrdem.id == ordem_id).first()
            if not os: return False
            
            os.diagnostico = diagnostico
            os.custo_reparo = custo
            os.mecanico_responsavel = mecanico
            os.empresa_reparo = empresa
            os.num_orcamento = num_orcamento
            os.status_ordem = 'Aguardando Aprovação'

            detalhes_log = f"Orçamento lançado para OS-{ordem_id}. Custo: R$ {custo:.2f} via {empresa or 'Oficina Interna'}"
            GovernanceService.registar_log(session, usuario, 'manutencao_ordens', ordem_id, 'ORCAMENTO_OS', detalhes_log)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False

    @staticmethod
    def aprovar_manutencao(session: Session, ordem_id: int, decisao: str, usuario: str):
        try:
            os = session.query(ManutencaoOrdem).filter(ManutencaoOrdem.id == ordem_id).first()
            if not os: return False

            if decisao == "Aprovar":
                os.status_ordem = 'Em Execução'
                GovernanceService.registar_log(session, usuario, 'manutencao_ordens', ordem_id, 'APROVACAO_OS', "Orçamento aprovado para reparo.")
            else:
                os.status_ordem = 'Sucateado'
                os.data_saida = datetime.now()
                
                item = session.query(Imobilizado).filter(Imobilizado.id == os.ferramenta_id).first()
                if item:
                    item.status = 'Sucateado'
                    item.quantidade = 0
                    
                mov = Movimentacao(ferramenta_id=os.ferramenta_id, tipo='Baixa/Sucata', responsavel=usuario, destino_projeto='Sucata', documento=f"Reprovação OS-{ordem_id}", data_movimentacao=datetime.now())
                session.add(mov)
                GovernanceService.registar_log(session, usuario, 'manutencao_ordens', ordem_id, 'REPROVACAO_OS', "Orçamento reprovado. Item sucateado.")

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False

    @staticmethod
    def finalizar_reparo(session: Session, ordem_id: int, ferramenta_id: int, polo_destino: str, usuario: str):
        try:
            agora = datetime.now()
            os = session.query(ManutencaoOrdem).filter(ManutencaoOrdem.id == ordem_id).first()
            item = session.query(Imobilizado).filter(Imobilizado.id == ferramenta_id).first()

            if os:
                os.data_saida = agora
                os.status_ordem = 'Concluída'
                empresa = os.empresa_reparo if os.empresa_reparo else "Oficina Interna"
            else:
                empresa = "Oficina Interna"

            if item:
                item.status = 'Disponível'
                item.localizacao = polo_destino

            doc_mov = f"OS-{ordem_id} concluída por {empresa}"
            mov = Movimentacao(ferramenta_id=ferramenta_id, tipo='Retorno Manutenção', responsavel=usuario, destino_projeto=polo_destino, documento=doc_mov, data_movimentacao=agora)
            session.add(mov)

            GovernanceService.registar_log(session, usuario, 'manutencao_ordens', ordem_id, 'CONCLUSAO_OS', f"Reparo finalizado. Item reincorporado ao polo {polo_destino}.")

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False