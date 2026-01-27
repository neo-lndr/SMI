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
	data_inicial = filters.datainicial
	data_final = filters.datafinal

	columns = get_columns()
	data = get_data(contract_measuremnent_name, data_inicial, data_final)

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
			"label": _("Revisado"),
			"fieldtype": "Check",
		},
		{
			"label": _("Tipo"),
			"fieldtype": "Data",
		},
		{
			"label": _("Data e hora"),
			"fieldtype": "Datetime",
		},
		{
			"label": _("Boletim de medição"),
			"fieldtype": "Data",
		},
		{
			"label": _("Informações"),
			"fieldtype": "Long Text",
		},
	]


def get_data(contract_measurement_name = None, data_inicial = None, data_final = None) -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""

	sql = """
		SELECT
			CONCAT('<a href="/app/integration-inconsistency/',name,'" target="_blank">🔗</a>') AS link,
			revisado,
			tipo,
			dataehora,
			boletimmedicao,
			observacoes
		FROM
			`tabIntegration Inconsistency`
		"""

	sql_where = "WHERE 1=1"

	if contract_measurement_name:
		sql_where += f" AND boletimmedicao = '{contract_measurement_name}'"

	if data_inicial:
		sql_where += f" AND dataehora >= '{data_inicial}'"

	if data_final:
		sql_where += f" AND dataehora <= '{data_final}'"

	data = frappe.db.sql(f"{sql} {sql_where}", as_list=True)

	return data
