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
	columns = get_columns()
	data = get_data()

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
			"label": "Nº da medição",#
			"fieldtype": "Data",
		},
		{
			"label": "Nº do contrato",#
			"fieldtype": "Data",
		},
		{
			"label": "Subsidiária",#
			"fieldtype": "Data",
		},
		{
			"label": "Data inicial da medição",#
			"fieldtype": "Date",
		},
		{
			"label": "Data final da medição",#
			"fieldtype": "Date",
		},
		{
			"label": "Data inicial da aprovação",#
			"fieldtype": "Date",
		},
		{
			"label": "Data final da aprovação",#
			"fieldtype": "Date",
		},
		{
			"label": "Medição acumulada anterior",#
			"fieldtype": "Currency",
		},
		{
			"label": "Caução acumulado anterior",#
			"fieldtype": "Currency",
		},
		{
			"label": "Faturamento direto (FTD) acumulado anterior",#
			"fieldtype": "Currency",
		},
		{
			"label": "Medição atual (A)",#
			"fieldtype": "Currency",
		},
		{
			"label": "Faturamento direto (FTD) na fase atual",#
			"fieldtype": "Currency",
		},
		{
			"label": "Medição atual com desconto de FTD (B)",#
			"fieldtype": "Currency",
		},
		{
			"label": "Desconto do REIDI [C] = -3,65% . [B]",#
			"fieldtype": "Currency",
		},
		{
			"label": "Medição líquida do REIDI (Vl. bruto NF) [D] = [B]+[C]",#
			"fieldtype": "Currency",
		},
		{
			"label": "Medição equivalente líquida do REIDI [F] = [A]+(E)",#
			"fieldtype": "Currency",
		},
		{
			"label": "Caução Contratual [G] =  5% . [F]",#
			"fieldtype": "Currency",
		},
		{
			"label": "Valor Total Vigente",#
			"fieldtype": "Currency",
		},
		{
			"label": "Faturamento direto (FTD) acumulado",#
			"fieldtype": "Currency",
		},
		{
			"label": "Valor total vigente com desconto de FTD",#
			"fieldtype": "Currency",
		},
		{
			"label": "Medição acumulada atual",#
			"fieldtype": "Currency",
		},
		{
			"label": "Saldo Contratual (R$)",#
			"fieldtype": "Currency",
		},
		{
			"label": "Saldo Contratual (%)",#
			"fieldtype": "Percent",
		},
		{
			"label": "Caução atual",#
			"fieldtype": "Currency",
		},
		{
			"label": "Caução acumulado",#
			"fieldtype": "Currency",
		},
		{
			"label": "Apontamento do desconto",#
			"fieldtype": "Currency",
		},
		{
			"label": "Porcentagem de desconto do payfactor",#
			"fieldtype": "Percent",
		},
		{
			"label": "Total de registros",#
			"fieldtype": "Int",
		},
	]


def get_data() -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""

	records = frappe.db.sql("""
		WITH mr AS (
			SELECT
				boletimmedicao,
				COUNT(1) AS registros
			FROM
				`tabContract Measurement Record`
			WHERE
				medicaovigente = 'Sim'
			GROUP BY boletimmedicao
		)
		SELECT
			CONCAT('<a href="/app/contract-measurement/',cm.name,'" target="_blank">🔗</a>') AS link,
			cm.name,
			c.contrato,
			s.nome AS subsidiaria,
			cm.datainicialmedicao,
			cm.datafinalmedicao,
			cm.datainicialtrabalho,
			cm.datafinaltrabalho,
			cm.medicaoacumuladaanterior,
			cm.caucaoacumuladoanterior,
			cm.ftdacumuladoanterior,
			cm.medicaoatual,
			cm.faturamentodireto,
			cm.medicaoatualdescontoftd,
			cm.descontoreidi,
			cm.medicaoliquida,
			cm.medicaoequivalente,
			cm.caucaocontratual,
			cm.valortotalvigente,
			cm.ftdacumulado,
			cm.totalvigentemenosftd,
			cm.medicaoacumulada,
			cm.saldo,
			cm.saldopercentual,
			cm.caucaoatual,
			cm.caucaoacumulado,
			cm.apontamento_desconto,
			cm.percent_payfatror_descont,
			mr.registros
		FROM
			`tabContract Measurement` cm
			INNER JOIN `tabContract` c ON cm.contrato = c.name
			LEFT JOIN mr ON mr.boletimmedicao = cm.name
			LEFT JOIN `tabSubsidiary` s ON s.name=c.subsidiaria
		WHERE
			cm.medicaovigente = 'Sim'
	""",
	as_list=True)

	data = records

	return data
