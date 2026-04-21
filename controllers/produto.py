# tracebox/controllers/produto.py
import pandas as pd
from database.conexao_orm import SessionLocal
from database.models import Imobilizado

# ==========================================
# 1. GESTÃO DO MASTER DATA (FICHA TÉCNICA)
# ==========================================
def atualizar_ficha_tecnica(codigo, dados_up):
    """
    Atualiza as características globais do produto.
    O texto é atualizado em todos os itens para manter a consistência de busca, 
    mas a IMAGEM é guardada APENAS no Master Data para poupar espaço!
    """
    with SessionLocal() as db:
        db.query(Imobilizado).filter(Imobilizado.codigo == codigo).update({
            Imobilizado.descricao: dados_up.get('descricao'),
            Imobilizado.marca: dados_up.get('marca'),
            Imobilizado.modelo: dados_up.get('modelo'),
            Imobilizado.categoria: dados_up.get('categoria'),
            Imobilizado.valor_unitario: dados_up.get('valor_unitario'),
            Imobilizado.dimensoes: dados_up.get('dimensoes'),
            Imobilizado.capacidade: dados_up.get('capacidade'),
            Imobilizado.ultima_manutencao: dados_up.get('ultima_manutencao'),
            Imobilizado.proxima_manutencao: dados_up.get('proxima_manutencao'),
            Imobilizado.detalhes: dados_up.get('detalhes')
        })
        
        # 2. 💡 Força a gravação da imagem APENAS no Master Data (Catálogo)
        if 'imagem' in dados_up and dados_up['imagem']:
            db.query(Imobilizado).filter(Imobilizado.codigo == codigo, Imobilizado.status == 'Catálogo').update({
                Imobilizado.imagem: dados_up['imagem']
            })
            
        db.commit()
    return True

def deletar_produto_master(codigo):
    with SessionLocal() as db:
        db.query(Imobilizado).filter(Imobilizado.codigo == codigo, Imobilizado.status == 'Catálogo').delete()
        db.commit()
    return True

# ==========================================
# 2. GESTÃO INDIVIDUAL (CALIBRAÇÃO DE TAGS)
# ==========================================
def atualizar_calibracao_tags(df_editado, usuario):
    with SessionLocal() as db:
        for _, row in df_editado.iterrows():
            id_db = int(row['ID_DB'])
            ult_insp = row['Última Inspeção']
            prox_insp = row['Deadline Calibração']
            
            ult_insp_str = str(ult_insp)[:10] if pd.notna(ult_insp) and str(ult_insp).strip() else None
            prox_insp_str = str(prox_insp)[:10] if pd.notna(prox_insp) and str(prox_insp).strip() else None
            
            db.query(Imobilizado).filter(Imobilizado.id == id_db).update({
                Imobilizado.ultima_manutencao: ult_insp_str,
                Imobilizado.proxima_manutencao: prox_insp_str
            })
        db.commit()
        
    return True, "As datas de inspeção e calibração foram atualizadas com sucesso!"