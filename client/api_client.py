import requests
import os
from typing import Dict, Any, Optional

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

import streamlit as st

@st.cache_data(ttl=15, show_spinner=False)
def _cached_get(url: str, token: str):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None

class TraceBoxClient:
    
    @staticmethod
    def _get_headers() -> Dict[str, str]:
        import streamlit as st
        token = ""
        if 'usuario_logado' in st.session_state and isinstance(st.session_state['usuario_logado'], dict):
            token = st.session_state['usuario_logado'].get('access_token', '')
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}
    
    @staticmethod
    def login(usuario: str, senha: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"usuario": usuario, "senha": senha},
                timeout=30   # aumentado: bcrypt pode demorar no primeiro rehash
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code in [200, 201]:
                _cached_get.clear()
            return None
        except requests.RequestException:
            return None

    @staticmethod

    def get_config() -> Optional[Dict[str, Any]]:
        token = st.session_state.get("usuario_logado", {}).get("access_token", "")
        return _cached_get(f"{API_BASE_URL}/configuracoes", token)

    @staticmethod
    def update_config(**kwargs) -> bool:
        try:
            response = requests.put(
                f"{API_BASE_URL}/configuracoes",
                json=kwargs,
                headers=TraceBoxClient._get_headers(), timeout=5
            )
            if response.status_code in [200, 201]:
                _cached_get.clear()
            return response.status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def get_me(token: str) -> Optional[Dict[str, Any]]:
        """Valida um token e retorna os dados do usuário — usado para restaurar sessão após F5."""
        try:
            res = requests.get(
                f"{API_BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if res.status_code == 200:
                return res.json()
            return None
        except requests.RequestException:
            return None

    @staticmethod

    def get_dashboard_metrics() -> Optional[Dict[str, Any]]:
        token = st.session_state.get("usuario_logado", {}).get("access_token", "")
        return _cached_get(f"{API_BASE_URL}/dashboard/metricas", token)

    @staticmethod
    def criar_produto(dados: Dict[str, Any]) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/produtos", json=dados, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Criado com sucesso")
            return False, res.json().get("detail", "Erro na API")
        except requests.RequestException as e:
            return False, f"Erro de conexão com a API: {str(e)}"

    @staticmethod
    def get_produto_detalhes(codigo: str) -> Optional[Dict[str, Any]]:
        try:
            res = requests.get(f"{API_BASE_URL}/produtos/{codigo}/detalhes", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json()
            return None
        except requests.RequestException:
            return None

    @staticmethod
    def update_produto_mestre(codigo: str, dados: Dict[str, Any]) -> bool:
        try:
            res = requests.put(f"{API_BASE_URL}/produtos/{codigo}/mestre", json=dados, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def update_produto_calibracao(codigo: str, itens: list, usuario: str) -> tuple[bool, str]:
        try:
            res = requests.put(f"{API_BASE_URL}/produtos/{codigo}/calibracao", json={"itens": itens, "usuario": usuario}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Atualizado com sucesso")
            return False, res.json().get("detail", "Erro na API")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod

    def get_fila_pedidos(polo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/outbound/pedidos", params={"polo": polo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json()
            return []
        except requests.RequestException:
            return []

    @staticmethod
    def cancelar_pedido(true_id: int, req_id: int, motivo: str, usuario: str) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/outbound/pedidos/cancelar", json={
                "true_id": int(true_id), "req_id": int(req_id), "motivo": motivo, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Cancelado com sucesso")
            return False, res.json().get("detail", "Erro na API")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod

    def get_detalhes_picking(req_id: int, polo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/outbound/pedidos/{req_id}/picking", params={"polo": polo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json()
            return []
        except requests.RequestException:
            return []

    @staticmethod
    def obter_tags_disponiveis(codigo: str, polo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/outbound/tags", params={"codigo": codigo, "polo": polo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json().get("tags", [])
            return []
        except requests.RequestException:
            return []

    @staticmethod
    def despachar_pedido_wms(true_id: int, req_id: int, polo: str, destino: str, dict_tags_final: dict, dict_lotes_final: dict, df_itens_json: list, usuario: str) -> tuple[bool, str, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/outbound/pedidos/despachar", json={
                "true_id": true_id, "req_id": req_id, "polo": polo, "destino": destino,
                "dict_tags_final": dict_tags_final, "dict_lotes_final": dict_lotes_final,
                "df_itens_json": df_itens_json, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=30)
            if res.status_code == 200:
                return True, res.json().get("documento"), res.json().get("mensagem")
            return False, "", res.json().get("detail", "Erro na API")
        except requests.RequestException as e:
            return False, "", str(e)

    @staticmethod
    def listar_itens_em_transito(polo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/outbound/transito", params={"polo": polo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json()
            return []
        except requests.RequestException:
            return []

    # ==========================================
    # INBOUND / RECEBIMENTO
    # ==========================================
    @staticmethod
    def processar_entrada_compra(codigo_produto: str, polo_destino: str, nf: str, valor_unit: float, quantidade: int, usuario: str) -> tuple[bool, str, list]:
        try:
            res = requests.post(f"{API_BASE_URL}/inbound/compras", json={
                "codigo_produto": codigo_produto, "polo_destino": polo_destino, "nf": nf,
                "valor_unit": valor_unit, "quantidade": quantidade, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("status"), data.get("mensagem"), data.get("tags_novas", [])
            return False, "Erro na API de Compras", []
        except requests.RequestException as e:
            return False, str(e), []

    @staticmethod
    def obter_origens_esperadas(polo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/inbound/doca/origens", params={"polo": polo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json().get("origens", [])
            return []
        except requests.RequestException:
            return []

    @staticmethod
    def carregar_itens_esperados(origem: str, polo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/inbound/doca/esperados", params={"origem": origem, "polo": polo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return res.json()
            return []
        except requests.RequestException:
            return []

    @staticmethod
    def processar_recebimento_doca(origem: str, polo_atual: str, dict_ativos: dict, dict_lotes: dict, df_esperados_json: list, usuario: str) -> tuple[bool, str, bool]:
        try:
            res = requests.post(f"{API_BASE_URL}/inbound/doca/receber", json={
                "origem": origem, "polo_atual": polo_atual, "dict_ativos": dict_ativos,
                "dict_lotes": dict_lotes, "df_esperados_json": df_esperados_json, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data.get("status"), data.get("mensagem"), data.get("alerta", False)
            return False, "Erro na API de Doca", False
        except requests.RequestException as e:
            return False, str(e), False

    @staticmethod
    def processar_reintegracao_falta(id_db: int, qtd_enc: int, qtd_pendente: int, destino: str, usuario: str) -> bool:
        try:
            res = requests.post(f"{API_BASE_URL}/inbound/malha-fina/reintegrar", json={
                "id_db": id_db, "qtd_enc": qtd_enc, "qtd_pendente": qtd_pendente, "destino": destino, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def processar_baixa_extravio(id_db: int, qtd_perda: int, qtd_pendente: int, origem: str, motivo: str, usuario: str) -> bool:
        try:
            res = requests.post(f"{API_BASE_URL}/inbound/malha-fina/extravio", json={
                "id_db": id_db, "qtd_perda": qtd_perda, "qtd_pendente": qtd_pendente, "origem": origem, "motivo": motivo, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def reativar_tag_extraviada(tag: str, polo: str, motivo: str, usuario: str) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/auditoria/reativar", json={
                "tag": tag, "polo": polo, "motivo": motivo, "usuario": usuario
            }, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data.get("status"), data.get("mensagem")
            return False, "Erro na API de Auditoria"
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod

    def get_catalogo_simples() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/imobilizado/catalogo/simples", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod

    def get_malha_fina_faltas() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/inbound/malha-fina/faltas", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # INVENTÁRIO CÍCLICO
    # ==========================================
    @staticmethod
    def inventario_esperado(polo: str, classificacao: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/inventario/esperado", params={"polo": polo, "classificacao": classificacao}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def processar_cruzamento_wms(polo: str, tags_bipadas: set, lotes_contados: dict) -> tuple[list, int]:
        try:
            res = requests.post(f"{API_BASE_URL}/inventario/cruzamento", json={
                "polo": polo, "tags_bipadas": list(tags_bipadas), "lotes_contados": lotes_contados
            }, headers=TraceBoxClient._get_headers(), timeout=30)
            if res.status_code == 200:
                d = res.json()
                return d.get("resultados_finais", []), d.get("divergencias", 0)
            return [], 0
        except requests.RequestException: return [], 0

    @staticmethod
    def processar_resultados_inventario(resultados_finais: list, usuario: str, polo: str, inv_id: str) -> list:
        try:
            res = requests.post(f"{API_BASE_URL}/inventario/processar", json={
                "resultados_finais": resultados_finais, "usuario": usuario, "polo": polo, "inv_id": inv_id
            }, headers=TraceBoxClient._get_headers(), timeout=30)
            if res.status_code == 200:
                return res.json().get("erros", [])
            return ["Erro na API de processamento do inventário."]
        except requests.RequestException as e: return [str(e)]

    # ==========================================
    # REQUISIÇÃO
    # ==========================================
    @staticmethod
    def obter_catalogo_disponivel_req(polo_alvo: str, carrinho_req: list, tipo_filtro: str) -> list:
        try:
            res = requests.post(f"{API_BASE_URL}/requisicao/catalogo", json={"polo_alvo": polo_alvo, "carrinho_req": carrinho_req, "tipo_filtro": tipo_filtro}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def salvar_nova_requisicao(polo_alvo: str, projeto: str, solicitante: str, df_carrinho: list) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/requisicao/salvar", json={"polo_alvo": polo_alvo, "projeto": projeto, "solicitante": solicitante, "df_carrinho": df_carrinho}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                d = res.json()
                return d.get("status"), d.get("mensagem")
            return False, "Erro na API de Requisição."
        except requests.RequestException as e: return False, str(e)

    @staticmethod
    def listar_historico_solicitante(usuario: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/requisicao/historico", params={"usuario": usuario}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def listar_itens_da_requisicao(req_id: int) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/requisicao/{req_id}/itens", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # MANUTENÇÃO
    # ==========================================
    @staticmethod
    def carregar_ativos_para_manutencao() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/manutencao/ativos", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def abrir_ordem_manutencao(ferramenta_id: int, codigo: str, motivo: str, solicitante: str, usuario: str) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/manutencao/abrir", json={"ferramenta_id": ferramenta_id, "codigo": codigo, "motivo": motivo, "solicitante": solicitante, "usuario": usuario}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                d = res.json()
                return d.get("status"), d.get("mensagem")
            return False, "Erro na API de Manutenção."
        except requests.RequestException as e: return False, str(e)

    @staticmethod
    def carregar_ordens_abertas() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/manutencao/abertas", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def lancar_orcamento_oficina(ordem_id: int, diagnostico: str, custo: float, mecanico: str, empresa: str, num_orcamento: str, usuario: str) -> bool:
        try:
            res = requests.post(f"{API_BASE_URL}/manutencao/orcamento", json={"ordem_id": ordem_id, "diagnostico": diagnostico, "custo": custo, "mecanico": mecanico, "empresa": empresa, "num_orcamento": num_orcamento, "usuario": usuario}, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.status_code == 200
        except requests.RequestException: return False

    @staticmethod
    def carregar_ordens_aprovacao() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/manutencao/aprovacao", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def aprovar_manutencao(ordem_id: int, decisao: str, usuario: str) -> bool:
        try:
            res = requests.post(f"{API_BASE_URL}/manutencao/aprovar", json={"ordem_id": ordem_id, "decisao": decisao, "usuario": usuario}, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.status_code == 200
        except requests.RequestException: return False

    @staticmethod
    def carregar_ordens_execucao() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/manutencao/execucao", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def finalizar_reparo_oficina(ordem_id: int, ferramenta_id: int, destino: str, usuario: str) -> bool:
        try:
            res = requests.post(f"{API_BASE_URL}/manutencao/finalizar", json={"ordem_id": ordem_id, "ferramenta_id": ferramenta_id, "destino": destino, "usuario": usuario}, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.status_code == 200
        except requests.RequestException: return False

    @staticmethod
    def carregar_historico_concluidas(ferramenta_id: int) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/manutencao/historico/{ferramenta_id}", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # MATRIZ FÍSICA
    # ==========================================
    @staticmethod
    def matriz_fisica_checar(codigo: str) -> bool:
        try:
            res = requests.get(f"{API_BASE_URL}/matriz-fisica/checar-codigo", params={"codigo": codigo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json().get("encontrado", False)
            return False
        except requests.RequestException: return False

    @staticmethod
    def matriz_fisica_raw() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/matriz-fisica/raw", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # ETIQUETAS
    # ==========================================
    @staticmethod
    def etiquetas_produtos(tipo_material: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/etiquetas/produtos", params={"tipo_material": tipo_material}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def etiquetas_inventario(codigo: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/etiquetas/inventario", params={"codigo": codigo}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # RELATÓRIOS
    # ==========================================
    @staticmethod
    def relatorios_produtos() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/relatorios/produtos", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json().get("produtos", [])
            return []
        except requests.RequestException: return []

    @staticmethod
    def relatorios_extrato(produto: str, inicio: str, fim: str) -> tuple[list, str]:
        try:
            res = requests.get(f"{API_BASE_URL}/relatorios/extrato", params={"produto": produto, "inicio": inicio, "fim": fim}, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                d = res.json()
                return d.get("dados", []), d.get("codigo", "")
            return [], ""
        except requests.RequestException: return [], ""

    @staticmethod
    def relatorios_posicao() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/relatorios/posicao", headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def relatorios_manutencao(inicio: str, fim: str, status: str) -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/relatorios/manutencao", params={"inicio": inicio, "fim": fim, "status": status}, headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # AUDITORIA
    # ==========================================
    @staticmethod
    def auditoria_logs(filtro_acao: str, filtro_usuario: str, filtro_data: str) -> list:
        try:
            res = requests.post(f"{API_BASE_URL}/auditoria/logs", json={
                "filtro_acao": filtro_acao, "filtro_usuario": filtro_usuario, "filtro_data": filtro_data
            }, headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    # ==========================================
    # GESTÃO DE USUÁRIOS
    # ==========================================
    @staticmethod
    def listar_usuarios() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/usuarios", headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200: return res.json()
            return []
        except requests.RequestException: return []

    @staticmethod
    def criar_usuario(nome: str, usuario: str, senha: str, perfil: str, email: str = "") -> tuple:
        try:
            res = requests.post(f"{API_BASE_URL}/usuarios",
                json={"nome": nome, "usuario": usuario, "senha": senha, "perfil": perfil, "email": email},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Usuario criado")
            return False, res.json().get("detail", "Erro ao criar usuario")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def alterar_senha_usuario(usuario_alvo: str, nova_senha: str) -> tuple:
        try:
            res = requests.put(f"{API_BASE_URL}/usuarios/senha",
                json={"usuario_alvo": usuario_alvo, "nova_senha": nova_senha},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Senha alterada")
            return False, res.json().get("detail", "Erro ao alterar senha")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def excluir_usuario(usuario_alvo: str) -> tuple:
        try:
            res = requests.delete(f"{API_BASE_URL}/usuarios/{usuario_alvo}",
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Usuario removido")
            return False, res.json().get("detail", "Erro ao excluir usuario")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def atualizar_email_usuario(usuario_alvo: str, email: str) -> tuple:
        try:
            res = requests.put(f"{API_BASE_URL}/usuarios/email",
                json={"usuario_alvo": usuario_alvo, "email": email},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "E-mail atualizado")
            return False, res.json().get("detail", "Erro ao atualizar e-mail")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def solicitar_recuperacao_senha(usuario: str, email: str) -> tuple:
        try:
            res = requests.post(f"{API_BASE_URL}/auth/recuperar-senha",
                json={"usuario": usuario, "email": email}, timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Código enviado")
            return False, res.json().get("detail", "Usuário ou e-mail não encontrado")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def confirmar_recuperacao_senha(usuario: str, codigo: str, nova_senha: str) -> tuple:
        try:
            res = requests.post(f"{API_BASE_URL}/auth/confirmar-recuperacao",
                json={"usuario": usuario, "codigo": codigo, "nova_senha": nova_senha}, timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Senha redefinida com sucesso")
            return False, res.json().get("detail", "Código inválido ou expirado")
        except requests.RequestException as e:
            return False, str(e)

    # ==========================================
    # MÓDULO FISCAL
    # ==========================================

    @staticmethod
    def preparar_nf(tipo_operacao: str, dados_mercadoria: list, dados_destinatario_remetente: dict, numero_nf_ref: str = "") -> dict:
        try:
            res = requests.post(f"{API_BASE_URL}/fiscal/preparar",
                json={"tipo_operacao": tipo_operacao, "dados_mercadoria": dados_mercadoria,
                      "dados_destinatario_remetente": dados_destinatario_remetente, "numero_nf_ref": numero_nf_ref},
                headers=TraceBoxClient._get_headers(), timeout=15)
            return res.json()
        except requests.RequestException as e:
            return {"sucesso": False, "mensagem": str(e), "api_gratuita_disponivel": True, "aviso": None, "rascunho_id": None}

    @staticmethod
    def listar_rascunhos_nf(status: str = "PENDENTE") -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/fiscal/rascunhos", params={"status": status},
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def emitir_nf(rascunho_id: int, chave_acesso: str = "", protocolo_sefaz: str = "", numero_nf: str = "") -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/fiscal/emitir",
                json={"rascunho_id": rascunho_id, "chave_acesso": chave_acesso,
                      "protocolo_sefaz": protocolo_sefaz, "numero_nf": numero_nf},
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "NF emitida.")
            return False, res.json().get("detail", "Erro ao emitir.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def cancelar_nf(rascunho_id: int, motivo: str) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/fiscal/cancelar",
                json={"rascunho_id": rascunho_id, "motivo": motivo},
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, f"Rascunho #{rascunho_id} cancelado."
            try:
                return False, res.json().get("detail", "Erro ao cancelar.")
            except Exception:
                return False, f"Erro ao cancelar (HTTP {res.status_code})."
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def reenviar_email_os(os_id: int) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/manutencao/{os_id}/reenviar-email",
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "E-mail reenviado.")
            return False, res.json().get("detail", "Erro ao reenviar.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def reenviar_email_requisicao(req_id: int) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/requisicao/{req_id}/reenviar-email",
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "E-mail reenviado.")
            return False, res.json().get("detail", "Erro ao reenviar.")
        except requests.RequestException as e:
            return False, str(e)

    # ==========================================
    # CNPJ
    # ==========================================
    @staticmethod
    def consultar_cnpj(cnpj: str) -> dict:
        try:
            res = requests.get(f"{API_BASE_URL}/cnpj/{cnpj}",
                headers=TraceBoxClient._get_headers(), timeout=12)
            if res.status_code == 200:
                return res.json()
            return {"status": "ERRO", "erro": res.json().get("detail", "Erro na consulta")}
        except requests.RequestException as e:
            return {"status": "ERRO", "erro": str(e)}

    # ==========================================
    # EMPRESA EMITENTE
    # ==========================================
    @staticmethod
    def get_emitente() -> dict:
        token = st.session_state.get("usuario_logado", {}).get("access_token", "")
        return _cached_get(f"{API_BASE_URL}/emitente", token) or {}

    @staticmethod
    def atualizar_emitente(dados: dict) -> tuple[bool, str]:
        try:
            res = requests.put(f"{API_BASE_URL}/emitente", json=dados,
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                _cached_get.clear()
                return True, res.json().get("mensagem", "Salvo.")
            return False, res.json().get("detail", "Erro ao salvar.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def sincronizar_emitente() -> tuple[bool, str, dict]:
        try:
            res = requests.post(f"{API_BASE_URL}/emitente/sincronizar",
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                _cached_get.clear()
                d = res.json()
                return True, d.get("mensagem", "Sincronizado."), d.get("dados", {})
            return False, res.json().get("detail", "Erro."), {}
        except requests.RequestException as e:
            return False, str(e), {}

    # ==========================================
    # PARCEIROS
    # ==========================================
    @staticmethod
    def listar_parceiros(tipo: str = "") -> list:
        try:
            params = {"tipo": tipo} if tipo else {}
            res = requests.get(f"{API_BASE_URL}/parceiros", params=params,
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def criar_parceiro(dados: dict) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/parceiros", json=dados,
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Criado.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def atualizar_parceiro(parceiro_id: int, dados: dict) -> tuple[bool, str]:
        try:
            res = requests.put(f"{API_BASE_URL}/parceiros/{parceiro_id}", json=dados,
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Atualizado.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def enriquecer_parceiro(parceiro_id: int) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/parceiros/{parceiro_id}/enriquecer",
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Dados atualizados.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    # ==========================================
    # DOCUMENTOS FISCAIS (NF-e estruturado)
    # ==========================================
    @staticmethod
    def criar_documento_fiscal(
        subtipo: str,
        parceiro_id: int,
        itens: list,
        serie: str = "1",
        observacao: str = "",
        doc_vinculado_id: int = None,
        num_os: str = "",
        asset_tag: str = "",
        num_serie: str = "",
        mod_frete: str = "9",
        ind_final: int = 0,
        ind_pres: int = 0,
    ) -> tuple[bool, str, int]:
        try:
            payload = {
                "subtipo": subtipo,
                "parceiro_id": parceiro_id,
                "itens": itens,
                "serie": serie,
                "observacao": observacao,
                "num_os": num_os or "",
                "asset_tag": asset_tag or "",
                "num_serie": num_serie or "",
                "mod_frete": mod_frete or "9",
                "ind_final": ind_final,
                "ind_pres": ind_pres,
            }
            if doc_vinculado_id is not None:
                payload["doc_vinculado_id"] = doc_vinculado_id
            res = requests.post(f"{API_BASE_URL}/fiscal/documentos", json=payload,
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                d = res.json()
                return True, d.get("mensagem", "Criado."), d.get("doc_id", 0)
            return False, res.json().get("detail", "Erro."), 0
        except requests.RequestException as e:
            return False, str(e), 0

    @staticmethod
    def listar_documentos_fiscais(status: str = "RASCUNHO") -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/fiscal/documentos",
                params={"status": status},
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def listar_os_para_nf() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/fiscal/os-concluidas",
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def listar_requisicoes_para_nf() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/fiscal/requisicoes-concluidas",
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def listar_remessas_abertas() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/fiscal/documentos/remessas-abertas",
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def aprovar_documento_fiscal(
        doc_id: int,
        numero_nf: str = "",
        chave_acesso: str = "",
        protocolo_sefaz: str = "",
    ) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/fiscal/documentos/aprovar",
                json={"doc_id": doc_id, "numero_nf": numero_nf,
                      "chave_acesso": chave_acesso, "protocolo_sefaz": protocolo_sefaz},
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Aprovado.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def cancelar_documento_fiscal(doc_id: int, motivo: str) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/fiscal/documentos/cancelar",
                json={"doc_id": doc_id, "motivo": motivo},
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Cancelado.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro ao cancelar (HTTP {res.status_code})."
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def enviar_email_nf(doc_id: int) -> tuple[bool, str]:
        """Envia DANFE PDF + XML informacional para o parceiro e destinatários do sistema."""
        try:
            res = requests.post(
                f"{API_BASE_URL}/fiscal/documentos/{doc_id}/enviar-email",
                headers=TraceBoxClient._get_headers(),
                timeout=30,
            )
            if res.status_code == 200:
                return True, res.json().get("mensagem", "E-mail enviado.")
            return False, res.json().get("detail", "Erro ao enviar e-mail.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def baixar_pdf_documento_fiscal(doc_id: int) -> bytes | None:
        """Retorna bytes do PDF DANFE-Rascunho ou None em caso de falha."""
        try:
            res = requests.get(
                f"{API_BASE_URL}/fiscal/documentos/{doc_id}/pdf",
                headers=TraceBoxClient._get_headers(),
                timeout=20,
            )
            if res.status_code == 200:
                return res.content
            return None
        except requests.RequestException:
            return None

    @staticmethod
    def buscar_produtos_fiscal(termo: str = "") -> list:
        """Busca produtos do catálogo com campos fiscais (NCM, EAN, origem) e TAGs disponíveis."""
        try:
            res = requests.get(
                f"{API_BASE_URL}/fiscal/produtos/busca",
                params={"termo": termo},
                headers=TraceBoxClient._get_headers(),
                timeout=10,
            )
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def listar_regras_fiscais() -> list:
        try:
            res = requests.get(f"{API_BASE_URL}/fiscal/regras",
                headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def listar_cfop_configs(direcao: str = None) -> list:
        try:
            params = {"direcao": direcao} if direcao else {}
            res = requests.get(f"{API_BASE_URL}/fiscal/cfop-config",
                params=params, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def criar_cfop_config(
        tipo_operacao: str,
        grupo_operacao: str,
        direcao: str,
        cfop_interno: str,
        cfop_interestadual: str,
        natureza_padrao: str = "",
    ) -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/fiscal/cfop-config",
                json={"tipo_operacao": tipo_operacao, "grupo_operacao": grupo_operacao,
                      "direcao": direcao, "cfop_interno": cfop_interno,
                      "cfop_interestadual": cfop_interestadual, "natureza_padrao": natureza_padrao},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Criado.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def atualizar_cfop_config(
        config_id: int,
        tipo_operacao: str,
        grupo_operacao: str,
        direcao: str,
        cfop_interno: str,
        cfop_interestadual: str,
        natureza_padrao: str = "",
    ) -> tuple[bool, str]:
        try:
            res = requests.put(f"{API_BASE_URL}/fiscal/cfop-config/{config_id}",
                json={"tipo_operacao": tipo_operacao, "grupo_operacao": grupo_operacao,
                      "direcao": direcao, "cfop_interno": cfop_interno,
                      "cfop_interestadual": cfop_interestadual, "natureza_padrao": natureza_padrao},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Atualizado.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def deletar_cfop_config(config_id: int) -> tuple[bool, str]:
        try:
            res = requests.delete(f"{API_BASE_URL}/fiscal/cfop-config/{config_id}",
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Removido.")
            return False, res.json().get("detail", "Erro.")
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def realizar_entrada_excepcional(carrinho: list, motivo: str, documento: str, usuario: str, polo: str, perfil_usuario: str) -> tuple:
        try:
            res = requests.post(f"{API_BASE_URL}/inbound/entrada-excepcional",
                json={"carrinho": carrinho, "motivo": motivo, "documento": documento,
                      "usuario": usuario, "polo": polo, "perfil_usuario": perfil_usuario},
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                data = res.json()
                return True, data.get("mensagem", "Entrada registrada"), data.get("tags", [])
            return False, res.json().get("detail", "Erro na entrada excepcional"), []
        except requests.RequestException as e:
            return False, str(e), []

    # ── Localizações (Bin Addresses) ──────────────────────────────────────────

    @staticmethod
    def listar_localizacoes(filial: str = "", apenas_ativas: bool = True) -> list:
        try:
            params = {"filial": filial, "apenas_ativas": apenas_ativas}
            res = requests.get(f"{API_BASE_URL}/localizacoes",
                params=params, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def criar_localizacao(filial: str, codigo: str, descricao: str = "",
                          zona: str = "", doca_polo: str = "") -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/localizacoes",
                json={"filial": filial, "codigo": codigo, "descricao": descricao,
                      "zona": zona, "doca_polo": doca_polo},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, "Localização criada."
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def atualizar_localizacao(loc_id: int, descricao: str = "", zona: str = "",
                              doca_polo: str = "", status: str = "ATIVO") -> tuple[bool, str]:
        try:
            res = requests.put(f"{API_BASE_URL}/localizacoes/{loc_id}",
                json={"descricao": descricao, "zona": zona, "doca_polo": doca_polo, "status": status},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Atualizado.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def inativar_localizacao(loc_id: int) -> tuple[bool, str]:
        try:
            res = requests.delete(f"{API_BASE_URL}/localizacoes/{loc_id}",
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Inativado.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def atribuir_endereco(item_id: int, localizacao_id) -> tuple[bool, str]:
        try:
            res = requests.put(f"{API_BASE_URL}/localizacoes/atribuir-endereco",
                json={"item_id": item_id, "localizacao_id": localizacao_id},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Endereço atualizado.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

    # ── Estoque Mínimo / Máximo ───────────────────────────────────────────────

    @staticmethod
    def listar_minmax(produto_codigo: str = "", filial: str = "") -> list:
        try:
            params = {"produto_codigo": produto_codigo, "filial": filial}
            res = requests.get(f"{API_BASE_URL}/estoque/minmax",
                params=params, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def salvar_minmax(produto_codigo: str, filial: str = "", estoque_minimo: float = 0,
                      estoque_maximo: float = 0, unidade_medida: str = "UN",
                      ativo: int = 1, observacao: str = "") -> tuple[bool, str]:
        try:
            res = requests.post(f"{API_BASE_URL}/estoque/minmax",
                json={"produto_codigo": produto_codigo, "filial": filial,
                      "estoque_minimo": estoque_minimo, "estoque_maximo": estoque_maximo,
                      "unidade_medida": unidade_medida, "ativo": ativo, "observacao": observacao},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Salvo.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

    @staticmethod
    def excluir_minmax(mm_id: int) -> tuple[bool, str]:
        try:
            res = requests.delete(f"{API_BASE_URL}/estoque/minmax/{mm_id}",
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Removido.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

    # ── Estoque de Segurança ──────────────────────────────────────────────────

    @staticmethod
    def listar_seguranca(produto_codigo: str = "") -> list:
        try:
            params = {"produto_codigo": produto_codigo}
            res = requests.get(f"{API_BASE_URL}/estoque/seguranca",
                params=params, headers=TraceBoxClient._get_headers(), timeout=10)
            return res.json() if res.status_code == 200 else []
        except requests.RequestException:
            return []

    @staticmethod
    def salvar_seguranca(produto_codigo: str, filial: str = "", controle_por_lote: int = 0,
                         controle_por_ativo: int = 0, ativo: int = 1,
                         janela_historica_dias: int = 90, lead_time_dias: int = 7,
                         nivel_de_servico: float = 0.95) -> tuple[bool, str, int | None]:
        try:
            res = requests.post(f"{API_BASE_URL}/estoque/seguranca",
                json={"produto_codigo": produto_codigo, "filial": filial,
                      "controle_por_lote": controle_por_lote, "controle_por_ativo": controle_por_ativo,
                      "ativo": ativo, "janela_historica_dias": janela_historica_dias,
                      "lead_time_dias": lead_time_dias, "nivel_de_servico": nivel_de_servico},
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                data = res.json()
                return True, data.get("mensagem", "Salvo."), data.get("id")
            try:
                return False, res.json().get("detail", "Erro."), None
            except Exception:
                return False, f"Erro HTTP {res.status_code}.", None
        except requests.RequestException as e:
            return False, str(e), None

    @staticmethod
    def calcular_seguranca(es_id: int) -> tuple[bool, str, float | None]:
        try:
            res = requests.post(f"{API_BASE_URL}/estoque/seguranca/{es_id}/calcular",
                headers=TraceBoxClient._get_headers(), timeout=15)
            if res.status_code == 200:
                data = res.json()
                return True, data.get("mensagem", "Calculado."), data.get("estoque_seguranca")
            try:
                return False, res.json().get("detail", "Erro."), None
            except Exception:
                return False, f"Erro HTTP {res.status_code}.", None
        except requests.RequestException as e:
            return False, str(e), None

    @staticmethod
    def excluir_seguranca(es_id: int) -> tuple[bool, str]:
        try:
            res = requests.delete(f"{API_BASE_URL}/estoque/seguranca/{es_id}",
                headers=TraceBoxClient._get_headers(), timeout=10)
            if res.status_code == 200:
                return True, res.json().get("mensagem", "Removido.")
            try:
                return False, res.json().get("detail", "Erro.")
            except Exception:
                return False, f"Erro HTTP {res.status_code}."
        except requests.RequestException as e:
            return False, str(e)

