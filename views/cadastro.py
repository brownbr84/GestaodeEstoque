# tracebox/views/cadastro.py
import streamlit as st
import base64
from client.api_client import TraceBoxClient

def tela_cadastro_produtos():
    st.markdown("<h2>➕ Cadastro de <span style='color: #2563eb;'>Master Data</span></h2>", unsafe_allow_html=True)
    st.caption("Crie o modelo base das ferramentas ou consumíveis. O saldo físico e as TAGs serão incluídos no módulo Inbound.")

    usuario_atual = st.session_state['usuario_logado']['nome']

    config_atual = TraceBoxClient.get_config() or {}
    lista_categorias = config_atual.get('categorias_produto', [])
    if not lista_categorias: lista_categorias = ["Elétrica", "Mecânica", "Hidráulica", "EPI", "Insumos", "Outros"]
    
    lista_materiais = config_atual.get('tipos_material', [])
    if not lista_materiais: lista_materiais = ["Ativo", "Consumo"]
    
    lista_controles = config_atual.get('tipos_controle', [])
    if not lista_controles: lista_controles = ["TAG (Individual)", "Lote (Quantidade)"]

    with st.form("form_novo_produto", clear_on_submit=True):
        st.write("#### 📝 Informações Base do Produto")
        c1, c2 = st.columns([1, 2])
        with c1: codigo = st.text_input("Código SKU (ID Único) *", placeholder="Ex: PRD-005")
        with c2: descricao = st.text_input("Descrição Completa *", placeholder="Ex: Furadeira de Impacto 750W")

        c3, c4, c5 = st.columns(3)
        with c3: marca = st.text_input("Marca", placeholder="Ex: Bosch")
        with c4: modelo = st.text_input("Modelo / Part Number", placeholder="Ex: GSB 16 RE")
        with c5: categoria = st.selectbox("Categoria *", lista_categorias)

        st.write("---")
        st.write("#### 📐 Especificações Técnicas e Controle")
        c6, c7, c8, c9 = st.columns(4)
        with c6: dimensoes = st.text_input("Dimensões / Peso", placeholder="Ex: 2kg, 220V")
        with c7: capacidade = st.text_input("Capacidade / Vida Útil", placeholder="Ex: Mandril 1/2, 500h")
        with c8: tipo_material = st.selectbox("Classe Contábil *", lista_materiais)
        with c9: tipo_controle = st.selectbox("Controle de Estoque *", lista_controles)
        
        st.write("---")
        c10, c11 = st.columns([1, 2])
        with c10:
            valor = st.number_input("Valor Unitário Base (R$)", min_value=0.0, format="%.2f")
        with c11:
            imagem_file = st.file_uploader("📷 Foto do Produto (Opcional)", type=['png', 'jpg', 'jpeg'])

        st.write("---")
        st.write("#### 🧾 Dados Fiscais (NF-e)")
        st.caption("Preencha para agilizar a emissão de NF-e. Todos os campos são opcionais no cadastro.")
        cf1, cf2, cf3, cf4 = st.columns([2, 2, 2, 2])
        with cf1:
            ncm = st.text_input("NCM (8 dígitos)", placeholder="Ex: 84798999",
                                help="Nomenclatura Comum do Mercosul — obrigatório na NF-e")
        with cf2:
            c_ean = st.text_input("EAN / Código de Barras",
                                  placeholder="Ex: 7891234567890 ou SEM GTIN")
        with cf3:
            cest = st.text_input("CEST (7 dígitos)", placeholder="Ex: 2800100",
                                 help="Código Especificador da Substituição Tributária — obrigatório quando há ST")
        with cf4:
            orig_icms = st.selectbox(
                "Origem da Mercadoria (ICMS)",
                options=["0", "1", "2", "3", "4", "5", "6", "7", "8"],
                format_func=lambda x: {
                    "0": "0 - Nacional",
                    "1": "1 - Estrangeira (importação direta)",
                    "2": "2 - Estrangeira (adquirida no mercado interno)",
                    "3": "3 - Nacional c/ > 40% importado",
                    "4": "4 - Nacional (processos produtivos básicos)",
                    "5": "5 - Nacional c/ ≤ 40% importado",
                    "6": "6 - Estrangeira (importação direta, sem similar nacional)",
                    "7": "7 - Estrangeira (merc. interno, sem similar nacional)",
                    "8": "8 - Nacional - mercadoria ou bem com conteúdo de importação superior a 70%",
                }.get(x, x),
            )

        st.write("<br>", unsafe_allow_html=True)
        if st.form_submit_button("🚀 Criar Produto no Catálogo WMS", use_container_width=True, type="primary"):
            if not codigo or not descricao:
                st.error("⚠️ Os campos Código e Descrição são obrigatórios!")
            else:
                imagem_b64 = ""
                if imagem_file is not None:
                    bytes_da_imagem = imagem_file.getvalue()
                    if bytes_da_imagem:
                        imagem_b64 = base64.b64encode(bytes_da_imagem).decode('utf-8')

                payload = {
                    "codigo": codigo.strip(),
                    "descricao": descricao.strip(),
                    "marca": marca.strip(),
                    "modelo": modelo.strip(),
                    "categoria": categoria,
                    "dimensoes": dimensoes.strip(),
                    "capacidade": capacidade.strip(),
                    "valor_unitario": valor,
                    "tipo_material": tipo_material.split(" ")[0],
                    "tipo_controle": tipo_controle.split(" ")[0],
                    "imagem_b64": imagem_b64,
                    "usuario_atual": usuario_atual,
                    "ncm": ncm.strip(),
                    "c_ean": c_ean.strip() or "SEM GTIN",
                    "orig_icms": orig_icms,
                    "cest": cest.strip(),
                }
                
                sucesso, msg = TraceBoxClient.criar_produto(payload)
                
                if sucesso:
                    st.success(msg)
                else:
                    st.error(msg)