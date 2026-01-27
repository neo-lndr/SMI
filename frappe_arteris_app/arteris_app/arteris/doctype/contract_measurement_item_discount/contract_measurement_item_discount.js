// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Measurement Item Discount", {
	refresh(frm) {

	},
    setup: function(frm) {
        frm.set_query("item", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_item_discount.contract_measurement_item_discount.get_items",
                filters: {
                    'medicao': frm.doc.boletimmedicao || ''
                },
                no_create: 1,
                only_select: 1
            }
        });    
        frm.set_query("boletimmedicao", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_item_discount.contract_measurement_item_discount.get_measurements",
                filters: {},
                no_create: 1,
                only_select: 1
            }
        });          
    }
});
