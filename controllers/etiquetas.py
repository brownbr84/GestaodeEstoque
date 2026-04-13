# tracebox/controllers/relatorios.py (podes colocar aqui ou num ficheiro novo controllers/etiquetas.py)
import qrcode
import io
import base64

def gerar_qr_base64(conteudo):
    """Gera um QR Code em memória e retorna como string base64."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(conteudo)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Certifique-se de que o import do banco de dados está no topo do arquivo:
# from database.queries import carregar_dados

def formatar_etiqueta_html(ativo_dados):
    """Gera o bloco HTML de uma etiqueta individual com a marca da empresa."""
    from database.queries import carregar_dados # Import local para segurança
    
    conteudo_qr = f"ID:{ativo_dados['id']}|COD:{ativo_dados['codigo']}|TAG:{ativo_dados['num_tag']}"
    qr_b64 = gerar_qr_base64(conteudo_qr)
    
    # 1. Busca a identidade visual no banco de dados
    df_config = carregar_dados("SELECT nome_empresa, logo_base64 FROM configuracoes WHERE id = 1")
    nome_empresa = "TRACEBOX"
    logo_html = ""
    
    if not df_config.empty:
        config = df_config.iloc[0]
        nome_empresa = config['nome_empresa']
        # Se houver um logo, renderiza uma miniatura dele na etiqueta
        if config['logo_base64']:
            logo_html = f'<img src="data:image/png;base64,{config["logo_base64"]}" style="max-height: 12px; margin-right: 4px; vertical-align: middle;">'
    
    # 2. Renderiza o HTML injetando a marca
    return f"""
    <div style="border: 1px solid #000; width: 280px; height: 140px; padding: 5px; font-family: 'Segoe UI', Arial; display: flex; background: white; color: black; margin: 5px; page-break-inside: avoid;">
        <div style="flex: 1; display: flex; align-items: center; justify-content: center;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 90px; height: 90px;">
        </div>
        <div style="flex: 1.5; padding-left: 5px; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 9px; font-weight: bold; border-bottom: 1px solid #000; margin-bottom: 3px; display: flex; align-items: center; height: 16px;">
                {logo_html}<span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px;">{nome_empresa.upper()}</span>
            </div>
            <div style="font-size: 13px; font-weight: bold; line-height: 1.1;">{ativo_dados['codigo']}</div>
            <div style="font-size: 10px; height: 24px; overflow: hidden;">{ativo_dados['descricao']}</div>
            <div style="font-size: 11px; margin-top: 4px; background: #000; color: #fff; padding: 2px; text-align: center; font-weight: bold;">
                TAG: {ativo_dados['num_tag'] if ativo_dados['num_tag'] else 'S/N'}
            </div>
            <div style="font-size: 8px; margin-top: 3px;">Polo: {ativo_dados['localizacao']}</div>
        </div>
    </div>
    """