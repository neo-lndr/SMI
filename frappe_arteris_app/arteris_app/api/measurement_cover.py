import frappe
import re
from frappe.utils.pdf import get_pdf
import base64
import requests

@frappe.whitelist(methods=['GET'])
def get_bm_cover_pdf(measurement: str) -> dict:
    m = get_measurement(measurement)
    html_content = frappe.render_template("www/capa_boletim.html", {
        "contract_measurement_json": frappe.as_json(m.get('contract_measurement', {})),
        "contract_json": frappe.as_json(m.get('contract', {})),
        "concessionaria_json": frappe.as_json(m.get('concessionaria', {})),
        "contracted_company_json": frappe.as_json(m.get('contracted_company', {})),
        "pedidos_sap_json": frappe.as_json(m.get('pedidos_sap', [])),
        "pedidos_sap_totais_json": frappe.as_json(m.get('pedidos_sap_totais ', {}))
    })

    with open("html_teste.html", "w") as f:
        f.write(html_content)  

    # html_content = adjust_html_content(html_content, m)

    # Opções específicas para wkhtmltopdf
    options = {
        'page-size': 'A4',
        'orientation': 'Portrait',
        'margin-top': '0.5in',
        'margin-right': '0.5in',
        'margin-bottom': '0.5in',
        'margin-left': '0.5in',
        'encoding': "UTF-8",
        'no-outline': None,
        'print-media-type': None,
        'disable-smart-shrinking': None,
        'javascript-delay': 30,  # Aguardar JavaScript
        'load-error-handling': 'ignore',
        'load-media-error-handling': 'ignore',
        'disable-external-links': None,
        'enable-local-file-access': None
    }

    # Gerar PDF
    # pdf_bytes = get_pdf(html_content, options)
    pdf_result = get_pdf(html_content)
    if hasattr(pdf_result, 'write'):
        # Se for um PdfWriter, obter os bytes
        import io
        buf = io.BytesIO()
        pdf_result.write(buf)
        pdf_bytes = buf.getvalue()
    else:
        pdf_bytes = pdf_result

    encoded = base64.b64encode(pdf_bytes).decode('utf-8')
    return encoded
    
def adjust_html_content(html_content, data):
    """Corrige problemas no HTML que podem causar falha no wkhtmltopdf"""
    # 1. Corrigir erro de sintaxe do JavaScript
    html_content = html_content.replace(
        'medicaoatualdescontoftd: contract_measurement,medicaoatualdescontoftd,',
        'medicaoatualdescontoftd: contract_measurement.medicaoatualdescontoftd,'
    )
    
    # 2. Substituir o CDN do jQuery por uma versão local ou incorporada
    html_content = html_content.replace(
        '<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>',
        '''<script>
        // Substituição mínima do jQuery para PDF
        window.$ = window.jQuery = function(selector) {
            return {
                text: function(value) {
                    if (value !== undefined) {
                        const el = document.querySelector(selector);
                        if (el) el.textContent = value;
                        return this;
                    }
                },
                attr: function(name, value) {
                    const el = document.querySelector(selector);
                    if (el && value !== undefined) {
                        el.setAttribute(name, value);
                    }
                    return this;
                },
                replaceWith: function(html) {
                    const el = document.querySelector(selector);
                    if (el) el.outerHTML = html;
                    return this;
                }
            };
        };
        $.each = function(array, callback) {
            if (Array.isArray(array)) {
                array.forEach(callback);
            }
        };
        </script>'''
    )
    
    # 3. Substituir imagens externas por um placeholder ou removê-las
    html_content = html_content.replace(
        'https://www.arteris.com.br/static/icons/arteris-logo.dc5c9168a8a3.svg',
        'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjUwIiB2aWV3Qm94PSIwIDAgMTAwIDUwIiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgo8cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjUwIiBmaWxsPSIjRkZGRkZGIi8+Cjx0ZXh0IHg9IjUwIiB5PSIyNSIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSIjMzMzMzMzIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+TG9nbzwvdGV4dD4KPHN2Zz4K'
    )
    
    # 4. Adicionar dados diretamente no JavaScript, se necessário
    contract_measurement = data.get('contract_measurement', {})
    if contract_measurement:
        # Adicionar script para pré-carregar dados críticos no PDF
        script_dados = f'''
        <script>
        // Dados pré-carregados para o PDF
        window.dadosPDF = {{
            concessionaria: '{data.get("concessionaria", {}).get("nome", "")}',
            obra: '{contract_measurement.get("obra", "")}',
            contrato: '{data.get("contract", {}).get("contrato", "")}',
            faseMedicao: '{contract_measurement.get("faseMedicao", "")}',
            fornecedor_razaosocial: '{data.get("contracted_company", {}).get("razaosocial", "")}',
            fornecedor_cnpj: '{data.get("contracted_company", {}).get("cnpj", "")}',
            fornecedor_endereco: '{data.get("contracted_company", {}).get("endereco", "")}'
        }};
        
        // Aplicar dados imediatamente
        document.addEventListener('DOMContentLoaded', function() {{
            if (window.dadosPDF) {{
                Object.keys(window.dadosPDF).forEach(function(key) {{
                    const el = document.getElementById(key);
                    if (el) el.textContent = window.dadosPDF[key];
                }});
            }}
        }});
        </script>
        '''
        html_content = html_content.replace('</head>', script_dados + '</head>')
    
    return html_content

def get_measurement(measurement):

    contract_measurement_json = None
    contract_json = None
    concessionaria_json = None
    contracted_company_json = None
    pedidos_sap_json = None
    pedidos_sap_totais_json = None
    saldos_json = None
    saldos_pagos_json = None

    doc_id = measurement
    if doc_id:
        try:      

            # Dados da medição
            doc = frappe.get_doc('Contract Measurement', doc_id)
            contract_measurement_json = frappe.as_json(doc.as_dict())

            # Dados do contrato
            contract = frappe.get_doc('Contract', doc.contrato)
            contract_json = frappe.as_json(contract.as_dict())

            # Dados da concessionaria
            concessionaria = frappe.get_doc('Subsidiary', contract.subsidiaria)
            concessionaria_json = frappe.as_json(concessionaria.as_dict())

            # Dados da contratada
            contractedCompany = frappe.get_doc('Contracted Company', doc.contratada)
            contracted_company_json = frappe.as_json(contractedCompany.as_dict())

            # Dados de pedidos SAP
            pedidosSap = frappe.db.sql("""
                SELECT
                    so.numeropedido,
                    cmso.linhapedido,
                    so.capexopex,
                    CASE WHEN so.capexopex='Capex' THEN sop.pep ELSE sop.centrodecusto END AS centrodecusto ,
                    '' AS tipo,
                    cmso.valortotalvigente,
                    cmso.medicaoacumantpercentual,
                    cmso.medicaoatualpercentual,
                    cmso.medicaoacumuladaatualpercentual,
                    cmso.acumuladoanterior,
                    cmso.acumuladoatual,
                    cmso.valormedido
                FROM
                    `tabContract Measurement SAP Order` AS cmso
                    INNER JOIN `tabSAP Order` AS so ON cmso.pedido_sap = so.name
                    INNER JOIN `tabSAP Order Period` AS sop ON cmso.linhapedido = sop.name
                WHERE
                    cmso.parent = %s
            """, (doc_id,), as_dict=True)

            pedidos_sap_totais = {
                'valortotalvigente': 0,
                'medicaoacumantpercentual': 0,
                'medicaoatualpercentual': 0,
                'medicaoacumuladaatualpercentual': 0,
                'acumuladoanterior': 0,
                'acumuladoatual': 0,
                'valormedido': 0
            }
            for pedido in pedidosSap:
                pedidos_sap_totais['valortotalvigente'] += pedido.valortotalvigente or 0
                pedidos_sap_totais['medicaoacumantpercentual'] += pedido.medicaoacumantpercentual or 0
                pedidos_sap_totais['medicaoatualpercentual'] += pedido.medicaoatualpercentual or 0
                pedidos_sap_totais['medicaoacumuladaatualpercentual'] += pedido.medicaoacumuladaatualpercentual or 0
                pedidos_sap_totais['acumuladoanterior'] += pedido.acumuladoanterior or 0
                pedidos_sap_totais['acumuladoatual'] += pedido.acumuladoatual or 0
                pedidos_sap_totais['valormedido'] += pedido.valormedido or 0

            pedidos_sap_totais_json = frappe.as_json(pedidos_sap_totais)
            pedidos_sap_json = frappe.as_json(pedidosSap)

            # Saldos do contrato
            saldos = frappe.db.sql("""
                SELECT
                    cmir.boletimmedicao,
                    CONCAT(ci.codigo, ci.descricao) AS item,
                    cmir.saldo
                FROM
                    `tabContract Measurement Item Remaining` AS cmir
                    INNER JOIN `tabContract Item` ci ON cmir.item = ci.name
                WHERE
                    cmir.contrato = %s"""
                , (doc.contrato,), as_dict=True)
            saldos_json = frappe.as_json(saldos)

            # Saldos pagos do contrato
            saldos_pagos = frappe.db.sql("""
                SELECT
                    cmibp.boletimmedicao,
                    CONCAT(ci.codigo, ci.descricao) AS item,
                    cmibp.saldo,
                    cmibp.valorpago
                FROM
                    `tabContract Measurement Item Balance Payment` AS cmibp
                    INNER JOIN `tabContract Item` ci ON cmibp.item = ci.name
                WHERE
                    cmibp.parent = %s"""
                , (doc_id,), as_dict=True)
            saldos_pagos_json = frappe.as_json(saldos_pagos)

        except frappe.DoesNotExistError:
            frappe.throw(_("Contract Measurement not found"), frappe.DoesNotExistError)
    else:
        frappe.throw(_("No id provided in URL"), frappe.DoesNotExistError)
    
    return {
        "contract_measurement": contract_measurement_json,
        "contract": contract_json,
        "concessionaria": concessionaria_json,
        "contracted_company": contracted_company_json,
        "pedidos_sap": pedidos_sap_json,
        "pedidos_sap_totais": pedidos_sap_totais_json,
        "saldos": saldos_json,
        "saldos_pagos": saldos_pagos_json
    }

@frappe.whitelist(methods=['GET'])
def get_cities(measurement):
    cities = frappe.db.sql("""
        SELECT
            cmc.municipio,
            cmc.valor
        FROM
            `tabContract Measurement City` cmc
        WHERE
            cmc.parent = %s
    """, (measurement,), as_dict=True)
    return cities

@frappe.whitelist(methods=['GET'])
def get_sap_orders(measurement):
    saporders = frappe.db.sql("""
        SELECT
            cmsoc.municipio,
            cmsoc.linhapedido,
            cmsoc.valor
        FROM
            `tabContract Measurement SAP Order City` cmsoc
        WHERE
            cmsoc.parent = %s
    """, (measurement,), as_dict=True)
    return saporders

def flatten_sap_order(json_data):
    """
    Achata os dados do pedido SAP combinando o cabeçalho com os dados do período.
    
    Args:
        json_data: Dicionário contendo os dados do pedido SAP
        
    Returns:
        Lista de dicionários achatados combinando o cabeçalho e os dados do período
    """
    # Verificar se json_data é um dicionário
    if not isinstance(json_data, dict):
        print(f"Erro: Esperado dicionário mas recebeu {type(json_data)}")
        return []

    # Obter o dicionário de dados com segurança
    data = json_data
    if not data:
        print("Aviso: Nenhuma chave 'data' encontrada em json_data")
        return []

    # Criar uma cópia dos dados do cabeçalho
    header = data.copy()
    
    # Remover de forma segura os arrays aninhados do cabeçalho
    periods = header.pop('table_dscc', [])
    header.pop('table_nqgi', [])  # Remover, mas não armazenar
    
    # Criar array achatado
    flattened = []
    
    # Se nenhum período for encontrado, retorne os dados do cabeçalho
    if not periods:
        print("Aviso: Nenhum período encontrado em table_dscc")
        return [header]
    
    try:
        for period in periods:
            # Combinar os dados do cabeçalho com cada período
            combined_item = {**header, **period}
            flattened.append(combined_item)
    except Exception as e:
        print(f"Erro ao processar períodos: {str(e)}")
        return [header]
    
    return flattened