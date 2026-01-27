# Copyright (c) 2025, Renoir and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import throw, _

class ContractMeasurementItemRemaining(Document):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._removed_childs = set()

	@frappe.whitelist()
	def check_has_measurement(self):
		"""
		Check if there is a measurement record associated with this item.
		"""

		contract = frappe.db.get_value(
			'Contract Measurement',
			{'name': self.boletimmedicao},
			'contrato'
		)

		open_measurement = frappe.db.exists('Contract Measurement', {'contrato': contract, 'medicaovigente': 'Sim'})


		return open_measurement

	@frappe.whitelist()
	def create_payment(self, percent: float, value: float, balance: float, observations: str):

		contract = frappe.db.get_value(
			'Contract Measurement',
			{'name': self.boletimmedicao},
			'contrato'
		)

		measurement = frappe.db.get_value('Contract Measurement', {'contrato': contract, 'medicaovigente': 'Sim'})
		measurement_doc = frappe.get_doc('Contract Measurement', measurement)

		self.append('tblpagamentos',{
			'boletimmedicao': measurement,
			'percentual': percent,
			'valor': value,
			'datahora': frappe.utils.now_datetime(),
			'observacoes': observations
		})		
		self.saldo = balance
		self.save(ignore_permissions=True)

		measurement_doc.append('tblsaldos',{
			'origem': self.name,
			'linhaorigem': self.tblpagamentos[-1].name,
			'boletimmedicao': self.boletimmedicao,
			'item': self.item,
			'saldo': self.saldo,
			'valorpago': value
		})
		measurement_doc.save(ignore_permissions=True)

		return True

	def before_save(self):
		"""Executado antes de salvar o documento"""
		
		# Verificar se o documento já existe (não é novo)
		if not self.is_new():
			# Buscar versão anterior do documento
			old_doc = frappe.get_doc(self.doctype, self.name)

			# Verificar se existe pagamento de origem
			chec_first = False
			for row in self.tblpagamentos:
				if row.origem:
					chec_first = True
					break
			if not chec_first:
				throw(_("Não é possivel remover o lançamento de pagamento de origem."))
				return False

			# Comparar child tables para detectar remoções
			if not self.check_removed_child(old_doc):
				throw(_("Não é possível remover itens de pagamento que estão vinculados a boletins de medição encerrados."))
				return False
			
		total = 0.0
		for row in self.tblpagamentos:
			if row.valor:
				total += flt(row.valor)
		self.valorpago = total
		self.saldo = self.valor - total

	def check_removed_child(self, old_doc): 
		"""Detecta itens removidos da child table"""

		# Pegar IDs dos itens atuais
		current_payment_ids = {}
		for row in self.tblpagamentos:
			if row.name:  # Só considerar itens já salvos
				current_payment_ids.setdefault(row.name, row.boletimmedicao)
		
		# Pegar IDs dos itens antigos
		old_payment_ids =  {}
		for row in old_doc.tblpagamentos:
			if row.name:
				old_payment_ids.setdefault(row.name, row.boletimmedicao)

		# Comparar IDs para encontrar itens removidos
		old_payment_set = set(old_payment_ids.keys())
		current_payment_set = set(current_payment_ids.keys())	

		# Encontrar itens removidos
		removed_ids = old_payment_set - current_payment_set

		for removed_id in removed_ids:

			# Check measurement is open
			measurement_open = frappe.db.get_value(
				'Contract Measurement',
				{'name': old_payment_ids[removed_id], 'medicaovigente': 'Sim'},
				'name'
			)

			if not measurement_open:
				return False

		self._removed_childs = removed_ids

		return True

	def on_update(self):

		for removed_id in self._removed_childs:
			frappe.db.sql("""
				DELETE FROM `tabContract Measurement Item Balance Payment`
				WHERE linhaorigem = %s
			""", (removed_id,))
			frappe.db.commit()

	@frappe.whitelist()
	def get_highways(self):
		"""
		Método adaptado para ser usado em campos Link
		Retorna rodovias associadas ao contrato no formato esperado pelo Frappe
		"""

		# Query para buscar rodovias associadas
		highways =frappe.db.sql("""
			SELECT 
				h.rodovia AS name,
				h.rodovia as display_name,
				h.kminicial,
				h.kmfinal
			FROM 
				`tabContract Measurement Item Remaining Highway` h
			WHERE  
				h.parent = %s 
			ORDER BY 
				h.name
		""", (self.name,), as_dict=True)

		highways_str = '/n'.join(f"{h.name}" for h in highways)

		return {'list': highways_str, 'count': len(highways), 'first': highways[0].name if highways else None}

	@frappe.whitelist()
	def check_highway(self, highway: str, kmstart: float, kmend: float):

		if not highway:
			return False
		
		# Check highway km range
		for h in self.tblrodovias:
			if h.rodovia == highway:
				if flt(kmstart) < flt(h.kminicial) or flt(kmend) > flt(h.kmfinal):
					return False
				return True

		return False