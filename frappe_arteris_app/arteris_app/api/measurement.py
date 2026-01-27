import frappe
from frappe.utils import flt
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
from .cities_distributor import processar_distribuicao

class MeasurementType(Enum):
    """Tipos de medição disponíveis."""
    CUSTOM = "CUSTOM"      # Período customizado com dias específicos
    MONTHLY = "MENSAL"     # Período mensal (1º ao último dia do mês)

@dataclass
class ContractConfiguration:
    """Configuração do contrato para cálculos de período de medição."""
    measurement_type: MeasurementType
    approval_limit_day: int                    # Ex: 18
    initial_measurement_day: Optional[int] = None  # Ex: 16 (apenas para CUSTOM)
    final_measurement_day: Optional[int] = None    # Ex: 15 (apenas para CUSTOM)
    
    def __post_init__(self):
        """Valida a configuração após inicialização."""
        if self.measurement_type == MeasurementType.CUSTOM:
            if self.initial_measurement_day is None or self.final_measurement_day is None:
                raise ValueError("CUSTOM measurement type requires initial_measurement_day and final_measurement_day")
        elif self.measurement_type == MeasurementType.MONTHLY:
            if self.initial_measurement_day is not None or self.final_measurement_day is not None:
                raise ValueError("MONTHLY measurement type should not have initial_measurement_day or final_measurement_day")

class MeasurementPeriodCalculator:
    """Calculadora para determinar períodos de medição baseada em configurações de contrato."""
    
    def __init__(self, config: ContractConfiguration):
        self.config = config
    
    def _add_months(self, date: datetime, months: int) -> datetime:
        """
        Adiciona meses a uma data usando datetime nativo.
        
        Args:
            date: Data de origem
            months: Número de meses a adicionar
            
        Returns:
            datetime: Nova data com meses adicionados
        """
        month = date.month + months
        year = date.year
        
        # Lidar com overflow de ano
        while month > 12:
            month -= 12
            year += 1
        
        # Lidar com underflow de ano
        while month < 1:
            month += 12
            year -= 1
            
        return date.replace(year=year, month=month)
    
    def _subtract_months(self, date: datetime, months: int) -> datetime:
        """
        Subtrai meses de uma data usando datetime nativo.
        
        Args:
            date: Data de origem
            months: Número de meses a subtrair
            
        Returns:
            datetime: Nova data com meses subtraídos
        """
        return self._add_months(date, -months)
    
    def _get_last_day_of_month(self, date: datetime) -> int:
        """
        Obtém o último dia do mês de uma data específica.
        
        Args:
            date: Data de referência
            
        Returns:
            int: Último dia do mês
        """
        # Vai para o primeiro dia do próximo mês e subtrai um dia
        if date.month == 12:
            next_month_first_day = date.replace(year=date.year + 1, month=1, day=1)
        else:
            next_month_first_day = date.replace(month=date.month + 1, day=1)
        
        last_day_of_month = next_month_first_day - timedelta(days=1)
        return last_day_of_month.day
        
    def _get_period_for_execution_date(self, execution_date: datetime) -> tuple[datetime, datetime, datetime]:
        """
        Calcula o período de medição baseado na data de execução.
        
        Args:
            execution_date: Data em que o lançamento foi executado
            
        Returns:
            tuple: (inicio_periodo, fim_periodo, limite_aprovacao)
        """
        if self.config.measurement_type == MeasurementType.MONTHLY:
            return self._get_monthly_period(execution_date)
        else:  # CUSTOM
            return self._get_custom_period(execution_date)
    
    def _get_monthly_period(self, execution_date: datetime) -> tuple[datetime, datetime, datetime]:
        """
        Calcula período de medição MENSAL baseado na data de execução.
        
        Args:
            execution_date: Data em que o lançamento foi executado
            
        Returns:
            tuple: (inicio_periodo, fim_periodo, limite_aprovacao)
        """
        # Para medição mensal, o período é sempre do primeiro ao último dia do mês
        period_start = execution_date.replace(day=1)
        
        # Último dia do mês
        last_day = self._get_last_day_of_month(execution_date)
        period_end = execution_date.replace(day=last_day)
        
        # Limite de aprovação é no próximo mês
        next_month = self._add_months(execution_date.replace(day=1), 1)
        approval_limit = next_month.replace(day=self.config.approval_limit_day)
        
        return period_start, period_end, approval_limit
    
    def _get_custom_period(self, execution_date: datetime) -> tuple[datetime, datetime, datetime]:
        """
        Calcula período de medição CUSTOM baseado na data de execução.
        
        Args:
            execution_date: Data em que o lançamento foi executado
            
        Returns:
            tuple: (inicio_periodo, fim_periodo, limite_aprovacao)
        """
        # Determinar mês/ano de referência baseado na data de execução
        if execution_date.day >= self.config.initial_measurement_day:
            # Se a execução foi no dia inicial ou depois, o período é do mês atual
            reference_month = execution_date.replace(day=1)
        else:
            # Se foi antes do dia inicial, o período é do mês anterior
            reference_month = self._subtract_months(execution_date.replace(day=1), 1)
        
        # Calcular início do período (dia inicial do mês de referência)
        period_start = reference_month.replace(day=self.config.initial_measurement_day)
        
        # Calcular fim do período (dia final do próximo mês)
        next_month = self._add_months(reference_month, 1)
        period_end = next_month.replace(day=self.config.final_measurement_day)
        
        # Calcular limite de aprovação (baseado no mês do fim do período)
        approval_limit = next_month.replace(day=self.config.approval_limit_day)
        
        return period_start, period_end, approval_limit
    
    def _get_next_period(self, current_period_end: datetime) -> tuple[datetime, datetime]:
        """
        Calcula o próximo período de medição baseado no fim do período atual.
        
        Args:
            current_period_end: Data final do período atual
            
        Returns:
            tuple: (inicio_proximo_periodo, fim_proximo_periodo)
        """
        # O próximo período inicia no dia seguinte ao fim do período atual
        next_start = current_period_end + timedelta(days=1)
        next_start_date, next_end_date, _ = self._get_period_for_execution_date(next_start)
        
        return next_start_date, next_end_date
    
    def calculate_measurement_period(self, 
                                   execution_date: datetime, 
                                   approval_date: datetime) -> Dict[str, Any]:
        """
        Calcula o período de medição e determina se o lançamento deve ser incluído.
        
        Args:
            execution_date: Data em que o lançamento foi executado
            approval_date: Data em que o lançamento foi aprovado
            
        Returns:
            Dict: {
                "is_next": bool,
                "start_date": datetime,
                "end_date": datetime
            }
        """
        # Obter período baseado na data de execução
        period_start, period_end, approval_limit = self._get_period_for_execution_date(execution_date)
        
        # Verificar se a execução está dentro do período calculado
        if not (period_start <= execution_date <= period_end):
            raise ValueError(
                f"Execution date {execution_date.strftime('%Y-%m-%d')} "
                f"is not within calculated period "
                f"({period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')})"
            )
        
        # Determinar se deve incluir na medição atual
        if approval_date <= approval_limit:
            # Incluir no período atual
            return {
                "is_next": False,
                "start_date": period_start,
                "end_date": period_end
            }
        else:
            # Incluir no próximo período
            next_start, next_end = self._get_next_period(period_end)

            # Loop para procurar o próximo período válido
            return self.calculate_measurement_period(next_start, approval_date)
            # return {
            #     "is_next": True,
            #     "start_date": next_start,
            #     "end_date": next_end
            # }
        
@frappe.whitelist(methods=["GET"])
def close_measurements(contract: str):
    """
    Get current 
    """
    try:
        # Get all measurements for the contract
        measurements = frappe.db.get_all("Contract Measurement", fields=["name"], filters={"contrato": contract, "medicaovigente": "Sim"})

        if not measurements:
            return {"message": f"No open measurements found for contract {contract}."}

        # Close each measurement
        for measurement in measurements:
            frappe.db.sql("""
                UPDATE 
                    `tabContract Measurement`
                SET 
                    medicaovigente = 'Não'
                WHERE 
                    name = %s
            """, (measurement.name,))
            frappe.db.sql("""
                UPDATE 
                    `tabContract Measurement Record`
                SET 
                    medicaovigente = 'Não'
                WHERE 
                    boletimmedicao = %s
            """, (measurement.name,))

        return {"message": f"Closed {len(measurements)} measurements for contract {contract}."}
    except Exception as e:
        frappe.log_error(f"Error on close_measurements: {str(e)}", "Close Measurement Error")    
        return None

@frappe.whitelist(methods=["POST"])
def open_measurement(measurement: str):
    """
    Open measurement.
    """
    try:
        measurement = measurement.replace("\r","")

        # Get all measurements for the contract
        measurements = frappe.db.get_all("Contract Measurement", fields=["name","contrato"], filters={"name": measurement})

        # Close the measurement if it is open
        close_measurements(measurements[0].contrato) 

        if not measurements:
            return {"message": f"No measurements found for name {measurement}."}

        # Open each measurement
        for measurement in measurements:
            doc = frappe.get_doc("Contract Measurement", measurement.name)
            doc.medicaovigente = "Sim"
            doc.save()
            # Open all measurement records associated with this measurement
            measurement_records = frappe.db.get_all("Contract Measurement Record", fields=["name"], filters={"boletimmedicao": measurement.name})
            for record in measurement_records:
                record_doc = frappe.get_doc("Contract Measurement Record", record.name)
                record_doc.medicaovigente = "Sim"
                record_doc.save()

        return {"message": f"Open measurement {measurement}."}
    except Exception as e:
        frappe.log_error(f"Error on open_measurement: {str(e)}", "Measurement API")
        return None

@frappe.whitelist(methods=["POST"])
def get_measurement(current_date_str: str, execution_date_str: str, contract: str):
    
    # Dados do contrato
    get_contracts = frappe.db.get_all(
        "Contract", 
        fields=[
            "name",
            "contrato",
            "medicaopormes", 
            "medicaodiainicial",
            "diainicialtrabalho",
            "medicaodiafinal",
            "diafinaltrabalho"
        ], 
        filters=
        {
            "name": contract
        })
    current_contrat = get_contracts[0]

    # Verifica se há parametros para o contrato
    if (current_contrat.medicaodiainicial == 0 or 
        current_contrat.medicaodiafinal == 0) and (current_contrat.medicaopormes == 0):

        # Cria registro de inconsistencia
        integration_inconsistency = frappe.new_doc("Integration Inconsistency")
        integration_inconsistency.tipo = "Registro de medição"
        integration_inconsistency.dataehora = frappe.utils.now()
        integration_inconsistency.contrato = contract
        integration_inconsistency.observacoes = f"O contrato {current_contrat.contrato} não possui informações de datas validas para medição."
        integration_inconsistency.save(ignore_permissions=True)
        frappe.db.commit()        

        return None        

    current_contrat = get_contracts[0]    
    approval_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    execution_date = datetime.strptime(execution_date_str, "%Y-%m-%d")

    if (current_contrat['diafinaltrabalho'] and 
        not current_contrat['diafinaltrabalho'] == 0):
        last_day_approval = current_contrat['diafinaltrabalho']
    else:
        last_day_approval = current_contrat['medicaodiafinal']

    if (current_contrat['diainicialtrabalho'] and 
        not current_contrat['diainicialtrabalho'] == 0):
        first_day_approval = current_contrat['diainicialtrabalho']
    else:
        first_day_approval = current_contrat['medicaodiainicial']        

    # Monta a configuracao para a calculadora de datas
    if current_contrat['medicaopormes'] == 1:
        config = ContractConfiguration(
            measurement_type = MeasurementType.MONTHLY,
            approval_limit_day = last_day_approval
        )
    else:
        config = ContractConfiguration(
            measurement_type=MeasurementType.CUSTOM,
            initial_measurement_day = current_contrat['medicaodiainicial'],
            final_measurement_day = current_contrat['medicaodiafinal'],
            approval_limit_day = last_day_approval
        )        

    # Calcula o periodo
    calculator = MeasurementPeriodCalculator(config)
    calculator_result = calculator.calculate_measurement_period(execution_date, approval_date)

    start_date = calculator_result["start_date"].date()
    end_date = calculator_result["end_date"].date()

    # Medicao existente
    existing_measurements = frappe.db.get_all(
        "Contract Measurement", 
        fields = [
            "name",
            "datainicialmedicao",
            "datafinalmedicao",
            "medicaovigente",
            "datainicialtrabalho",
            "datafinaltrabalho",
        ],
        filters = {
            "status": "Aberto",
            "datainicialmedicao": start_date,
            "datafinalmedicao": end_date,
            "contrato": contract
        })    

    if existing_measurements:

        current_measurement = existing_measurements[0]

        measurements = [{
            "name": current_measurement['name'], 
            "contract": contract, 
            "start": current_measurement['datainicialmedicao'], 
            "end": current_measurement['datafinalmedicao'], 
            "approval_start": current_measurement["datainicialtrabalho"],
            "approval_end": current_measurement["datafinaltrabalho"],
            "current": current_measurement['medicaovigente']
        }]

        return {
            "measurements": measurements
        }        
    
    else:

        end_date_approval = end_date
        start_date_approval = start_date
        if current_contrat['medicaopormes'] == 1:
            # Verifica se o dia final de aprovação é diferente do dia final de medição
            if (not start_date.day == last_day_approval):
                if (end_date.month == 12):
                    end_date_approval = end_date_approval.replace(month=1, year=end_date_approval.year + 1, day = last_day_approval)
                    start_date_approval = end_date_approval.replace(month=12, year=start_date_approval.year, day = first_day_approval)
                else:
                    end_date_approval = end_date_approval.replace(month=end_date_approval.month + 1, day = last_day_approval)
                    start_date_approval = start_date   
        else:
            # Se o dia final de aprovacao maior que o dia final de medição
            if (last_day_approval > end_date.day):
                # Mesmo mes
                end_date_approval = end_date_approval.replace(day = last_day_approval)
                if end_date_approval.month == 1:
                    start_date_approval = start_date_approval.replace(day = first_day_approval, month = 1, year = end_date_approval.year - 1)
                else:
                    start_date_approval = start_date_approval.replace(day = first_day_approval, month = end_date_approval.month - 1, year = end_date_approval.year)
            else:
                # Proximo mes
                if (end_date.month == 12):
                    end_date_approval = end_date_approval.replace(month=1, year=end_date_approval.year + 1, day = last_day_approval)
                    start_date_approval = start_date_approval.replace(day = first_day_approval, month = 12, year = end_date_approval.year - 1)
                else:
                    end_date_approval = end_date_approval.replace(month=end_date_approval.month + 1, day = last_day_approval)
                    start_date_approval = start_date_approval.replace(day = first_day_approval, month = end_date_approval.month, year = end_date_approval.year)
    
        return _create_measurement(start_date, end_date, end_date_approval, start_date_approval, current_contrat)

def _create_measurement(start_date: date, end_date: date, end_date_approval: date, start_date_approval: date, contract):

    try: 

        measurements = []
        inconsistencies = []

        medicaoacumulada = 0.0
        caucaoacumulado = 0.0
        ftdacumulado = 0.0

        next_measurement = 0

        # Verifica se existe medição anterior
        last_contract_measurement = get_last_contract_measurement(contract.name)
        if last_contract_measurement:
            # Carrega valores da ultima medição
            medicaoacumulada = last_contract_measurement.medicaoacumulada
            caucaoacumulado = last_contract_measurement.caucaoacumulado
            ftdacumulado = last_contract_measurement.ftdacumulado
            next_measurement = int(last_contract_measurement.name[-3:])

        next_measurement += 1

        # Fecha as demais medições existentes
        close_measurements(contract.name)

        measurement = f"BM-{contract.contrato}-{next_measurement:03d}"
        contract_measurement = frappe.new_doc("Contract Measurement")
        contract_measurement.name = measurement
        contract_measurement.status = "Aberto"
        contract_measurement.contrato = contract.name
        contract_measurement.datainicialmedicao = start_date
        contract_measurement.datafinalmedicao = end_date
        contract_measurement.datainicialtrabalho = start_date_approval
        contract_measurement.datafinaltrabalho = end_date_approval
        contract_measurement.medicaovigente = "Sim"
        contract_measurement.data_ejak = contract.datainicial
        contract_measurement.obra = contract.obra
        contract_measurement.valorcontrato = contract.valortotal
        contract_measurement.medicaoatual = 0.0
        contract_measurement.faturamentodireto = 0.0
        contract_measurement.medicaoatualdescontoftd = 0.0
        contract_measurement.descontoreidi = 0.0
        contract_measurement.medicaoliquida = 0.0
        contract_measurement.medicaoequivalente = 0.0
        contract_measurement.caucaocontratual = 0.0
        contract_measurement.valortotalvigente = contract.valortotal
        contract_measurement.ftdacumulado = 0.0
        contract_measurement.totalvigentemenosftd = 0.0
        contract_measurement.medicaoacumulada = 0.0
        contract_measurement.saldo = 0.0
        contract_measurement.saldopercentual = 0.0
        contract_measurement.caucaoatual = 0.0
        contract_measurement.caucaoacumulado = 0.0
        contract_measurement.medicaoacumuladaanterior = medicaoacumulada
        contract_measurement.caucaoacumuladoanterior = caucaoacumulado
        contract_measurement.ftdacumuladoanterior = ftdacumulado

        # _create_measurement_items(contract_measurement, last_contract_measurement, contract_measurement.datainicialtrabalho, contract_measurement.datafinaltrabalho, contract_measurement.contrato)
        _create_measurement_items(contract_measurement, last_contract_measurement, contract_measurement.datainicialmedicao.strftime("%Y-%m-%d"), contract_measurement.datafinalmedicao.strftime("%Y-%m-%d") , contract_measurement.contrato)

        # Add the contract measurement to the database
        contract_measurement.save(ignore_permissions=True)
        measurements.extend([{
            "name": contract_measurement.name, 
            "contract": contract.name, 
            "start": contract_measurement.datainicialmedicao, 
            "end": contract_measurement.datafinalmedicao, 
            "approval_start": contract_measurement.datainicialtrabalho, 
            "approval_end": contract_measurement.datafinaltrabalho, 
            "current": contract_measurement.medicaovigente
        }])

        return { "measurements": measurements }
    
    except Exception as e:
        frappe.log_error(f"Error on create_measurement: {str(e)}", "Measurement API")    
        return None        

def get_last_contract_measurement(contract, measurement = None):        
    last_contract_measurement = None
    try:
        if measurement:
            last_contract_measurement = frappe.get_last_doc("Contract Measurement", filters={"contrato": contract, "name": ["!=", measurement]})
        else:
            last_contract_measurement = frappe.frappe.get_last_doc("Contract Measurement", filters={"contrato": contract})
    except Exception as e:
        last_contract_measurement = None
    return last_contract_measurement

@frappe.whitelist(methods=["POST"])
def create_measurement_items(measurement: str):
    """
    Create measurement items for the measurement.
    """
    try:
        contract_measurement = frappe.get_doc("Contract Measurement", measurement)
        last_contract_measurement = get_last_contract_measurement(contract_measurement.contrato, measurement)
        contract_measurement.set("tabitenscontatrato", [])
        contract_measurement.set("tablemaodeobra", [])
        contract_measurement.set("tableativos", [])
        # _create_measurement_items(contract_measurement, last_contract_measurement, contract_measurement.datainicialtrabalho.strftime("%Y-%m-%d"), contract_measurement.datafinaltrabalho.strftime("%Y-%m-%d"), contract_measurement.contrato)
        _create_measurement_items(contract_measurement, last_contract_measurement, contract_measurement.datainicialmedicao.strftime("%Y-%m-%d"), contract_measurement.datafinalmedicao.strftime("%Y-%m-%d"), contract_measurement.contrato)
        contract_measurement.save(ignore_permissions=True)
        return {"message": f"Created items for measurement {measurement}."} 
    except Exception as e:
        frappe.log_error(f"Error on create_measurement_items: {str(e)}", "Measurement API")    
        return None            

def _create_measurement_items(contract_measurement, last_contract_measurement, first_day, last_day, contract):

    try:
            
        holidays = {}

        # Function to check if a date is a holiday
        def check_holiday(date: date, uf: str, city: str):

            key = f"{date.strftime('%Y-%m-%d')}-{city}-{uf}"
            if holidays.get(key, None) == None:
                if not city == "all":
                    get_result = frappe.db.get_all("Holiday", fields=["data","descricao"], filters={"data": date, "cidade": city})
                elif not uf == "all":
                    get_result = frappe.db.get_all("Holiday", fields=["data","descricao"], filters={"data": date, "uf": uf})
                else:
                    get_result = frappe.db.get_all("Holiday", fields=["data","descricao"], filters={"data": date, "uf": "", "cidade": ""})
                if get_result:
                    holidays[key] = {
                        "isholiday": True,
                        "uf": "" if uf == "all" else uf,
                        "cidade": "" if city == "all" else city,
                        "descricao": get_result[0].descricao
                    }
                else:
                    holidays[key] = {
                        "isholiday": False
                    }
            return holidays[key]

        def check_holidays(date: date, city: str = None):

            # City and UF is a key of city
            uf = "all"
            if city:
                s_sity = city.split("-")
                uf = s_sity[1]
                city = s_sity[0]
            else:
                city = "all"
                uf = "all"

            # Check if the date is a holiday
            holiday = check_holiday(date, "all", "all")
            if holiday['isholiday']:
                return holiday
            holiday = check_holiday(date,  uf, "all")
            if check_holiday(date, uf, "all"):
                return holiday
            holiday = check_holiday(date, "all", city)
            if check_holiday(date, "all", city):
                return holiday

        def get_busy_days(start_date: date, end_date: date, city: str = None) -> int:

            busy_days = 0
            
            while start_date <= end_date:
                holiday = check_holidays(start_date, city)
                if not holiday['isholiday']:
                    # 0-4 is business days (Monday to Friday)
                    if start_date.weekday() < 5:  
                        busy_days += 1
                start_date += timedelta(days=1)
            
            return busy_days
        
        # Get Contract Items
        get_contract_items = frappe.db.sql("""
            SELECT
                item.name,
                item.codigo,
                item.tipodoitem,
                item.valortotalvigente,
                item.quantidade,
                item.valorunitario,
                item.cidade,
                item.aplicar_performance,
                item.fatorpagamento
            FROM
                `tabContract Item` item
            WHERE
                item.contrato = %s AND 
                NOT item.codigo LIKE 'Contrato %%' AND 
                NOT item.is_group = 1 
            ORDER BY
                INET_ATON(SUBSTRING_INDEX(CONCAT(item.codigo,'.0.0.0.0.0.0.0.0'), '.', 8))
        """, (contract,), as_dict=True)

        for item in get_contract_items:

            busy_days = get_busy_days(
                datetime.strptime(first_day, "%Y-%m-%d"), 
                datetime.strptime(last_day, "%Y-%m-%d"), 
                item.cidade)
            # busy_days = get_busy_days(
            #     first_day, 
            #     last_day, 
            #     item.cidade)

            # Set the value to valortotalvigente if it is 0.0
            if item.valortotalvigente == 0.0:
                if item.quantidade:
                    item.quantidade = 0.0
                if item.valorunitario:
                    item.valorunitario = 0.0
                item.valortotalvigente = item.quantidade * item.valorunitario

            saldo = 0.0
            valortotalacumulado = 0.0
            quantidadeacumulada = 0.0

            # Get last contract measurement item
            if last_contract_measurement:

                try:
                    last_measurement_item = frappe.get_last_doc("Contract Measurement Item", filters={"itemcontrato": item.name, "parent": last_contract_measurement.name})
                except Exception as e:
                    last_measurement_item = None
                    # frappe.log_error(f"Error getting last contract measurement item: {str(e)}", "Create Measurement Error")

                if last_measurement_item:
                    saldo = last_measurement_item.saldoatual
                    valortotalacumulado = last_measurement_item.valortotalmedido
                    quantidadeacumulada = last_measurement_item.quantidademedida

            # Mount the contract item to the contract measurement
            contract_measurement_item = contract_measurement.append("tabitenscontatrato")
            contract_measurement_item.itemcontrato = item.name
            contract_measurement_item.tipodoitem = item.tipodoitem
            contract_measurement_item.valortotalvigente = item.valortotalvigente
            contract_measurement_item.quantidadetotalvigente = item.quantidade
            contract_measurement_item.saldoanterior = saldo
            contract_measurement_item.quantidademedida = 0.0
            contract_measurement_item.valortotalmedido = 0.0
            contract_measurement_item.saldoatual = 0.0
            contract_measurement_item.valortotalacumuladoanterior = valortotalacumulado
            contract_measurement_item.quantidadeacumuladaanterior = quantidadeacumulada                
            contract_measurement_item.valortotalacumulado = 0.0
            contract_measurement_item.quantidadeacumulada = 0.0
            contract_measurement_item.fatorpagamento = 100.0 # Não aplicar fator de pagamento na criação da medição
            contract_measurement_item.valorfatorpagamento = 0.0
            contract_measurement_item.cidade = item.cidade
            contract_measurement_item.diasuteis = busy_days
            contract_measurement_item.valorunitario = item.valorunitario
            contract_measurement_item.aplicar_performance = item.aplicar_performance
            contract_measurement_item.quantidademedidarecursos = 0.0
            contract_measurement_item.valortotalmedidorecursos = 0.0
            contract_measurement_item.quantidademedidaativos = 0.0
            contract_measurement_item.valortotalmedidoativos = 0.0
            contract_measurement_item.quantidademedidamo = 0.0
            contract_measurement_item.valortotalmedidomo = 0.0
            contract_measurement_item.valorpago = 0.0
            contract_measurement_item.valortotalmedidopc = 0.0
            contract_measurement_item.quantidademedidapc = 0.0

            # Get Work Role
            item_work_roles = frappe.db.get_all("Contract Item Work Role", fields=["*"], filters={"parent": item.name})
            if item_work_roles:
                for work_role in item_work_roles:
                    if not item.item in contract_measurement.tablemaodeobra:
                        # Mount the Work Role to the contract measurement
                        contract_measurement_work_role = contract_measurement.append("tablemaodeobra")
                        contract_measurement_work_role.item = item.name
                        contract_measurement_work_role.tipoitem = item.tipoitem
                        contract_measurement_work_role.funcao = work_role.funcao
                        contract_measurement_work_role.quantidademedida = 0.0
                        contract_measurement_work_role.valormedido = 0.0
                        contract_measurement_work_role.quantidade = work_role.quantidade
                        contract_measurement_work_role.totaldias = busy_days
                        if work_role.pagamentohora:
                            contract_measurement_work_role.valorunitario = work_role.valorporhora
                        else:
                            contract_measurement_work_role.valorunitario = work_role.valortotalmensal

            # Get Asset
            item_assets = frappe.db.get_all("Contract Item Asset", fields=["*"], filters={"parent": item.name})
            if item_assets:
                for asset in item_assets:
                    if not item.item in contract_measurement.tableativos:
                        # Mount the Asset to the contract measurement
                        contract_measurement_asset = contract_measurement.append("tableativos")
                        contract_measurement_asset.item = item.name
                        contract_measurement_asset.tipoitem = item.tipoitem
                        contract_measurement_asset.maquina_equipamento_ou_ferramenta = asset.asset
                        contract_measurement_asset.quantidademedida = 0.0
                        contract_measurement_asset.valormedido = 0.0
                        contract_measurement_asset.valorunitario = asset.valormensal
                        contract_measurement_asset.quantidade = asset.quantidade
                        contract_measurement_asset.totaldias = busy_days
    except Exception as e:
        frappe.log_error(f"Error on _create_measurement_items: {str(e)}", "Measurement API")    
        return None    

@frappe.whitelist(methods=["POST"])
def update_measurement_records(measurement: str):
    """
    Sum all measurement orders for a given measurement.
    """
    try:
        # Get the measurement document
        measurement_doc = frappe.db.get_all("Contract Measurement",["workflow_state", "name"], filters={"name": measurement})

        # Update measurement items only if the measurement is active
        if measurement_doc[0]["workflow_state"] == "Aberto":

            # Atualiza o valor de reajuste retroativo se existir
            frappe.db.sql("""
                UPDATE
                    `tabContract Measurement Item` cmi
                    INNER JOIN (
                        SELECT
                            cmi.name as cmi_name,
                            SUM(cad.saldopagamento) as total_saldo
                        FROM
                            `tabContract Adjustment` ca
                            INNER JOIN `tabContract Adjustment Data` cad ON cad.parent = ca.name
                            INNER JOIN `tabContract Measurement Item` cmi ON cmi.itemcontrato = cad.item
                                                                        AND cmi.parent = ca.boletimmedicao
                        WHERE
                            ca.boletimmedicao = %s
                            AND ca.docstatus = 1
                            AND cad.saldopagamento <> 0
                        GROUP BY
                            cmi.name
                    ) AS aggregated ON cmi.name = aggregated.cmi_name
                SET
                    cmi.valorretroativo = aggregated.total_saldo;
            """, (measurement,))

            # Atualiza o valor total vigente caso seja nulo ou zero
            frappe.db.sql("""
                UPDATE
                    `tabContract Measurement` m
                    INNER JOIN `tabContract` c ON m.contrato = c.name
                SET
                    m.valortotalvigente = c.valortotal
                WHERE
                    (
                        m.valortotalvigente IS NULL OR
                        m.valortotalvigente = 0
                    ) AND
                    m.name = %s
            """, (measurement,))

            # Update maesurement items
            frappe.db.sql("""
                UPDATE
                    `tabContract Measurement Item` m_item
                    INNER JOIN `tabContract Item` i ON m_item.itemcontrato = i.name
                SET 
                    m_item.valorunitario = i.valorunitario,
                    m_item.valortotalvigente = i.valortotalvigente,
                    m_item.tipodoitem = i.tipodoitem,
                    m_item.aplicar_performance = i.aplicar_performance
                WHERE 
                    m_item.parent = %s;
                """, 
                (measurement,))

            # Update work roles
            frappe.db.sql("""   
                UPDATE 
                    `tabContract Measurement Work Role` work_role
                    INNER JOIN `tabContract Item` i ON i.name = work_role.item
                    INNER JOIN `tabContract Item Work Role` w ON w.parent = i.name and w.funcao = work_role.funcao 
                    INNER JOIN `tabContract Measurement Item` m_item ON m_item.itemcontrato = i.name
                SET 
                    work_role.valorunitario =   CASE 
                                                    WHEN 
                                                        (CASE WHEN w.valorporhora IS NULL THEN 0 ELSE w.valorporhora END) +
                                                        (CASE WHEN w.valortotalmensal IS NULL THEN 0 ELSE w.valortotalmensal END) = 0
                                                    THEN i.valorunitario
                                                    WHEN 
                                                        w.pagamentohora 
                                                    THEN w.valorporhora 
                                                    ELSE w.valortotalmensal 
                                                END,
                    work_role.quantidade = w.quantidade,
                    work_role.tipodoitem = i.tipodoitem,
                    work_role.totaldias = m_item.diasuteis,
                    work_role.percentualhe = i.percentualhe
                WHERE 
                    work_role.parent = %s;
                """, 
                (measurement,))       

            # Update assets
            frappe.db.sql("""
                UPDATE 
                    `tabContract Measurement Asset` asset
                    INNER JOIN `tabContract Item` i ON i.name = asset.item
                    INNER JOIN `tabContract Item Asset` a ON a.parent = i.name and a.asset = asset.maquina_equipamento_ou_ferramenta
                    INNER JOIN `tabContract Measurement Item` m_item ON m_item.itemcontrato = i.name
                SET 
                    asset.valorunitario =   CASE 
                                                WHEN 
                                                    a.valormensal IS NULL 
                                                THEN i.valorunitario
                                                WHEN 
                                                    a.valormensal = 0 
                                                THEN i.valorunitario
                                                ELSE a.valormensal 
                                            END,
                    asset.quantidade = a.quantidade,
                    asset.tipodoitem = i.tipodoitem,
                    asset.totaldias = m_item.diasuteis,
                    asset.percentualhe = i.percentualhe
                WHERE 
                    asset.parent = %s
                """, 
                (measurement,))

            # Update maesurement record items
            sql_update = """
                UPDATE 
                    `tabContract Measurement Record` record
                    INNER JOIN `tabContract Measurement Record Resource` resource ON resource.parent = record.name
                    INNER JOIN `tabContract Item` item ON item.name = resource.item
                SET 
                    resource.valorunitario = item.valorunitario,
                    resource.valorcalculado = ROUND(item.valorunitario * resource.quantidademedida,2)
                WHERE 
                    record.boletimmedicao = %s
                    AND (
                        item.produtividadecompensatoria = 0 OR 
                        item.produtividadecompensatoria IS NULL
                        );
                """
            frappe.db.sql(sql_update,(measurement,))

            # Update measurement record work roles
            frappe.db.sql("""
                UPDATE 
                    `tabContract Measurement Record Work Role` work_role
                    INNER JOIN `tabContract Measurement Record` record ON work_role.parent = record.name
                    INNER JOIN `tabContract Item` i ON i.name = work_role.item
                    INNER JOIN `tabContract Item Work Role` w ON w.parent = i.name AND w.funcao = work_role.funcao 
                SET 
                    work_role.valorunitario =   CASE 
                                                    WHEN 
                                                        (CASE WHEN w.valorporhora IS NULL THEN 0 ELSE w.valorporhora END) +
                                                        (CASE WHEN w.valortotalmensal IS NULL THEN 0 ELSE w.valortotalmensal END) = 0
                                                    THEN i.valorunitario
                                                    WHEN 
                                                        w.pagamentohora 
                                                    THEN w.valorporhora 
                                                    ELSE w.valortotalmensal
                                                END,
                    work_role.valorcalculado =  ROUND(
                                                    CASE 
                                                        WHEN 
                                                            (CASE WHEN w.valorporhora IS NULL THEN 0 ELSE w.valorporhora END) +
                                                            (CASE WHEN w.valortotalmensal IS NULL THEN 0 ELSE w.valortotalmensal END) = 0
                                                        THEN i.valorunitario
                                                        WHEN 
                                                            w.pagamentohora 
                                                        THEN w.valorporhora 
                                                        ELSE w.valortotalmensal
                                                    END * work_role.quantidademedida
                                                , 2)
                WHERE 
                    record.boletimmedicao = %s;
                """, 
                (measurement,))    

            # Update measurement record assets
            frappe.db.sql("""
                UPDATE 
                    `tabContract Measurement Record` record
                    INNER JOIN `tabContract Measurement Record Asset` asset ON asset.parent = record.name
                    INNER JOIN `tabContract Item` i ON i.name = asset.item
                    INNER JOIN `tabContract Item Asset` a ON a.parent = i.name and a.asset = asset.maquina_equipamento_ou_ferramenta
                SET 
                    asset.valorunitario =   CASE 
                                                WHEN 
                                                    a.valormensal IS NULL 
                                                THEN i.valorunitario
                                                WHEN 
                                                    a.valormensal = 0 
                                                THEN i.valorunitario
                                                ELSE a.valormensal 
                                            END,
                    asset.valorcalculado = ROUND(
                                                CASE 
                                                    WHEN 
                                                        a.valormensal IS NULL 
                                                    THEN i.valorunitario
                                                    WHEN 
                                                        a.valormensal = 0 
                                                    THEN i.valorunitario
                                                    ELSE a.valormensal 
                                                END * asset.quantidademedida
                                            , 2)                                            
                WHERE record.boletimmedicao = %s;
                """, 
                (measurement,))

        return {"Processed": True} #, "message": "Records updated successfully.", "count": count_update}
    except Exception as e:
        frappe.log_error(f"Error on update_measurement_records: {str(e)}", "Measurement API")    
        return None

@frappe.whitelist(methods=["POST"])
def sumarize_measurement(measurement: str):
    """
    Summarize measurement data.
    """
    try:
        sum_measurement_ftd(measurement)
        sum_measurement_records_work_role(measurement)
        sum_measurement_records_asset(measurement)
        sum_measurement_items(measurement)
        sum_cover(measurement)
        sum_cities(measurement)
    except Exception as e:
        frappe.log_error(f"Error on sumarize_measurement: {str(e)}", "Measurement API")    
        return None

@frappe.whitelist(methods=["POST"])
def sum_cover(measurement: str):

    try:

        # FDT
        total_ftd = 0.0
        ftd_data = frappe.db.sql("""
                        SELECT 
                            SUM(valor) AS total
                        FROM
                            `tabContract Measurement FTD`
                        WHERE
                            parent = %s;
                        """, (measurement,), as_dict=True)
        if ftd_data:
            total_ftd = ftd_data[0]['total'] if ftd_data[0]['total'] else 0.0

        # Items
        total_items = 0.0
        items_data = frappe.db.sql("""
                        SELECT 
                            SUM(valorpago) AS total
                        FROM
                            `tabContract Measurement Item`
                        WHERE
                            parent = %s;
                        """, (measurement,), as_dict=True)    
        if items_data:
            total_items = items_data[0]['total'] if items_data[0]['total'] else 0.0

        # Reidi
        total_reidi = 0.0
        reidi_data = frappe.db.sql("""
                        SELECT 
                            SUM(valor_medicao_reidi) AS total
                        FROM
                            `tabContract Measurement SAP Order`
                        WHERE
                            parent = %s;
                        """, (measurement,), as_dict=True)   
        if reidi_data:
            total_reidi = reidi_data[0]['total'] if reidi_data[0]['total'] else 0.0                

        # Caução
        total_caucao = 0.0
        caucao_data = frappe.db.sql("""
                        SELECT
                            c.valortotal,
                            c.percentualcalcao,
                            c.tetopercentualcalcao,
                            m.caucaoacumuladoanterior
                        FROM
                            `tabContract Measurement` m
                            INNER JOIN `tabContract` c ON c.name = m.contrato
                        WHERE
                            m.name = %s
                        """, (measurement,), as_dict=True)   
        if caucao_data:
            valor_do_contrato = caucao_data[0]['valortotal'] if caucao_data[0]['valortotal'] else 0.0
            percentual_caucao = caucao_data[0]['percentualcalcao'] if caucao_data[0]['percentualcalcao'] else 0.0
            teto_caucao = caucao_data[0]['tetopercentualcalcao'] if caucao_data[0]['tetopercentualcalcao'] else 0.0
            caucao_acumulado_anterior = caucao_data[0]['caucaoacumuladoanterior'] if caucao_data[0]['caucaoacumuladoanterior'] else 0.0
            if percentual_caucao > 0:
                percentual_caucao = flt(percentual_caucao/100,3)
                teto_caucao = flt(teto_caucao/100,3)  
                medicao_com_reidi = total_items - total_reidi
                valor_caucao_atual = flt(percentual_caucao * medicao_com_reidi,2)
                valor_teto = flt(teto_caucao * valor_do_contrato,2)
                acumulado_caucao = caucao_acumulado_anterior
                valor_caucao = 0.0
                if acumulado_caucao + teto_caucao > valor_teto or teto_caucao == 0:
                    valor_caucao = valor_caucao_atual  
                total_caucao = valor_caucao   

        # Saldo de pagamento atual
        remaining = frappe.db.sql("""
            SELECT
                SUM(cmir.saldo) AS saldo
            FROM
                `tabContract Measurement Item Remaining` cmir
                INNER JOIN `tabContract Measurement`cm ON cm.contrato=cmir.contrato
            WHERE
                NOT cmir.saldo = 0
                AND cm.name = %s            
        """,
        (measurement,),
        as_dict=True)

        saldo_pagamento = 0.0
        if remaining:
            saldo_pagamento = remaining[0]['saldo']        

        if not saldo_pagamento:
            saldo_pagamento = 0.0

        # Atualiza os valores
        frappe.db.sql("""
                        UPDATE
                            `tabContract Measurement`
                        SET
                            medicaoatual = %s,
                            faturamentodireto = %s,
                            medicaoatualdescontoftd = %s,
                            descontoreidi = %s,
                            medicaoliquida = %s,
                            medicaoequivalente = %s,
                            caucaocontratual = %s,
                            ftdacumulado = %s + ftdacumuladoanterior,
                            totalvigentemenosftd = %s,
                            medicaoacumulada = %s + medicaoacumuladaanterior,
                            saldo = (valortotalvigente - (medicaoacumuladaanterior + %s)) - %s,
                            saldopercentual = CASE 
                                WHEN valortotalvigente = 0 
                                    THEN 0
                                    ELSE ROUND(((valortotalvigente - (medicaoacumuladaanterior + %s)) / valortotalvigente) * 100, 3)
                            END,
                            caucaoatual = %s,
                            caucaoacumulado = caucaoacumuladoanterior + %s,
                            saldopagamento = %s
                        WHERE
                            name = %s
                        """, (
                            total_items, # medicaoatual = %s,0
                            total_ftd, # faturamentodireto = %s,0
                            total_items - total_ftd, # medicaoatualdescontoftd = %s,
                            total_reidi, # descontoreidi = %s,
                            total_items - total_ftd - total_reidi, # medicaoliquida = %s,
                            total_items - total_ftd - total_reidi, # medicaoequivalente = %s,
                            total_caucao, # caucaocontratual = %s,
                            total_ftd, # ftdacumulado = %s + ftdacumuladoanterior,
                            total_items - total_ftd, # totalvigentemenosftd = %s,
                            total_items, # medicaoacumulada = %s + medicaoacumuladaanterior,

                            total_items, # saldo = %s,
                            saldo_pagamento, # saldo = %s,

                            total_items, # saldopercentual = %s,
                            total_caucao, # caucaoatual = %s,
                            total_caucao, # caucaoacumulado = caucaoacumuladoanterior + %s
                            saldo_pagamento,  # saldopagamento 
                            measurement)) 
    except Exception as e:
        frappe.log_error(f"Error on cum_cover: {str(e)}", "Measurement API")    
        return None           

@frappe.whitelist(methods=["POST"])
def sum_measurement_ftd(measurement: str):
    """
    Sum all FTD values for a given measurement.
    """
    try:
        # Get all FTD values for the measurement
        ftd_values = frappe.db.get_all("Contract Measurement FTD", fields=["valor"], filters={"parent": measurement})

        total_ftd = 0.0
        for ftd in ftd_values:
            total_ftd += ftd.valor

        # Update the measurement document with the total FTD value
        frappe.db.set_value("Contract Measurement", measurement, "faturamentodireto", total_ftd)

        return {"Total": total_ftd}
    except Exception as e:
        frappe.log_error(f"Error on sum_measurement_ftd: {str(e)}", "Measurement API")    
        return None               

@frappe.whitelist(methods=["POST"])
def update_hours_measurement_record(measurement: str):
    """
    Udate hours records
    """
    try:
        # get body data and relations from the request
        # record_type = frappe.form_dict.type
        items = {}
        holidays = {}
        # totals = {}

        # Function to check if a date is a holiday
        def check_holiday(date: date, uf: str, city: str):

            key = f"{date.strftime('%Y-%m-%d')}-{city}-{uf}"
            if holidays.get(key, None) == None:
                if not city == "all":
                    get_result = frappe.db.get_all("Holiday", fields=["data","descricao"], filters={"data": date, "cidade": city})
                elif not uf == "all":
                    get_result = frappe.db.get_all("Holiday", fields=["data","descricao"], filters={"data": date, "uf": uf})
                else:
                    get_result = frappe.db.get_all("Holiday", fields=["data","descricao"], filters={"data": date, "uf": "", "cidade": ""})
                if get_result:
                    holidays[key] = {
                        "isholiday": True,
                        "uf": "" if uf == "all" else uf,
                        "cidade": "" if city == "all" else city,
                        "descricao": get_result[0].descricao
                    }
                else:
                    holidays[key] = {
                        "isholiday": False
                    }
            return holidays[key]

        def check_holidays(date: date, city: str):

            # City and UF is a key of city
            uf = "all"
            if city:
                s_sity = city.split("-")
                uf = s_sity[1]
                city = s_sity[0]
            else:
                city = "all"
                uf = "all"

            # Check if the date is a holiday
            holiday = check_holiday(date, "all", "all")
            if holiday['isholiday']:
                return holiday
            holiday = check_holiday(date,  uf, "all")
            if check_holiday(date, uf, "all"):
                return holiday
            holiday = check_holiday(date, "all", city)
            if check_holiday(date, "all", city):
                return holiday
        
        def get_week_day(date: date):
            """
            Get the name of the week day.
            :param date: The date object.
            :return: The name of the week day.
            """
            dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
            return dias_semana[date.weekday()]
        
        def get_busy_days(start_date: date, end_date: date, city: str) -> int:

            busy_days = 0
            
            while start_date <= end_date:
                holiday = check_holidays(start_date, city)
                if holiday and not holiday['isholiday']:
                    # 0-4 is business days (Monday to Friday)
                    if start_date.weekday() < 5:  
                        busy_days += 1
                start_date += timedelta(days=1)
            
            return busy_days    
        
        # Get all Contract Measurement Record
        contract_measurement = frappe.db.get_all("Contract Measurement", fields = ["contrato","datainicialmedicao","datafinalmedicao"], filters={"name": measurement})
        contract_city = frappe.db.get_value("Contract", contract_measurement[0]["contrato"], "cidade")

        items = {}
        teams = {}
        total_item_hours = {}

        # Get busy days for each item
        records = frappe.db.sql("""
                                SELECT
                                    item.name AS item,
                                    item.codigo AS codigo,
                                    item.cidade AS cidade,
                                    item.percentualhe AS percentualhe,
                                    item.dom_hora,
                                    item.seg_hora,
                                    item.ter_hora,
                                    item.qua_hora, 
                                    item.qui_hora,
                                    item.sex_hora,
                                    item.sab_hora
                                FROM
                                    `tabContract Item` item
                                    INNER JOIN `tabContract Measurement Item` measurement_item ON measurement_item.itemcontrato = item.name
                                WHERE
                                    measurement_item.parent = %s
                                """,
                                (measurement,
                                ), as_dict=True)
        
        if records:
            for i in records:

                city = i["cidade"] if i["cidade"] else contract_city

                busy_days = get_busy_days(
                    contract_measurement[0]["datainicialmedicao"],
                    contract_measurement[0]["datafinalmedicao"],
                    city
                )            

                items[i["item"]] = {
                    "name": i["item"],
                    "codigo": i["codigo"],
                    "cidade": city,
                    "percentualhe": i["percentualhe"],
                    "busy_days": busy_days
                }

                # Update the item busy days
                frappe.db.sql("""
                    
                    UPDATE 
                        `tabContract Measurement Item` item
                    SET 
                        item.diasuteis = %s
                    WHERE 
                        item.itemcontrato = %s AND 
                        item.parent = %s;
                    """,
                    (
                        busy_days,
                        i["item"],
                        measurement
                    ))
                
                # Update busy days for work roles
                frappe.db.sql("""
                    
                    UPDATE
                        `tabContract Measurement Work Role` work_role
                    SET
                        work_role.totaldias = %s
                    WHERE 
                        work_role.item = %s AND 
                        work_role.parent = %s;
                    """,
                    (
                        busy_days,
                        i["item"],
                        measurement
                    ))
                # Update busy days for assets
                frappe.db.sql("""
                    
                    UPDATE
                        `tabContract Measurement Asset` asset
                    SET
                        asset.totaldias = %s
                    WHERE 
                        asset.item = %s AND
                        asset.parent = %s;
                    """,
                    (
                        busy_days,
                        i["item"],
                        measurement,
                    ))        

        # Parse the itens
        m_records = frappe.db.get_all("Contract Measurement Record", fields=["name"], filters={"boletimmedicao": measurement})
        for r in m_records:

            kartado_measurement_record = frappe.get_doc("Contract Measurement Record", r.name)

            for k_time in kartado_measurement_record.tabhoras:

                if not k_time.item in items:
                    continue

                record_contract_item = items[k_time.item]

                # Set city for holiday check
                city = record_contract_item["cidade"]
                busy_days = record_contract_item["busy_days"]
                
                if k_time.funcao:
                    hour_key = f"{k_time.funcao}-{k_time.item}"
                if k_time.maquina_equipamento_ou_ferramenta:
                    hour_key = f"{k_time.maquina_equipamento_ou_ferramenta}-{k_time.item}"
                
                if not hour_key in total_item_hours:
                    total_item_hours[hour_key] = {
                        "item": k_time.item,
                        "funcao": k_time.funcao if k_time.funcao else "",
                        "maquina_equipamento_ou_ferramenta": k_time.maquina_equipamento_ou_ferramenta if k_time.maquina_equipamento_ou_ferramenta else "",
                        "horanormal": 0.0,
                        "horaextra": 0.0,
                        "horaextra100": 0.0,
                        "compensacoes": 0.0,
                        "horanormalda": 0.0,
                        "valorcalculado": 0.0,
                        "percentualhe": record_contract_item.get("percentualhe", 0.0)
                    }

                # Create a team if it does not exist
                if not kartado_measurement_record.equipe in teams:
                    # Get the team from the contract item
                    teams[kartado_measurement_record.equipe] = []

                # Add funcao and item to the team
                if k_time.funcao not in teams[kartado_measurement_record.equipe] and k_time.item not in teams[kartado_measurement_record.equipe]:
                    teams[kartado_measurement_record.equipe].append(
                        {
                            "funcao": k_time.funcao,
                            "item": k_time.item
                        })

                # Set the default date to process
                date_process = kartado_measurement_record.dataexecucao
                next_date_process = date_process

                # Timestamp strings
                time_start = k_time.horainicial
                time_end = k_time.horafinal

                # Calculate the hours based on the day of the week
                if (time_end < time_start):
                    add_days = timedelta(days=1)
                    time_end += add_days

                total_hours_time =  time_end - time_start

                # Convert to decimal hours
                total_hours = total_hours_time.total_seconds() / 3600.0

                # Discount interval time
                if total_hours > 6:
                    total_hours -= 1.0

                # Get work hours from contract item
                work_hours = 8.0
                if date_process.weekday() == 0:
                    work_hours = record_contract_item.get("seg_hora", 0)
                    if work_hours == 0:
                        work_hours = 9

                if date_process.weekday() == 1:
                    work_hours = record_contract_item.get("ter_hora", 0)
                    if work_hours == 0:
                        work_hours = 9

                if date_process.weekday() == 2:
                    work_hours = record_contract_item.get("qua_hora", 0)
                    if work_hours == 0:
                        work_hours = 9

                if date_process.weekday() == 3:
                    work_hours = record_contract_item.get("qui_hora", 0)
                    if work_hours == 0:
                        work_hours = 9

                if date_process.weekday() == 4:
                    work_hours = record_contract_item.get("sex_hora", 0)
                    if work_hours == 0:
                        work_hours = 8

                if date_process.weekday() == 5:
                    work_hours = record_contract_item.get("sab_hora", 0)
                    
                # Check if has extra hours
                extra_hours = 0.0
                if total_hours > work_hours:
                    # Calculate the extra hours
                    extra_hours = total_hours - work_hours          

                # Check if has discount hours
                discount_hours = 0.0
                if (work_hours > 0 and
                    total_hours < work_hours):
                    # Calculate the extra hours
                    discount_hours = total_hours - work_hours

                # Hours record
                k_time.compensacoes = 0.0
                k_time.horaextra100 = 0.0
                k_time.horaextra = 0.0
                k_time.horanormal = 0.0
                k_time.horanormalda = 0.0
                k_time.valorcalculado = 0.0
                
                # Return the name of weekday
                kartado_measurement_record.diasemana = get_week_day(date_process)
                
                # Is it a holiday?
                holiday = check_holidays(date_process, city)
                if holiday['isholiday']:
                    k_time.horaextra100 = total_hours
                    total_item_hours[hour_key]["horaextra100"] += total_hours
                    kartado_measurement_record.feriado = holiday['descricao']
                    kartado_measurement_record.eh_feriado = True
                else:                            
                    # Is it a Sunday?
                    if date_process.weekday() == 6:
                        k_time.horaextra100 = total_hours
                        total_item_hours[hour_key]["horaextra100"] += total_hours
                    else:
                        # Check if has extra hours
                        if extra_hours > 0:
                            # Calculate the extra hours
                            k_time.horanormal = work_hours
                            k_time.horaextra = extra_hours
                            total_item_hours[hour_key]["horanormal"] += work_hours
                            total_item_hours[hour_key]["horaextra"] += extra_hours
                        else:
                            k_time.horanormal = total_hours
                            k_time.horanormalda = discount_hours
                            total_item_hours[hour_key]["horanormal"] += total_hours
                            total_item_hours[hour_key]["horanormalda"] += discount_hours                        

            # Update the measurement record
            kartado_measurement_record.save()

        contract_measurement = frappe.get_doc("Contract Measurement", measurement)

        for team, items in teams.items():

            for t in items:
                wr = None
                team_localized = False
                for m in contract_measurement.tablemaodeobra:
                    if m.item == t['item'] and m.funcao == t['funcao']:
                        wr = m
                        break

                for e in contract_measurement.tablemaodeobraequipe:
                    if e.item == t['item'] and e.funcao == t['funcao'] and e.equipe == team:
                        e.valorunitario = wr.valorunitario
                        e.percentualhe = wr.percentualhe
                        team_localized = True
                        break
                
                # If the team is not localized, create a new one
                if team_localized:
                    new_team = contract_measurement.append("tablemaodeobraequipe")
                    new_team.item = m.item
                    new_team.funcao = m.funcao
                    new_team.tipodoitem = wr.tipodoitem
                    new_team.equipe = team
                    new_team.quantidademedida = 0.0
                    new_team.valorunitario = wr.valorunitario
                    new_team.valormedido = 0.0
                    new_team.totaldias = 0
                    new_team.horanormal= 0.0
                    new_team.horanormalda= 0.0
                    new_team.compensacoes = 0.0
                    new_team.horaextra = 0.0
                    new_team.percentualhe = wr.percentualhe
                    new_team.horaextra100 = 0.0

        contract_measurement.save()
        
        # Update measurement records with total hours
        for total_item_hour in total_item_hours.values():
            # Update work roles
            if total_item_hour["funcao"]:
                frappe.db.sql("""
                    
                    UPDATE 
                        `tabContract Measurement Work Role` work_role
                    SET 
                        work_role.horanormal = %s,
                        work_role.horanormalda = %s,
                        work_role.compensacoes = %s,
                        work_role.horaextra = %s,
                        work_role.percentualhe = %s,
                        work_role.horaextra100 = %s
                    WHERE 
                        work_role.parent = %s AND 
                        work_role.item = %s AND 
                        work_role.funcao = %s;
                    """,
                    (
                        total_item_hour["horanormal"],
                        total_item_hour["horanormalda"],
                        total_item_hour["compensacoes"],
                        total_item_hour["horaextra"],
                        total_item_hour["percentualhe"],
                        total_item_hour["horaextra100"],
                        measurement,
                        total_item_hour["item"],
                        total_item_hour["funcao"]
                    ))
            # Update assets
            if total_item_hour["maquina_equipamento_ou_ferramenta"]:
                frappe.db.sql("""
                    
                    UPDATE 
                        `tabContract Measurement Asset` asset
                    SET 
                        asset.horanormal = %s,
                        asset.horanormalda = %s,
                        asset.compensacoes = %s,
                        asset.horaextra = %s,
                        asset.percentualhe = %s,
                        asset.horaextra100 = %s
                    WHERE 
                        asset.parent = %s AND 
                        asset.item = %s AND 
                        asset.maquina_equipamento_ou_ferramenta = %s;
                    """,
                    (
                        total_item_hour["horanormal"],
                        total_item_hour["horanormalda"],
                        total_item_hour["compensacoes"],
                        total_item_hour["horaextra"],
                        total_item_hour["percentualhe"],
                        total_item_hour["horaextra100"],
                        measurement,
                        total_item_hour["item"],
                        total_item_hour["maquina_equipamento_ou_ferramenta"]
                    ))            

        return {"Processed": True, "message": "Hours records updated successfully."}
    except Exception as e:
        frappe.log_error(f"Error on update_hours_measurement_records: {str(e)}", "Measurement API")    
        return None

@frappe.whitelist(methods=["POST"])
def sum_measurement_records_work_role(measurement: str):
    """
    Sum work role records for a given measurement.
    """
    try:
        # Sum all work role values for the measurement
        records = frappe.db.sql("""
                SELECT
                    work_role.item,
                    work_role.funcao, 
                    item.codigo,
                    SUM(work_role.quantidademedida) AS total
                FROM 
                    `tabContract Measurement Record Work Role` work_role
                    INNER JOIN `tabContract Measurement Record` record ON record.name = work_role.parent
                    INNER JOIN `tabContract Item` item ON item.name = work_role.item
                WHERE record.boletimmedicao = %s
                GROUP BY work_role.item, work_role.funcao, item.codigo
                """, 
                (measurement,), as_dict = True)   

        for record in records:
            frappe.db.sql("""
                
                UPDATE 
                    `tabContract Measurement Work Role` work_role
                SET 
                    work_role.quantidadetotal = %s
                WHERE 
                    work_role.parent = %s AND 
                    work_role.item = %s AND 
                    work_role.funcao = %s;
                """,
                (
                    record.total,
                    measurement,
                    record.item,
                    record.funcao
                ))

        return {"Processed": True, "message": "Work role values summed successfully."}
    except Exception as e:
        frappe.log_error(f"Error on sum_measurement_records_work_role: {str(e)}", "Measurement API")    
        return None    

@frappe.whitelist(methods=["POST"])
def sum_measurement_records_asset(measurement: str):
    """
    Sum asset records for a given measurement.
    """
    try:
        # Sum all asset values for the measurement
        records = frappe.db.sql("""
                SELECT
                    asset.item,
                    asset.maquina_equipamento_ou_ferramenta, 
                    SUM(asset.quantidademedida) AS total
                FROM 
                    `tabContract Measurement Record Asset` asset
                    INNER JOIN `tabContract Measurement Record` record ON record.name = asset.parent
                WHERE record.boletimmedicao = %s
                GROUP BY asset.item, asset.maquina_equipamento_ou_ferramenta
                """, 
                (measurement,), as_dict =True)   

        for record in records:
            frappe.db.sql("""
                UPDATE 
                    `tabContract Measurement Asset` asset
                SET 
                    asset.quantidadetotal = %s
                WHERE 
                    asset.parent = %s AND 
                    asset.item = %s AND 
                    asset.maquina_equipamento_ou_ferramenta = %s;
                """,
                (
                    record.total,
                    measurement,
                    record.item,
                    record.maquina_equipamento_ou_ferramenta
                ))

        return {"Processed": True, "message": "Assets values summed successfully."}
    except Exception as e:
        frappe.log_error(f"Error on sum_measurement_records_asset: {str(e)}", "Measurement API")    
        return None        

@frappe.whitelist(methods=["POST"])
def update_reidi_measurement_record(measurement: str):
    """
    Calculate all REIDI
    """
    try:
        # Get all FTD values for the measurement
        reidi_values = frappe.db.get_all("Contract Measurement SAP Order", fields=["name","valormedido","reidi"], filters={"parent": measurement})
        total_reidi = 0.0

        for ftd in reidi_values:
            # Get the REIDI value
            reidi_value = flt(ftd.valormedido * (ftd.reidi / 100.0 if ftd.reidi else 0.0),2)
            # Sum the REIDI value
            total_reidi += reidi_value
            # Update the REIDI value in the SAP Order
            frappe.db.set_value("Contract Measurement SAP Order", ftd.name, "reidi", reidi_value)

        # Update the measurement document with the total REIDI value
        frappe.db.set_value("Contract Measurement", measurement, "descontoreidi", total_reidi)

        return {"Processed": True, "message": "REIDI values summed successfully."}
    except Exception as e:
        frappe.log_error(f"Error on update_reidi_measurement_record: {str(e)}", "Measurement API")    
        return None            

@frappe.whitelist(methods=["DELETE"])
def delete_measurement(measurement: str):
    """
    Delete a measurement.
    """
    try:
        # Get the measurement document
        # measurement_doc = frappe.get_doc("Contract Measurement", measurement)

        # Get remaining records
        frappe.db.sql("DELETE FROM `tabContract Measurement Item Remaining` WHERE boletimmedicao = %s", (measurement,))

        # Get adjustment records
        frappe.db.sql("DELETE FROM `tabContract Adjustment` WHERE boletimmedicao = %s", (measurement,))

        # Get integration records
        frappe.db.sql("DELETE FROM `tabIntegration Record` WHERE boletimmedicao = %s", (measurement,))

        # Get all inconsistency records
        frappe.db.sql("DELETE FROM `tabIntegration Inconsistency` WHERE boletimmedicao = %s", (measurement,))

        # Get all measurement records
        frappe.db.sql("DELETE FROM `tabContract Measurement Record` WHERE boletimmedicao = %s", (measurement,))

        # Get all measurement records
        frappe.db.sql("DELETE FROM `tabContract Measurement Reload` WHERE medicao = %s", (measurement,))

        # measurement_doc.delete()

        frappe.db.commit()
                                                                                                
        return {"Processed": True, "message": "Measurement deleted successfully."}

    except Exception as e:
        frappe.log_error(f"Error on delete_measurement: {str(e)}", "Measurement API")
        return None

@frappe.whitelist(methods=["POST"])
def apply_measurement_performance_conditions(measurement: str):

    try:
        # Get measurement document
        measurement_doc = frappe.get_doc("Contract Measurement", measurement)

        # Get contract name
        contract = measurement_doc.contrato

        # Get performance table
        performance_table = frappe.db.get_all(
            "Contract Performance",
            fields=["name", "maximo", "minimo", "fator"],
            filters={"parent": contract})
        if not performance_table:
            return {
                "Processed": False,
                "message": "No performance table found for the contract."
            }

        # Get contract itens where is performance condition
        contract_items = frappe.db.get_all(
            "Contract Item",
            fields=["name", "valorunitario","codigo"],
            filters={
                "contrato": contract,
                "aplicar_performance": True
            })
        if not contract_items:
            return {
                "Processed": False,
                "message": "No contract items found with performance conditions."
            }

        # Caculate performance average
        performance_sum = 0.0
        for performance in measurement_doc.tabperfm:
            performance_sum += performance.mediaponderada
        if measurement_doc.tabperfm:
            performance_average = flt(performance_sum / len(measurement_doc.tabperfm), 3)
            # Check if the performance average is in the performance table
            performance_factor = 0.0
            for performance in performance_table:
                if (performance_average >= performance["minimo"] and 
                    performance_average <= performance["maximo"]):
                    if performance["fator"] == 0:
                        performance_factor = performance_average
                    elif performance["fator"] < 0:
                        performance_factor = 0.0
                    else:
                        performance_factor = performance["fator"]
        else:
            performance_average = 0.0
            performance_factor = 0.0

        # Update all measurement itens
        for item in contract_items:
            frappe.db.sql("""
                        UPDATE `tabContract Measurement Item`
                            SET 
                                valorfatorpagamento = %s,
                                aplicar_performance = True,
                                fatorpagamento = %s
                        WHERE itemcontrato = %s AND parent = %s;
                        """,
                        (
                            flt(item["valorunitario"] * performance_factor,2),
                            flt(performance_factor,3),
                            item["name"],
                            measurement
                        )) 
                
        return {
            "Processed": True,
            "message": "Performance conditions applied successfully.",
            "performance_average": performance_average,
            "performance_factor": performance_factor
        }
    except Exception as e:
        frappe.log_error(f"Error on apply_measurement_performance_conditions: {str(e)}", "Measurement API")
        return None        

@frappe.whitelist(methods=["POST"])
def apply_measurement_items_factor(measurement: str):
    try:
        # Get contract itens where is performance condition
        contract_items = frappe.db.sql("""
            SELECT 
                cmi.name, 
                ci.codigo, 
                ci.fatorpagamento, 
                ci.valorunitario
            FROM 
                `tabContract Item` ci
                INNER JOIN `tabContract Measurement Item` cmi ON cmi.itemcontrato = ci.name
            WHERE 
                cmi.parent = %s AND 
                ci.aplicar_performance = False AND 
                ci.fatorpagamento > 0;
        """, (measurement,), as_dict=True)

        if not contract_items:
            return {
                "Processed": False,
                "message": "No contract items found with factor conditions."
            }

        # Update all measurement itens
        for item in contract_items:
            frappe.db.sql("""
                            UPDATE `tabContract Measurement Item`
                            SET 
                                fatorpagamento = %s
                            WHERE 
                                name = %s;
                            """,
                            (
                                item["fatorpagamento"],
                                item["name"]
                            )) 
                
        return {
            "Processed": True,
            "message": "Factor conditions applied successfully."
        }
    except Exception as e:
        frappe.log_error(f"Error on apply_measurement_items_factor: {str(e)}", "Measurement API")
        return None         

@frappe.whitelist(methods=["POST"])
def sum_measurement_items(measurement: str):
    try:
        # Get the measurement document
        measurement_doc = frappe.get_doc("Contract Measurement",measurement)
        
        contract = measurement_doc.contrato
        
        # Get contract formula group
        contract_doc = frappe.db.get_all(
            "Contract",
            fields=["name", "grupoformulas"],
            filters={"name": contract})
        if not contract_doc:
            return {"Processed": False, "message": "Contract not found."}
        
        formula_group = contract_doc[0].grupoformulas

        # Get the formula group document
        formula_group_fields = frappe.db.get_all(
            "Formula Group Field",
            fields=["name", "groupfieldfieldname"],
            filters={"parent": formula_group,
                    "groupfielddoctype": "Contract Measurement Item"})
        fields = [field.groupfieldfieldname for field in formula_group_fields]

        measurement_items = frappe.db.sql("""
            SELECT 
                item.codigo,
                item.descricao,
                m_item.name,
                m_item.fatorpagamento,
                m_item.valorfatorpagamento,
                m_item.aplicar_performance,
                m_item.itemcontrato,
                m_item.valorunitario,
                m_item.valortotalacumuladoanterior,
                m_item.quantidadeacumuladaanterior 
            FROM
                `tabContract Measurement Item` m_item
                INNER JOIN `tabContract Item` item ON item.name=m_item.itemcontrato
            WHERE
                m_item.parent = %s
        """, (measurement,), as_dict=True)

        # Get measurement items
        measurement_items_ = frappe.db.get_all(
            "Contract Measurement Item",
            fields=[
                        "name", 
                        "fatorpagamento", 
                        "valorfatorpagamento", 
                        "aplicar_performance", 
                        "itemcontrato", 
                        "valorunitario", 
                        "valortotalacumuladoanterior", 
                        "quantidadeacumuladaanterior", 
                        "saldoanterior",
                        "saldopago",
                        "valorpago"
                    ],
            filters={"parent": measurement})    

        for item in measurement_items:

            qtd_total_r = 0.0
            val_total_r = 0.0
            qtd_total_pc = 0.0
            val_total_pc = 0.0        
            val_total_pf = 0.0
            qtd_total_wk = 0.0
            val_total_wk = 0.0        
            qtd_total_asset = 0.0
            val_total_asset = 0.0
            val_total_pg_saldo = 0.0

            # Registros de medição - Exceto Payfactor e produtividade compensatória
            records = frappe.db.sql("""
                SELECT 
                    SUM(mrr.quantidademedida) AS quantidademedida,
                    SUM(mrr.valorcalculado) AS valorcalculado
                FROM 
                    `tabContract Measurement Record` mr
                    INNER JOIN `tabContract Measurement Record Resource` mrr ON mr.name = mrr.parent
                    INNER JOIN `tabContract Item` ci ON mrr.item = ci.name 
                WHERE 
                    NOT mr.origem_integracao = 'Payfactor' AND 
                    mr.boletimmedicao = %s AND 
                    mrr.item = %s AND 
                    (ci.produtividadecompensatoria = 0 OR ci.produtividadecompensatoria IS NULL)
            """, (measurement, item.itemcontrato), as_dict=True)

            if records:
                quantidade_medida = records[0].quantidademedida if records[0].quantidademedida else 0.0
                valor_calculado = records[0].valorcalculado if records[0].valorcalculado else 0.0    
                qtd_total_r += quantidade_medida
                val_total_r += valor_calculado
            
            # Get payfactor records
            records = frappe.db.sql("""
                SELECT 
                    SUM(desconto) AS discount
                FROM 
                    `tabContract Measurement Item Discount`
                WHERE 
                    boletimmedicao = %s AND 
                    item = %s
            """, (measurement, item.itemcontrato), as_dict=True)

            if records:
                val_total_pf += records[0].discount if records[0].discount else 0.0

            # Get total discounts
            records = frappe.db.sql("""
                SELECT 
                    SUM(mrr.payfactor_discount) AS payfactor_discount
                FROM 
                    `tabContract Measurement Record` mr
                    INNER JOIN `tabContract Measurement Record Resource` mrr ON mr.name = mrr.parent
                WHERE 
                    mr.origem_integracao = 'Payfactor' AND 
                    mr.boletimmedicao = %s AND 
                    mrr.item = %s
            """, (measurement, item.itemcontrato), as_dict=True)  

            if records:
                val_total_pf += records[0].discount if records[0].discount else 0.0                      

            # Get total balance payments
            for payment in measurement_doc.tblsaldos:
                if payment.item == item.itemcontrato:
                    val_total_pg_saldo += payment.valorpago

            # Get assets from measurement records
            for asset in measurement_doc.tableativos:
                if asset.item == item.itemcontrato:
                    qtd_total_asset += asset.quantidademedida
                    qtd_total_asset += asset.valormedido

            # Get work roles from measurement records\
            for work_role in measurement_doc.tablemaodeobra:
                if work_role.item == item.itemcontrato:
                    qtd_total_wk += work_role.quantidademedida
                    qtd_total_wk += work_role.valormedido

            # Get productivity compensatory values
            for productivity in measurement_doc.tblpctotal:
                if productivity.item == item.itemcontrato:
                    qtd_total_pc += productivity.quantidade
                    val_total_pc += productivity.valortotal

            # Update payfactor_discount
            if (not "payfactor_discount" in fields):
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET payfactor_discount = %s
                    WHERE name = %s;
                """, 
                (val_total_pf,
                item.name))            

            # Update payment value
            val_total_pago = item.valorpago if item.valorpago else 0.0
            if not "valorpago" in fields:   
                val_total_pago = ((flt((val_total_r + val_total_wk + val_total_asset + val_total_pc)*(item.fatorpagamento/100),2) + val_total_pg_saldo)-val_total_pf)
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valorpago = %s
                    WHERE name = %s;
                """, 
                (val_total_pago,
                item.name))
            # Update work roles quantity
            if not "quantidademedidamo" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET quantidademedidamo = %s
                    WHERE name = %s;
                """, 
                (qtd_total_wk,
                item.name))
            # Update work roles value
            if not "valortotalmedidomo" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valortotalmedidomo = %s
                    WHERE name = %s;
                """, 
                (val_total_wk,
                item.name))
            # Update asset quantity
            if not "quantidademedidaativos" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET quantidademedidaativos = %s
                    WHERE name = %s;
                """, 
                (qtd_total_asset,
                item.name))    
            # Update asset value
            if not "valortotalmedidoativos" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valortotalmedidoativos = %s
                    WHERE name = %s;
                """, 
                (val_total_asset,
                item.name))                      
            # Update resource quantity
            if not "quantidademedidarecursos" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET quantidademedidarecursos = %s                      
                    WHERE name = %s;
                """, 
                (qtd_total_r,
                item.name))    
            # Update resource value
            if not "valortotalmedidorecursos" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valortotalmedidorecursos = %s
                    WHERE name = %s;
                """, 
                (val_total_r,
                item.name))     
            # Update productivity compensatory quantity
            if not "quantidademedidapc" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET quantidademedidapc = %s
                    WHERE name = %s;
                """, 
                (qtd_total_pc,
                item.name))
            # Update productivity compensatory value
            if not "valortotalmedidopc" in fields:
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valortotalmedidopc = %s
                    WHERE name = %s;
                """, 
                (val_total_pc,
                item.name))
            # Update the quantity measure
            if not "quantidademedida" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET quantidademedida = %s
                    WHERE name = %s;
                """, 
                (qtd_total_r + qtd_total_wk + qtd_total_asset, 
                item.name))
            # Update the value measure
            if not "valortotalmedido" in fields:
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valortotalmedido = %s
                    WHERE name = %s;
                """, 
                (val_total_r + val_total_wk + val_total_asset, 
                item.name))
            # Update the accumulated values
            if not "valortotalacumulado" in fields:
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET valortotalacumulado = %s
                    WHERE name = %s;
                """, 
                (item.valortotalacumuladoanterior + val_total_pago, 
                item.name))
            # Update the accumulated quantity
            if not "quantidadeacumulada" in fields:
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET quantidadeacumulada = %s
                    WHERE name = %s;
                """, 
                (item.quantidadeacumuladaanterior + (qtd_total_r + qtd_total_wk + qtd_total_asset), 
                item.name))
            # Update the saldo
            if not "saldoatual" in fields:
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET saldoatual = %s
                    WHERE name = %s;
                """, 
                (item.saldoanterior - val_total_pago, 
                item.name))     
            # Update balance payment
            if not "saldopago" in fields:                
                frappe.db.sql("""                    
                    UPDATE `tabContract Measurement Item`
                    SET saldopago = %s
                    WHERE name = %s;
                """, 
                (val_total_pg_saldo,
                item.name))


        return {"Processed": True, "message": "Measurement items summed successfully."}
    except Exception as e:
        frappe.log_error(f"Error on sum_measurement_items: {str(e)}", "Measurement API")
        return None           

# @frappe.whitelist(methods=["POST"])
# def sum_cities(measurement: str):
#     try:
#         cities_items = {}
#         items_cities = {}
#         items = []

#         cities_records = frappe.db.sql("""
#             WITH t_cities AS (
#                 SELECT
#                     cmr.name AS record_name,
#                     cmrl.rodovia_name AS rodovia,
#                     cmrl.kminicial,
#                     cmrl.kmfinal,
#                     cmrl.cidade_name  AS cidade,
#                     cmr.boletimmedicao
#                     FROM
#                         `tabContract Measurement Record` cmr
#                         INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
#                     WHERE
#                         cmr.boletimmedicao = %(measurement)s
#                         AND NOT cmrl.cidade_name IS NULL
#                         AND NOT cmrl.rodovia_name IS NULL
#             ), t_items AS (
#                 SELECT
#                     t_cities.record_name,
#                     t_cities.rodovia,
#                     t_cities.kminicial,
#                     t_cities.kmfinal,
#                     t_cities.cidade,
#                     cmwk.item,
#                     cmi.valorpago,
#                     cmwk.valormedido,
#                     ci.codigo,
#                     ci.descricao
#                 FROM
#                     t_cities
#                     INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
#                     INNER JOIN `tabContract Measurement Record Work Role` cmrwk ON cmr.name = cmrwk.parent
#                     LEFT JOIN `tabContract Measurement Work Role` cmwk ON cmwk.item = cmrwk.item AND
#                                                                         cmwk.funcao = cmrwk.funcao AND
#                                                                         cmwk.parent = cmr.boletimmedicao
#                     LEFT JOIN `tabContract Measurement Item` cmi ON cmwk.item = cmi.itemcontrato AND
#                                                                     cmi.parent = cmr.boletimmedicao
#                     LEFT JOIN `tabContract Item` ci ON ci.name = cmrwk.item
#                 WHERE
#                     NOT cmi.valorpago = 0
#                 UNION ALL
#                 SELECT
#                     t_cities.record_name,
#                     t_cities.rodovia,
#                     t_cities.kminicial,
#                     t_cities.kmfinal,
#                     t_cities.cidade,
#                     cma.item,
#                     cmi.valorpago,
#                     cma.valormedido,
#                     ci.codigo,
#                     ci.descricao
#                 FROM
#                     t_cities
#                     INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
#                     INNER JOIN `tabContract Measurement Record Asset` cmra ON cmr.name = cmra.parent
#                     LEFT JOIN `tabContract Measurement Asset` cma ON cma.item = cmra.item AND
#                                                                     cma.maquina_equipamento_ou_ferramenta =
#                                                                     cmra.maquina_equipamento_ou_ferramenta AND
#                                                                     cma.parent = cmr.boletimmedicao
#                     LEFT JOIN `tabContract Measurement Item` cmi ON cma.item = cmi.itemcontrato AND
#                                                                     cmi.parent = cmr.boletimmedicao
#                     LEFT JOIN `tabContract Item` ci ON ci.name = cmra.item
#                 WHERE
#                     NOT cmi.valorpago = 0 
#                 UNION ALL
#                 SELECT
#                     t_cities.record_name,
#                     t_cities.rodovia,
#                     t_cities.kminicial,
#                     t_cities.kmfinal,
#                     t_cities.cidade,
#                     cmrr.item,
#                     cmi.valorpago,
#                     cmrr.valorcalculado AS valormedido,
#                     ci.codigo,
#                     ci.descricao
#                 FROM
#                     t_cities
#                     INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
#                     INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
#                     LEFT JOIN `tabContract Measurement Item` cmi ON cmrr.item = cmi.itemcontrato AND
#                                                                     cmi.parent = cmr.boletimmedicao
#                     LEFT JOIN `tabContract Item` ci ON ci.name = cmrr.item
#                 WHERE
#                     NOT cmi.valorpago = 0
#             ), t_geral AS (
#                 SELECT
#                     NULL AS record_name,
#                     NULL AS rodovia,
#                     NULL AS kminicial,
#                     NULL AS kmfinal,
#                     CASE
#                         WHEN IFNULL(item.cidade, '') = '' THEN COALESCE(contract.cidade, '')
#                         ELSE COALESCE(item.cidade, '')
#                     END AS cidade,
#                     item.name AS item,
#                     cm_item.valorpago,
#                     cm_item.valortotalmedido AS valormedido,
#                     item.codigo,
#                     item.descricao
#                 FROM
#                     `tabContract Item` item
#                     INNER JOIN `tabContract` contract ON item.contrato = contract.name
#                     INNER JOIN `tabContract Measurement` cm ON cm.contrato = contract.name
#                     INNER JOIN `tabContract Measurement Item` cm_item ON item.name = cm_item.itemcontrato AND
#                                                                         cm_item.parent = cm.name
#                 WHERE
#                     cm.name = %(measurement)s
#                     AND NOT cm_item.valorpago = 0
#                     AND NOT (cm_item.itemcontrato IN (SELECT item FROM t_items))
#                 UNION ALL
#                 SELECT
#                     record_name,
#                     rodovia,
#                     kminicial,
#                     kmfinal,
#                     cidade,
#                     item,
#                     valorpago,
#                     valormedido,
#                     codigo,
#                     descricao
#                 FROM
#                     t_items)
#             SELECT
#                 record_name,
#                 rodovia,
#                 kminicial,
#                 kmfinal,
#                 cidade,
#                 item,
#                 valorpago,
#                 CASE
#                     WHEN valorpago > 0 THEN
#                         CASE
#                             WHEN valormedido = 0 THEN valorpago
#                             ELSE valormedido
#                         END
#                     ELSE valormedido
#                 END AS valormedido,
#                 codigo,
#                 descricao
#             FROM
#                 t_geral
#             WHERE 
#                 NOT cidade IS NULL""", {"measurement": measurement, }, as_dict=True)

#         # Itens para validar os valores totais
#         db_measurement_items = frappe.db.sql("""
#             SELECT
#                 cmi.itemcontrato,
#                 cmi.valorpago
#             FROM
#                 `tabContract Measurement Item` cmi 
#             WHERE
#                 cmi.parent = %s AND 
#                 NOT cmi.valorpago = 0 
#             """, (measurement, ), as_dict=True)
#         measurement_items = {}
#         for i in db_measurement_items:
#             measurement_items.setdefault(i.itemcontrato, i.valorpago)

#         if cities_records:

#             # Monta as matrizes de cidades por item e itens por cidade
#             for record in cities_records:

#                 if record.item:
#                     # Cria o item se não existir
#                     if not record.item in items_cities:
#                         items_cities[record.item] = {
#                             'valorpago': record.valorpago,
#                             'valortotalmedido': 0.0,
#                             'cidades': []
#                         }
#                     # Inclusão na lista de itens
#                     if record.item not in items:
#                         items.append(record.item)
#                     # Define a rodovia e cidade
                    
#                     _measure_value = record.valormedido
#                     _reference_value = 0.0
#                     if (record.valorpago < 0 and record.valormedido > 0) or (record.valorpago > 0 and record.valormedido < 0):
#                         _measure_value = 0.0
#                         _reference_value = abs(record.valormedido)
#                     items_cities[record.item]['valortotalmedido'] += _measure_value
#                     items_cities[record.item]['cidades'].append(
#                         {
#                             "cidade": record.cidade, 
#                             "valor": _measure_value, 
#                             "valormedido": _measure_value, 
#                             "percentual": 0.0, 
#                             "distribuicao": 0.0,
#                             "rodovia": record.rodovia,
#                             "kminicial": record.kminicial,
#                             "referencia": _reference_value
#                         })

#         if items_cities:

#             # Variavel para calculo do percentual de cada cidade
#             total_value = 0.0

#             item_count=0
#             # Calcula o valor total para cada item e percentual para cada cidade
#             for item, data in items_cities.items():

#                 item_count+=1
#                 print(f"Processando item {item_count} de {len(items_cities)}")

#                 # Distribui a diferença quando valores positivos e negativos ocorrem em cidades do item
#                 if not data['valorpago'] == data['valortotalmedido']:
#                     _total_diference = abs(data['valorpago']) - abs(data['valortotalmedido'])
#                     _total_reference = sum(abs(city['referencia']) for city in data['cidades'])
#                     if _total_reference:
#                         for city in data['cidades']:
#                             if city['valor'] == 0:
#                                 _value = _total_diference * (abs(city['referencia']) / _total_reference)
#                                 city['valor'] = _value
#                                 city['valormedido'] = _value

#                 # # if data['valorpago'] < 0:
#                 # # Somatório dos valores negativos das cidades do item
#                 # city_total_sum = sum(city['valor'] if city['valor']<0 else 0 for city in data['cidades'])
#                 # # Primeiro calcula os valores e percentuais por cidade do item
#                 # for city in data['cidades']:
#                 #     if city['valor'] < 0:
#                 #         if not city_total_sum == 0:
#                 #             city_percentual = (city['valor'] / city_total_sum) * 100.0
#                 #             # city_value = flt(city['valormedido'] * (city_percentual/100), 2)
#                 #             city_value = flt(measurement_items[item] * (city_percentual/100), 2)
#                 #         else:
#                 #             city_percentual = 0.0
#                 #             city_value = 0.0
#                 #         city['percentual'] = flt(city_percentual, 3)
#                 #         city['distribuicao'] = city_value
#                 #         if not city['cidade'] in cities_items:
#                 #             cities_items[city['cidade']] = {
#                 #                 'valortotal': 0.0,
#                 #                 'percentual': 0.0
#                 #             }
#                 #         cities_items[city['cidade']]['valortotal'] += city_value
#                 #         total_value += city_value

#                 # #else:
#                 # # Somatório dos valores positivos das cidades do item
#                 # city_total_sum = sum(city['valor'] if city['valor']>0 else 0 for city in data['cidades'])
#                 # # Primeiro calcula os valores e percentuais por cidade do item
#                 # for city in data['cidades']:
#                 #     if city['valor'] > 0:
#                 #         if not city_total_sum == 0:
#                 #             city_percentual = (city['valor'] / city_total_sum) * 100.0
#                 #             # city_value = flt(city['valormedido'] * (city_percentual/100), 2)
#                 #             city_value = flt(measurement_items[item] * (city_percentual/100), 2)
#                 #         else:
#                 #             city_percentual = 0.0
#                 #             city_value = 0.0
#                 #         city['percentual'] = flt(city_percentual, 3)
#                 #         city['distribuicao'] = city_value
#                 #         if not city['cidade'] in cities_items:
#                 #             cities_items[city['cidade']] = {
#                 #                 'valortotal': 0.0,
#                 #                 'percentual': 0.0
#                 #             }
#                 #         cities_items[city['cidade']]['valortotal'] += city_value
#                 #         total_value += city_value

#                 for city in data['cidades']:
#                     city["distribuicao"] = city["valor"]
            
#                 # Variavel para controle de loop infinito
#                 iteration_count = 0
#                 while True:
#                     # Ajusta os valores para fechar o total (redistribui centavos)                
#                     city_count = len(data['cidades'])
#                     sum_values = flt(sum(city['distribuicao'] for city in data['cidades']), 2)
#                     diff = flt(measurement_items[item] - sum_values, 2)
#                     # print(f".   Item {item} - Total Item: {measurement_items[item]} - Soma Cidades: {sum_values} - Diferença: {diff}")
#                     # Se houver diferença, redistribui centavos
#                     if abs(diff) >= 0.01:
#                         step = 0.01 if diff > 0 else -0.01
#                         idx = 0
#                         while abs(diff) >= 0.01:
#                             city_idx = idx % city_count
#                             # Previna valortotal negativo
#                             if step < 0 and abs(data['cidades'][city_idx]['distribuicao']) + step < 0:
#                                 idx += 1
#                                 continue
#                             # Aplica o fator a cidade do item
#                             data['cidades'][city_idx]['distribuicao'] += step
#                             # Aplica o fator a totalização de cidades
#                             cities_items[data['cidades'][city_idx]['cidade']]['valortotal'] += step
#                             diff -= step
#                             idx += 1
#                             iteration_count += 1
#                             total_value += step
#                             # Previne loop infinito
#                             if iteration_count > 1000:
#                                 frappe.log_error(f"Erro em sum_cities: Muitas iterações para ajustar os valores das cidades na medição {measurement}.", "Measurement API")
#                                 return {
#                                     "Processed": False,
#                                     "message": f"Erro em sum_cities: Muitas iterações para ajustar os valores das cidades na medição {measurement}."
#                                 }
#                     # Checa se fechou o valor do item
#                     sum_values = abs(sum(city['distribuicao'] for city in data['cidades']))
#                     if abs((abs(measurement_items[item]) - abs(sum_values))) < 0.001:
#                         # print(f"*** Item {item} - Total Item: {measurement_items[item]} - Soma Cidades: {sum_values}")
#                         print(f"{item}|{sum_values}|{measurement_items[item]}")
#                         break

#             print(f"Total Geral: {total_value}")

#             # Recupera o documento de medição
#             measurement_doc = frappe.get_doc("Contract Measurement", measurement)
#             measurement_doc.set('tablemunicipios', [])
#             measurement_doc.set('tblmunicipiositem', [])

#             # Calcula o percentual de cada cidade
#             for city, data in cities_items.items():
#                 # data['valortotal'] = data['valortotal']
#                 # data['percentual'] = 0.0
#                 if not total_value == 0:
#                     city_percent = flt((data['valortotal'] / total_value) * 100.0, 3)
#                     data['percentual'] = city_percent
#                 else:
#                     data['percentual'] = 0.0

#             # Variavel para carga e calculo final das cidades e itens
#             for city, data in cities_items.items():
#                 # Adiciona a cidade ao documento de medição
#                 m_c = measurement_doc.append('tablemunicipios')
#                 m_c.municipio = city
#                 m_c.participacao = data['percentual']
#                 m_c.valor = data['valortotal']

#                 # Adiciona os itens para cada cidade
#                 for item, data in items_cities.items():
#                     for i_city in data['cidades']:
#                         if i_city['cidade'] != city:
#                             continue
#                         # Adiciona o item ao documento de medição
#                         m_ci = measurement_doc.append('tblmunicipiositem')
#                         m_ci.item = item
#                         m_ci.municipio = i_city['cidade']
#                         m_ci.rodovia = i_city['rodovia']
#                         m_ci.kminicial = i_city['kminicial']
#                         m_ci.participacao = i_city['percentual']
#                         m_ci.valor = i_city['distribuicao']

#             # Salva o documento de medição
#             measurement_doc.save(ignore_permissions=True)
#             return {
#                 "Processed": True,
#                 "message": "Calculo de valores por cidade concluidos com sucesso."
#             }
        
#         else:

#             # Recupera o documento de medição
#             measurement_doc = frappe.get_doc("Contract Measurement", measurement)
#             measurement_doc.set('tablemunicipios', [])
#             measurement_doc.set('tblmunicipiositem', [])
#             measurement_doc.save(ignore_permissions=True)

#             return {
#                 "Processed": False,
#                 "message": "Nenhuma cidade encontrada para calculo."
#             }
#     except Exception as e:
#         print(f"Error on sum_cities: {str(e)}", "Measurement API")
#         frappe.log_error(f"Error on sum_cities: {str(e)}", "Measurement API")
#         return None        

def sum_cities_no_distribute(measurement: str) -> Dict:
    try:
        cities_items = {}
        items_cities = {}
        items = []

        cities_records = frappe.db.sql("""
        WITH t_cities AS (
            SELECT
                cmr.name AS record_name,
                cmrl.rodovia_name AS rodovia, 
                cmrl.kminicial,
                cmrl.kmfinal,
                cmrl.cidade_name AS cidade,
                cmr.boletimmedicao,
				cmrl.codigorelatorio
            FROM
                `tabContract Measurement Record` cmr
                INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
            WHERE
                cmr.boletimmedicao = %(measurement)s AND 
                NOT cmrl.cidade_name IS NULL AND 
                NOT cmrl.rodovia_name IS NULL
        )
        SELECT
			cmr.name,
			cmr.origem_integracao,
            t_cities.record_name,
            t_cities.rodovia,
            t_cities.kminicial,
            t_cities.kmfinal,
            t_cities.cidade,
			item.codigo,
			item.descricao,
			cmr.dataexecucao,
			cmr.dataaprovacao,
			cmr.codigo as rdo,
			t_cities.codigorelatorio,
			cm_item.quantidademedida,
			cm_item.valortotal,
			cm_item.valorcalculado,
            cm_item.item
        FROM
            t_cities
            INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
            INNER JOIN `tabContract Measurement Record Work Role` cm_item ON cmr.name = cm_item.parent
            LEFT JOIN `tabContract Measurement Item` m_item ON cm_item.item = m_item.itemcontrato AND 
                                                     m_item.parent = cmr.boletimmedicao
			LEFT JOIN `tabContract Item` item ON cm_item.item = item.name								   
        UNION ALL
        SELECT
			cmr.name,
			cmr.origem_integracao,
            t_cities.record_name,
            t_cities.rodovia,
            t_cities.kminicial,
            t_cities.kmfinal,
            t_cities.cidade,
			item.codigo,
			item.descricao,
			cmr.dataexecucao,
			cmr.dataaprovacao,
			cmr.codigo as rdo,
			t_cities.codigorelatorio,
			cm_item.quantidademedida,
			cm_item.valortotal,
			cm_item.valorcalculado,
            cm_item.item
        FROM
            t_cities
            INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
            INNER JOIN `tabContract Measurement Record Asset` cm_item ON cmr.name = cm_item.parent   
            LEFT JOIN `tabContract Measurement Item` m_item ON cm_item.item = m_item.itemcontrato AND 
                                                     m_item.parent = cmr.boletimmedicao     
			LEFT JOIN `tabContract Item` item ON cm_item.item = item.name								   
        UNION ALL
        SELECT
			cmr.name,
			cmr.origem_integracao,
            t_cities.record_name,
            t_cities.rodovia,
            t_cities.kminicial,
            t_cities.kmfinal,
            t_cities.cidade,
			item.codigo,
			item.descricao,
			cmr.dataexecucao,
			cmr.dataaprovacao,
			cmr.codigo as rdo,
			t_cities.codigorelatorio,
			cm_item.quantidademedida,
			cm_item.valortotal,
			cm_item.valorcalculado,	   
            cm_item.item
        FROM
            t_cities
            INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
            INNER JOIN `tabContract Measurement Record Resource` cm_item ON cmr.name = cm_item.parent   
            LEFT JOIN `tabContract Measurement Item` m_item ON cm_item.item = m_item.itemcontrato AND 
                                                     m_item.parent = cmr.boletimmedicao
			LEFT JOIN `tabContract Item` item ON cm_item.item = item.name""", 
        {"measurement": measurement, }, as_dict=True)

        # Itens para validar os valores totais
        db_measurement_items = frappe.db.sql("""
            SELECT
                cmi.itemcontrato,
                cmi.valorpago
            FROM
                `tabContract Measurement Item` cmi 
            WHERE
                cmi.parent = %s AND 
                NOT cmi.valorpago = 0 
            """, (measurement, ), as_dict=True)
        
        total_items = 0.0
        measurement_items = []
        for i in db_measurement_items:
            measurement_items.append(
                {
                    "item": i.itemcontrato,
                    "paid_value": i.valorpago,
                    "cities": []
                }
            )
            total_items += i.valorpago

        total_cities = 0.0
        if cities_records:

            # Monta as matrizes de cidades por item e itens por cidade
            for item in measurement_items:
                for record in cities_records:
                    if record.item == item["item"]:
                        item["cities"].append({
                            "city": record.cidade,
                            "measured_value": record.valorcalculado,
                            "highway": record.rodovia,
                            "startkm": record.kminicial
                        })
                        total_cities += abs(record.valorcalculado)

            if not total_items == total_cities:
                return {
                    "Processed": False,
                    "message": "Distribuir"
                }


            total_cities = 0.0
            for item in measurement_items:

                for city in item['cities']:
                    # Ignora cidades com valor zero
                    if city['measured_value'] == 0.0:
                        continue
                    # Cria o item se não existir
                    cities_items.setdefault(city['city'], {
                        'total': 0.0,
                        "items": []
                    })
                    # Acumula o valor da cidade
                    cities_items[city['city']]['total'] += city['measured_value']
                    cities_items[city['city']]['items'].append({
                        'item': item['item'],
                        'highway': city['highway'],
                        'startkm': city['startkm'],
                        'final_value': city['measured_value']
                    })
                    # Acumula o total geral
                    total_cities += abs(city['measured_value'])

            # Variavel para carga e calculo final das cidades e itens
            measurement_doc = frappe.get_doc("Contract Measurement", measurement)
            measurement_doc.set('tablemunicipios', [])
            measurement_doc.set('tblmunicipiositem', [])
            for city, data in cities_items.items():
                # Adiciona a cidade ao documento de medição
                m_c = measurement_doc.append('tablemunicipios')
                m_c.municipio = city
                m_c.participacao = flt((abs(data['total']) / total_cities) * 100.0, 3)
                m_c.valor = data['total']


                # Adiciona os itens para cada cidade
                for item in data['items']:
                    # Adiciona o item ao documento de medição
                    m_ci = measurement_doc.append('tblmunicipiositem')
                    m_ci.item = item['item']
                    m_ci.municipio = city
                    m_ci.rodovia = item['highway']
                    m_ci.kminicial = item['startkm']
                    m_ci.participacao = flt((abs(item['final_value']) / abs(data['total'])) * 100.0, 3)
                    m_ci.valor = item['final_value']

            # Salva o documento de medição
            measurement_doc.save(ignore_permissions=True)
            return {
                "Processed": True,
                "message": "Calculo de valores por cidade concluidos com sucesso."
            }
        
        else:

            # Recupera o documento de medição
            measurement_doc = frappe.get_doc("Contract Measurement", measurement)
            measurement_doc.set('tablemunicipios', [])
            measurement_doc.set('tblmunicipiositem', [])
            measurement_doc.save(ignore_permissions=True)

            return {
                "Processed": False,
                "message": "Distribuir"
            }
        
    except Exception as e:
        print(f"Error on sum_cities: {str(e)}", "Measurement API")
        frappe.log_error(f"Error on sum_cities: {str(e)}", "Measurement API")
        return {
                "Processed": False,
                "message": "Erro",
                "error": str(e)
            }

@frappe.whitelist(methods=["POST"])
def sum_cities(measurement: str):
    try:

        # Distribuição direta sem rateio
        result = sum_cities_no_distribute(measurement)
        if result.get("Processed", True):
            return {
                "Processed": False,
                "message": "Nenhuma cidade encontrada para calculo."
            }

        cities_items = {}

        cities_records = frappe.db.sql("""
            WITH t_cities AS (
                SELECT
                    cmr.name AS record_name,
                    cmrl.rodovia_name AS rodovia,
                    cmrl.kminicial,
                    cmrl.kmfinal,
                    cmrl.cidade_name  AS cidade,
                    cmr.boletimmedicao
                FROM
                    `tabContract Measurement Record` cmr
                    INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                WHERE
                    cmr.boletimmedicao = %(measurement)s
                    AND NOT cmrl.cidade_name IS NULL
                    AND NOT cmrl.rodovia_name IS NULL
            ), t_items AS (
                SELECT
                    t_cities.record_name,
                    t_cities.rodovia,
                    t_cities.kminicial,
                    t_cities.kmfinal,
                    t_cities.cidade,
                    cmwk.item,
                    cmi.valorpago,
                    cmwk.valormedido,
                    ci.codigo,
                    ci.descricao
                FROM
                    t_cities
                    INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
                    INNER JOIN `tabContract Measurement Record Work Role` cmrwk ON cmr.name = cmrwk.parent
                    LEFT JOIN `tabContract Measurement Work Role` cmwk ON cmwk.item = cmrwk.item AND
                                                                        cmwk.funcao = cmrwk.funcao AND
                                                                        cmwk.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Measurement Item` cmi ON cmwk.item = cmi.itemcontrato AND
                                                                    cmi.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Item` ci ON ci.name = cmrwk.item
                WHERE
                    NOT cmi.valorpago = 0
                UNION ALL
                SELECT
                    t_cities.record_name,
                    t_cities.rodovia,
                    t_cities.kminicial,
                    t_cities.kmfinal,
                    t_cities.cidade,
                    cma.item,
                    cmi.valorpago,
                    cma.valormedido,
                    ci.codigo,
                    ci.descricao
                FROM
                    t_cities
                    INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
                    INNER JOIN `tabContract Measurement Record Asset` cmra ON cmr.name = cmra.parent
                    LEFT JOIN `tabContract Measurement Asset` cma ON cma.item = cmra.item AND
                                                                    cma.maquina_equipamento_ou_ferramenta =
                                                                    cmra.maquina_equipamento_ou_ferramenta AND
                                                                    cma.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Measurement Item` cmi ON cma.item = cmi.itemcontrato AND
                                                                    cmi.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Item` ci ON ci.name = cmra.item
                WHERE
                    NOT cmi.valorpago = 0 
                UNION ALL
                SELECT
                    t_cities.record_name,
                    t_cities.rodovia,
                    t_cities.kminicial,
                    t_cities.kmfinal,
                    t_cities.cidade,
                    cmrr.item,
                    cmi.valorpago,
                    cmrr.valorcalculado AS valormedido,
                    ci.codigo,
                    ci.descricao
                FROM
                    t_cities
                    INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
                    INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
                    LEFT JOIN `tabContract Measurement Item` cmi ON cmrr.item = cmi.itemcontrato AND
                                                                    cmi.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Item` ci ON ci.name = cmrr.item
                WHERE
                    NOT cmi.valorpago = 0
            ), t_geral AS (
                SELECT
                    NULL AS record_name,
                    NULL AS rodovia,
                    NULL AS kminicial,
                    NULL AS kmfinal,
                    CASE
                        WHEN IFNULL(item.cidade, '') = '' THEN COALESCE(contract.cidade, '')
                        ELSE COALESCE(item.cidade, '')
                    END AS cidade,
                    item.name AS item,
                    cm_item.valorpago,
                    cm_item.valortotalmedido AS valormedido,
                    item.codigo,
                    item.descricao
                FROM
                    `tabContract Item` item
                    INNER JOIN `tabContract` contract ON item.contrato = contract.name
                    INNER JOIN `tabContract Measurement` cm ON cm.contrato = contract.name
                    INNER JOIN `tabContract Measurement Item` cm_item ON item.name = cm_item.itemcontrato AND
                                                                        cm_item.parent = cm.name
                WHERE
                    cm.name = %(measurement)s
                    AND NOT cm_item.valorpago = 0
                    AND NOT (cm_item.itemcontrato IN (SELECT item FROM t_items))
                UNION ALL
                SELECT
                    record_name,
                    rodovia,
                    kminicial,
                    kmfinal,
                    cidade,
                    item,
                    valorpago,
                    valormedido,
                    codigo,
                    descricao
                FROM
                    t_items)
            SELECT
                record_name,
                rodovia,
                kminicial,
                kmfinal,
                cidade,
                item,
                valorpago,
                CASE
                    WHEN valorpago > 0 THEN
                        CASE
                            WHEN valormedido = 0 THEN valorpago
                            ELSE valormedido
                        END
                    ELSE valormedido
                END AS valormedido,
                codigo,
                descricao
            FROM
                t_geral
            WHERE 
                NOT cidade IS NULL""", {"measurement": measurement, }, as_dict=True)

        # Itens para validar os valores totais
        db_measurement_items = frappe.db.sql("""
            SELECT
                cmi.itemcontrato,
                cmi.valorpago
            FROM
                `tabContract Measurement Item` cmi 
            WHERE
                cmi.parent = %s AND 
                NOT cmi.valorpago = 0 
            """, (measurement, ), as_dict=True)
        measurement_items = []
        for i in db_measurement_items:
            measurement_items.append(
                {
                    "item": i.itemcontrato,
                    "paid_value": i.valorpago,
                    "cities": []
                }
            )

        if cities_records:

            # Monta as matrizes de cidades por item e itens por cidade
            for item in measurement_items:
                for record in cities_records:
                    if record.item == item["item"]:
                        item["cities"].append({
                            "city": record.cidade,
                            "measured_value": record.valormedido,
                            "highway": record.rodovia,
                            "startkm": record.kminicial
                        })

            # Distribui o valor pago para as cidades do item
            measurement_items_result = processar_distribuicao(measurement_items)

            total_cities = 0.0
            for item in measurement_items_result:

                for city in item['cities']:
                    # Ignora cidades com valor zero
                    if city['distributed_value'] == 0.0:
                        continue
                    # Cria o item se não existir
                    cities_items.setdefault(city['city'], {
                        'total': 0.0,
                        "items": []
                    })
                    # Acumula o valor da cidade
                    cities_items[city['city']]['total'] += city['distributed_value']
                    cities_items[city['city']]['items'].append({
                        'item': item['item'],
                        'highway': city['highway'],
                        'startkm': city['startkm'],
                        'final_value': city['distributed_value']
                    })
                    # Acumula o total geral
                    total_cities += abs(city['distributed_value'])

            # Variavel para carga e calculo final das cidades e itens
            measurement_doc = frappe.get_doc("Contract Measurement", measurement)
            measurement_doc.set('tablemunicipios', [])
            measurement_doc.set('tblmunicipiositem', [])
            for city, data in cities_items.items():
                # Adiciona a cidade ao documento de medição
                m_c = measurement_doc.append('tablemunicipios')
                m_c.municipio = city
                m_c.participacao = flt((abs(data['total']) / total_cities) * 100.0, 3)
                m_c.valor = data['total']


                # Adiciona os itens para cada cidade
                for item in data['items']:
                    # Adiciona o item ao documento de medição
                    m_ci = measurement_doc.append('tblmunicipiositem')
                    m_ci.item = item['item']
                    m_ci.municipio = city
                    m_ci.rodovia = item['highway']
                    m_ci.kminicial = item['startkm']
                    m_ci.participacao = flt((abs(item['final_value']) / abs(data['total'])) * 100.0, 3)
                    m_ci.valor = item['final_value']

            # Salva o documento de medição
            measurement_doc.save(ignore_permissions=True)
            return {
                "Processed": True,
                "message": "Calculo de valores por cidade concluidos com sucesso."
            }
        
        else:

            # Recupera o documento de medição
            measurement_doc = frappe.get_doc("Contract Measurement", measurement)
            measurement_doc.set('tablemunicipios', [])
            measurement_doc.set('tblmunicipiositem', [])
            measurement_doc.save(ignore_permissions=True)

            return {
                "Processed": False,
                "message": "Nenhuma cidade encontrada para calculo."
            }
    except Exception as e:
        print(f"Error on sum_cities: {str(e)}", "Measurement API")
        frappe.log_error(f"Error on sum_cities: {str(e)}", "Measurement API")
        return None        

@frappe.whitelist(methods=["POST"])
def update_cities(measurement: str):

    try:
        def write_inconsistencies(error_highways):
            """
            Write inconsistencies in the database.
            """
            lines = ""
            for highway, error in error_highways.items():
                lines += f"{highway}: {error}\n"
            inconsistency = frappe.new_doc("Integration Inconsistency")
            inconsistency.observacoes = lines
            inconsistency.tipo = "Cidades"
            inconsistency.dataehora = frappe.utils.now_datetime()
            inconsistency.save()

        error_highways = {}

        # Get cities with highways
        sql_citiess = """
                SELECT
                    cmrl.name,
                    CONCAT(cmrl.rodovia,'-',cmrl.via,'-',cmrl.sentido,'-',cmrl.faixa) AS rodovia, 
                    cmrl.kminicial,
                    cmrl.kmfinal,
                    hc.cidade AS cidade_name,
                    h.name AS rodovia_name,
                    cmr.boletimmedicao,
                    'Osiris' AS tipo
                FROM
                    `tabContract Measurement Record` cmr
                    INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                    LEFT JOIN `tabHighway Kartado` hk ON CONCAT(cmrl.rodovia,'-',cmrl.via,'-',cmrl.sentido,'-',cmrl.faixa) = hk.rodovia
                    LEFT JOIN `tabHighway` h ON hk.parent = h.name
                    LEFT JOIN `tabHighway City` hc ON h.name = hc.parent AND cmrl.kminicial BETWEEN hc.kminicial AND hc.kmfinal
                WHERE
                    cmr.origem_integracao IN ('Osiris') AND 
                    (cmrl.cidade_name IS NULL OR cmrl.rodovia_name IS NULL) AND 
                    cmr.boletimmedicao = %(measurement)s
                UNION ALL
                SELECT
                    cmrl.name,
                    CONCAT(cmrl.rodovia,'-',cmrl.sentido,'-',cmrl.faixa) AS rodovia, 
                    cmrl.kminicial,
                    cmrl.kmfinal,
                    hc.cidade AS cidade_name,
                    h.name AS rodovia_name,
                    cmr.boletimmedicao,
                    'Kartado' AS tipo             
                FROM
                    `tabContract Measurement Record` cmr
                    INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                    LEFT JOIN `tabHighway Kartado` hk ON CONCAT(cmrl.rodovia,'-',cmrl.sentido,'-',cmrl.faixa) = hk.rodovia
                    LEFT JOIN `tabHighway` h ON hk.parent = h.name
                    LEFT JOIN `tabHighway City` hc ON h.name = hc.parent AND cmrl.kminicial BETWEEN hc.kminicial AND hc.kmfinal
                WHERE
                    cmr.origem_integracao IN ('Kartado RDO','Kartado Apontamento','Kartado Outros') AND 
                    (cmrl.cidade_name IS NULL OR cmrl.rodovia_name IS NULL) AND 
                    cmr.boletimmedicao = %(measurement)s"""
                
        # Update cities and highways
        update_records = frappe.db.sql(f"""
            UPDATE 
                `tabContract Measurement Record` cmr
                INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                LEFT JOIN `tabHighway Kartado` hk ON CONCAT(cmrl.rodovia,'-',cmrl.via,'-',cmrl.sentido,'-',cmrl.faixa) = hk.rodovia
                LEFT JOIN `tabHighway` h ON hk.parent = h.name
                LEFT JOIN `tabHighway City` hc ON h.name = hc.parent AND cmrl.kminicial BETWEEN hc.kminicial AND hc.kmfinal
            SET 
                cmrl.cidade_name = hc.cidade, 
                cmrl.rodovia_name = h.name 
            WHERE 
                cmr.origem_integracao IN ('Osiris')  
                AND (cmrl.cidade_name IS NULL OR cmrl.rodovia_name IS NULL)
                AND hc.cidade IS NOT NULL 
                AND h.name IS NOT NULL AND 
                cmr.boletimmedicao = %(measurement)s;
            """,
            {"measurement": measurement, })
        update_records = frappe.db.sql(f"""
            UPDATE 
                `tabContract Measurement Record` cmr
                INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                LEFT JOIN `tabHighway Kartado` hk ON CONCAT(cmrl.rodovia,'-',cmrl.sentido,'-',cmrl.faixa) = hk.rodovia
                LEFT JOIN `tabHighway` h ON hk.parent = h.name
                LEFT JOIN `tabHighway City` hc ON h.name = hc.parent AND cmrl.kminicial BETWEEN hc.kminicial AND hc.kmfinal
            SET 
                cmrl.cidade_name = hc.cidade,
                cmrl.rodovia_name = h.name
            WHERE 
                cmr.origem_integracao IN ('Kartado RDO','Kartado Apontamento','Kartado Outros')
                AND (cmrl.cidade_name IS NULL OR cmrl.rodovia_name IS NULL) 
                AND hc.cidade IS NOT NULL 
                AND h.name IS NOT NULL AND 
                cmr.boletimmedicao = %(measurement)s;
            """,
            {"measurement": measurement, })
        # Atualiza cidades de apontamento auxiliar

        # Check highways
        data_records = frappe.db.sql(f"""
            WITH t_cities AS (
                {sql_citiess}
            )
            SELECT DISTINCT
                t_cities.rodovia
            FROM
                t_cities
            WHERE
                t_cities.rodovia_name IS NULL
            """,
            {"measurement": measurement, },
            as_dict=True)
        
        if data_records:
            for record in data_records:
                # Highway not found
                if not record.cidade:
                    r = f"{record.rodovia}"
                    if not r in error_highways:
                        error_highways[r] = f'Rodovia: {record.rodovia} sem relação com o cadastro do MSI.'

        # Check cities
        data_records = frappe.db.sql(f"""
            WITH t_cities AS (
                {sql_citiess}
            )
            SELECT DISTINCT
                t_cities.rodovia,
                t_cities.kminicial,
                t_cities.kmfinal
            FROM
                t_cities
            WHERE
                NOT t_cities.rodovia_name IS NULL AND 
                t_cities.cidade_name IS NULL
            """, 
            {"measurement": measurement, },
            as_dict=True)
        
        if data_records:
            for record in data_records:
                # Highway not found
                if not record.cidade:
                    r = f"{record.rodovia}-{record.kminicial}-{record.kmfinal}"
                    if not r in error_highways:
                        error_highways[r] = f'Rodovia: {record.rodovia}, Km Inicial: {record.kminicial}, Km Final: {record.kmfinal} sem relação com cidade.'

        write_inconsistencies(error_highways)
        
        return {
            "Processed": True,
            "errors": error_highways,
            "message": "Checagem de cidades e rodovias concluída."
        }
    except Exception as e:
        frappe.log_error(f"Error on update_cities: {str(e)}", "Measurement API")
        return None        

# @frappe.whitelist(methods=["POST"])
# def create_measurement_items_balance(measurement: str):
#     """
#     Create item balance for a measurement.
#     """
#     try:
#         # Get items to be processed
#         items = frappe.db.sql("""
#             SELECT
#                 cmi.name,
#                 cmi.itemcontrato,
#                 cmi.valortotalmedido,
#                 cmi.valorpago,
#                 cmi.fatorpagamento,
#                 c.name AS contrato,
#                 c.contratada,
#                 c.subsidiaria
#             FROM
#                 `tabContract Measurement Item` cmi
#                 INNER JOIN `tabContract Item` ci ON cmi.itemcontrato = ci.name
#                 INNER JOIN `tabContract` c ON ci.contrato = c.name
#             WHERE
#                 cmi.parent = %s AND 
#                 cmi.aplicar_performance = False AND 
#                 cmi.fatorpagamento > 0 AND 
#                 cmi.fatorpagamento <= 100 AND 
#                 cmi.valortotalmedido > 0
#             """, (measurement,), as_dict=True)

#         for item in items:

#             total = 0.0

#             # # Get measurement record 
#             # resrouces_records = frappe.db.sql("""
#             #     SELECT DISTINCT
#             #         cmr.name,
#             #         cmrr.valorcalculado,
#             #         cmir.name AS remaining_name
#             #     FROM
#             #         `tabContract Measurement Record` cmr
#             #         INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
#             #         LEFT JOIN `tabContract Measurement Item Remaining` cmir ON cmrr.name = cmir.contract_measurement_record                                          
#             #     WHERE
#             #         cmr.boletimmedicao = %s AND 
#             #         cmrr.item = %s
#             #         """,
#             #         (measurement, item.itemcontrato), as_dict=True)

#             resrouces_records = frappe.db.sql("""
#                 WITH t_recursos AS (
#                     SELECT
#                         cmr.name,
#                         cmrr.valorcalculado,
#                         cmir.name AS remaining_name
#                     FROM
#                         `tabContract Measurement Record` cmr
#                         INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
#                         LEFT JOIN `tabContract Measurement Item Remaining` cmir ON cmr.name = cmir.contract_measurement_record
#                     WHERE
#                         cmr.boletimmedicao = %(measurement)s AND
#                         cmrr.item = %(item)s
#                 ), t_funcoes AS(
#                 SELECT
#                         cmr.name,
#                         cmrwk.valorcalculado,
#                         cmir.name AS remaining_name
#                     FROM
#                         `tabContract Measurement Record` cmr
#                         INNER JOIN `tabContract Measurement Record Work Role` cmrwk ON cmr.name = cmrwk.parent
#                         LEFT JOIN `tabContract Measurement Item Remaining` cmir ON cmr.name = cmir.contract_measurement_record
#                     WHERE
#                         cmr.boletimmedicao = %(measurement)s AND
#                         cmrwk.item = %(item)s AND
#                         NOT cmr.name IN (SELECT name FROM t_recursos)
#                     UNION ALL
#                     SELECT
#                         name,
#                         valorcalculado,
#                         remaining_name
#                     FROM
#                         t_recursos
#                 ), t_ativos AS (
#                     SELECT
#                         cmr.name,
#                         cmra.valorcalculado,
#                         cmir.name AS remaining_name
#                     FROM
#                         `tabContract Measurement Record` cmr
#                         INNER JOIN `tabContract Measurement Record Asset` cmra ON cmr.name = cmra.parent
#                         LEFT JOIN `tabContract Measurement Item Remaining` cmir ON cmr.name = cmir.contract_measurement_record
#                     WHERE
#                         cmr.boletimmedicao = %(measurement)s AND
#                         cmra.item = %(item)s AND
#                         NOT cmr.name IN (SELECT name FROM t_funcoes)
#                     UNION ALL
#                     SELECT
#                         name,
#                         valorcalculado,
#                         remaining_name
#                     FROM
#                         t_funcoes
#                 )
#                 SELECT
#                     name,
#                     valorcalculado,
#                     remaining_name
#                 FROM
#                     t_ativos;
#             """, 
#             {
#                 'measurement': measurement,
#                 'item': item.itemcontrato
#             }, as_dict=True)

#             total_medido = 0.0
#             total_pago = 0.0
#             registros = len(resrouces_records)
#             conta_registros = 0

#             # total_recursos = sum(flt(record.valorcalculado if record.valorcalculado else 0.0) for record in resrouces_records)

#             for record in resrouces_records:

#                 conta_registros += 1

#                 if not record['remaining_name']:
#                     # Create a new remaining item if it does not exist
#                     remaining_item = frappe.new_doc("Contract Measurement Item Remaining")
#                 else:
#                     # Get the existing remaining item
#                     remaining_item = frappe.get_doc("Contract Measurement Item Remaining", record['remaining_name'])

#                 # Percentual que o recurso representa do total de recursos
#                 # fator = flt((record.valorcalculado if record.valorcalculado else 0.0) / total_recursos, 3)
#                 fator = flt(item.fatorpagamento / 100, 3) # flt((record.valorcalculado if record.valorcalculado else 0.0) / total_recursos, 3)

#                 # Calcula o valor medido e pago para o recurso
#                 # valor_medido = flt((record.valorcalculado if record.valorcalculado else 0.0) * fator,2)
#                 # valor_pago = flt((item.valorpago if item.valorpago else 0.0) * fator,2)
#                 valor_medido = record.valorcalculado if record.valorcalculado else 0.0
#                 valor_pago = flt(valor_medido * fator, 2)

#                 # Acumula os valores para o ajuste no último registro
#                 total_medido += valor_medido
#                 total_pago += valor_pago

#                 # Ajusta o valor medido e pago no último registro para fechar o total
#                 if conta_registros == registros:
#                     if total_medido > item.valortotalmedido:
#                         valor_medido -= flt(item.valortotalmedido - total_medido,2)
#                     else:   
#                         valor_medido += flt(total_medido - item.valortotalmedido,2)
#                     if total_pago > item.valorpago:
#                         valor_pago -= flt(item.valorpago - total_pago,2)
#                     else:
#                         valor_pago += flt(total_pago - item.valorpago,2)

#                 remaining_item.contract_measurement_record = record.name
#                 remaining_item.item = item.itemcontrato
#                 remaining_item.boletimmedicao = measurement
#                 remaining_item.valor = valor_medido
#                 remaining_item.valorpago = valor_pago
#                 remaining_item.subsidiaria = item.subsidiaria
#                 remaining_item.contrato = item.contrato
#                 remaining_item.contratada = item.contratada

#                 # Verifica se o item restante já possui pagamentos
#                 if len(remaining_item.tblpagamentos) == 0:
#                     remaining_item.append("tblpagamentos", {
#                         "boletimmedicao": measurement,
#                         "percentual": item.fatorpagamento,
#                         "valor": valor_pago,
#                         "datahora": frappe.utils.now_datetime(),
#                         "observacoes": "Saldo inicial",
#                         "origem": True
#                     })
#                 else:
#                     for ri in remaining_item.tblpagamentos:
#                         # Se o item restante já possui pagamentos, atualiza o primeiro
#                         if ri.origem:
#                             ri = remaining_item.tblpagamentos[0]
#                             ri.boletimmedicao = measurement
#                             ri.percentual = item.fatorpagamento
#                             ri.valor = valor_pago
#                             ri.datahora = frappe.utils.now_datetime()
#                             ri.observacoes = "Saldo inicial"
#                             ri.origem = True
#                         else:
#                             # Se o item restante tiver outros pagamentos, apenas adicione o novo
#                             total += ri.valor

#                 # Obtém as rodovias distintas do registro de medição
#                 highways = frappe.db.sql("""
#                     SELECT DISTINCT
#                         cmrl.rodovia_name,
#                         cmrl.kminicial, 
#                         cmrl.kmfinal
#                     FROM
#                         `tabContract Measurement Record Log` cmrl
#                     WHERE 
#                         cmrl.parent = %s
#                         """,
#                         (record.name, ), as_dict=True)
                
#                 remaining_item.set('tblrodovias', [])

#                 if highways:
#                     for highway in highways:
#                         # Adiciona a rodovia ao item restante
#                         remaining_item.append("tblrodovias", {
#                             "rodovia": highway.rodovia_name,
#                             "kminicial": highway.kminicial,
#                             "kmfinal": highway.kmfinal
#                         })

#                 # Salva o item restante
#                 remaining_item.saldo = flt(valor_medido - valor_pago, 2)
#                 remaining_item.save()

#         return {
#             "Processed": True,
#             "message": "Measurement items balance created successfully."
#         }
#     except Exception as e:
#         frappe.log_error(f"Error on create_measurement_items_balance: {str(e)}", "Measurement API")
#         return None            

@frappe.whitelist(methods=["POST"])
def create_measurement_items_balance(measurement: str):
    """
    Create item balance for a measurement.
    """
    try:
        # Get items to be processed
        items = frappe.db.sql("""
            SELECT
                cmi.name,
                cmi.itemcontrato,
                cmi.valortotalmedido,
                cmi.valorpago,
                cmi.fatorpagamento,
                c.name AS contrato,
                c.contratada,
                c.subsidiaria
            FROM
                `tabContract Measurement Item` cmi
                INNER JOIN `tabContract Item` ci ON cmi.itemcontrato = ci.name
                INNER JOIN `tabContract` c ON ci.contrato = c.name
            WHERE
                cmi.parent = %s AND 
                cmi.aplicar_performance = False AND 
                cmi.fatorpagamento > 0 AND 
                cmi.fatorpagamento < 100 AND 
                cmi.valortotalmedido > 0
            """, (measurement,), as_dict=True)

        for item in items:

            total = 0.0
          
            # Obter o registro de medição, para compatibilidade com PayFactor apenas o primeiro registro
            resources_records = frappe.db.sql("""
                SELECT
                    cmr.name
                FROM
                    `tabContract Measurement Record` cmr
                    INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
                    LEFT JOIN `tabContract Measurement Item Remaining` cmir ON cmrr.name = cmir.contract_measurement_record                                          
                WHERE
                    cmr.boletimmedicao = %s AND 
                    cmrr.item = %s
                LIMIT 1
                    """,
                    (measurement, item.itemcontrato), as_dict=True)

            total_medido = item.valortotalmedido
            total_pago = item.valorpago

            if (frappe.db.exists("Contract Measurement Item Remaining",{"parent_contract_measurement_item": item.name})):
                r_name = frappe.db.get_value("Contract Measurement Item Remaining",{"parent_contract_measurement_item": item.name}, "name")
                remaining_item = frappe.new_doc("Contract Measurement Item Remaining", r_name.name)
            else:
                remaining_item = frappe.new_doc("Contract Measurement Item Remaining")

            if resources_records:
                record = resources_records[0]
                remaining_item.contract_measurement_record = record.name
            remaining_item.parent_contract_measurement_item = item.name
            remaining_item.item = item.itemcontrato
            remaining_item.boletimmedicao = measurement
            remaining_item.valor = total_medido
            remaining_item.valorpago = total_pago
            remaining_item.subsidiaria = item.subsidiaria
            remaining_item.contrato = item.contrato
            remaining_item.contratada = item.contratada

            # Verifica se o item restante já possui pagamentos
            if len(remaining_item.tblpagamentos) == 0:
                remaining_item.append("tblpagamentos", {
                    "boletimmedicao": measurement,
                    "percentual": item.fatorpagamento,
                    "valor": total_pago,
                    "datahora": frappe.utils.now_datetime(),
                    "observacoes": "Saldo inicial",
                    "origem": True
                })
            else:
                for ri in remaining_item.tblpagamentos:
                    # Se o item restante já possui pagamentos, atualiza o primeiro
                    if ri.origem:
                        ri = remaining_item.tblpagamentos[0]
                        ri.boletimmedicao = measurement
                        ri.percentual = item.fatorpagamento
                        ri.valor = total_pago
                        ri.datahora = frappe.utils.now_datetime()
                        ri.observacoes = "Saldo inicial"
                        ri.origem = True
                    else:
                        # Se o item restante tiver outros pagamentos, apenas adicione o novo
                        total += ri.valor

            # Obtém as rodovias distintas do registro de medição
            if resources_records:
                record = resources_records[0]

                highways = frappe.db.sql("""
                    SELECT DISTINCT
                        cmrl.rodovia_name,
                        cmrl.kminicial, 
                        cmrl.kmfinal
                    FROM
                        `tabContract Measurement Record Log` cmrl
                    WHERE 
                        cmrl.parent = %s
                        """,
                        (record.name, ), as_dict=True)
                
                remaining_item.set('tblrodovias', [])

                if highways:
                    for highway in highways:
                        # Adiciona a rodovia ao item restante
                        remaining_item.append("tblrodovias", {
                            "rodovia": highway.rodovia_name,
                            "kminicial": highway.kminicial,
                            "kmfinal": highway.kmfinal
                        })

            # Salva o item restante
            remaining_item.saldo = flt(total_medido - total_pago, 2)
            remaining_item.save()

        return {
            "Processed": True,
            "message": "Measurement items balance created successfully."
        }
    except Exception as e:
        frappe.log_error(f"Error on create_measurement_items_balance: {str(e)}", "Measurement API")
        return None            

@frappe.whitelist(methods=["POST"])
def update_measurement_productivity(measurement: str):
    """
    Cria os registros para produtividade compensatória
    """
    try:
        frappe.db.sql("""
            UPDATE
                `tabContract Measurement Record Resource` update_cmrr
                INNER JOIN `tabContract Measurement Record` cmr ON update_cmrr.parent = cmr.name
                INNER JOIN `tabContract Item` update_ci ON update_cmrr.item = update_ci.name
                INNER JOIN `tabContract Measurement Record Resource` f_cmrr ON f_cmrr.parent = cmr.name
                INNER JOIN `tabContract Item` ci ON f_cmrr.item = ci.name AND   
                                                    ci.produtividadecompensatoria = 1 AND 
                                                    ci.templateitem = 'F'    
            SET
                update_cmrr.fresagem = f_cmrr.quantidademedida
            WHERE
                cmr.boletimmedicao = %s AND 
                NOT update_ci.templateitem IS NULL
        """,
        (measurement,))

        records = frappe.db.sql("""
            WITH daily_records AS (
                SELECT
                    DATE(cmr.dataexecucao) AS dataexecucao,
                    cmrr.item,
                    cmrr.equipe,
                    MAX(cmrl.rap) AS rap,            
                    SUM(cmrr.fresagem) AS fresagem,
                    SUM(cmrr.quantidademedida) AS quantidade,
                    ci.templateitem,
                    ci.contrato,
                    ci.codigo,
                    ci.descricao
                FROM
                    `tabContract Measurement Record` cmr
                    INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
                    INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                    INNER JOIN `tabContract Item` ci ON cmrr.item = ci.name 
                WHERE
                    cmr.boletimmedicao = %s AND 
                    ci.produtividadecompensatoria = 1 AND 
                    NOT ci.templateitem IS NULL
                GROUP BY
                    cmrr.equipe, 
                    cmrr.item, 
                    DATE(cmr.dataexecucao),
                    ci.templateitem,
                    ci.contrato,
                    ci.codigo,
                    ci.descricao
            )
            SELECT
                dr.dataexecucao,
                dr.item, 
                dr.equipe, 
                cp.faixa,
                dr.rap,       
                dr.fresagem, 
                dr.quantidade,
                dr.codigo,
                dr.descricao,
                dr.templateitem
            FROM
                daily_records dr
                LEFT JOIN `tabContract Price` cp ON cp.templateitem = dr.templateitem AND
                                                    dr.fresagem BETWEEN cp.volumeinicial AND cp.volumefinal AND 
                                                    cp.parent = dr.contrato AND
                                                    cp.rap = dr.rap
            ORDER BY
                dr.dataexecucao ASC,
                dr.equipe ASC,
                CASE 
                    WHEN dr.templateitem = 'F' THEN 1
                    WHEN dr.templateitem = 'Q' THEN 2
                    WHEN dr.templateitem = 'P' THEN 3
                END ASC,
                INET_ATON(SUBSTRING_INDEX(CONCAT(dr.codigo,'.0.0.0.0.0.0.0.0'), '.', 8)) ASC
            """,
        (measurement,), as_dict=True)

        if not records:
            return {
                "Processed": False,
                "message": "No compensatory productivity records found for this measurement."
            }

        measurement_doc = frappe.get_doc("Contract Measurement", measurement)

        measurement_doc.set('tblpc', [])

        for record in records:
            # Create a new record for compensatory productivity
            measurement_doc.append('tblpc', {
                'dataexecucao': record.dataexecucao,
                'item': record.item,
                'equipe': record.equipe,
                'faixa': record.faixa,
                'rap': record.rap,
                'fresagem': record.fresagem,
                'quantidade': record.quantidade
            })
        # Salva a medição antes de incluir os totais
        measurement_doc.save(ignore_permissions=True)

        # Calcula os totais 
        records = frappe.db.sql("""
            WITH cte_pc AS (
                SELECT
                    mp.item,
                    mp.equipe,
                    mp.faixa,
                    mp.rap,
                    ROUND(AVG(mp.fresagem), 3) AS fresagem,
                    ROUND(SUM(mp.quantidade), 9) AS quantidade,
                    ci.codigo,
                    ci.templateitem,
                    ci.contrato
                FROM
                    `tabContract Measurement Productivity` mp
                    INNER JOIN `tabContract Item` ci ON mp.item = ci.name
                WHERE
                    mp.parent = %s
                GROUP BY
                    mp.item,
                    mp.equipe,
                    mp.faixa,
                    mp.rap,
                    ci.codigo,
                    ci.templateitem,
                    ci.contrato)
            SELECT
                dr.item,
                dr.equipe,
                dr.faixa,
                dr.rap,
                dr.fresagem,
                dr.quantidade,
                cp.valor,
                ROUND(dr.quantidade * cp.valor, 2) AS valortotal,
                dr.codigo
            FROM
                cte_pc dr
                LEFT JOIN `tabContract Price` cp ON cp.templateitem = dr.templateitem AND
                                                    dr.fresagem BETWEEN cp.volumeinicial AND cp.volumefinal AND 
                                                    cp.parent = dr.contrato AND
                                                    cp.rap = dr.rap              
            ORDER BY
                dr.equipe ASC,
                dr.faixa ASC,
                dr.rap ASC,
                INET_ATON(SUBSTRING_INDEX(CONCAT(dr.codigo,'.0.0.0.0.0.0.0.0'), '.', 8)) ASC
        """, (measurement, ), as_dict=True)

        measurement_doc.set('tblpctotal', [])

        for record in records:
            measurement_doc.append('tblpctotal', {
                'item': record.item,
                'equipe': record.equipe,
                'faixa': record.faixa,
                'rap': record.rap,
                'fresagem': record.fresagem,
                'quantidade': record.quantidade,
                'valorunitario': record.valor,
                'valortotal': record.valortotal
            })
        # Save the measurement document
        measurement_doc.save(ignore_permissions=True)

        # Update measument
        frappe.db.sql("""
            UPDATE
                `tabContract Measurement Record Resource` cmrr
                INNER JOIN `tabContract Measurement Record` cmr ON cmr.name = cmrr.parent
                INNER JOIN `tabContract Item` ci ON cmrr.item = ci.name
                LEFT JOIN `tabContract Measurement Productivity` cmp ON cmrr.item = cmp.item AND 
                                                                DATE(cmp.dataexecucao) = DATE(cmr.dataexecucao) AND
                                                                cmp.parent = cmr.boletimmedicao
                LEFT JOIN `tabContract Measurement Productivity Total` cmpt ON cmpt.item = cmp.item AND 
                                                                        cmpt.parent = cmr.boletimmedicao AND 
                                                                        cmpt.equipe = cmp.equipe AND 
                                                                        cmpt.faixa = cmp.faixa AND
                                                                        cmpt.rap = cmp.rap 
            SET
                cmrr.valorunitario = cmpt.valorunitario,
                cmrr.valorcalculado = ROUND(cmpt.valorunitario * cmrr.quantidademedida, 2)
            WHERE
                cmr.boletimmedicao = %s
        """,
        (measurement,))

        return {
            "Processed": True,
            "message": "Compensatory productivity updated successfully."
        }
    except Exception as e:
        frappe.log_error(f"Error on update_measurement_productivity: {str(e)}", "Measurement API")
        return None           

@frappe.whitelist(methods=["POST"])
def create_measurement_sap_orders_records(measurement: str):
    """
    Sum the measurement orders for a given measurement.
    """
    try:
        contract_measurement = frappe.get_doc("Contract Measurement", measurement)
        contract_measurement.set('tablepedidossap', [])
        contract_measurement.set('tablepedidossapitem', [])
        contract_measurement.set('tabsapmunicipio', [])

        total_items = 0.0
        total_sap = 0.0
        for item in contract_measurement.tabitenscontatrato:
            total_items += item.valorpago

        # Verifica se é lancamento auxiliar
        query = """
            SELECT
                contract_item.name AS item,
                contract_item.codigo,
                note.valor,
                note.reidi,
                note.pedidosap,
                note.pedidolinha,
                note.percentual,
                note.saldo,
                cm_item.valorpago,
                note.creation,
                note.capexopex,
                note.pep,
                note.centrodecusto,
                note.valormedido
            FROM
                (
                    SELECT
                        cmr.apontamentodireto,
                        cmr.boletimmedicao,
                        sap_period.valor_para_o_periodo AS valor,
                        sap_period.reidi,
                        sap_period.parent AS pedidosap,
                        sap_period.name AS pedidolinha,
                        sap_period.percentual,
                        sap_period.saldo,
                        sap_period.creation,
                        sap_order.capexopex,
                        sap_period.pep,
                        sap_period.centrodecusto,
                        cmso.valormedido
                    FROM
                        `tabContract Measurement Record` cmr
                        INNER JOIN `tabContract Measurement Note` cmn ON cmn.name = cmr.apontamentodireto
                        INNER JOIN `tabContract Measurement Note SAP Order` cmso ON cmso.parent = cmn.name
                        INNER JOIN `tabSAP Order Period` sap_period ON sap_period.name = cmso.pedidolinha
                        INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    WHERE
                        cmr.boletimmedicao=%(measurement)s) note
                        INNER JOIN `tabContract Measurement Note Resource` cmnr ON cmnr.parent = note.apontamentodireto
                        INNER JOIN `tabContract Item` contract_item ON contract_item.name = cmnr.item
                        INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                                                                        AND cm_item.parent = note.boletimmedicao
        """
        records = frappe.db.sql(query,
            {
                'measurement': contract_measurement.name
            }, as_dict=True)

        # Carrega os registros de pedido SAP conforme informado no registro auxiliar
        has_aux = False
        if records:

            has_aux = True

            item_orders = {}
            item_orders_lines = {}
            orders_items = {}
            total_medido_itens = 0.0
            orders = {}

            for record in records:
                # Armazena os itens e o valor pago do item
                if not record['item'] in item_orders:
                    total_medido_itens += record['valorpago']
                    item_orders.setdefault(record['item'],
                                        {
                                            'saldo': record['valorpago'], 
                                            'descontar': 0.0,
                                            'medido': 0.0,
                                            'linhas': [],
                                            'linhas_com_saldo_com_percentual': [],
                                            'linhas_com_saldo_sem_percentual': [],
                                            'linhas_cidade': []
                                            })
                # O valor para lancamento auxiliar é fixo
                item_orders[record['item']]['medido'] += record['valormedido']
                # Carrega as linhas de pedido SAP para cada item
                item_order_line = f"{record['item']}{record['pedidolinha']}"
                if not item_order_line in item_orders_lines:
                    item_orders_lines.setdefault(item_order_line)
                    item_orders[record['item']]['linhas_com_saldo_sem_percentual'].append({
                        'pedidosap': record['pedidosap'],
                        'linha': record['pedidolinha'],
                        'percentual': record['percentual'],
                        'saldo': record['saldo'],
                        'valor': record['valor'],
                        'reidi': record['reidi'],
                        'medido': record['valormedido'],
                        'pep': record['pep'],
                        'centrodecusto': record['centrodecusto'],
                        'capexopex': record['capexopex']
                        })
                    if not record['pedidolinha'] in orders:
                        orders.setdefault(record['pedidolinha'])
                        total_sap += record['valormedido']

            # Carrega os itens
            item_count=0
            for item, data in item_orders.items():

                item_count+=1

                saldo_pedidos_sem_percentual = sum(p['saldo'] for p in data['linhas_com_saldo_sem_percentual'])

                for line in data['linhas_com_saldo_sem_percentual']:
                    if not line['linha'] in orders_items:
                        orders_items.setdefault(line['linha'], 
                                                {
                                                    'pedidosap': line['pedidosap'],
                                                    'saldo': line['saldo'], 
                                                    'valor': line['valor'], 
                                                    'reidi': line['reidi'],
                                                    'percentual': line['percentual'],
                                                    'pep': line['pep'],
                                                    'centrodecusto': line['centrodecusto'],
                                                    'capexopex': line['capexopex'],
                                                    'rateio': 0.0,
                                                    'medido': line['medido'],
                                                    'items': []
                                                })
                    # Fator proporcional do saldo do pedido SAP sobre o total de pedidos com percentual
                    factor = (line['saldo'] / saldo_pedidos_sem_percentual)
                    valor = flt((data['saldo'] * (line['percentual']/100))*factor, 2)
                    total_sap += valor
                    orders_items[line['linha']]['items'].append({
                        'linha': line['linha'],
                        'medido': valor,
                        'item': item})

            # Aplica a diferenca no primeiro item
            diff = total_items - total_sap
            if abs(diff) > 0.001:
                for line, data in orders_items.items():
                    data['medido'] += diff
                    break

        # Senão carrega pela regra geral
        else:

            query="""
                WITH linha_vinculada AS (
                    -- Linha de pedido vinculada ao item
                    SELECT
                        contract_item.name AS item,
                        contract_item.codigo,
                        sap_period.valor_para_o_periodo AS valor,
                        sap_period.reidi,
                        sap_period.parent AS pedidosap,
                        sap_period.name AS pedidolinha,
                        CASE WHEN sap_period.percentual IS NULL
                            OR sap_period.percentual = 0 THEN CASE WHEN item_order.percentual IS NULL THEN 0 ELSE item_order.percentual END ELSE sap_period.percentual END AS percentual,
                        sap_period.saldo,
                        cm_item.valorpago,
                        sap_period.creation,
                        sap_order.capexopex,
                        sap_period.pep,
                        sap_period.centrodecusto
                    FROM
                        `tabContract Item` contract_item
                            INNER JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent
                            INNER JOIN `tabSAP Order Period` sap_period ON sap_period.name = item_order.pedidolinha
                            INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                            INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                    WHERE
                        NOT item_order.pedidolinha IS NULL
                        AND NOT cm_item.valorpago = 0
                        AND sap_period.saldo > 0
                        AND sap_order.faturamentodireto = 0
                        AND cm_item.parent = %(measurement)s
                        AND contract_item.contrato = %(contract)s
                    ),
                    pep_vinculado AS (
                -- PEP da linha do pedido com PEP do item
                SELECT
                    contract_item.name AS item,
                    contract_item.codigo,
                    sap_period.valor_para_o_periodo AS valor,
                    sap_period.reidi,
                    sap_period.parent AS pedidosap,
                    sap_period.name AS pedidolinha,
                    CASE WHEN sap_period.percentual IS NULL
                    OR sap_period.percentual = 0 THEN CASE WHEN item_order.percentual IS NULL THEN 0 ELSE item_order.percentual END ELSE sap_period.percentual END AS percentual,
                    sap_period.saldo,
                    cm_item.valorpago,
                    sap_period.creation,
                    sap_order.capexopex,
                    sap_period.pep,
                    sap_period.centrodecusto
                FROM
                    `tabContract Item` contract_item
                    INNER JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent
                    AND item_order.pedidolinha IS NULL
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.parent = item_order.pedidosap
                    AND YEAR (sap_period.datainicial) <= %(start_year)s
                    AND YEAR (sap_period.datafinal) >= %(end_year)s
                    AND sap_period.pep = contract_item.codigopep
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                WHERE
                    contract_item.is_group = 0
                    AND NOT cm_item.valorpago = 0
                    AND sap_period.saldo > 0
                    AND sap_order.faturamentodireto = 0
                    AND cm_item.parent = %(measurement)s
                    AND contract_item.contrato = %(contract)s
                    AND NOT sap_period.name IN (
                        SELECT
                            pedidolinha
                        FROM
                            linha_vinculada
                        )
                UNION ALL
                SELECT
                    item,
                    codigo,
                    valor,
                    reidi,
                    pedidosap,
                    pedidolinha,
                    percentual,
                    saldo,
                    valorpago,
                    creation,
                    capexopex,
                    pep,
                    centrodecusto
                FROM
                    linha_vinculada
                    ),
                    pedido_vinculado AS (
                -- Apenas pedido vinculado, porem sem PEP ou linha vincualda ao item
                SELECT
                    contract_item.name AS item,
                    contract_item.codigo,
                    sap_period.valor_para_o_periodo AS valor,
                    sap_period.reidi,
                    sap_period.parent AS pedidosap,
                    sap_period.name AS pedidolinha,
                    CASE WHEN sap_period.percentual IS NULL
                    OR sap_period.percentual = 0 THEN CASE WHEN item_order.percentual IS NULL THEN 0 ELSE item_order.percentual END ELSE sap_period.percentual END AS percentual,
                    sap_period.saldo,
                    cm_item.valorpago,
                    sap_period.creation,
                    sap_order.capexopex,
                    sap_period.pep,
                    sap_period.centrodecusto
                FROM
                    `tabContract Item` contract_item
                    INNER JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent
                    AND item_order.pedidolinha IS NULL
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.parent = item_order.pedidosap
                    AND YEAR (sap_period.datainicial) <= %(start_year)s
                    AND YEAR (sap_period.datafinal) >= %(end_year)s
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                WHERE
                    contract_item.is_group = 0
                    AND NOT cm_item.valorpago = 0
                    AND sap_period.saldo > 0
                    AND sap_order.faturamentodireto = 0
                    AND cm_item.parent = %(measurement)s
                    AND contract_item.contrato = %(contract)s
                    AND NOT sap_period.name IN (
                    SELECT
                    pedidolinha
                    FROM
                    pep_vinculado
                    )
                UNION ALL
                SELECT
                    item,
                    codigo,
                    valor,
                    reidi,
                    pedidosap,
                    pedidolinha,
                    percentual,
                    saldo,
                    valorpago,
                    creation,
                    capexopex,
                    pep,
                    centrodecusto
                FROM
                    pep_vinculado
                    ),
                    nenhum_vinculo AS (
                -- Nenhum vinculo, pesquisa linhas para o contrato
                SELECT
                    contract_item.name AS item,
                    contract_item.codigo,
                    sap_period.valor_para_o_periodo AS valor,
                    sap_period.reidi,
                    sap_period.parent AS pedidosap,
                    sap_period.name AS pedidolinha,
                    sap_period.percentual,
                    sap_period.saldo,
                    cm_item.valorpago,
                    sap_period.creation,
                    sap_order.capexopex,
                    sap_period.pep,
                    sap_period.centrodecusto
                FROM
                    `tabContract Item` contract_item
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.contrato = contract_item.contrato
                    AND YEAR (sap_period.datainicial) <= %(start_year)s
                    AND YEAR (sap_period.datafinal) >= %(end_year)s
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                    LEFT JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent
                WHERE
                    contract_item.is_group = 0
                    AND item_order.name IS NULL
                    AND item_order.pedidolinha IS NULL
                    AND NOT cm_item.valorpago = 0
                    AND sap_period.saldo > 0
                    AND sap_order.faturamentodireto = 0
                    AND cm_item.parent = %(measurement)s
                    AND contract_item.contrato = %(contract)s
                    AND NOT sap_period.name IN (
                        SELECT
                            pedidolinha
                        FROM
                            pedido_vinculado
                    )
                UNION ALL
                SELECT
                    item,
                    codigo,
                    valor,
                    reidi,
                    pedidosap,
                    pedidolinha,
                    percentual,
                    saldo,
                    valorpago,
                    creation,
                    capexopex,
                    pep,
                    centrodecusto
                FROM
                    pedido_vinculado
                    )
                SELECT
                    item,
                    codigo,
                    valor,
                    reidi,
                    pedidosap,
                    pedidolinha,
                    percentual,
                    saldo,
                    valorpago,
                    creation,
                    capexopex,
                    pep,
                    centrodecusto
                FROM
                    nenhum_vinculo
                ORDER BY
                    INET_ATON(
                            SUBSTRING_INDEX(
                                    CONCAT(codigo, '.0.0.0.0.0.0.0.0'),
                                    '.',
                                    8
                            )
                    )
            """

            records = frappe.db.sql(query,
                {
                    'start_year': contract_measurement.datainicialmedicao.year,
                    'end_year': contract_measurement.datafinalmedicao.year,
                    'measurement': contract_measurement.name,
                    'contract': contract_measurement.contrato
                }, as_dict=True)
        
            item_orders = {}
            item_orders_lines = {}
            orders_items = {}
            total_medido_itens = 0.0

            for record in records:
                # Armazena os itens e o valor pago do item
                if not record['item'] in item_orders:
                    total_medido_itens += record['valorpago']
                    item_orders.setdefault(record['item'],
                                        {
                                            'saldo': record['valorpago'], 
                                            'descontar': 0.0,
                                            'medido': 0.0,
                                            'linhas_com_saldo_com_percentual': [], 
                                            'linhas_com_saldo_sem_percentual': [],
                                            'linhas_cidade': []
                                            })
                # Carrega as linhas de pedido SAP para cada item
                item_order_line = f"{record['item']}{record['pedidolinha']}"
                if not item_order_line in item_orders_lines:
                    item_orders_lines.setdefault(item_order_line)
                    if record['percentual']>0.0:
                        # Separa os pedidos SAP com percentuais definidos
                        item_orders[record['item']]['linhas_com_saldo_com_percentual'].append({
                            'pedidosap': record['pedidosap'],
                            'linha': record['pedidolinha'],
                            'percentual': record['percentual'],
                            'saldo': record['saldo'],
                            'valor': record['valor'],
                            'reidi': record['reidi'],
                            'pep': record['pep'],
                            'centrodecusto': record['centrodecusto'],
                            'capexopex': record['capexopex']
                        })
                    else:
                        # Separa os pedidos SAP sem percentuais definidos
                        item_orders[record['item']]['linhas_com_saldo_sem_percentual'].append({
                            'pedidosap': record['pedidosap'],
                            'linha': record['pedidolinha'],
                            'percentual': 0.0,
                            'saldo': record['saldo'],
                            'valor': record['valor'],
                            'reidi': record['reidi'],
                            'pep': record['pep'],
                            'centrodecusto': record['centrodecusto'],
                            'capexopex': record['capexopex']
                        })

            # Calcula primeiro as linhas com percentual definido, como IPCA
            # descontanto o valor do saldo do pagamento do item
            item_count=0
            for item, data in item_orders.items():

                item_count+=1
                print(f"Processando com percentual item {item_count} de {len(item_orders)}")

                saldo_pedidos_com_percentual = sum(p['saldo'] for p in data['linhas_com_saldo_com_percentual'])

                for line in data['linhas_com_saldo_com_percentual']:
                    if not line['linha'] in orders_items:
                        orders_items.setdefault(line['linha'], 
                                                {
                                                    'pedidosap': line['pedidosap'],
                                                    'saldo': line['saldo'], 
                                                    'valor': line['valor'], 
                                                    'reidi': line['reidi'],
                                                    'percentual': line['percentual'],
                                                    'pep': line['pep'],
                                                    'centrodecusto': line['centrodecusto'],
                                                    'capexopex': line['capexopex'],
                                                    'rateio': 0.0,
                                                    'medido': 0.0,
                                                    'items': []
                                                })
                    # Fator proporcional do saldo do pedido SAP sobre o total de pedidos com percentual
                    factor = (line['saldo'] / saldo_pedidos_com_percentual)
                    valor = flt((data['saldo'] * (line['percentual']/100))*factor, 2)
                    orders_items[line['linha']]['medido'] += valor
                    orders_items[line['linha']]['items'].append({
                        'linha': line['linha'],
                        'medido': valor,
                        'item': item})
                    data['medido'] += valor
                    data['descontar'] += valor

            # Ajusta o valor dos saldos dos itens
            total_descontar = 0.0
            saldo_total = 0.0
            for item, data in item_orders.items():
                total_descontar += data['descontar']
                data['saldo'] -= data['descontar']
                saldo_total += data['saldo']

            # Para pedidos sem percentual definido, rateia o saldo restante do item entre os pedidos carregados para o item
            item_count=0
            for item, data in item_orders.items():

                item_count+=1
                print(f"Processando SEM percentual item {item_count} de {len(item_orders)}")

                saldo_pedidos_sem_percentual = sum(p['saldo'] for p in data['linhas_com_saldo_sem_percentual'])

                # Processa apenas itens com saldo
                saldo_item = data['saldo'] 
                for line in data['linhas_com_saldo_sem_percentual']:

                    percentual = (line['saldo']/saldo_pedidos_sem_percentual)

                    if not line['linha'] in orders_items:

                        orders_items.setdefault(line['linha'], 
                                                {
                                                    'pedidosap': line['pedidosap'],
                                                    'saldo': line['saldo'], 
                                                    'valor': line['valor'], 
                                                    'reidi': line['reidi'],
                                                    'pep': line['pep'],
                                                    'centrodecusto': line['centrodecusto'],
                                                    'capexopex': line['capexopex'],
                                                    'percentual': 0.0,
                                                    'rateio': 0.0,
                                                    'medido': 0.0, 
                                                    'items': []
                                                })
                        
                    valor = flt(saldo_item * percentual, 2)

                    # # Previne valor negativo
                    # if abs(item_orders[item]['medido'] + valor) >= abs(data['saldo']):
                    #     valor = flt(data['saldo'] - item_orders[item]['medido'], 2)

                    item_orders[item]['medido'] += flt(valor, 2)
                    orders_items[line['linha']]['medido'] += flt(valor, 2)
                    orders_items[line['linha']]['items'].append({
                        'linha': line['linha'],
                        'medido': flt(valor, 2),
                        'item': item})      

                # Variavel de controle de loop
                iteration_count = 0
                while True:
                    # Carrega os totais para checar diferenças
                    saldo_item = (data['saldo']+data['descontar'])
                    total_medido = flt(item_orders[item]['medido'], 2)
                    diff = flt(saldo_item - total_medido, 2)
                    sap_count = len(data['linhas_com_saldo_sem_percentual'])
                    # Se houver diferença, redistribui centavos
                    if abs(diff) >= 0.01:
                        step = 0.01 if diff > 0 else -0.01
                        idx = 0
                        while abs(diff) >= 0.01:
                            sap_idx = idx % sap_count
                            o_line = data['linhas_com_saldo_sem_percentual'][sap_idx]['linha']
                            # Verifica se a linha do pedido consta na lista de pedidos do item
                            if not o_line in orders_items:
                                idx += 1
                                continue
                            # Previne valortotal negativo
                            if step < 0 and abs(orders_items[o_line]['medido']) + step < 0:
                                idx += 1
                                continue
                            # Aplica o fator a linha do pedido
                            orders_items[o_line]['medido'] += step
                            # Aplica o fator a totalização de itens
                            item_orders[item]['medido'] += step
                            diff -= step
                            idx += 1
                            iteration_count += 1
                            if iteration_count > 1000:
                                frappe.log_error(f"Erro ao ajustar os valores dos pedidos SAP na medição {measurement}.", "Measurement API")
                                return {
                                    "Processed": False,
                                    "message": f"Erro ao ajustar os valores dos pedidos SAP na medição {measurement}."
                                }
                    # saldo_item = data['saldo']
                    total_medido = flt(item_orders[item]['medido'], 2)
                    diff = flt(saldo_item - total_medido, 2)
                    if abs(saldo_item - total_medido) < 0.001:
                        break

        # Verifica a existencia de uma medicao anterior
        m_number = measurement[-3:]
        if m_number == "001":
            last_contract_measurement = None
        else:
            last_contract_measurement = f"{measurement[:-3]}{int(m_number)-1:03}"

        for line, order in orders_items.items():

            medicaoacumantpercentual = 0.0
            acumuladoanterior = 0.0
            saldoanterior = 0.0

            # Recupera os dados da ultima medicao
            if last_contract_measurement:

                last_contract_measurement_sap_order = None
                records = frappe.db.sql(""" 
                    SELECT
                        medicaoacumantpercentual,
                        acumuladoatual,
                        saldo
                    FROM
                        `tabContract Measurement SAP Order`
                    WHERE
                        linhapedido = %s AND 
                        parent = %s """, 
                    (line, last_contract_measurement), as_dict=True)
                if records:
                    last_contract_measurement_sap_order = records[0]
                
                if last_contract_measurement_sap_order:
                    medicaoacumantpercentual = last_contract_measurement_sap_order['medicaoacumantpercentual']
                    acumuladoanterior = last_contract_measurement_sap_order['acumuladoatual']
                    saldoanterior = last_contract_measurement_sap_order['saldo']
            
            else:
                # Sem medição anterior o saldo é igual ao saldo atual
                saldoanterior = order['saldo']

            # Mount the SAP Order to the contract measurement
            contract_measurement_sap_order = contract_measurement.append("tablepedidossap")
            contract_measurement_sap_order.pedido_sap = order['pedidosap']
            contract_measurement_sap_order.linhapedido = line
            contract_measurement_sap_order.valortotalvigente = order['valor']
            contract_measurement_sap_order.medicaoacumantpercentual = medicaoacumantpercentual
            contract_measurement_sap_order.medicaoatualpercentual = flt((order['medido']/order['valor'])*100, 3)
            contract_measurement_sap_order.medicaoacumuladaatualpercentual = flt(((order['medido']+acumuladoanterior)/order['valor'])*100, 3)
            contract_measurement_sap_order.acumuladoanterior = acumuladoanterior
            contract_measurement_sap_order.valormedido = order['medido']
            contract_measurement_sap_order.acumuladoatual = acumuladoanterior + order['medido']
            contract_measurement_sap_order.reidi = order['reidi']
            contract_measurement_sap_order.valor_medicao_reidi = flt(order['medido']*(order['reidi']/100), 2)
            contract_measurement_sap_order.saldoanterior = saldoanterior
            contract_measurement_sap_order.saldo = order['saldo'] - order['medido']
            contract_measurement_sap_order.capexopex = order['capexopex']
            contract_measurement_sap_order.pep = order['pep']
            contract_measurement_sap_order.centrodecusto = order['centrodecusto']

            current_item = 0
            items_count = len(order['items'])
            for item in order['items']:
                rateio = flt((item['medido']/total_medido_itens) * 100, 3)
                # Lista auxiliar para carga de pedidos por cidade
                item_orders[item['item']]['linhas_cidade'].append({
                    'linha': line,
                    'pedidosap': order['pedidosap'],
                    'saldo': order['saldo'],
                    'percentual': order['percentual'],
                    'pep': order['pep'],
                    'centrodecusto': order['centrodecusto'],
                    'capexopex': order['capexopex']
                })
                contract_measurement_sap_order_item = contract_measurement.append("tablepedidossapitem")
                contract_measurement_sap_order_item.item = item['item']
                contract_measurement_sap_order_item.pedido_sap = order['pedidosap']
                contract_measurement_sap_order_item.linhapedido = line
                contract_measurement_sap_order_item.valortotalvigente = order['valor']
                contract_measurement_sap_order_item.percentualfixo = order['percentual']
                contract_measurement_sap_order_item.rateio = rateio
                contract_measurement_sap_order_item.valordotitem = item['medido']
                contract_measurement_sap_order_item.capexopex = order['capexopex']
                contract_measurement_sap_order_item.pep = order['pep']
                contract_measurement_sap_order_item.centrodecusto = order['centrodecusto']
                current_item += 1
                if (current_item == items_count) and (abs(order['medido'] - sum(i['medido'] for i in order['items'])) >= 0.01):
                    diff = flt(order['medido'] - sum(i['medido'] for i in order['items']), 2)
                    contract_measurement_sap_order_item.valordotitem = flt(item['medido'] + diff, 2)

        city_orders = {}

        # Monta a matriz de rateio por cidade
        if has_aux:
            # Se origem for lançamento auxiliar, não faz rateio por cidade, apenas divide igualmente
            
            #Lista auxiliar de rateio
            sap_values = {}

            for city in contract_measurement.tablemunicipios:
                city_orders.setdefault(city.municipio, {
                    'totalitens': 0.0,
                    'totallinhas': 0.0,
                    'itens': {},
                    'linhas': {}
                })

            # Numero de cidades para rateio simples
            num_cities = len(city_orders)

            for city, city_values in city_orders.items():

                # Rateio simples por cidade
                sap_total = 0.0
                for line, order in orders_items.items():
                    sap_values.setdefault(line, {
                        'medido': order['medido'],
                        'rateio': 0.0
                    })
                    sap_value = flt(order['medido'] / num_cities, 2)
                    sap_total += sap_value
                    city_values['linhas'].setdefault(line, {
                        'pedidosap': order['pedidosap'],
                        'rateio': 0.0,
                        'medido': sap_value,
                        'capexopex': order['capexopex'],
                        'pep': order['pep'],
                        'centrodecusto': order['centrodecusto']
                    })
                    sap_values[line]['rateio'] += sap_value

            for line, values in sap_values.items():
                # Carrega a diferença do rateio para a ultima cidade da lista
                diff = flt(values['medido'] - values['rateio'], 2)
                if abs(diff) >= 0.01:
                    # Pega a ultima cidade da lista
                    last_city = list(city_orders.keys())[-1]
                    city_orders[last_city]['linhas'][line]['medido'] += diff

        else:
            # Rateios normais
            
            # Cria a lista de itens por cidade
            for city in contract_measurement.tblmunicipiositem:

                if city.valor == 0:
                    continue

                if not city.municipio in city_orders:
                    city_orders.setdefault(city.municipio, {
                        'totalitens': 0.0,
                        'totallinhas': 0.0,
                        'itens': {},
                        'linhas': {}
                    })

                # Ignorar itens que não estejam na lista
                if not city.item in item_orders:
                    continue

                if not city.item in city_orders[city.municipio]['itens']:
                    city_orders[city.municipio]['itens'].setdefault(city.item, 0.0)

                city_orders[city.municipio]['itens'][city.item] += city.valor
                city_orders[city.municipio]['totalitens'] += city.valor

            for city, city_values in city_orders.items():

                for item, item_value in city_values['itens'].items():

                    # Totalizacao para rateio
                    sem_percentual_saldo = sum(0.0 if l['percentual'] > 0.0 else l['saldo'] for l in item_orders[item]['linhas_cidade'])
                    com_percentual_saldo = sum(l['saldo'] if l['percentual'] > 0.0 else 0.0 for l in item_orders[item]['linhas_cidade'])

                    def proccess_line(line_values: Dict, total: float, grand_total: float, wiht_percentual: bool) -> float:
                        """
                        Processa as linhas do pedido SAP para rateio por cidade
                        e retorna o total rateado para controle interno
                        na medição.
                        Parâmetros:
                            line_values: Lista de linhas do pedido SAP do item
                            total: Valor total do item na cidade
                            grand_total: valor total das cidades para o item
                            wiht_percentual: Indica se processa linhas com ou sem percentual definido
                        Retorno:
                            lines_total: Total rateado para a cidade
                        """

                        lines_total = 0.0

                        for line_value in line_values:

                            # Filtra linhas com e sem percentual
                            if wiht_percentual and line_value['percentual'] == 0.0:
                                continue
                            if (not wiht_percentual) and line_value['percentual'] > 0:
                                continue

                            # Pedido SAP com percentual definido
                            percentual_prop = 1.0
                            if line_value['percentual'] > 0.0:
                                percentual = line_value['percentual']
                                percentual_prop = (line_value['saldo'] / grand_total)

                            # Pedido SAP sem percentual definido
                            else:
                                percentual = flt((line_value['saldo'] / grand_total) * 100, 3)
                                # Calculo do valor medido

                            # Calculo do valor medido
                            medido = flt(total * (percentual/100)*percentual_prop, 2)

                            line = line_value['linha']
                            # Cria a linha do pedido SAP na cidade
                            if not line in city_values['linhas']:
                                city_values['linhas'].setdefault(line, {
                                    'pedidosap': line_value['pedidosap'],
                                    'percentual': line_value['percentual'],
                                    'capexopex': line_value['capexopex'],
                                    'pep': line_value['pep'],
                                    'centrodecusto': line_value['centrodecusto'],
                                    'rateio': 0.0,
                                    'medido': 0.0
                                })
                            city_values['linhas'][line]['medido'] += medido
                            city_values['totallinhas'] += medido
                            lines_total += medido
                        
                        return lines_total

                    # Primeiro processa as linhas com percentual definido     
                    total_com_percentual_saldo = proccess_line(
                        item_orders[item]['linhas_cidade'],
                        item_value,
                        com_percentual_saldo,
                        True)
                    
                    # Depois processa as linhas sem percentual definido
                    proccess_line(
                        item_orders[item]['linhas_cidade'],
                        item_value - total_com_percentual_saldo,
                        sem_percentual_saldo,
                        False)
                        
                # Variavel de controle de loop
                iteration_count = 0
                while True:
                    # Carrega os totais para checar diferenças
                    total_items = city_values['totalitens']
                    total_linhas = city_values['totallinhas']
                    diff = flt(total_items - total_linhas, 2)
                    numero_linhas = len(city_values['linhas'])
                    keys = list(city_values['linhas'].keys())
                    # Se houver diferença, redistribui centavos
                    if abs(diff) >= 0.01:
                        step = 0.01 if diff > 0 else -0.01
                        idx = 0
                        while abs(diff) >= 0.01:
                            linha_idx = idx % numero_linhas
                            # Previne valortotal negativo
                            key = keys[linha_idx]
                            if step < 0 and city_values['linhas'][key]['medido'] + step < 0:
                                idx += 1
                                continue
                            # Aplica o fator a linha do pedido
                            city_values['linhas'][key]['medido'] += step
                            # Aplica o fator a totalização das linhas
                            city_values['totallinhas'] += step
                            diff -= step
                            idx += 1
                            iteration_count += 1
                            if iteration_count > 100000:
                                frappe.log_error(f"Erro ao ajustar os valores dos pedidos SAP para cidades na medição {measurement}.", "Measurement API")
                                return {
                                    "Processed": False,
                                    "message": f"Erro ao ajustar os valores dos pedidos SAP para cidades na medição {measurement}."
                                }
                    total_linhas = city_values['totallinhas']
                    if abs(flt(total_items - total_linhas, 2)) < 0.001:
                        break

        # Adiciona as cidades a medição
        for city, values in city_orders.items():
            for line, values in values['linhas'].items():
                contract_measurement_sap_order_city = contract_measurement.append("tabsapmunicipio")
                contract_measurement_sap_order_city.pedidosap = values['pedidosap']
                contract_measurement_sap_order_city.linhapedido = line
                contract_measurement_sap_order_city.municipio = city
                contract_measurement_sap_order_city.rateio = values['rateio']
                contract_measurement_sap_order_city.valor = values['medido']    
                contract_measurement_sap_order_city.capexopex = values['capexopex']
                contract_measurement_sap_order_city.pep = values['pep']
                contract_measurement_sap_order_city.centrodecusto = values['centrodecusto']

        contract_measurement.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "message": "Contract measurement orders created successfully"
        }
    except Exception as e:
        print(f"Error on create_measurement_sap_orders_records: {str(e)}")
        frappe.log_error(f"Error on create_measurement_sap_orders_records: {str(e)}", "Measurement API")
        return None       
    
@frappe.whitelist(methods=["POST"])
def check_orphans_records(measurement: str):
    """
    Verifica registros de mão de obra e ativos orfãos, que tem registros 
    carregados porem sem informação nos itens contratuais
    """
    try:
        # Verifica registros de mão de obra
        records = frappe.db.sql(
            """
                SELECT
                    cmrwr.item,
                    cmrwr.funcao,
                    ci.valorunitario,
                    ci.quantidade
                FROM
                    `tabContract Measurement Record` cmr 
                    INNER JOIN `tabContract Measurement Record Work Role` cmrwr ON cmr.name = cmrwr.parent
                    INNER JOIN `tabContract Item` ci ON ci.name = cmrwr.item
                    LEFT JOIN `tabContract Item Work Role` ciwr ON ciwr.parent = ci.name AND 
                                                        ciwr.funcao = cmrwr.funcao   
                WHERE
                    cmr.boletimmedicao = %s
                GROUP BY
                    cmrwr.item,
                    cmrwr.funcao,
                    ci.valorunitario,
                    ci.quantidade
                HAVING
                    COUNT(ciwr.name) = 0
            """, 
            (measurement,), 
            as_dict=True)

        # Cria os registros de mão de obra
        if len(records)>0:
            last_item = None
            item = None
            for idx, r in enumerate(records):

                if not last_item == r['item']:
                    if item:
                        item.save(ignore_permissions=True)
                    last_item = r['item']
                    item = frappe.get_doc('Contract Item', r['item'])

                # Adicona a mão de obra
                item_wk = item.append("tablemaodeobra")
                item_wk.funcao = r['funcao']
                item_wk.quantidade = r['quantidade']
                item_wk.valortotalmensal = r['valorunitario']
                item_wk.valorporhora = 0.0
                item_wk.pagamentohora = False

                if idx == len(records) - 1:
                    if item:
                        item.save(ignore_permissions=True)

        # Verifica registros de ativos
        records = frappe.db.sql(
            """
                SELECT
                    cmra.item,
                    cmra.maquina_equipamento_ou_ferramenta,
                    ci.valorunitario,
                    ci.quantidade
                FROM
                    `tabContract Measurement Record` cmr 
                    INNER JOIN `tabContract Measurement Record Asset` cmra ON cmr.name = cmra.parent
                    INNER JOIN `tabContract Item` ci ON ci.name = cmra.item
                    LEFT JOIN `tabContract Item Asset` cia ON cia.parent = ci.name AND 
                                                            cia.asset = cmra.maquina_equipamento_ou_ferramenta
                WHERE
                    cmr.boletimmedicao = %s
                GROUP BY
                    cmra.item,
                    cmra.maquina_equipamento_ou_ferramenta,
                    ci.valorunitario,
                    ci.quantidade
                HAVING
                    COUNT(cia.name) = 0
            """, 
            (measurement,), 
            as_dict=True)

        # Cria os registros de ativos
        if len(records)>0:
            last_item = None
            item = None
            for idx, r in enumerate(records):

                if not last_item == r['item']:
                    if item:
                        item.save(ignore_permissions=True)
                    last_item = r['item']
                    item = frappe.get_doc('Contract Item', r['item'])

                # Adicona o ativo
                item_a = item.append("tableassets")
                item_a.asset = r['maquina_equipamento_ou_ferramenta']
                item_a.quantidade = r['quantidade']
                item_a.valorunitario = 0.0
                item_a.valormensal = r['valorunitario']

                if idx == len(records) - 1:
                    if item:
                        item.save(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Error on check_orphans_records: {str(e)}", "Measurement API")
        return None  

@frappe.whitelist(methods=["GET"])
def get_measurements_orders(datainicial: str, datafinal: str):
    """
    Retorna as medições com pedidos SAP vinculados para o contrato e período informado
    """
    try:
        records = frappe.db.sql(
            """
                WITH latest_approvals AS (
                    SELECT
                        boletim,
                        etapa,
                        dataehora
                    FROM (
                            SELECT
                                cms.parent as boletim,
                                cm.workflow_state AS etapa,
                                cms.dataehora,
                                ROW_NUMBER() OVER (
                                    PARTITION BY cms.parent
                                    ORDER BY cms.dataehora DESC
                                ) AS rn
                            FROM
                                `tabContract Measurement State` cms
                                INNER JOIN `tabContract Measurement` cm ON cm.name = cms.parent
                            WHERE
                                cm.workflow_state NOT IN ('Devolvido','Aberto')
                        ) ranked
                    WHERE 
                        rn = 1
                        AND dataehora BETWEEN %s AND %s
                )
                SELECT
                    so.numeropedido as pedido,
                    sop.linhapedido as item,
                    sop.pep as elemento_pep,
                    sop.centrodecusto as centro_custo,
                    cmso.valormedido as valor_medicao,
                    cmso.reidi as aliquota_reidi,
                    la.dataehora as data_aprovacao,
                    la.boletim as nr_boletim,
                    la.etapa as status_do_boletim
                FROM
                    latest_approvals la
                    INNER JOIN `tabContract Measurement SAP Order` cmso ON cmso.parent = la.boletim
                    INNER JOIN `tabSAP Order Period` sop ON sop.name = cmso.linhapedido
                    INNER JOIN `tabSAP Order` so ON so.name = sop.parent; """,
            (f"{datainicial} 00:00:00", f"{datafinal} 23:59:59"), 
            as_dict=True)

        return records
    except Exception as e:
        frappe.log_error(f"Error on get_measurements_orders: {str(e)}", "Measurement API")
        return None 

def set_measurement_adjustment(adjustment: str, contract: str) -> str:
    """
    Aplica reajustes retroativos ao boletim de medição

    Parâmetros:
        adjustment (str): Nome do reajuste
        contract (str): Nome do contrato

    Retorna:
        bool: True se reajustes foram aplicados, False caso contrário
    """
    try:

        # Verifica se existem reajustes para o contrato que não estejam vinculados a um boletim de medição
        # que a data de reajuste esteja entre o período da medição e o status da medição seja Aberto
        adjustments = frappe.db.sql(
            """
                SELECT
                    ca.datareajuste,
                    ca.name,
                    cad.item,
                    cad.saldopagamento,
                    cm.name AS boletimmedicao
                FROM
                    `tabContract Adjustment` ca
                    INNER JOIN `tabContract Adjustment Data` cad ON cad.parent = ca.name
                    LEFT JOIN `tabContract Measurement` cm ON cm.contrato = ca.contrato AND
                                                            ca.datareajuste >= cm.datainicialmedicao AND
                                                            ca.datareajuste <= cm.datafinalmedicao AND
                                                            cm.workflow_state = 'Aberto'
                WHERE
                    ca.name = %s
                    AND ca.contrato = %s
                    AND NOT cm.name IS NULL
                    AND ca.boletimmedicao IS NULL
                    AND NOT cad.indicereajuste = 0
                ORDER BY
                    cm.name; """,
            (adjustment, contract,), 
            as_dict=True)

        last_measurement = None

        if adjustments and len(adjustments)>0:

            for r in adjustments:

                # Controle para aplicar o reajuste apenas a um boletim de medição
                if not last_measurement:
                    last_measurement = r['boletimmedicao']

                if not last_measurement == r['boletimmedicao']:
                    # Vincula o reajuste a apenas um boletim de medição
                    break
            
                # Aplica o reajuste ao boletim de medição
                frappe.db.sql("""
                    UPDATE 
                        `tabContract Measurement Item` 
                    SET 
                        valorretroativo = %s
                    WHERE
                        parent = %s 
                        AND itemcontrato = %s
                    """, (r['saldopagamento'], r['boletimmedicao'], r['item'],))

            return last_measurement
        
        else:
            return None
        
    except Exception as e:
        frappe.log_error(f"Error on check_adjustments: {str(e)}", "Measurement API")
        return None

def clear_measurement_adjustment(measurement: str) -> bool:
    """
    Remove os valores de reajustes retroativos do boletim de medição

    Parâmetros:
        measurement (str): Nome do boletim de medição

    Retorna:
        bool: True se reajustes foram removidos, False caso contrário
    """

    try:

        # Remove os valores de reajustes retroativos do boletim de medição
        frappe.db.sql("""
            UPDATE 
                `tabContract Measurement Item` 
            SET 
                valorretroativo = 0
            WHERE
                parent = %s 
            """, (measurement,))
        frappe.db.commit()
        
        return True
    
    except Exception as e:
        frappe.log_error(f"Error on remove_adjustments: {str(e)}", "Measurement API")
        return False

@frappe.whitelist(methods=["POST"])
def update_measurement_balance(
        measurement: str, 
        contract: str, 
        previous_cumulative_measurement: float, 
        previous_accumulated_deposit: float, 
        previous_accumulated_direct_billing: float, 
        current_measurement: float, 
        direct_billing_ftd: float, 
        current_metering_with_ftd_discount: float, 
        reidi_discount: float, 
        net_reidi_measurement: float, 
        reidi_net_equivalent_metering_f: float, 
        contractual_security: float,
        current_total_value: float,
        cumulative_direct_billing: float,
        current_total_value_with_ftd_discount: float,
        current_accumulated_measurement: float,
        contract_balance: float,
        contractual_balance_percent: float,
        current_deposit: float,
        accumulated_deposit: float
    ):
    """
    Atualiza os saldos do contrato na medição

    Parâmetros:
        measurement (str): Nome do boletim de medição
        contract (str): Nome do contrato
        previous_cumulative_measurement (float): Medição acumulada anterior
        previous_accumulated_deposit (float): Depósito acumulado anterior
        previous_accumulated_direct_billing (float): Faturamento direto acumulado anterior
        current_measurement (float): Medição atual
        direct_billing_ftd (float): Faturamento direto FTD
        current_metering_with_ftd_discount (float): Medição atual com desconto FTD
        reidi_discount (float): Desconto REIDI
        net_reidi_measurement (float): Medição líquida REIDI
        reidi_net_equivalent_metering_f (float): Medição equivalente líquida REIDI F
        contractual_security (float): Garantia contratual
        current_total_value (float): Valor total atual
        cumulative_direct_billing (float): Faturamento direto acumulado
        current_total_value_with_ftd_discount (float): Valor total atual com desconto FTD
        current_accumulated_measurement (float): Medição acumulada atual
        contract_balance (float): Saldo do contrato
        contractual_balance_percent (float): Percentual de saldo contratual
        current_deposit (float): Depósito atual
        accumulated_deposit (float): Depósito acumulado
    """

    # Verifica se a medição existe
    check_measurement = frappe.db.exists("Contract Measurement", measurement)

    # Se medição já existe
    if check_measurement:
        
        # Verifica se há outra medição ja com carga de saldos
        records = frappe.db.sql("""
            SELECT 
                name 
            FROM 
                `tabContract Measurement` 
            WHERE 
                contrato IN (SELECT contrato FROM `tabContract Measurement` WHERE name = %s) AND 
                importacaosaldos IS NOT NULL
            LIMIT 1
            """, (contract, measurement), as_dict=True)

        if records and len(records)>0:
            # Verfica se a medição com carga de saldos é a mesma que está sendo processada
            if not records[0]['name'] == measurement:
                return {
                    "Processed": False,
                    "message": f"Já existe uma medição com carga de saldos para o contrato {contract}. Verifique a medição {records[0]['name']}."
                }

        # Atualiza os saldos do contrato na medição
        measurement_doc = frappe.get_doc("Contract Measurement", measurement)
            
    else:

        # Get contract name
        contract_name = frappe.db.get_value("Contract Measurement", measurement, "contrato")

        # Cria nova medição
        measurement_doc = frappe.new_doc("Contract Measurement")
        measurement_doc.name = measurement
        measurement_doc.contrato = contract
        measurement_doc.workflow_state = "Concluído"
        measurement_doc.datainicialmedicao = datetime.now().date()
        measurement_doc.datafinalmedicao = datetime.now().date()

    measurement_doc.importacaosaldos = datetime.now()
    measurement_doc.medicaoacumuladaanterior = previous_cumulative_measurement
    measurement_doc.caucaoacumuladoanterior = previous_accumulated_deposit
    measurement_doc.ftdacumuladoanterior = previous_accumulated_direct_billing
    measurement_doc.medicaoatual = current_measurement
    measurement_doc.faturamentodireto = direct_billing_ftd
    measurement_doc.medicaoatualdescontoftd = current_metering_with_ftd_discount
    measurement_doc.descontoreidi = reidi_discount
    measurement_doc.medicaoliquida = net_reidi_measurement
    measurement_doc.medicaoequivalente = reidi_net_equivalent_metering_f
    measurement_doc.caucaocontratual = contractual_security
    measurement_doc.valortotalvigente = current_total_value
    measurement_doc.ftdacumulado = cumulative_direct_billing
    measurement_doc.medicaoacumulada = current_accumulated_measurement
    measurement_doc.saldo = contract_balance
    measurement_doc.saldopercentual = contractual_balance_percent
    measurement_doc.caucaoatual = current_deposit
    measurement_doc.caucaoacumulado = accumulated_deposit
    measurement_doc.save(ignore_permissions=True)