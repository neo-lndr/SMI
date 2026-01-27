
import frappe
import json
from datetime import datetime, date
from ..api.measurement_report import get_measurement_data
from frappe import _

def get_context(context):

    # Converter objetos Python para formato JSON
    def convert_to_json_serializable(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, bool):
            return obj
        return obj
        
    context.no_cache = 1
    context.show_sidebar = False
    context.show_navbar = False  
    context.show_footer = False  
    doc_id = frappe.form_dict.get('id')
    if doc_id:
        try:        
            m = get_measurement_data(doc_id)
            if m:
                measurement_data_json = json.dumps(m, default=convert_to_json_serializable, ensure_ascii=False)
                context.measurement_data_json = measurement_data_json
        except Exception as e:
            frappe.throw(_("Error fetching measurement data: {0}").format(str(e)), frappe.ValidationError)
    else:
        frappe.throw(_("No id provided in URL"), frappe.DoesNotExistError)
    return context
