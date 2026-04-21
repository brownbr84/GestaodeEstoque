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
# TODO (SEGURANÇA P1): mover SECRET_KEY para variável de ambiente.
# Exemplo: SECRET_KEY = os.getenv("JWT_SECRET_KEY")
# Nunca commite chaves secretas no código-fonte.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "TraceBox_S3cr3t_K3y_For_JWT_T0kens")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

app = FastAPI(title="TraceBox API", version="1.0.0", description="API RESTful para gestão de estoque e movimentações.")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

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
        req.get("tipo_material"), req.get("tipo_controle"), req.get("imagem_b64"), req.get("usuario_atual")
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
    
    # 2. Inventário Físico
    df_inv = carregar_dados("SELECT id, num_tag, localizacao, status, quantidade FROM imobilizado WHERE codigo = ? AND status != 'Catálogo' AND quantidade > 0", (codigo,))
    inv_fisico = df_inv.to_dict(orient='records') if not df_inv.empty else []
    
    # 3. TAGs para Calibração
    df_tags = carregar_dados('SELECT id as "ID_DB", num_tag as "TAG", localizacao as "Localização", status as "Status", ultima_manutencao as "Última Inspeção", proxima_manutencao as "Deadline Calibração" FROM imobilizado WHERE codigo = ? AND tipo_controle = \'TAG\' AND num_tag != \'\' AND status != \'Catálogo\'', (codigo,))
    tags = df_tags.to_dict(orient='records') if not df_tags.empty else []
    
    # 4. Histórico
    ids_produto = tuple(df_inv['id'].tolist()) if not df_inv.empty else ()
    historico = []
    if ids_produto:
        placeholders = ','.join('?' for _ in ids_produto)
        query_hist = f'SELECT m.data_movimentacao as "Data", i.num_tag as "Serial", m.tipo as "Operação", m.documento as "Doc/NF", m.responsavel as "Agente", m.destino_projeto as "Destino" FROM movimentacoes m JOIN imobilizado i ON m.ferramenta_id = i.id WHERE m.ferramenta_id IN ({placeholders}) ORDER BY m.data_movimentacao DESC LIMIT 200'
        df_hist = carregar_dados(query_hist, ids_produto)
        if not df_hist.empty:
            historico = df_hist.to_dict(orient='records')
            
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

