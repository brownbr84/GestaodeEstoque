# tracebox/controllers/produto.py
import pandas as pd
from database.queries import executar_query, carregar_dados

# ==========================================
# 1. GESTÃO DO MASTER DATA (FICHA TÉCNICA)
# ==========================================
def atualizar_ficha_tecnica(codigo, dados_up):
    """
    Atualiza as características globais do produto.
    O texto é atualizado em todos os itens para manter a consistência de busca, 
    mas a IMAGEM é guardada APENAS no Master Data para poupar espaço!
    """
    # 1. Atualiza os dados textuais de TODO o inventário deste código
    query_texto = """
        UPDATE imobilizado 
        SET descricao = ?, marca = ?, modelo = ?, categoria = ?, 
            valor_unitario = ?, dimensoes = ?, capacidade = ?, 
            ultima_manutencao = ?, proxima_manutencao = ?, detalhes = ?
        WHERE codigo = ?
    """
    valores_texto = (
        dados_up.get('descricao'), dados_up.get('marca'), dados_up.get('modelo'), 
        dados_up.get('categoria'), dados_up.get('valor_unitario'), dados_up.get('dimensoes'), 
        dados_up.get('capacidade'), dados_up.get('ultima_manutencao'), dados_up.get('proxima_manutencao'), 
        dados_up.get('detalhes'), codigo
    )
    executar_query(query_texto, valores_texto)

    # 2. 💡 Força a gravação da imagem APENAS no Master Data (Catálogo)
    if 'imagem' in dados_up and dados_up['imagem']:
        executar_query("UPDATE imobilizado SET imagem = ? WHERE codigo = ? AND status = 'Catálogo'", (dados_up['imagem'], codigo))
        
    return True

def deletar_produto_master(codigo):
    executar_query("DELETE FROM imobilizado WHERE codigo = ? AND status = 'Catálogo'", (codigo,))
    return True

# ==========================================
# 2. GESTÃO INDIVIDUAL (CALIBRAÇÃO DE TAGS)
# ==========================================
def atualizar_calibracao_tags(df_editado, usuario):
    for _, row in df_editado.iterrows():
        id_db = int(row['ID_DB'])
        ult_insp = row['Última Inspeção']
        prox_insp = row['Deadline Calibração']
        
        ult_insp_str = str(ult_insp)[:10] if pd.notna(ult_insp) and str(ult_insp).strip() else None
        prox_insp_str = str(prox_insp)[:10] if pd.notna(prox_insp) and str(prox_insp).strip() else None
        
        executar_query(
            "UPDATE imobilizado SET ultima_manutencao = ?, proxima_manutencao = ? WHERE id = ?",
            (ult_insp_str, prox_insp_str, id_db)
        )
        
    return True, "As datas de inspeção e calibração foram atualizadas com sucesso!"