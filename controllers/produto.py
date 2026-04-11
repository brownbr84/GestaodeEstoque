# tracebox/controllers/produto.py
from database.queries import executar_query

def atualizar_lotes_fisicos(df_editado, df_original, usuario_atual):
    """Verifica quais linhas foram alteradas na tabela e salva no banco com log."""
    for index, row in df_editado.iterrows():
        linha_original = df_original.loc[index]
        
        # Se o utilizador mudou o status ou o polo na tabela
        if row['status'] != linha_original['status'] or row['localizacao'] != linha_original['localizacao']:
            executar_query(
                "UPDATE imobilizado SET status = ?, localizacao = ? WHERE id = ?", 
                (row['status'], row['localizacao'], row['id'])
            )
            executar_query(
                "INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Ajuste', ?, ?, '')", 
                (row['id'], usuario_atual, f"Edição Admin: {row['status']} / {row['localizacao']}")
            )
    return True

def atualizar_ficha_tecnica(codigo, dados):
    """Atualiza as informações globais (Master Data) do produto."""
    
    # Função interna para padronizar para maiúsculas (o seu to_upper)
    to_upper = lambda x: str(x).strip().upper() if x else ""
    
    query = """
        UPDATE imobilizado 
        SET descricao=?, marca=?, modelo=?, categoria=?, valor_unitario=?, 
            dimensoes=?, capacidade=?, ultima_manutencao=?, proxima_manutencao=?, detalhes=? 
        WHERE codigo=?
    """
    executar_query(query, (
        to_upper(dados['descricao']), to_upper(dados['marca']), to_upper(dados['modelo']), 
        dados['categoria'], dados['valor_unitario'], to_upper(dados['dimensoes']), 
        to_upper(dados['capacidade']), to_upper(dados['ultima_manutencao']), 
        to_upper(dados['proxima_manutencao']), to_upper(dados['detalhes']), codigo
    ))
    return True

def deletar_produto_master(codigo):
    """Deleta todos os registros físicos de um código Master."""
    executar_query("DELETE FROM imobilizado WHERE codigo = ?", (codigo,))
    return True