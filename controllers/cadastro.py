# tracebox/controllers/cadastro.py
from database.conexao_orm import SessionLocal
from database.models import Imobilizado, Movimentacao
from repositories.imobilizado_repository import ImobilizadoRepository
from datetime import date, datetime

def cadastrar_novo_produto(codigo, descricao, marca, modelo, categoria, dimensoes, capacidade, valor_unit, tipo_material, tipo_controle, imagem_b64, usuario):
    with SessionLocal() as db:
        repo = ImobilizadoRepository()
        check = repo.get_by_codigo(db, codigo.upper())
        if check:
            return False, "Este código já existe no cadastro de Master Data."

        novo_item = Imobilizado(
            codigo=codigo.upper(),
            descricao=descricao,
            marca=marca,
            modelo=modelo,
            categoria=categoria,
            dimensoes=dimensoes,
            capacidade=capacidade,
            valor_unitario=valor_unit,
            tipo_material=tipo_material,
            tipo_controle=tipo_controle.upper(),
            imagem=imagem_b64,
            quantidade=0,
            localizacao='Geral/Catálogo',
            status='Catálogo',
            num_tag='',
            data_aquisicao=date.today()
        )
        
        repo.create(db, novo_item)
        
        mov = Movimentacao(
            ferramenta_id=novo_item.id,
            tipo='Criação Master Data',
            responsavel=usuario,
            destino_projeto='Sistema',
            documento='Setup Inicial',
            data_movimentacao=datetime.now()
        )
        db.add(mov)
        db.commit()
        
        return True, "Master Data cadastrado com sucesso! Produto pronto para receber estoque via Inbound."