# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
import time
from frappe.model.document import Document


class IntegrationInconsistency(Document):
	pass

@frappe.whitelist()
def clear_inconsistencies():
	frappe.db.sql("DELETE FROM `tabIntegration Inconsistency` WHERE creation < DATE_ADD(NOW(), INTERVAL -7 DAY);")
	frappe.db.commit()
	time.sleep(3)
