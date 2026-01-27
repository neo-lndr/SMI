import frappe
from frappe.utils import flt

@frappe.whitelist(methods=["POST"])
def update_contract_item():
    
    item = frappe.form_dict.item

    try:
        
        doc_item = frappe.get_doc("Contract Item", item['name'])
        doc_item.valortotalvigente = item['valortotal']
        doc_item.saldocarregado = item['saldoatual']
        doc_item.tipodoitem = item['tipo'] if item['tipo'] else None
        doc_item.codigopep = item['pep'] if item['pep'] else None
        if item['cidade']:
            doc_item.cidade = item['cidade']
        doc_item.percentualhe = item['percentualhe'] if item['percentualhe'] else None
        doc_item.dom_hora = item['h_dom']
        doc_item.seg_hora = item['h_seg']
        doc_item.ter_hora = item['h_ter']
        doc_item.qua_hora = item['h_qua']
        doc_item.qui_hora = item['h_qui']
        doc_item.sex_hora = item['h_sex']
        doc_item.sab_hora = item['h_sab']
        doc_item.valormedidocarregado = item['medido']
        doc_item.save(ignore_permissions=True)        

        frappe.db.commit()
        
        return {"success": True, "message": "Item do contrato atualizado com sucesso"}
    
    except Exception as e:
        frappe.log_error(e, "update_contract_item")
        return {"success": False, "message": str(e)}
    

@frappe.whitelist(methods=["POST"])
def create_item_main(contract: str):
    """
    Cria o item principal para o contrato
    """

    exists_item = frappe.db.exists("Contract Item", {"contrato": contract, "is_group": 1})
    if exists_item:
        return {"message": "Item principal já existe para este contrato"}

    contract_doc = frappe.db.get_all("Contract", fields=["name", "contrato"], filters={"name": contract})
    
    # Certifique-se de que existe um documento de contrato
    if not contract_doc:
        frappe.throw("Contrato não encontrado")
    
    # Acessa o primeiro item da lista
    contract_data = contract_doc[0]
    
    contract_item = frappe.new_doc("Contract Item")
    contract_item.is_group = 1
    contract_item.codigo = f"Contrato {contract_data['contrato']}"
    contract_item.descricao = f"Contrato {contract_data['contrato']}"
    contract_item.contrato = contract_data["name"]
    result = contract_item.save()

    return result

@frappe.whitelist(methods=["POST"])
def create_item_main_all_contracts():
    """
    Cria o item principal para todos os contratos
    """

    contracts = frappe.get_all("Contract", fields=["name"])
    
    for contract in contracts:
        create_item_main(contract.name)
    
    return {"message": "Itens principais criados para todos os contratos"}

@frappe.whitelist(methods=["POST"])
def update_contrat():

    def update_childs(parent, contract):
        frappe.db.sql("UPDATE `tabContract Item` SET contrato=%s WHERE parent_contract_item=%s", (contract, parent))
        child_itens = frappe.db.sql(f"""
            SELECT
                item.name,
                item.contrato
            FROM
                `tabContract Item` item
            WHERE 
                item.parent_contract_item = '{parent}'
                AND item.is_group = 1
        """, as_dict=True)
        for c in child_itens:
            update_childs(c['name'], contract)

    root_itens = frappe.db.sql(f"""
        SELECT
            item.name,
            item.contrato
        FROM
            `tabContract Item` item
        WHERE 
            item.parent_contract_item IS NULL
            AND NOT item.contrato IS NULL
            AND item.is_group = 1
    """, as_dict=True)

    for r in root_itens:
        update_childs(r['name'], r['contrato'].replace("'", ""))    
    
    return {"Informação": "Contrato atualizado para todos os itens"}

def set_item_adjustment(
        item: str, 
        sap_order_line: str, 
        percent: float, 
        unitvalue: float,
        adjustment_name: str):
    """
    Aplica o reajuste no item do contrato

    Parâmetros:
        item: str - Nome do item do contrato
        sap_order_line: str - Nome da linha do pedido SAP
        percent: float - Percentual de reajuste
        unitvalue: float - Valor unitário atualizado
    """

    # Obtém os dados da linha do pedido SAP
    sap_order = frappe.db.get_value("SAP Order Period", sap_order_line, ["parent","saldo","valor_para_o_periodo"], as_dict=True)
    # Obtém o capex_opex do pedido SAP
    capex_opex = frappe.db.get_value("SAP Order", sap_order.parent, "capexopex")
    # Carrega e atualiza o item do contrato
    doc_item = frappe.get_doc("Contract Item", item)
    if not doc_item.valorunitariop0:
        doc_item.valorunitariop0 = doc_item.valorunitario
        doc_item.quantidadep0 = doc_item.quantidade
        doc_item.valortotalvigentep0 = doc_item.valortotalvigente
    doc_item.valorunitario = unitvalue
    doc_item.valortotalvigente = flt(doc_item.valorunitario * doc_item.quantidade, 2)
    # Adiciona a linha do pedido SAP no item do contrato
    doc_item.append("tablepedidossap", {
        "pedidosap": sap_order.parent,
        "pedidolinha": sap_order_line,
        "capexopex": capex_opex,
        "saldo": sap_order.saldo,
        "valortotal": sap_order.valor_para_o_periodo,
        "percentual": percent
    })
    # Vincula o reajuste ao item do contrato
    doc_item.append("tabreajustes", {
        "reajustecodigo": adjustment_name
    })
    doc_item.save(ignore_permissions=True)

def clear_item_adjustment(
        item: str, 
        sap_order_line: str, 
        unitvalue: float, 
        adjustment_name: str):
    """
    Limpa o reajuste no item do contrato

    Parâmetros:
        item: str - Nome do item do contrato
        sap_order_line: str - Nome da linha do pedido SAP
        unitvalue: float - Valor unitário anterior
    """

    # Carrega o item do contrato
    doc_item = frappe.get_doc("Contract Item", item)
    doc_item.valorunitario = unitvalue
    doc_item.valortotalvigente = flt(doc_item.valorunitario * doc_item.quantidade, 2)

    # Remove a linha do pedido SAP do item do contrato
    for d in doc_item.tablepedidossap:
        if d.pedidolinha == sap_order_line:
            frappe.db.sql("DELETE FROM `tabContract Item Order` WHERE name = %s", (d.name,))
    # Remove o reajuste do item do contrato
    for r in doc_item.tabreajustes:
        if r.reajustecodigo == adjustment_name:
            frappe.db.sql("DELETE FROM `tabContract Item Adjustment` WHERE name = %s", (r.name,))
    doc_item.save(ignore_permissions=True)

