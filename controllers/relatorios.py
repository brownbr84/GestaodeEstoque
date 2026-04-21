# tracebox/controllers/relatorios.py
import pandas as pd
from database.queries import carregar_dados
from datetime import datetime

def obter_lista_produtos():
    df = carregar_dados("SELECT DISTINCT codigo, descricao FROM imobilizado ORDER BY codigo")
    return df.apply(lambda r: f"{r['codigo']} - {r['descricao']}", axis=1).tolist() if not df.empty else []

def gerar_extrato_movimentacoes(codigo_produto, data_inicio, data_fim):
    codigo_puro = str(codigo_produto).split(" - ")[0].strip()
    query = """
        SELECT m.data_movimentacao, m.tipo as "Operação", i.num_tag as "TAG", i.quantidade as "Qtd_Transação",
               m.destino_projeto as "Origem/Destino", m.responsavel as "Usuário", m.documento as "Doc. Ref."
        FROM movimentacoes m JOIN imobilizado i ON m.ferramenta_id = i.id
        WHERE i.codigo = ? ORDER BY m.data_movimentacao ASC
    """
    df = carregar_dados(query, (codigo_puro,))
    
    if df.empty: return pd.DataFrame(columns=['Data', 'Operação', 'Movimento', 'Saldo Global', 'TAG', 'Origem/Destino', 'Usuário', 'Doc. Ref.']), codigo_puro

    saldo_atual = 0; saldos = []; sinais = []
    for _, row in df.iterrows():
        op = str(row['Operação']).lower()
        tem_tag = pd.notna(row['TAG']) and str(row['TAG']).strip() != ""
        qtd = 1 if tem_tag else int(row['Qtd_Transação'])

        if 'compra' in op or 'localizado' in op:
            saldo_atual += qtd; sinais.append(f"+ {qtd}")
        elif 'baixa' in op or 'extravio' in op or 'perda' in op or 'sucata' in op:
            saldo_atual -= qtd; sinais.append(f"- {qtd}")
        else:
            sinais.append(f"⮂ {qtd}")
        saldos.append(saldo_atual)

    df['Movimento'] = sinais; df['Saldo Global'] = saldos
    df['data_movimentacao'] = pd.to_datetime(df['data_movimentacao'], format='mixed', errors='coerce')
    mascara_data = (df['data_movimentacao'].dt.date >= data_inicio) & (df['data_movimentacao'].dt.date <= data_fim)
    df = df.loc[mascara_data].copy()

    if df.empty: return pd.DataFrame(columns=['Data', 'Operação', 'Movimento', 'Saldo Global', 'TAG', 'Origem/Destino', 'Usuário', 'Doc. Ref.']), codigo_puro

    df = df.sort_values(by='data_movimentacao', ascending=False)
    df['Data'] = df['data_movimentacao'].dt.strftime('%d/%m/%Y %H:%M')
    return df[['Data', 'Operação', 'Movimento', 'Saldo Global', 'TAG', 'Origem/Destino', 'Usuário', 'Doc. Ref.']].fillna(""), codigo_puro

def gerar_posicao_consolidada():
    query = """
        SELECT localizacao as polo, tipo_material as tipo, codigo, descricao,
               SUM(quantidade) as qtd_total, SUM(quantidade * valor_unitario) as valor_total
        FROM imobilizado WHERE status NOT IN ('Extraviado', 'Sucateado') AND quantidade > 0
        GROUP BY localizacao, tipo_material, codigo, descricao
        ORDER BY localizacao, tipo_material DESC, codigo
    """
    df = carregar_dados(query)
    if df.empty: return pd.DataFrame()

    linhas_relatorio = []; total_geral_qtd = 0; total_geral_valor = 0.0
    for polo, df_polo in df.groupby('polo', sort=False):
        subtotal_qtd = 0; subtotal_valor = 0.0
        for _, row in df_polo.iterrows():
            qtd = int(row['qtd_total']); valor = float(row['valor_total'])
            subtotal_qtd += qtd; subtotal_valor += valor
            linhas_relatorio.append({
                'Polo / Filial': row['polo'], 'Tipo': row['tipo'], 'Código': row['codigo'], 'Descrição': row['descricao'],
                'Qtd': str(qtd), 'Valor Total': f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            })
        total_geral_qtd += subtotal_qtd; total_geral_valor += subtotal_valor
        v_sub = f"R$ {subtotal_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas_relatorio.append({'Polo / Filial': f"<span style='color:#2563eb; font-weight:bold;'>↳ SUBTOTAL {polo}</span>", 'Tipo': "", 'Código': "", 'Descrição': "", 'Qtd': f"<span style='color:#2563eb; font-weight:bold;'>{subtotal_qtd}</span>", 'Valor Total': f"<span style='color:#2563eb; font-weight:bold;'>{v_sub}</span>"})

    v_tot = f"R$ {total_geral_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    linhas_relatorio.append({'Polo / Filial': "<span style='color:#0f172a; font-weight:bold; font-size:14px;'>🚀 TOTAL GERAL</span>", 'Tipo': "", 'Código': "", 'Descrição': "", 'Qtd': f"<span style='color:#0f172a; font-weight:bold; font-size:14px;'>{total_geral_qtd}</span>", 'Valor Total': f"<span style='color:#0f172a; font-weight:bold; font-size:14px;'>{v_tot}</span>"})
    return pd.DataFrame(linhas_relatorio)

# =========================================================
# NOVO MÓDULO: RELATÓRIO DE MANUTENÇÕES
# =========================================================

def gerar_relatorio_manutencao(data_inicio, data_fim, status_filtro):
    """Gera o relatório de OS da oficina com análise de depreciação e viabilidade real."""
    
    # IMPORTAÇÃO DA INTELIGÊNCIA DE DEPRECIAÇÃO
    from controllers.viabilidade import calcular_viabilidade
    
    try:
        query = """
            SELECT 
                mo.id as "OS",
                mo.data_entrada,
                to_char(mo.data_entrada, 'DD/MM/YYYY') as "Abertura",
                i.codigo as "Código",
                i.descricao as "Ferramenta",
                mo.status_ordem as "Status",
                COALESCE(mo.custo_reparo, 0) as custo_reparo,
                COALESCE(i.valor_unitario, 0) as valor_novo
            FROM manutencao_ordens mo
            JOIN imobilizado i ON mo.ferramenta_id = i.id
            ORDER BY mo.data_entrada DESC
        """
        df = carregar_dados(query)
        if df.empty: raise Exception("Base vazia")
    except:
        return pd.DataFrame(columns=['OS', 'Abertura', 'Código', 'Ferramenta', 'Status', 'Vlr. Manutenção', 'Índice %', 'Viabilidade'])

    # 1. Filtro de Data
    df['data_entrada'] = pd.to_datetime(df['data_entrada']).dt.date
    df = df[(df['data_entrada'] >= data_inicio) & (df['data_entrada'] <= data_fim)]

    # 2. Filtro de Status
    if status_filtro != "Todas":
        if status_filtro == "Em Aberto":
            df = df[df['Status'].isin(['Pendente', 'Em Andamento', 'Aguardando Peça', 'Aguardando Aprovação'])]
        elif status_filtro == "Realizadas/Concluídas":
            df = df[df['Status'] == 'Concluída']
        elif status_filtro == "Reprovadas":
            df = df[df['Status'] == 'Reprovada']

    if df.empty:
        return pd.DataFrame(columns=['OS', 'Abertura', 'Código', 'Ferramenta', 'Status', 'Vlr. Manutenção', 'Índice %', 'Viabilidade'])

    # 3. Regras de Negócio e Cálculos (Usando o Motor de Viabilidade Oficial)
    def processar_indicadores(row):
        custo = float(row['custo_reparo'])
        valor_novo = float(row['valor_novo'])
        
        if custo == 0: 
            return pd.Series(["-", "⏳ Aguardando Orçamento"])
        if valor_novo == 0: 
            return pd.Series(["-", "⚪ Sem Ref. de Preço"])
            
        # Usa a exata mesma função e parâmetros da tela views/manutencao.py
        v_atual, comp, viavel = calcular_viabilidade(valor_novo, 2, 5, custo)
        
        indice_formatado = f"{comp:.1f}%"
        
        if viavel:
            viabilidade_txt = f"<span style='color:green; font-weight:bold;'>🟢 Viável</span>"
        else:
            viabilidade_txt = f"<span style='color:red; font-weight:bold;'>🔴 Inviável</span>"
            
        return pd.Series([indice_formatado, viabilidade_txt])

    # Aplicamos a lógica
    df[['Índice %', 'Viabilidade']] = df.apply(processar_indicadores, axis=1)
    
    # 4. Formatação Final
    df['Vlr. Manutenção'] = df['custo_reparo'].apply(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x > 0 else "-"
    )
    
    def colorir_status(s):
        if 'Concluída' in s: return f"<span style='color:green;'>{s}</span>"
        if 'Reprovada' in s: return f"<span style='color:red;'>{s}</span>"
        if 'Aguardando Aprovação' in s: return f"<span style='color:blue;'>{s}</span>"
        return f"<span style='color:orange;'>{s}</span>"
        
    df['Status'] = df['Status'].apply(colorir_status)

    df = df[['OS', 'Abertura', 'Código', 'Ferramenta', 'Status', 'Vlr. Manutenção', 'Índice %', 'Viabilidade']]
    return df

def construir_html_impressao(titulo, usuario, filtros, df_dados):
    """O Motor de Renderização HTML para PDF (Agora White-label)."""
    from datetime import datetime
    data_atual = datetime.now().strftime('%d/%m/%Y às %H:%M')
    
    # 1. Puxa a Identidade da Empresa
    df_config = carregar_dados("SELECT nome_empresa, cnpj, logo_base64 FROM configuracoes WHERE id = 1")
    nome_empresa = "TraceBox Logística"
    cnpj_empresa = ""
    logo_html = ""
    
    if not df_config.empty:
        config = df_config.iloc[0]
        nome_empresa = config['nome_empresa']
        cnpj_empresa = f"<p style='margin: 0; font-size: 11px; color: #475569;'>CNPJ: {config['cnpj']}</p>" if config['cnpj'] else ""
        if config['logo_base64']:
            logo_html = f'<img src="data:image/png;base64,{config["logo_base64"]}" style="max-height: 60px;">'

    # 2. Constrói a tabela
    if df_dados.empty:
        tabela_html = "<p style='text-align: center; font-weight: bold; padding: 20px;'>Nenhum dado encontrado para os filtros informados.</p>"
    else:
        tabela_html = df_dados.to_html(index=False, classes="tabela-relatorio", justify="left", escape=False)

    # 3. Monta o Documento Final
    html_template = f"""
    <html><head><style>
        body {{ font-family: 'Segoe UI', sans-serif; color: black !important; background-color: white !important; padding: 15px; }}
        .tabela-relatorio {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 12px; }}
        .tabela-relatorio th, .tabela-relatorio td {{ border: 1px solid #cbd5e1; padding: 8px; text-align: left; }}
        .tabela-relatorio th {{ background-color: #f1f5f9; font-weight: bold; border-bottom: 2px solid #0f172a; text-transform: uppercase; }}
        .tabela-relatorio tr:nth-child(even) {{ background-color: #f8fafc; }}
        /* Novo layout do Cabeçalho com Flexbox */
        .cabecalho {{ border: 2px solid #0f172a; padding: 15px; margin-bottom: 20px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }}
        .cabecalho-info {{ flex: 1; }}
        .cabecalho-logo {{ text-align: right; margin-left: 20px; }}
        .linha-assinatura {{ display: flex; justify-content: space-between; margin-top: 40px; text-align: center; }}
        .linha-assinatura div {{ width: 45%; border-top: 1px solid #000; padding-top: 5px; }}
        @media print {{ #btn-imprimir {{ display: none; }} body {{ padding: 0; }} }}
    </style></head><body>
        <button id="btn-imprimir" onclick="window.print()" style="padding: 10px 20px; margin-bottom: 15px; background: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">🖨️ Imprimir Relatório (PDF)</button>
        
        <div class="cabecalho">
            <div class="cabecalho-info">
                <h2 style="margin: 0 0 10px 0; color: #0f172a;">{titulo}</h2>
                <p style="margin: 5px 0;"><strong>Emitido por:</strong> {usuario}</p>
                <p style="margin: 5px 0;"><strong>Data da Extração:</strong> {data_atual}</p>
                <p style="margin: 5px 0; color: #475569;"><em>{filtros}</em></p>
            </div>
            <div class="cabecalho-logo">
                {logo_html}
                <h3 style="margin: 5px 0 0 0; color: #0f172a;">{nome_empresa}</h3>
                {cnpj_empresa}
            </div>
        </div>
        
        {tabela_html}
        
        <div class="linha-assinatura">
            <div>Visto do Responsável (Emissor)</div>
            <div>Visto da Auditoria / Diretoria</div>
        </div>
    </body></html>
    """
    return html_template