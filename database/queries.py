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
            if DB_TYPE == "postgres" and params:
                query = query.replace("?", "%s")

            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            cols = [desc[0] for desc in cursor.description]
            result = cursor.fetchall()
            df = pd.DataFrame(result, columns=cols)
            return df

    except Exception as e:
        print(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

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
        print(f"Erro ao executar operação no banco: {e}")
        return None
    finally:
        if conn:
            conn.close()