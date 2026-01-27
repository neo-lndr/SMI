// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.query_reports["Integration Inconsistency"] = {
	filters: [
		{
			"fieldname": "datainicial",
			"label": __("Data inicial"),
			"fieldtype": "Date",
			"reqd": 0,
		},
		{
			"fieldname": "datafinal",
			"label": __("Data final"),
			"fieldtype": "Date",
			"reqd": 0,
		},		
		{
			"fieldname": "medicao",
			"label": "Boletim de medição",
			"fieldtype": "Link",
			"options": "Contract Measurement",
			"reqd": 0
		}		
	],
};
