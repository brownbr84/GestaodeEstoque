# tracebox/controllers/manutencao.py
from database.conexao_orm import SessionLocal
from services.manutencao_service import ManutencaoService
from repositories.manutencao_repository import ManutencaoRepository
from repositories.imobilizado_repository import ImobilizadoRepository
from database.models import Imobilizado
import pandas as pd

def abrir_ordem_manutencao(ferramenta_id, codigo, motivo, solicitante, usuario_atual):
    with SessionLocal() as session:
        return ManutencaoService.abrir_ordem_manutencao(session, int(ferramenta_id), codigo, motivo, solicitante, usuario_atual)

def lancar_orcamento_oficina(ordem_id, diagnostico, custo_estimado, mecanico, empresa, num_orcamento, usuario_atual):
    with SessionLocal() as session:
        return ManutencaoService.lancar_orcamento(session, int(ordem_id), diagnostico, custo_estimado, mecanico, empresa, num_orcamento, usuario_atual)

def aprovar_manutencao(ordem_id, decisao, usuario_atual):
    with SessionLocal() as session:
        return ManutencaoService.aprovar_manutencao(session, int(ordem_id), decisao, usuario_atual)

def finalizar_reparo_oficina(ordem_id, ferramenta_id, polo_destino, usuario_atual):
    with SessionLocal() as session:
        return ManutencaoService.finalizar_reparo(session, int(ordem_id), int(ferramenta_id), polo_destino, usuario_atual)

# Funções de Leitura para a View
def carregar_ativos_para_manutencao():
    with SessionLocal() as session:
        # Pega todos que não estão em Manutenção, não Sucateado, >0, categoria não Consumo
        # Como o ImobilizadoRepository.get_all não tem todos esses filtros, usaremos SQLAlchemy simples
        resultados = session.query(Imobilizado).filter(
            Imobilizado.status.notin_(['Manutenção', 'Sucateado']),
            Imobilizado.quantidade > 0,
            ~Imobilizado.categoria.like('%Consumo%'),
            Imobilizado.categoria != 'Consumíveis'
        ).all()
        
        return pd.DataFrame([{
            'id': r.id, 'codigo': r.codigo, 'descricao': r.descricao,
            'num_tag': r.num_tag, 'localizacao': r.localizacao,
            'quantidade': r.quantidade, 'categoria': r.categoria
        } for r in resultados])

def carregar_ordens_abertas():
    with SessionLocal() as session:
        repo = ManutencaoRepository()
        dados = repo.get_ordens_abertas(session)
        return pd.DataFrame([{
            'id': o.id, 'codigo_ferramenta': o.codigo_ferramenta, 'descricao': i.descricao,
            'num_tag': i.num_tag, 'motivo_falha': o.motivo_falha, 'solicitante': o.solicitante
        } for o, i in dados])

def carregar_ordens_aprovacao():
    with SessionLocal() as session:
        repo = ManutencaoRepository()
        dados = repo.get_ordens_aguardando_aprovacao(session)
        return pd.DataFrame([{
            'id': o.id, 'ferramenta_id': o.ferramenta_id, 'codigo_ferramenta': o.codigo_ferramenta,
            'descricao': i.descricao, 'num_tag': i.num_tag, 'valor_unitario': i.valor_unitario,
            'custo_reparo': o.custo_reparo, 'diagnostico': o.diagnostico,
            'empresa_reparo': o.empresa_reparo, 'num_orcamento': o.num_orcamento
        } for o, i in dados])

def carregar_ordens_execucao():
    with SessionLocal() as session:
        repo = ManutencaoRepository()
        dados = repo.get_ordens_em_execucao(session)
        return pd.DataFrame([{
            'id': o.id, 'ferramenta_id': o.ferramenta_id, 'codigo_ferramenta': o.codigo_ferramenta,
            'descricao': i.descricao, 'num_tag': i.num_tag
        } for o, i in dados])

def carregar_historico_concluidas(ferramenta_id):
    with SessionLocal() as session:
        repo = ManutencaoRepository()
        dados = repo.get_historico_concluidas(session, ferramenta_id)
        return pd.DataFrame([{
            'Data': o.data_saida, 'Serviço': o.diagnostico,
            'Fornecedor': o.empresa_reparo, 'Valor (R$)': o.custo_reparo
        } for o in dados])