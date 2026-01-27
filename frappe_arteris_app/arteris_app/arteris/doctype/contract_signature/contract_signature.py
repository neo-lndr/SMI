# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
import json 
from frappe.model.document import Document
from frappe.utils import flt


class ContractSignature(Document):
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
			LEFT JOIN `tabContract Signature` s ON c.name = s.contrato
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
def get_persons(doctype, txt, searchfield, start, page_len, filters):
    
	filters = json.loads(filters) if filters else {}

	persons = frappe.db.sql("""
		SELECT DISTINCT
			name AS value,
			nome AS label
		FROM 
			`tabPerson`
		WHERE
			NOT fluxomedicao IS NULL
			AND fluxomedicao = 1 
			AND (nome LIKE %(txt)s)
		ORDER BY 
			idx, nome
		LIMIT %(start)s, %(page_len)s""", {
		'start': int(start),
		'txt': '%%%s%%' % txt,
		'page_len': int(page_len)
	})

	return persons

@frappe.whitelist()
def get_contract_detail(contrato):
    """
    Busca detalhes do contrato
    """
    if not contrato:
        return {}
    

    co_name = frappe.db.get_value("Contract", contrato, ["contratada","contrato"], as_dict=True)
    co = frappe.db.get_value("Contracted Company", co_name.get('contratada'), ["Nome"], as_dict=True)

    # CORREÇÃO: Retorna o valor correto
    return {'contratada': co.get('Nome') if co else '', 'contrato': co_name.get('contrato') if co_name else ''}
