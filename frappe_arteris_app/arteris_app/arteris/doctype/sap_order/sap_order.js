// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.ui.form.on("SAP Order", {
        refresh(frm) {
                frm.get_field("table_dscc").grid.cannot_add_rows = true;
                refresh_field("table_dscc");
        },
        
});
