// frappe.ui.form.on('Contract Item Order', {
// 	refresh(frm) {
// 	    sap_order = frm.fields_dict["tablepedidossap"].grid.get_field("pedidosap")
//     	frm.fields_dict["tablepedidossap"].grid.get_field("pedidolinha").get_query = function(doc) {
//             return {
//                 filters: {
//                     'pedidosap': sap_order,
//                 }
//             }
//     	}
// 	}
// })

frappe.ui.form.on('Contract Item', {
    refresh: function(frm) {
        frappe.call({
            method: "arteris_app.arteris.doctype.contract_item.contract_item.get_childs",
            args: {
                name: frm.doc.name
            },
            callback: function(r) {
                if (!r.message) {
                    frm.set_df_property('is_group', 'hidden', false);
                }
            }
        });       
    },
    setup: function(frm) {
        // Configurar query para campo pedidolinha na tabela tabsap
        frm.set_query("pedidosap", "tablepedidossap", function(doc, cdt, cdn) {
        let row = locals[cdt][cdn];
        return {
            query: "arteris_app.arteris.doctype.contract_item.contract_item.get_sap_order",
            filters: {
                'contrato': frm.doc.contrato || ''
            },
            no_create: 1,
            only_select: 1
        }
        })
    },    
    contrato: function(frm) {
        //set_references(frm);
    },
    templateitem: function(frm) {
        if (frm.doc.itempadrao) {
            if ((frm.doc.codigo === undefined || frm.doc.codigo === '') &&
                (frm.doc.descricao === undefined || frm.doc.descricao === '')) {
                frappe.call({
                    method: "arteris_app.arteris.doctype.contract_item.contract_item.get_default_item_details",
                    args: {
                        item: frm.doc.templateitem
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.set_value('codigo', r.message.codigo);
                            frm.set_value('descricao', r.message.descricao);
                        }
                    }
                });
            }
        }
    }
});

// function set_references(frm) {
//     if (frm.doc.contrato) {
//         frappe.call({
//             method: "arteris_app.arteris.doctype.contract_item.contract_item.get_references",
//             args: {
//                 contract: frm.doc.contrato
//             },
//             callback: function(r) {
//                 if (r.message) {

//                     frm.set_df_property('referencia', 'options', r.message);
//                 }
//             }
//         });
//     } else {
//         frm.set_df_property('referencia', 'options', []);
//     }
// }
