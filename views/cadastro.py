# tracebox/views/cadastro.py
import streamlit as st

# Importa as ferramentas do controlador
from controllers.cadastro import obter_proximo_codigo, processar_commit_master_data

def tela_cadastro_produtos():
    st.title("🆕 Criação de Master Data")
    usuario_atual = st.session_state['usuario_logado']['nome']
    
    tipo_controle = st.radio("Regime de Traceabilidade", ["Lote Volumétrico (S/ Serial)", "Rastreabilidade Individual (TAG Obrigatória)"], horizontal=True)

    CATEGORIAS_OFICIAIS = ["Ferramentas Elétricas", "Ferramentas Manuais", "EPIs", "Consumíveis", "Máquinas Pesadas", "Outros"]
    LOCAIS_ESTOQUE = ["Filial CTG", "Filial ITJ", "Filial REC", "Filial SÃO", "Manutenção"]

    # TUDO O QUE ESTÁ ABAIXO DEVE FICAR DENTRO DESTE BLOCO (Recuado à direita)
    with st.form("form_cadastro", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            codigo_final = obter_proximo_codigo()
            st.text_input("ID TraceBox", value=codigo_final, disabled=True)
            descricao = st.text_input("Nomenclatura Oficial *")
            marca = st.text_input("Fabricante")
            modelo = st.text_input("Série / Modelo")
            tipo_material = st.selectbox("Classificação do Material", ["Ativo", "Consumo"], help="Ativos devem ser devolvidos. Consumo é gasto na obra.")
        
        with c2:
            categoria = st.selectbox("Família Lógica *", CATEGORIAS_OFICIAIS)
            valor = st.number_input("Custo de Implantação (R$)", min_value=0.0)
            capacidade = st.text_input("Carga Útil")
            dimensoes = st.text_input("Gabarito (L x A x P)")
        
        with c3:
            localizacao = st.selectbox("Pólo de Ancoragem *", LOCAIS_ESTOQUE)
            status = st.selectbox("Status", ["Disponível", "Manutenção"])
            data_aq = st.date_input("Data de Inserção")
            arquivo_foto = st.file_uploader("Upload de Imagem", type=["jpg", "png"])

        col_man1, col_man2 = st.columns(2)
        with col_man1: ultima_manutencao = st.text_input("Última Inspeção")
        with col_man2: proxima_manutencao = st.text_input("Deadline de Calibração (AAAA-MM-DD)")

        # Recriamos as colunas com segurança (Sem a Nota Fiscal)
        col_tag, col_qtd = st.columns([2, 1])
        
        with col_tag: 
            num_tags = st.text_area("Injetar Seriais (VÍRGULA)") if "Rastreabilidade" in tipo_controle else ""
        with col_qtd: 
            quantidade_lote = 1 if "Rastreabilidade" in tipo_controle else st.number_input("Carga Total", min_value=1, value=1)
        
        detalhes = st.text_area("Observações")

        # O BOTÃO ESTÁ AGORA DENTRO DO FORMULÁRIO CORRETAMENTE
        if st.form_submit_button("💾 Commit de Master Data", type="primary"):
            
            # 1. Validação Visual
            if not descricao.strip(): 
                st.error("⚠️ Nomenclatura Obrigatória")
                st.stop()
                
            if "Rastreabilidade" in tipo_controle and not num_tags.strip(): 
                st.error("⚠️ Injeção de serial falhou: Preencha as TAGs separadas por vírgula.")
                st.stop()

            # 2. Empacota os dados para enviar ao Controlador
            dados_form = {
                'tipo_controle': tipo_controle,
                'codigo_final': codigo_final,
                'descricao': descricao,
                'marca': marca,
                'modelo': modelo,
                'tipo_material': tipo_material,
                'categoria': categoria,
                'valor': valor,
                'capacidade': capacidade,
                'dimensoes': dimensoes,
                'localizacao': localizacao,
                'status': status,
                'data_aq': data_aq,
                'ultima_manutencao': ultima_manutencao,
                'proxima_manutencao': proxima_manutencao,
                'doc_entrada': "Entrada de Master Data", # Enviamos um texto padrão para não quebrar o banco
                'num_tags': num_tags,
                'quantidade_lote': quantidade_lote,
                'detalhes': detalhes
            }

            # 3. O Cérebro executa a ação!
            sucesso = processar_commit_master_data(dados_form, arquivo_foto, usuario_atual)

            if sucesso:
                st.success(f"✅ Commit Realizado! ID: {codigo_final}")
            else:
                st.error("❌ Erro ao processar dados no banco.")