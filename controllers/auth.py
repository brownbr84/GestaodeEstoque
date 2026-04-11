# Tela de Login
# tracebox/controllers/auth.py
import hashlib
from database.queries import carregar_dados, executar_query

def configurar_banco_seguranca():
    """Cria a tabela de usuários se ela não existir e injeta o 1º Admin"""
    
    query_tabela = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        perfil TEXT NOT NULL
    )
    """
    executar_query(query_tabela)
    
    # Verifica se a tabela está vazia. Se estiver, cria o Admin Mestre.
    df_users = carregar_dados("SELECT id FROM usuarios")
    if df_users.empty:
        # Encripta a senha "admin123"
        senha_padrao_criptografada = hashlib.sha256("admin123".encode()).hexdigest()
        
        executar_query(
            "INSERT INTO usuarios (nome, usuario, senha, perfil) VALUES (?, ?, ?, ?)",
            ("Gestor Mestre", "admin", senha_padrao_criptografada, "Admin")
        )

def autenticar_usuario(usuario_digitado, senha_digitada):
    """Verifica as credenciais e retorna os dados do usuário se baterem"""
    
    # 1. Garante que o banco está pronto
    configurar_banco_seguranca()
    
    # 2. Encripta a senha que o utilizador digitou na tela
    senha_hash = hashlib.sha256(senha_digitada.encode()).hexdigest()
    
    # 3. Vai ao banco tentar achar aquele utilizador com aquele hash de senha
    query = "SELECT nome, perfil FROM usuarios WHERE usuario = ? AND senha = ?"
    df = carregar_dados(query, (usuario_digitado, senha_hash))
    
    if not df.empty:
        # Credenciais corretas! Retorna o dicionário de sessão
        return {
            'nome': df.iloc[0]['nome'],
            'perfil': df.iloc[0]['perfil']
        }
    
    # Se chegou aqui, a senha ou usuário estão errados
    return None