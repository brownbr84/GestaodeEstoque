# Validações de inventário e acuracidade
# tracebox/controllers/auditoria.py
from datetime import datetime
from database.queries import executar_query, carregar_dados  # <-- Adicionado carregar_dados

def processar_cruzamento_wms(polo, tags_bipadas, lotes_contados):
    """
    O Cérebro do WMS: Cruza o que o sistema espera com o que o operador bipou.
    Retorna a lista de resultados formatada para o 'processar_resultados_inventario'.
    """
    # 1. Busca a verdade do Banco de Dados
    query = "SELECT id, codigo, num_tag, quantidade FROM imobilizado WHERE localizacao = ? AND status IN ('Disponível', 'Manutenção')"
    df_esperado = carregar_dados(query, (polo,))
    
    resultados_finais = []
    divergencias = 0

    if df_esperado.empty:
        return resultados_finais, divergencias

    df_tags = df_esperado[df_esperado['num_tag'].notna() & (df_esperado['num_tag'] != '')]
    df_lotes = df_esperado[~(df_esperado['num_tag'].notna() & (df_esperado['num_tag'] != ''))]

    # 2. Avalia as TAGs bipadas vs esperadas
    for _, row in df_tags.iterrows():
        presente = row['num_tag'] in tags_bipadas
        if not presente: 
            divergencias += 1
            
        resultados_finais.append({
            'ids_originais': [row['id']],
            'qtd_sistema': 1,
            'qtd_fisica': 1 if presente else 0,
            # Justificativa automática (>4 caracteres) para passar na sua regra de negócio
            'justificativa': "Auditado OK via WMS" if presente else "Falta detectada via Leitor WMS",
            'is_lote': False
        })
    
    # 3. Avalia os Lotes Contados vs esperados
    if not df_lotes.empty:
        df_lotes_agg = df_lotes.groupby('codigo').agg({'quantidade': 'sum', 'id': lambda x: list(x)}).reset_index()
        for _, row in df_lotes_agg.iterrows():
            qtd_digitada = lotes_contados.get(row['codigo'], row['quantidade'])
            if qtd_digitada != row['quantidade']: 
                divergencias += 1
                
            resultados_finais.append({
                'ids_originais': row['id'], 
                'qtd_sistema': row['quantidade'],
                'qtd_fisica': qtd_digitada,
                'justificativa': "Contagem Física via WMS", # Justificativa automática
                'is_lote': True
            })

    return resultados_finais, divergencias


# MANTENHA A FUNÇÃO processar_cruzamento_wms INTACTA NO TOPO DO ARQUIVO!

def processar_resultados_inventario(resultados, usuario_atual, polo, inventario_id):
    """
    Recebe os resultados, aplica regras de negócio e carimba com o ID de Rastreabilidade.
    """
    erros = []
    agora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # 1. Validação de Regra de Negócio
    for res in resultados:
        if res['qtd_fisica'] != res['qtd_sistema'] and len(res['justificativa']) < 4:
            erros.append(f"Atenção: Justificativa obrigatória para divergência no item {res['ids_originais']}")
            
    if erros: return erros

    # 2. Processamento
    for res in resultados:
        qtd_fisica = res['qtd_fisica']
        qtd_sistema = res['qtd_sistema']
        
        # A. Lotes
        if res['is_lote'] and qtd_fisica != qtd_sistema:
            total_contado = qtd_fisica
            for i, id_origem in enumerate(res['ids_originais']):
                nova_qtd = total_contado if i == 0 else 0
                status_n = 'Disponível' if nova_qtd > 0 else 'Extraviado'
                executar_query("UPDATE imobilizado SET quantidade = ?, status = ? WHERE id = ?", (nova_qtd, status_n, id_origem))
        
        # B. Unitários
        elif not res['is_lote'] and qtd_fisica != qtd_sistema:
            status_t = 'Disponível' if qtd_fisica == 1 else 'Extraviado'
            executar_query("UPDATE imobilizado SET quantidade = ?, status = ? WHERE id = ?", (qtd_fisica, status_t, res['ids_originais'][0]))

        # 3. Log de Auditoria RASTREÁVEL
        tipo_log = "Auditoria Cíclica OK" if qtd_fisica == qtd_sistema else "Ajuste de Inventário"
        for id_log in (res['ids_originais'] if isinstance(res['ids_originais'], list) else [res['ids_originais']]):
            # AQUI ESTÁ A MÁGICA: O protocolo do inventário é injetado no log!
            msg = f"[{inventario_id}] Físico: {qtd_fisica}. Just: {res['justificativa']}"
            executar_query("INSERT INTO movimentacoes (ferramenta_id, tipo, responsavel, destino_projeto, documento) VALUES (?,?,?,?,?)", 
                          (id_log, tipo_log, usuario_atual, polo, msg))
            
    return erros