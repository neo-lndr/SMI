"""
Importador de FTD (Faturamento Direto) a partir de CSV
Propósito:
    Ler um arquivo CSV gerado pelo sistema SAP, filtrar e mapear linhas de
    "FATURAMENTO DIRETO" em estruturas agrupadas por nota fiscal e postar o
    payload consolidado para o endpoint da API responsável por criar FTDs.
Responsabilidades principais:
    - Detectar a codificação do arquivo CSV e ler o conteúdo com tratamento adequado.
    - Filtrar linhas relevantes e converter campos de data/numérico para formatos esperados.
    - Agrupar linhas por nota fiscal e construir o payload JSON esperado pela API.
    - Enviar o payload para a API remota (retry/timeout básico e tratamento de exceções).
Posição na arquitetura:
    Componente de camada de ingestão/integração que atua como um adaptador entre
    arquivos CSV (exportados do SAP) e o serviço HTTP da aplicação (arteris_app).
    Geralmente executado como utilitário CLI ou integrado em um pipeline de ETL.
Dependências críticas:
    - secure_api_client: cliente HTTP personalizado usado para chamar o endpoint FTD.
    - chardet: para detecção automática de codificação de arquivos.
    - python-dotenv (dotenv): para carregar ARTERIS_API_TOKEN e ARTERIS_API_BASE_URL.
    - Módulos padrão: csv, os, sys.
Considerações de segurança:
    - Segredos (ARTERIS_API_TOKEN) devem ser fornecidos via variáveis de ambiente; nunca logar tokens.
    - Validar e sanitizar caminhos de arquivos recebidos (evitar traversal).
    - Validar formatos de dados (datas, números) antes de enviar para a API para evitar injeção/erros.
    - Garantir TLS ao comunicar-se com a API (requests usa HTTPS se a URL for https://).
    - Tratar corretamente exceções de rede e evitar vazamento de informações sensíveis em mensagens de erro.
    - Limitar tempo de execução e tamanho do payload para mitigar DoS por arquivos maliciosos.
Exemplo de uso básico:
    CLI:
        python ftd.py /caminho/para/arquivo.csv
    Uso programático:
        import_ftd_from_csv("/caminho/para/arquivo.csv")

Modulo de importação de FTD (Faturamento Direto) a partir de um arquivo CSV.

"""

import csv
import requests
import chardet
import sys
import os
from dotenv import load_dotenv
from api_client import custom_url
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def import_ftd_from_csv(csv_path: str) -> None:
    """
    Importa FTD a partir de um arquivo CSV.
    Parâmetros:
        csv_path (str): Caminho para o arquivo CSV a ser processado.
    """

    load_dotenv()

    def _create_ftd(ftds: dict) -> dict | None:
        """
        Envia o payload de FTD para o endpoint da API.
        Parâmetros:
            ftds (dict): Dicionário estruturado de FTDs a serem criados.
        Retorno:
            dict ou None: Resposta da API ou None em caso de falha.
        """

        _url = f"{os.getenv('ARTERIS_API_BASE_URL')}/method/arteris_app.api.ftd.create_ftd"
        
        try:
            json_data = {
                "data": ftds
            }
            data = custom_url(
                api_base_url=_url,
                api_token=os.getenv("ARTERIS_API_TOKEN"),
                body=json_data,
                timeout=300,
                method="POST")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error: {e}")
            return None

    def parse_date(d: str) -> str:
        """
        Converte datas do formato DD/MM/AAAA ou AAAAMMDD para AAAA-MM-DD.
        
        Parâmetros:
            d (str): Data em formato string.
        
        Retorno:
            str: Data no formato AAAA-MM-DD.
        """
        if '/' in d:
            # Tratar formato de data com barras
            day, month, year = d.split('/')
        else:
            year = d[0:4]
            month = d[4:6]
            day = d[6:8]
        return f"{year}-{month}-{day}"

    def parse_float(value: str) -> float:
        """
        Converte strings numéricas com vírgulas e pontos para float.
        
        Parâmetros:
            value (str): String representando um número.
        
        Retorno:
            float: Valor numérico convertido.
        """
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", ".")
        return float(value)
    
    load_dotenv()
    
    ftds = {}

    # Detectar codificação do arquivo
    with open(csv_path, 'rb') as f:
        raw_data = f.read()
        encoding_result = chardet.detect(raw_data)
        detected_encoding = encoding_result['encoding']
    
    # Ler arquivo CSV com a codificação detectada
    with open(csv_path, encoding=detected_encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:

            # Filtrar apenas linhas de FATURAMENTO DIRETO
            if not row["Texto breve"].strip() == "FATURAMENTO DIRETO":
                continue

            # Extrair e converter campos necessários
            numero_pedido = row["Documento de compras"].strip()
            linha_pedido = int(row["Item"].strip())
            notafiscal = row["Referência"].strip()
            quantidade = parse_float(row["Quantidade"])
            valor_total = parse_float(row["Valor da fatura"])
            data_documento = parse_date(row["Data do documento"].strip())
            data_entrada = parse_date(row["Data de entrada"].strip())
            codigo_imposto = row["Código de imposto"].strip()
            unidade = row["Unid.prç.pedido"].strip()

            # Criar estrutura de carga
            _nota = {
                    "notafiscal": notafiscal,
                    "datadocumento": data_documento,
                    "dataentrada": data_entrada,
                    "linhas": []
            }
            _linha_pedido = {
                "numeropedido": numero_pedido,
                "linhapedido": linha_pedido,
                "quantidade": quantidade,
                "valortotal": valor_total,
                "documentomigo": 'N/A',
                "documentomiro": 'N/A',
                "codigoimposto": codigo_imposto,
                "unidade": unidade
            }

            # Adicionar ao dicionário de pedidos
            ftds.setdefault(notafiscal, _nota)["linhas"].append(_linha_pedido)

    if ftds:
        # Enviar pedidos para a API
        if not _create_ftd(ftds):
            logger.error("Falha ao criar FTDs via API.")

# ───────────────────────── main ──────────────────────────────
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Uso: python saporder.py <caminho_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    import_ftd_from_csv(csv_path)


