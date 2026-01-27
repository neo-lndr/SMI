# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import throw, _

class ContractMeasurementRecord(Document):

    def set_apontamento_origem(self, method=None):
        if getattr(self.flags, "is_copy", False):
            original = getattr(self.flags, "original_doc", None)
            if original:
                self.apontamento_origem = original.name

    @frappe.whitelist()
    def descontar_payfactor(self, percent_payfactor, lote_payfactor):
        # valida percentual
        percent = flt(percent_payfactor)
        if percent <= 0:
            throw(_("O percentual Payfactor deve ser maior que zero"))

        # pega o documento original e clona
        original = frappe.get_doc(self.doctype, self.name)
        new_doc = frappe.copy_doc(original)

        # sinaliza para set_apontamento_origem
        new_doc.flags.is_copy = True
        new_doc.flags.original_doc = original
        new_doc.run_method("set_apontamento_origem")

        # grava percent_payfactor e lote_payfactor no clone
        new_doc.percent_payfactor = percent
        new_doc.lote_payfactor    = lote_payfactor

        # insere clone
        new_doc.insert(ignore_permissions=True)

        # seta boletim de medição vigente e outros campos
        contrato_id = new_doc.contrato
        boletim = frappe.db.get_value(
            'Contract Measurement',
            {'contrato': contrato_id, 'medicaovigente': 'SIM'},
            'name'
        )
        if boletim:
            new_doc.db_set('boletimmedicao', boletim, update_modified=False)
            new_doc.db_set('origem_integracao', 'Payfactor', update_modified=False)
            new_doc.db_set('medicaovigente', 'Sim',        update_modified=False)

        # prepara percentual restante para o cálculo do desconto
        restante_pct = (100.0 - percent) / 100.0

        # percorre cada recurso filho
        recursos = frappe.get_all(
            'Contract Measurement Record Resource',
            filters={'parent': new_doc.name}
        )

        for rec in recursos:
            # marca checkbox e propaga percent_payfactor
            frappe.db.set_value(
                'Contract Measurement Record Resource',
                rec.name,
                {
                    'is_payfactor': 1,
                    'percent_payfactor': percent
                },
                update_modified=False
            )

            # carrega o recurso para buscar quantidademedida e item
            rec = frappe.get_doc('Contract Measurement Record Resource', rec.name)
            quantidade = flt(rec.quantidademedida)
            item_code  = rec.item  # link para Contract Items

            # # busca valor unitário no Contract Items
            # valor_unitario = flt(frappe.db.get_value(
            #     'Contract Item', item_code, 'valorunitario'
            # ))

            valor_unitario = rec.valorunitario

            # calcula desconto: unitário * quantidade * restante_pct
            desconto = (valor_unitario * quantidade) * restante_pct

            # grava o desconto como valor negativo
            frappe.db.set_value(
                'Contract Measurement Record Resource',
                rec.name,
                'payfactor_discount',
                -desconto,
                update_modified=False
            )

        return new_doc.name

    def on_update(self):
        """
        Sempre que o pai for salvo, propaga percent_payfactor e recalcula payfactor_discount
        para todos os filhos.
        """
        percent = flt(self.percent_payfactor or 0)
        # Se percent for 0, evita divisão por zero
        if percent == 0:
            restante_pct = 0
        else:
            restante_pct = max(0.0, 100.0 - percent) / 100.0

        recursos = frappe.get_all(
            'Contract Measurement Record Resource',
            filters={'parent': self.name},
            pluck='name'
        )

        for rec_name in recursos:
            # atualização do percent_payfactor
            frappe.db.set_value(
                'Contract Measurement Record Resource',
                rec_name,
                'percent_payfactor',
                percent,
                update_modified=False
            )

            # recarrega para calcular quantidademedida e item
            rec = frappe.get_doc('Contract Measurement Record Resource', rec_name)
            quantidade = flt(rec.quantidademedida)
            item_code  = rec.item

            valor_unitario = flt(frappe.db.get_value(
                'Contract Item', item_code, 'valorunitario'
            ))

            desconto = valor_unitario * quantidade * restante_pct

            frappe.db.set_value(
                'Contract Measurement Record Resource',
                rec_name,
                'payfactor_discount',
                -desconto,
                update_modified=False
            )