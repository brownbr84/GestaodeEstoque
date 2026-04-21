# -*- coding: utf-8 -*-
"""
migrar_sqlite_para_postgres.py
================================
Migra todos os dados do banco SQLite local para o PostgreSQL do Docker.

Execute com os containers rodando:
    .venv\\Scripts\\python migrar_sqlite_para_postgres.py

O script:
  1. Le cada tabela do SQLite
  2. Apaga os dados antigos do PostgreSQL (exceto o usuario admin criado pelo seed)
  3. Insere os dados do SQLite no PostgreSQL
  4. Exibe um relatorio de quantos registros foram migrados
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estoque_ferramentas.db")

PG_CONFIG = {
    "host":     os.getenv("PG_HOST",     "localhost"),
    "database": os.getenv("PG_DATABASE", "tracebox_db"),
    "user":     os.getenv("PG_USER",     "postgres"),
    # Usa a senha do .env; se for o placeholder, usa a senha do docker-compose
    "password": (os.getenv("PG_PASSWORD", "tracebox_password")
                 if os.getenv("PG_PASSWORD") not in (None, "", "sua_senha_segura")
                 else "tracebox_password"),
    "port":     os.getenv("PG_PORT",     "5432"),
}

# Tabelas para migrar (ordem respeita FKs)
TABELAS = [
    "configuracoes",
    "imobilizado",
    "movimentacoes",
    "requisicoes",
    "requisicoes_itens",
    "manutencao_ordens",
    "governance_logs",
    "notas_fiscais_rascunho",
]

def migrar():
    print("=" * 60)
    print("  TraceBox WMS - Migrador SQLite -> PostgreSQL")
    print("=" * 60)

    if not os.path.exists(SQLITE_PATH):
        print(f"\n[ERRO] SQLite nao encontrado em: {SQLITE_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        pg_conn = psycopg2.connect(**PG_CONFIG)
        print("\n[OK] Conectado ao PostgreSQL.")
    except Exception as e:
        print(f"\n[ERRO] Nao foi possivel conectar ao PostgreSQL: {e}")
        print("  Verifique se o container 'tracebox_db' esta rodando.")
        sys.exit(1)

    pg_cur = pg_conn.cursor()
    total_migrado = 0

    for tabela in TABELAS:
        # Verifica se a tabela existe no SQLite
        sqlite_cur = sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
        )
        if not sqlite_cur.fetchone():
            print(f"\n[SKIP] Tabela '{tabela}' nao existe no SQLite - pulando.")
            continue

        # Le os dados do SQLite
        rows = sqlite_conn.execute(f"SELECT * FROM {tabela}").fetchall()
        if not rows:
            print(f"\n[SKIP] Tabela '{tabela}' esta vazia no SQLite.")
            continue

        colunas = [desc[0] for desc in sqlite_conn.execute(f"SELECT * FROM {tabela} LIMIT 0").description]

        # Protege o usuario admin criado pelo seed
        print(f"\n[...] Migrando '{tabela}' ({len(rows)} registros)...")

        try:
            if tabela == "usuarios":
                # Nao apaga o admin, insere apenas novos
                for row in rows:
                    pg_cur.execute(
                        f"INSERT INTO {tabela} ({', '.join(colunas)}) "
                        f"VALUES ({', '.join(['%s'] * len(colunas))}) "
                        f"ON CONFLICT (usuario) DO NOTHING",
                        list(row)
                    )
            else:
                # Limpa e reinseere
                pg_cur.execute(f"DELETE FROM {tabela}")
                for row in rows:
                    pg_cur.execute(
                        f"INSERT INTO {tabela} ({', '.join(colunas)}) "
                        f"VALUES ({', '.join(['%s'] * len(colunas))})",
                        list(row)
                    )

            # Reseta a sequence do ID para evitar conflitos
            pg_cur.execute(f"""
                SELECT setval(pg_get_serial_sequence('{tabela}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {tabela}), 1))
            """)

            pg_conn.commit()
            total_migrado += len(rows)
            print(f"  [OK] {len(rows)} registros inseridos.")
        except Exception as e:
            pg_conn.rollback()
            print(f"  [AVISO] Erro ao migrar '{tabela}': {e}")

    sqlite_conn.close()
    pg_conn.close()

    print("\n" + "=" * 60)
    print(f"  Migracao concluida! Total: {total_migrado} registros.")
    print("=" * 60)
    print("\n  Recarregue o sistema no browser para ver os dados.\n")

if __name__ == "__main__":
    migrar()
