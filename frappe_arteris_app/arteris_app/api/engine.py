import frappe
import frappe.utils

@frappe.whitelist(methods=["GET"])
def get_contracts():
    """
    Lista de contratos e boletins de medição para cálculo
    """

    # Antes de usar o boletim de medição como filtro
    # contracts = frappe.db.sql("""
    #     SELECT
    #         m.name AS boletimmedicao,
    #         c.name AS contrato
    #     FROM
    #         `tabContract` c
    #         INNER JOIN `tabContract Measurement` m ON c.name = m.contrato
    #     WHERE
    #         m.medicaovigente = 'Sim' AND
    #         m.workflow_state = 'Aberto' AND
    #         c.contratoencerrado IS NULL
    # """, as_dict=True)
    # return {"contracts": contracts}

    # Após usar o boletim de medição como filtro
    contracts = frappe.db.sql("""
        SELECT
            m.name AS boletimmedicao,
            c.name AS contrato
        FROM
            `tabContract` c
            INNER JOIN `tabContract Measurement` m ON c.name = m.contrato
        WHERE
            CASE WHEN m.workflow_state IS NULL THEN 'Aberto' ELSE m.workflow_state END = 'Aberto' AND
            c.contratoencerrado IS NULL
    """, as_dict=True)
    return {"contracts": contracts}

@frappe.whitelist(methods=["POST"])
def update_doctype():
    """
    Atualiza o doctype a partir do motor
    """
    body = frappe.form_dict
    
    engine_doctype = frappe.form_dict.doctype
    engine_field = frappe.form_dict.fields
    engine_value = frappe.form_dict.parameters_values
    engine_name = frappe.form_dict.id

    set_str = ", ".join([f"`{field}` = %s" for field in engine_field])

    frappe.db.sql(f"""
        UPDATE `tab{engine_doctype}`
        SET {set_str}
        WHERE name = %s;
    """, engine_value + [engine_name])

    # Obter todos os itens de contrato do banco de dados
    # set_result = frappe.db.set_value(engine_doctype, engine_name, engine_field, engine_value)
    # return set_result
    return {"Processed": True, "message": "Measurement items updated successfully."}

@frappe.whitelist(methods=["GET"])
def get_keys():
    """
    Obter todas as chaves de um doctype
    """
    
    body = frappe.form_dict

    doctype = frappe.form_dict.doctype
    filters = frappe.form_dict.filters
    return_field = frappe.form_dict.return_field

    # Obter todas as chaves do doctype
    keys = frappe.db.get_all(doctype, fields=return_field, filters=filters) 
    
    return keys

@frappe.whitelist(methods=["POST"])
def write_errors():
    """
    Inserir erros do motor
    """

    body = frappe.form_dict
    
    measurement = frappe.form_dict.measurement
    errors = frappe.form_dict.errors

    integration_inconsistency = frappe.new_doc("Integration Inconsistency")
    integration_inconsistency.tipo = "Motor de fórmulas"
    integration_inconsistency.dataehora = frappe.utils.now()
    integration_inconsistency.boletimmedicao = measurement

    str_error = ""
    for error in errors:
        str_error += f"{error}\n"
        
    integration_inconsistency.observacoes = str_error
    integration_inconsistency.save()

    return {"Processed": True, "message": "Errors written successfully."}
