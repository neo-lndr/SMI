import frappe
import frappe.utils

@frappe.whitelist(methods=["POST"])
def set_sap_orders_balance():
    frappe.db.sql("""
        UPDATE
            `tabSAP Order`
        SET
            saldo = saldosap
        WHERE
            (valortotalmedido IS NULL OR valortotalmedido = 0) AND 
            (saldo IS NULL OR saldo = 0)
    """)
    frappe.db.sql("""
        UPDATE
            `tabSAP Order Period`
        SET
            saldo = saldosap
        WHERE
            (valormedido IS NULL OR valormedido = 0) AND 
            (saldo IS NULL OR saldo = 0)
        """)    

@frappe.whitelist(methods=["POST"])
def update_sap_orders_balance():
    try:
        # Atualiza os pedidos SAP
        frappe.db.sql("""
            UPDATE 
                `tabSAP Order` sap_order
                LEFT JOIN 
                    (SELECT
                        pedido_sap,
                        SUM(valormedido) AS valormedido
                    FROM
                        `tabContract Measurement SAP Order`
                    GROUP BY
                        pedido_sap) m_sap_order ON m_sap_order.pedido_sap = sap_order.name
            SET
                sap_order.valortotalmedido = CASE WHEN m_sap_order.valormedido IS NULL THEN 0 ELSE m_sap_order.valormedido END,
                sap_order.saldo = sap_order.valortotal - CASE WHEN m_sap_order.valormedido IS NULL THEN 0 ELSE m_sap_order.valormedido END""")
        
        frappe.db.sql("""
            UPDATE 
                `tabSAP Order Period` sap_order
                LEFT JOIN 
                    (SELECT
                        linhapedido,
                        SUM(valormedido) AS valormedido
                    FROM
                        `tabContract Measurement SAP Order`
                    GROUP BY
                        linhapedido) m_sap_order ON m_sap_order.linhapedido = sap_order.name
            SET
                sap_order.valormedido = CASE WHEN m_sap_order.valormedido IS NULL THEN 0 ELSE m_sap_order.valormedido END,
                sap_order.saldo = sap_order.valor_para_o_periodo - CASE WHEN m_sap_order.valormedido IS NULL THEN 0 ELSE m_sap_order.valormedido END""")
    except Exception as e:
        frappe.log_error(f"Error on update_sap_orders_balance: {str(e)}", "Measurement API")
        return None       

@frappe.whitelist(methods=["POST"])
def create_sap_orders():

    body = frappe.form_dict
    sap_orders = frappe.form_dict.data

    contracts = {}
    errors = []

    # Insert or update SAP orders
    for order, order_data in sap_orders.items():

        # Calculate the total amount for the order
        valor_total = sum(line.get('valortotal', 0) for line in order_data['linhas'])
        saldo = sum(line.get('saldo', 0) for line in order_data['linhas'])

        # Check if the order already exists
        order_name = frappe.db.get_value('SAP Order', {'numeropedido': order_data['numeropedido']}, 'name')

        order_doc = None
        if not order_name or not isinstance(order_name, str):
            # Create a new SAP Order if it doesn't exist
            order_doc = frappe.new_doc("SAP Order")
            order_doc.saldo = saldo
        else:
            # Load the existing SAP Order
            order_doc = frappe.get_doc("SAP Order", str(order_name))

        for line in order_data['linhas']:
            # Get contracts with cost center
            contract_cc = f"{order_data['contrato']}-{line['centrodecusto'][:2]}"
            if (not contract_cc in contracts):
                contract_name = frappe.db.get_value('Contract', {'contrato': contract_cc}, 'name')
                if not contract_name:
                    contract_name = frappe.db.get_value('Contract', {'contrato': order_data['contrato']}, 'name')
                    if not contract_name:
                        contracts[contract_cc] = None
                    else:
                        contracts[contract_cc] = contract_name
                else:
                    contracts[contract_cc] = contract_name
            line['contrato'] = contracts[contract_cc]            

        order_doc.numeropedido = order_data['numeropedido']
        order_doc.valortotal = valor_total
        order_doc.contratomarco = order_data['contrato_marco']
        order_doc.classe = order_data['classe']
        order_doc.capexopex = order_data['capexopex']
        if not order_doc.saldosap == saldo:
            order_doc.saldosapatualizacao = frappe.utils.now_datetime()
            order_doc.saldosap = saldo
        order_doc.descricao = order_data['descricao'][0:119].upper()
        if order_data['descricao'].upper() == 'FATURAMENTO DIRETO':
            order_doc.faturamentodireto = 1
        order_doc.save(ignore_permissions=True)

        for line in order_data['linhas']:
            
            line['exists'] = False    

            # Check line has contract
            if not line['contrato']:
                continue     

            # Check if the line already exists
            line_doc = None
            for line_doc in order_doc.table_dscc:
                line['exists'] = (line_doc.linhapedido == line['linhapedido'])
                # Get the existing line if it exists
                if line['exists']:
                    break
            # Create a new line if it doesn't exist
            if not line['exists']:
                line_doc = order_doc.append('table_dscc')
                line_doc.saldo = line['saldo']
                
            line_doc.datainicial = line['datainicial']
            line_doc.datafinal = line['datafinal']
            line_doc.linhapedido = line['linhapedido']
            line_doc.pep = line['pep']
            line_doc.centrodecusto = line['centrodecusto']
            line_doc.valor_para_o_periodo = line['valortotal']
            line_doc.reidi = line['reidi']
            if not line_doc.saldosap == line['saldo']:
                line_doc.saldosapatualizacao = frappe.utils.now_datetime()
            line_doc.saldosap = line['saldo']
            if line_doc.saldo == 0 and line['saldo'] > 0:
                line_doc.saldo = line['saldo']
            line_doc.contrato = line['contrato']

        try:
            order_doc.save(ignore_permissions=True)
            print(f"Processed SAP Order: {order}")
        except Exception as e:
            errors.append(f"Erro ao processar o Pedido SAP {order}: {str(e)}")
            print(f"Error processing SAP Order {order}: {str(e)}")

    for error in errors:
        frappe.log_error(error)
        print(error)

    return {"Processed": True, "errors": errors}

def set_sap_order_line_adjustment(order_line: str, indice: float) -> bool:
    """
    Atualiza o índice de reajuste na linha do pedido SAP

    Parâmetros:
        order_line: str - Nome da linha do pedido SAP
        indice: float - Índice de reajuste a ser aplicado

    Retorna:
        bool - True se o ajuste foi aplicado com sucesso, False caso contrário
    """
    try:
        
        # Aplica o índice de reajuste na linha do pedido SAP
        line_doc = frappe.get_doc("SAP Order Period", order_line)
        line_doc.indicereajuste = indice
        line_doc.save(ignore_permissions=True)
        return True
    
    except Exception as e:
        frappe.log_error(f"Error on set_adjustment for line {order_line}: {str(e)}", "SAP Order Adjustment")
        return False
    
def clear_sap_order_line_adjustment(order_line: str) -> bool:
    """
    Atualiza o índice de reajuste na linha do pedido SAP

    Parâmetros:
        order_line: str - Nome da linha do pedido SAP
        indice: float - Índice de reajuste a ser aplicado

    Retorna:
        bool - True se o ajuste foi aplicado com sucesso, False caso contrário
    """
    try:
        
        # Aplica o índice de reajuste na linha do pedido SAP
        line_doc = frappe.get_doc("SAP Order Period", order_line)
        line_doc.indicereajuste = 0
        line_doc.save(ignore_permissions=True)
        return True
    
    except Exception as e:
        frappe.log_error(f"Error on set_adjustment for line {order_line}: {str(e)}", "SAP Order Adjustment")
        return False    