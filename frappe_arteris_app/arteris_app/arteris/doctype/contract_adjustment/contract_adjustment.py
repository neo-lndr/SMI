# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
import json  # ADICIONADO: import json que estava faltando
from frappe.model.document import Document
from arteris_app.api.saporder import set_sap_order_line_adjustment, clear_sap_order_line_adjustment
from arteris_app.api.contractitem import set_item_adjustment, clear_item_adjustment
from arteris_app.api.measurement import set_measurement_adjustment, clear_measurement_adjustment
from arteris_app.api.contract import set_adjustment


class ContractAdjustment(Document):

    def before_submit(self):

        # Verfica os requisitos
        sap_lines = {}

        for sap in self.tabsap:

            # Verifique se temos valor, indice e linha do pedido SAP
            existe_linha = 0
            if (sap.pedidolinha):
                existe_linha = 1
            existe_indice = 0
            if (sap.indicereajuste):
                if (sap.indicereajuste != 0):
                    existe_indice = 1

            if not sap.pedidolinha in sap_lines:
                sap_lines.setdefault(sap.pedidolinha, sap.indicereajuste)
            else:
                if sap_lines[sap.pedidolinha] != sap.indicereajuste:
                    frappe.throw(f"Verifique a linha de reajustes {sap.idx}, o Pedido SAP {sap.pedidolinha} possui índices diferentes, não é possível infomar dois ou mais índices para uma mesma linha de Pedido SAP.")


            # Valida se todos os campos estão preenchidos ou todos estão vazios
            if (existe_linha + existe_indice) not in (0, 2):
                frappe.throw(f"Verifique a linha de reajustes {sap.idx}, preencha Ind.% e Pedido SAP. Ou zere o valor do Ind.% e remova pedido SAP da linha.")


        # Recupera o valor total antes do ajuste
        _total_before = frappe.db.sql("""
            SELECT
                SUM(valortotalvigente) AS total_before
            FROM
                `tabContract Item`
            WHERE
                contrato = %s
        """, (self.contrato,), as_dict = True)

        for sap in self.tabsap:
            if sap.pedidolinha and sap.indicereajuste and sap.indicereajuste != 0:
                # Aplica os indices para os pedidos SAP
                set_sap_order_line_adjustment(sap.pedidolinha, sap.indicereajuste)
                # Atualiza os valores unitários dos itens do contrato
                set_item_adjustment(sap.item, sap.pedidolinha, sap.indicereajuste, sap.valorreajuste, self.name)
        # Atualiza os valores retroativos dos itens da medição vinculadas ao contrato, se houver
        measurement = set_measurement_adjustment(self.name, self.contrato)
        if not measurement:
            frappe.throw("Não foi possível aplicar o reajuste ao contrato. Verifique se há ao menos uma medição aberta para o contrato.")
        self.boletimmedicao = measurement

        # Recupera o valor total após o ajuste
        _total_after = frappe.db.sql("""
            SELECT
                SUM(valortotalvigente) AS total_after
            FROM
                `tabContract Item`
            WHERE
                contrato = %s
        """, (self.contrato,), as_dict = True)
        self.valoranterior = _total_before[0]['total_before'] if _total_before else 0.0
        self.valorreajustado = _total_after[0]['total_after'] if _total_after else 0.0

        # Atualiza o valor total do contrato
        set_adjustment(self.contrato)

    def on_cancel(self):
        for sap in self.tabsap:
            if sap.pedidolinha and sap.indicereajuste and sap.indicereajuste != 0:
                # Limpa os indices para os pedidos SAP
                clear_sap_order_line_adjustment(sap.pedidolinha)
                # Restaura os valores unitários dos itens do contrato
                clear_item_adjustment(sap.item, sap.pedidolinha, sap.valorunitario, self.name)
        # Restaura os valores retroativos dos itens da medição vinculadas ao contrato, se houver
        clear_measurement_adjustment(self.boletimmedicao)
        # Atualiza o valor total do contrato
        set_adjustment(self.contrato)        
    

@frappe.whitelist()
def get_sap_order_line(doctype, txt, searchfield, start, page_len, filters):
    """
    Busca linhas do pedido SAP específico
    """
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    contrato = filters.get('contrato', '')
    
    # Se não tiver pedido_sap, retorna vazio
    if not contrato:
        return []
    
    # Filtrar apenas linhas que não estão associadas a nenhum Contract Item Order e sem saldo de medição
    return frappe.db.sql("""
        SELECT DISTINCT
            child.name AS value,
            CONCAT(child.name,' - ',child.centrodecusto) AS label
        FROM 
            `tabSAP Order Period` child
            INNER JOIN `tabSAP Order` sorder ON child.parent = sorder.name
            LEFT JOIN `tabContract Item Order` cio_sorder ON cio_sorder.pedidosap = sorder.name
            LEFT JOIN `tabContract Item Order` cio_child ON cio_child.pedidolinha = child.name
        WHERE 
            cio_sorder.name IS NULL
            AND cio_child.name IS NULL
            AND CASE WHEN child.valormedido IS NULL THEN 0 ELSE child.valormedido END = 0                         
            AND child.contrato = %(contrato)s
            AND (child.name LIKE %(txt)s)
        ORDER BY 
            child.idx, child.name
        LIMIT %(start)s, %(page_len)s""", {
        'contrato': contrato,
        'txt': '%%%s%%' % txt,
        'start': int(start),
        'page_len': int(page_len)
    })

@frappe.whitelist()
def get_contract_items(contract):
    """
    Busca itens do contrato específico
    """
    
    # Se vazio, retorna vazio
    if not contract:
        return []
    
    return frappe.db.sql("""
		SELECT
			name,
			codigo,
			descricao,
            valorunitario
		FROM
			`tabContract Item`
		WHERE
			NOT is_group = 1
			AND contrato = %(contrato)s
		ORDER BY
			INET_ATON(SUBSTRING_INDEX(CONCAT(codigo,'.0.0.0.0.0.0.0.0'), '.', 8)) ASC""", {
        'contrato': contract
    }, as_dict=1)

@frappe.whitelist()
def get_contract_measurements(retroactivedate, contract):
    """
    Busca medições do contrato específico
    """
    
    # Se vazio, retorna vazio
    if not contract or not retroactivedate:
        return []
    
    measurements = frappe.db.sql("""
		SELECT
			name,
			datainicialmedicao,
            datafinalmedicao,
            workflow_state as status
		FROM
			`tabContract Measurement`
		WHERE
			workflow_state = 'Concluído'
			AND DATE(datafinalmedicao) >= DATE(%(retroactivedate)s)
            AND contrato = %(contrato)s
        """, {
        'retroactivedate': retroactivedate,
        'contrato': contract
    }, as_dict=1)

    return measurements

@frappe.whitelist()
def get_items_retroactive_values(retroactivedate, contract):
    """
    Busca medições do contrato específico
    """
    
    # Se vazio, retorna vazio
    if not contract:
        return []
    
    retroactive_values = frappe.db.sql("""
		SELECT
            ci.codigo,
			cmi.itemcontrato AS item,
			SUM(cmi.quantidademedida) AS quantidadetotal,
            SUM(cmi.valorpago) AS valortotal
		FROM
			`tabContract Measurement` cm
            INNER JOIN `tabContract Measurement Item` cmi ON cmi.parent = cm.name
            INNER JOIN `tabContract Item` ci ON ci.name = cmi.itemcontrato
		WHERE
            NOT cmi.valorpago = 0
			AND cm.workflow_state = 'Concluído'
			AND cm.datafinalmedicao >= %(retroactivedate)s
            AND cm.contrato = %(contrato)s
        GROUP BY
            ci.codigo,
            cmi.itemcontrato
        """, {
        'retroactivedate': retroactivedate,
        'contrato': contract
    }, as_dict=1)

    return retroactive_values