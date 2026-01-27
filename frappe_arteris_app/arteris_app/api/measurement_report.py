import frappe
import frappe.utils
from frappe.utils.pdf import get_pdf
from typing import Dict, Any
import requests
from requests import adapters
import re

@frappe.whitelist(methods=['GET'])
def get_measurement_data(id: str) -> Dict[str, Any]:
    """
    Obtém os dados da medição para a página customizada do Frappe.
    Isto substitui a função get_data_remote utilizando as funções do banco de dados do Frappe.
    """
    data = {}

    # Verifica se o id é um UUID usando regex
    uuid_regex = re.compile(
        r'^[0-9a-fA-F]{8}-'
        r'[0-9a-fA-F]{4}-'
        r'[0-9a-fA-F]{4}-'
        r'[0-9a-fA-F]{4}-'
        r'[0-9a-fA-F]{12}$'
    )
    is_uuid = bool(uuid_regex.match(id))
    
    if is_uuid:
        uuid = id
    else:
        # Obtém o UUID do contrato
        contract = frappe.get_value('Contract Measurement', id, 'contrato')
        if not contract:
            frappe.throw(_("Contrato não encontrado"), frappe.DoesNotExistError)
        uuid = contract

    # Obtém o valor total do contrato
    contract = frappe.get_all('Contract', filters={'name': uuid}, fields=['valortotal','valortotalp0'])
    valor_total_contrato = contract[0].valortotalp0 if contract else contract[0].valortotal

    data['valor_total_contrato'] = valor_total_contrato

    # Obtém os itens do contrato
    contract_items_list = frappe.db.sql("""
            SELECT
                item.name,
                item.codigo,
                item.descricao, 
                item.unidade,
                item.quantidade,                                      
                item.valorunitario,
                item.valortotalvigente,
                CASE 
                    WHEN item.quantidadep0 IS NULL THEN item.quantidade
                    WHEN item.quantidadep0 = 0 THEN item.quantidade
                    ELSE item.quantidadep0 
                END AS quantidadep0,                                           
                CASE 
                    WHEN item.valorunitariop0 IS NULL THEN item.valorunitario
                    WHEN item.valorunitariop0 = 0 THEN item.valorunitario
                    ELSE item.valorunitariop0 
                END AS valorunitariop0,
                CASE 
                    WHEN item.valortotalvigentep0 IS NULL THEN item.valortotalvigente
                    WHEN item.valortotalvigentep0 = 0 THEN item.valortotalvigente
                    ELSE item.valortotalvigentep0 
                END AS valortotalvigentep0                                        
            FROM 
                `tabContract Item` item 
            WHERE item.contrato = %s AND NOT item.codigo LIKE 'Contrato %%' 
            ORDER BY INET_ATON(SUBSTRING_INDEX(CONCAT(item.codigo, '.0.0.0.0.0.0.0.0'), '.', 8)) ASC;
        """, (uuid,), as_dict=True)

    # Adiciona o cálculo do nível aos itens do contrato
    for item in contract_items_list:
        item['level'] = calculate_contract_item_level(item.get('codigo', ''))

    # Atribui a soma de todos os filhos se o valortotalvigente estiver ausente ou for zero
    for idx, item in enumerate(contract_items_list):
        codigo = item.get('codigo')
        valor = item.get('valortotalvigente', 0)
        if not valor or valor == 0:
            # Encontra todos os filhos cujo 'codigo' começa com este 'codigo' seguido de '.'
            children_sum = sum(
                child.get('valortotalvigente', 0)
                for child in contract_items_list
                if child.get('codigo', '').startswith(f"{codigo}.") and child.get('codigo') != codigo
            )
            contract_items_list[idx]['valortotalvigente'] = children_sum

    # Obtém as medições do contrato
    contract_measurements = frappe.get_all(
        'Contract Measurement',
        filters={'contrato': uuid},
        fields=['name'],
        order_by='datafinalmedicao'
    )

    # Obtém os reajustes do contrato
    contract_adjustments = frappe.get_all(
        'Contract Adjustment',
        filters={'contrato': uuid},
        fields=['titulo','datareajuste','indicereajuste','dataretroativa','valoranterior','valorreajustado'],
        order_by='datareajuste'
    )

    contract_measurement_list = []
    valor_total_periodo = 0.0
    valor_total_acumulado = 0.0
    
    # Cria um mapa de nomes dos itens para índices uma única vez antes do loop
    item_index_map = {item['name']: index for index, item in enumerate(contract_items_list)}

    for measurement_ref in contract_measurements:
        # Obtém o documento completo de medição
        contract_measurement = frappe.get_doc('Contract Measurement', measurement_ref['name'])
        
        # Converte para dicionário para facilitar a manipulação
        measurement_dict = contract_measurement.as_dict()
        
        valor_total_periodo += measurement_dict.get('valorpago', 0)
        valor_total_acumulado += measurement_dict.get('valortotalvigente', 0)
        if 'medicaoacumulada' in data:
            if data['medicaoacumulada'] < measurement_dict.get('medicaoacumulada', 0):
                data['medicaoacumulada'] = measurement_dict.get('medicaoacumulada', 0)
        else:
            data['medicaoacumulada'] = measurement_dict.get('medicaoacumulada', 0)

        data['valor_total_periodo'] = valor_total_periodo
        data['valor_total_acumulado'] = valor_total_acumulado

        # Inicializa a lista de itens de medição do contrato
        contract_measurement_contract_items_list = [{} for _ in range(len(contract_items_list))]
        show_pay_factor = False
        
        contract_items = frappe.db.sql("""
            SELECT
                item.codigo,
                m_item.itemcontrato, 
                m_item.quantidademedida, 
                m_item.quantidadetotalvigente,
                m_item.quantidadeacumulada,
                m_item.valorpago, 
                m_item.valortotalacumulado, 
                m_item.valortotalvigente, 
                m_item.valorfatorpagamento,
                m_item.valorretroativo
            FROM 
                `tabContract Measurement Item` m_item
                INNER JOIN `tabContract Item` item ON m_item.itemcontrato = item.name
            WHERE m_item.parent = %s AND NOT item.codigo LIKE 'Contrato %%' 
            ORDER BY INET_ATON(SUBSTRING_INDEX(CONCAT(item.codigo, '.0.0.0.0.0.0.0.0'), '.', 8)) ASC;
        """, (measurement_ref['name'],), as_dict=True)

        valor_retroativo_total = sum(item.get('valorretroativo', 0) for item in contract_items)

        # Processa os itens de medição (assumindo que tabitenscontatrato é uma tabela filha)
        for contract_item in contract_items:  # measurement_dict.get('tabitenscontatrato', []):
            ordered_list_index = item_index_map.get(contract_item.get('itemcontrato'))
            
            if ordered_list_index is not None:
                level = contract_items_list[ordered_list_index]['level']
                contract_item['level'] = level
                contract_item['codigo'] = contract_items_list[ordered_list_index]['codigo']

                # if contract_item.get('valorfatorpagamento') and contract_item.get('valorfatorpagamento') != 0:
                #     show_pay_factor = False
                
                contract_measurement_contract_items_list[ordered_list_index] = contract_item

        # Preenche os itens vazios com informações básicas
        for index, contract_item in enumerate(contract_measurement_contract_items_list):
            if contract_item == {}:
                contract_measurement_contract_items_list[index]['codigo'] = contract_items_list[index]['codigo']
                contract_measurement_contract_items_list[index]['level'] = contract_items_list[index]['level']

        # Calcula a soma dos pais para valores ausentes
        for idx, item in enumerate(contract_measurement_contract_items_list):
            codigo = item.get('codigo')
            
            # Soma valorpago
            valor_medido = item.get('valorpago', 0)
            if not valor_medido or valor_medido == 0:
                children_sum = sum(
                    child.get('valorpago', 0)
                    for child in contract_measurement_contract_items_list
                    if child.get('codigo', '').startswith(f"{codigo}.") and child.get('codigo') != codigo
                )
                contract_measurement_contract_items_list[idx]['valorpago'] = children_sum
                contract_measurement_contract_items_list[idx]['totalizador_medido'] = (children_sum > 0)  # Assumindo que o totalizador é o mesmo que valorpago

            # Soma valortotalacumulado
            valor_vigente = item.get('valortotalacumulado', 0)
            if not valor_vigente or valor_vigente == 0:
                children_sum_vigente = sum(
                    child.get('valortotalacumulado', 0)
                    for child in contract_measurement_contract_items_list
                    if child.get('codigo', '').startswith(f"{codigo}.") and child.get('codigo') != codigo
                )
                contract_measurement_contract_items_list[idx]['valortotalacumulado'] = children_sum_vigente
                contract_measurement_contract_items_list[idx]['totalizador_acumulado'] = (children_sum_vigente > 0)  # Assumindo que o totalizador é o mesmo que valortotalvigente

        # Atualiza o dicionário de medição
        measurement_dict['pay_factor_exist'] = show_pay_factor
        measurement_dict['tabitenscontatrato'] = contract_measurement_contract_items_list
        measurement_dict['valor_retroativo_total'] = valor_retroativo_total

        contract_measurement_list.append(measurement_dict)

    data['contract_measurement_list'] = contract_measurement_list
    data['contract_items_list'] = contract_items_list
    data['adjustment_list'] = contract_adjustments
    
    # Calcula o percentual
    if valor_total_contrato and valor_total_contrato > 0:
        data['medicao_atual_acumulada_percentual'] = (data.get('medicaoacumulada', 0) / valor_total_contrato) * 100
    else:
        data['medicao_atual_acumulada_percentual'] = 0

    return data

def calculate_contract_item_level(code: str) -> int:
    """Calcula o nível de um item do contrato com base na estrutura do seu código"""
    if not code:
        return 0
    return code.count('.') + 1
