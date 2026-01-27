
import frappe
from ..api.measurement_cover import get_cities, get_sap_orders
from frappe import _
import json

def get_context(context):

    doc_id = frappe.form_dict.get('id')

    context.no_cache = 1
    context.show_sidebar = True
    doc_id = frappe.form_dict.get('id')
    if doc_id:
        try:        
            c = get_cities(doc_id)
            if c:
                context.cities_json = json.dumps({"cities": c})
            s = get_sap_orders(doc_id)
            if s:
                context.saporders_json = json.dumps({"saporders": s})
        except frappe.DoesNotExistError:
            frappe.throw(_("Contract Measurement not found"), frappe.DoesNotExistError)
    else:
        frappe.throw(_("No id provided in URL"), frappe.DoesNotExistError)
    return context
