# tracebox/database/conexao.py
import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

# Carrega as variáveis do .env
load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

# --- MAPEAMENTO INTELIGENTE DE PASTAS ---
DATABASE_DIR = os.path.dirname(os.path.abspath(__file__)) # Pasta: tracebox/database
TRACEBOX_DIR = os.path.dirname(DATABASE_DIR)              # Pasta: tracebox/
ROOT_DIR = os.path.dirname(TRACEBOX_DIR)                  # Pasta: Gestao_Estoque/ (Raiz)

def get_conexao():
    """
    Retorna a conexão correta dependendo do ambiente (SQLite ou Postgres).
    """
    if DB_TYPE == "postgres":
        return psycopg2.connect(
            host=os.getenv("PG_HOST"),
            database=os.getenv("PG_DATABASE"),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            port=os.getenv("PG_PORT")
        )
    else:
        nome_arquivo_db = os.getenv("SQLITE_PATH", "estoque_ferramentas.db")
        
        # O sistema verifica os dois caminhos possíveis
        caminho_tracebox = os.path.join(TRACEBOX_DIR, nome_arquivo_db)
        caminho_raiz = os.path.join(ROOT_DIR, nome_arquivo_db)
        
        # LÓGICA DE DETETIVE: Se o arquivo estiver lá fora (na raiz), ele usa esse!
        if os.path.exists(caminho_raiz):
            db_path = caminho_raiz
        else:
            db_path = caminho_tracebox # Usa a pasta tracebox como padrão
            
        return sqlite3.connect(db_path, check_same_thread=False)
    
