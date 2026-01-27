# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ContractItemWorkloadCfg(Document):
	
	def after_insert(self):

		doc = frappe.get_doc("Contract Item Workload Cfg", self.name)
		doc_itens = doc.append("tabitens")

		items = frappe.db.sql("""
			SELECT
				name
			FROM
				`tabContract Item`
			WHERE
				contrato = %s
			ORDER BY 
						
		""", (self.contrato,), as_dict=True)


		if self.is_default:
			self.set_as_default()
