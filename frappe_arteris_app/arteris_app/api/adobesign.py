import frappe
import io
import img2pdf
import pypdf
import requests
import os
import json
import base64
from .measurement_workflow import finish_measurement_approvement, return_measurement_to_draft, send_measurement_to_sign
import asyncio
from playwright.async_api import async_playwright
from .attachment import upload_file
from frappe import throw, _

def send_measurement_to_adobesign(doc):

    # Gera o PDF do boletim de medição e envia para o AdobeSign
    resultado = asyncio.run(send_async_measurement_to_adobesign(doc.name))

    if not resultado:
        frappe.error_log(f"Erro desconhecido ao enviar medição {doc.name} para assinatura no AdobeSign", "AdobeSign")
        throw(_(f"Erro desconhecido ao enviar medição para assinatura. Detalhes no log de erros."))

    if not resultado.get("success"):
        message = '<p class="alert alert-danger">Erro ao enviar medição para assinatura!</p>'
        message += f'<div class="alert alert-warning">{json.dumps(resultado)}</div>'
        frappe.error_log(message)
        throw(_(f"Erro ao enviar medição para assinatura. Detalhes no log de erros."))
    else:
        # Armazena o ID do AdobeSign na medição
        doc.idadobesign = resultado.get("data").get("id")
        # Registra a etapa no fluxo da medição
        send_measurement_to_sign(doc)

    return {"success": True, "message": f'Medição {doc.name} enviada para assinatura no AdobeSign com sucesso.'}

async def test_playwright_connection(): 
    print("🔗 Conectando ao Playwright...")
    async with async_playwright() as p:
        # Conectar
        browser = await p.chromium.connect("ws://playwright:3000/")
        print("✅ Conectado!")
        
        context = await browser.new_context(
            ignore_https_errors=True 
        )        

        # Criar página
        page = await context.new_page()
        print("📄 Página criada!")
        
        # Testar internet
        await page.goto("https://smi.arteris.com.br/capa_boletim?id=BM-CW44149-001")
        await page.wait_for_load_state('networkidle')
        print("🌐 Página carregada!")
        
        # # Verificar conteúdo
        # content = await page.text_content("body")
        # if "origin" in content:
        #     print("✅ Internet OK!")
        
        # Screenshot
        bytes_image = await page.screenshot(full_page=True)
        # await page.screenshot(path="/tmp/test.png")
        # print("📸 Screenshot salvo em /tmp/test.png")
        
        # Limpar
        await context.close()
        await browser.close()
        print("🧹 Finalizado!")        

    return {"success": True, "message": "Playwright funcionando corretamente."}

async def send_async_measurement_to_adobesign(measurement):
    """
    Envia a medição para o AdobeSign
    """
    import requests
    import json

    try:

        # Recupera a URL base do sistema
        url = "https://smi.arteris.com.br/" # frappe.local.request.host_url
        
        # Recupera as configurações do AdobeSign
        adobe_settings = frappe.get_doc("SMI Config")
        adobe_token = adobe_settings.get_password('adobesign_token')

        # Recupera o fluxo de assinatura
        workflow_sign = frappe.db.sql("""
            SELECT
                cs.pessoa1,
                cs.pessoa2,
                cs.pessoa3,
                cs.pessoa4,
                cs.pessoa5,
                CASE WHEN cs.valormedicao IS NULL THEN 0 ELSE cs.valormedicao END AS valormedicao,
                CASE WHEN cm.medicaoatual IS NULL THEN 0 ELSE cm.medicaoatual END AS medicaoatual
            FROM `tabContract Signature` cs
                INNER JOIN `tabContract` c ON c.contrato = cs.name
                INNER JOIN `tabContract Measurement` cm ON cm.contrato = c.name
            WHERE 
                cm.name = %s
        """,
        (measurement, ),
        as_dict=True)

        if not workflow_sign:
            return {"success": False, "message": f'Fluxo de assinatura não encontrado para o contrato da medição {measurement}'}

        # Monta a lista de signatários do payload
        order_sign = 0
        signers = []
        w = workflow_sign[0]

        for i in range(1, 5):
            pessoa = w[f'pessoa{i}']
            if pessoa:
                order_sign += 1
                pessoa_email = frappe.db.get_value("Person", pessoa, "email")
                if pessoa_email:
                    signers.append(
                    {
                        "memberInfos": [
                            {
                                "email": pessoa_email
                            }
                        ],
                        "order": order_sign,
                        "name": f"Assinante 0{order_sign}",
                        "role": "SIGNER"
                    })
                else:
                    break

        # Se a medição atual for maior que o valor da medição, adiciona o signatário correspondente
        if (w['valormedicao'] > 0) and  (w['medicaoatual'] > w['valormedicao']):
            order_sign += 1
            if w['pessoa5']:
                pessoa_email = frappe.db.get_value("Person", w['pessoa5'], "email")
                if not pessoa_email:
                    return {"success": False, "message": f'Email da Pessoa 5 não encontrado para o contrato da medição {measurement}'}
                signers.append(
                    {
                        "memberInfos": [
                            {
                                "email": pessoa_email
                            }
                        ],
                        "order": order_sign,
                        "name": f"Assinante 0{order_sign}",
                        "role": "SIGNER"
                    }
                )
            else:
                return {"success": False, "message": f'Fluxo de assinatura inválido. Pessoa 5 não informada para o contrato da medição {measurement}'}

        # Upload do PDF do boletim de medição
        upload_response = await upload_measurement_to_adobesign(measurement, url, adobe_token)

        # Recupera o transientDocumentId do upload
        transient_document_id = upload_response['transientDocumentId']

        # Cabeçalhos
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {adobe_token}"
        }

        # Monta o payload para criar o acordo
        payload = {
            "fileInfos": [
                {
                    "transientDocumentId": transient_document_id,
                    "label": f"Boletim de Medição {measurement}"
                }
            ],
            "name": f"Boletim de Medição {measurement}",
            "participantSetsInfo": signers,
            "locale": "pt_BR",
            "signatureType": "ESIGN",
            "state": "IN_PROCESS"
        }

        url_adobe = "https://api.na4.adobesign.com/api/rest/v6/agreements"

        try:
            json_payload = json.dumps(payload)
            # Fazer a requisição POST
            response = requests.post(url_adobe, headers=headers, data=json_payload)

            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                return {"success": True, "data": json.loads(response.text)}
            else:
                frappe.log_error(f"Erro na requisição: {response.status_code}. Resposta: {response.text}", "AdobeSign")
                return {"success": False, "message": f"Erro ao enviar medição para AdobeSign. Erro na requisição:\n{response.text}"}
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro durante a requisição: {e}", "AdobeSign")
            return {"success": False, "message": f"Erro ao enviar medição para AdobeSign. Erro durante a requisição:\n {e}"}


    except Exception as e:
        frappe.log_error(f"Erro ao recuperar o fluxo de assinatura para a medição {measurement}: {e}", "AdobeSign")
        return {"success": False, "message": f"Erro ao recuperar o fluxo de assinatura para a medição {measurement}."}

async def upload_measurement_to_adobesign(measurement: str, url: str, adobe_token: str) -> dict:

    try:
        
        # Cria o PDF do boletim de medição
        pdf_bytes = await create_measurement_pdf(measurement, url)
        if not pdf_bytes['success']:
            return {"success": False, "message": f"Erro ao criar PDF da medição:\n{pdf_bytes['message']}"}

        # pdf_64 = base64.b64encode(pdf_bytes['data']).decode('utf-8')
        # upload_file(file_64=pdf_64, file_name=f'BM-{measurement}.pdf')

        # URL do AdobeSign
        url_adobe = 'https://api.na4.adobesign.com/api/rest/v6/transientDocuments'

        # Cabeçalhos
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {adobe_token}'
        }

        # Nome do arquivo
        file_name = f'{measurement}.pdf'

        # Preparar os dados do formulário multipart
        files = {
            'File': (file_name, io.BytesIO(pdf_bytes['data']), 'application/pdf')
        }        
        data = {
            'Mime-Type': 'application/pdf',
            'File-Name': file_name
        }

        try:

            # Fazer a requisição POST
            response = requests.post(url_adobe, headers=headers, files=files, data=data)
                        
            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                print("Upload realizado com sucesso!")
                print("Resposta:", response.content)
                return json.loads(response.text)
            else:
                print(f"Erro na requisição: {response.status_code}")
                print("Resposta:", response.text)
                throw(f"Erro ao enviar medição para AdobeSign. Erro na requisição:\n{response.text}")
                
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro na requisição para AdobeSign: {e}", "AdobeSign")
            throw(e)

    except Exception as e:
        frappe.log_error(f"Erro ao enviar medição {measurement} para AdobeSign: {e}", "AdobeSign")
        throw(e)

async def create_measurement_screenshot(url: str) -> bytearray:
    """
    Cria o screenshot da capa do boletim de medição usando Playwright
    """

    try:

        # url = "https://msi.arteris.com.br/capa_boletim?id=BM-CW44149-001"

        browsers_path = frappe.get_doc("SMI Config")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path.pwpath

        if 'development' in url:
            url = url.replace("http://development.localhost:8000", "https://smi.arteris.com.br")

        # browser = await p.chromium.launch(
        #     headless=True,
        #     args=[
        #         '--no-sandbox',                    # Essencial para containers
        #         '--disable-setuid-sandbox',        # Segurança para containers
        #         '--disable-gpu'                    # GPU não disponível em containers                
        #     ]
        # )

        async with async_playwright() as p:
            browser = await p.chromium.connect("ws://playwright:3000/")
            context = await browser.new_context(
                ignore_https_errors=True 
            )        
            page = await context.new_page()
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            bytes_image = await page.screenshot(full_page=True)
            await browser.close()
            return bytes_image

    except Exception as e:
        frappe.log_error(f"Erro ao tentar gerar o screenshot da url {url}: {str(e)}", "AdobeSign")
        throw(e)

async def create_measurement_pdf(measurement: str, url: str) -> dict:
    """
    Cria o boletim de medição em PDF usando Playwright e img2pdf
    """

    try:
        
        # Screenshot da capa
        url_cover = f"{url}capa_boletim?id={measurement}"
        bytes_cover_image = await create_measurement_screenshot(url_cover)

        # Screenshot das cidades
        url_cities = f"{url}cidades_medicao?id={measurement}"
        bytes_cities_image = await create_measurement_screenshot(url_cities)

        # Screenshot do boletim
        url_measurement = f"{url}boletim_medicao_fixo?id={measurement}"
        bytes_measurement_image = await create_measurement_screenshot(url_measurement)

        # Screenshot das imagens
        # url_pictures = f"{url}imagens?id={measurement}"
        # bytes_pictures_image = await create_measurement_screenshot(url_pictures)

        # Converte as imagens para PDF
        pdf_cover = img2pdf.convert(bytes_cover_image)
        pdf_cities = img2pdf.convert(bytes_cities_image)
        pdf_measurement = img2pdf.convert(bytes_measurement_image)
        # pdf_pictures = img2pdf.convert(bytes_pictures_image)

        # Mescla os PDFs
        pdfMerge = pypdf.PdfWriter()
        pdfMerge.append(io.BytesIO(pdf_cover))
        pdfMerge.append(io.BytesIO(pdf_cities))
        pdfMerge.append(io.BytesIO(pdf_measurement))
        # pdfMerge.append(io.BytesIO(pdf_pictures))

        # Salva o PDF em um buffer de bytes
        output_buffer = io.BytesIO()
        pdfMerge.write(output_buffer)

        # Obtém os bytes do PDF mesclado
        merged_pdf_bytes = output_buffer.getvalue()

        # Fecha os objetos
        pdfMerge.close()

    except Exception as e:
        frappe.log_error(f"Erro ao criar PDF da medição {measurement}: {e}", "AdobeSign")
        throw(e)
    
    return {"success": True, "message": "", "data": merged_pdf_bytes}
        
def get_adobesign_agreement_events(agreement_id: str) -> dict:
    """
    Recupera os eventos do acordo no AdobeSign
    """

    try:        
        # Recupera as configurações do AdobeSign
        adobe_settings = frappe.get_doc("SMI Config")
        adobe_token = adobe_settings.get_password('adobesign_token')

        # URL do AdobeSign
        url_adobe = f'https://api.na4.adobesign.com/api/rest/v6/agreements/{agreement_id}/events'

        # Cabeçalhos
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {adobe_token}'
        }

        try:

            # # Faz a requisição dos eventos
            # response = requests.get(f'{url_adobe}/events', headers=headers)

            # Fazer a requisição GET
            response = requests.get(url_adobe, headers=headers)
                        
            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                print("Requisição realizada com sucesso!")
                print("Resposta:", response.content)
                response_json = json.loads(response.text)

                # Se utilizado o botão, a chamada do método para concluir a medição é executada no frontend
                # finish_measurement_approvement
                return {"success": True, "data": response_json}
            else:
                print(f"Erro na requisição: {response.status_code}")
                print("Resposta:", response.text)
                return {"success": False, "message": f"Erro ao recuperar eventos do acordo no AdobeSign. Erro na requisição:\n{response.text}"}
                
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro na requisição para AdobeSign: {e}", "AdobeSign")
            return {"success": False, "message": f"Erro ao recuperar eventos da assinatura no AdobeSign. Erro durante a requisição:\n {e}"}

    except Exception as e:
        frappe.log_error(f"Erro ao recuperar eventos do acordo {agreement_id} no AdobeSign: {e}", "AdobeSign")
        return {"success": False, "message": f"Erro ao recuperar eventos da assinatura {agreement_id} no AdobeSign."}
    
def get_adobesign_agreement_audittrail(agreement_id: str) -> dict:
    """
    Recupera o histórico de auditoria do acordo no AdobeSign
    """

    try:        
        # Recupera as configurações do AdobeSign
        adobe_settings = frappe.get_doc("SMI Config")
        adobe_token = adobe_settings.get_password('adobesign_token')

        # URL do AdobeSign
        url_adobe = f'https://api.na4.adobesign.com/api/rest/v6/agreements/{agreement_id}/auditTrail'

        # Cabeçalhos
        headers = {
            'accept': 'application/pdf',
            'Authorization': f'Bearer {adobe_token}'
        }

        try:

            # # Faz a requisição do histórico de auditoria
            # response = requests.get(f'{url_adobe}/events', headers=headers)

            # Fazer a requisição GET
            response = requests.get(url_adobe, headers=headers)
                        
            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                print("Requisição realizada com sucesso!")
                print("Resposta:", response.content)
                data64 = base64.b64encode(response.content).decode('utf-8')

                # Se utilizado o botão, a chamada do método para concluir a medição é executada no frontend
                # finish_measurement_approvement
                return {"success": True, "data": data64}
            else:
                print(f"Erro na requisição: {response.status_code}")
                print("Resposta:", response.text)
                return {"success": False, "message": f"Erro ao recuperar histórico de auditoria do acordo no AdobeSign. Erro na requisição:\n{response.text}"}
                
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro na requisição para AdobeSign: {e}", "AdobeSign")
            return {"success": False, "message": f"Erro ao recuperar histórico de auditoria da assinatura no AdobeSign. Erro durante a requisição:\n {e}"}

    except Exception as e:
        frappe.log_error(f"Erro ao recuperar histórico de auditoria do acordo {agreement_id} no AdobeSign: {e}", "AdobeSign")
        return {"success": False, "message": f"Erro ao recuperar histórico de auditoria da assinatura {agreement_id} no AdobeSign."}

def get_adobesign_agreement_documents(agreement_id: str) -> dict:
    """
    Recupera os documentos do acordo no AdobeSign
    """

    try:        
        # Recupera as configurações do AdobeSign
        adobe_settings = frappe.get_doc("SMI Config")
        adobe_token = adobe_settings.get_password('adobesign_token')

        # URL do AdobeSign
        url_adobe = f'https://api.na4.adobesign.com/api/rest/v6/agreements/{agreement_id}/documents'

        # Cabeçalhos
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {adobe_token}'
        }

        try:

            # # Faz a requisição dos documentos 
            # response = requests.get(f'{url_adobe}/events', headers=headers)

            # Fazer a requisição GET
            response = requests.get(url_adobe, headers=headers)
                        
            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                print("Requisição realizada com sucesso!")
                print("Resposta:", response.content)
                response_json = json.loads(response.text)

                # Se utilizado o botão, a chamada do método para concluir a medição é executada no frontend
                # finish_measurement_approvement
                return {"success": True, "data": response_json}
            else:
                print(f"Erro na requisição: {response.status_code}")
                print("Resposta:", response.text)
                return {"success": False, "message": f"Erro ao recuperar documentos AdobeSign. Erro na requisição:\n{response.text}"}
                
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro na requisição para AdobeSign: {e}", "AdobeSign")
            return {"success": False, "message": f"Erro ao recuperar documentos da assinatura no AdobeSign. Erro durante a requisição:\n {e}"}

    except Exception as e:
        frappe.log_error(f"Erro ao recuperar documentos {agreement_id} no AdobeSign: {e}", "AdobeSign")
        return {"success": False, "message": f"Erro ao recuperar documentos da assinatura {agreement_id} no AdobeSign."}

def get_adobesign_agreement_document(agreement_id: str, doc_id: str) -> dict:
    """
    Recupera o documento no AdobeSign
    """

    try:        
        # Recupera as configurações do AdobeSign
        adobe_settings = frappe.get_doc("SMI Config")
        adobe_token = adobe_settings.get_password('adobesign_token')

        # URL do AdobeSign
        url_adobe = f'https://api.na4.adobesign.com/api/rest/v6/agreements/{agreement_id}/documents/{doc_id}'

        # Cabeçalhos
        headers = {
            'accept': 'application/pdf',
            'Authorization': f'Bearer {adobe_token}'
        }

        try:

            # # Faz a requisição dos documentos 
            # response = requests.get(f'{url_adobe}/events', headers=headers)

            # Fazer a requisição GET
            response = requests.get(url_adobe, headers=headers)
                        
            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                print("Requisição realizada com sucesso!")
                print("Resposta:", response.content)
                data64 = base64.b64encode(response.content).decode('utf-8')

                # Se utilizado o botão, a chamada do método para concluir a medição é executada no frontend
                # finish_measurement_approvement
                return {"success": True, "data": data64}
            else:
                print(f"Erro na requisição: {response.status_code}")
                print("Resposta:", response.text)
                return {"success": False, "message": f"Erro ao recuperar documento AdobeSign. Erro na requisição:\n{response.text}"}
                
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro na requisição para AdobeSign: {e}", "AdobeSign")
            return {"success": False, "message": f"Erro ao recuperar documento no AdobeSign. Erro durante a requisição:\n {e}"}

    except Exception as e:
        frappe.log_error(f"Erro ao recuperar documento {agreement_id} no AdobeSign: {e}", "AdobeSign")
        return {"success": False, "message": f"Erro ao recuperar documento da assinatura {agreement_id} no AdobeSign."}

@frappe.whitelist(methods=["POST"])
def get_adobesign_agreement_status(agreement_id: str, measurement: str) -> dict:
    """
    Recupera o status do acordo no AdobeSign
    """

    try:        
        # Recupera as configurações do AdobeSign
        adobe_settings = frappe.get_doc("SMI Config")
        adobe_token = adobe_settings.get_password('adobesign_token')

        # URL do AdobeSign
        url_adobe = f'https://api.na4.adobesign.com/api/rest/v6/agreements/{agreement_id}'

        # Cabeçalhos
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {adobe_token}'
        }

        try:

            # Fazer a requisição GET
            response = requests.get(url_adobe, headers=headers)
                        
            # Verificar se a requisição foi bem-sucedida
            if (response.status_code == 200 or 
                response.status_code == 201):
                print("Requisição realizada com sucesso!")
                print("Resposta:", response.content)
                response_json = json.loads(response.text)

                comment = ""

                # Atualiza o status da medição conforme o status do AdobeSign
                # Se o status for SIGNED, conclui a medição
                if response_json.get("status") == "SIGNED":
                    # Recupera o histórico de auditoria
                    audit_json = get_adobesign_agreement_audittrail(agreement_id)
                    if audit_json:
                        upload_file(
                            doctype="Contract Measurement", 
                            record_name=measurement, 
                            file_64=audit_json.get('data'), 
                            file_name=f'Historico-{agreement_id}.pdf'
                        )
                    # Recupera os documentos assinados
                    docs_json = get_adobesign_agreement_documents(agreement_id)
                    if docs_json:
                        doc_id = docs_json.get('data').get('documents')[0].get('id')
                        # Recupera o documento assinado
                        doc_json = get_adobesign_agreement_document(agreement_id, doc_id)
                        if doc_json:
                            upload_file(
                                doctype="Contract Measurement", 
                                record_name=measurement, 
                                file_64=doc_json.get('data'), 
                                file_name=f'BM-{agreement_id}.pdf'
                            )
                    # Finaliza a medição
                    finish_measurement_approvement(measurement)

                # Se o status for CANCELLED, adiciona um comentário com o motivo do cancelamento
                if response_json.get("status") == "CANCELLED":
                    # Recupera os eventos do acordo para identificar o motivo do cancelamento
                    cancelled_json = get_adobesign_agreement_events(agreement_id)
                    if cancelled_json:
                        last_event = cancelled_json.get('data').get('events')[-1]
                        comment = f"Fluxo de assinatura cancelado por {last_event.get('actingUserName')} ({last_event.get('actingUserEmail')}) em {last_event.get('date')}. Motivo: {last_event.get('comment')}"
                    # Recupera o histórico de auditoria
                    audit_json = get_adobesign_agreement_audittrail(agreement_id)
                    if audit_json:
                        upload_file(
                            doctype="Contract Measurement", 
                            record_name=measurement, 
                            file_64=audit_json.get('data'), 
                            file_name=f'Historico-{agreement_id}.pdf'
                        )
                    return_measurement_to_draft(measurement, comment)

                return {"success": True, "data": response_json, "comment": comment}
            
            else:
                print(f"Erro na requisição: {response.status_code}")
                print("Resposta:", response.text)
                return {"success": False, "message": f"Erro ao recuperar status do acordo no AdobeSign. Erro na requisição:\n{response.text}"}
                
                
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Erro na requisição para AdobeSign: {e}", "AdobeSign")
            return {"success": False, "message": f"Erro ao recuperar status da assinatura no AdobeSign. Erro durante a requisição:\n {e}"}

    except Exception as e:
        frappe.log_error(f"Erro ao recuperar status do acordo {agreement_id} no AdobeSign: {e}", "AdobeSign")
        return {"success": False, "message": f"Erro ao recuperar status da assinatura {agreement_id} no AdobeSign."}

@frappe.whitelist(methods=["POST"])
def check_agreement_status() -> dict:
    """
    Verifica o status do acordo no AdobeSign
    """

    agreements = frappe.db.sql("""
        SELECT
            name,
            idadobesign
        FROM 
            `tabContract Measurement`
        WHERE
            idadobesign IS NOT NULL AND
            workflow_state = 'Enviado para assinatura'""", 
    as_dict=True)
    for agreement in agreements:
        agreement_id = agreement.get("idadobesign")
        measurement = agreement.get("name")
        get_adobesign_agreement_status(agreement_id, measurement)