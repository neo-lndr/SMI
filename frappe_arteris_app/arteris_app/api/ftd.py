import frappe
import frappe.utils
from datetime import datetime, date
from .measurement import get_measurement

@frappe.whitelist(methods=["POST"])
def create_ftd():

    def parse_date(d: str) -> date:
        year, month, day = d.split('-')
        return date(int(year), int(month), int(day))

    body = frappe.form_dict
    ftds = frappe.form_dict.data

    contracts = {}
    errors = []

    # Inserir ou atualizar pedidos SAP
    for ftd, ftd_data in ftds.items():

        # Calcular o valor total do pedido
        valor_total = sum(line.get('valortotal', 0) for line in ftd_data['linhas'])

        # Verificar todas as linhas do pedido SAP
        line_errors = []
        ftd_data['contrato'] = None
        ftd_data['registroexiste'] = False
        for line in ftd_data['linhas']:
            sap_order_line_a = f"{line['numeropedido']}-{line['linhapedido']}"
            sap_order_line_b = f"{line['numeropedido']}-{line['linhapedido']:03d}"
            order_line = frappe.db.sql("""
                SELECT 
                    p.name,
                    s.contrato
                FROM 
                    `tabSAP Order Period` p
                    INNER JOIN `tabSAP Order` s ON s.name = p.parent
                WHERE 
                    p.name = %s OR
                    p.name = %s
            """, (sap_order_line_a, sap_order_line_b), as_dict=True)

            line['linhasap'] = None

            # Obter o contrato e a linha do pedido
            if order_line:
                line['linhasap'] = order_line[0]['name']
                ftd_data['contrato'] = order_line[0]['contrato']
            else:
                line_errors.append(f"Linha do Pedido SAP {sap_order_line_b} não localizada, FTD - NF: {ftd_data['notafiscal']}!")

            # Ignorar se já existir
            if len(line_errors) == 0:
                # Verificar se ainda não existe na medição
                ftp_measurement = frappe.db.sql("""
                    SELECT
                        fo.name
                    FROM
                        `tabContract Measurement FTD Order` fo
                        INNER JOIN `tabContract Measurement` cm ON cm.name = fo.parent
                    WHERE
                        cm.contrato = %s AND
                        fo.notafiscal = %s AND
                        (fo.linhapedidosap = %s OR fo.linhapedidosap = %s) 
                """, (ftd_data['contrato'], ftd_data['notafiscal'], sap_order_line_a, sap_order_line_b), as_dict=True)
                # Ignorar se já existir
                if ftp_measurement:
                    ftd_data['registroexiste'] = True
                    break

        # Todas as linhas devem ser válidas
        if len(line_errors) > 0:
            errors.extend(line_errors)
            continue

        # Ignorar se já existir
        if ftd_data['registroexiste']:
            continue        

        data_entrada = parse_date(ftd_data['datadocumento'])

        new_measurement = get_measurement(
            data_entrada.strftime('%Y-%m-%d'), 
            data_entrada.strftime('%Y-%m-%d'), 
            ftd_data['contrato'])

        measurement_name = None
        if new_measurement:
            measurement_name = new_measurement['measurements'][0]['name']  

        # É necessário ter uma medição válida
        if not measurement_name:
            errors.append(f"Contrato {ftd_data['contrato']} não possui medição vigente. FTD - NF: {ftd_data['notafiscal']}!")
            continue

        # Obter o doctype de medição
        measurement_doc = frappe.get_doc('Contract Measurement', measurement_name)

        # Verificar o desconto de data
        if not (parse_date(ftd_data['datadocumento']) >= measurement_doc.datainicialmedicao and 
                parse_date(ftd_data['datadocumento']) <= measurement_doc.datafinalmedicao):
            continue

        # Criar as linhas de pedido FTD
        for line in ftd_data['linhas']:
           measurement_doc.append('tabftporder', {
                'notafiscal': ftd_data['notafiscal'],
                'quantidade': line['quantidade'],
                'unidade': line['unidade'],
                'valor': line['valortotal'],
                'linhapedidosap': line['linhasap'],
                'miro': line['documentomigo'],
                'migo': line['documentomiro']
            })

        measurement_doc.append('tableftp', {
            'notafiscal': ftd_data['notafiscal'],
            'datadesconto': ftd_data['dataentrada'],
            'data': ftd_data['datadocumento'],
            'valor': valor_total
        })

        measurement_doc.save(ignore_permissions=True)

    for error in errors:
        frappe.log_error(error)
        print(error)

    return {"Processed": True, "errors": errors}