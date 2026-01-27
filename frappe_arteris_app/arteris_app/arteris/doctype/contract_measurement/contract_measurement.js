frappe.ui.form.on('Contract Measurement', {
    refresh: function(frm) {

        let totais_msg = '';

        totais_msg = calcular_totais(frm);

        let contrato_msg = '';

        frm.call('check_contract').then(function(response) {
                if (response.message) {
                    contrato_msg = `<p class="alert alert-danger">${response.message}:</p>`;
                }
            }
        )
        frm.call('check_measurement').then(function(response) {

            if (response.message) {
                let message = '';
                message += totais_msg;
                message += contrato_msg;
                if (response.message.items_sem_pedido.length > 0) {
                    message += '<p class="alert alert-danger">Existem itens sem pedidos SAP associados. Verifique a existência de pedidos, seus respecivos saldo e período das linhas, para os seguintes itens:</p>';
                    // message += '<br><br>';
                    for (let item of response.message.items_sem_pedido) {
                        message += `<div class="alert alert-warning">${item.codigo} - ${item.descricao}</div>`;
                    }
                }
                // if (response.message.pedidos_sem_saldo.length > 0) {
                //     message += '<p class="alert alert-danger">Pedidos sem saldo:</p>';
                //     // message += '<br><br>';
                //     for (let item of response.message.pedidos_sem_saldo) {
                //         message += `<div class="alert alert-warning">Linha: ${item.linha} Valor medido: ${item.valormedido} > Saldo anterior: ${item.saldoanterior}</div>`;
                //     }
                // }
                if (response.message.mao_de_obra_orfa.length > 0) {
                    message += '<p class="alert alert-danger">Existem registros de mão de obra que não constam na medição, verifique o cadastro dos itens contratuais, o sistema tentará carregar automaticamente as informações para os itens, porem cabe revisão, ao concluir a revisão clique em "Recarregar itens":</p>';
                    // message += '<br><br>';
                    for (let item of response.message.mao_de_obra_orfa) {
                        message += `<div class="alert alert-warning">Função: ${item.funcao}, Item código: ${item.codigo}</div>`;
                    }
                    }                
                if (response.message.ativo_orfao.length > 0) {
                    message += '<p class="alert alert-danger">Existem registros de ativos que não constam na medição, verifique o cadastro dos itens contratuais, o sistema tentará carregar automaticamente as informações para os itens, porem cabe revisão, ao concluir a revisão clique em "Recarregar itens":</p>';
                    // message += '<br><br>';
                    for (let item of response.message.ativo_orfao) {
                        message += `<div class="alert alert-warning">Ativo: ${item.ativo}, Item código: ${item.codigo}</div>`;
                    }
                }
                if (response.message.cidades.length > 0) {
                    message += '<p class="alert alert-danger">Verifique sobre as cidades:</p>';
                    // message += '<br><br>';
                    for (let item of response.message.cidades) {
                        message += `<div class="alert alert-warning">${item}</div>`;
                    }
                }
                if (message != '') {
                    //message += frm['warning'].options
                    frm.set_df_property('hatencao', 'hidden', false);
                    frm.set_df_property('warning', 'options', message);
                }
                else {
                    message = '<div class="alert alert-success">Nenhuma critica para o boletim de medição.</div>';
                    frm.set_df_property('hatencao', 'hidden', true);
                    frm.set_df_property('warning', 'options', message);
                }
            }
        });
        if (frm.doc.workflow_state === 'Enviado para assinatura' && frm.doc.idadobesign)    
        {
            frm.add_custom_button(
                '<i class="fa fa-refresh"></i> ' + __('Status AdobeSign'), 
                function() {
                    frappe.call({
                        method: "arteris_app.api.adobesign.get_adobesign_agreement_status",
                        args: {
                            agreement_id: frm.doc.idadobesign,
                            measurement: frm.doc.name
                        },
                        freeze: true,
                        freeze_message: `
                            <div class="custom-loading">
                                <div class="spinner-container">
                                    <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
                                </div>
                                <div class="loading-message">
                                    <strong>${__('Verificando status no AdobeSign...')}</strong>
                                </div>
                            </div>
                            <style>
                                .custom-loading {
                                    text-align: center;
                                    padding: 30px 20px;
                                }
                                .spinner-container {
                                    margin-bottom: 20px;
                                }
                                .loading-message {
                                    line-height: 1.5;
                                }
                                .fa-spin {
                                    animation: fa-spin 1s infinite linear;
                                }
                            </style>
                        `,
                        callback: function(response) {
                            if (response.message.success) {
                                if (response.message.data.status === "SIGNED") {        
                                    frappe.msgprint({
                                        title: __('Boletim de medição'),
                                        message: __('O processo de assinatura para o boletim de medição {0} foi concluído com sucesso!', [frm.doc.name]),
                                        indicator: 'green',
                                        primary_action: {       
                                            label: __('OK'),
                                            action: function() {
                                                frappe.hide_msgprint();
                                                frm.reload_doc();
                                            }
                                        }
                                    })
                                }
                                if (response.message.data.status === "OUT_FOR_SIGNATURE") {
                                    frappe.msgprint({
                                        title: __('Boletim de medição'),
                                        message: __('O processo de assinatura para o boletim de medição {0} ainda está em andamento.', [frm.doc.name]),
                                        indicator: 'blue',
                                        primary_action: {       
                                            label: __('OK'),
                                            action: function() {
                                                frappe.hide_msgprint();
                                                frm.reload_doc();
                                            }
                                        }
                                        
                                    })
                                }
                                if (response.message.data.status === "CANCELLED") {                                
                                    frappe.msgprint({
                                        title: __('Boletim de medição'),
                                        message: __('O processo de assinatura para o boletim de medição {0} foi cancelado.', [frm.doc.name]),
                                        indicator: 'red',
                                        primary_action: {       
                                            label: __('OK'),
                                            action: function() {
                                                frappe.hide_msgprint();
                                                frm.reload_doc();
                                            }
                                        }
                                        
                                    })
                                }                                
                            }
                            frm.reload_doc();
                        }
                    })
                }
            )
        };
        if (['Aberto','Devolvido'].includes(frm.doc.workflow_state)  && frappe.user.has_role('Administrador Global'))
        {
            // Botão Excluir
            frm.add_custom_button(
                '<i class="fa fa-trash"></i> ' + __('Excluir'), 
                function() {
                    frappe.confirm(
                        __('Tem certeza que deseja excluir este boletim de medição?'),
                        function() {
                            // Sim - executa a exclusão
                            frappe.call({
                                method: "arteris_app.arteris.doctype.contract_measurement.contract_measurement.delete",
                                args: {
                                    measurement: frm.doc.name
                                },
                                freeze: true,
                                freeze_message: `
                                    <div class="custom-loading">
                                        <div class="spinner-container">
                                            <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
                                        </div>
                                        <div class="loading-message">
                                            <strong>${__('Excluindo a medição...')}</strong>
                                        </div>
                                    </div>
                                    <style>
                                        .custom-loading {
                                            text-align: center;
                                            padding: 30px 20px;
                                        }
                                        .spinner-container {
                                            margin-bottom: 20px;
                                        }
                                        .loading-message {
                                            line-height: 1.5;
                                        }
                                        .fa-spin {
                                            animation: fa-spin 1s infinite linear;
                                        }
                                    </style>
                                `,
                                callback: function(response) {
                                    console.log(response);
                                    if (response.message.success) {
                                        if (response.message.data.success === "True") {        
                                            frappe.msgprint({
                                                title: __('Boletim de medição'),
                                                message: __('Boletim de medição {0} excluido com sucesso!', [frm.doc.name]),
                                                indicator: 'green',
                                                primary_action: {       
                                                    label: __('OK'),
                                                    action: function() {
                                                        frappe.hide_msgprint();
                                                    }
                                                }
                                            })
                                        }
                                        if (response.message.data.success === "False") {
                                            frappe.msgprint({
                                                title: __('Boletim de medição'),
                                                message: __('Falha ao excluir o boletim de medição {0}.', [frm.doc.name]),
                                                indicator: 'red',
                                                primary_action: {       
                                                    label: __('OK'),
                                                    action: function() {
                                                        frappe.hide_msgprint();
                                                        frm.reload_doc();
                                                    }
                                                }
                                            })
                                        }
                                    }
                                    frappe.set_route('List', 'Contract Measurement');
                                }
                            })
                        },
                        function() {
                            // Não - cancela a operação
                            frappe.show_alert({
                                message: __('Operação cancelada'),
                                indicator: 'info'
                            });
                        }
                    );
                }
            );            
            
            // Botão Recarregar e recalcular
            frm.add_custom_button(
                '<i class="fa fa-refresh"></i> ' + __('Recarregar'), 
                function() {
                    frappe.confirm(
                        __('Tem certeza que deseja recarregar e recalcular este boletim de medição? Esta operação pode levar alguns minutos.'),
                        function() {
                            // Sim - executa o reload
                            frappe.call({
                                method: "arteris_app.arteris.doctype.contract_measurement.contract_measurement.reload",
                                args: {
                                    measurement: frm.doc.name
                                },
                                freeze: true,
                                freeze_message: `
                                    <div class="custom-loading">
                                        <div class="spinner-container">
                                            <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
                                        </div>
                                        <div class="loading-message">
                                            <strong>${__('Recarregando e recalculando a medição...')}</strong>
                                        </div>
                                    </div>
                                    <style>
                                        .custom-loading {
                                            text-align: center;
                                            padding: 30px 20px;
                                        }
                                        .spinner-container {
                                            margin-bottom: 20px;
                                        }
                                        .loading-message {
                                            line-height: 1.5;
                                        }
                                        .fa-spin {
                                            animation: fa-spin 1s infinite linear;
                                        }
                                    </style>
                                `,
                                callback: function(response) {
                                    console.log(response);
                                    if (response.message.success) {
                                        if (response.message.data.success === "True") {        
                                            frappe.msgprint({
                                                title: __('Boletim de medição'),
                                                message: __('O processo de recarga e recalculo do boletim de medição {0} foi iniciado com sucesso, aguarde conclusão!', [frm.doc.name]),
                                                indicator: 'green',
                                                primary_action: {       
                                                    label: __('OK'),
                                                    action: function() {
                                                        frappe.hide_msgprint();
                                                        frm.reload_doc();
                                                    }
                                                }
                                            })
                                        }
                                        if (response.message.data.success === "False") {
                                            frappe.msgprint({
                                                title: __('Boletim de medição'),
                                                message: __('Falha ao iniciar o processo de recarga e recalculo do boletim de medição {0}. {1}', [frm.doc.name, response.message.error]),
                                                indicator: 'red',
                                                primary_action: {       
                                                    label: __('OK'),
                                                    action: function() {
                                                        frappe.hide_msgprint();
                                                        frm.reload_doc();
                                                    }
                                                }
                                            })
                                        }
                                    }
                                    frm.reload_doc();
                                }
                            })
                        },
                        function() {
                            // Não - cancela a operação
                            frappe.show_alert({
                                message: __('Operação cancelada'),
                                indicator: 'info'
                            });
                        }
                    );
                }
            );
            // Botão Recalcular
            frm.add_custom_button(
                '<i class="fa fa-calculator"></i> ' + __('Recalcular'), 
                function() {
                    frappe.confirm(
                        __('Tem certeza que deseja recalcular este boletim de medição? Esta operação pode levar alguns minutos.'),
                        function() {
                            // Sim - executa o recálculo
                            frappe.call({
                                method: "arteris_app.arteris.doctype.contract_measurement.contract_measurement.recalculate",
                                args: {
                                    measurement: frm.doc.name
                                },
                                freeze: true,
                                freeze_message: `
                                    <div class="custom-loading">
                                        <div class="spinner-container">
                                            <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
                                        </div>
                                        <div class="loading-message">
                                            <strong>${__('Recalculando a medição...')}</strong>
                                        </div>
                                    </div>
                                    <style>
                                        .custom-loading {
                                            text-align: center;
                                            padding: 30px 20px;
                                        }
                                        .spinner-container {
                                            margin-bottom: 20px;
                                        }
                                        .loading-message {
                                            line-height: 1.5;
                                        }
                                        .fa-spin {
                                            animation: fa-spin 1s infinite linear;
                                        }
                                    </style>
                                `,
                                callback: function(response) {
                                    console.log("Chegou aqui");
                                    if (response.message.success) {
                                        console.log("Verificou sucesso");
                                        if (response.message.data.success === "True") {        
                                            console.log("Imprimindo msg");
                                            frappe.msgprint({
                                                title: __('Boletim de medição'),
                                                message: __('O processo de recalculo do boletim de medição {0} foi iniciado com sucesso, aguarde conclusão!', [frm.doc.name]),
                                                indicator: 'green',
                                                primary_action: {       
                                                    label: __('OK'),
                                                    action: function() {
                                                        frappe.hide_msgprint();
                                                        frm.reload_doc();
                                                    }
                                                }
                                            })
                                        }
                                        if (response.message.data.success === "False") {
                                            console.log("Falhou msg");
                                            frappe.msgprint({
                                                title: __('Boletim de medição'),
                                                message: __('Falha ao iniciar o processo de recalculo do boletim de medição {0}. {1}', [frm.doc.name, response.message.error]),
                                                indicator: 'red',
                                                primary_action: {       
                                                    label: __('OK'),
                                                    action: function() {
                                                        frappe.hide_msgprint();
                                                        frm.reload_doc();
                                                    }
                                                }
                                            })
                                        }
                                    }
                                    frm.reload_doc();
                                }
                            })
                        },
                        function() {
                            // Não - cancela a operação
                            frappe.show_alert({
                                message: __('Operação cancelada'),
                                indicator: 'info'
                            });
                        }
                    );
                }
            )
        };
        frm.add_custom_button('Capa do boletim', function() {
            window.open('/capa_boletim?id=' + frm.doc.name);
        }, '🖨 Boletim');
        frm.add_custom_button('Boletim de medição', function() {
            // Concat openlink with the specific URL            
             window.open('/boletim_medicao?uuid='+frm.doc.contrato);
        }, '🖨 Boletim');
        frm.add_custom_button('Cidades', function() {
            // Concat openlink with the specific URL            
             window.open('/cidades_medicao?id=' + frm.doc.name);
        }, '🖨 Boletim');        
        frm.add_custom_button('Imagens', function() {
            // Concat openlink with the specific URL            
             window.open('/imagens?id=' + frm.doc.name);
        }, '🖨 Boletim');        
        
        frm.add_custom_button('Registros de tempo', function() {
            let url = `/app/query-report/Contract%20Measurement%20Record%20-%20Time?medicao=${frm.doc.name}`;
            window.open(url, '_blank');
        }, '🖨️ Auditoria');
        
        frm.add_custom_button('Registros de funções', function() {
            let url = let_url = `/app/query-report/Contract%20Measurement%20Record%20-%20Work%20Role?medicao=${frm.doc.name}`;
            window.open(url, '_blank');
        }, '🖨️ Auditoria');
        
        frm.add_custom_button('Registros de maq., equip. e veículos', function() {
            let url = let_url = `/app/query-report/Contract%20Measurement%20Record%20-%20Asset?medicao=${frm.doc.name}`;
            window.open(url, '_blank');
        }, '🖨️ Auditoria');   
 
        frm.add_custom_button('Registros de recursos', function() {
            let url = let_url = `/app/query-report/Contract%20Measurement%20Record%20-%20Resource?medicao=${frm.doc.name}`;
            window.open(url, '_blank');
        }, '🖨️ Auditoria');   
               
        frm.add_custom_button('Registros de cidades', function() {
            let url = let_url = `/app/query-report/Contract%20Measurement%20Record%20-%20Cities?medicao=${frm.doc.name}`;
            window.open(url, '_blank');
        }, '🖨️ Auditoria');        
  
    },
    before_workflow_action: function(frm) {
        // Primeiro, remove qualquer freeze existente
        frappe.dom.unfreeze();
        
        // Aguarda um ciclo de execução e aplica o freeze customizado
        setTimeout(function() {
            frappe.dom.freeze(`
                <div class="custom-loading">
                    <div class="spinner-container">
                        <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
                    </div>
                    <div class="loading-message">
                        <strong>${__('Aguarde...')}</strong>
                    </div>
                </div>
                <style>
                    .custom-loading {
                        text-align: center;
                        padding: 30px 20px;
                    }
                    .spinner-container {
                        margin-bottom: 20px;
                    }
                    .loading-message {
                        line-height: 1.5;
                    }
                    .fa-spin {
                        animation: fa-spin 1s infinite linear;
                    }
                </style>
            `);
        }, 10);
    },
    
    after_workflow_action: function(frm) {
        frappe.dom.unfreeze();
    },
    error: function(frm, cdt, cdn) {
        frappe.dom.unfreeze();
    }
});
 

function calcular_totais(frm) {

    let pedido_sap_sem_saldo = "";
    let total_tablepedidossap = 0;
    let total_tablepedidossapitem = 0;
    let total_tabsapmunicipio = 0;
    let total_tableftp = 0;
    let total_tabftporder = 0;
    let total_tablemaodeobra = 0;
    let total_tableativos = 0;
    let total_tablemunicipios = 0;
    let total_tblmunicipiositem = 0;
    let total_tabitenscontatrato = 0;
    let total_tblsaldos = 0;
    let medicaoatual = frm.doc.medicaoatual || 0;


    if (frm.doc.tablepedidossap) {
        frm.doc.tablepedidossap.forEach(function(row) {
            total_tablepedidossap += flt(row.valormedido) || 0;
            if (row.saldo < 0) {
                pedido_sap_sem_saldo += `<div class="alert alert-warning">Linha de pedido SAP sem saldo. ${row.linhapedido} saldo ${row.saldo} </div>`;
            }
        });
    }
    if (frm.doc.tablepedidossapitem) {
        frm.doc.tablepedidossapitem.forEach(function(row) {
            total_tablepedidossapitem += flt(row.valordotitem) || 0;
        });
    }
    if (frm.doc.tabsapmunicipio) {
        frm.doc.tabsapmunicipio.forEach(function(row) {
            total_tabsapmunicipio += flt(row.valor) || 0;
        });
    }
    if (frm.doc.tableftp) {
        frm.doc.tableftp.forEach(function(row) {
            total_tableftp += flt(row.valor) || 0;
        });
    }
    if (frm.doc.tabftporder) {
        frm.doc.tabftporder.forEach(function(row) {
            total_tabftporder += flt(row.valor) || 0;
        });
    }
    if (frm.doc.tablemaodeobra) {
        frm.doc.tablemaodeobra.forEach(function(row) {
            total_tablemaodeobra += flt(row.valormedido) || 0;
        });
    }
    if (frm.doc.tableativos) {
        frm.doc.tableativos.forEach(function(row) {
            total_tableativos += flt(row.valormedido) || 0;
        });
    }    
    if (frm.doc.tablemunicipios) {
        frm.doc.tablemunicipios.forEach(function(row) {
            total_tablemunicipios += flt(row.valor) || 0;
        });
    }
    if (frm.doc.tblmunicipiositem) {
        frm.doc.tblmunicipiositem.forEach(function(row) {
            total_tblmunicipiositem += flt(row.valor) || 0;
        });
    }    
    if (frm.doc.tabitenscontatrato) {
        frm.doc.tabitenscontatrato.forEach(function(row) {
            total_tabitenscontatrato += flt(row.valorpago) || 0;
        });
    }
    if (frm.doc.tblsaldos) {
        frm.doc.tblsaldos.forEach(function(row) {
            total_tblsaldos += flt(row.valorpago) || 0;
        });
    }          


    frm.set_df_property('total_tablepedidossap', 'options', html_total(total_tablepedidossap));
    frm.set_df_property('total_tablepedidossapitem', 'options', html_total(total_tablepedidossapitem));
    frm.set_df_property('total_tabsapmunicipio', 'options', html_total(total_tabsapmunicipio));
    frm.set_df_property('total_tableftp', 'options', html_total(total_tableftp));
    frm.set_df_property('total_tabftporder', 'options', html_total(total_tabftporder));
    frm.set_df_property('total_tablemaodeobra', 'options', html_total(total_tablemaodeobra));
    frm.set_df_property('total_tableativos', 'options', html_total(total_tableativos));
    frm.set_df_property('total_tablemunicipios', 'options', html_total(total_tablemunicipios));
    frm.set_df_property('total_tblmunicipiositem', 'options', html_total(total_tblmunicipiositem));
    frm.set_df_property('total_tabitenscontatrato', 'options', html_total(total_tabitenscontatrato));
    frm.set_df_property('total_tblsaldos', 'options', html_total(total_tblsaldos));

    let message = '';


    // Verificação dos totais para aprovação do boletim de medição
    if (
        (
            medicaoatual === 0 ||
            total_tablepedidossap === 0 ||
            total_tablemunicipios === 0 ||
            total_tabitenscontatrato === 0 ||
            !(
                medicaoatual.toFixed(2) === total_tablepedidossap.toFixed(2) &&
                medicaoatual.toFixed(2) === total_tablemunicipios.toFixed(2) &&
                medicaoatual.toFixed(2) === total_tabitenscontatrato.toFixed(2)
            )
        ) || (pedido_sap_sem_saldo !== "")
    )
    {

        message += '<p class="alert alert-danger">Para aprovar o boletim de medição verifique:</p>';
        message += pedido_sap_sem_saldo;
        if (medicaoatual === 0) {
            message += '<div class="alert alert-warning">Valor de "Medição atual (A)" zerado.</div>';
        }
        if (total_tablepedidossap === 0) {
            message += '<div class="alert alert-warning">Valor total de pedidos SAP zerado.</div>';
        }
        if (total_tablemunicipios === 0) {
            message += '<div class="alert alert-warning">Valor total de municípios zerado.</div>';
        }
        if (total_tabitenscontatrato === 0) {
            message += '<div class="alert alert-warning">Valor total de itens contratuais zerado.</div>';
        }
        if (
            !(
                medicaoatual.toFixed(2) === total_tablepedidossap.toFixed(2) &&
                medicaoatual.toFixed(2) === total_tablemunicipios.toFixed(2) &&
                medicaoatual.toFixed(2) === total_tabitenscontatrato.toFixed(2)
            ) 
        ) {
            message += '<div class="alert alert-warning">Os valores de "Medição atual (A)", "Total pedidos SAP", "Total municípios" e "Total itens contratuais" estão divergentes.</div>';
        }
        return message;
    }

    return '';

}

function html_total(value) {
    return `
        <hr style="margin: 10px 0 6px 0; border-color: #000000ff;">
        <div class="text-right text-bold" style="color: #000000ff; font-size: 1.1em;">
            Total: ${value.toLocaleString('pt-BR', { 
                style: 'currency', 
                currency: 'BRL', 
                minimumFractionDigits: 2 
            })}
        </div>`;
}