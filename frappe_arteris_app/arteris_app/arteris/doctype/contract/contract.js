frappe.ui.form.on('Contract', {
    refresh: function(frm) {        
        if (frappe.user.has_role('Administrador Global'))
        {
            frm.add_custom_button(
                '<i class="fa fa-refresh"></i> ' + __('Forçar carga de dados'), 
                function() {
                    frappe.confirm(
                        __('Tem certeza que deseja forçar a carga de dados do contrato? Esta operação pode levar alguns minutos.'),
                        function() {
                            // Sim - executa a carga de dados
                            frappe.call({
                                method: "arteris_app.arteris.doctype.contract.contract.force_data_load",
                                args: {
                                    contract: frm.doc.name
                                },
                                freeze: true,
                                freeze_message: `
                                    <div class="custom-loading">
                                        <div class="spinner-container">
                                            <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
                                        </div>
                                        <div class="loading-message">
                                            <strong>${__('Carregando dados do contrato...')}</strong>
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
                                                title: __('Contrato'),
                                                message: __('O processo de carga do contrato {0} foi inciado com sucesso!', [frm.doc.contrato]),
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
                                                title: __('Contrato'),
                                                message: __('Falha ao iniciar o processo de carga do contrato {0}. {1}', [frm.doc.contrato, response.message.error]),
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
        if (!frm.is_new()) {
            // Adicionar ícone ao botão
            frm.add_custom_button(
                '<i class="fa fa-sitemap"></i> ' + __('Estrutura de Itens'), 
                function() {
                    // Navegar com query parameter
                    var route = frappe.get_route();
                    window.location.href = frappe.urllib.get_full_url(
                        `/app/contract-item?contrato=${encodeURIComponent(frm.doc.name)}`
                    );
                }
            ).addClass('btn-primary');
        };
        frm.add_custom_button(
            'Curva S', 
            function() {
                window.open('/curvas?contract=' + frm.doc.name + '&cw=' + frm.doc.contrato);
            }
        ).addClass('btn-secondary');
    }
});