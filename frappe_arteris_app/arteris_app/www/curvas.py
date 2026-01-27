import frappe
from frappe import _

def get_context(context):
    """Context para a página de Curva S"""
    context.no_cache = 1
    context.show_sidebar = False
    context.show_navbar = False  
    context.show_footer = False  
    
    # Pegar contrato da URL
    contract = frappe.form_dict.get('contract')
    cw = frappe.form_dict.get('cw')

    # Buscar dados do contrato
    contract_data = frappe.get_last_doc('Contract S', filters = {'contrato': ("like", contract)})

    context.update({
        'contract': contract,
        'cw': cw,
        'contract_data': contract_data,
        'title': f'Curva S - {contract}',
        'page_title': 'Análise Curva S'
    })
    
    return context

@frappe.whitelist()
def get_chart_data(contract):
    """API endpoint para dados do gráfico"""
    return get_contract_chart_data(contract)

def get_contract_chart_data(contract):
    """Função para buscar dados da curva S"""
    data = frappe.db.sql("""
        WITH RECURSIVE meses_contrato AS (
            SELECT
                c.datainicial AS data_mes,
                c.datafinal,
                c.valortotal,
                TIMESTAMPDIFF(MONTH, c.datainicial, c.datafinal) + 1 AS total_meses,
                1 AS numero_mes
            FROM
                `tabContract S` c
            WHERE
                c.contrato = %(contract)s
            UNION ALL
            SELECT
                DATE_ADD(data_mes, INTERVAL 1 MONTH) AS data_mes,
                datafinal,
                valortotal,
                total_meses,
                numero_mes + 1
            FROM
                meses_contrato
            WHERE
                DATE_ADD(data_mes, INTERVAL 1 MONTH) <= datafinal
        ), sap_orders AS (
            SELECT
                so.datainicial AS data_mes,
                so.datafinal,
                so.valor_para_o_periodo AS valortotal,
                TIMESTAMPDIFF(MONTH, so.datainicial, so.datafinal) + 1 AS total_meses,
                1 AS numero_mes
            FROM
                `tabSAP Order Period` so
            WHERE
                so.contrato = %(contract)s
            UNION ALL
            SELECT
                DATE_ADD(data_mes, INTERVAL 1 MONTH) AS data_mes,
                datafinal,
                valortotal,
                total_meses,
                numero_mes + 1
            FROM
                sap_orders  -- CORREÇÃO: estava referenciando meses_contrato
            WHERE
                DATE_ADD(data_mes, INTERVAL 1 MONTH) <= datafinal
        ), dados_com_medicoes AS (
            SELECT
                mc.*,
                COALESCE(cm.medicaoatual, 0) AS valor_realizado_mes,
                COALESCE(
                    (SELECT SUM(sop.valor_para_o_periodo / (TIMESTAMPDIFF(MONTH, sop.datainicial, sop.datafinal) + 1))
                     FROM `tabSAP Order Period` sop
                     WHERE sop.contrato = %(contract)s
                       AND mc.data_mes BETWEEN sop.datainicial AND sop.datafinal),
                    0
                ) AS valor_sap_mes
            FROM
                meses_contrato mc
                    LEFT JOIN
                `tabContract Measurement` cm ON cm.contrato = %(contract)s
                    AND YEAR(cm.datafinalmedicao) = YEAR(mc.data_mes)
                    AND MONTH(cm.datafinalmedicao) = MONTH(mc.data_mes)
        )
        SELECT
            DATE_FORMAT(data_mes, '%%b/%%Y') AS periodo,
            ROUND(valortotal / total_meses, 2) AS valor_planejado_mes,
            valor_realizado_mes,
            valor_sap_mes,
            ROUND((valortotal / total_meses) * numero_mes, 2) AS valor_planejado_acumulado,
            SUM(valor_realizado_mes) OVER (ORDER BY data_mes) AS valor_realizado_acumulado,
            SUM(valor_sap_mes) OVER (ORDER BY data_mes) AS valor_sap_acumulado, 
            ROUND(((valortotal / total_meses) * numero_mes) / valortotal * 100, 2) AS percentual_planejado,
            ROUND(SUM(valor_realizado_mes) OVER (ORDER BY data_mes) / valortotal * 100, 2) AS percentual_realizado
        FROM
            dados_com_medicoes
        ORDER BY
            data_mes;
    """, {'contract': contract}, as_dict=True)
    
    if not data:
        return {"labels": [], "datasets": [], "performance_data": {"percentual_planejado": [], "percentual_realizado": []}}

    return {
        "labels": [d["periodo"] for d in data],
        "datasets": [
            {
                "name": "Planejado",
                "values": [float(d["valor_planejado_mes"] or 0) for d in data]
            },
            {
                "name": "SAP",
                "values": [float(d["valor_sap_mes"] or 0) for d in data]
            },
            {
                "name": "Realizado",
                "values": [float(d["valor_realizado_mes"] or 0) for d in data]
            },
            {
                "name": "Acum. Planejado", 
                "values": [float(d["valor_planejado_acumulado"] or 0) for d in data]
            },
            {
                "name": "Acum. SAP", 
                "values": [float(d["valor_sap_acumulado"] or 0) for d in data]
            },
            {
                "name": "Acum. Realizado",
                "values": [float(d["valor_realizado_acumulado"] or 0) for d in data]
            }
        ],
        "performance_data": {
            "percentual_planejado": [float(d["percentual_planejado"] or 0) for d in data],
            "percentual_realizado": [float(d["percentual_realizado"] or 0) for d in data]
        }
    }