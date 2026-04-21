import pytest
from database.models import Imobilizado
from services.outbound_service import OutboundService

def test_bloqueio_saldo_negativo(db_session):
    """
    TRAVA 1: Impede que o sistema processe uma baixa com quantidade superior ao saldo em estoque.
    """
    # 1. Preparação (Arrange): Criar um lote com 5 unidades
    lote = Imobilizado(
        codigo="TEST-123", descricao="Luva de Couro", quantidade=5, 
        status="Disponível", localizacao="Filial CTG", tipo_material="Consumo"
    )
    db_session.add(lote)
    db_session.commit()

    # 2. Ação (Act): Tentar baixar 10 unidades (5 a mais do que o permitido)
    carrinho = [{
        "id": lote.id,
        "codigo": "TEST-123",
        "tipo": "LOTE/CONSUMO",
        "qtd_baixar": 10
    }]
    
    sucesso, msg = OutboundService.realizar_baixa_excepcional(
        session=db_session,
        carrinho=carrinho,
        motivo="Perda na Obra",
        documento="DOC-001",
        usuario="Admin",
        polo="Filial CTG",
        perfil_usuario="ADMIN"
    )

    # 3. Validação (Assert)
    assert sucesso is False, "A trava de saldo negativo falhou e permitiu a baixa."
    assert "Saldo insuficiente" in msg, "A mensagem de erro de saldo deveria ter sido retornada."

    # Verifica se o banco manteve as 5 unidades (não comitou valor negativo)
    lote_banco = db_session.query(Imobilizado).filter_by(codigo="TEST-123").first()
    assert lote_banco.quantidade == 5, "O saldo foi reduzido indevidamente mesmo com a falha."

def test_trava_perfil_gestor(db_session):
    """
    TRAVA 2: Impede que um usuário com perfil Operador consiga fazer Baixa Excepcional.
    """
    carrinho = []
    sucesso, msg = OutboundService.realizar_baixa_excepcional(
        session=db_session,
        carrinho=carrinho,
        motivo="Ajuste",
        documento="DOC-002",
        usuario="João",
        polo="Filial CTG",
        perfil_usuario="OPERADOR"  # Perfil sem permissão
    )
    
    assert sucesso is False
    assert "Operação negada" in msg
    assert "administradores ou gestores" in msg
