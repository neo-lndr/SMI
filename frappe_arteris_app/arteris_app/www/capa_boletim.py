
import frappe
from ..api.measurement_cover import get_measurement
from frappe import _

def get_context(context):

    doc_id = frappe.form_dict.get('id')

    context.no_cache = 1
    context.show_sidebar = False
    context.show_navbar = False  
    context.show_footer = False  
    doc_id = frappe.form_dict.get('id')
    if doc_id:
        try:        
            m = get_measurement(doc_id)
            if m:
                context.contract_measurement_json = m.get("contract_measurement")
                context.contract_json = m.get("contract")
                context.concessionaria_json = m.get("concessionaria")
                context.contracted_company_json = m.get("contracted_company")
                context.pedidos_sap_json = m.get("pedidos_sap")
                context.pedidos_sap_totais_json = m.get("pedidos_sap_totais")
                context.saldos_json = m.get("saldos")
                context.saldos_pagos_json = m.get("saldos_pagos")

        except frappe.DoesNotExistError:
            frappe.throw(_("Contract Measurement not found"), frappe.DoesNotExistError)
    else:
        frappe.throw(_("No id provided in URL"), frappe.DoesNotExistError)
    return context
