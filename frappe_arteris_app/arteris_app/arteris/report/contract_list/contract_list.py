# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

import frappe
#from frappe import _


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	columns = get_columns()
	data = get_data()

	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [{'label': 'Nº do Contrato',
   'fieldtype': 'Data',
   'fieldname': 'contrato',
   'width': 150},
  {'label': 'Contratada',
   'fieldtype': 'Link',
   'fieldname': 'contratada',
   'width': 150,
   'options': 'Contracted Company'},
  {'label': 'Data inicial do contrato',
   'fieldtype': 'Date',
   'fieldname': 'datainicial',
   'width': 100},
  {'label': 'Data final do contrato',
   'fieldtype': 'Date',
   'fieldname': 'datafinal',
   'width': 100},
  {'label': 'Subsidiaria',
   'fieldtype': 'Link',
   'fieldname': 'subsidiaria',
   'width': 150,
   'options': 'Subsidiary'},
  {'label': 'Responsável',
   'fieldtype': 'Link',
   'fieldname': 'responsavel',
   'width': 150,
   'options': 'Person'},
  {'label': 'Obra', 'fieldtype': 'Data', 'fieldname': 'obra', 'width': 150},
  {'label': 'Objeto',
   'fieldtype': 'Small Text',
   'fieldname': 'descricao',
   'width': 200},
  {'label': 'Valor total do contrato',
   'fieldtype': 'Currency',
   'fieldname': 'valortotal',
   'width': 120},
  {'label': 'Vertical',
   'fieldtype': 'Link',
   'fieldname': 'vertical',
   'width': 150,
   'options': 'Vertical'},
  {'label': 'Categoria',
   'fieldtype': 'Link',
   'fieldname': 'categoria',
   'width': 150,
   'options': 'Category'},
  {'label': 'Início dos serviços conf. contrato',
   'fieldtype': 'Date',
   'fieldname': 'inicioservicosprevisto',
   'width': 100},
  {'label': 'Início real dos serviços',
   'fieldtype': 'Date',
   'fieldname': 'inicioservicos',
   'width': 100},
  {'label': 'Término serviços conf. contrato',
   'fieldtype': 'Date',
   'fieldname': 'terminoservicosprevisto',
   'width': 100},
  {'label': 'Término previsto dos serviços',
   'fieldtype': 'Date',
   'fieldname': 'terminoservicos',
   'width': 100},
  {'label': 'Medição mês cheio',
   'fieldtype': 'Check',
   'fieldname': 'medicaopormes',
   'width': 80},
  {'label': 'Dia inicial',
   'fieldtype': 'Int',
   'fieldname': 'medicaodiainicial',
   'width': 100},
  {'label': 'Dia final',
   'fieldtype': 'Int',
   'fieldname': 'medicaodiafinal',
   'width': 100},
  {'label': 'Percentual caução',
   'fieldtype': 'Float',
   'fieldname': 'percentualcalcao',
   'width': 120},
  {'label': 'Teto percentual caução',
   'fieldtype': 'Float',
   'fieldname': 'tetopercentualcalcao',
   'width': 120},
  {'label': 'Descrição da regra do caução',
   'fieldtype': 'Data',
   'fieldname': 'regracaucao',
   'width': 150},
  {'label': 'Data de inicio de medição pelo MSI',
   'fieldtype': 'Date',
   'fieldname': 'datainiciomedicao',
   'width': 100},
  {'label': 'Contrato encerrado em',
   'fieldtype': 'Datetime',
   'fieldname': 'contratoencerrado',
   'width': 150},
  {'label': 'Grupo',
   'fieldtype': 'Link',
   'fieldname': 'grupoformulas',
   'width': 150,
   'options': 'Formula Group'},
  {'label': 'Chave Kartado',
   'fieldtype': 'Data',
   'fieldname': 'uuidkartado',
   'width': 150},
  {'label': 'Chave Osiris',
   'fieldtype': 'Data',
   'fieldname': 'uuidosiris',
   'width': 150}]

def get_data() -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
	data = frappe.db.get_all(
		'Contract', 
		['contrato',
  'contratada',
  'datainicial',
  'datafinal',
  'subsidiaria',
  'responsavel',
  'obra',
  'descricao',
  'valortotal',
  'vertical',
  'categoria',
  'inicioservicosprevisto',
  'inicioservicos',
  'terminoservicosprevisto',
  'terminoservicos',
  'medicaopormes',
  'medicaodiainicial',
  'medicaodiafinal',
  'percentualcalcao',
  'tetopercentualcalcao',
  'regracaucao',
  'datainiciomedicao',
  'contratoencerrado',
  'grupoformulas',
  'uuidkartado',
  'uuidosiris'],
				order_by = "contrato ASC")

	return data

