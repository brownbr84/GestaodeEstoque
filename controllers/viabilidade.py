# tracebox/controllers/viabilidade.py

def calcular_viabilidade(valor_novo, idade_anos, vida_util_anos, custo_reparo):
    """
    Calcula a depreciação linear e retorna se o reparo é viável.
    Regra: Se o reparo custar mais de 50% do valor atual, é inviável.
    """
    # 1. Calcular Depreciação
    taxa_depreciacao_anual = valor_novo / vida_util_anos if vida_util_anos > 0 else 0
    depreciacao_acumulada = taxa_depreciacao_anual * idade_anos
    
    # 2. Valor Atual (Não pode ser menor que zero)
    valor_atual = valor_novo - depreciacao_acumulada
    if valor_atual < 0:
        valor_atual = 0.0

    # 3. Índice de Comprometimento (%)
    if valor_atual > 0:
        comprometimento = (custo_reparo / valor_atual) * 100
    else:
        # Se o valor atual é zero (totalmente depreciado), qualquer custo é 100%+ comprometedor
        comprometimento = 100.0 if custo_reparo > 0 else 0.0

    # 4. Veredito (Limiar de 50%)
    viavel = comprometimento <= 50.0

    return valor_atual, comprometimento, viavel