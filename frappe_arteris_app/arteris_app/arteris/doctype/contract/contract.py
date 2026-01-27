# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from arteris_app.api.contractitem import create_item_main
from arteris_app.api.support import contract_data_support, check_pending_process


class Contract(Document):
	def after_insert(self):
		# This method is called after the document is inserted into the database
		# You can add any custom logic here that needs to run after the contract is created

		# Create the main item for the contract
		create_item_main(self.name)

@frappe.whitelist()
def force_data_load(contract: str):

	if check_pending_process():
		return {"success": False, "error": "Já existe um processo de recarregamento ou recálculo em andamento. Aguarde a conclusão deste processo antes de iniciar outro."}

	cs = contract_data_support(contract)
	cs.load_contract_data()
	return {"success": True}	

