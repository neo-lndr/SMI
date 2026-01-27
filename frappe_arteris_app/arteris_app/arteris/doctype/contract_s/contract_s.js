// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract S", {
	refresh(frm) {

	},
    setup: function(frm) {
        frm.set_query("contrato", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_s.contract_s.get_contracts",
                filters: {},
                no_create: 1,
                only_select: 1
            };
        });
    },
    onload(frm) {
        frm.get_field('tabperiodos').grid.cannot_add_rows = true;  
    },
    contrato: function(frm) {
        // Verifica se frm.doc.tabperiodos existe e está vazio
        if (frm.doc.tabperiodos && frm.doc.tabperiodos.length === 0) {
            load_periods(frm);
        }
    },
});

frappe.ui.form.on("Contract S Period", {

    valor: function(frm, cdt, cdn) {
        // Obter a linha atual
        let local_row = locals[cdt][cdn];
        calculate_row(frm, local_row);
        frm.refresh_field("tabperiodos");
    },   

});

function load_periods(frm) {
    frappe.call({
        method: "arteris_app.arteris.doctype.contract_s.contract_s.get_contrat_periods",
        args: {
            contract: frm.doc.contrato
        },
        callback: function(r) {
            if (r.message) {
                r.message.forEach(function(period) {
                    let row = frm.add_child("tabperiodos");
                    row.ano = period.ano;
                    row.mes = period.mes;
                    row.valor = period.valor;
                    row.acumuladovalor = period.acumuladovalor;
                    row.acumuladopercentual = period.acumuladopercentual;
                });
                setTimeout(function() {
                    frm.refresh_field("tabperiodos");
                }, 200);
                frm.refresh_field("tabperiodos");
            }
        }
    });
}

function calculate_row(frm, row){
    let sumarize = 0.0;
    frm.doc.tabperiodos.forEach(function(r) {
        if (r.idx < row.idx) {
            sumarize += r.valor;
        }
    });
    row.acumuladovalor = sumarize + row.valor;
    if (frm.doc.valortotal && frm.doc.valortotal > 0) {
        let precise_value = (row.acumuladovalor / frm.doc.valortotal) * 100;
        row.acumuladopercentual = precise_value;
    } else {
        row.acumuladopercentual = 0.0;
    }

}