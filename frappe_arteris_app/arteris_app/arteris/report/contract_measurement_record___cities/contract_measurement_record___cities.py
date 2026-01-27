# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	contract_measuremnent_name = filters.medicao

	columns = get_columns()
	data = get_data(contract_measuremnent_name)

	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": "...",#
			"fieldtype": "Html",
			"width": 50
		},
		{
			"label": "Origem integração",#
			"fieldtype": "Data",
		},
		{
			"label": "Rodovia",#
			"fieldtype": "Data",
		},
		{
			"label": "Km Inicial",#
			"fieldtype": "Float",
		},
		{
			"label": "Km Final",#
			"fieldtype": "Float",
		},
		{
			"label": "Cidade",#
			"fieldtype": "Data",
		},	
		{
			"label": "Data execução",#
			"fieldtype": "Datetime",
		},	
		{
			"label": "Data aprovação",#
			"fieldtype": "Datetime",
		},		
		{
			"label": "RDO",#
			"fieldtype": "Data",
		},	
		{
			"label": "Relatório",#
			"fieldtype": "Data",
		},	
		{
			"label": "Quantidade medida",#
			"fieldtype": "Float",
		},
		{
			"label": "Valor total",#
			"fieldtype": "Currency",
		},
		{
			"label": "Valor calculado",#
			"fieldtype": "Currency",
		},
		{
			"label": "Código Item",#
			"fieldtype": "Data",
		},	
		{
			"label": "Descrição Item",#
			"fieldtype": "Data",
		},		
	]

def get_data(contract_measuremnent_name) -> list[list]:

	data = []

    # Get cities with highways
	cities_records = frappe.db.sql("""
        WITH t_cities AS (
            SELECT
                cmr.name AS record_name,
                cmrl.rodovia_name AS rodovia, 
                cmrl.kminicial,
                cmrl.kmfinal,
                cmrl.cidade_name AS cidade,
                cmr.boletimmedicao,
				cmrl.codigorelatorio,
                'Osiris' AS tipo
            FROM
                `tabContract Measurement Record` cmr
                INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
            WHERE
                cmr.boletimmedicao = %s AND 
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
            cm_item.item,
            cm_item.valorcalculado          
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
            cm_item.item,
            cm_item.valorcalculado  
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
            cm_item.item,
            cm_item.valorcalculado   
        FROM
            t_cities
            INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
            INNER JOIN `tabContract Measurement Record Resource` cm_item ON cmr.name = cm_item.parent   
            LEFT JOIN `tabContract Measurement Item` m_item ON cm_item.item = m_item.itemcontrato AND 
                                                     m_item.parent = cmr.boletimmedicao
			LEFT JOIN `tabContract Item` item ON cm_item.item = item.name
        """, (contract_measuremnent_name, ), as_dict=True)
	if cities_records:
		for record in cities_records:
			data.append(
				[
					'<a href="/app/contract-measurement-record/{0}" target="_blank">🔗</a>'.format(record['name']),  # Link to the record

					record['origem_integracao'],
					record['rodovia'],
					record['kminicial'],
					record['kmfinal'],
					record['cidade'],
					record['dataexecucao'],
					record['dataaprovacao'],
					record['rdo'],
					record['codigorelatorio'],
					record['quantidademedida'],
					record['valortotal'],
					record['valorcalculado'],
					record['codigo'],
					record['descricao'],

				]
			)

	return data	
