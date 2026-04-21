# -*- coding: utf-8 -*-
"""
criar_admin.py
==============
Script de seed seguro para criar (ou redefinir) o usuario Admin no TraceBox WMS.
Execute UMA VEZ apos a instalacao:

    .venv\\Scripts\\python criar_admin.py   (Windows)
    python criar_admin.py                  (Linux/Docker)
"""
import sys
import os

# Forca UTF-8 no stdout para evitar erros de encoding em Windows (CP1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")



# Adiciona a raiz do projeto ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.conexao_orm import Base, engine, SessionLocal
from database.models import Usuario, Configuracoes
from utils.security import hash_senha

# ──────────────────────────────────────────────
# CREDENCIAIS DO ADMIN
# Altere aqui antes de executar, se quiser
# ──────────────────────────────────────────────
ADMIN_NOME    = "Administrador"
ADMIN_USUARIO = "admin"
ADMIN_SENHA   = "Admin@2026"        # Será hasheada — não fica em texto puro no BD
ADMIN_PERFIL  = "Admin"


def _migrar_colunas_incrementais():
    """Adiciona colunas novas a tabelas existentes sem recriar o schema."""
    import sqlalchemy as _sa
    with engine.connect() as conn:
        inspector = _sa.inspect(engine)

        cols_usuarios = [c["name"] for c in inspector.get_columns("usuarios")]
        if "email" not in cols_usuarios:
            conn.execute(_sa.text("ALTER TABLE usuarios ADD COLUMN email TEXT"))
            conn.commit()
            print("      [OK] Coluna 'email' adicionada à tabela usuarios.")

        cols_config = [c["name"] for c in inspector.get_columns("configuracoes")]
        if "smtp_host" not in cols_config:
            conn.execute(_sa.text("ALTER TABLE configuracoes ADD COLUMN smtp_host TEXT"))
            conn.commit()
            print("      [OK] Coluna 'smtp_host' adicionada à tabela configuracoes.")
        if "smtp_porta" not in cols_config:
            conn.execute(_sa.text("ALTER TABLE configuracoes ADD COLUMN smtp_porta INTEGER"))
            conn.commit()
            print("      [OK] Coluna 'smtp_porta' adicionada à tabela configuracoes.")

        cols_os = [c["name"] for c in inspector.get_columns("manutencao_ordens")]
        for col, tipo in [("email_status", "TEXT"), ("email_enviado_em", "DATETIME"), ("email_erro", "TEXT")]:
            if col not in cols_os:
                conn.execute(_sa.text(f"ALTER TABLE manutencao_ordens ADD COLUMN {col} {tipo}"))
                conn.commit()
                print(f"      [OK] Coluna '{col}' adicionada à tabela manutencao_ordens.")

        cols_req = [c["name"] for c in inspector.get_columns("requisicoes")]
        for col, tipo in [("email_status", "TEXT"), ("email_enviado_em", "DATETIME"), ("email_erro", "TEXT")]:
            if col not in cols_req:
                conn.execute(_sa.text(f"ALTER TABLE requisicoes ADD COLUMN {col} {tipo}"))
                conn.commit()
                print(f"      [OK] Coluna '{col}' adicionada à tabela requisicoes.")

        cols_config = [c["name"] for c in inspector.get_columns("configuracoes")]
        for col, ddl in [
            ("fiscal_habilitado",     "ALTER TABLE configuracoes ADD COLUMN fiscal_habilitado INTEGER DEFAULT 0"),
            ("fiscal_ambiente",       "ALTER TABLE configuracoes ADD COLUMN fiscal_ambiente TEXT DEFAULT 'homologacao'"),
            ("fiscal_serie",          "ALTER TABLE configuracoes ADD COLUMN fiscal_serie TEXT DEFAULT '1'"),
            ("fiscal_numeracao_atual","ALTER TABLE configuracoes ADD COLUMN fiscal_numeracao_atual INTEGER DEFAULT 1"),
        ]:
            if col not in cols_config:
                conn.execute(_sa.text(ddl))
                conn.commit()
                print(f"      [OK] Coluna '{col}' adicionada à tabela configuracoes.")


def main():
    print("=" * 55)
    print("  TraceBox WMS — Setup de Usuário Administrador")
    print("=" * 55)

    # 1. Garante que as tabelas existem
    print("\n[1/3] Verificando/criando estrutura do banco de dados...")
    Base.metadata.create_all(bind=engine)
    _migrar_colunas_incrementais()
    print("      [OK] Banco de dados pronto.")

    with SessionLocal() as db:
        # 2. Verifica se o admin já existe
        existente = db.query(Usuario).filter(Usuario.usuario == ADMIN_USUARIO).first()

        senha_hash = hash_senha(ADMIN_SENHA)

        if existente:
            print(f"\n[2/3] Usuario '{ADMIN_USUARIO}' ja existe - redefinindo senha...")
            existente.senha  = senha_hash
            existente.perfil = ADMIN_PERFIL
            existente.nome   = ADMIN_NOME
            db.commit()
            print("      [OK] Senha redefinida com sucesso.")
        else:
            print(f"\n[2/3] Criando usuario '{ADMIN_USUARIO}'...")
            novo_admin = Usuario(
                nome    = ADMIN_NOME,
                usuario = ADMIN_USUARIO,
                senha   = senha_hash,
                perfil  = ADMIN_PERFIL,
            )
            db.add(novo_admin)
            db.commit()
            print("      [OK] Usuario Admin criado com sucesso.")

        # 3. Garante que existe ao menos uma linha de Configuracoes
        config = db.query(Configuracoes).first()
        if not config:
            print("\n[3/3] Criando configuracao inicial do sistema...")
            db.add(Configuracoes(
                nome_empresa="TraceBox WMS",
                cnpj="",
                logo_base64="",
            ))
            db.commit()
            print("      [OK] Configuracoes iniciais criadas.")
        else:
            print("\n[3/3] Configuracoes do sistema ja existem - sem alteracoes.")

    print("\n" + "=" * 55)
    print("  Setup concluido com sucesso!")
    print("=" * 55)
    print(f"\n  Login   : {ADMIN_USUARIO}")
    print(f"  Senha   : {ADMIN_SENHA}")
    print(f"  Perfil  : {ADMIN_PERFIL}")
    print("\n  IMPORTANTE: Altere a senha apos o primeiro login!\n")



if __name__ == "__main__":
    main()
