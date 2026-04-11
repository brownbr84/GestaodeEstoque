# tracebox/controllers/cadastro.py
import os
from database.queries import carregar_dados, executar_query

def obter_proximo_codigo():
    """Busca o último ID no banco e gera o próximo código formatado (Ex: TRC-0015)"""
    df = carregar_dados("SELECT id FROM imobilizado ORDER BY id DESC LIMIT 1")
    if not df.empty:
        ultimo_id = df.iloc[0]['id']
        return f"TRC-{(ultimo_id + 1):04d}"
    return "TRC-0001"

def processar_commit_master_data(dados, arquivo_foto, usuario_atual):
    """
    Controlador que processa a criação de Master Data.
    Lida com Upload de Arquivos, formatação (Upper Case) e explosão de Lotes (TAGs).
    """
    
    # 1. Função interna de padronização (o seu to_upper)
    def to_upper(texto):
        return str(texto).strip().upper() if texto else ""

    # Padroniza os dados textuais
    desc = to_upper(dados['descricao'])
    marc = to_upper(dados['marca'])
    mod = to_upper(dados['modelo'])
    cap = to_upper(dados['capacidade'])
    dim = to_upper(dados['dimensoes'])
    det = to_upper(dados['detalhes'])
    doc = to_upper(dados['doc_entrada'])
    u_man = to_upper(dados['ultima_manutencao'])
    p_man = to_upper(dados['proxima_manutencao'])
    
    lista_tags = [to_upper(t) for t in dados['num_tags'].split(',')] if dados['num_tags'].strip() else []

    # 2. Processamento da Imagem
    caminho_arquivo = ""
    if arquivo_foto:
        # Garante que a pasta existe
        os.makedirs("imagens_estoque", exist_ok=True)
        caminho_arquivo = os.path.join("imagens_estoque", f"prod_{dados['codigo_final']}_{arquivo_foto.name}")
        with open(caminho_arquivo, "wb") as f: 
            f.write(arquivo_foto.getbuffer())

    # 3. Query base (Adicionei o alerta_falta com 0 no final para não quebrar a arquitetura nova)
    query_insert = """
        INSERT INTO imobilizado 
        (codigo, descricao, marca, modelo, num_tag, quantidade, status, localizacao, 
         categoria, valor_unitario, data_aquisicao, dimensoes, capacidade, 
         ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material, alerta_falta) 
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 0)
    """

    sucesso = False

    # 4. Regra de Negócio: Rastreabilidade Individual (Várias TAGs) vs Lote Volumétrico
    if "Rastreabilidade" in dados['tipo_controle']:
        for tag in lista_tags:
            if not tag: continue # Ignora vírgulas vazias
            
            n_id = executar_query(query_insert, (
                dados['codigo_final'], desc, marc, mod, tag, 1, dados['status'], 
                dados['localizacao'], dados['categoria'], dados['valor'], 
                str(dados['data_aq']), dim, cap, u_man, p_man, det, caminho_arquivo, dados['tipo_material']
            ))
            if n_id:
                executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Entrada', ?, ?, ?)", 
                              (n_id, usuario_atual, f"Implantação {dados['localizacao']}", doc))
                sucesso = True

    else:
        # Lote Volumétrico
        n_id = executar_query(query_insert, (
            dados['codigo_final'], desc, marc, mod, "", dados['quantidade_lote'], 
            dados['status'], dados['localizacao'], dados['categoria'], dados['valor'], 
            str(dados['data_aq']), dim, cap, u_man, p_man, det, caminho_arquivo, dados['tipo_material']
        ))
        if n_id:
            executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?, 'Entrada', ?, ?, ?)", 
                          (n_id, usuario_atual, f"Implantação Lote {dados['localizacao']}", doc))
            sucesso = True

    return sucesso