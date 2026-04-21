# Tela de Login
# tracebox/controllers/auth.py
import hashlib
from database.conexao_orm import SessionLocal
from database.models import Usuario
from repositories.usuario_repository import UsuarioRepository

def configurar_banco_seguranca():
    """Verifica se existe algum usuário, se não, cria o Admin Mestre"""
    with SessionLocal() as db:
        repo = UsuarioRepository()
        if len(repo.get_all(db)) == 0:
            senha_padrao_criptografada = hashlib.sha256("admin123".encode()).hexdigest()
            admin = Usuario(nome="Gestor Mestre", usuario="admin", senha=senha_padrao_criptografada, perfil="Admin")
            repo.create(db, admin)
            db.commit()

def autenticar_usuario(usuario_digitado, senha_digitada):
    """Verifica as credenciais e retorna os dados do usuário se baterem"""
    configurar_banco_seguranca()
    
    senha_hash = hashlib.sha256(senha_digitada.encode()).hexdigest()
    
    with SessionLocal() as db:
        repo = UsuarioRepository()
        user = repo.get_by_username(db, usuario_digitado)
        if user and user.senha == senha_hash:
            return {
                'nome': user.nome,
                'perfil': user.perfil
            }
    
    return None