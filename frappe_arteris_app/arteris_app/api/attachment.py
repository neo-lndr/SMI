import frappe
import base64

@frappe.whitelist(methods=["POST"])
def upload_file(doctype=None, record_name=None, file_64=None, file_name=None):
    """
    Envia um arquivo e anexa a um Doctype
    """

    try:

        if not doctype:
            doctype = frappe.form_dict.doctype
            record_name = frappe.form_dict.name
            file_64 = frappe.form_dict.data
            file_name = frappe.form_dict.filename

        file_bytes = base64.b64decode(file_64)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": doctype,
            "attached_to_name": record_name,
            "content": file_bytes,
            "is_private": 1
        })
        file_doc.save(ignore_permissions=True)

        record_doc = frappe.get_doc(doctype, record_name)
        record_doc.datahoraimagens = frappe.utils.now()
        record_doc.set("attachment", file_doc.file_url)
        record_doc.save(ignore_permissions=True)

        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "upload_file")
        return {"success": False, "message": str(e)}

    return {"success": True, "message": "Arquivo anexado com sucesso."}


