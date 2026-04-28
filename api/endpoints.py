from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.conexao_orm import get_session
from database.models import NotaFiscalRascunho
from repositories.imobilizado_repository import ImobilizadoRepository
from repositories.usuario_repository import UsuarioRepository
from repositories.configuracoes_repository import ConfiguracoesRepository
from utils.security import verificar_senha, hash_senha, precisa_rehash, criptografar, descriptografar
import jwt
import datetime
import os
import re
import xml.etree.ElementTree as ET
# TODO (SEGURANÇA P1): mover SECRET_KEY para variável de ambiente.
# Exemplo: SECRET_KEY = os.getenv("JWT_SECRET_KEY")
# Nunca commite chaves secretas no código-fonte.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "TraceBox_S3cr3t_K3y_For_JWT_T0kens")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

app = FastAPI(title="TraceBox API", version="1.0.0", description="API RESTful para gestão de estoque e movimentações.")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ── CORS — permite requisições do frontend Next.js ──────────────────────────
from fastapi.middleware.cors import CORSMiddleware
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _seed_e_migrar_fiscal():
    """Garante migrações incrementais e seed de regras fiscais ao subir a API (Docker-safe)."""
    from database.conexao_orm import engine, Base
    import sqlalchemy as _sa
    import logging
    _log = logging.getLogger(__name__)

    try:
        import database.models as _models  # noqa: F401 — registra todos os modelos no Base
        Base.metadata.create_all(bind=engine)
    except Exception as _e:
        _log.error(f"create_all falhou (ignorando): {_e}")

    try:
        with engine.connect() as conn:
            inspector = _sa.inspect(engine)

            # ── Migração: regras_operacao_fiscal ─────────────────────────────
            cols_regras = [c["name"] for c in inspector.get_columns("regras_operacao_fiscal")]
            for col, tipo in [("cst_ipi", "TEXT"), ("cst_pis", "TEXT"), ("cst_cofins", "TEXT")]:
                if col not in cols_regras:
                    conn.execute(_sa.text(f"ALTER TABLE regras_operacao_fiscal ADD COLUMN {col} {tipo}"))
                    conn.commit()

            # ── Migração: documentos_fiscais ─────────────────────────────────
            cols_df = [c["name"] for c in inspector.get_columns("documentos_fiscais")]
            for col, tipo in [
                ("num_os",            "TEXT"),
                ("asset_tag",         "TEXT"),
                ("num_serie",         "TEXT"),
                ("info_complementar", "TEXT"),
                ("mod_frete",         "TEXT DEFAULT '9'"),
                ("ind_final",         "INTEGER DEFAULT 0"),
                ("ind_pres",          "INTEGER DEFAULT 0"),
                ("status_historico",  "TEXT"),
            ]:
                if col not in cols_df:
                    conn.execute(_sa.text(f"ALTER TABLE documentos_fiscais ADD COLUMN {col} {tipo}"))
                    conn.commit()

            # ── Migração: imobilizado (campos fiscais NF-e + endereçamento) ────
            cols_imob = [c["name"] for c in inspector.get_columns("imobilizado")]
            for col, tipo in [
                ("ncm",            "TEXT"),
                ("c_ean",          "TEXT DEFAULT 'SEM GTIN'"),
                ("orig_icms",      "TEXT DEFAULT '0'"),
                ("cest",           "TEXT DEFAULT ''"),
                ("localizacao_id", "INTEGER"),
            ]:
                if col not in cols_imob:
                    conn.execute(_sa.text(f"ALTER TABLE imobilizado ADD COLUMN {col} {tipo}"))
                    conn.commit()

            # ── Migração: documentos_fiscais_itens ───────────────────────────
            cols_dfi = [c["name"] for c in inspector.get_columns("documentos_fiscais_itens")]
            for col, tipo in [
                ("c_ean",      "TEXT DEFAULT 'SEM GTIN'"),
                ("c_ean_trib", "TEXT DEFAULT 'SEM GTIN'"),
                ("ind_tot",    "INTEGER DEFAULT 1"),
                ("x_ped",      "TEXT"),
                ("n_item_ped", "TEXT"),
                ("orig_icms",  "TEXT DEFAULT '0'"),
                ("cest",       "TEXT"),
                ("ipi_cst",    "TEXT"),
                ("pis_cst",    "TEXT"),
                ("cofins_cst", "TEXT"),
            ]:
                if col not in cols_dfi:
                    conn.execute(_sa.text(f"ALTER TABLE documentos_fiscais_itens ADD COLUMN {col} {tipo}"))
                    conn.commit()

            # ── Seed: regras fiscais com CST codes ───────────────────────────
            _REGRAS = [
                ("Remessa para Conserto — Interna/Interestadual", "REMESSA_CONSERTO", "5915", "6915", "Remessa para conserto", "41", "53", "07", "07"),
                ("Retorno de Conserto — Interna/Interestadual",  "RETORNO_CONSERTO", "5916", "6916", "Retorno de conserto",   "41", "53", "07", "07"),
                ("Saída Geral — Interna/Interestadual",          "SAIDA_GERAL",      "5102", "6102", "Saída de mercadorias",  "00", "50", "01", "01"),
                ("Entrada Geral — Interna/Interestadual",        "ENTRADA_GERAL",    "1102", "2102", "Entrada de mercadorias","00", "50", "01", "01"),
            ]
            for nome, tipo_op, cfop_int, cfop_inter, nat_op, cst_icms, cst_ipi, cst_pis, cst_cofins in _REGRAS:
                existe = conn.execute(
                    _sa.text("SELECT id FROM regras_operacao_fiscal WHERE tipo_operacao = :t"),
                    {"t": tipo_op}
                ).fetchone()
                if not existe:
                    conn.execute(
                        _sa.text(
                            "INSERT INTO regras_operacao_fiscal "
                            "(nome, tipo_operacao, cfop_interno, cfop_interestadual, natureza_operacao, "
                            "cst_icms, cst_ipi, cst_pis, cst_cofins, ativo) "
                            "VALUES (:nome, :tipo, :cfop_int, :cfop_inter, :nat_op, "
                            ":cst_icms, :cst_ipi, :cst_pis, :cst_cofins, 1)"
                        ),
                        {"nome": nome, "tipo": tipo_op, "cfop_int": cfop_int,
                         "cfop_inter": cfop_inter, "nat_op": nat_op,
                         "cst_icms": cst_icms, "cst_ipi": cst_ipi,
                         "cst_pis": cst_pis, "cst_cofins": cst_cofins},
                    )
                else:
                    # Atualiza CST codes se a linha já existia sem eles
                    conn.execute(
                        _sa.text(
                            "UPDATE regras_operacao_fiscal SET "
                            "cst_icms=:cst_icms, cst_ipi=:cst_ipi, cst_pis=:cst_pis, cst_cofins=:cst_cofins "
                            "WHERE tipo_operacao=:tipo AND (cst_ipi IS NULL OR cst_ipi='')"
                        ),
                        {"tipo": tipo_op, "cst_icms": cst_icms, "cst_ipi": cst_ipi,
                         "cst_pis": cst_pis, "cst_cofins": cst_cofins},
                    )
            conn.commit()

            # ── Seed: fiscal_cfop_config ─────────────────────────────────────
            # Cria a tabela se não existir usando o próprio ORM (SQLite e PostgreSQL)
            from database.models import FiscalCfopConfig as _FiscalCfopConfig
            _FiscalCfopConfig.__table__.create(engine, checkfirst=True)

            _CFOP_SEEDS = [
                ("Remessa Conserto",  "CONSERTO",      "SAIDA",   "5915", "6915", "Remessa para conserto"),
                ("Saída Geral",       "GERAL",          "SAIDA",   "5101", "6101", "Venda de mercadoria"),
                ("Devolução",         "DEVOLUCAO",      "SAIDA",   "5921", "6921", "Devolução de mercadoria"),
                ("Transferência",     "TRANSFERENCIA",  "SAIDA",   "5150", "6150", "Transferência"),
                ("Retorno Conserto",  "CONSERTO",      "ENTRADA",  "5916", "6916", "Retorno de conserto"),
                ("Entrada Geral",     "GERAL",          "ENTRADA", "1101", "2101", "Compra de mercadoria"),
                ("Devolução",         "DEVOLUCAO",      "ENTRADA", "5922", "6922", "Devolução recebida"),
                ("Transferência",     "TRANSFERENCIA",  "ENTRADA", "1150", "2150", "Transferência"),
            ]
            for tipo_op, grupo, direcao, cfop_int, cfop_inter, nat in _CFOP_SEEDS:
                existe_cfop = conn.execute(
                    _sa.text("SELECT id FROM fiscal_cfop_config WHERE tipo_operacao=:t AND direcao=:d"),
                    {"t": tipo_op, "d": direcao}
                ).fetchone()
                if not existe_cfop:
                    conn.execute(
                        _sa.text(
                            "INSERT INTO fiscal_cfop_config "
                            "(tipo_operacao, grupo_operacao, direcao, cfop_interno, cfop_interestadual, "
                            "natureza_padrao, ativo) "
                            "VALUES (:t, :g, :d, :ci, :ce, :n, 1)"
                        ),
                        {"t": tipo_op, "g": grupo, "d": direcao,
                         "ci": cfop_int, "ce": cfop_inter, "n": nat},
                    )
            conn.commit()
    except Exception as exc:
        _log.warning("Migração/seed fiscal falhou: %s", exc)

# P3 — Rate Limiting (slowapi)
# Limita cada IP a 60 requisições/minuto por padrão.
# Para endpoints fiscais e de login, aplique @limiter.limit("10/minute") individualmente.
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from fastapi import Request

    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    # Degradação segura: se slowapi não estiver instalado ainda, a API roda sem rate limit
    limiter = None


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Não autorizado")

imob_repo = ImobilizadoRepository()

# Modelos Pydantic (Entrada/Saída)
class LoginRequest(BaseModel):
    usuario: str
    senha: str

class ConfigUpdateRequest(BaseModel):
    nome_empresa: str
    cnpj: str
    logo_base64: str

class NovoProdutoRequest(BaseModel):
    codigo: str
    descricao: str
    marca: str
    modelo: str
    categoria: str
    dimensoes: str
    capacidade: str
    valor_unitario: float
    tipo_material: str
    tipo_controle: str
    imagem_b64: str
    usuario_atual: str

# ==========================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================
@app.post("/api/v1/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_session)):
    repo = UsuarioRepository()
    user = repo.get_by_username(db, req.usuario)

    # P1-FIX: usa bcrypt com fallback SHA-256 legável e migração automática
    if not user or not verificar_senha(req.senha, user.senha):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    # Migração transparente: se ainda é SHA-256, rehasheia para bcrypt
    if precisa_rehash(user.senha):
        user.senha = hash_senha(req.senha)
        db.commit()

    token = create_access_token(data={"sub": user.usuario, "perfil": user.perfil})
    return {
        "access_token": token,
        "token_type": "bearer",
        "nome": user.nome,
        "perfil": user.perfil
    }

@app.get("/api/v1/auth/me")
def auth_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Valida o token e devolve os dados do usuário — usado para restaurar sessão após F5."""
    from repositories.usuario_repository import UsuarioRepository
    repo = UsuarioRepository()
    user = repo.get_by_username(db, current_user.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return {"nome": user.nome, "perfil": user.perfil, "usuario": user.usuario}

# ==========================================
# ROTAS DE CONFIGURAÇÕES
# ==========================================
@app.get("/api/v1/configuracoes")
def configuracoes_get(current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    repo = ConfiguracoesRepository()
    config = repo.get_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")
    return {
        "nome_empresa": config.nome_empresa,
        "cnpj": config.cnpj,
        "logo_base64": config.logo_base64,
        "categorias_produto": config.categorias_produto or [],
        "tipos_material": config.tipos_material or [],
        "tipos_controle": config.tipos_controle or [],
        "email_smtp": config.email_smtp or "",
        "smtp_host": config.smtp_host or "",
        "smtp_porta": config.smtp_porta or 587,
        # senha SMTP nunca é retornada ao front-end
        "emails_destinatarios": config.emails_destinatarios or [],
        # Módulo Fiscal
        "fiscal_habilitado": bool(config.fiscal_habilitado),
        "fiscal_ambiente": config.fiscal_ambiente or "homologacao",
        "fiscal_serie": config.fiscal_serie or "1",
        "fiscal_numeracao_atual": config.fiscal_numeracao_atual or 1,
    }

@app.put("/api/v1/configuracoes")
def configuracoes_put(req: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    # P2-FIX: renomeado de 'configuracoes' para 'configuracoes_put' (nome duplicado)
    repo = ConfiguracoesRepository()
    config = repo.get_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")
        
    config.nome_empresa = req.get("nome_empresa")
    config.cnpj = req.get("cnpj")
    config.logo_base64 = req.get("logo_base64")
    
    if "categorias_produto" in req: config.categorias_produto = req.get("categorias_produto")
    if "tipos_material" in req: config.tipos_material = req.get("tipos_material")
    if "tipos_controle" in req: config.tipos_controle = req.get("tipos_controle")
    if "email_smtp" in req: config.email_smtp = req.get("email_smtp")
    if "emails_destinatarios" in req: config.emails_destinatarios = req.get("emails_destinatarios")
    if "smtp_host" in req: config.smtp_host = req.get("smtp_host")
    if "smtp_porta" in req and req.get("smtp_porta"): config.smtp_porta = int(req.get("smtp_porta"))
    if "senha_smtp" in req and req.get("senha_smtp"):
        config.senha_smtp = criptografar(req.get("senha_smtp"))
    # Módulo Fiscal
    if "fiscal_habilitado" in req: config.fiscal_habilitado = 1 if req.get("fiscal_habilitado") else 0
    if "fiscal_ambiente" in req: config.fiscal_ambiente = req.get("fiscal_ambiente")
    if "fiscal_serie" in req: config.fiscal_serie = req.get("fiscal_serie")
    if "fiscal_numeracao_atual" in req and req.get("fiscal_numeracao_atual") is not None:
        config.fiscal_numeracao_atual = int(req.get("fiscal_numeracao_atual"))

    db.commit()
    return {"status": "sucesso"}

@app.get("/api/v1/dashboard/metricas")
def dashboard_metricas(current_user: dict = Depends(get_current_user)):
    # P3-FIX: lógica extraida para DashboardService (testável e reutilizável)
    from services.dashboard_service import DashboardService
    resultado = DashboardService.obter_metricas_completas()
    if resultado.get("status") == "erro":
        raise HTTPException(status_code=500, detail=resultado.get("detalhe"))
    return resultado

# ==========================================
# ROTAS DE GESTÃO DE USUÁRIOS
# ==========================================

class CriarUsuarioRequest(BaseModel):
    nome: str
    usuario: str
    senha: str
    perfil: str  # "Admin" | "Gestor" | "Operador"
    email: str = ""

class AlterarSenhaRequest(BaseModel):
    usuario_alvo: str
    nova_senha: str

class AtualizarEmailRequest(BaseModel):
    usuario_alvo: str
    email: str

class RecuperarSenhaRequest(BaseModel):
    usuario: str
    email: str

class ConfirmarRecuperacaoRequest(BaseModel):
    usuario: str
    codigo: str
    nova_senha: str

class EntradaExcepcionalRequest(BaseModel):
    carrinho: list
    motivo: str
    documento: str
    usuario: str
    polo: str
    perfil_usuario: str

@app.get("/api/v1/usuarios")
def listar_usuarios(current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Lista todos os usuários (somente Admin e Gestor podem ver)."""
    if current_user.get("perfil") not in ["Admin", "Gestor"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    from database.models import Usuario
    usuarios = db.query(Usuario).all()
    return [
        {"id": u.id, "nome": u.nome, "usuario": u.usuario, "perfil": u.perfil, "email": u.email or ""}
        for u in usuarios
    ]

@app.post("/api/v1/usuarios")
def criar_usuario(req: CriarUsuarioRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Cria novo usuário. Somente Admin."""
    if current_user.get("perfil") != "Admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem criar usuarios")
    if req.perfil not in ["Admin", "Gestor", "Operador"]:
        raise HTTPException(status_code=400, detail="Perfil invalido. Use: Admin, Gestor ou Operador")
    repo = UsuarioRepository()
    if repo.get_by_username(db, req.usuario):
        raise HTTPException(status_code=409, detail=f"Usuario '{req.usuario}' ja existe")
    from database.models import Usuario
    novo = Usuario(
        nome=req.nome,
        usuario=req.usuario,
        senha=hash_senha(req.senha),
        perfil=req.perfil,
        email=req.email or None,
    )
    db.add(novo)
    db.commit()
    return {"status": "sucesso", "mensagem": f"Usuario '{req.usuario}' criado com perfil {req.perfil}"}

@app.put("/api/v1/usuarios/email")
def atualizar_email_usuario(req: AtualizarEmailRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Atualiza e-mail de recuperação do usuário."""
    eh_admin = current_user.get("perfil") == "Admin"
    eh_proprio = current_user.get("sub") == req.usuario_alvo
    if not eh_admin and not eh_proprio:
        raise HTTPException(status_code=403, detail="Acesso negado")
    repo = UsuarioRepository()
    user = repo.get_by_username(db, req.usuario_alvo)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    user.email = req.email
    db.commit()
    return {"status": "sucesso", "mensagem": "E-mail atualizado com sucesso"}

@app.put("/api/v1/usuarios/senha")
def alterar_senha_usuario(req: AlterarSenhaRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Altera senha de um usuário. Admin pode alterar qualquer um; usuário comum só a própria."""
    eh_admin = current_user.get("perfil") == "Admin"
    eh_proprio = current_user.get("sub") == req.usuario_alvo
    if not eh_admin and not eh_proprio:
        raise HTTPException(status_code=403, detail="Acesso negado")
    repo = UsuarioRepository()
    user = repo.get_by_username(db, req.usuario_alvo)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    user.senha = hash_senha(req.nova_senha)
    db.commit()
    return {"status": "sucesso", "mensagem": "Senha alterada com sucesso"}

@app.delete("/api/v1/usuarios/{usuario_alvo}")
def excluir_usuario(usuario_alvo: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Remove um usuário. Somente Admin. Não pode excluir a si mesmo."""
    if current_user.get("perfil") != "Admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem excluir usuarios")
    if current_user.get("sub") == usuario_alvo:
        raise HTTPException(status_code=400, detail="Voce nao pode excluir sua propria conta")
    repo = UsuarioRepository()
    user = repo.get_by_username(db, usuario_alvo)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    db.delete(user)
    db.commit()
    return {"status": "sucesso", "mensagem": f"Usuario '{usuario_alvo}' removido"}

# ==========================================
# RECUPERAÇÃO DE SENHA VIA EMAIL
# ==========================================
import secrets as _secrets
import smtplib as _smtplib
from email.mime.text import MIMEText as _MIMEText

_recovery_codes: dict = {}  # {usuario: {"code": str, "expires": datetime}}

@app.post("/api/v1/auth/recuperar-senha")
def solicitar_recuperacao(req: RecuperarSenhaRequest, db: Session = Depends(get_session)):
    """Gera código OTP e envia para o e-mail cadastrado do usuário."""
    import datetime as _dt
    repo = UsuarioRepository()
    user = repo.get_by_username(db, req.usuario)
    if not user or (user.email or "").lower() != req.email.lower():
        raise HTTPException(status_code=404, detail="Usuário ou e-mail não encontrado")

    code = str(_secrets.randbelow(900000) + 100000)  # 6 dígitos
    _recovery_codes[req.usuario] = {
        "code": code,
        "expires": _dt.datetime.utcnow() + _dt.timedelta(minutes=15)
    }

    config_repo = ConfiguracoesRepository()
    config = config_repo.get_config(db)

    if not config or not config.email_smtp or not config.senha_smtp:
        raise HTTPException(
            status_code=503,
            detail="Servidor de e-mail não configurado. Contate o administrador do sistema para configurar em Configurações → Automação de E-mails."
        )

    smtp_host = (config.smtp_host or "").strip() or "smtp.gmail.com"
    smtp_porta = config.smtp_porta or 587

    try:
        senha_plain = descriptografar(config.senha_smtp)
        msg = _MIMEText(
            f"Olá {user.nome},\n\n"
            f"Seu código de recuperação de senha TraceBox WMS é:\n\n"
            f"  {code}\n\n"
            f"Este código expira em 15 minutos.\n\n"
            f"Se você não solicitou a recuperação, ignore este e-mail.",
            "plain",
            "utf-8"
        )
        msg["Subject"] = "TraceBox WMS — Recuperação de Senha"
        msg["From"] = config.email_smtp
        msg["To"] = user.email

        if smtp_porta == 465:
            with _smtplib.SMTP_SSL(smtp_host, smtp_porta) as server:
                server.login(config.email_smtp, senha_plain)
                server.send_message(msg)
        else:
            with _smtplib.SMTP(smtp_host, smtp_porta) as server:
                server.ehlo()
                server.starttls()
                server.login(config.email_smtp, senha_plain)
                server.send_message(msg)
    except Exception as exc:
        _recovery_codes.pop(req.usuario, None)
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao enviar e-mail: {exc}. Verifique as configurações SMTP em Configurações → Automação de E-mails."
        )

    return {"status": "sucesso", "mensagem": f"Código enviado para {user.email}"}

@app.post("/api/v1/auth/confirmar-recuperacao")
def confirmar_recuperacao(req: ConfirmarRecuperacaoRequest, db: Session = Depends(get_session)):
    """Valida o código OTP e redefine a senha."""
    import datetime as _dt
    entrada = _recovery_codes.get(req.usuario)
    if not entrada:
        raise HTTPException(status_code=400, detail="Nenhum código de recuperação ativo para este usuário")
    if _dt.datetime.utcnow() > entrada["expires"]:
        _recovery_codes.pop(req.usuario, None)
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")
    if entrada["code"] != req.codigo:
        raise HTTPException(status_code=400, detail="Código inválido")
    if len(req.nova_senha) < 6:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 6 caracteres")

    repo = UsuarioRepository()
    user = repo.get_by_username(db, req.usuario)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    user.senha = hash_senha(req.nova_senha)
    db.commit()
    _recovery_codes.pop(req.usuario, None)
    return {"status": "sucesso", "mensagem": "Senha redefinida com sucesso"}

# ==========================================
# ENTRADA EXCEPCIONAL INBOUND
# ==========================================
@app.post("/api/v1/inbound/entrada-excepcional")
def entrada_excepcional(req: EntradaExcepcionalRequest, _: dict = Depends(get_current_user)):
    """Entrada excepcional de produto sem NF. Restrita a Admin/Gestor."""
    from controllers.inbound import realizar_entrada_excepcional
    ok, msg, tags = realizar_entrada_excepcional(
        req.carrinho, req.motivo, req.documento,
        req.usuario, req.polo, req.perfil_usuario
    )
    if ok:
        return {"status": "sucesso", "mensagem": msg, "tags": tags}
    raise HTTPException(status_code=400, detail=msg)

class ProdutoMasterUpdateRequest(BaseModel):
    descricao: str
    marca: str
    modelo: str
    categoria: str
    dimensoes: str
    capacidade: str
    valor_unitario: float
    ultima_manutencao: str
    proxima_manutencao: str
    detalhes: str
    imagem: str

class CalibracaoItemRequest(BaseModel):
    ID_DB: int
    ultima_inspecao: str
    deadline_calibracao: str

class CalibracaoUpdateRequest(BaseModel):
    itens: list[CalibracaoItemRequest]
    usuario: str

# ==========================================
# ROTAS DE ESTOQUE
# ==========================================
@app.post("/api/v1/produtos")
def produtos(req: dict, current_user: dict = Depends(get_current_user)):
    from controllers.cadastro import cadastrar_novo_produto
    sucesso, msg = cadastrar_novo_produto(
        req.get("codigo"), req.get("descricao"), req.get("marca"), req.get("modelo"),
        req.get("categoria"), req.get("dimensoes"), req.get("capacidade"), req.get("valor_unitario"),
        req.get("tipo_material"), req.get("tipo_controle"), req.get("imagem_b64"), req.get("usuario_atual"),
        req.get("ncm", ""), req.get("c_ean", ""), req.get("orig_icms", "0"), req.get("cest", ""),
    )
    if not sucesso:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}

@app.get("/api/v1/produtos/{codigo}/detalhes")
def produtos_codigo_detalhes(codigo: str, current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    
    # 1. Dados Mestre
    df_mestre = carregar_dados("SELECT descricao, marca, modelo, categoria, valor_unitario, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material, tipo_controle FROM imobilizado WHERE codigo = ? AND status = 'Catálogo' LIMIT 1", (codigo,))
    if df_mestre.empty:
        df_mestre = carregar_dados("SELECT descricao, marca, modelo, categoria, valor_unitario, dimensoes, capacidade, ultima_manutencao, proxima_manutencao, detalhes, imagem, tipo_material, tipo_controle FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo,))
        if df_mestre.empty:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
            
    dados_mestre = df_mestre.iloc[0].to_dict()
    
    import math, pandas as _pd

    def _clean(df):
        """Substitui NaN/NaT por None — converte para object primeiro para preservar None em colunas numéricas."""
        mask = _pd.notnull(df)
        return df.astype(object).where(mask, other=None)

    def _scalar(v):
        """Converte np.int64/np.float64/NaN para tipos Python nativos."""
        if v is None:
            return None
        try:
            if math.isnan(float(v)):
                return None
            n = float(v)
            return int(n) if n == int(n) else n
        except (TypeError, ValueError):
            return v

    # 2. Inventário Físico — query base sem localizacao_id (segura mesmo sem a coluna)
    df_inv = carregar_dados(
        "SELECT id, num_tag, localizacao, status, quantidade "
        "FROM imobilizado WHERE codigo = ? AND status != 'Catálogo' AND quantidade > 0",
        (codigo,),
    )
    inv_fisico = _clean(df_inv).to_dict(orient='records') if not df_inv.empty else []

    # 2a. Enriquece com localizacao_id + nome do bin (colunas podem não existir ainda)
    if inv_fisico:
        item_ids = [int(r["id"]) for r in inv_fisico]
        ph_ids = ",".join("?" for _ in item_ids)

        # Tenta buscar localizacao_id (coluna adicionada por migração; pode não existir)
        df_loc_ids = carregar_dados(
            f"SELECT id, localizacao_id FROM imobilizado WHERE id IN ({ph_ids})",
            tuple(item_ids),
        )
        loc_id_by_item: dict = {}
        if not df_loc_ids.empty and "localizacao_id" in df_loc_ids.columns:
            for _, row in _clean(df_loc_ids).iterrows():
                # None seguro: NULL vira None após _clean; nunca NaN
                raw = row["localizacao_id"]
                loc_id_by_item[int(row["id"])] = int(raw) if raw is not None else None
        for r in inv_fisico:
            r["localizacao_id"] = loc_id_by_item.get(int(r["id"]))

        # Apenas IDs inteiros válidos (exclui None explicitamente)
        ids_loc = [lid for lid in {r["localizacao_id"] for r in inv_fisico} if lid is not None]
        loc_map: dict = {}
        if ids_loc:
            ph_locs = ",".join("?" for _ in ids_loc)
            df_locs = carregar_dados(
                f"SELECT id, codigo, descricao FROM localizacoes WHERE id IN ({ph_locs})",
                tuple(ids_loc),
            )
            if not df_locs.empty:
                for _, row in _clean(df_locs).iterrows():
                    loc_map[int(row["id"])] = {
                        "codigo": row["codigo"],
                        "descricao": row["descricao"] or "",
                    }
        for r in inv_fisico:
            loc = loc_map.get(r["localizacao_id"])
            r["endereco_codigo"] = loc["codigo"] if loc else None
            r["endereco_descricao"] = loc["descricao"] if loc else None

    # 3. TAGs para Calibração
    df_tags = carregar_dados('SELECT id as "ID_DB", num_tag as "TAG", localizacao as "Localização", status as "Status", ultima_manutencao as "Última Inspeção", proxima_manutencao as "Deadline Calibração" FROM imobilizado WHERE codigo = ? AND tipo_controle = \'TAG\' AND num_tag != \'\' AND status != \'Catálogo\'', (codigo,))
    tags = _clean(df_tags).to_dict(orient='records') if not df_tags.empty else []

    # 4. Histórico
    ids_produto = tuple(int(i) for i in df_inv['id'].tolist()) if not df_inv.empty else ()
    historico = []
    if ids_produto:
        placeholders = ','.join('?' for _ in ids_produto)
        query_hist = f'SELECT m.data_movimentacao as "Data", i.num_tag as "Serial", m.tipo as "Operação", m.documento as "Doc/NF", m.responsavel as "Agente", m.destino_projeto as "Destino" FROM movimentacoes m JOIN imobilizado i ON m.ferramenta_id = i.id WHERE m.ferramenta_id IN ({placeholders}) ORDER BY m.data_movimentacao DESC LIMIT 200'
        df_hist = carregar_dados(query_hist, ids_produto)
        if not df_hist.empty:
            historico = _clean(df_hist).to_dict(orient='records')

    # Sanitiza mestre — valor_unitario e outros campos numéricos nullable
    dados_mestre = {k: _scalar(v) if isinstance(v, (int, float)) or type(v).__module__ == 'numpy'
                    else (None if (hasattr(v, '__class__') and 'NaT' in type(v).__name__) else v)
                    for k, v in dados_mestre.items()}

    return {
        "mestre": dados_mestre,
        "inventario": inv_fisico,
        "tags": tags,
        "historico": historico
    }

@app.put("/api/v1/produtos/{codigo}/mestre")
def produtos_codigo_mestre(codigo: str, req: dict, current_user: dict = Depends(get_current_user)):
    from controllers.produto import atualizar_ficha_tecnica
    dados_up = req
    sucesso = atualizar_ficha_tecnica(codigo, dados_up)
    if not sucesso:
        raise HTTPException(status_code=400, detail="Erro ao atualizar ficha técnica")
    return {"status": "sucesso"}

@app.put("/api/v1/produtos/{codigo}/calibracao")
def produtos_codigo_calibracao(codigo: str, req: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    import pandas as pd
    from controllers.produto import atualizar_calibracao_tags
    df_editado = pd.DataFrame([{"ID_DB": i.get("ID_DB"), "Última Inspeção": i.get("ultima_inspecao") or i.get("Última Inspeção"), "Deadline Calibração": i.get("deadline_calibracao") or i.get("Deadline Calibração")} for i in req.get("itens", [])])
    sucesso, msg = atualizar_calibracao_tags(df_editado, req.get("usuario"))
    if not sucesso:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}

class CancelarPedidoRequest(BaseModel):
    true_id: int
    req_id: int
    motivo: str
    usuario: str

class DespachoTagRequest(BaseModel):
    tag: str
    metodo: str

class DespachoPedidoRequest(BaseModel):
    true_id: int
    req_id: int
    polo: str
    destino: str
    dict_tags_final: dict
    dict_lotes_final: dict
    df_itens_json: list
    usuario: str

class EntradaCompraRequest(BaseModel):
    codigo_produto: str
    polo_destino: str
    nf: str
    valor_unit: float
    quantidade: int
    usuario: str

class RecebimentoDocaRequest(BaseModel):
    origem: str
    polo_atual: str
    dict_ativos: dict
    dict_lotes: dict
    df_esperados_json: list
    usuario: str

class ReintegracaoRequest(BaseModel):
    id_db: int
    qtd_enc: int
    qtd_pendente: int
    destino: str
    usuario: str

class BaixaExtravioRequest(BaseModel):
    id_db: int
    qtd_perda: int
    qtd_pendente: int
    origem: str
    motivo: str
    usuario: str

class ReativarTagRequest(BaseModel):
    tag: str
    polo: str
    motivo: str
    usuario: str

# ==========================================
# ROTAS DE INBOUND / RECEBIMENTO
# ==========================================
@app.post("/api/v1/inbound/compras")
def inbound_compras(req: EntradaCompraRequest, current_user: dict = Depends(get_current_user)):
    from controllers.inbound import processar_entrada_compra
    sucesso, msg, tags_novas = processar_entrada_compra(
        req.codigo_produto, req.polo_destino, req.nf, req.valor_unit, req.quantidade, req.usuario
    )
    return {"status": sucesso, "mensagem": msg, "tags_novas": tags_novas}

@app.get("/api/v1/inbound/doca/origens")
def inbound_doca_origens(polo: str, current_user: dict = Depends(get_current_user)):
    from controllers.inbound import obter_origens_esperadas
    return {"origens": obter_origens_esperadas(polo)}

@app.get("/api/v1/inbound/doca/esperados")
def inbound_doca_esperados(
    origem: str,          # P2-FIX: parâmetros que faltavam no endpoint
    polo: str,
    current_user: dict = Depends(get_current_user)
):
    from controllers.inbound import carregar_itens_esperados
    df = carregar_itens_esperados(origem, polo)
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/inbound/doca/receber")
def inbound_doca_receber(req: RecebimentoDocaRequest, current_user: dict = Depends(get_current_user)):
    import pandas as pd
    from controllers.inbound import processar_recebimento_doca
    df_esperados = pd.DataFrame(req.df_esperados_json)
    sucesso, msg, alerta = processar_recebimento_doca(
        req.origem, req.polo_atual, req.dict_ativos, req.dict_lotes, df_esperados, req.usuario
    )
    return {"status": sucesso, "mensagem": msg, "alerta": alerta}

@app.post("/api/v1/inbound/malha-fina/reintegrar")
def inbound_malha_fina_reintegrar(req: ReintegracaoRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    from controllers.inbound import processar_reintegracao_falta
    processar_reintegracao_falta(req.id_db, req.qtd_enc, req.qtd_pendente, req.destino, req.usuario)
    return {"status": True}

@app.post("/api/v1/inbound/malha-fina/extravio")
def inbound_malha_fina_extravio(req: BaixaExtravioRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    from controllers.inbound import processar_baixa_extravio
    processar_baixa_extravio(req.id_db, req.qtd_perda, req.qtd_pendente, req.origem, req.motivo, req.usuario)
    return {"status": True}

# ==========================================
# REENVIO DE E-MAILS
# ==========================================

@app.post("/api/v1/manutencao/{os_id}/reenviar-email")
def manutencao_reenviar_email(os_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Reenvia o e-mail de abertura de uma OS. Somente Admin ou Gestor."""
    if current_user.get("perfil") not in ["Admin", "Gestor"]:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from database.models import ManutencaoOrdem, Imobilizado
    from services.email_service import EmailService
    from datetime import datetime as _dt

    os_obj = db.query(ManutencaoOrdem).filter(ManutencaoOrdem.id == os_id).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail=f"OS-{os_id} não encontrada.")

    item = db.query(Imobilizado).filter(Imobilizado.id == os_obj.ferramenta_id).first()
    descricao = item.descricao if item else ""

    assunto, corpo = EmailService.template_abertura_os(
        os_obj.id, os_obj.codigo_ferramenta, descricao, os_obj.solicitante, os_obj.motivo_falha
    )
    ok, erro = EmailService.enviar(db, assunto, corpo)

    os_obj.email_status = 'ENVIADO' if ok else 'FALHOU'
    os_obj.email_enviado_em = _dt.now() if ok else os_obj.email_enviado_em
    os_obj.email_erro = None if ok else erro
    db.commit()

    if not ok:
        raise HTTPException(status_code=502, detail=f"Falha ao reenviar e-mail: {erro}")
    return {"status": "sucesso", "mensagem": f"E-mail da OS-{os_id} reenviado com sucesso."}


@app.post("/api/v1/requisicao/{req_id}/reenviar-email")
def requisicao_reenviar_email(req_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Reenvia o e-mail de notificação de uma requisição. Somente Admin ou Gestor."""
    if current_user.get("perfil") not in ["Admin", "Gestor"]:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from database.models import Requisicao
    from services.email_service import EmailService
    from datetime import datetime as _dt

    req_obj = db.query(Requisicao).filter(Requisicao.id == req_id).first()
    if not req_obj:
        raise HTTPException(status_code=404, detail=f"REQ-{req_id:04d} não encontrada.")

    itens = [
        {"codigo_produto": i.codigo_produto, "descricao_produto": i.descricao_produto, "quantidade_solicitada": i.quantidade_solicitada}
        for i in req_obj.itens
    ]
    assunto, corpo = EmailService.template_nova_requisicao(req_obj.id, req_obj.solicitante, req_obj.destino_projeto, itens)
    ok, erro = EmailService.enviar(db, assunto, corpo)

    req_obj.email_status = 'ENVIADO' if ok else 'FALHOU'
    req_obj.email_enviado_em = _dt.now() if ok else req_obj.email_enviado_em
    req_obj.email_erro = None if ok else erro
    db.commit()

    if not ok:
        raise HTTPException(status_code=502, detail=f"Falha ao reenviar e-mail: {erro}")
    return {"status": "sucesso", "mensagem": f"E-mail da REQ-{req_id:04d} reenviado com sucesso."}


@app.post("/api/v1/auditoria/reativar")
def auditoria_reativar(req: ReativarTagRequest, current_user: dict = Depends(get_current_user)):
    from controllers.auditoria import reativar_tag_extraviada
    sucesso, msg_reativacao = reativar_tag_extraviada(req.tag, req.polo, req.motivo, req.usuario)
    return {"status": sucesso, "mensagem": msg_reativacao}

class ProcessarCruzamentoRequest(BaseModel):
    polo: str
    tags_bipadas: list
    lotes_contados: dict

class ProcessarInventarioRequest(BaseModel):
    resultados_finais: list
    usuario: str
    polo: str
    inv_id: str

@app.get("/api/v1/imobilizado/catalogo/simples")
def imobilizado_catalogo_simples(
    skip: int = 0,
    limit: int = 500,
    current_user: dict = Depends(get_current_user)
):
    # P3-FIX: paginação adicionada
    from database.queries import carregar_dados
    df = carregar_dados("SELECT DISTINCT codigo, descricao, tipo_material FROM imobilizado")
    records = df.to_dict(orient='records') if not df.empty else []
    return records[skip: skip + limit]

@app.get("/api/v1/inventario/esperado")
def inventario_esperado(polo: str, classificacao: str, current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    query = "SELECT id, codigo, descricao, num_tag, quantidade, categoria FROM imobilizado WHERE localizacao = ? AND status IN ('Disponível', 'Manutenção')"
    if classificacao == "Apenas Ativos (Máquinas com TAG)":
        query += " AND num_tag IS NOT NULL AND trim(num_tag) != ''"
    elif classificacao == "Apenas Consumo (Lotes/Insumos)":
        query += " AND (num_tag IS NULL OR trim(num_tag) = '')"
    df = carregar_dados(query, (polo,))
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/inventario/cruzamento")
def inventario_cruzamento(req: ProcessarCruzamentoRequest, current_user: dict = Depends(get_current_user)):
    from controllers.auditoria import processar_cruzamento_wms
    res, div = processar_cruzamento_wms(req.polo, set(req.tags_bipadas), req.lotes_contados)
    return {"resultados_finais": res, "divergencias": div}

@app.post("/api/v1/inventario/processar")
def inventario_processar(req: ProcessarInventarioRequest, current_user: dict = Depends(get_current_user)):
    from controllers.auditoria import processar_resultados_inventario
    erros = processar_resultados_inventario(req.resultados_finais, req.usuario, req.polo, req.inv_id)
    return {"erros": erros}


class SalvarRequisicaoRequest(BaseModel):
    polo_alvo: str
    projeto: str
    solicitante: str
    df_carrinho: list

@app.post("/api/v1/requisicao/catalogo")
def requisicao_catalogo(req: dict, current_user: dict = Depends(get_current_user)):
    from controllers.requisicao import obter_catalogo_disponivel
    df = obter_catalogo_disponivel(req.get('polo_alvo'), req.get('carrinho_req'), req.get('tipo_filtro'))
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/requisicao/salvar")
def requisicao_salvar(req: SalvarRequisicaoRequest, current_user: dict = Depends(get_current_user)):
    from controllers.requisicao import salvar_nova_requisicao
    s, msg = salvar_nova_requisicao(req.polo_alvo, req.projeto, req.solicitante, req.df_carrinho)
    return {"status": s, "mensagem": msg}

@app.get("/api/v1/requisicao/historico")
def requisicao_historico(usuario: str, current_user: dict = Depends(get_current_user)):
    from controllers.requisicao import listar_historico_solicitante
    df = listar_historico_solicitante(usuario)
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/requisicao/{req_id}/itens")
def requisicao_req_id_itens(req_id: str, current_user: dict = Depends(get_current_user)):
    from controllers.requisicao import listar_itens_da_requisicao
    df = listar_itens_da_requisicao(req_id)
    return df.to_dict(orient='records') if not df.empty else []

class AbrirOSRequest(BaseModel):
    ferramenta_id: int
    codigo: str
    motivo: str
    solicitante: str
    usuario: str

class LancarOrcamentoRequest(BaseModel):
    ordem_id: int
    diagnostico: str
    custo: float
    mecanico: str
    empresa: str
    num_orcamento: str
    usuario: str

class AprovarOSRequest(BaseModel):
    ordem_id: int
    decisao: str
    usuario: str

class FinalizarOSRequest(BaseModel):
    ordem_id: int
    ferramenta_id: int
    destino: str
    usuario: str

@app.get("/api/v1/manutencao/ativos")
def manutencao_ativos(
    skip: int = 0,
    limit: int = 200,
    current_user: dict = Depends(get_current_user)
):
    # P3-FIX: paginação adicionada
    from controllers.manutencao import carregar_ativos_para_manutencao
    df = carregar_ativos_para_manutencao()
    records = df.to_dict(orient='records') if not df.empty else []
    return records[skip: skip + limit]

@app.post("/api/v1/manutencao/abrir")
def manutencao_abrir(req: AbrirOSRequest, current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import abrir_ordem_manutencao
    s, m = abrir_ordem_manutencao(req.ferramenta_id, req.codigo, req.motivo, req.solicitante, req.usuario)
    return {"status": s, "mensagem": m}

@app.get("/api/v1/manutencao/abertas")
def manutencao_abertas(current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import carregar_ordens_abertas
    df = carregar_ordens_abertas()
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/manutencao/orcamento")
def manutencao_orcamento(req: LancarOrcamentoRequest, current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import lancar_orcamento_oficina
    s = lancar_orcamento_oficina(req.ordem_id, req.diagnostico, req.custo, req.mecanico, req.empresa, req.num_orcamento, req.usuario)
    return {"status": s}

@app.get("/api/v1/manutencao/aprovacao")
def manutencao_aprovacao(current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import carregar_ordens_aprovacao
    df = carregar_ordens_aprovacao()
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/manutencao/aprovar")
def manutencao_aprovar(req: AprovarOSRequest, current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import aprovar_manutencao
    s = aprovar_manutencao(req.ordem_id, req.decisao, req.usuario)
    return {"status": s}

@app.get("/api/v1/manutencao/execucao")
def manutencao_execucao(current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import carregar_ordens_execucao
    df = carregar_ordens_execucao()
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/manutencao/finalizar")
def manutencao_finalizar(req: FinalizarOSRequest, current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import finalizar_reparo_oficina
    s = finalizar_reparo_oficina(req.ordem_id, req.ferramenta_id, req.destino, req.usuario)
    return {"status": s}

@app.get("/api/v1/manutencao/historico/{ferramenta_id}")
def manutencao_historico_ferramenta_id(ferramenta_id: str, current_user: dict = Depends(get_current_user)):
    from controllers.manutencao import carregar_historico_concluidas
    df = carregar_historico_concluidas(ferramenta_id)
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/inbound/malha-fina/faltas")
def inbound_malha_fina_faltas(current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    df = carregar_dados("SELECT id, codigo, descricao, num_tag, quantidade, localizacao, tipo_material FROM imobilizado WHERE alerta_falta = 1 AND quantidade > 0")
    return df.to_dict(orient='records') if not df.empty else []

# ==========================================
# ROTAS DE OUTBOUND / LOGÍSTICA
# ==========================================
@app.get("/api/v1/outbound/pedidos")
def outbound_pedidos(polo: str, current_user: dict = Depends(get_current_user)):
    from controllers.outbound import carregar_fila_pedidos
    df = carregar_fila_pedidos(polo)
    return df.to_dict(orient='records') if not df.empty else []

@app.post("/api/v1/outbound/pedidos/cancelar")
def outbound_pedidos_cancelar(req: CancelarPedidoRequest, current_user: dict = Depends(get_current_user)):
    from controllers.outbound import cancelar_pedido
    sucesso, msg = cancelar_pedido(req.true_id, req.req_id, req.motivo, req.usuario)
    if not sucesso:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}

@app.get("/api/v1/outbound/pedidos/{req_id}/picking")
def outbound_pedidos_req_id_picking(req_id: str, polo: str, current_user: dict = Depends(get_current_user)):
    from controllers.outbound import carregar_detalhes_picking
    df = carregar_detalhes_picking(req_id, polo)
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/outbound/tags")
def outbound_tags(codigo: str, polo: str, current_user: dict = Depends(get_current_user)):
    from controllers.outbound import obter_tags_disponiveis
    return {"tags": obter_tags_disponiveis(codigo, polo)}

@app.post("/api/v1/outbound/pedidos/despachar")
def outbound_pedidos_despachar(req: DespachoPedidoRequest, current_user: dict = Depends(get_current_user)):
    import pandas as pd
    from controllers.outbound import despachar_pedido_wms
    df_itens = pd.DataFrame(req.df_itens_json)
    sucesso, doc, msg = despachar_pedido_wms(
        req.true_id, req.req_id, req.polo, req.destino,
        req.dict_tags_final, req.dict_lotes_final, df_itens, req.usuario
    )
    if not sucesso:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "documento": doc, "mensagem": msg}

@app.get("/api/v1/outbound/transito")
def outbound_transito(polo: str, current_user: dict = Depends(get_current_user)):
    from controllers.outbound import listar_itens_em_transito
    df = listar_itens_em_transito(polo)
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/imobilizado/{codigo}")
def imobilizado_codigo(codigo: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    item = imob_repo.get_by_codigo(db, codigo)
    if not item:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return {
        "id": item.id,
        "codigo": item.codigo,
        "descricao": item.descricao,
        "quantidade": item.quantidade,
        "status": item.status,
        "localizacao": item.localizacao
    }

@app.get("/api/v1/polos/em-uso")
def polos_em_uso(current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    polos = imob_repo.get_in_use_locations(db)
    return {"polos": polos}

@app.post("/api/v1/outbound/baixa-excepcional")
def outbound_baixa_excepcional(payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    from services.outbound_service import OutboundService
    sucesso, msg = OutboundService.realizar_baixa_excepcional(
        db, payload.get('carrinho', []), payload.get('motivo'), 
        payload.get('documento'), payload.get('usuario'), 
        payload.get('polo'), payload.get('perfil_usuario', 'Operador')
    )
    if not sucesso:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}

@app.get("/api/v1/matriz-fisica/checar-codigo")
def matriz_fisica_checar_codigo(codigo: str, current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    df = carregar_dados("SELECT codigo FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo,))
    return {"encontrado": not df.empty}

@app.get("/api/v1/matriz-fisica/raw")
def matriz_fisica_raw(current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    df = carregar_dados("SELECT codigo, descricao, status, localizacao, quantidade FROM imobilizado")
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/etiquetas/produtos")
def etiquetas_produtos(tipo_material: str, current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    # CORRIGIDO: substituída f-string por query parametrizada (previne SQL Injection)
    df = carregar_dados(
        "SELECT DISTINCT codigo, descricao FROM imobilizado WHERE tipo_material = ? AND quantidade > 0 ORDER BY descricao",
        (tipo_material,)
    )
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/etiquetas/inventario")
def etiquetas_inventario(codigo: str, current_user: dict = Depends(get_current_user)):
    from database.queries import carregar_dados
    df = carregar_dados("SELECT id, num_tag, localizacao, quantidade, descricao FROM imobilizado WHERE codigo = ? AND quantidade > 0", (codigo,))
    return df.to_dict(orient='records') if not df.empty else []

@app.get("/api/v1/relatorios/produtos")
def relatorios_produtos(current_user: dict = Depends(get_current_user)):
    from controllers.relatorios import obter_lista_produtos
    return {"produtos": obter_lista_produtos()}

@app.get("/api/v1/relatorios/extrato")
def relatorios_extrato(produto: str, inicio: str, fim: str, current_user: dict = Depends(get_current_user)):
    from controllers.relatorios import gerar_extrato_movimentacoes
    from datetime import datetime
    dt_i = datetime.strptime(inicio, "%Y-%m-%d").date()
    dt_f = datetime.strptime(fim, "%Y-%m-%d").date()
    df, cod_puro = gerar_extrato_movimentacoes(produto, dt_i, dt_f)
    return {"dados": df.to_dict(orient='records') if not df.empty else [], "codigo": cod_puro}

@app.get("/api/v1/relatorios/posicao")
def relatorios_posicao(
    skip: int = 0,
    limit: int = 1000,
    current_user: dict = Depends(get_current_user)
):
    # P3-FIX: paginação adicionada
    from controllers.relatorios import gerar_posicao_consolidada
    df = gerar_posicao_consolidada()
    records = df.to_dict(orient='records') if not df.empty else []
    return records[skip: skip + limit]

@app.get("/api/v1/relatorios/manutencao")
def relatorios_manutencao(inicio: str, fim: str, status: str, current_user: dict = Depends(get_current_user)):
    from controllers.relatorios import gerar_relatorio_manutencao
    from datetime import datetime
    dt_i = datetime.strptime(inicio, "%Y-%m-%d").date()
    dt_f = datetime.strptime(fim, "%Y-%m-%d").date()
    df = gerar_relatorio_manutencao(dt_i, dt_f, status)
    return df.to_dict(orient='records') if not df.empty else []

class AuditoriaLogsRequest(BaseModel):
    filtro_acao: str
    filtro_usuario: str
    filtro_data: str

@app.post("/api/v1/auditoria/logs")
def auditoria_logs(req: AuditoriaLogsRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    import os
    from sqlalchemy import text
    db_type = os.getenv("DB_TYPE", "sqlite")

    # Constrói query com parâmetros nomeados para compatibilidade SQLite/Postgres
    conditions = ["1=1"]
    params: dict = {}
    if req.filtro_acao != "Todas":
        conditions.append("acao = :acao")
        params["acao"] = req.filtro_acao
    if req.filtro_usuario:
        conditions.append("usuario LIKE :usuario")
        params["usuario"] = f"%{req.filtro_usuario}%"
    if req.filtro_data:
        if db_type == "postgres":
            conditions.append("CAST(data_hora AS DATE) = CAST(:data AS DATE)")
        else:
            conditions.append("DATE(data_hora) = :data")
        params["data"] = req.filtro_data

    sql = "SELECT id, data_hora, usuario, acao, tabela, registro_id, detalhes FROM logs_auditoria WHERE " + " AND ".join(conditions) + " ORDER BY id DESC LIMIT 1000"
    rows = db.execute(text(sql), params).fetchall()
    return [
        {
            "id": r[0],
            "data_hora": str(r[1]),
            "usuario": r[2],
            "acao": r[3],
            "tabela": r[4],
            "registro_id": r[5],
            "detalhes": r[6],
        }
        for r in rows
    ]


# ==========================================
# ROTAS FISCAIS — NF-e (TRAVA DE SEGURANÇA)
# ==========================================

class PrepararNFRequest(BaseModel):
    tipo_operacao: str                      # 'entrada' ou 'saida'
    dados_mercadoria: list[dict]            # [{codigo, descricao, ncm, quantidade, valor_unitario}]
    dados_destinatario_remetente: dict      # {cnpj, nome, logradouro, municipio, uf, cep}
    numero_nf_ref: str = ""                 # NF de referência (entrada via compra)

class AprovarNFRequest(BaseModel):
    rascunho_id: int
    # Campos opcionais para quando a aprovação ocorre após emissão manual externa
    chave_acesso: str = ""
    protocolo_sefaz: str = ""
    numero_nf: str = ""

class CancelarNFRequest(BaseModel):
    rascunho_id: int
    motivo: str


@app.post("/api/v1/fiscal/preparar", tags=["Fiscal"])
def fiscal_preparar(
    req: PrepararNFRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Prepara o rascunho da NF-e e salva no BD com status='PENDENTE'.

    TRAVA DE SEGURANÇA: Este endpoint NUNCA emite a NF-e.
    A emissão real ocorre apenas em /api/v1/fiscal/emitir, com aprovação
    de usuário autorizado (perfil ADMIN ou FISCAL).
    """
    from services.fiscal_service import FiscalService

    resultado = FiscalService.preparar_emissao_nf_sefaz(
        session=db,
        tipo_operacao=req.tipo_operacao,
        dados_mercadoria=req.dados_mercadoria,
        dados_destinatario_remetente=req.dados_destinatario_remetente,
        usuario=current_user.get("sub", "sistema"),
        numero_nf=req.numero_nf_ref or None,
    )

    # Se APIs insuficientes, retorna 422 com o aviso completo para o front
    if not resultado["api_gratuita_disponivel"]:
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "APIS_INSUFICIENTES",
                "aviso": resultado["aviso"],
                "mensagem": resultado["mensagem"],
            },
        )

    if not resultado["sucesso"]:
        raise HTTPException(status_code=400, detail=resultado["mensagem"])

    return {
        "status": "rascunho_criado",
        "rascunho_id": resultado["rascunho_id"],
        "aviso": resultado["aviso"],
        "mensagem": resultado["mensagem"],
        "payload_resumo": {
            "tipo_operacao": req.tipo_operacao,
            "total_itens": len(req.dados_mercadoria),
            "valor_total_nf": resultado["payload"]["vNF"] if resultado["payload"] else 0,
        },
    }


@app.get("/api/v1/fiscal/rascunhos", tags=["Fiscal"])
def fiscal_rascunhos(
    status: str = "PENDENTE",
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista rascunhos de NF-e filtrados por status."""
    import json
    rascunhos = (
        db.query(NotaFiscalRascunho)
        .filter(NotaFiscalRascunho.status == status.upper())
        .order_by(NotaFiscalRascunho.criado_em.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id":            r.id,
            "tipo_operacao": r.tipo_operacao,
            "status":        r.status,
            "criado_por":    r.criado_por,
            "criado_em":     str(r.criado_em),
            "aprovado_por":  r.aprovado_por,
            "numero_nf":     r.numero_nf,
            "chave_acesso":  r.chave_acesso,
            "payload":       json.loads(r.payload_json) if r.payload_json else {},
        }
        for r in rascunhos
    ]


@app.post("/api/v1/fiscal/emitir", tags=["Fiscal"])
def fiscal_emitir(
    req: AprovarNFRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    TRAVA DE SEGURANÇA — Aprovação humana para emissão de NF-e.

    Apenas usuários com perfil 'Admin' ou 'Fiscal' podem chamar este endpoint.
    O rascunho deve estar em status='PENDENTE'.

    IMPORTANTE: Este endpoint marca o rascunho como 'EMITIDA' e registra
    quem aprovou. A assinatura digital e envio ao SEFAZ devem ser feitos
    pelo módulo de certificado digital (fora do escopo desta versão —
    requer Certificado A1 e PyNFe ou serviço pago).
    """
    # ── Verificação de perfil (trava de segurança) ──────────────────
    perfil = current_user.get("perfil", "").strip().lower()
    if perfil not in ("admin", "fiscal", "adm", "gestor"):
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: apenas usuários com perfil Admin ou Fiscal podem emitir NF-e.",
        )

    rascunho = db.query(NotaFiscalRascunho).filter(
        NotaFiscalRascunho.id == req.rascunho_id
    ).first()

    if not rascunho:
        raise HTTPException(status_code=404, detail="Rascunho não encontrado.")

    if rascunho.status != "PENDENTE":
        raise HTTPException(
            status_code=409,
            detail=f"Rascunho já processado (status atual: {rascunho.status}).",
        )

    # ── Atualiza o rascunho ─────────────────────────────────────────
    from datetime import datetime as dt_cls
    rascunho.status        = "EMITIDA"
    rascunho.aprovado_por  = current_user.get("sub")
    rascunho.aprovado_em   = dt_cls.now()
    rascunho.chave_acesso  = req.chave_acesso or None
    rascunho.protocolo_sefaz = req.protocolo_sefaz or None
    rascunho.numero_nf     = req.numero_nf or None

    # ── Log de auditoria ────────────────────────────────────────────
    from services.governance_service import GovernanceService
    GovernanceService.registar_log(
        db,
        current_user.get("sub", "sistema"),
        "notas_fiscais_rascunho",
        rascunho.id,
        "NF_APROVADA_EMITIDA",
        (
            f"Rascunho #{rascunho.id} aprovado por {current_user.get('sub')}. "
            f"NF: {req.numero_nf} | Chave: {req.chave_acesso}"
        ),
    )
    db.commit()

    return {
        "status": "emitida",
        "rascunho_id": rascunho.id,
        "mensagem": f"Rascunho #{rascunho.id} marcado como EMITIDA com sucesso.",
    }


@app.post("/api/v1/fiscal/cancelar", tags=["Fiscal"])
def fiscal_cancelar(
    req: CancelarNFRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Cancela um rascunho de NF-e pendente. Apenas perfil Admin ou Fiscal."""
    perfil = current_user.get("perfil", "").strip().lower()
    if perfil not in ("admin", "fiscal", "adm", "gestor"):
        raise HTTPException(status_code=403, detail="Acesso negado.")

    rascunho = db.query(NotaFiscalRascunho).filter(
        NotaFiscalRascunho.id == req.rascunho_id
    ).first()
    if not rascunho:
        raise HTTPException(status_code=404, detail="Rascunho não encontrado.")
    if rascunho.status not in ("PENDENTE",):
        raise HTTPException(
            status_code=409,
            detail=f"Não é possível cancelar um rascunho com status '{rascunho.status}'.",
        )

    from datetime import datetime as dt_cls
    rascunho.status          = "CANCELADA"
    rascunho.motivo_rejeicao = req.motivo
    rascunho.aprovado_por    = current_user.get("sub")
    rascunho.aprovado_em     = dt_cls.now()

    from services.governance_service import GovernanceService
    GovernanceService.registar_log(
        db,
        current_user.get("sub", "sistema"),
        "notas_fiscais_rascunho",
        rascunho.id,
        "NF_CANCELADA",
        f"Rascunho #{rascunho.id} cancelado. Motivo: {req.motivo}",
    )
    db.commit()

    return {"status": "cancelada", "rascunho_id": rascunho.id}


# ============================================================
# ROTAS — CNPJ
# ============================================================

@app.get("/api/v1/cnpj/{cnpj}", tags=["CNPJ"])
def cnpj_consultar(cnpj: str, _: dict = Depends(get_current_user)):
    """Consulta CNPJ via BrasilAPI com validação por dígito verificador."""
    from services.cnpj_service import CnpjService
    resultado = CnpjService.consultar(cnpj)
    return resultado


# ============================================================
# ROTAS — EMPRESA EMITENTE
# ============================================================

@app.get("/api/v1/emitente", tags=["Emitente"])
def emitente_get(_: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Retorna os dados do emitente ativo."""
    from services.emitente_service import EmitenteService
    e = EmitenteService.get_ou_criar(db)
    return EmitenteService.serializar(e)


@app.put("/api/v1/emitente", tags=["Emitente"])
def emitente_put(req: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Atualiza dados do emitente. Somente Admin."""
    if current_user.get("perfil") != "Admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem alterar o emitente.")
    from services.emitente_service import EmitenteService
    ok, msg = EmitenteService.atualizar(db, req, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


@app.post("/api/v1/emitente/sincronizar", tags=["Emitente"])
def emitente_sincronizar(current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Sincroniza dados do emitente via BrasilAPI usando o CNPJ cadastrado."""
    if current_user.get("perfil") != "Admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem sincronizar o emitente.")
    from services.emitente_service import EmitenteService
    ok, msg, dados = EmitenteService.sincronizar_cnpj(db, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "dados": dados}


# ============================================================
# ROTAS — PARCEIROS
# ============================================================

class CriarParceiroRequest(BaseModel):
    tipo: str = "CLIENTE"
    razao_social: str
    nome_fantasia: str = ""
    cnpj: str = ""
    ie: str = ""
    im: str = ""
    cep: str = ""
    logradouro: str = ""
    numero: str = ""
    complemento: str = ""
    bairro: str = ""
    municipio: str = ""
    uf: str = ""
    codigo_ibge: str = ""
    telefone: str = ""
    email_contato: str = ""
    regime_tributario: str = "REGIME_NORMAL"
    contribuinte_icms: int = 1


@app.get("/api/v1/parceiros", tags=["Parceiros"])
def parceiros_listar(tipo: str = "", _: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    from repositories.parceiro_repository import ParceiroRepository
    from services.parceiro_service import ParceiroService
    repo = ParceiroRepository()
    parceiros = repo.listar_ativos(db, tipo)
    return [ParceiroService.serializar(p) for p in parceiros]


@app.post("/api/v1/parceiros", tags=["Parceiros"])
def parceiros_criar(req: CriarParceiroRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    if current_user.get("perfil") not in ["Admin", "Gestor"]:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from services.parceiro_service import ParceiroService
    ok, msg, parceiro = ParceiroService.criar(db, req.model_dump(), current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "id": parceiro.id}


@app.put("/api/v1/parceiros/{parceiro_id}", tags=["Parceiros"])
def parceiros_atualizar(parceiro_id: int, req: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    if current_user.get("perfil") not in ["Admin", "Gestor"]:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from services.parceiro_service import ParceiroService
    ok, msg = ParceiroService.atualizar(db, parceiro_id, req, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


@app.post("/api/v1/parceiros/{parceiro_id}/enriquecer", tags=["Parceiros"])
def parceiros_enriquecer(parceiro_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    """Consulta BrasilAPI e atualiza dados do parceiro."""
    from services.parceiro_service import ParceiroService
    ok, msg, dados = ParceiroService.enriquecer_cnpj(db, parceiro_id, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "dados": dados}


# ============================================================
# ROTAS — REGRAS DE OPERAÇÃO FISCAL
# ============================================================

@app.get("/api/v1/fiscal/produtos/busca", tags=["Fiscal"])
def fiscal_produtos_busca(
    termo: str = "",
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Busca produtos do catálogo com campos fiscais (NCM, EAN, origem) e TAGs disponíveis."""
    from database.models import Imobilizado
    from sqlalchemy import or_

    q = db.query(Imobilizado).filter(Imobilizado.status == "Catálogo")
    if termo:
        q = q.filter(
            or_(
                Imobilizado.codigo.ilike(f"%{termo}%"),
                Imobilizado.descricao.ilike(f"%{termo}%"),
            )
        )
    produtos = q.order_by(Imobilizado.descricao).limit(50).all()

    # Pre-fetch all tags in a single query to avoid N+1
    tags_por_codigo: dict = {}
    if produtos:
        codigos = [p.codigo for p in produtos]
        tags_rows = (
            db.query(Imobilizado.codigo, Imobilizado.num_tag)
            .filter(
                Imobilizado.codigo.in_(codigos),
                Imobilizado.status != "Catálogo",
                Imobilizado.quantidade > 0,
                Imobilizado.num_tag != "",
                Imobilizado.num_tag.isnot(None),
            )
            .all()
        )
        for row in tags_rows:
            tags_por_codigo.setdefault(row.codigo, []).append(row.num_tag)

    resultado = []
    for p in produtos:
        resultado.append({
            "codigo":          p.codigo,
            "descricao":       p.descricao or "",
            "marca":           p.marca or "",
            "modelo":          p.modelo or "",
            "valor_unitario":  float(p.valor_unitario or 0),
            "ncm":             (p.ncm or "") if hasattr(p, "ncm") else "",
            "c_ean":           (p.c_ean or "SEM GTIN") if hasattr(p, "c_ean") else "SEM GTIN",
            "orig_icms":       (p.orig_icms or "0") if hasattr(p, "orig_icms") else "0",
            "cest":            (p.cest or "") if hasattr(p, "cest") else "",
            "tipo_controle":   p.tipo_controle or "",
            "tags_disponiveis": tags_por_codigo.get(p.codigo, []),
        })
    return resultado


@app.get("/api/v1/fiscal/regras", tags=["Fiscal"])
def fiscal_regras(_: dict = Depends(get_current_user), db: Session = Depends(get_session)):
    from repositories.documento_fiscal_repository import RegraOperacaoFiscalRepository
    repo = RegraOperacaoFiscalRepository()
    regras = repo.listar_ativas(db)
    return [
        {
            "id": r.id, "nome": r.nome, "tipo_operacao": r.tipo_operacao,
            "cfop_interno": r.cfop_interno, "cfop_interestadual": r.cfop_interestadual,
            "natureza_operacao": r.natureza_operacao,
            "cst_icms": r.cst_icms or "", "csosn": r.csosn or "",
            "permite_destaque_icms": bool(r.permite_destaque_icms),
        }
        for r in regras
    ]


# ============================================================
# ROTAS — DOCUMENTOS FISCAIS (NF-e estruturado)
# ============================================================

class CriarDocumentoFiscalRequest(BaseModel):
    subtipo: str                  # REMESSA_CONSERTO | RETORNO_CONSERTO | SAIDA_GERAL | ENTRADA_GERAL
    parceiro_id: int
    itens: list[dict]
    serie: str = "1"
    observacao: str = ""
    doc_vinculado_id: int = 0
    num_os: str = ""              # Número da OS de manutenção
    asset_tag: str = ""           # Tag / patrimônio do bem
    num_serie: str = ""           # Número de série do bem
    mod_frete: str = "9"          # 0=emit, 1=dest, 2=terceiros, 9=sem frete
    ind_final: int = 0            # 0=não consumidor final, 1=consumidor final
    ind_pres: int = 0             # 0=não se aplica, 1=presencial, 2=internet


class AprovarDocumentoFiscalRequest(BaseModel):
    doc_id: int
    numero_nf: str = ""
    chave_acesso: str = ""
    protocolo_sefaz: str = ""


class CancelarDocumentoFiscalRequest(BaseModel):
    doc_id: int
    motivo: str


@app.post("/api/v1/fiscal/documentos", tags=["Fiscal"])
def fiscal_documentos_criar(
    req: CriarDocumentoFiscalRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Cria rascunho de NF-e estruturado com CFOP parametrizado conforme subtipo."""
    from services.documento_fiscal_service import DocumentoFiscalService

    _usuario = current_user.get("sub", "sistema")
    _op_kwargs = dict(
        num_os=req.num_os or "",
        asset_tag=req.asset_tag or "",
        num_serie=req.num_serie or "",
        mod_frete=req.mod_frete or "9",
        ind_final=req.ind_final,
        ind_pres=req.ind_pres,
    )
    metodos = {
        "REMESSA_CONSERTO": lambda: DocumentoFiscalService.criar_remessa_conserto(
            db, req.parceiro_id, req.itens, req.serie, req.observacao,
            _usuario, **_op_kwargs,
        ),
        "RETORNO_CONSERTO": lambda: DocumentoFiscalService.criar_retorno_conserto(
            db, req.parceiro_id, req.itens, req.serie, req.observacao,
            req.doc_vinculado_id or None, _usuario, **_op_kwargs,
        ),
        "SAIDA_GERAL": lambda: DocumentoFiscalService.criar_saida_geral(
            db, req.parceiro_id, req.itens, req.serie, req.observacao,
            _usuario, **_op_kwargs,
        ),
        "ENTRADA_GERAL": lambda: DocumentoFiscalService.criar_entrada_geral(
            db, req.parceiro_id, req.itens, req.serie, req.observacao,
            _usuario, **_op_kwargs,
        ),
    }

    criador = metodos.get(req.subtipo)
    if not criador:
        raise HTTPException(status_code=400, detail=f"Subtipo '{req.subtipo}' inválido.")

    ok, msg, doc_id = criador()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "doc_id": doc_id}


@app.get("/api/v1/fiscal/documentos", tags=["Fiscal"])
def fiscal_documentos_listar(
    status: str = "RASCUNHO",
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from repositories.documento_fiscal_repository import DocumentoFiscalRepository
    from services.documento_fiscal_service import DocumentoFiscalService
    repo = DocumentoFiscalRepository()
    if status.upper() == "TODOS":
        docs = repo.listar_todos(db)
    else:
        docs = repo.listar_por_status(db, status)
    return [DocumentoFiscalService.serializar(d) for d in docs]


@app.get("/api/v1/fiscal/documentos/remessas-abertas", tags=["Fiscal"])
def fiscal_remessas_abertas(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista remessas para conserto sem retorno vinculado."""
    from repositories.documento_fiscal_repository import DocumentoFiscalRepository
    from services.documento_fiscal_service import DocumentoFiscalService
    repo = DocumentoFiscalRepository()
    docs = repo.listar_remessas_abertas(db)
    return [DocumentoFiscalService.serializar(d) for d in docs]


@app.get("/api/v1/fiscal/os-concluidas", tags=["Fiscal"])
def fiscal_os_concluidas(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista OS de manutenção concluídas para importação em NF-e."""
    from database.models import ManutencaoOrdem, Imobilizado
    ordens = (
        db.query(ManutencaoOrdem)
        .filter(ManutencaoOrdem.status_ordem == "Concluída")
        .order_by(ManutencaoOrdem.data_entrada.desc())
        .limit(200)
        .all()
    )
    result = []
    for os_ in ordens:
        imob = db.query(Imobilizado).filter(
            Imobilizado.id == os_.ferramenta_id
        ).first() if os_.ferramenta_id else None
        result.append({
            "id": os_.id,
            "codigo_ferramenta": os_.codigo_ferramenta or "",
            "descricao": imob.descricao if imob else os_.codigo_ferramenta or "",
            "ncm": (imob.ncm or "") if imob and hasattr(imob, "ncm") else "",
            "c_ean": (imob.c_ean or "SEM GTIN") if imob and hasattr(imob, "c_ean") else "SEM GTIN",
            "orig_icms": (imob.orig_icms or "0") if imob and hasattr(imob, "orig_icms") else "0",
            "cest": (imob.cest or "") if imob and hasattr(imob, "cest") else "",
            "valor_unitario": float(imob.valor_unitario or 0) if imob else float(os_.custo_reparo or 0),
            "custo_reparo": float(os_.custo_reparo or 0),
            "num_os": str(os_.id),
            "asset_tag": os_.codigo_ferramenta or "",
            "data_entrada": os_.data_entrada.isoformat() if os_.data_entrada else None,
            "data_saida": os_.data_saida.isoformat() if os_.data_saida else None,
            "empresa_reparo": os_.empresa_reparo or "",
            "num_orcamento": os_.num_orcamento or "",
        })
    return result


@app.get("/api/v1/fiscal/requisicoes-concluidas", tags=["Fiscal"])
def fiscal_requisicoes_concluidas(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Lista requisições concluídas do Outbound com itens e dados fiscais do catálogo."""
    from database.models import Requisicao, RequisicaoItem, Imobilizado
    reqs = (
        db.query(Requisicao)
        .filter(Requisicao.status == "Concluída")
        .order_by(Requisicao.data_solicitacao.desc())
        .limit(200)
        .all()
    )
    result = []
    for req in reqs:
        itens_out = []
        for item in req.itens:
            imob = db.query(Imobilizado).filter(
                Imobilizado.codigo == item.codigo_produto,
                Imobilizado.status == "Catálogo",
            ).first()
            itens_out.append({
                "codigo":         item.codigo_produto or "",
                "descricao":      item.descricao_produto or "",
                "quantidade":     float(item.quantidade_solicitada or 1),
                "ncm":            (imob.ncm or "") if imob and hasattr(imob, "ncm") else "",
                "c_ean":          (imob.c_ean or "SEM GTIN") if imob and hasattr(imob, "c_ean") else "SEM GTIN",
                "orig_icms":      (imob.orig_icms or "0") if imob and hasattr(imob, "orig_icms") else "0",
                "cest":           (imob.cest or "") if imob and hasattr(imob, "cest") else "",
                "valor_unitario": float(imob.valor_unitario or 0) if imob else 0.0,
            })
        result.append({
            "id":              req.id,
            "solicitante":     req.solicitante or "",
            "polo_origem":     req.polo_origem or "",
            "destino_projeto": req.destino_projeto or "",
            "data_solicitacao": req.data_solicitacao.isoformat() if req.data_solicitacao else None,
            "itens":           itens_out,
        })
    return result


@app.get("/api/v1/fiscal/documentos/{doc_id}/pdf", tags=["Fiscal"])
def fiscal_documento_pdf(
    doc_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Gera e retorna o DANFE-Rascunho em PDF para download."""
    from fastapi.responses import Response
    from repositories.documento_fiscal_repository import DocumentoFiscalRepository
    from services.documento_fiscal_service import DocumentoFiscalService
    from utils.danfe_pdf import gerar_danfe_rascunho

    repo = DocumentoFiscalRepository()
    doc = repo.get_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    doc_dict = DocumentoFiscalService.serializar(doc)
    from database.models import Configuracoes as _Conf
    _conf = db.query(_Conf).first()
    if _conf and _conf.logo_base64:
        doc_dict['logo_base64'] = _conf.logo_base64
    pdf_bytes = gerar_danfe_rascunho(doc_dict)

    filename = f"DANFE_Rascunho_{doc_id:05d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _gerar_xml_rascunho(doc: dict) -> bytes:
    """Gera XML informacional (não SEFAZ-válido) do documento fiscal rascunho."""
    root = ET.Element("nfeRascunho", versao="4.00")
    ET.SubElement(root, "aviso").text = (
        "RASCUNHO — SEM VALOR FISCAL — NAO TRANSMITIDO A SEFAZ"
    )

    infNFe = ET.SubElement(root, "infNFe")

    ide = ET.SubElement(infNFe, "ide")
    ET.SubElement(ide, "nNF").text    = str(doc.get("numero") or "0")
    ET.SubElement(ide, "serie").text  = str(doc.get("serie") or "1")
    ET.SubElement(ide, "mod").text    = "55"
    ET.SubElement(ide, "dhEmi").text  = str(doc.get("criado_em") or "")
    ET.SubElement(ide, "tpNF").text   = str(doc.get("tipo_nf") or "1")
    ET.SubElement(ide, "natOp").text  = str(doc.get("natureza_operacao") or "")
    ET.SubElement(ide, "CFOP").text   = str(doc.get("cfop") or "")
    ET.SubElement(ide, "status").text = str(doc.get("status") or "RASCUNHO")

    emit_snap = doc.get("emitente_snapshot") or {}
    emit = ET.SubElement(infNFe, "emit")
    ET.SubElement(emit, "CNPJ").text  = re.sub(r"\D", "", emit_snap.get("cnpj") or "")
    ET.SubElement(emit, "xNome").text = emit_snap.get("razao_social") or ""
    ET.SubElement(emit, "IE").text    = emit_snap.get("ie") or ""

    parc_snap = doc.get("parceiro_snapshot") or {}
    dest = ET.SubElement(infNFe, "dest")
    ET.SubElement(dest, "CNPJ").text  = re.sub(r"\D", "", parc_snap.get("cnpj") or "")
    ET.SubElement(dest, "xNome").text = parc_snap.get("razao_social") or ""
    ET.SubElement(dest, "IE").text    = parc_snap.get("ie") or ""

    for it in (doc.get("itens") or []):
        det = ET.SubElement(infNFe, "det", nItem=str(it.get("sequencia", 1)))
        prod = ET.SubElement(det, "prod")
        ET.SubElement(prod, "cProd").text    = str(it.get("codigo_produto") or "")
        ET.SubElement(prod, "xProd").text    = str(it.get("descricao") or "")
        ET.SubElement(prod, "NCM").text      = str(it.get("ncm") or "")
        ET.SubElement(prod, "CFOP").text     = str(it.get("cfop") or "")
        ET.SubElement(prod, "uCom").text     = str(it.get("unidade") or "UN")
        ET.SubElement(prod, "qCom").text     = str(it.get("quantidade") or "1")
        ET.SubElement(prod, "vUnCom").text   = str(it.get("valor_unitario") or "0")
        ET.SubElement(prod, "vProd").text    = str(it.get("valor_total") or "0")
        ET.SubElement(prod, "cEAN").text     = str(it.get("c_ean") or "SEM GTIN")
        ET.SubElement(prod, "origICMS").text = str(it.get("orig_icms") or "0")

        imposto = ET.SubElement(det, "imposto")
        icms = ET.SubElement(imposto, "ICMS")
        ET.SubElement(icms, "CST").text  = str(it.get("cst_icms") or "")
        ipi = ET.SubElement(imposto, "IPI")
        ET.SubElement(ipi, "CST").text   = str(it.get("ipi_cst") or "")
        pis = ET.SubElement(imposto, "PIS")
        ET.SubElement(pis, "CST").text   = str(it.get("pis_cst") or "")
        cof = ET.SubElement(imposto, "COFINS")
        ET.SubElement(cof, "CST").text   = str(it.get("cofins_cst") or "")

    total = ET.SubElement(infNFe, "total")
    ET.SubElement(total, "vNF").text = str(doc.get("valor_total") or "0")

    if doc.get("info_complementar"):
        infAdic = ET.SubElement(infNFe, "infAdic")
        ET.SubElement(infAdic, "infCpl").text = str(doc["info_complementar"])

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
    return xml_str.encode("utf-8")


@app.post("/api/v1/fiscal/documentos/{doc_id}/enviar-email", tags=["Fiscal"])
def fiscal_documento_enviar_email(
    doc_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Envia DANFE PDF + XML informacional para o e-mail do parceiro e destinatários do sistema."""
    from repositories.documento_fiscal_repository import DocumentoFiscalRepository
    from services.documento_fiscal_service import DocumentoFiscalService
    from services.email_service import EmailService
    from utils.danfe_pdf import gerar_danfe_rascunho, _SUBTIPO_LABEL
    from database.models import Parceiro

    repo = DocumentoFiscalRepository()
    doc_obj = repo.get_by_id(db, doc_id)
    if not doc_obj:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    doc = DocumentoFiscalService.serializar(doc_obj)
    from database.models import Configuracoes as _Conf
    _conf = db.query(_Conf).first()
    if _conf and _conf.logo_base64:
        doc['logo_base64'] = _conf.logo_base64

    parc = db.query(Parceiro).filter(Parceiro.id == doc_obj.parceiro_id).first()
    parceiro_email = (parc.email_contato or "").strip() if parc else ""

    try:
        pdf_bytes = gerar_danfe_rascunho(doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {exc}")

    xml_bytes = _gerar_xml_rascunho(doc)

    subtipo_label = _SUBTIPO_LABEL.get(doc.get("subtipo", ""), doc.get("subtipo", ""))
    emit_nome     = (doc.get("emitente_snapshot") or {}).get("razao_social", "TraceBox WMS")
    parc_nome     = (doc.get("parceiro_snapshot") or {}).get("razao_social", "Parceiro")
    vl_fmt        = f"R$ {doc.get('valor_total', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    os_tag_html = ""
    if doc.get("num_os") or doc.get("asset_tag"):
        parts = []
        if doc.get("num_os"):    parts.append(f"OS: <strong>{doc['num_os']}</strong>")
        if doc.get("asset_tag"): parts.append(f"Tag: <strong>{doc['asset_tag']}</strong>")
        if doc.get("num_serie"): parts.append(f"Série: <strong>{doc['num_serie']}</strong>")
        os_tag_html = (
            "<p style='background:#f0fdf4;padding:10px;border-radius:6px;margin-top:12px;'>"
            "🔧 " + " &nbsp;|&nbsp; ".join(parts) + "</p>"
        )

    assunto = f"TraceBox WMS — DANFE Rascunho #{doc_id} | {subtipo_label} | {emit_nome}"
    corpo_html = f"""
<div style="font-family:Arial,sans-serif;max-width:650px;margin:auto;">
  <div style="background:#1e40af;padding:20px;border-radius:8px 8px 0 0;">
    <h2 style="color:white;margin:0;">🧾 Documento Fiscal — DANFE Rascunho</h2>
    <p style="color:#bfdbfe;margin:6px 0 0;">Documento #{doc_id} — {subtipo_label}</p>
  </div>
  <div style="border:1px solid #e2e8f0;padding:24px;border-radius:0 0 8px 8px;">
    <div style="background:#fef9c3;padding:12px;border-radius:6px;color:#854d0e;margin-bottom:16px;">
      ⚠️ <strong>RASCUNHO — SEM VALOR FISCAL</strong><br>
      Este documento é interno e não substitui a NF-e autorizada pela SEFAZ.
    </div>
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px;color:#64748b;width:40%;">Documento</td>
          <td style="padding:8px;font-weight:bold;">#{doc_id}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;">Operação</td>
          <td style="padding:8px;">{subtipo_label}</td></tr>
      <tr><td style="padding:8px;color:#64748b;">CFOP</td>
          <td style="padding:8px;">{doc.get("cfop","—")}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;">Emitente</td>
          <td style="padding:8px;">{emit_nome}</td></tr>
      <tr><td style="padding:8px;color:#64748b;">Destinatário / Remetente</td>
          <td style="padding:8px;">{parc_nome}</td></tr>
      <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;">Valor Total</td>
          <td style="padding:8px;font-weight:bold;">{vl_fmt}</td></tr>
      <tr><td style="padding:8px;color:#64748b;">Status</td>
          <td style="padding:8px;">{doc.get("status","RASCUNHO")}</td></tr>
    </table>
    {os_tag_html}
    <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0;">
    <p style="color:#64748b;font-size:12px;">
      Segue em anexo o <strong>DANFE (PDF)</strong> e o <strong>XML informacional</strong> do documento.<br>
      Este é um e-mail automático do sistema <strong>TraceBox WMS</strong>.
    </p>
  </div>
</div>
"""

    _anexos = [
        {"nome": f"DANFE_Rascunho_{doc_id:05d}.pdf", "dados": pdf_bytes, "tipo": "application/pdf"},
        {"nome": f"NFe_Rascunho_{doc_id:05d}.xml",   "dados": xml_bytes, "tipo": "application/xml"},
    ]

    if parceiro_email:
        # Envia diretamente para o e-mail do parceiro (destinatário do documento fiscal)
        ok, erro = EmailService.enviar_fiscal_com_anexos(
            session=db,
            assunto=assunto,
            corpo_html=corpo_html,
            destinatarios=[parceiro_email],
            anexos=_anexos,
        )
    else:
        # Sem e-mail do parceiro: usa destinatários configurados no sistema (fallback)
        ok, erro = EmailService.enviar_com_anexos(
            session=db,
            assunto=assunto,
            corpo_html=corpo_html,
            destinatarios_extra=[],
            anexos=_anexos,
        )

    if not ok:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar e-mail: {erro}")

    return {
        "status":         "enviado",
        "mensagem":       f"E-mail enviado com DANFE PDF e XML"
                          + (f" para {parceiro_email}" if parceiro_email else " para destinatários do sistema") + ".",
        "parceiro_email": parceiro_email,
    }


# ── CFOP Config ──────────────────────────────────────────────────────────────

class CfopConfigRequest(BaseModel):
    tipo_operacao: str
    grupo_operacao: str = ""
    direcao: str           # SAIDA | ENTRADA
    cfop_interno: str
    cfop_interestadual: str
    natureza_padrao: str = ""
    ativo: int = 1


@app.get("/api/v1/fiscal/cfop-config", tags=["Fiscal"])
def fiscal_cfop_listar(
    direcao: str = None,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from database.models import FiscalCfopConfig
    q = db.query(FiscalCfopConfig).filter(FiscalCfopConfig.ativo == 1)
    if direcao:
        q = q.filter(FiscalCfopConfig.direcao == direcao.upper())
    rows = q.order_by(FiscalCfopConfig.direcao, FiscalCfopConfig.tipo_operacao).all()
    return [
        {
            "id": r.id,
            "tipo_operacao": r.tipo_operacao,
            "grupo_operacao": r.grupo_operacao,
            "direcao": r.direcao,
            "cfop_interno": r.cfop_interno,
            "cfop_interestadual": r.cfop_interestadual,
            "natureza_padrao": r.natureza_padrao,
            "ativo": r.ativo,
        }
        for r in rows
    ]


@app.post("/api/v1/fiscal/cfop-config", tags=["Fiscal"])
def fiscal_cfop_criar(
    req: CfopConfigRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    if current_user.get("perfil", "").lower() not in ("admin", "gestor"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from database.models import FiscalCfopConfig
    from datetime import datetime as _dt
    row = FiscalCfopConfig(
        tipo_operacao=req.tipo_operacao,
        grupo_operacao=req.grupo_operacao,
        direcao=req.direcao.upper(),
        cfop_interno=req.cfop_interno,
        cfop_interestadual=req.cfop_interestadual,
        natureza_padrao=req.natureza_padrao,
        ativo=req.ativo,
        criado_em=_dt.now(),
        atualizado_em=_dt.now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "mensagem": "Configuração CFOP criada."}


@app.put("/api/v1/fiscal/cfop-config/{config_id}", tags=["Fiscal"])
def fiscal_cfop_atualizar(
    config_id: int,
    req: CfopConfigRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    if current_user.get("perfil", "").lower() not in ("admin", "gestor"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from database.models import FiscalCfopConfig
    from datetime import datetime as _dt
    row = db.query(FiscalCfopConfig).filter(FiscalCfopConfig.id == config_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    row.tipo_operacao      = req.tipo_operacao
    row.grupo_operacao     = req.grupo_operacao
    row.direcao            = req.direcao.upper()
    row.cfop_interno       = req.cfop_interno
    row.cfop_interestadual = req.cfop_interestadual
    row.natureza_padrao    = req.natureza_padrao
    row.ativo              = req.ativo
    row.atualizado_em      = _dt.now()
    db.commit()
    return {"mensagem": "Configuração CFOP atualizada."}


@app.delete("/api/v1/fiscal/cfop-config/{config_id}", tags=["Fiscal"])
def fiscal_cfop_deletar(
    config_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    if current_user.get("perfil", "").lower() not in ("admin", "gestor"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from database.models import FiscalCfopConfig
    row = db.query(FiscalCfopConfig).filter(FiscalCfopConfig.id == config_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    db.delete(row)
    db.commit()
    return {"mensagem": "Configuração CFOP removida."}


@app.post("/api/v1/fiscal/documentos/aprovar", tags=["Fiscal"])
def fiscal_documentos_aprovar(
    req: AprovarDocumentoFiscalRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "fiscal", "adm"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from services.documento_fiscal_service import DocumentoFiscalService
    ok, msg = DocumentoFiscalService.aprovar(
        db, req.doc_id, req.numero_nf, req.chave_acesso,
        req.protocolo_sefaz, current_user.get("sub", "sistema"),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


@app.post("/api/v1/fiscal/documentos/cancelar", tags=["Fiscal"])
def fiscal_documentos_cancelar(
    req: CancelarDocumentoFiscalRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "fiscal", "adm"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    from services.documento_fiscal_service import DocumentoFiscalService
    ok, msg = DocumentoFiscalService.cancelar(
        db, req.doc_id, req.motivo, current_user.get("sub", "sistema")
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


# ══════════════════════════════════════════════════════════════════════════════
# LOCALIZAÇÕES (Bin Addresses)
# ══════════════════════════════════════════════════════════════════════════════

class LocalizacaoCreateRequest(BaseModel):
    filial: str
    codigo: str
    descricao: str = ""
    zona: str = ""
    doca_polo: str = ""

class LocalizacaoUpdateRequest(BaseModel):
    descricao: str = ""
    zona: str = ""
    doca_polo: str = ""
    status: str = "ATIVO"

class AtribuirEnderecoRequest(BaseModel):
    item_id: int
    localizacao_id: int | None = None


@app.get("/api/v1/localizacoes", tags=["Localizações"])
def localizacoes_listar(
    filial: str = "",
    apenas_ativas: bool = True,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from services.localizacao_service import LocalizacaoService
    locs = LocalizacaoService.listar(db, filial=filial, apenas_ativas=apenas_ativas)
    return [LocalizacaoService.serializar(l) for l in locs]


@app.post("/api/v1/localizacoes", tags=["Localizações"])
def localizacoes_criar(
    req: LocalizacaoCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem criar localizações.")
    from services.localizacao_service import LocalizacaoService
    ok, msg, loc = LocalizacaoService.criar(db, req.dict(), current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return LocalizacaoService.serializar(loc)


@app.put("/api/v1/localizacoes/atribuir-endereco", tags=["Localizações"])
def localizacoes_atribuir(
    req: AtribuirEnderecoRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from services.localizacao_service import LocalizacaoService
    ok, msg = LocalizacaoService.atribuir_a_item(
        db, req.item_id, req.localizacao_id, current_user.get("sub", "sistema")
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


@app.put("/api/v1/localizacoes/{loc_id}", tags=["Localizações"])
def localizacoes_atualizar(
    loc_id: int,
    req: LocalizacaoUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem editar localizações.")
    from services.localizacao_service import LocalizacaoService
    ok, msg = LocalizacaoService.atualizar(db, loc_id, req.dict(), current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


@app.delete("/api/v1/localizacoes/{loc_id}", tags=["Localizações"])
def localizacoes_inativar(
    loc_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem inativar localizações.")
    from services.localizacao_service import LocalizacaoService
    ok, msg = LocalizacaoService.inativar(db, loc_id, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


# ══════════════════════════════════════════════════════════════════════════════
# ESTOQUE MÍNIMO / MÁXIMO
# ══════════════════════════════════════════════════════════════════════════════

class MinMaxSalvarRequest(BaseModel):
    produto_codigo: str
    filial: str = ""
    estoque_minimo: float = 0.0
    estoque_maximo: float = 0.0
    unidade_medida: str = "UN"
    ativo: int = 1
    observacao: str = ""


@app.get("/api/v1/estoque/minmax", tags=["Estoque Min/Max"])
def minmax_listar(
    produto_codigo: str = "",
    filial: str = "",
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from services.estoque_minmax_service import EstoqueMinMaxService
    return EstoqueMinMaxService.listar_com_status(db, produto_codigo=produto_codigo, filial=filial)


@app.post("/api/v1/estoque/minmax", tags=["Estoque Min/Max"])
def minmax_salvar(
    req: MinMaxSalvarRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem definir Min/Max.")
    from services.estoque_minmax_service import EstoqueMinMaxService
    ok, msg, mm = EstoqueMinMaxService.salvar(db, req.dict(), current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "id": mm.id}


@app.delete("/api/v1/estoque/minmax/{mm_id}", tags=["Estoque Min/Max"])
def minmax_excluir(
    mm_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem remover Min/Max.")
    from services.estoque_minmax_service import EstoqueMinMaxService
    ok, msg = EstoqueMinMaxService.excluir(db, mm_id, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"status": "sucesso", "mensagem": msg}


# ══════════════════════════════════════════════════════════════════════════════
# ESTOQUE DE SEGURANÇA
# ══════════════════════════════════════════════════════════════════════════════

class EstoqueSegurancaSalvarRequest(BaseModel):
    produto_codigo: str
    filial: str = ""
    controle_por_lote: int = 0
    controle_por_ativo: int = 0
    ativo: int = 1
    janela_historica_dias: int = 90
    lead_time_dias: int = 7
    nivel_de_servico: float = 0.95


@app.get("/api/v1/estoque/seguranca", tags=["Estoque Segurança"])
def seguranca_listar(
    produto_codigo: str = "",
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from services.estoque_seguranca_service import EstoqueSegurancaService
    from repositories.estoque_seguranca_repository import EstoqueSegurancaRepository
    repo = EstoqueSegurancaRepository()
    if produto_codigo:
        registros = repo.listar_por_produto(db, produto_codigo)
    else:
        registros = repo.listar_ativos(db)
    return [EstoqueSegurancaService.serializar(es) for es in registros]


@app.post("/api/v1/estoque/seguranca", tags=["Estoque Segurança"])
def seguranca_salvar(
    req: EstoqueSegurancaSalvarRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem configurar estoque de segurança.")
    from services.estoque_seguranca_service import EstoqueSegurancaService
    ok, msg, es = EstoqueSegurancaService.salvar(db, req.dict(), current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "id": es.id}


@app.post("/api/v1/estoque/seguranca/{es_id}/calcular", tags=["Estoque Segurança"])
def seguranca_calcular(
    es_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from services.estoque_seguranca_service import EstoqueSegurancaService
    ok, msg, valor = EstoqueSegurancaService.calcular(db, es_id, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "sucesso", "mensagem": msg, "estoque_seguranca": valor}


@app.delete("/api/v1/estoque/seguranca/{es_id}", tags=["Estoque Segurança"])
def seguranca_excluir(
    es_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    perfil = current_user.get("perfil", "").lower()
    if perfil not in ("admin", "gestor", "adm"):
        raise HTTPException(status_code=403, detail="Apenas Admin ou Gestor podem remover configurações.")
    from services.estoque_seguranca_service import EstoqueSegurancaService
    ok, msg = EstoqueSegurancaService.excluir(db, es_id, current_user.get("sub", "sistema"))
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"status": "sucesso", "mensagem": msg}
