"""
Carga de feriados do Brasil e sincronização com a API da Arteris.

Propósito:
    Fornece utilitários para obter feriados do Brasil (nacionais e por subdivisão) para um ano
    e sincronizá-los com a API externa da Arteris.

Responsabilidades principais:
    - Coletar feriados base nacionais usando a biblioteca `holidays`.
    - Recuperar feriados por subdivisão (estados) e consolidar sem duplicatas.
    - Consultar a API para verificar se é necessário atualizar os feriados.
    - Enviar a lista consolidada de feriados para a API quando houver atualização.

Posição na arquitetura:
    Módulo de integração/serviço backend: componente utilitário usado por tarefas agendadas,
    scripts CLI ou serviços que precisam sincronizar o calendário de feriados com o sistema Arteris.

Dependências críticas:
    - holidays (python-holidays) para geração de feriados.
    - secure_api_client (módulo interno) responsável por chamadas HTTP à API da Arteris.

Considerações de segurança:
    - Armazenar tokens em variáveis de ambiente e nunca comitá-los em código-fonte.
    - Usar HTTPS para comunicar com a API e validar respostas antes de processar.

Exemplo de uso básico:
    year = 2025
    b = Brazil(year)
    result = b.update_holidays()
    print(result)
"""

import holidays
import os
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
from api_client import custom_url

class Brazil():
    """
    Feriados do Brasil.
    Vide: https://en.wikipedia.org/wiki/Public_holidays_in_Brazil
    """

    def __init__(self, year: int):
        # Inicializa o objeto com o ano e carrega os feriados base
        self.year = year
        self.country = "BR"
        self.holiday_base = holidays.country_holidays(country=self.country, years=[self.year], language='pt_BR')

    def update_holidays(self) -> dict:
        """
        Obter feriados para todas as subdivisões do Brasil do ano especificado.
        Retorno: 
            dict com feriados
        """

        # Carrega as variáveis de ambiente do arquivo .env, se existir
        load_dotenv()

        # Obtém a URL base e o token a partir das variáveis de ambiente
        API_BASE_URL = os.getenv("ARTERIS_API_BASE_URL")
        API_TOKEN = os.getenv("ARTERIS_API_TOKEN")

        # Verifica feriados
        _url = f"{API_BASE_URL}/method/arteris_app.api.holidays.check_holidays?year={self.year}"
        data = custom_url(
            api_base_url=_url,
            api_token=API_TOKEN,
            method = "GET")
        
        if not data or 'message' not in data or 'update' not in data['message']:
            return {"error": "Resposta invalida da API ao verificar feriados."}

        # Se houver atualização, compila a lista de feriados e envia para a API
        if (data['message']['update'] == True):

            # Feriados básicos do Brasil
            holidays_list=[]
            for base_holiday in self.holiday_base:
                holidays_list.append({
                    "uf": None,
                    "data": date(self.year, base_holiday.month, base_holiday.day).strftime("%Y-%m-%d"),
                    "descricao": self.holiday_base[base_holiday]
                })
                if self.holiday_base[base_holiday] == "Sexta-feira Santa":
                    c_day = datetime(self.year, base_holiday.month, base_holiday.day) + timedelta(days=62)
                    holidays_list.append({
                        "uf": None,
                        "data": date(c_day.year, c_day.month, c_day.day).strftime("%Y-%m-%d"),
                        "descricao": "Corpus Christi"
                    })

            # Feriados para cada subdivisão
            for subdivision in self.holiday_base.subdivisions:
                sbd_holidays = holidays.country_holidays(country=self.country, years=[self.year], language='pt_BR', subdiv=subdivision)
                for sbd_holiday in sbd_holidays:
                    sbd_date = date(self.year, sbd_holiday.month, sbd_holiday.day).strftime("%Y-%m-%d")
                    new_holiday = True
                    for hl in holidays_list:
                        if hl["descricao"] == sbd_holidays[sbd_holiday] and hl["data"] == sbd_date:
                            new_holiday = False
                            break
                    if new_holiday:
                        holidays_list.append({
                            "uf": subdivision,
                            "data": sbd_date,
                            "descricao": sbd_holidays[sbd_holiday]
                        })

            holidays_json = {"holidays": holidays_list}
            
            _url = f"{API_BASE_URL}/method/arteris_app.api.holidays.update_holidays"
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                body=holidays_json,
                method="POST")
            
            if not data or 'message' not in data:
                return {"error": "Resposta invalida da API ao atualizar feriados."}
            
            data = data["message"]        

        return data

if __name__ == "__main__":
    year = datetime.now().year
    brazil_holidays = Brazil(year)
    holidays_list = brazil_holidays.update_holidays()
