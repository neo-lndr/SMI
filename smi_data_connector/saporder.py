"""
Modulo para carga de pedidos SAP

Propósito:
    Fornece uma rotina para importar pedidos SAP a partir de um arquivo CSV, normalizar campos
    e enviar os pedidos em lotes para um endpoint remoto da API Arteris.

Responsabilidades principais:
    - Ler e detectar automaticamente a codificação de um CSV (delimitador ';') contendo pedidos SAP.
    - Agregar linhas por número de pedido e construir a estrutura JSON esperada pela API.
    - Enviar lotes de pedidos para os endpoints remotos de criação e limpeza (create_sap_orders / remove_orphan_sap_orders).
    - Tratar conversões básicas de tipos (datas, números com vírgula decimal) e filtros simples (contratos que começam com "CW").

Posição na arquitetura:
    - Camada de integração/importação: atua como um conector entre os arquivos de exportação SAP (CSV) e a API backend (arteris_app).
    - Deve ser usado como ferramenta de ingestão por processos offline ou jobs agendados que alimentam a aplicação central.

Dependências críticas:
    - api_client: cliente HTTP que faz as chamadas para os endpoints remotos.
    - security.get_env.load_dotenv / variáveis de ambiente: espera ARTERIS_API_TOKEN e ARTERIS_API_BASE_URL definidos.
    - chardet: para detectar a codificação do arquivo CSV.
    - csv (stdlib) para parsing e adição de regras de campo (delimitador ';').
    
Considerações de segurança:
    - Não exponha o ARTERIS_API_TOKEN em logs ou mensagens de erro. Use mecanismos seguros para armazenar e carregar segredos.
    
Exemplo de uso básico:
    # Assegure que as variáveis de ambiente ARTERIS_API_TOKEN e ARTERIS_API_BASE_URL estejam definidas
    # (por exemplo via .env carregado por security.get_env.load_dotenv()).
    csv_path = "/caminho/para/pedidos_sap.csv"

"""

import csv
import chardet
import sys
import logging
import os
from dotenv import load_dotenv
from api_client import custom_url

logger = logging.getLogger(__name__)

def import_sap_orders_from_csv(csv_path: str):

    def _create_sap_orders(orders: dict) -> bool:
        """
        Envia pedidos SAP para o endpoint remoto create_sap_orders.
        Parâmetros:
            orders: dicionário de pedidos agregados por número.
        """

        _url = f"{API_BASE_URL}/method/arteris_app.api.saporder.create_sap_orders"
        body = {
            "data": orders
        }
        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                body=body,
                method="POST",
                timeout=360)
            if not data:
                logger.error("Falha ao enviar pedidos SAP")
                return False
            logger.info(f"Sucesso ao enviar {len(orders)} pedidos SAP")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar pedido SAP: {e}")
            return False

    def parse_date(d: str) -> str:
        """
        Converte datas do formato 'YYYYMMDD' para 'YYYY-MM-DD'.
        Parâmetros:
            d: string de data no formato 'YYYYMMDD'.
        Retorna:
            string de data no formato 'YYYY-MM-DD'.
        """
        year = d[0:4]
        month = d[4:6]
        day = d[6:8]
        return f"{year}-{month}-{day}"

    load_dotenv()

    # Obter a URL base e token das variáveis de ambiente
    API_BASE_URL = os.getenv("ARTERIS_API_BASE_URL")
    API_TOKEN = os.getenv("ARTERIS_API_TOKEN")      

    orders = {}

    # Detectar codificação do arquivo
    with open(csv_path, 'rb') as f:
        raw_data = f.read()
        encoding_result = chardet.detect(raw_data)
        detected_encoding = encoding_result['encoding']
    
    # Ler arquivo CSV com a codificação detectada
    with open(csv_path, encoding=detected_encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=";")

        ultimo_numeropedido = None

        for row in reader:

            contrato = row["Referencia"].strip()

            # Verificar se o contrato começa com "CW"
            if not contrato[:2] == "CW":
                continue            

            numero_pedido = row["Documento compras"].strip()
            linha = int(row["Posición"].strip())
            centro_custo = row["Centro de coste"].strip()
            codigo_pep = row["Elemento PEP"].strip()
            capex_opex = "Capex" if row["Tipo de imputación"] == "O" else "Opex"
            quantidade = float(row["Cantidad de pedido"].replace(",", ".").strip())
            quantidade_saldo = float(row["Cantidad Pendiente de Recepcionar"].replace(",", ".").strip())
            valor_unitario = float(row["Precio neto pedido"].replace(",", ".").strip())
            valor_total = float(row["Valor neto de pedido"].replace(",", ".").strip())
            saldo = quantidade_saldo * valor_unitario
            data_inicial = parse_date(row["Fecha documento"].strip())
            data_final = parse_date(row["Fecha de entrega"].strip())
            reidi = float(row["Porc. Descuento Reidi"].replace(",", ".").strip()) if row["Porc. Descuento Reidi"].strip() else 0.0
            descricao = row["Texto breve"].strip()
            classe = row["Clase de pedido"].strip()
            contrato_marco = row["Contrato marco"].strip()

            # Criar estrutura do objeto
            _pedido = {
                    "numeropedido": numero_pedido,
                    "pep": codigo_pep,
                    "capexopex": capex_opex,
                    "contrato": contrato,
                    "contrato_marco": contrato_marco,
                    "classe": classe,
                    "descricao": descricao,
                    "linhas": []
            }
            _linha_pedido = {
                "datainicial": data_inicial,
                "datafinal": data_final,
                "linhapedido": linha,
                "centrodecusto": centro_custo,
                "pep": codigo_pep,
                "valorunitario": valor_unitario,
                "quantidade": quantidade,
                "quantidadesaldo": quantidade_saldo,
                "valortotal": valor_total,
                "saldo": saldo,
                "reidi": reidi
            }

            if not ultimo_numeropedido == numero_pedido:
                ultimo_numeropedido = numero_pedido
                if len(orders) >= 100:
                    # Enviar pedidos em lotes de 1000
                    if not _create_sap_orders(orders):
                        return
                    orders = {}

            # Adicionar ao dicionário de pedidos
            orders.setdefault(numero_pedido, _pedido)["linhas"].append(_linha_pedido)

    if orders:
        # Enviar quaisquer pedidos restantes
        _create_sap_orders(orders)
        

# ───────────────────────── main ──────────────────────────────
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python saporder.py <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    import_sap_orders_from_csv(csv_path)
