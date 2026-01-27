
import frappe
from ..api.kartado import get_measurement_images_list
from frappe import _
import json

def get_context(context):

    doc_id = frappe.form_dict.get('id')

    context.no_cache = 1
    context.show_sidebar = True
    doc_id = frappe.form_dict.get('id')
    if doc_id:
        try:        
            i = get_measurement_images_list(doc_id)
            if i:
                context.pictures_json = json.dumps(i)
        except frappe.DoesNotExistError:
            frappe.throw(_("Contract Measurement not found"), frappe.DoesNotExistError)
    else:
        frappe.throw(_("No id provided in URL"), frappe.DoesNotExistError)
    return context
