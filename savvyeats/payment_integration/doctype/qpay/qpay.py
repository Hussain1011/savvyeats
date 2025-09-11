# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import uuid
from datetime import datetime
import hmac
import hashlib
import random
import base64
import json
import string
from frappe.utils import flt, getdate, add_days, get_date_str

class QPay(Document):
	def generate_hash(self, doc, payment_gateway):
		qpl = frappe.new_doc("QPay Payment Log")
		qpl.payment_gateway = payment_gateway
		qpl.gateway_settings = self.doctype
		qpl.gateway_controller = self.name
		qpl.reference_doctype = doc.doctype
		qpl.reference_docname = doc.name
		qpl.flags.ignore_permissions = True
		qpl.save()
		frappe.db.commit()

		amount = str(0)
		if doc.doctype in ("Sales Order", "Sales Invoice"):
			amount = format(float(doc.rounded_total), '.2f')
			amount = str(int(flt(doc.rounded_total) * 100.0))
			if doc.doctype == "Sales Order":
				if doc.advance_paid == doc.rounded_total:
					frappe.local.response["type"] = "redirect"
					frappe.local.response["location"] = "/payment-response/error/{0}".format(doc.name)
					raise frappe.Redirect

		session_id = self.get_session_id()
		timestamp = datetime.utcnow().replace(microsecond=0).strftime("%d%m%Y%H%M%S")

		reference_number = "{0}/{1}".format(doc.doctype, doc.name)

		hash_data = {
		"SecretKey": self.secret_key,
		"Action": "0",
		"Amount": str(amount),
		"BankID": self.bank_id,
		"CurrencyCode": str(self.currency_code),
		"ExtraFields_f14": self.response_url,
		"Lang": "en",
		"MerchantID": self.merchant_id,
		"MerchantModuleSessionID": session_id,
		"PUN": qpl.name,
		"PaymentDescription": reference_number,
		"Quantity": "1",
		"TransactionRequestDate": str(timestamp)
		}

		data =  list(hash_data.values())
		data_str = "".join(data)
		hash_value = hashlib.sha256(data_str.encode())
		signature = hash_value.hexdigest()

		fields = []
		fields.append({"Action": "0"})
		fields.append({"Amount": amount})
		fields.append({"BankID": self.bank_id})
		fields.append({"CurrencyCode": self.currency_code})
		fields.append({"ExtraFields_f14": self.response_url})
		fields.append({"Lang": "en"})
		fields.append({"MerchantID": self.merchant_id})
		fields.append({"MerchantModuleSessionID": session_id})
		fields.append({"PUN": qpl.name})
		fields.append({"PaymentDescription": reference_number})
		fields.append({"Quantity": "1"})
		fields.append({"SecureHash": signature})
		fields.append({"TransactionRequestDate" : timestamp})

		date = add_days(getdate(), -17)
		date_str = get_date_str(date)
		date_str_en = date_str.encode()
		code = (hashlib.md5(date_str_en)).hexdigest()

		return fields, self.payment_url, code, self.redirect_url, self.response_url


	def get_session_id(self):
		letters_and_digits = string.ascii_lowercase + string.digits
		return ''.join((random.choice(letters_and_digits) for i in range(20)))
    
