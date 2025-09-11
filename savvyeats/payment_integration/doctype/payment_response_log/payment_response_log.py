# # Copyright (c) 2022, Blue Lynx and contributors
# # For license information, please see license.txt

# import frappe
# import json
from frappe.model.document import Document
# from frappe.utils import getdate, flt

class PaymentResponseLog(Document):
	pass

# # Cron job action to create payment logs
# @frappe.whitelist()
# def create_payment_log():
# 	pay_logs = frappe.get_all('Payment Response Log', filters={'log_created': 0}, fields=['name', 'payment_type', 'response_data', 'log_created'])
# 	if pay_logs:
# 		for row in pay_logs:
			
# 			response = json.loads(row.response_data)
# 			if row.payment_type == "Debit Card":
# 				pun = response['Response.PUN']
# 				pun_type = pun[0:3]

# 				if pun_type == "123":
# 					doctype = "Wallet Transaction"
# 					wallet_list = frappe.get_all('Wallet Transaction', filters={"payment_reference": pun})
# 					doc = frappe.get_doc('Wallet Transaction', wallet_list[0])
# 					client = frappe.get_doc('Client', doc.client_id)
# 					amount_flt = flt(doc.amount) / 100.0
# 					amount = '{:,.2f}'.format(amount_flt)
				
# 				decision = ""
# 				if response['Response.Status'] == "0000":
# 					decision = "ACCEPT"
# 				else:
# 					decision = "DECLINE"

# 				doc = frappe.get_doc({
# 					'doctype': 'Payment Log',
# 					'client_id': client.name,
# 					'payment_log_type': 'Debit Card',
# 					'document_type': doctype,
# 					'reference_doc': doc.name,
# 					'req_amount': amount,
# 					'decision': decision,
# 					'reason_code': response['Response.Status'],
# 					'message': response['Response.StatusMessage'],
# 					'qpay_date_time': response['Response.EZConnectResponseDate'],
# 					'qpay_txn_pun': response['Response.PUN'],
# 					'qpay_confirmation_id': response['Response.ConfirmationID'],
# 					'qpay_merchant_id': response['Response.MerchantModuleSessionID'],
# 					'qpay_card_number': response['Response.CardNumber'],
# 					'qpay_expiry_date': response['Response.CardExpiryDate'],
# 					'qpay_auth_amount': response['Response.Amount']
# 				})
# 				doc.insert(ignore_permissions=True)

# 				frappe.db.set_value('Payment Response Log', row.name, 'log_created', 1)
# 				frappe.db.commit()