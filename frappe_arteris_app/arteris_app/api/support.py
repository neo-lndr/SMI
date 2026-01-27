"""
Classe para uso das APIs internas de outros containers
"""

from datetime import datetime, timedelta
import requests
import frappe
import time
from frappe import throw, _
from .measurement import delete_measurement

class measurement_data_support:

    def __init__(self, measurement_code: str):

        # Obter os dados necessarios para recarregar a medição
        measurement_data = frappe.db.sql("""
            SELECT 
                c.name AS id_contrato,
                c.contrato,
                cm.datainicialmedicao,
                cm.datafinaltrabalho AS datafinalmedicao,
                c.uuidkartado,
                c.uuidosiris
            FROM
                `tabContract Measurement` cm
                INNER JOIN `tabContract` c ON cm.contrato = c.name   
            WHERE
                cm.name = %s
        """, measurement_code, as_dict=True)       

        if not measurement_data:
            throw(f"Medição {measurement_code} não encontrada.")

        self.contract_id = measurement_data[0]['id_contrato']
        self.contract = measurement_data[0]['contrato']
        self.measurement_start_date = measurement_data[0]['datainicialmedicao']
        self.measurement_end_date = measurement_data[0]['datafinalmedicao']
        self.uuidkartado = measurement_data[0]['uuidkartado']
        self.uuidosiris = measurement_data[0]['uuidosiris']
        self.measurement = measurement_code


    def reload_measurement(self) -> dict:
        """
        Recarrega a medição de um contrato específico

        Retorna:
            dict - Resultado da operação
        """

        # Apagar a medição existente
        try:
            delete_measurement(self.measurement)
        except Exception as e:
            throw(f"Erro ao apagar medição existente: {e}")

        _url_base = "http://smi-data-connector-api:8085"

        # Recarregar os dados da medição
        _url = f"{_url_base}/import_data"
        # Dados para importação
        source_system = "kartado" if self.uuidkartado else "osiris" if self.uuidosiris else "both"
        payload = {
            "start_date": self.measurement_start_date.strftime("%Y-%m-%d"),
            "end_date": self.measurement_end_date.strftime("%Y-%m-%d"),
            "contract_code": self.contract,
            "source_system": source_system,
            "ignore_check": True,
            "ignore_images": True
        }    
        response = requests.post(_url, json=payload)
        if response.status_code != 200:
            throw(f"Erro ao iniciar tarefa: {response.json()}")
        
        task_id = response.json()["task_id"]
        start_time = datetime.now()
        status = "executando"

        # Grava o registro da task
        reload_doc = frappe.new_doc("Contract Measurement Reload")
        reload_doc.name = task_id
        reload_doc.contrato = self.contract_id
        reload_doc.medicao = self.measurement
        reload_doc.inicio = start_time
        reload_doc.status = status
        reload_doc.tipo = "Recarregar Medição"
        reload_doc.save(ignore_permissions=True)
        frappe.db.commit()

 
    def recalculate_measurement(self) -> dict:
        """
        Recalcula a medição de um contrato específico

        Retorna:
            dict - Resultado da operação
        """
    
        _url_base = "http://smi-h-engine-api:8084"

        # Recalcular a medição
        _url = f"{_url_base}/calculate"

        # Inicia o recálculo e retorna o task_id
        payload = {
            "measurement": self.measurement,
            "use_cached_data": False,
            "debug": True
        }  
        response = requests.post(_url, json=payload)
        if response.status_code != 200:
            throw(f"Erro ao iniciar tarefa: {response.json()}")

        task_id = response.json()["task_id"]
        start_time = datetime.now()
        status = "executando"

        # Grava o registro da task
        reload_doc = frappe.new_doc("Contract Measurement Reload")
        reload_doc.name = task_id
        reload_doc.contrato = self.contract_id
        reload_doc.medicao = self.measurement
        reload_doc.inicio = start_time
        reload_doc.status = status
        reload_doc.tipo = "Recalcular Medição"
        reload_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "measurement": self.measurement}


class contract_data_support:

    def __init__(self, contract_id: str):
        
        self.contract_id = contract_id

        # Obter os dados necessarios para carregar o contrato
        contract_data = frappe.db.sql("""
            SELECT
                c.name AS id_contrato,
                c.contrato,
                CASE
                    WHEN MAX(cm.datafinalmedicao) IS NULL THEN c.datainiciomedicao
                    WHEN MAX(cm.datafinalmedicao) > c.datainiciomedicao THEN MAX(cm.datafinalmedicao)
                    ELSE c.datainiciomedicao
                END AS datainicial,
                DATE(NOW()) AS datafinal,
                c.uuidkartado,
                c.uuidosiris
            FROM
                `tabContract` c
                LEFT JOIN `tabContract Measurement` cm ON cm.contrato = c.name
            WHERE
                NOT c.datainiciomedicao IS NULL AND
                c.name = %s
            GROUP BY
                c.name,
                c.contrato,
                c.datainiciomedicao
        """, contract_id, as_dict=True)     
        if not contract_data:
            throw(f"Contrato {contract_id} não encontrado ou data de inicio da medição nulo.")

        self.contract_code = contract_data[0]['contrato']
        self.contract_id = contract_data[0]['id_contrato']
        self.start_date = contract_data[0]['datainicial']
        self.end_date = contract_data[0]['datafinal']
        self.uuidkartado = contract_data[0]['uuidkartado']
        self.uuidosiris = contract_data[0]['uuidosiris']

    def load_contract_data(self):
        """
        Carrega os dados do contrato a partir do conector de dados

        Retorna:
            dict - Resultado da operação
        """

        source_system = "kartado" if self.uuidkartado else "osiris" if self.uuidosiris else "both"

        _url = "http://smi-data-connector-api:8085/import_data"
        # Dados para importação
        payload = {
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "end_date": self.end_date.strftime("%Y-%m-%d"),
            "contract_code": self.contract_code,
            "source_system": source_system,
            "ignore_check": True,
            "ignore_images": True
        }    
        response = requests.post(_url, json=payload)
        if response.status_code != 200:
            throw(f"Erro ao iniciar tarefa: {response.json()}")
        
        task_id = response.json()["task_id"]
        start_time = datetime.now()
        status = "executando"

        # Grava o registro da task
        reload_doc = frappe.new_doc("Contract Measurement Reload")
        reload_doc.name = task_id
        reload_doc.contrato = self.contract_id
        reload_doc.inicio = start_time
        reload_doc.status = status
        reload_doc.tipo = "Carregar contrato"
        reload_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "contract": self.contract_code}

def check_pending_process() -> bool:
    """
    Verifica se há processos pendentes

    Retorna:
        bool - True se houver processos pendentes, False caso contrário
    """

    pending = frappe.db.sql("""
        SELECT 
            name
        FROM
            `tabContract Measurement Reload`
        WHERE
            status = 'executando'
        LIMIT 1
    """, as_dict=True)

    if pending:
        if len(pending) >= 1:
            return True

    return False

@frappe.whitelist(methods=["POST"])
def taskcompleted(task_id: str, error: str):
    """
    Atualiza o status da tarefa de recarregamento ou recálculo de medição

    Args:
        task_id (str): ID da tarefa
        error (str, optional): Mensagem de erro, se houver. Defaults to None.

    Returns:
        dict: Resultado da operação
    """

    try:
        
        reload_doc = frappe.get_doc("Contract Measurement Reload", task_id)
        if not reload_doc:
            throw(f"Tarefa com ID {task_id} não encontrada.")

        reload_doc.status = "erro" if error else "concluido"
        reload_doc.fim = datetime.now()
        reload_doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Falha ao atualizar tarefa {task_id}: {e}")

    return {"success": True, "task_id": task_id, "error": error}
