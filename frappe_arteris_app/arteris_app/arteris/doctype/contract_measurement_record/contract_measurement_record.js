// Copyright (c) 2025, Renoir and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Contract Measurement Record", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Contract Measurement Record', {
  onload(frm) {
    const hasOrigin = !!frm.doc.apontamento_origem;
    frm.toggle_display('payfactor_section', hasOrigin);

    // exibe modal de sucesso, se aplicável
    if (sessionStorage.getItem('cmr_dup_success')) {
      frappe.msgprint({
        title: __('Sucesso'),
        indicator: 'green',
        message: __('Registro duplicado com sucesso!')
      });
      sessionStorage.removeItem('cmr_dup_success');
    }
  },

  refresh(frm) {
    const hasOrigin = !!frm.doc.apontamento_origem;
    // frm.toggle_display('payfactor_section', hasOrigin);

    if (!frm.is_new() && !frm.doc.apontamento_origem) {
      frm.add_custom_button(__('Decontar Payfactor'), () => {
        frappe.prompt([
          {
            fieldtype: 'Float',
            fieldname: 'porcentagem_payfactor_input',
            label: __('Percentual Payfactor'),
            reqd: 1
          },
          {
            fieldtype: 'Data',
            fieldname: 'lote_payfactor_input',
            label: __('Observação (Lote)'),
            reqd: 1
          }
        ], values => {
          // validações
          if (values.porcentagem_payfactor_input <= 0) {
            frappe.msgprint({
              title: __('Aviso'),
              indicator: 'orange',
              message: __('Informe um percentual maior que zero para continuar.')
            });
            return;
          }
          if (!values.lote_payfactor_input.trim()) {
            frappe.msgprint({
              title: __('Aviso'),
              indicator: 'orange',
              message: __('Informe observação (lote) para continuar.')
            });
            return;
          }

          // sinaliza popup de sucesso pendente
          sessionStorage.setItem('cmr_dup_success', '1');

          // chama o método Python passando os dois valores
          frm.call('descontar_payfactor', {
            percent_payfactor: values.porcentagem_payfactor_input,
            lote_payfactor: values.lote_payfactor_input
          })
          .then(r => {
            if (r.message) {
              frappe.set_route('Form', 'Contract Measurement Record', r.message);
            }
          })
          .catch(err => {
            frappe.msgprint({
              title: __('Erro'),
              indicator: 'red',
              message: __('Não foi possível duplicar o registro: ') + err.message
            });
            sessionStorage.removeItem('cmr_dup_success');
          });

        }, __('Informe dados de Payfactor'), __('Continue'));
      });
    }
  }
});