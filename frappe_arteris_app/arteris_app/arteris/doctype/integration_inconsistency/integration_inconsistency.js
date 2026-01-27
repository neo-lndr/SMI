// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

function ButtonFunction(listview) {
     console.log("ButtonFunction");
     frappe.msgprint("ButtonFunction");
}
 
frappe.listview_settings['Integration Inconsistency'] = {
    refresh: function(listview) {
        listview.page.add_inner_button("Button Name", function() {
            ButtonFunction(listview);
        });;
    },
};

// // Para a LISTA do DocType - adicione este código
// frappe.listview_settings['Integration Inconsistency'] = {
//     onload: function(listview) {
//         // Adiciona botão personalizado na lista
//         listview.page.add_menu_item(__('Status AdobeSign'), function() {
//             frappe.call({
//                 method: "arteris_app.arteris.doctype.integration_inconsistency.integration_inconsistency.clear_inconsistencies",
//                 args: {},
//                 freeze: true,
//                 freeze_message: `
//                     <div class="custom-loading">
//                         <div class="spinner-container">
//                             <i class="fa fa-spinner fa-spin fa-3x text-primary"></i>
//                         </div>
//                         <div class="loading-message">
//                             <strong>${__('Limpando registros...')}</strong>
//                         </div>
//                     </div>
//                     <style>
//                         .custom-loading {
//                             text-align: center;
//                             padding: 30px 20px;
//                         }
//                         .spinner-container {
//                             margin-bottom: 20px;
//                         }
//                         .loading-message {
//                             line-height: 1.5;
//                         }
//                         .fa-spin {
//                             animation: fa-spin 1s infinite linear;
//                         }
//                     </style>
//                 `,
//                 callback: function(r) {
//                     if (r.message) {
//                         frappe.msgprint(__('Operação concluída com sucesso!'));
//                         // Recarrega a lista
//                         listview.refresh();
//                     }
//                 }
//             });
//         });
//     }
// };