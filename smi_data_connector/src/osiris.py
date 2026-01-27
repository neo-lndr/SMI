"""
Conector para a API OSIRIS — login, coleta de produções e imagens

Propósito:
    Fornecer funções utilitárias para autenticação na API OSIRIS e para recuperar produções e imagens,
    encapsulando lógica de sessão, paginação e integração com o backend Frappe/Arteris.

Responsabilidades principais:
    - Autenticar-se contra a API OSIRIS e manter sessão (login, create_session_and_login).
    - Consultar produções e imagens (get_producoes, get_prod_with_session, get_image).
    - Agrupar e transformar produções em registros de medição compatíveis com o backend e enviar via API (create_osiris_measurement_records).

Posição na arquitetura:
    - Camada de integração / adaptador entre o serviço OSIRIS (fornecedor de dados) e o backend Arteris/Frappe.
    - Atua como orquestrador para coleta diária, preparação de payloads e gravação de registros no sistema central.

Dependências críticas:
    - Bibliotecas Python: requests, holidays_br, datetime, argparse, logging.
    - Módulos internos: security.secrets_manager.SimpleSecretManager, security.secure_api_client.get_secure_client, security.get_env.load_dotenv/get_env.
    - Variáveis de ambiente obrigatórias: ARTERIS_API_BASE_URL, ARTERIS_API_TOKEN (API_TOKEN), OSIRIS_LOGIN, OSIRIS_PASSWORD.
    - Endpoint OSIRIS pré-configurado (ex.: https://preprod-osiris.arteris.com.br/api/api).

Considerações de segurança:
    - A API OSIRIS usada por este módulo aceita credenciais via GET (query string) — risco de exposição em logs e caches; preferir POST/headers se a API suportar.
    - Segredos são carregados por um gerenciador (SimpleSecretManager) com fallback para .env; evite commits de credenciais em repositórios.
    - Timeouts foram configurados nas requisições; tratar adequadamente exceções de rede (Retry / backoff pode ser adicionado).
    - Cookies de sessão podem ser manipulados como objeto RequestsCookieJar ou string; validar origem e validade antes de reutilizar.
    - Sanitizar e limitar dados enviados ao backend para reduzir risco de injeção; logar informações sensíveis apenas em modo seguro (não logar senhas).

Exemplo de uso básico:
    # Autenticar com sessão (recomenda-se obter credenciais via secrets manager / env)
    session = create_session_and_login("usuario@exemplo.com", "senha-secreta")
    # Buscar produções paginadas para um contrato num intervalo
    produtos = get_prod_with_session(session, page_number=1, page_size=100,
                                     data_inicio="2025-09-01", data_fim="2025-09-01", contract="CW37277-RB")
    # Processar e enviar registros entre datas (usa variáveis de ambiente para API do backend)
    start = datetime.strptime("2025-09-01", "%Y-%m-%d")
    end = datetime.strptime("2025-09-15", "%Y-%m-%d")
    create_osiris_measurement_records(start, end, contract_code="CW37277-RB", ignore_check=False, only_images=False)

"""

import requests
import logging
import holidays_br
import argparse
import time
import os
from dotenv import load_dotenv
from api_client import custom_url
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union

logger = logging.getLogger(__name__)

def login(email: str, password: str) -> Union[str, requests.cookies.RequestsCookieJar]: # type: ignore
    """
    Login seguro no sistema OSIRIS

    Parâmetros:
        email: Email do usuário para autenticação
        password: Senha do usuário para autenticação

    Retorno:
        Cookie de sessão ou jarra de cookies para requisições autenticadas

    """
    if not email or not password:
        raise ValueError("Email and password are required")

    base_url = "https://preprod-osiris.arteris.com.br/api/api"
    login_url = f"{base_url}/user/login"

    params = {
        "Email": email,
        "Password": password
    }

    try:
        # Realizar requisição de login com timeout
        response = requests.get(login_url, params=params, timeout=30)

        if response.status_code == 200:
            # Obter cookie de sessão
            session_cookie = response.cookies.get('.Elleve_Rodovias')
            if not session_cookie:
                logger.warning("Cookie de sessão principal não encontrado, utilizando todos os cookies")
                return response.cookies

            return session_cookie
        else:
            raise Exception(f"Authentication failed: {response.status_code} - {response.text}")

    except requests.exceptions.Timeout:
        logger.error("Timeout na requisição de login OSIRIS")
        raise Exception("Login request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro no login OSIRIS: {e}")
        raise Exception(f"Login request failed: {e}")

def get_image(
        session_cookie, 
        page_number=1, 
        page_size=10, 
        production_id=None, 
        base_url = "https://preprod-osiris.arteris.com.br/api/api/mediaproduction/") -> Dict[str, Any]:
    
    """
    Buscar imagens associadas a uma produção específica no sistema OSIRIS

    Parâmetros:
        session_cookie: Cookie de sessão ou jarra de cookies para autenticação
        page_number: Número da página para paginação (padrão: 1)
        page_size: Tamanho da página para paginação (padrão: 10)
        production_id: ID da produção para buscar imagens (obrigatório)
        base_url: URL base da API OSIRIS (padrão: ambiente de pré-produção)

    Retorno:
        Dados JSON com informações das imagens ou erro em caso de falha
    """
    
    images_url = f"{base_url}{production_id}"
    params = {}
    # }
    #     "PageNumber": page_number,
    #     "PageSize": page_size
    # }
    
    # Verifica se session_cookie é um objeto cookies ou uma string
    if isinstance(session_cookie, requests.cookies.RequestsCookieJar): # type: ignore
        # Usa o objeto cookies diretamente
        response = requests.get(images_url, params=params, cookies=session_cookie)
    else:
        # Cabeçalhos com o cookie de sessão (formato string)
        headers = {
            "Cookie": f".Elleve_Rodovias={session_cookie}"
        }
        response = requests.get(images_url, params=params, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Erro ao buscar produções: {response.status_code} - {response.text}")

def get_producoes(
        session_cookie, 
        page_number=1, 
        page_size=10, 
        data_inicio=None, 
        data_fim=None,
        base_url = "https://preprod-osiris.arteris.com.br/api/api") -> Dict[str, Any]:
    """
    Buscar produções no sistema OSIRIS

    Parâmetros:
        session_cookie: Cookie de sessão ou jarra de cookies para autenticação
        page_number: Número da página para paginação (padrão: 1)
        page_size: Tamanho da página para paginação (padrão: 10)
        data_inicio: Data de início para filtrar produções (formato 'YYYY-MM-DD', opcional)
        data_fim: Data de fim para filtrar produções (formato 'YYYY-MM-DD', opcional)
        base_url: URL base da API OSIRIS (padrão: ambiente de pré-produção)
        
    Retorno:
        Dados JSON com informações das produções ou erro em caso de falha
    """

    # Endpoint de produções
    producoes_url = f"{base_url}/production/producoes"
    # Parâmetros de consulta
    params = {
        "PageNumber": page_number,
        "PageSize": page_size
    }
    # Adiciona filtros opcionais
    if data_inicio:
        params["DataInicio"] = data_inicio
    if data_fim:
        params["DataFim"] = data_fim
    
    # Verifica se session_cookie é um objeto cookies ou uma string
    if isinstance(session_cookie, requests.cookies.RequestsCookieJar): # type: ignore
        # Usa o objeto cookies diretamente
        response = requests.get(producoes_url, params=params, cookies=session_cookie)
    else:
        # Cabeçalhos com o cookie de sessão (formato string)
        headers = {
            "Cookie": f".Elleve_Rodovias={session_cookie}"
        }
        response = requests.get(producoes_url, params=params, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Erro ao buscar produções: {response.status_code} - {response.text}")

# Versão alternativa usando Session para manter cookies automaticamente
def create_session_and_login(email: str, password: str) -> requests.Session:
    """
    Criar sessão e realizar login no sistema OSIRIS com tratamento adequado de erros

    Parâmetros:
        email: Email do usuário para autenticação
        password: Senha do usuário para autenticação

    Retorno:
        Sessão autenticada para requisições
    """
    if not email or not password:
        raise ValueError("Email and password are required")

    session = requests.Session()
    base_url = "https://preprod-osiris.arteris.com.br/api/api"
    login_url = f"{base_url}/user/login"

    params = {
        "Email": email,
        "Password": password
    }

    try:
        response = session.get(login_url, params=params, timeout=30)
        if response.status_code == 200:
            return session
        else:
            raise Exception(f"Falha na autenticação: {response.status_code} - {response.text}")

    except requests.exceptions.Timeout:
        raise Exception("Timeout no login da sessão OSIRIS")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Falha na requisição de login da sessão: {e}")

def get_prod_with_session(
        session, 
        page_number=1, 
        page_size=10, 
        data_inicio=None, 
        data_fim=None,
        contract=None,
        base_url = "https://preprod-osiris.arteris.com.br/api/api") -> Dict[str, Any]:
    """
    Versão de get_producoes que utiliza uma sessão autenticada

    Parâmetros:
        session: Sessão autenticada para requisições
        page_number: Número da página para paginação (padrão: 1)
        page_size: Tamanho da página para paginação (padrão: 10)
        data_inicio: Data de início para filtrar produções (formato 'YYYY-MM-DD', opcional)
        data_fim: Data de fim para filtrar produções (formato 'YYYY-MM-DD', opcional)
        contract: Código do contrato para filtrar produções (opcional)
        base_url: URL base da API OSIRIS (padrão: ambiente de pré-produção)

    Retorno:
        Dados JSON com informações das produções ou erro em caso de falha
    """
    producoes_url = f"{base_url}/production/producoes"
    params = {
        "PageNumber": page_number,
        "PageSize": page_size,
        "DataInicio": data_inicio,
        "DataFim": data_fim
    }
    if contract:
        params["ContractCode"] = contract

    try:
        response = session.get(producoes_url, params=params)
        response.raise_for_status()  # Lança um erro para códigos de status HTTP 4xx/5xx
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"Erro ao buscar produções com sessão: {e}")

def create_osiris_measurement_records(
        start_date: datetime, 
        end_date: datetime = datetime.now(), 
        contract_code = None, 
        ignore_check = False,
        ignore_images = False) -> None:
    """
    Criar registros de medição do OSIRIS no SMI.

    Parâmetros:
        start_date: Data de início para processar registros
        end_date: Data de fim para processar registros (padrão: agora)
        contract_code: Código do contrato específico para processar (opcional)
        ignore_check: Ignorar verificação de contratos com dados (padrão: False)

    Retorno:
        True se o processamento for bem-sucedido, False caso contrário
    """

    # Enviar dados para o frappe
    def write_measurement_record(measurement_records: List[Dict[str, Any]], contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:

        """
        Enviar registros de medição para o backend via API

        Parâmetros:
            measurement_records: Lista de registros de medição a serem enviados
            contract: Informações do contrato associadas aos registros

        Retorno:
            Registro de medição criado ou None em caso de falha
        """

        if not measurement_records:
            return None

        data = {
            "contract_name": contract["name"],
            "contract_meaesurement": contract["measurements"][-1]["name"],
            "contract_meaesurement_current": contract["measurements"][-1]["current"],
            "contract_processing_date": contract["processing_date"],
            "data": measurement_records,
            "relations": {
                "asset": osiris_assets,
                "work_role": osiris_work_roles,
                "contract_item": contract["itens"]
            }
        }

        # Escrever registro de medição
        _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.create_osiris_measurement_record"

        try:
            response_data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                body=data,
                timeout=360,
                method="POST")
        except Exception as e:
            logger.error(f"Falha ao criar registro de medição para o contrato {contract}: {e}")

        return response_data["message"] # type: ignore

    def get_measurement(search_date: datetime, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Obter ou criar a medição atual do contrato para a data de pesquisa

        Parâmetros:
            search_date: Data para a qual a medição deve ser obtida ou criada
            contract: Informações do contrato para o qual a medição é relevante

        Retorno:
            Dados da medição ou None em caso de falha
        """

        # Criar ou retornar medições do contrato
        str_search_date = search_date.strftime("%Y-%m-%d")
        _url = f"{API_BASE_URL}/method/arteris_app.api.measurement.get_measurement?current_date_str={str_search_date}&execution_date_str={str_search_date}&contract={contract['name']}"

        try:
            response_data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                timeout=360,
                method="POST")
        except Exception as e:
            logger.error(f"Falha ao obter registro de medição para o contrato {contract}: {e}")

        return response_data["message"] # type: ignore

    def get_osiris_keys(contract_name: str, contract_processing_date: str) -> Optional[Dict[str, Any]]:
        """
        Obter chaves do OSIRIS para uma medição de contrato específica.

        Parâmetros:
            contract_name: Nome do contrato para o qual as chaves são necessárias
            contract_processing_date: Data de processamento do contrato (formato 'YYYY-MM-DD')

        Retorno:
            Lista de chaves ou None em caso de falha
        """
        _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_keys?contract_name={contract_name}&contract_processing_date={contract_processing_date}"

        try:
            response_data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                timeout=360,
                method="GET")
        except Exception as e:
            logger.error(f"Falha ao obter chaves do OSIRIS para o contrato {contract_name}: {e}")

        return response_data["message"] # type: ignore
    
    def get_contract_to_process(start_date: date) -> Optional[List[Dict[str, Any]]]:
        """
        Obter o contrato a ser processado com base na data de início.

        Parâmetros:
            start_date: Data de início para filtrar contratos

        Retorno:
            Lista de contratos ou None em caso de falha
        """
        _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_process?start_date={start_date.strftime('%Y-%m-%d')}"

        try:
            response_data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                timeout=360, 
                method="GET")
        except Exception as e:
            logger.error(f"Falha ao obter contratos: {e}")

        return response_data["message"] # type: ignore

    def load_osiris_data():
        """
        Processar dados do OSIRIS entre as datas especificadas.
        """

        contracts = {}
        search_date = start_date
        counter_01 = 0
        counter_02 = 0
        counter_03 = 0

        logger.info(f"Processando de {start_date.strftime('%Y-%m-%d')} até {end_date.strftime('%Y-%m-%d')}")

        # Para apenas um contrato específico
        if contract_code:
            contracts_to_process = [{"name": None, "contrato": contract_code, "uuidosiris": None}] 
        else:
            contracts_to_process = get_contract_to_process(search_date)

        if not contracts_to_process:
            logger.warning("Nenhum contrato para processar")
            return
        # Mapeamento de contratos para nome e UUID
        contracts_name_to_process = {contract['contrato']: {"name": contract['name'],"uuid": contract['uuidosiris']} for contract in contracts_to_process}

        if not contracts_to_process:
            logger.warning("Nenhum contrato para processar")
            return

        try:
            session = create_session_and_login(OSIRIS_LOGIN, OSIRIS_PASSWORD)
            logger.info("Sessão OSIRIS criada para processamento de dados")
        except Exception as e:
            logger.error(f"Falha ao criar sessão OSIRIS: {e}")
            return

        # Pode ignorar a verificação de contratos com dados
        if ignore_check:
            contracts_with_data = {cp: values['name'] for cp, values in contracts_name_to_process.items()}
        else:
            contracts_with_data = {}
            # Verificar contratos com dados
            for cp, values in contracts_name_to_process.items():
                if not values['uuid']:
                    logger.info(f"Verificando contrato: {cp}")
                    productions = get_prod_with_session(
                        session, 
                        page_number = 1, 
                        page_size = 1,
                        data_inicio = start_date.strftime('%Y-%m-%d'), 
                        data_fim = end_date.strftime('%Y-%m-%d'),
                        contract = cp)  
                    if len(productions['Data'])>0:
                        logger.info(f"Contrato {cp} possui dados.")
                        contracts_with_data.setdefault(cp, values['name'])
                    else:
                        inconsistency = f"Nenhum registro localizado para o contrato {cp}, no periodo de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}!"

                        json_post = {
                            "contract": values['name'],
                            "errors": [inconsistency]
                        }

                        # Gravar o erro
                        _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.write_no_records"
                        try:
                            # Usar cliente de API seguro
                            data = custom_url(
                                api_base_url=_url,
                                api_token=API_TOKEN,
                                body=json_post,
                                method="POST")
                        except Exception as e:
                            logger.error(f"Falha ao gravar 'no records' SMI: {e}")
                            data = None
        
        # Laço while para iterar por cada dia
        while search_date <= end_date:

            logger.info(f"Processando data: {search_date.strftime('%Y-%m-%d')}")

            counter_01 += 1

            for cp in contracts_with_data:
                page = 1

                last_contract = ""
                measurement_records = []                

                while page > 0:

                    # Consultar dados na API do OSIRIS
                    productions = get_prod_with_session(
                        session, 
                        page_number = page, 
                        page_size = 500,
                        data_inicio = search_date.strftime('%Y-%m-%d'), 
                        data_fim = search_date.strftime('%Y-%m-%d'),
                        contract = cp)

                    for p in productions['Data']:

                        counter_02 += 1

                        # Ignorar se for nulo
                        if p['MeasurementInfo']:
                            rodovia = p['ConcessionaireRoadState']['RoadName']
                            rodovia = f'{rodovia.upper()}-{p["ConcessionaireRoadState"]["StateUf"]}'

                            mcount = 0

                            for m in p['MeasurementInfo']:

                                counter_03 += 1

                                mcount +=1
                                
                                # Verificar se é medido
                                if not m['IsMeasured']:
                                    continue

                                # Obter contrato 
                                osiris_cw = m['Contract']['Number']
                                osiris_cw_id = m['Contract']['Id']

                                # Verificar se o registro já está nos itens do contrato
                                if last_contract != osiris_cw_id:
                                    # Verificar se não é o primeiro registro
                                    if last_contract:
                                        if measurement_records:
                                            write_measurement_record(measurement_records, contract) # type: ignore
                                            measurement_records = []

                                    # Redefinir os registros de medição para o novo contrato
                                    measurement_records = []
                                    last_contract = osiris_cw_id                        

                                if not osiris_cw in contracts:
                                    # Obter nome do contrato
                                    contract = { 
                                        "name": contracts_with_data[cp],
                                        "code": "",
                                        "osiris": "",
                                        "last_measurement_date": None,
                                        "processing_date": None,
                                        "process": True,
                                        "itens": [],
                                        "keys": [],
                                        "measurements":[]
                                    }
                                    contracts[osiris_cw] = contract
                                    
                                    # Obter contrato
                                    _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_contract?contract={osiris_cw}&osiris_uuid={osiris_cw_id}"

                                    try:
                                        data = custom_url(
                                            api_base_url=_url,
                                            api_token=API_TOKEN,
                                            method="GET",
                                            timeout=360)
                                    except Exception as e:
                                        logger.error(f"Falha ao obter o contrato {contract}: {e}")

                                    if data["message"]: # type: ignore
                                        # Verificar relacionamento do contrato
                                        if not data["message"]["osiris"]: # type: ignore
                                            # Gravar relacionamento no OSIRIS
                                            _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.update_contract?contract={data['message']['name']}&osiris_uuid={osiris_cw_id}" # type: ignore
                                            try:
                                                custom_url(
                                                    api_base_url=_url,
                                                    api_token=API_TOKEN,
                                                    method="POST",
                                                    timeout=360)
                                            except Exception as e:
                                                logger.error(f"Falha ao atualizar o contrato {contract}: {e}")

                                        # Atualizar informações do contrato
                                        contract["name"] = data["message"]["name"] # type: ignore
                                        contract["osiris"] = osiris_cw_id
                                        contract["code"] = osiris_cw

                                        # Obter itens do contrato
                                        _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_contract_items?contract_name={contract['name']}"
                                        try:
                                            data = custom_url(
                                                api_base_url=_url,
                                                api_token=API_TOKEN,
                                                method="GET",
                                                timeout=360)
                                        except Exception as e:
                                            logger.error(f"Falha ao obter itens do contrato {contract}: {e}")

                                        itens = data["message"] # type: ignore
                                        contract["itens"].extend(itens)
                                    else:
                                        # Falha ao obter contrato
                                        contract["process"] = False

                                else:
                                    contract = contracts[osiris_cw]

                                # Definir data de processamento
                                s_search_date = p['DateProduction'][0:10]
                                if not contract["processing_date"] == s_search_date:
                                    contract["processing_date"] = s_search_date
                                    contract["keys"] = get_osiris_keys(contract["name"], s_search_date)

                                # Continuar somente se o contrato possuir um nome
                                if contract["name"] and contract["process"]:                
                                    # Verificar medição atual do contrato
                                    if not contract["measurements"]:
                                        measurement = get_measurement(search_date, contract)

                                        # Verificar se a resposta contém dados
                                        if measurement and "measurements" in measurement and measurement["measurements"]:
                                            contract["measurements"].extend(measurement["measurements"])
                                            contract["last_measurement_date"] = measurement["measurements"][0]["end"]
                                        else:
                                            # Falha ao obter a medição atual
                                            contract["process"] = False                    

                                if contract["process"]:                
                                    # Se a data for maior que a última data de medição, criar uma nova medição
                                    if search_date > datetime.strptime(contract["last_measurement_date"], "%Y-%m-%d"):
                                        measurement = get_measurement(search_date, contract)
                                        contract["measurements"].extend(measurement["measurements"])
                                        contract["last_measurement_date"] = measurement["measurements"][0]["end"]    

                                    # Necessário Id de composição para criar a chave
                                    id = f"{counter_01:04d}.{counter_02:04d}.{counter_03:04d}-{search_date.strftime('%Y%m%d')}-{p['Id']}"
                                    key = id

                                    # Adicionar o registro aos registros de medição
                                    if id in contract["keys"]:
                                        continue                                

                                    km_inicial = p['KmStart']
                                    if p['Mstart']:
                                        km_inicial += p['Mstart']/1000
                                    km_final = p['KmEnd']
                                    if p['Mend']:
                                        km_final += p['Mend']/1000

                                    # Monta o registro
                                    measurement_records.append({
                                        "id": id,
                                        "chave": key,
                                        "tipo": 'Osiris',
                                        "datacriacao": p['DateProduction'],
                                        "dataexecucao": p['DateProduction'],
                                        "dataaprovacao": None,
                                        "contrato": contract["name"],
                                        "boletimmedicao": contract["measurements"][-1]["name"],
                                        "medicaovigente": contract["measurements"][-1]["current"],
                                        "aprovador": None,
                                        "eh_feriado": False,
                                        "mstart": p['Mstart'],
                                        "mend": p['Mend'],
                                        "length": p['Length'],
                                        "width": p['Width'],
                                        "thickness": p['Thickness'],
                                        "codigo": p['Rdo']['Code'],
                                        "cidade": p['City']['Description'],
                                        "entitysystem": p['EntitySystem']['Description'],
                                        "atvidade": p['Activity']['Description'][0:120],
                                        "servico": p['Service']['Description'][0:120],
                                        "os": p['ServiceOrder']['Code'],
                                        "contractor": p['Contractor']['FantasyName'],
                                        "equipe": p['Team']['Description'],
                                        "laboratorystatus": p['ProductionLaboratoryStatus']['Description'],
                                        "codigorelatorio": p['Rdo']['Code'],
                                        "dataexecucao": p['DateProduction'],
                                        "rodovia": rodovia,
                                        "via": p['Track']['Description'],
                                        "sentido": p['Direction']['Description'],
                                        "faixa": p['Lane']['Description'],
                                        "kminicial": km_inicial,
                                        "kmfinal": km_final,
                                        "ismeasured": m['IsMeasured'],
                                        "itemcode": m['Contract']['Item']['CodeItemContract'],
                                        "itemdescription": m['Contract']['Item']['DescriptionItemContract'],
                                        "itemunit": m['Contract']['Item']['Unit'],
                                        "itemquantity": m['Contract']['Item']['Quantity'],
                                        "compositioncode": m['Contract']['ItemComposition']['Code'],
                                        "compositiondescription": m['Contract']['ItemComposition']['Description'],
                                        "compositionunit": m['Contract']['ItemComposition']['Unit'],
                                        "percentpendingpayment": m['PercentPendingPayment'],
                                        "quantity": m['Quantity'],
                                        "unitaryvalue": m['UnitaryValue'],
                                        "totalvalue": m['TotalValue'],
                                        "productionid": p['ProductionId']
                                    })

                    # Paginação                    
                    if page == productions['TotalPages'] or productions['TotalPages'] == 0:
                        page = 0
                    else:
                        page += 1

                # Gravar registros pendentes
                if measurement_records:
                    write_measurement_record(measurement_records, contract) # type: ignore
                    measurement_records = []

            # Próximo dia
            search_date += timedelta(days=1)

    def load_osiris_images():
        """
        Carregar imagens associadas aos apontamentos do OSIRIS
        """

        # Registros para carregamento de imagens
        _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_list_log_to_attach_images"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET",
                timeout=360)
        except Exception as e:
            logger.error(f"Falha ao obter lista para carga de imagens OSIRIS: {e}")

        if not data or not data["message"]: # type: ignore
            logger.info("Nenhum apontamento encontrado para carregamento de imagens")
            return

        try:
            session = create_session_and_login(OSIRIS_LOGIN, OSIRIS_PASSWORD)
        except Exception as e:
            logger.error(f"Falha ao criar sessão OSIRIS: {e}")
            return

        list_count = len(data["message"])
        count_record = 0
        total_record = 0
        str_reports = "("
        keys = {}

        for key, values in data["message"].items():
        
            page = 1
            last_page = 0

            # Consultar dados na API
            images = get_image(
                session, 
                page_number = page, 
                page_size = 100,
                production_id = key)        
            
            if images:
                logger.info(f"Imagens encontradas para o apontamento {key}: {len(images['Data'])}")

            time.sleep(1)  # Pequena pausa para evitar sobrecarga no servidor

            # # enquanto page > 0:
            # #     # Consultar dados na API
            # #     images = get_image(
            # #         session, 
            # #         page_number = page, 
            # #         page_size = 100,
            # #         production_id = p["productionid"])        
            #     
            # #     if images:
            # #         print(f"Imagens encontradas para o apontamento {p['productionid']}: {len(images['Data'])}")
            #     
            # #     if page == productions['TotalPages'] or productions['TotalPages'] == 0:
            # #         page = 0
            # #     else:
            # #         page += 1
    
    load_dotenv()

    # Obter a URL base e token das variáveis de ambiente
    API_BASE_URL = os.getenv("ARTERIS_API_BASE_URL")
    API_TOKEN = os.getenv("ARTERIS_API_TOKEN")

    # Carregar chaves do OSIRIS
    OSIRIS_LOGIN = os.getenv("OSIRIS_LOGIN")
    OSIRIS_PASSWORD = os.getenv("OSIRIS_PASSWORD")

    # Ativos
    _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_assets"
    try:
        data = custom_url(
            api_base_url=_url,
            api_token=API_TOKEN,
            method="GET",
            timeout=360)
    except Exception as e:
        logger.error(f"Falha ao obter ativos do OSIRIS: {e}")
        return None

    osiris_assets = data["message"] # type: ignore

    # Funções de trabalho
    _url = f"{API_BASE_URL}/method/arteris_app.api.osiris.get_work_roles"
    try:
        data = custom_url(
            api_base_url=_url,
            api_token=API_TOKEN,
            method="GET",
            timeout=360)
    except Exception as e:
        logger.error(f"Falha ao funções do OSIRIS: {e}")
        return None

    osiris_work_roles = data["message"] # type: ignore

    # Gravar feriados
    holidays_br.Brazil(start_date.year).update_holidays()
    if start_date.year != end_date.year:
        holidays_br.Brazil(end_date.year).update_holidays()

    load_osiris_data()

    if not ignore_images:
        load_osiris_images()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Processar dados do Osiris')
    
    # Adicionar argumentos opcionais para as datas
    parser.add_argument('--start-date', 
                        type=str,
                        help='Data de início no formato YYYY-MM-DD (padrão: ontem)')
    
    parser.add_argument('--end-date',
                        type=str, 
                        help='Data de fim no formato YYYY-MM-DD (padrão: hoje)')
    
    parser.add_argument('--contract-code',
                        type=str,
                        help='Código do contrato específico')

    parser.add_argument('--ignore-check',
                        action='store_true',
                        help='Ignorar verificações de dados nos contratos')
    
    parser.add_argument('--ignore-images',
                        action='store_true',
                        help='Ignora processamento das imagens')
    
    args = parser.parse_args()
    
    # Definir datas padrão ou usar as fornecidas
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
    
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.combine(date.today(), datetime.min.time())

    # start_date = datetime.strptime('2025-09-29', '%Y-%m-%d')
    # end_date = datetime.strptime('2025-10-06', '%Y-%m-%d')
    # args.ignore_check = True
    
    # Executar com os parâmetros
    create_osiris_measurement_records(start_date, end_date, args.contract_code, args.ignore_check, args.ignore_images)