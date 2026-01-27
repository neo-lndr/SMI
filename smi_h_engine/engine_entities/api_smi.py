"""
Cliente Arteris API — utilitários para interação com o backend SMI Arteris.

Propósito:
    Fornecer um cliente leve para executar operações comuns contra a API SMI Arteris (consulta de DocTypes,
    leitura/atualização de registros e execução de métodos remotos) de forma centralizada e reutilizável.

Responsabilidades principais:
    - Encapsular chamadas HTTP (GET/POST) com tratamento de erros e timeouts.
    - Fornecer helpers para obter DocTypes, campos e registros por chave.
    - Normalizar lógica de atualização de registros (batch de campos/valores).
    - Remover/filtrar propriedades não desejadas em payloads retornados.

Posição na arquitetura:
    Camada de integração / cliente HTTP — funciona como adaptador entre a aplicação local (motor) e o backend SMI Arteris,
    sendo chamado por componentes de negócio que precisam ler ou alterar dados no servidor remoto.

Dependências críticas:
    - requests (com configuração de verify/timeout)
    - python-dotenv para carregar variáveis de ambiente (ARTERIS_API_BASE_URL, ARTERIS_API_TOKEN, DISABLE_SSL_VERIFY)
    - logging para rastreamento de operações e erros, typing para tipagem
    - Variáveis de ambiente (.env)

Considerações de segurança:
    - Executar exclusivamente em rede isolada com o backend do SMI Arteris.

Exemplo de uso básico:

    api = SmiApi()
    doctypes = api.get_arteris_doctypes()
    record = api.get_data_from_key('Asset', 'ASSET-001')
    api.update_measurement_records('MEASUREMENT_ID')

"""

import os
import json
import logging
from api_client import custom_url
from dotenv import load_dotenv
from typing import Any
from ast import Dict
from typing import Literal

# Carregar variáveis de ambiente
load_dotenv()

class SmiApi():
    """
    Classe para interagir com API SMI Arteris.
    Fornece métodos para buscar DocTypes, seus campos e dados.
    """

    def __init__(self):
        try:
            self.api_token = os.getenv("ARTERIS_API_TOKEN")
            self.api_base_url = f"{os.getenv('ARTERIS_API_BASE_URL')}"
            self.api_get_keys = f"{os.getenv('ARTERIS_API_BASE_URL')}/method/arteris_app.api.engine.get_keys"
            self.api_get_contracts = f"{os.getenv('ARTERIS_API_BASE_URL')}/method/arteris_app.api.engine.get_contracts"
            self.logger = logging.getLogger("SmiApi")
        except Exception as e:
            self.logger.exception("Erro inesperado na inicialização: %s", e)
            raise

    def _call_request(self, url: str, body: dict | str | None = None, params: dict = {}, method: Literal["GET", "POST", "PUT", "DELETE"] = "GET") -> Any:
        """
        Metodo padrao para requeisicoes HTTP
        Parâmetros:
            url: URL do endpoint
            body: corpo da requisição (para POST/PUT)
            params: parâmetros de consulta (para GET)
            method: método HTTP (GET, POST, PUT, DELETE)
        Retorno:
            Resposta JSON ou None em caso de erro
        """
        try:
            if not self.api_token:
                self.logger.error("Token da API não configurado")
                return None

            if not params:
                params = {}

            data = custom_url(
                api_base_url = url,
                api_token = self.api_token,
                body=body,
                params=params,
                method=method)

            if data is None:
                self.logger.error("Erro na chamada %s para %s", method, url)
                return None

            return data
        except Exception as e:
            self.logger.exception("Erro inesperado na requisição %s para %s: %s", method, url, e)
            return None

    def update(self, results: dict, formulas: dict) -> None:
        """
        Atualiza os doctypes conforme os resultados das formulas
        Parâmetros:
            results: resultados das formulas
            formulas: formulas utilizadas
        """
        try:
            def get_formula(path: str, formulas: dict) -> tuple[str | None, str | None]:
                try:
                    for formula in formulas['formulas']:
                        if formula.get('path') == path:
                            return  formula.get('update').get('doctype'), formula.get('update').get('fieldname')
                    return None, None
                except Exception as e:
                    self.logger.exception("Erro inesperado ao buscar fórmula: %s", e)
                    return None, None

            updates = {}

            if results:
                for result in results:
                    try:
                        for path_result in result.get('results'):
                            try:
                                if path_result.get('status') == 'error':
                                    continue

                                doctype, field = get_formula(path_result.get('path'), formulas)

                                if not doctype or not field:
                                    continue

                                _id = result.get('id')
                                if _id not in updates:
                                    updates[_id] = {
                                        "doctype": doctype,
                                        "fields": [],
                                        "values": []
                                    }

                                updates[_id]['fields'].append(field)
                                updates[_id]['values'].append(path_result.get('result'))
                            except Exception as e:
                                self.logger.exception("Erro inesperado processando resultado: %s", e)
                                continue
                    except Exception as e:
                        self.logger.exception("Erro inesperado processando result: %s", e)
                        continue

                for __id, update in updates.items():
                    try:
                        if len(update['fields']) == 0:
                            continue

                        body = {
                            "doctype": update['doctype'],
                            "fields": update['fields'],
                            "parameters_values": update['values'],
                            "id": __id,
                        }
                        url = f"{self.api_base_url}/method/arteris_app.api.engine.update_doctype"

                        self._call_request(url, body=body, method="POST")
                    except Exception as e:
                        self.logger.exception("Erro inesperado atualizando doctype %s: %s", __id, e)
                        continue
        except Exception as e:
            self.logger.exception("Erro inesperado no método update: %s", e)

    def sumarize_measurement(self, measurement: str) -> None:
        """
        Totaliza a medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.sumarize_measurement",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao totalizar medição %s: %s", measurement, e)

    def create_measurement_items(self, measurement: str) -> None:
        """
        Recria os itens de medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.create_measurement_items",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao criar itens de medição %s: %s", measurement, e)

    def update_measurement_records(self, measurement: str) -> None:
        """
        Atualiza os registros de medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.update_measurement_records",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao atualizar registros de medição %s: %s", measurement, e)

    def update_hours_measurement_record(self, measurement: str) -> None:
        """
        Atualiza informações de horas dos registros de medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.update_hours_measurement_record",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao atualizar horas de medição %s: %s", measurement, e)

    def update_reidi_measurement_record(self, measurement: str) -> None:
        """
        Calcula os valores de REIDI para os pedidos SAP da medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.update_reidi_measurement_record",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao atualizar REIDI de medição %s: %s", measurement, e)

    def apply_measurement_performance_conditions(self, measurement: str) -> None:
        """
        Aplica as condições de produtividade compensatória para a medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.apply_measurement_performance_conditions",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao aplicar condições de produtividade para medição %s: %s", measurement, e)

    def apply_measurement_items_factor(self, measurement: str) -> None:
        """
        Aplica as condições de fator de produtividade para a medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.apply_measurement_items_factor",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao aplicar fator de produtividade para medição %s: %s", measurement, e)

    def create_measurement_items_balance(self, measurement: str) -> None:
        """
        Cria os registros de saldo de pagamento dos itens contratuais
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.create_measurement_items_balance",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao criar saldo de itens para medição %s: %s", measurement, e)

    def update_cities(self, measurement: str) -> None:
        """
        Atualiza cidades e rodovias para os registros de medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.update_cities",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao atualizar cidades para medição %s: %s", measurement, e)

    def update_measurement_productivity(self, measurement: str) -> None:
        """
        Atualiza os registros de produtividade compensatória
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.update_measurement_productivity",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao atualizar produtividade para medição %s: %s", measurement, e)

    def create_measurement_sap_orders_records(self, measurement: str) -> None:
        """
        Carrega os pedidos SAP para a medição
        Parâmetros:
            measurement: id da medição
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.measurement.create_measurement_sap_orders_records",
                body = {"measurement": measurement},
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao criar pedidos SAP para medição %s: %s", measurement, e)

    def update_sap_orders_balance(self) -> None:
        """
        Atualiza o saldo dos pedidos SAP
        """
        try:
            self._call_request(
                url = f"{self.api_base_url}/method/arteris_app.api.saporder.update_sap_orders_balance",
                body = None,
                method = "POST"
            )
        except Exception as e:
            self.logger.exception("Erro inesperado ao atualizar saldo dos pedidos SAP: %s", e)

    def get_arteris_doctypes(self, child: bool = False) -> list[Dict] | None:
        """
        Recupera todos os DocTypes da API SMI Arteris que pertencem ao módulo 'Arteris' e que não são itens filhos.
        Parâmetros:
            child (bool): Se True, busca doctypes filhos
        Retorno:
            Uma lista de dicionários, em que cada dicionário representa um DocType
            encontrado ou None em caso de erro.
        """
        try:
            url = f"{self.api_base_url}/resource/DocType"
            params = {
                "filters": json.dumps([
                    ["module", "=", "Arteris"],
                    ["istable", "=", "1"] if child else ["istable", "!=", "1"]
                ]),
                "limit_page_length": 0
            }

            data = self._call_request(
                url = url,
                params = params,
                method = "GET"
            )

            if data:
                return data.get("data", [])
            return None
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar DocTypes Arteris: %s", e)
            return None

    def get_docfields_for_doctype(self, doctype_name) -> list[Dict] | None:
        """
        Recupera DocFields (metadados de campos) para um DocType específico.
        Parâmetros:
            doctype_name (str): Nome do DocType para o qual buscar os campos.
        Retorno:
            Uma lista de dicionários, onde cada dicionário representa um DocField
            ou None em caso de erro.
        """
        try:
            url = f"{self.api_base_url}/resource/DocType/{doctype_name}"
            params = {
                "limit_page_length": 0
            }

            data = self._call_request(
                url = url,
                params = params,
                method = "GET"
            )

            if data:
                return data.get("data", [])
            return None
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar campos do DocType %s: %s", doctype_name, e)
            return None

    def get_keys(self, doctype_name: str, return_field: str, filters: dict = {}) -> list[str] | None:
        """
        Recupera chaves para um DocType específico da API SMI Arteris com base em um filtro.
        Parâmetros:
            doctype_name (str): O nome do DocType para obter chaves.
            return_field (str): Campo a ser retornado.
            filters (dict): Filtros a serem aplicados.
        Retorno:
            Uma lista de strings contendo os valores das chaves do DocType ou None em caso de erro.
        """
        try:
            url = f"{self.api_get_keys}"
            params = {}
            body = {
                "doctype": doctype_name,
                "filters": filters,
                "return_field": return_field
            }

            data = self._call_request(
                url = url,
                params = params,
                body = body,
                method = "GET"
            )

            if data:
                keys = [k[return_field] for k in data.get("message", [])]
                return keys
            return None
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar chaves do DocType %s: %s", doctype_name, e)
            return None

    def remove_properties_recursively(self, data: dict, properties_to_remove: list) -> dict:
        """
        Remove recursivamente propriedades especificadas de um objeto JSON.
        Parâmetros:
            data: O objeto JSON do qual remover as propriedades.
            properties_to_remove: Lista de propriedades a serem removidas.
        Retorno:
            O objeto JSON com as propriedades removidas.
        """
        try:
            if isinstance(data, dict):
                for prop in properties_to_remove:
                    if prop in data:
                        del data[prop]

                for key, value in list(data.items()):
                    data[key] = self.remove_properties_recursively(value, properties_to_remove)

            elif isinstance(data, list):
                for i, item in enumerate(data):
                    data[i] = self.remove_properties_recursively(item, properties_to_remove)

            return data
        except Exception as e:
            self.logger.exception("Erro inesperado ao remover propriedades: %s", e)
            return data

    def get_data_from_key(self, doctype_name: str, key: str) -> dict | None:
        """
        Busca dados de um DocType específico na API SMI Arteris usando uma chave.
        Parâmetros:
            doctype_name (str): O nome do DocType para o qual buscar os dados.
            key (str): A chave do DocType a ser consultada.
        Retorno:
            Um objeto JSON contendo os dados do DocType ou None em caso de erro.
        """
        try:
            url = f"{self.api_base_url}/resource/{doctype_name}/{key}"
            params = {
                "limit_page_length": 0
            }

            data = self._call_request(
                url = url,
                params = params,
                method = "GET"
            )

            if data and "data" in data:
                data_filtered = data["data"]
                properties_to_remove = []
                data_filtered = self.remove_properties_recursively(data_filtered, properties_to_remove)
                return data_filtered
            return None
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar dados do DocType %s com chave %s: %s", doctype_name, key, e)
            return None

    def get_contracts(self) -> list[Dict] | None:
        """
        Recupera os contratos a serem calculados pelo motor
        Retorno:
            Lista de contratos ou None em caso de erro
        """
        try:
            url = f"{self.api_base_url}/method/arteris_app.api.engine.get_contracts"

            contracts = self._call_request(
                url = url,
                method = "GET"
            )

            if contracts and "message" in contracts:
                return contracts["message"]
            return None
        
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar contratos: %s", e)
            return None

    def write_errors(self, measurement, errors):
        """
        Envia os erros do motor para a API SMI Arteris
        Parâmetros:
            measurement: id da medição
            errors: lista de erros
        Retorno:
            Resposta da API ou None em caso de erro
        """
        try:
            url = "engine.write_errors"
            body = {
                "measurement": measurement,
                "errors": errors
            }

            data = self._call_request(
                url = url,
                body = body,
                method = "POST"
            )

            return data
        except Exception as e:
            self.logger.exception("Erro inesperado ao enviar erros para medição %s: %s", measurement, e)
            return None