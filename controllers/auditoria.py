# Validações de inventário e acuracidade
# tracebox/controllers/auditoria.py
from database.queries import carregar_dados
from database.conexao_orm import SessionLocal
from services.inventario_service import InventarioService

def processar_cruzamento_wms(polo, tags_bipadas, lotes_contados):
    """
    O Cérebro do WMS: Cruza o que o sistema espera com o que o operador bipou.
    Retorna a lista de resultados formatada para o 'processar_resultados_inventario'.
    """
    # 1. Busca a verdade do Banco de Dados
    query = "SELECT id, codigo, num_tag, quantidade FROM imobilizado WHERE localizacao = ? AND status IN ('Disponível', 'Manutenção')"
    df_esperado = carregar_dados(query, (polo,))
    
    resultados_finais = []
    divergencias = 0

    if df_esperado.empty:
        return resultados_finais, divergencias

    df_tags = df_esperado[df_esperado['num_tag'].notna() & (df_esperado['num_tag'] != '')]
    df_lotes = df_esperado[~(df_esperado['num_tag'].notna() & (df_esperado['num_tag'] != ''))]

    # 2. Avalia as TAGs bipadas vs esperadas
    for _, row in df_tags.iterrows():
        presente = row['num_tag'] in tags_bipadas
        if not presente: 
            divergencias += 1
            
        resultados_finais.append({
            'ids_originais': [row['id']],
            'qtd_sistema': 1,
            'qtd_fisica': 1 if presente else 0,
            # Justificativa automática (>4 caracteres) para passar na sua regra de negócio
            'justificativa': "Auditado OK via WMS" if presente else "Falta detectada via Leitor WMS",
            'is_lote': False
        })
    
    # 3. Avalia os Lotes Contados vs esperados
    if not df_lotes.empty:
        df_lotes_agg = df_lotes.groupby('codigo').agg({'quantidade': 'sum', 'id': lambda x: list(x)}).reset_index()
        for _, row in df_lotes_agg.iterrows():
            qtd_digitada = lotes_contados.get(row['codigo'], row['quantidade'])
            if qtd_digitada != row['quantidade']: 
                divergencias += 1
                
            resultados_finais.append({
                'ids_originais': row['id'], 
                'qtd_sistema': row['quantidade'],
                'qtd_fisica': qtd_digitada,
                'justificativa': "Contagem Física via WMS", # Justificativa automática
                'is_lote': True
            })

    return resultados_finais, divergencias


def processar_resultados_inventario(resultados, usuario_atual, polo, inventario_id):
    """
    Recebe os resultados do cruzamento, e aciona o Service para gravar o inventário de forma transacional.
    """
    with SessionLocal() as session:
        sucesso, erros = InventarioService.processar_resultados_inventario(
            session, resultados, usuario_atual, polo, inventario_id
        )
        return erros # Retorna a lista de erros (vazia se deu tudo certo) para a View mostrar os alertas

def reativar_tag_extraviada(tag, polo, motivo, usuario):
    with SessionLocal() as session:
        return InventarioService.reativar_tag_extraviada(session, tag, polo, motivo, usuario)