
import frappe

def set_adjustment(
        contract: str):
    """
    Aplica o reajuste ao total do contrato

    Parâmetros:
        contract: str - Nome do contrato
    """

    # Calcula o valor total do contrato
    total = frappe.db.sql("""
        SELECT
            SUM(valortotalvigente) AS total
        FROM
            `tabContract Item`
        WHERE
            contrato = %s
    """, (contract,), as_dict=True)

    # Atualiza o valor total do contrato
    if total and total[0]['total'] is not None:
        frappe.db.sql("""
            UPDATE
                `tabContract`
            SET
                valortotalp0 = CASE WHEN valortotalp0 IS NULL THEN valortotal  WHEN valortotalp0 = 0 THEN valortotal ELSE valortotalp0 END,
                valortotal = %(valor)s
            WHERE
                name = %(contrato)s
        """, {'valor': total[0]['total'], 'contrato': contract})
