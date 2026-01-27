from fastapi import logger
import csv, requests
import os
import chardet
import sys
import api_client
import pandas as pd
from dotenv import load_dotenv
import time

# f69f2f0bc02c39f:449e2440843c0ee
# f69f2f0bc02c39f:9fb1e74594d77ac

def importar_saldos(csv_path: str):

    def _update_item(items: dict):

        api_token = os.getenv("ARTERIS_API_TOKEN")
        api_base_url = f"{os.getenv('ARTERIS_API_BASE_URL')}/method/arteris_app.api.contractitem.update_contract_item"
        try:
            json_data = {
                "item": items
            }
            data = api_client.custom_url(api_base_url, api_token, body=json_data, timeout=300, method="POST")
            return data

        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return None    

    def parse_date(d: str) -> str:
        if '/' in d:
            # Tratar formato de data com barras
            day, month, year = d.split('/')
        else:
            year = d[0:4]
            month = d[4:6]
            day = d[6:8]
        return f"{year}-{month}-{day}"

    def parse_int(value: str) -> int:
        int_value = 0
        try:                
            int_value = int(value)
        except:
            return int_value
        return int_value
        

    def parse_float(value: str) -> float:
        float_value = 0.0
        if not value:
            return 0.0
        try:
            float_value = float(value)
        except:
            return float_value
        return float_value  
    
    load_dotenv()

    items = {}


    df = pd.read_excel(csv_path)

    for index, row in df.iterrows():
        if pd.isna(row["Chave do item"]):
            continue
        if row["Subsidiária"] != 'Intervias':
            continue
        
        row = row.fillna('')

        name = row["Chave do item"]
        quantidade = parse_float(row["Quantidade"])
        valorunitario = parse_float(row["Valor unitário"])
        valortotal = parse_float(row["Valor total"])
        if (valortotal == 0):
            valortotal = quantidade * valorunitario
        saldoatual = parse_float(row["Saldo atual (R$)"])
        tipo = row['Tipo de calculo']
        pep = row['Código PEP']
        cidade = row['Cidade base']
        percentualhe = row['Percentual padrão para hora extra']
        h_dom = parse_float(row['Horas domingo'])
        h_seg = parse_int(row['Horas segunda'])
        h_ter = parse_int(row['Horas terça'])
        h_qua = parse_int(row['Horas quarta'])
        h_qui = parse_int(row['Horas quinta'])
        h_sex = parse_int(row['Horas sexta'])
        h_sab = parse_int(row['Horas sabado'])
        medido = parse_float(row['Quantidade acumulada'])

        # Criar estrutura de objeto
        items = {
                "name": name,
                "valortotal": valortotal,
                "saldoatual": saldoatual,
                "tipo": tipo,
                "pep": pep,
                "cidade": cidade,
                "percentualhe": percentualhe,
                "h_dom": h_dom,
                "h_seg": h_seg,
                "h_ter": h_ter,
                "h_qua": h_qua,
                "h_qui": h_qui,
                "h_sex": h_sex,
                "h_sab": h_sab,
                "medido": medido
        }

        # Meça o tempo necessário de cada requisição
        start_time = time.time()

        if not _update_item(items):
            print("Fail to update itens.")       

        elapsed_time = time.time() - start_time
        print(f"Elapsed time for request: {elapsed_time:.2f} seconds")

        time.sleep(0.05)

    