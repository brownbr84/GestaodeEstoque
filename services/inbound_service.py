from sqlalchemy.orm import Session
from datetime import datetime
from database.models import Imobilizado, Movimentacao
from services.governance_service import GovernanceService
from repositories.imobilizado_repository import ImobilizadoRepository

imob_repo = ImobilizadoRepository()

class InboundService:
    @staticmethod
    def obter_proximas_tags(session: Session, qtd: int):
        tags = imob_repo.find_tags_like(session, 'TAG-')
        max_num = 1000
        if tags:
            nums = []
            for tag in tags:
                try:
                    n = int(tag.replace("TAG-", "").strip())
                    nums.append(n)
                except: pass
            if nums: max_num = max(nums)
        return [f"TAG-{max_num + i + 1}" for i in range(qtd)]

    @staticmethod
    def processar_entrada_compra(session: Session, codigo_produto: str, polo_destino: str, nf: str, valor_unit: float, quantidade: int, usuario: str):
        try:
            molde = imob_repo.get_by_codigo(session, codigo_produto)
            if not molde: return False, "Produto não encontrado.", []

            tipo_controle = str(molde.tipo_controle).upper() if molde.tipo_controle else ("TAG" if str(molde.tipo_material).upper() == 'ATIVO' else "LOTE")
            tags_geradas = []
            data_hoje = datetime.now().date()

            if tipo_controle == 'TAG':
                lista_tags = InboundService.obter_proximas_tags(session, quantidade)
                for tag in lista_tags:
                    novo = Imobilizado(codigo=molde.codigo, descricao=molde.descricao, marca=molde.marca, modelo=molde.modelo, categoria=molde.categoria, tipo_material=molde.tipo_material, tipo_controle=tipo_controle, num_tag=tag, quantidade=1, status='Disponível', localizacao=polo_destino, valor_unitario=valor_unit, data_aquisicao=data_hoje)
                    session.add(novo)
                    session.flush()
                    session.add(Movimentacao(ferramenta_id=novo.id, tipo='Entrada via Compra', responsavel=usuario, destino_projeto=polo_destino, documento=f"NF: {nf}", data_movimentacao=datetime.now()))
                    tags_geradas.append({'codigo': molde.codigo, 'descricao': molde.descricao, 'tag': tag})
            else:
                novo_lote = Imobilizado(codigo=molde.codigo, descricao=molde.descricao, quantidade=quantidade, status='Disponível', localizacao=polo_destino, valor_unitario=valor_unit, data_aquisicao=data_hoje, tipo_material=molde.tipo_material, tipo_controle=tipo_controle)
                session.add(novo_lote)
                session.flush()
                session.add(Movimentacao(ferramenta_id=novo_lote.id, tipo='Entrada via Compra', responsavel=usuario, destino_projeto=polo_destino, documento=f"NF: {nf}", data_movimentacao=datetime.now()))

            # 👉 O LOG DE AUDITORIA
            detalhes_log = f"Entrada de NF {nf}: {quantidade} un do produto {codigo_produto} para o polo {polo_destino}."
            GovernanceService.registar_log(session, usuario, 'imobilizado', 0, 'ENTRADA_COMPRA', detalhes_log)

            session.commit()
            return True, "Sucesso!", tags_geradas
            
        except Exception as e:
            session.rollback()
            return False, f"Erro BD: {str(e)}", []
    
    @staticmethod
    def obter_origens_esperadas(session: Session, polo_atual: str):
        # Busca obras em uso
        obras_db = imob_repo.get_in_use_locations(session)
        
        obras = [f"🏗️ Obra: {loc}" for loc in obras_db]
        
        # Verifica se há carga em trânsito para este polo
        qtd_transito = imob_repo.count_in_transit(session, polo_atual)
        
        if qtd_transito > 0:
            obras.insert(0, "🚚 Carga de Transferência")
            
        return obras

    @staticmethod
    def carregar_itens_esperados(session: Session, origem: str, polo: str):
        query = session.query(
            Imobilizado.id, Imobilizado.codigo, Imobilizado.descricao, 
            Imobilizado.num_tag, Imobilizado.quantidade, 
            Imobilizado.tipo_material, Imobilizado.tipo_controle
        ).filter(Imobilizado.quantidade > 0)

        if "Carga de Transferência" in origem:
            query = query.filter(Imobilizado.status == 'Em Trânsito', Imobilizado.localizacao == polo)
        else:
            nome_obra = origem.replace("🏗️ Obra: ", "").strip()
            query = query.filter(Imobilizado.status == 'Em Uso', Imobilizado.localizacao == nome_obra)

        resultados = query.all()
        return [row._asdict() for row in resultados]

    @staticmethod
    def processar_recebimento_doca(session: Session, origem: str, polo_atual: str, dict_ativos: dict, dict_lotes: dict, df_esperados, usuario: str):
        doc_ref = f"INB-{datetime.now().strftime('%H%M%S')}"
        houve_falta = False
        
        try:
            for _, row in df_esperados.iterrows():
                id_db = int(row['id'])
                qtd_esp = int(row['quantidade'])
                
                item = session.query(Imobilizado).filter(Imobilizado.id == id_db).first()
                if not item:
                    continue

                tipo_ctrl = str(item.tipo_controle).strip().upper() if item.tipo_controle else ""
                is_tag = (tipo_ctrl == 'TAG') if tipo_ctrl not in ('', 'NONE', 'NAN') else (str(item.tipo_material).strip().upper() == 'ATIVO')
                
                if is_tag:
                    tag = str(item.num_tag).upper()
                    if tag in dict_ativos:
                        status_q = dict_ativos[tag]['status_qualidade']
                        metodo = dict_ativos[tag].get('metodo', 'Sistema')
                        
                        item.localizacao = polo_atual
                        item.status = status_q
                        item.alerta_falta = 0
                        
                        doc_auditoria = f"{doc_ref} | {status_q} [Via {metodo}]"
                        mov = Movimentacao(ferramenta_id=item.id, tipo='Recebimento Inbound', responsavel=usuario, destino_projeto=polo_atual, documento=doc_auditoria, data_movimentacao=datetime.now())
                        session.add(mov)
                    else:
                        houve_falta = True
                        item.alerta_falta = 1
                else:
                    if id_db in dict_lotes:
                        dl = dict_lotes[id_db]
                        total_rec = dl['disponivel'] + dl['manutencao'] + dl['sucata']
                        
                        if total_rec < qtd_esp:
                            houve_falta = True
                            item.quantidade = qtd_esp - total_rec
                            item.alerta_falta = 1
                        else:
                            item.quantidade = 0
                            item.alerta_falta = 0
                        
                        for qtd, stat in [(dl['disponivel'], 'Disponível'), (dl['manutencao'], 'Manutenção'), (dl['sucata'], 'Sucateado')]:
                            if qtd > 0:
                                novo_lote = Imobilizado(
                                    codigo=item.codigo, descricao=item.descricao, marca=item.marca, modelo=item.modelo,
                                    quantidade=qtd, status=stat, localizacao=polo_atual, categoria=item.categoria,
                                    valor_unitario=item.valor_unitario, tipo_material=item.tipo_material, 
                                    tipo_controle=item.tipo_controle, alerta_falta=0, data_aquisicao=item.data_aquisicao
                                )
                                session.add(novo_lote)
                                session.flush()
                                
                                session.add(Movimentacao(ferramenta_id=novo_lote.id, tipo='Recebimento Lote', responsavel=usuario, destino_projeto=polo_atual, documento=f"{doc_ref} | {stat}", data_movimentacao=datetime.now()))
                    else:
                        houve_falta = True
                        item.alerta_falta = 1

            # 👉 REGISTO DE AUDITORIA: Recebimento de Carga
            detalhes_log = f"Recebimento de carga vinda de {origem} no polo {polo_atual}."
            GovernanceService.registar_log(session, usuario, 'imobilizado', 0, 'RECEBIMENTO_DOCA', detalhes_log)

            session.commit()
            msg = "⚠️ Recebimento PARCIAL! Faltas enviadas para a Malha Fina." if houve_falta else "✅ Recebimento TOTAL concluído!"
            return True, msg, houve_falta

        except Exception as e:
            session.rollback()
            return False, f"Erro ao processar doca: {str(e)}", False


    @staticmethod
    def processar_reintegracao_falta(session: Session, id_db: int, qtd_enc: int, qtd_pendente: int, destino: str, usuario: str):
        try:
            item = session.query(Imobilizado).filter(Imobilizado.id == id_db).first()
            if not item:
                raise ValueError("Item não encontrado no banco de dados.")

            if qtd_enc == qtd_pendente:
                item.localizacao = destino
                item.status = 'Disponível'
                item.alerta_falta = 0
                ferramenta_log_id = item.id
            else:
                item.quantidade -= qtd_enc
                
                novo_item = Imobilizado(
                    codigo=item.codigo, descricao=item.descricao, num_tag=item.num_tag,
                    quantidade=qtd_enc, status='Disponível', localizacao=destino, alerta_falta=0, 
                    tipo_material=item.tipo_material, tipo_controle=item.tipo_controle,
                    marca=item.marca, modelo=item.modelo, categoria=item.categoria, valor_unitario=item.valor_unitario
                )
                session.add(novo_item)
                session.flush()
                ferramenta_log_id = novo_item.id

            mov = Movimentacao(
                ferramenta_id=ferramenta_log_id, tipo='Material Localizado', 
                responsavel=usuario, destino_projeto=destino, 
                documento='Reintegração', data_movimentacao=datetime.now()
            )
            session.add(mov)

            # 👉 REGISTO DE AUDITORIA
            detalhes_log = f"Reintegração de {qtd_enc} un (ID original: {id_db}) localizada e enviada para {destino}."
            GovernanceService.registar_log(session, usuario, 'imobilizado', id_db, 'REINTEGRACAO_MALHA', detalhes_log)

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            print(f"Erro na reintegração: {e}")
            return False

    @staticmethod
    def realizar_entrada_excepcional(session: Session, carrinho: list, motivo: str, documento: str, usuario: str, polo: str, perfil_usuario: str = "Operador"):
        try:
            if perfil_usuario.upper() not in ["ADMIN", "ADM", "GESTOR"]:
                return False, "Operação negada: apenas Administradores ou Gestores podem realizar entradas excepcionais.", []
            agora = datetime.now()
            tipo_mov = f"Entrada Excepcional - {motivo}"
            doc_ref = f"{documento} | ENT-{agora.strftime('%H%M%S')}"
            tags_geradas = []

            for item in carrinho:
                molde = imob_repo.get_by_codigo(session, item['codigo'])
                if not molde:
                    continue

                tipo_controle = str(molde.tipo_controle).upper() if molde.tipo_controle else ("TAG" if str(molde.tipo_material).upper() == 'ATIVO' else "LOTE")

                if tipo_controle == 'TAG':
                    lista_tags = InboundService.obter_proximas_tags(session, int(item['qtd']))
                    for tag in lista_tags:
                        novo = Imobilizado(
                            codigo=molde.codigo, descricao=molde.descricao, marca=molde.marca,
                            modelo=molde.modelo, categoria=molde.categoria, tipo_material=molde.tipo_material,
                            tipo_controle=tipo_controle, num_tag=tag, quantidade=1,
                            status='Disponível', localizacao=polo,
                            valor_unitario=float(item.get('valor', 0)), data_aquisicao=agora.date()
                        )
                        session.add(novo)
                        session.flush()
                        session.add(Movimentacao(
                            ferramenta_id=novo.id, tipo=tipo_mov, responsavel=usuario,
                            destino_projeto=polo, documento=doc_ref, data_movimentacao=agora
                        ))
                        tags_geradas.append({'codigo': molde.codigo, 'descricao': molde.descricao, 'tag': tag, 'tipo': 'Ativo'})
                else:
                    novo_lote = Imobilizado(
                        codigo=molde.codigo, descricao=molde.descricao, quantidade=int(item['qtd']),
                        status='Disponível', localizacao=polo,
                        valor_unitario=float(item.get('valor', 0)), data_aquisicao=agora.date(),
                        tipo_material=molde.tipo_material, tipo_controle=tipo_controle
                    )
                    session.add(novo_lote)
                    session.flush()
                    session.add(Movimentacao(
                        ferramenta_id=novo_lote.id, tipo=tipo_mov, responsavel=usuario,
                        destino_projeto=polo, documento=doc_ref, data_movimentacao=agora
                    ))
                    tags_geradas.append({'codigo': molde.codigo, 'descricao': molde.descricao, 'tag': 'LOTE / CAIXA', 'tipo': 'Consumo'})

            detalhes_log = f"Entrada Excepcional no polo {polo}. Motivo: {motivo}. Documento: {doc_ref}"
            GovernanceService.registar_log(session, usuario, 'imobilizado', 0, 'ENTRADA_EXCEPCIONAL', detalhes_log)

            session.commit()
            return True, "✅ Entrada Excepcional registada e auditada com sucesso!", tags_geradas
        except Exception as e:
            session.rollback()
            return False, f"Erro no banco de dados: {str(e)}", []

    @staticmethod
    def processar_baixa_extravio(session: Session, id_db: int, qtd_perda: int, qtd_pendente: int, origem: str, motivo: str, usuario: str):
        try:
            item = session.query(Imobilizado).filter(Imobilizado.id == id_db).first()
            if not item:
                raise ValueError("Item não encontrado no banco de dados.")

            local_ext = f"Extravio: {origem}"
            
            if qtd_perda == qtd_pendente:
                item.status = 'Extraviado'
                item.localizacao = local_ext
                item.alerta_falta = 0
                ferramenta_log_id = item.id
            else:
                item.quantidade -= qtd_perda
                
                novo_item = Imobilizado(
                    codigo=item.codigo, descricao=item.descricao, num_tag=item.num_tag,
                    quantidade=qtd_perda, status='Extraviado', localizacao=local_ext, alerta_falta=0, 
                    tipo_material=item.tipo_material, tipo_controle=item.tipo_controle,
                    marca=item.marca, modelo=item.modelo, categoria=item.categoria, valor_unitario=item.valor_unitario
                )
                session.add(novo_item)
                session.flush()
                ferramenta_log_id = novo_item.id

            mov = Movimentacao(
                ferramenta_id=ferramenta_log_id, tipo='Baixa por Perda', 
                responsavel=usuario, destino_projeto=local_ext, 
                documento=motivo, data_movimentacao=datetime.now()
            )
            session.add(mov)

            # 👉 REGISTO DE AUDITORIA
            detalhes_log = f"Baixa por extravio confirmada para {qtd_perda} un (ID: {id_db}). Motivo: {motivo}"
            GovernanceService.registar_log(session, usuario, 'imobilizado', id_db, 'EXTRAVIO_MALHA', detalhes_log)

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            print(f"Erro na baixa por extravio: {e}")
            return False