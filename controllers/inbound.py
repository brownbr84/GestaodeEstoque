# tracebox/controllers/inbound.py
import pandas as pd
from database.conexao_orm import SessionLocal
from services.inbound_service import InboundService

def processar_entrada_compra(codigo_produto, polo_destino, nf, valor_unit, quantidade, usuario):
    with SessionLocal() as session:
        return InboundService.processar_entrada_compra(session, codigo_produto, polo_destino, nf, valor_unit, quantidade, usuario)

# ==========================================
# MÓDULO 2: DOCA DE DESCARGA WMS
# ==========================================

def obter_origens_esperadas(polo_atual):
    with SessionLocal() as session:
        return InboundService.obter_origens_esperadas(session, polo_atual)

def carregar_itens_esperados(origem, polo):
    with SessionLocal() as session:
        dados = InboundService.carregar_itens_esperados(session, origem, polo)
        # Convertendo a lista do ORM para DataFrame para a View usar como antes
        return pd.DataFrame(dados) if dados else pd.DataFrame()

def processar_recebimento_doca(origem, polo_atual, dict_ativos, dict_lotes, df_esperados, usuario):
    with SessionLocal() as session:
        return InboundService.processar_recebimento_doca(
            session, origem, polo_atual, dict_ativos, dict_lotes, df_esperados, usuario
        )

# ==========================================
# MÓDULO 3: MALHA FINA (FALTAS)
# ==========================================
def processar_reintegracao_falta(id_db, qtd_enc, qtd_pendente, destino, usuario):
    with SessionLocal() as session:
        return InboundService.processar_reintegracao_falta(
            session, id_db, qtd_enc, qtd_pendente, destino, usuario
        )

def processar_baixa_extravio(id_db, qtd_perda, qtd_pendente, origem, motivo, usuario):
    with SessionLocal() as session:
        return InboundService.processar_baixa_extravio(
            session, id_db, qtd_perda, qtd_pendente, origem, motivo, usuario
        )

def realizar_entrada_excepcional(carrinho, motivo, documento, usuario, polo, perfil_usuario="Operador"):
    with SessionLocal() as session:
        ok, msg, tags = InboundService.realizar_entrada_excepcional(session, carrinho, motivo, documento, usuario, polo, perfil_usuario)
        return ok, msg, tags