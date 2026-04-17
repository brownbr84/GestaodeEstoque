# tracebox/controllers/cadastro.py
from database.queries import executar_query, carregar_dados

def configurar_tabela_cadastro():
    """Garante que a coluna tipo_controle existe na base, de forma silenciosa e segura."""
    df_schema = carregar_dados("PRAGMA table_info(imobilizado)")
    if not df_schema.empty:
        colunas = df_schema['name'].str.lower().tolist()
        if 'tipo_controle' not in colunas:
            executar_query("ALTER TABLE imobilizado ADD COLUMN tipo_controle TEXT DEFAULT 'TAG'")

def cadastrar_novo_produto(codigo, descricao, marca, modelo, categoria, dimensoes, capacidade, valor_unit, tipo_material, tipo_controle, imagem_b64, usuario):
    configurar_tabela_cadastro()
    
    check = carregar_dados("SELECT id FROM imobilizado WHERE upper(codigo) = ?", (codigo.upper(),))
    if not check.empty:
        return False, "Este código já existe no cadastro de Master Data."

    query = """
        INSERT INTO imobilizado 
        (codigo, descricao, marca, modelo, categoria, dimensoes, capacidade, 
         valor_unitario, tipo_material, tipo_controle, imagem, quantidade, localizacao, status, num_tag, data_aquisicao) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'Geral/Catálogo', 'Catálogo', '', date('now'))
    """
    
    id_novo = executar_query(query, (
        codigo.upper(), descricao, marca, modelo, categoria, dimensoes, capacidade, 
        valor_unit, tipo_material, tipo_controle.upper(), imagem_b64
    ))

    if id_novo:
        executar_query(
            "INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Criação Master Data', ?, 'Sistema', 'Setup Inicial')", 
            (id_novo, usuario)
        )
        return True, "Master Data cadastrado com sucesso! Produto pronto para receber estoque via Inbound."
    
    return False, "Erro ao gravar no banco de dados."