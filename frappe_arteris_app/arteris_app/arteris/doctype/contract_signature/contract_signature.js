// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Signature", {
    setup: function(frm) {
        frm.set_query("contrato", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_contracts",
                filters: {},
                no_create: 1,
                only_select: 1
            };

        });
        frm.set_query("pessoa1", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_persons",
                filters: {},
                no_create: 1,
                only_select: 1
            };

        });        
        frm.set_query("pessoa2", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_persons",
                filters: {},
                no_create: 1,
                only_select: 1
            };

        });        
        frm.set_query("pessoa3", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_persons",
                filters: {},
                no_create: 1,
                only_select: 1
            };

        });        
        frm.set_query("pessoa4", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_persons",
                filters: {},
                no_create: 1,
                only_select: 1
            };

        });        
        frm.set_query("pessoa5", function() {
            return {
                query: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_persons",
                filters: {},
                no_create: 1,
                only_select: 1
            };

        });        
    },    
    contrato: function(frm) {
        console.log("Contrato changed:", frm.doc.contrato);
        
        // CORREÇÃO: Chama apenas quando há um valor selecionado
        if (frm.doc.contrato) {
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_signature.contract_signature.get_contract_detail",
                args: {
                    contrato: frm.doc.contrato
                },
                callback: function(r) {
                    console.log("Response:", r);
                    if (r.message && r.message.contratada) {
                        frm.set_value('contrato_str', r.message.contrato);
                        frm.set_value('contratada', r.message.contratada);
                    }
                }
            });
        } else {
            // Limpa o campo quando não há seleção
            frm.set_value('contratada', '');
        }
    }
});