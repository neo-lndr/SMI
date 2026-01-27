
import frappe.utils
from frappe import throw, _
from frappe.utils import flt
import asyncio

def approve_measurement(doc):

    print("Aprovando medição...")

    msg = ""

    last_doc = frappe.get_last_doc("Contract Measurement", filters={"name": doc.name})
    if last_doc and last_doc.workflow_state == "Devolvido":
        msg = "Revisão de medição devolvida."

    total_tablepedidossap = 0.0
    pedidos_sap_sem_saldo = 0
    for s in doc.tablepedidossap:
        total_tablepedidossap += s.valormedido
        pedidos_sap_sem_saldo += 1 if s.saldo < 0 else 0

    total_tablemunicipios = 0.0
    for m in doc.tablemunicipios:
        total_tablemunicipios += m.valor

    total_tabitenscontatrato = 0.0
    for i in doc.tabitenscontatrato:
        total_tabitenscontatrato += i.valortotalmedido        

    if not (
        flt(total_tablepedidossap, 2) == 
        flt(total_tabitenscontatrato, 2) == 
        flt(total_tablemunicipios, 2) == 
        flt(doc.medicaoatual, 2)
    ) or pedidos_sap_sem_saldo > 0:
        message = '<p class="alert alert-danger">Não é possivel aprovar a medição!</p>'
        message +=  '<div class="alert alert-warning">Os valores de "Medição atual (A)", "Total pedidos SAP", "Total municípios" e "Total itens contratuais" estão divergentes, ou existem pedidos SAP sem saldo.</div>'
        throw(message)
        return

    doc_cms = doc.append("tabetapas")
    doc_cms.parent = doc.name
    doc_cms.parenttype = "Contract Measurement"
    doc_cms.dataehora = frappe.utils.now_datetime()
    doc_cms.usuario = frappe.session.user
    doc_cms.etapa = "Aprovado"
    doc_cms.observacao = msg

def send_measurement_to_sign(doc):

    doc_cms = doc.append("tabetapas")
    doc_cms.parent = doc.name
    doc_cms.parenttype = "Contract Measurement"
    doc_cms.dataehora = frappe.utils.now_datetime()
    doc_cms.usuario = frappe.session.user
    doc_cms.etapa = "Enviado para assinatura"
    doc_cms.observacao = f'Adobe Sign ID: {doc.idadobesign}'
    
def suspend_measurement_approvement(doc):
    
    doc_cms = doc.append("tabetapas")
    doc_cms.parent = doc.name
    doc_cms.parenttype = "Contract Measurement"
    doc_cms.dataehora = frappe.utils.now_datetime()
    doc_cms.usuario = frappe.session.user
    doc_cms.etapa = "Aberto"
    doc_cms.observacao = "Aberto após suspensão de aprovação."

def finish_measurement_approvement(measurement):

    doc = frappe.get_doc("Contract Measurement", measurement)

    doc.workflow_state = "Concluído"

    doc_cms = doc.append("tabetapas")
    doc_cms.parent = doc.name
    doc_cms.parenttype = "Contract Measurement"
    doc_cms.dataehora = frappe.utils.now_datetime()
    doc_cms.usuario = frappe.session.user
    doc_cms.etapa = "Concluído"
    doc_cms.observacao = "Todas as assinaturas coletadas."   

    doc.save(ignore_permissions=True)
    frappe.db.commit()

def return_measurement_to_draft(measurement, comment):

    doc = frappe.get_doc("Contract Measurement", measurement)

    doc.workflow_state = "Devolvido"

    doc_cms = doc.append("tabetapas")
    doc_cms.parent = doc.name
    doc_cms.parenttype = "Contract Measurement"
    doc_cms.dataehora = frappe.utils.now_datetime()
    doc_cms.usuario = frappe.session.user
    doc_cms.etapa = "Devolvido"
    doc_cms.observacao = comment 

    doc.save(ignore_permissions=True)
    frappe.db.commit()