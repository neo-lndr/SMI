import frappe

@frappe.whitelist(methods=["GET"])
def check_holidays(year: int):
    """
    Verifica se há feriados para um determinado ano.
    :param year: Ano para verificar os feriados.
    :return: Lista de feriados para o ano especificado.
    """
    if not year:
        return {"message": "Ano é obrigatório."}

    new_year = frappe.db.get_value('Holiday', {'data': f'{year}-01-01'}, ['data'])

    if new_year:
        return {"update": False, "message": f"Ano Novo já existe para o ano {year}. (Todos os feriados carregados)"}
    else:
        return {"update": True, "message": f"Ano Novo não existe para o ano {year}. (Carregar feriados)"}

@frappe.whitelist(methods=["POST"])
def update_holidays():
    """
    Atualiza os feriados atuais.
    """
    holidays_list = frappe.form_dict.holidays

    # Obter todos os feriados para o contrato
    for h in holidays_list:
        h_doctype = frappe.new_doc("Holiday")
        h_doctype.data = h['data']
        h_doctype.descricao = h['descricao']
        if h['uf']:
            h_doctype.uf = h['uf']
        h_doctype.save()

    return {"message": "Feriados atualizados com sucesso."}

