"""
API client para comunicação com o SMI Arteris.

Propósito:
    Fornecer uma função simples e reutilizável para realizar requisições HTTP (GET, POST, PUT, DELETE)
    contra o backend do SMI Arteris, encapsulando headers, timeout e opções de verificação SSL.

Responsabilidades principais:
    - Construir e enviar requisições HTTP autenticadas com header Authorization.
    - Tratar serialização de payloads JSON e parsing de respostas JSON.
    - Gerenciar comportamento de verificação SSL (certificado customizado ou desabilitação controlada).
    - Aplicar timeout e tratamento básico de erros de rede/resposta HTTP.

Posição na arquitetura:
    Camada de integração/infraestrutura: componente cliente usado por camadas de serviço/negócio para
    acessar as APIs externas do SMI Arteris.

Dependências críticas:
    - requests (requisições HTTP)
    - python-dotenv (carregar variáveis de ambiente)
    - urllib3 (controle de avisos SSL)
    - Sistema de arquivos para certificados opcionais e variáveis de ambiente (.env)

Considerações de segurança:
    - Executar exclusivamente em rede isolada com o backend do SMI Arteris.
    - Evitar desabilitar verificação SSL em produção; a flag DISABLE_SSL_VERIFY só deve ser usada em dev/test.

Exemplo de uso básico:
    api_base = "https://api.exemplo.com/recursos"
    api_token = os.getenv("API_TOKEN")
    resp = custom_url(api_base, api_token, method="GET")
    if resp is not None:
            print(resp)
"""

import requests
import json
import os
import urllib3
import logging
from typing import Literal
from dotenv import load_dotenv

def custom_url(
        api_base_url: str, 
        api_token: str,
        params: dict = {},
        body: dict | str | None = None, 
        method: Literal["GET", "POST", "PUT", "DELETE"] = "GET", 
        timeout: int = 30):
    """
    Realiza uma requisição HTTP personalizada para a API do SMI Arteris.
    Paramêtros:
        api_base_url (str): URL base da API.
        api_token (str): Token de autenticação para o header Authorization.
        method (str): Método HTTP a ser usado ("GET", "POST", "PUT", "DELETE").
        body (dict or str, optional): Payload JSON para métodos que suportam corpo (POST, PUT).
        timeout (int, optional): Tempo máximo de espera pela resposta em segundos. Default é 30.
    Retorno:
        dict: Resposta JSON da API, ou None em caso de erro.
    """

    # Configuração básica de logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:

        # Carregar variáveis de ambiente do arquivo .env
        load_dotenv()

        # Construir URL completa e headers
        resource_url = f"{api_base_url}"
        headers = {
            "Authorization": api_token,
            "Content-Type": "application/json",
        }

        # Configuração SSL
        verify_ssl = True
        cert_path = None
        
        # Verificar variável de ambiente
        ssl_disable = os.getenv("DISABLE_SSL_VERIFY", "false").lower()

        # Verificar configuração SSL (prioridade: DISABLE_SSL_VERIFY)
        if ssl_disable == "true":
            verify_ssl = False
            logger.warning("Atenção: a verificação SSL está desabilitada.")
            # Desabilitar avisos de SSL
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Se não desabilitar, verificar se o certificado customizado existe
        elif os.path.exists("ssl-certs/arteris_com_br.crt"):
            cert_path = "ssl-certs/arteris_com_br.crt"
            verify_ssl = cert_path
            logger.info(f"Usando certificado customizado: {cert_path}")    

        # Serializar corpo se for string
        if body:
            if not isinstance(body, dict):
                body = json.loads(body)

        # Executar requisição conforme o método
        if method == "GET":
            if body:
                response = requests.get(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    timeout=timeout, 
                    json=body,
                    verify=verify_ssl)
            else:
                response = requests.get(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    timeout=timeout, 
                    verify=verify_ssl)

        elif method == "POST":
            # Incluir corpo se fornecido
            if body:
                response = requests.post(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    json=body, 
                    timeout=timeout, 
                    verify=verify_ssl)
            else:
                response = requests.post(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    timeout=timeout, 
                    verify=verify_ssl)
        elif method == "PUT":
            # Incluir corpo se fornecido
            if body:
                response = requests.put(
                    resource_url, headers=headers, 
                    params=params, 
                    json=body, 
                    timeout=timeout, 
                    verify=verify_ssl)
            else:
                response = requests.put(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    timeout=timeout, 
                    verify=verify_ssl)
        elif method == "DELETE":
            if body:
                response = requests.delete(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    json=body, 
                    timeout=timeout, 
                    verify=verify_ssl)
            else:
                response = requests.delete(
                    resource_url, 
                    headers=headers, 
                    params=params, 
                    timeout=timeout, 
                    verify=verify_ssl)

        # Lança HTTPError para respostas 4xx/5xx
        response.raise_for_status() 
        # Parsear resposta JSON
        data = response.json()

        return data
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição HTTP: {e}")
        return None
    
    except Exception as e:
        logger.exception("Erro inesperado: %s", e)
        return None
    