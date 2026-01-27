// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.query_reports["Items"] = {
	filters: [
		{
			"fieldname": "contrato",
			"label": "Contrato",
			"fieldtype": "Link",
			"options": "Contract",
			"reqd": 0
		}
	],
};
