frappe.ui.form.on('Contract Measurement Note', {
    refresh(frm) {
        calcular_totais(frm);
        // Configurar query para campo item na tabela tabitem
        frm.fields_dict["tabitem"].grid.get_field("item").get_query = function(doc) {
            return {
                filters: {
                    'contrato': frm.doc.contrato,
                },
                no_create: 1,
                only_select: 1
            }
        }
    },
    
    setup: function(frm) {
        // Configurar query para campo pedidolinha na tabela tabsap
        frm.set_query("pedidolinha", "tabsap", function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_sap_order_line",
                filters: {
                    'contrato': frm.doc.contrato || ''
                },
                no_create: 1,
                only_select: 1
            }
        });
        
        // Configurar query para campo funcao na tabela tabfuncoes
        frm.set_query("funcao", "tabfuncoes", function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_work_role",
                filters: {
                    'contrato': frm.doc.contrato || ''
                },
                no_create: 1,
                only_select: 1
            }
        });

        // Query para campo item na tabela tabfuncoes
        frm.set_query("item", "tabfuncoes", function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_work_role_item",
                filters: {
                    'contrato': frm.doc.contrato || '',
                    'funcao': row.funcao || ''
                },
                no_create: 1,
                only_select: 1
            }
        });     

        // Configurar query para campo funcao na tabela tabativos
        frm.set_query("ativo", "tabativos", function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_asset",
                filters: {
                    'contrato': frm.doc.contrato || ''
                },
                no_create: 1,
                only_select: 1
            }
        });     
        
        // Configurar query para campo funcao na tabela tabativos
        frm.set_query("item", "tabativos", function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                query: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_asset_item",
                filters: {
                    'contrato': frm.doc.contrato || '',
                    'ativo': row.ativo
                },
                no_create: 1,
                only_select: 1
            }
        });  
                
    },

    contrato: function(frm) {
        if (frm.doc.contrato) {
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_contract_data",
                args: {
                    contrato: frm.doc.contrato
                },
                callback: function(r) {
                    if (r.message) {
                        // Usar frm.set_value em vez de frm.doc direto
                        frm.set_value('subsidiaria', r.message['subsidiaria']);
                        frm.set_value('contratada', r.message['contratada']);
                        
                        // Forçar refresh dos campos após definir os valores
                        setTimeout(() => {
                            frm.refresh_field('subsidiaria');
                            frm.refresh_field('contratada');
                        }, 100);
                    }
                },
                error: function() {
                    frappe.msgprint('Erro ao buscar contrato');
                }
            });
        } else {
            // Limpar campos
            frm.set_value('subsidiaria', '');
            frm.set_value('contratada', '');
        }
    }
});

// Eventos para a child table Contract Measurement Note SAP Order
frappe.ui.form.on('Contract Measurement Note SAP Order', {
    pedidolinha: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.pedidolinha) {
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_sap_order_line_cc",
                args: {
                    pedido_linha: row.pedidolinha
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'codigocc', r.message['codigocc']);
                    }
                },
                error: function() {
                    frappe.msgprint('Erro ao buscar centro de custo');
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'codigocc', '');
        }

        calcular_totais(frm);
    },
    valormedido: function(frm, cdt, cdn) {
        calcular_totais(frm);
    }
});

// Eventos para a child table Contract Measurement Note Work Role
frappe.ui.form.on('Contract Measurement Note Work Role', {
    // Evento quando o campo funcao muda
    item: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];       
        if (row.item && row.funcao) {
            // Chamar método do backend para obter dados da função e item
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_work_role_data",
                args: {
                    funcao: row.funcao,
                    item: row.item,
                    contrato: frm.doc.contrato
                },
                callback: function(r) {
                    if (r.message) {
                        // Setar os valores nos campos
                        frappe.model.set_value(cdt, cdn, 'valorporhora', r.message['valorporhora']);
                        frappe.model.set_value(cdt, cdn, 'valormensal', r.message['valormensal']);
                    }
                },
                error: function() {
                    frappe.msgprint('Erro ao buscar dados da função');
                }
            });
        } else if (!row.item) {
            // Limpar campos de valor quando item for removido
            frappe.model.set_value(cdt, cdn, 'valorporhora', '');
            frappe.model.set_value(cdt, cdn, 'valormensal', '');
        }
    },
    quantidade: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        calcular_totais(frm);
    }
});

// Eventos para a child table Contract Measurement Note Asset
frappe.ui.form.on('Contract Measurement Note Asset', {
    item: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.ativo && row.item) {
            frappe.call({
                method: "arteris_app.arteris.doctype.contract_measurement_note.contract_measurement_note.get_asset_data",
                args: {
                    ativo: row.ativo, 
                    item: row.item,
                    contrato: frm.doc.contrato
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'valorunitario', r.message['valorunitario']);
                        frappe.model.set_value(cdt, cdn, 'valormensal', r.message['valormensal']);
                    }
                },
                error: function() {
                    frappe.msgprint('Erro ao buscar dados do ativo');
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'valorunitario', '');
            frappe.model.set_value(cdt, cdn, 'valormensal', '');
        }
    },
    quantidade: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        calcular_totais(frm);
    }  
});

frappe.ui.form.on("Contract Measurement Note Resource", {

    // Calcular quando a quantidade for alterada
    quantidademedida: function(frm, cdt, cdn) {

        // Obter a linha atual
        let row = locals[cdt][cdn];

        // Verificar se os valores existem e são números válidos
        let _quantidade = flt(row.quantidademedida) || 0;
        let _valorunitario = flt(row.valorunitario) || 0;
        let _valortotal = _quantidade * _valorunitario;

        console.log(`Calculando valor medido: ${_quantidade} * ${_valorunitario} = ${_valortotal}`);

        // Definir o valor calculado no campo
        frappe.model.set_value(cdt, cdn, 'valormedido', _valortotal);

        calcular_totais(frm);

    }
    
});

function calcular_totais(frm) {

    console.log('Calculando totais...');

    let total_tabitem = 0;
    let total_tabfuncoes = 0;
    let total_tabativos = 0;
    let total_tabsap = 0;
    
    // Calcular total da tabela tabfuncoes
    if (frm.doc.tabfuncoes) {
        frm.doc.tabfuncoes.forEach(function(row) {
            total_tabfuncoes += flt(row.valortotal) || 0;
        });
    }
    
    // Calcular total da tabela tabativos
    if (frm.doc.tabativos) {
        frm.doc.tabativos.forEach(function(row) {
            total_tabativos += flt(row.valortotal) || 0;
        });
    }
    
    // Calcular total da tabela tabsap
    if (frm.doc.tabsap) {
        frm.doc.tabsap.forEach(function(row) {
            total_tabsap += flt(row.valormedido) || 0;
        });
    }
    
    // Calcular total da tabela resources
    if (frm.doc.tabitem) {
        frm.doc.tabitem.forEach(function(row) {
            total_tabitem += flt(row.valormedido) || 0;
        });
    }
    
    // Calcular total geral
    let total_geral = total_tabitem + total_tabfuncoes + total_tabativos;
    
    frm.set_value('totalfuncoes', total_tabfuncoes);
    frm.set_value('totalativos', total_tabativos);
    frm.set_value('totalsap', total_tabsap);
    frm.set_value('totalrecursos', total_tabitem);
    frm.set_value('totalmedido', total_geral);
    
    // Log para debug
    console.log('Totais calculados:', {
        tabitem: total_tabitem,
        tabfuncoes: total_tabfuncoes,
        tabativos: total_tabativos,
        tabsap: total_tabsap,
        total_geral: total_geral
    });
}