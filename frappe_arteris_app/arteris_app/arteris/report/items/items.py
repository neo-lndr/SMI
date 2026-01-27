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

	contract = filters.contrato

	columns = get_columns()
	data = get_data(contract)

	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Chave do item"),
			"fieldtype": "Data",
		},
		{
			"label": _("Contrato"),
			"fieldtype": "Data",
		},
		{
			"label": _("Subsidiária"),
			"fieldtype": "Data",
		},
		{
			"label": _("É grupo"),
			"fieldtype": "Check",
		},
		{
			"label": _("Aplicar performance"),
			"fieldtype": "Check",
		},
		{
			"label": _("Produtividade compensatória "),
			"fieldtype": "Check",
		},
		{
			"label": _("Temp. Código"),
			"fieldtype": "Data",
		},
		{
			"label": _("Temp. Descrição"),
			"fieldtype": "Data",
		},
		{
			"label": _("Código"),
			"fieldtype": "Data",
		},
		{
			"label": _("Descrição"),
			"fieldtype": "Data",
		},
		{
			"label": _("Quantidade"),
			"fieldtype": "Float",
		},
		{
			"label": _("Unidade"),
			"fieldtype": "Data",
		},
		{
			"label": _("Valor unitário"),
			"fieldtype": "Currency",
		},
		{
			"label": _("Valor total"),
			"fieldtype": "Currency",
		},
		{
			"label": _("Saldo atual"),
			"fieldtype": "Currency",
		},
		{
			"label": _("Tipo"),
			"fieldtype": "Data",
		},
		{
			"label": _("% Fator pagamento"),
			"fieldtype": "Percent",
		},
		{
			"label": _("Código PEP"),
			"fieldtype": "Data",
		},
		{
			"label": _("Cidade base"),
			"fieldtype": "Data",
		},
		{
			"label": _("Percentual padrão para hora extra"),
			"fieldtype": "Percent",
		},
		{
			"label": _("Horas domingo"),
			"fieldtype": "Int",
		},
		{
			"label": _("Horas segunda"),
			"fieldtype": "Int",
		},
		{
			"label": _("Horas terça"),
			"fieldtype": "Int",
		},
		{
			"label": _("Horas quarta"),
			"fieldtype": "Int",
		},
		{
			"label": _("Horas quinta"),
			"fieldtype": "Int",
		},
		{
			"label": _("Horas sexta"),
			"fieldtype": "Int",
		},
		{
			"label": _("Horas sabado"),
			"fieldtype": "Int",
		}
	]

def get_data(contract = None) -> list[list]:
	"""Return data for the report.
	The report data is a list of rows, with each row being a list of cell values.
	"""

	data = []
	str_select_item = """SELECT
							item.name,
							contract.contrato,
							sub.nome as subsidiaria,
							item.is_group,
							item.aplicar_performance,
							item.produtividadecompensatoria,
							it.codigo as t_codigo,
							it.descricao as t_descricao,
							item.codigo,
							item.descricao,
							item.quantidade,
							item.unidade,
							item.valorunitario,
							item.valortotalvigente,
							item.saldo,
							item.tipodoitem,
							item.fatorpagamento,
							item.codigopep,
							item.cidade,
							item.percentualhe,
							item.dom_hora,
							item.seg_hora,
							item.ter_hora,
							item.qua_hora,
							item.qui_hora,
							item.sex_hora,
							item.sab_hora
						FROM 
							`tabContract Item` item
							LEFT JOIN `tabContract` contract ON item.contrato = contract.name
							LEFT JOIN `tabSubsidiary` sub ON sub.name=contract.subsidiaria
							LEFT JOIN `tabItem` it ON it.name = item.templateitem 
						"""
	str_where = "WHERE 1=1"

	if contract:
		str_where += f" AND contrato = '{contract}' "

	def get_childs(parent, contrato, is_root = False):

		if is_root:
			str_where = f"item.name = '{parent}' "
		else:
			str_where = f"item.parent_contract_item = '{parent}' "

		str_query = f"""
			{str_select_item.replace("contract.contrato,", f"'{contrato}' as contrato,")}
            WHERE 
				{str_where}
            ORDER BY 
				INET_ATON(SUBSTRING_INDEX(CONCAT(item.codigo,'.0.0.0.0.0.0.0.0'), '.', 8)) ASC;
			"""
		print(str_query)
		childs = frappe.db.sql(str_query, as_list = True)
		for c in childs:
			data.append(c)
			if (c[3] == 1):  # is_group
				get_childs(c[0], contrato) # name

	contracts = frappe.db.sql(f"""
		SELECT
			name,
			contrato
		FROM
			`tabContract`
			{str_where}
		ORDER BY
			contrato
		""", as_dict=True)

	for c in contracts:
		root_item = frappe.db.sql(f"""
			{str_select_item}
			WHERE 
				item.parent_contract_item IS NULL
				AND item.is_group = 1
				AND item.contrato = '{c['name']}'			
			LIMIT 1 
		""", as_dict = True)

		if root_item:
			for r in root_item:
				get_childs(r['name'], r['contrato'].replace("'", ""), is_root=True)

	return data
