# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ContractS(Document):
	pass

@frappe.whitelist()
def get_contracts(doctype, txt, searchfield, start, page_len, filters):
    
	filters = json.loads(filters) if filters else {}

	contracts = frappe.db.sql("""
		SELECT DISTINCT
			c.name AS value,
			c.contrato AS label
		FROM 
			`tabContract` c
			LEFT JOIN `tabContract S` s ON c.name = s.contrato
		WHERE
			s.name IS NULL AND 
			(c.contrato LIKE %(txt)s)
		ORDER BY 
			c.idx, c.contrato
		LIMIT %(start)s, %(page_len)s""", {
		'start': int(start),
		'txt': '%%%s%%' % txt,
		'page_len': int(page_len)
	})

	return contracts

@frappe.whitelist()
def get_contrat_periods(contract: str):
	periods = frappe.db.sql("""
		WITH RECURSIVE meses_contrato AS (
			-- Parte âncora
			SELECT
				datainicial AS data_mes,
				datafinal,
				valortotal,
				TIMESTAMPDIFF(MONTH, datainicial, datafinal) + 1 AS total_meses,
				1 AS numero_mes
			FROM
				`tabContract`
			WHERE
				name = %s
			UNION ALL
			-- Parte recursiva
			SELECT
				ADD_MONTHS(data_mes, 1) AS data_mes,
				datafinal,
				valortotal,
				total_meses,
				numero_mes + 1
			FROM
				meses_contrato
			WHERE
				ADD_MONTHS(data_mes, 1) <= datafinal
		)
		SELECT
			YEAR(data_mes) AS ano,
			MONTH(data_mes) AS mes,
			DATE_FORMAT(data_mes, '%%Y-%%m') AS periodo,
			numero_mes,
			total_meses,
			-- Valor mensal linear
			ROUND(valortotal / total_meses, 2) AS valor,
			-- Valor acumulado linear
			ROUND((valortotal / total_meses) * numero_mes, 2) AS acumuladovalor,
			-- Percentual acumulado
			ROUND(((valortotal / total_meses) * numero_mes) / valortotal * 100, 2) AS acumuladopercentual
		FROM
			meses_contrato
		ORDER BY data_mes;""", (contract,), as_dict=1)

	return periods

