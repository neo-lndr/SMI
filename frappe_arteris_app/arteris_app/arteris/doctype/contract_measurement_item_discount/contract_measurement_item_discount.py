# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document


class ContractMeasurementItemDiscount(Document):

	def validate(self):
		if not self.is_new():
			m_doc = frappe.get_value("Contract Measurement", self.boletimmedicao, "workflow_state")
			if m_doc != "Aberto":
				frappe.throw(f"Boletim de Medição {self.boletimmedicao} está com status '{m_doc}', não é possível realizar a operação.")



@frappe.whitelist()
def get_items(doctype, txt, searchfield, start, page_len, filters):
	"""
	Busca linhas da medicao
	"""
	if isinstance(filters, str):
		filters = json.loads(filters)

	medicao = filters.get('medicao', '')

	# Se não tiver pedido_sap, retorna vazio
	if not medicao:
		return []
    
	data = frappe.db.sql("""
		SELECT DISTINCT
			ci.name AS value,
			CONCAT(ci.codigo,' - ',ci.descricao) AS label
		FROM 
			`tabContract Measurement Item` cmi
			INNER JOIN `tabContract Item` ci ON cmi.itemcontrato = ci.name
		WHERE 
			cmi.parent = %(medicao)s
			AND (ci.descricao LIKE %(txt)s)
		ORDER BY 
			INET_ATON(SUBSTRING_INDEX(CONCAT(ci.codigo,'.0.0.0.0.0.0.0.0'), '.', 8)) ASC
		LIMIT %(start)s, %(page_len)s""", {
		'medicao': medicao,
		'txt': '%%%s%%' % txt,
		'start': int(start),
		'page_len': int(page_len)
	})

	# Filtrar apenas linhas que não estão associadas a nenhum Contract Item Order e sem saldo de medição
	return data

@frappe.whitelist()
def get_measurements(doctype, txt, searchfield, start, page_len, filters):
	"""
	Busca as medicoes do contrato
	"""
	if isinstance(filters, str):
		filters = json.loads(filters)

	data = frappe.db.sql("""
		SELECT
			name AS value,
			CONCAT(name) AS label
		FROM 
			`tabContract Measurement`
		WHERE 
			(name LIKE %(txt)s) AND 
			workflow_state = 'Aberto'
		ORDER BY 
			name
		LIMIT %(start)s, %(page_len)s""", {
		'txt': '%%%s%%' % txt,
		'start': int(start),
		'page_len': int(page_len)
	})

	return data