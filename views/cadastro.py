# tracebox/views/cadastro.py
import streamlit as st
import base64
from controllers.cadastro import cadastrar_novo_produto

def tela_cadastro_produtos():
    st.markdown("<h2>➕ Cadastro de <span style='color: #2563eb;'>Master Data</span></h2>", unsafe_allow_html=True)
    st.caption("Crie o modelo base das ferramentas ou consumíveis. O saldo físico e as TAGs serão incluídos no módulo Inbound.")

    usuario_atual = st.session_state['usuario_logado']['nome']

    with st.form("form_novo_produto", clear_on_submit=True):
        st.write("#### 📝 Informações Base do Produto")
        c1, c2 = st.columns([1, 2])
        with c1: codigo = st.text_input("Código SKU (ID Único) *", placeholder="Ex: PRD-005")
        with c2: descricao = st.text_input("Descrição Completa *", placeholder="Ex: Furadeira de Impacto 750W")

        c3, c4, c5 = st.columns(3)
        with c3: marca = st.text_input("Marca", placeholder="Ex: Bosch")
        with c4: modelo = st.text_input("Modelo / Part Number", placeholder="Ex: GSB 16 RE")
        with c5: categoria = st.selectbox("Categoria *", ["Elétrica", "Mecânica", "Hidráulica", "EPI", "Insumos", "Outros"])

        st.write("---")
        st.write("#### 📐 Especificações Técnicas e Controle")
        c6, c7, c8, c9 = st.columns(4)
        with c6: dimensoes = st.text_input("Dimensões / Peso", placeholder="Ex: 2kg, 220V")
        with c7: capacidade = st.text_input("Capacidade / Vida Útil", placeholder="Ex: Mandril 1/2, 500h")
        with c8: tipo_material = st.selectbox("Classe Contábil *", ["Ativo", "Consumo"])
        with c9: tipo_controle = st.selectbox("Controle de Estoque *", ["TAG (Individual)", "Lote (Quantidade)"])
        
        st.write("---")
        c10, c11 = st.columns([1, 2])
        with c10: 
            valor = st.number_input("Valor Unitário Base (R$)", min_value=0.0, format="%.2f")
        with c11:
            imagem_file = st.file_uploader("📷 Foto do Produto (Opcional)", type=['png', 'jpg', 'jpeg'])

        st.write("<br>", unsafe_allow_html=True)
        if st.form_submit_button("🚀 Criar Produto no Catálogo WMS", use_container_width=True, type="primary"):
            if not codigo or not descricao:
                st.error("⚠️ Os campos Código e Descrição são obrigatórios!")
            else:
                # CORREÇÃO DA MEMÓRIA: Extração segura dos bytes usando getvalue()
                imagem_b64 = ""
                if imagem_file is not None:
                    bytes_da_imagem = imagem_file.getvalue()
                    if bytes_da_imagem:
                        imagem_b64 = base64.b64encode(bytes_da_imagem).decode('utf-8')

                sucesso, msg = cadastrar_novo_produto(
                    codigo.strip(), descricao.strip(), marca.strip(), modelo.strip(), 
                    categoria, dimensoes.strip(), capacidade.strip(), valor, 
                    tipo_material.split(" ")[0], tipo_controle.split(" ")[0], imagem_b64, usuario_atual
                )
                if sucesso:
                    st.success(msg)
                else:
                    st.error(msg)