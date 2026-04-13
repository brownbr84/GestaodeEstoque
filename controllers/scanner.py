# tracebox/controllers/scanner.py
import streamlit as st
from database.queries import carregar_dados

def decodificar_leitura(codigo_bipado):
    """
    Recebe a string crua do leitor de código de barras.
    Se for uma etiqueta TraceBox (QR Code), extrai o código do produto.
    Se for digitação manual, retorna o que foi digitado.
    """
    if not codigo_bipado:
        return None
        
    codigo_alvo = codigo_bipado.strip()
    
    # Descasca a string do QR Code (ex: ID:1|COD:PRD-001|TAG:1001)
    if "COD:" in codigo_bipado:
        try:
            partes = codigo_bipado.split("|")
            for p in partes:
                if p.startswith("COD:"):
                    codigo_alvo = p.replace("COD:", "").strip()
                    break
        except:
            pass 
            
    return codigo_alvo

def renderizar_widget_scanner(chave="scanner_geral"):
    """
    Desenha o campo na tela e já devolve o código limpo e validado.
    """
    codigo_bipado = st.text_input(
        "📷 Scanner de Código de Barras / QR Code", 
        placeholder="Posicione o cursor aqui e acione o leitor...",
        key=chave
    )
    
    codigo_limpo = decodificar_leitura(codigo_bipado)
    
    # Se leu alguma coisa, verifica se o produto existe no banco
    if codigo_limpo:
        df_check = carregar_dados("SELECT descricao FROM imobilizado WHERE codigo = ? LIMIT 1", (codigo_limpo,))
        if not df_check.empty:
            st.success(f"✅ Lido: **{codigo_limpo}** - {df_check.iloc[0]['descricao']}")
            return codigo_limpo
        else:
            st.error(f"❌ Código '{codigo_limpo}' não localizado no banco de dados.")
            return None
            
    return None