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


class Cybersource(Document):

	def generate_hash(self, doc, payment_gateway):
		transaction_uuid = str(uuid.uuid4()).replace("-", "")
		signed_date_time = datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
		reference_number = "{0}/{1}".format(doc.doctype, doc.name)
		amount = 0
		if doc.doctype in ("Sales Order", "Sales Invoice"):
			amount = format(float(doc.rounded_total), '.2f')

			if doc.doctype == "Sales Order":
				if doc.advance_paid == doc.rounded_total:
					frappe.local.response["type"] = "redirect"
					frappe.local.response["location"] = "/payment-response/error/{0}".format(doc.name)
					raise frappe.Redirect


		currency = doc.currency

		client = frappe.get_doc("User", doc.owner)

		default_dict = {
			"access_key": self.access_key,
			"profile_id": self.profile_id,
			"transaction_uuid": transaction_uuid,
			"customer_ip_address": frappe.local.request_ip,
			"device_fingerprint_id": transaction_uuid,
			"signed_date_time" : signed_date_time,
			"locale": "en",
			"transaction_type" : "sale",
			"reference_number" : reference_number,
			"amount" : amount,
			"currency": currency,
			"payment_method": "card",
			"bill_to_forename": client.first_name,
			"bill_to_surname": client.last_name,
			"bill_to_email": client.email,
			"bill_to_address_country":"QA",
			"merchant_defined_data1": doc.doctype,
			"merchant_defined_data2": doc.name,
			"merchant_defined_data3": self.doctype,
			"merchant_defined_data4": self.name,
			"merchant_defined_data5": payment_gateway,
			# "override_custom_receipt_page": "{0}/api/method/savvyeats.payment_integration.doctype.cybersource.cybersource.reciept".format(frappe.utils.get_url()),
			# "override_custom_cancel_page": "{1}/payment-response/failure/{0}".format(doc.name, frappe.utils.get_url()),
			"signed_field_names": "access_key,profile_id,transaction_uuid,customer_ip_address,device_fingerprint_id,signed_date_time,locale,transaction_type,signed_field_names,unsigned_field_names,reference_number,amount,currency,payment_method,bill_to_forename,bill_to_surname,bill_to_email,bill_to_address_country,merchant_defined_data1,merchant_defined_data2,merchant_defined_data3,merchant_defined_data4,merchant_defined_data5",
			"unsigned_field_names": ""
		}

		signed_list = default_dict["signed_field_names"].split(",")

		fields_array = []
		for item in signed_list:
			for key,value in default_dict.items():
				if key==item:
					fields_array.append(str(key)+"="+str(value))

		encode_string = ",".join(fields_array)

		signature = self.get_signature(signed_list, encode_string=encode_string)
		
		data = []
		for key,value in default_dict.items():
			data.append({key:value})

		data.append({
			'signature' : signature
		})

		return data, self.transaction_url

	def get_signature(self, fields, encode_string=None):
		if not encode_string:
			encode_string = self.generate_data_string(fields)
		hash_value = hmac.new(self.signature.encode(), encode_string.encode(), hashlib.sha256)
		signature = base64.b64encode(hash_value.digest()).decode("utf-8")

		return signature

	def generate_data_string(self, data):
		fields = []
		for i,v in data.items():
			fields.append(str(i)+"="+str(v))

		fields_str = ",".join(fields)
		return fields_str


@frappe.whitelist(allow_guest = True)
def reciept(**kwargs):
	response = frappe._dict(kwargs)
	json_dict = json.dumps(kwargs)
	doctype = response.req_merchant_defined_data1
	docname = response.req_merchant_defined_data2
	gateway_settings = response.req_merchant_defined_data3
	gateway_controller = response.req_merchant_defined_data4
	payment_gateway = response.req_merchant_defined_data5

	if not response.decision == "ACCEPT":
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/failure/{0}".format(docname)
		return frappe.Redirect

	if frappe.db.exists("Payment Log", {"req_transaction_uuid": response.req_transaction_uuid}):
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/{0}".format(docname)
		return

	signed_list = response['signed_field_names'].split(",")
	fields = {}
	for item in signed_list:
		fields[item] = response[item]

	gateway_settings = frappe.get_doc(gateway_settings, gateway_controller)
	signature = gateway_settings.get_signature(fields)

	if signature == response["signature"]:
		prl = frappe.new_doc("Payment Response Log")
		prl.response_data = json_dict
		prl.payment_type = "Credit Card"
		prl.insert(ignore_permissions=True)
		frappe.db.commit()
		doc = frappe.get_doc(doctype, docname, ignore_permissions=True)
		if response['req_transaction_type'] == 'sale':
			pay_log = frappe.get_doc({
				'doctype': 'Payment Log',
				'payment_log_type': 'Credit Card',
				'document_type': doctype,
				'reference_doc': docname,
				'req_amount': doc.rounded_total,
				'decision': 'ACCEPT',
				'reason_code': response['reason_code'],
				'message': response['message'],
				'payment_gateway': payment_gateway,
				'gateway_settings': gateway_settings.doctype,
				'gateway_controller': gateway_settings.name,
				'transaction_id' : response['auth_trans_ref_no'],
				'req_transaction_uuid' : response['req_transaction_uuid'],
				'req_transaction_type' : response['req_transaction_type'],
				'req_reference_number': response['req_reference_number'],
				'req_bill_to_forename': response['req_bill_to_forename'],
				'req_bill_to_surname' : response['req_bill_to_surname'],
				'req_bill_to_email' : response['req_bill_to_email'],
				'req_customer_ip_address' : response['req_customer_ip_address'],
				'req_card_number' : response['req_card_number'],
				'req_card_expiry_date' : response['req_card_expiry_date'],
				'card_type' : response['req_card_type'],
				'card_type_name' : response['card_type_name'],
				'auth_amount' : response['auth_amount'],
				'signed_field_names' : response['signed_field_names'],
				'signed_date_time' : response['signed_date_time'],
				'response_data': json_dict,
				'payment_gateway_hash': response["signature"],
				'generated_hash': signature,
				'signature_verified': 1,
				'v2': 1,
				'payment_response_log': prl.name
			})
			pay_log.insert(ignore_permissions=True)
			frappe.db.commit()
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/payment-response/success/{0}".format(docname)

