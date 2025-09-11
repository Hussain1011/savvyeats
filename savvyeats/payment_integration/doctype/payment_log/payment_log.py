import frappe
from frappe import _
from frappe.utils import getdate, flt
from frappe.model.document import Document

class PaymentLog(Document):
	def validate(self):
		self.set_title()

	def set_title(self):
		self.title = _('{0} / {1}').format(self.document_type, self.reference_doc)
	

	# def send_notification(self):
	# 	client = frappe.get_doc('Client', self.client_id)
	# 	msg = "Dear valued guest, The payment of "+self.auth_amount+" is under process. Please wait for the amount to be reflected on your account. Thank you."
	# 	receiver_list='"'+str(client.mobile_no)+'"'
	# 	send_sms(receiver_list,msg)

	# 	if client.fcm_token:
	# 		title = "Payment under process"
	# 		send_push(self.client_id,title,msg)

	# def save_card(self):
	# 	doc = frappe.get_doc({
	# 		'doctype': 'Card Token',
	# 		'client_id': self.client_id,
	# 		'card_first_name': self.req_bill_to_forename,
	# 		'card_last_name': self.req_bill_to_surname,
	# 		'card_type' : self.card_type,
	# 		'card_type_name': self.card_type_name,
	# 		'last_4_digits_of_card': self.req_card_number,
	# 		'card_expiry_date' : self.req_card_expiry_date,
	# 		'payment_token': self.req_payment_token
	# 	})
	# 	doc.save()
	# 	frappe.db.set_value('Payment Log', self.name, 'payment_updated', 1)
	# 	frappe.db.commit()

	# 	client = frappe.get_doc('Client', self.client_id)
	# 	if client.fcm_token:
	# 		title = "Card saved"
	# 		msg = "Dear valued guest, a new card has been saved under your account. Thank you."
	# 		send_push(client.name,title,msg)

# # Cron job action to update payments 
# @frappe.whitelist()
# def update_payments():
# 	today = getdate()

# 	payment_list = frappe.get_all('Payment Log', filters={'date_time': today, 'payment_updated': 0})
# 	for payment in payment_list:
# 		payment_log = frappe.get_doc('Payment Log', payment.name)

# 		if payment_log.payment_log_type == "Credit Card":
# 			if payment_log.document_type == "Cart":
# 				doc = frappe.get_doc("Cart", payment_log.reference_doc)
# 				if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 						doc.append('payment_table', {
# 							"payment_date": today,
# 							"mode_of_payment": "Online Payment",
# 							"paid_amount": float(payment_log.auth_amount),
# 							"transaction_reference": payment_log.transaction_id
# 						})

# 						doc.save(ignore_permissions=True)
# 						doc.submit()
# 				else:
# 					if doc.online:
# 						frappe.db.set_value('Cart', payment_log.reference_doc, 'docstatus', 2)
# 						frappe.db.set_value('Cart', payment_log.reference_doc, 'payment_status', 'Cancelled')
# 						frappe.db.commit()
					
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()
# 			elif payment_log.document_type == "Gift Voucher":
# 				doc = frappe.get_doc("Gift Voucher", payment_log.reference_doc)
# 				if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 						doc.append('payment_table', {
# 							"payment_date": today,
# 							"mode_of_payment": "Online Payment",
# 							"paid_amount": float(payment_log.auth_amount),
# 							"transaction_reference": payment_log.transaction_id
# 						})
# 						doc.voucher_status = "Active"
# 						doc.save(ignore_permissions=True)
# 						doc.submit()
# 				else:
# 					if doc.online:
# 						frappe.db.set_value('Gift Voucher', payment_log.reference_doc, 'docstatus', 2)
# 						frappe.db.set_value('Gift Voucher', payment_log.reference_doc, 'payment_status', 'Not Paid')
# 						frappe.db.commit()						
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()
# 			elif payment_log.document_type == "Wallet Transaction":
# 				doc = frappe.get_doc("Wallet Transaction", payment_log.reference_doc)
# 				if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 					doc.transaction_reference = payment_log.name
# 					doc.save(ignore_permissions=True)
# 					doc.submit()

# 					wallet_topup(doc, doc.client_id)
# 				else:
# 					if doc.online:
# 						frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'docstatus', 2)
# 						frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'transaction_status', 'Cancelled')
# 						frappe.db.commit()
				
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()

# 			elif payment_log.document_type == "Food Order Entry":
# 				doc = frappe.get_doc("Food Order Entry", payment_log.reference_doc)
# 				if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 					doc.append('payment_table', {
# 						"payment_date": today,
# 						"mode_of_payment": "Online Payment",
# 						"paid_amount": float(payment_log.auth_amount),
# 						"transaction_reference": payment_log.transaction_id
# 					})
# 					# doc.order_status = "Ordered"
# 					# doc.payment_status = "Paid"
# 					doc.save(ignore_permissions=True)
# 					doc.submit()
# 				else:
# 					frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'docstatus', 2)
# 					frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'order_status', 'Cancelled')
# 					frappe.db.commit()

# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()

# 		elif payment_log.payment_log_type == "Debit Card":
# 			if payment_log.document_type == "Wallet Transaction":
# 				if payment_log.decision == "ACCEPT":
# 					doc = frappe.get_doc("Wallet Transaction", payment_log.reference_doc)
# 					doc.transaction_reference = payment_log.name
# 					doc.save(ignore_permissions=True)
# 					doc.submit()

# 					wallet_topup(doc, doc.client_id)
# 				else:
# 					if doc.online:
# 						frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'docstatus', 2)
# 						frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'transaction_status', 'Cancelled')
# 						frappe.db.commit()
				
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()
			
# 			elif payment_log.document_type == "Cart":
# 				doc = frappe.get_doc("Cart", payment_log.reference_doc)
# 				if payment_log.decision == "ACCEPT":
# 					doc.append('payment_table', {
# 						"payment_date": getdate(),
# 						"mode_of_payment": "Online Payment",
# 						"paid_amount": float(payment_log.qpay_auth_amount),
# 						"transaction_reference": payment_log.qpay_confirmation_id
# 					})
# 					doc.save(ignore_permissions=True)
# 					doc.submit()
# 				else:
# 					if doc.online:
# 						frappe.db.set_value('Cart', payment_log.reference_doc, 'docstatus', 2)
# 						frappe.db.set_value('Cart', payment_log.reference_doc, 'payment_status', 'Cancelled')
# 						frappe.db.commit()
					
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()
			
# 			elif payment_log.document_type == "Gift Voucher":
# 				doc = frappe.get_doc("Gift Voucher", payment_log.reference_doc)
# 				if payment_log.decision == "ACCEPT":
# 						doc.append('payment_table', {
# 							"payment_date": today,
# 							"mode_of_payment": "Online Payment",
# 							"paid_amount": float(payment_log.qpay_auth_amount),
# 							"transaction_reference": payment_log.qpay_confirmation_id
# 						})
# 						doc.voucher_status = "Active"
# 						doc.save(ignore_permissions=True)
# 						doc.submit()
# 				else:
# 					if doc.online:
# 						frappe.db.set_value('Gift Voucher', payment_log.reference_doc, 'docstatus', 2)
# 						frappe.db.set_value('Gift Voucher', payment_log.reference_doc, 'payment_status', 'Not Paid')
# 						frappe.db.commit()					
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()

# 			elif payment_log.document_type == "Food Order Entry":
# 				if payment_log.decision == "ACCEPT":
# 					doc = frappe.get_doc("Food Order Entry", payment_log.reference_doc)
# 					doc.append('payment_table', {
# 						"payment_date": getdate(),
# 						"mode_of_payment": "Online Payment",
# 						"paid_amount": float(payment_log.qpay_auth_amount),
# 						"transaction_reference": payment_log.qpay_confirmation_id
# 					})
# 					# doc.order_status = "Ordered"
# 					# doc.payment_status = "Paid"
# 					doc.save(ignore_permissions=True)
# 					doc.submit()

# 					frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 					frappe.db.commit()
# 				else:
# 					frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'docstatus', 2)
# 					frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'order_status', 'Cancelled')
# 					frappe.db.commit()
				
# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()

# # Manual updation of payment in case of payment failures
# @frappe.whitelist()
# def update_payment_manual(doc_id):
# 	payment_log = frappe.get_doc('Payment Log', doc_id)
	
# 	if payment_log.payment_log_type == "Credit Card":
# 		if payment_log.document_type == "Cart":
# 			doc = frappe.get_doc("Cart", payment_log.reference_doc)
# 			if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 				doc.append('payment_table', {
# 					"payment_date": getdate(),
# 					"mode_of_payment": "Online Payment",
# 					"paid_amount": float(payment_log.auth_amount),
# 					"transaction_reference": payment_log.transaction_id
# 				})

# 				doc.save(ignore_permissions=True)
# 				doc.submit()
# 			else:
# 				if doc.online:
# 					frappe.db.set_value('Cart', payment_log.reference_doc, 'docstatus', 2)
# 					frappe.db.set_value('Cart', payment_log.reference_doc, 'payment_status', 'Cancelled')
# 					frappe.db.commit()
					
# 			frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 			frappe.db.commit()
	
# 		elif payment_log.document_type == "Wallet Transaction":
# 			doc = frappe.get_doc("Wallet Transaction", payment_log.reference_doc)
# 			if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 				doc.transaction_reference = payment_log.name
# 				doc.save(ignore_permissions=True)
# 				doc.submit()
# 			else:
# 				if doc.online:
# 					frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'docstatus', 2)
# 					frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'transaction_status', 'Cancelled')
# 					frappe.db.commit()
				
# 			frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 			frappe.db.commit()

# 		elif payment_log.document_type == "Food Order Entry":
# 			doc = frappe.get_doc("Food Order Entry", payment_log.reference_doc)
# 			if payment_log.decision == "ACCEPT" and payment_log.req_amount == payment_log.auth_amount:
# 				doc.append('payment_table', {
# 					"payment_date": getdate(),
# 					"mode_of_payment": "Online Payment",
# 					"paid_amount": float(payment_log.auth_amount),
# 					"transaction_reference": payment_log.transaction_id
# 				})
# 				doc.order_status = "Ordered"
# 				doc.payment_status = "Paid"
# 				doc.save(ignore_permissions=True)
# 				doc.submit()

# 			else:
# 				frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'docstatus', 2)
# 				frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'order_status', 'Cancelled')
# 				frappe.db.commit()

# 			frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 			frappe.db.commit()
		
# 		frappe.msgprint(msg = "Payment has been updated", title="Success")

# 	elif payment_log.payment_log_type == "Debit Card":
# 		if payment_log.document_type == "Wallet Transaction":
# 			if payment_log.decision == "ACCEPT":
# 				doc = frappe.get_doc("Wallet Transaction", payment_log.reference_doc)
# 				doc.transaction_reference = payment_log.name
# 				doc.save(ignore_permissions=True)
# 				doc.submit()
# 			else:
# 				if doc.online:
# 					frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'docstatus', 2)
# 					frappe.db.set_value('Wallet Transaction', payment_log.reference_doc, 'transaction_status', 'Cancelled')
# 					frappe.db.commit()
				
# 			frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 			frappe.db.commit()
			
# 		elif payment_log.document_type == "Cart":
# 			doc = frappe.get_doc("Cart", payment_log.reference_doc)
# 			if payment_log.decision == "ACCEPT":
# 				doc.append('payment_table', {
# 					"payment_date": getdate(),
# 					"mode_of_payment": "Online Payment",
# 					"paid_amount": float(payment_log.qpay_auth_amount),
# 					"transaction_reference": payment_log.qpay_confirmation_id
# 				})
# 				doc.save(ignore_permissions=True)
# 				doc.submit()
# 			else:
# 				if doc.online:
# 					frappe.db.set_value('Cart', payment_log.reference_doc, 'docstatus', 2)
# 					frappe.db.set_value('Cart', payment_log.reference_doc, 'payment_status', 'Cancelled')
# 					frappe.db.commit()
					
# 			frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 			frappe.db.commit()

# 		elif payment_log.document_type == "Food Order Entry":
# 			if payment_log.decision == "ACCEPT":
# 				doc = frappe.get_doc("Food Order Entry", payment_log.reference_doc)
# 				doc.append('payment_table', {
# 					"payment_date": getdate(),
# 					"mode_of_payment": "Online Payment",
# 					"paid_amount": float(payment_log.qpay_auth_amount),
# 					"transaction_reference": payment_log.qpay_confirmation_id
# 				})
# 				doc.order_status = "Ordered"
# 				doc.payment_status = "Paid"
# 				doc.save(ignore_permissions=True)
# 				doc.submit()

# 				frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 				frappe.db.commit()
# 			else:
# 				frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'docstatus', 2)
# 				frappe.db.set_value('Food Order Entry', payment_log.reference_doc, 'order_status', 'Cancelled')
# 				frappe.db.commit()
				
# 			frappe.db.set_value('Payment Log', payment_log.name, 'payment_updated', 1)
# 			frappe.db.commit()
		
# 		frappe.msgprint(msg = "Payment has been updated", title="Success")