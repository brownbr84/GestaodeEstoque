# Funções puras (ex: carregar_dados, executar_query)
# tracebox/database/queries.py
import pandas as pd
import streamlit as st
from database.conexao import get_conexao, DB_TYPE

# Fazemos cache para relatórios pesados não travarem o sistema
@st.cache_data(ttl=60) # Atualiza a cache a cada 60 segundos
def carregar_dados(query, params=None):
    """Executa SELECT e retorna um DataFrame do Pandas"""
    try:
        with get_conexao() as conn:
            if params:
                # O Pandas lida bem com os parâmetros de segurança
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame() # Retorna vazio em caso de erro para não crashar a tela

def executar_query(query, params=None):
    """Executa INSERT, UPDATE, DELETE com Transação Segura (ACID)"""
    conn = None
    try:
        conn = get_conexao()
        cursor = conn.cursor()
        
        # Ajuste de sintaxe entre SQLite (?) e Postgres (%s)
        if DB_TYPE == "postgres" and params:
            query = query.replace("?", "%s")
            
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        conn.commit() # Confirma a transação
        return cursor.lastrowid # Retorna o ID inserido
        
    except Exception as e:
        if conn:
            conn.rollback() # Se der erro, desfaz a operação! (Evita dados fantasma)
        st.error(f"Erro ao executar operação no banco: {e}")
        return None
    finally:
        if conn:
            conn.close()