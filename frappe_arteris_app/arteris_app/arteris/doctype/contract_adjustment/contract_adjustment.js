// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Adjustment", {
    
    onload(frm) {
        frm.get_field('tabsap').grid.cannot_add_rows = true;
        frm.get_field('tabmedicoes').grid.cannot_add_rows = true;  
    },

	refresh(frm) {
        // Configurar query para campo item na tabela tabitem
        frm.fields_dict["tabsap"].grid.get_field("item").get_query = function(doc) {
            return {
                filters: {
                    'contrato': frm.doc.contrato,
                },
                no_create: 1,
                only_select: 1
            }
        }
        if (!frm.doc.datareajuste) {
            frm.set_value("datareajuste", frappe.datetime.get_today());
        }
        if (!frm.doc.dataretroativa){
            frm.set_value("dataretroativa", frappe.datetime.get_today());
        }
        if (!frm.is_new()) {  
            frm.toggle_enable(['titulo','indicereajuste','datareajuste','dataretroativa','contrato'], false);
        }
	},

    setup: function(frm) {
        frm.add_fetch('itemcontrato', 'name', 'descricao');
        // Configurar query para campo pedidolinha na tabela tabsap
        frm.set_query("pedidolinha", "tabsap", function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                query: "arteris_app.arteris.doctype.contract_adjustment.contract_adjustment.get_sap_order_line",
                filters: {
                    'contrato': frm.doc.contrato || ''
                },
                no_create: 1,
                only_select: 1
            }
        });
    },

    contrato: function(frm) {
        if (frm.doc.docstatus === 0) {
            load_measurements(frm);
            load_contract_items(frm);
            calculate_items_values(frm);
        }
    },

    dataretroativa: function(frm) {
        if (frm.doc.docstatus === 0) {        
            load_measurements(frm);
            calculate_items_values(frm);
        }
    },

    indicereajuste: function(frm) {
        if (frm.doc.docstatus === 0) {
            if (frm.doc.tabsap) {
                frm.doc.tabsap.forEach(function(row) {
                    if (row.indicereajuste === 0 && frm.doc.indicereajuste) {
                        row.indicereajuste = frm.doc.indicereajuste;
                        row.valorunitarioreajustado = row.valorunitario;
                    }
                    if (frm.doc.indicereajuste === 0) {
                        row.indicereajuste = 0;
                        row.valorunitarioreajustado = 0;
                    }
                    calculate_item_row(row);
                });
                frm.refresh_field("tabsap"); 
            }
        }
    }

    

});

frappe.ui.form.on("Contract Adjustment Data", {

    indicereajuste: function(frm, cdt, cdn) {
        if (frm.doc.docstatus === 0) {
            // Obter a linha atual
            let local_row = locals[cdt][cdn];
            calculate_item_row(local_row);
            frm.refresh_field("tabsap");
        }
    },

    pedidolinha: function(frm, cdt, cdn) {

        if (frm.doc.docstatus === 0) {
            // Obter a linha atual
            let local_row = locals[cdt][cdn];   
            frm.doc.tabsap.forEach(function(row) {
                if (row.idx > local_row.idx) {
                    row.pedidolinha = local_row.pedidolinha;
                }
            });
            frm.refresh_field("tabsap");
        }
    }    

});

function load_contract_items(frm) {
    if (frm.doc.docstatus === 0) {
        frm.clear_table("tabsap");
        if (frm.doc.contrato && 
            frm.doc.indicereajuste && 
            frm.doc.indicereajuste != 0 && 
            frm.doc.datareajuste && 
            frm.doc.titulo) {
            // Buscar dados do contrato e preencher tabela
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_adjustment.contract_adjustment.get_contract_items",
                args: {
                    contract: frm.doc.contrato
                },
                callback: function(r) {
                    if (r.message) {
                        let has_items = false;
                        r.message.forEach(function(item) {
                            let row = frm.add_child("tabsap");
                            has_items = true;
                            row.item = item.name;
                            row.valorunitario = item.valorunitario;
                            row.indicereajuste = frm.doc.indicereajuste;
                        });
                        if (has_items)
                        {
                            calculate_items_values(frm).then(() => {;

                                frm.doc.tabsap.forEach(function(row) {
                                    calculate_item_row(row);
                                })
                                frm.refresh_field("tabsap");
                                frm.save().then(() => {
                                    frm.reload_doc();
                                });
                            });
                        }
                    }
                }
            });       
        };
    }
};

function load_measurements(frm) {
    if (frm.doc.docstatus === 0) {
        frm.clear_table("tabmedicoes");
        if (frm.doc.dataretroativa && frm.doc.contrato) {
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_adjustment.contract_adjustment.get_contract_measurements",
                args: {
                    contract: frm.doc.contrato,
                    retroactivedate: frm.doc.dataretroativa
                },
                callback: function(r) {
                    if (r.message) {
                        r.message.forEach(function(measurement) {
                            let row = frm.add_child("tabmedicoes");
                            row.boletimmedicao = measurement.name;
                            row.status = measurement.status;
                            row.datainicial = measurement.datainicialmedicao;
                            row.datafinal = measurement.datafinalmedicao;
                        });
                        frm.refresh_field("tabmedicoes");
                    }
                }
            });
        }   
    }   
};

function calculate_items_values(frm) {
    return new Promise((resolve, reject) => {
        if (frm.doc.docstatus === 0) {
            if (frm.doc.dataretroativa && frm.doc.contrato) {
                frappe.call({
                    method: "arteris_app.arteris.doctype.contract_adjustment.contract_adjustment.get_items_retroactive_values",
                    args: {
                        retroactivedate: frm.doc.dataretroativa,
                        contract: frm.doc.contrato
                    },
                    callback: function(r) {
                        if (r.message) {
                            r.message.forEach(function(item) {
                                if (frm.doc.tabsap) {
                                    frm.doc.tabsap.forEach(function(row) {
                                        if (row.item === item.item) {
                                            row.quantidadetotal = item.quantidadetotal;
                                            row.valortotal = item.valortotal;
                                            calculate_item_row(row);
                                        }
                                    });
                                }
                            });
                        }                        
                        setTimeout(function() {
                            frm.refresh_field("tabsap");
                            resolve();
                        }, 200);
                    },
                    error: function(err) {
                        reject(err); 
                    }
                });
            } else {
                resolve(); 
            }
        } else {
            resolve(); 
        }
    });
}

function calculate_item_row(row) {
    row.valorunitarioreajustado = 0;
    row.saldopagamento = 0;
    row.valorreajuste = row.valorunitario;
    if (row.indicereajuste && row.valorunitario) {
        row.valorreajuste =  Math.round(row.valorunitario * (1 + (row.indicereajuste / 100)), 2);
    }
    if (row.valortotal) {
        row.valorreajustado = Math.round(row.valortotal * (1 + (row.indicereajuste / 100)), 2);
        row.saldopagamento = Math.round(row.valorreajustado - row.valortotal, 2);
    }
};