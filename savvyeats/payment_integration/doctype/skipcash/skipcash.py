# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import base64, hashlib, hmac, json, uuid
import requests
import frappe
from frappe.utils.password import get_decrypted_password
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import get_datetime


CREATE_ORDER_SIGN_ORDER = [
	"Uid","KeyId","Amount","FirstName","LastName","Phone","Email",
	"Street","City","State","Country","PostalCode","TransactionId","Custom1"
]

WEBHOOK_SIGN_ORDER = [
	"PaymentId","Amount","StatusId","TransactionId","Custom1","VisaId"
]

STATUS_MAP = {
	0: "new",
	1: "pending",
	2: "paid",
	3: "canceled",
	4: "failed",
	5: "rejected",
	6: "refunded",
	7: "pending refund",
	8: "refund failed",
}

class SkipCash(Document):
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

		body = {
			"uid": transaction_uuid,
			"keyId": self.key_id,
			"amount": amount,
			"firstName": client.first_name,
			"lastName": client.last_name or client.first_name,
			"phone": client.mobile_no,
			"email": client.email,
			"street": None,
			"city": None,
			"state": None,
			"country": "QA",
			"postalCode": None,
			"transactionId": reference_number,
			"custom1": doc.doctype,
			"custom2": doc.name,
			"custom3": self.doctype,
			"custom4": self.name,
			"custom5": payment_gateway
		}

		sig_str = self.build_signature_string_for_create(body)
		signature = self.b64_hmac_sha256(self.key_secret, sig_str)

		url = f"{self.base_url}/api/v1/payments"
		resp = requests.post(url, headers=self.make_headers_for_create(signature), data=json.dumps(body), timeout=15)
		try:
			payload = resp.json()
		except Exception:
			frappe.throw(f"SkipCash create payment failed (HTTP {resp.status_code}). Raw: {resp.text}")

		if resp.status_code != 200 or payload.get("hasError") or payload.get("hasValidationError"):
			frappe.throw(f"SkipCash create payment error: {payload}")




		result_obj = payload.get("resultObj") or {}

		# scpl = frappe.new_doc("SkipCash Payment Log")
		# scpl.reference_doctype = doc.doctype
		# scpl.reference_docname = doc.name
		# scpl.payment_gateway = payment_gateway
		# scpl.gateway_settings = self.doctype
		# scpl.gateway_controller = self.name
		# scpl.skipcash_id = result_obj["id"]
		# scpl.skipcash_statusid = result_obj["statusId"]
		# scpl.skipcash_status = result_obj["status"]
		# scpl.skipcash_created = datetime.fromisoformat(result_obj["created"]).strftime("%Y-%m-%d %H:%M:%S")
		# scpl.skipcash_payurl = result_obj["payUrl"]
		# scpl.skipcash_amount = result_obj["amount"]
		# scpl.skipcash_currency = result_obj["currency"]
		# scpl.skipcash_transactionid = result_obj["transactionId"]
		# scpl.skipcash_custom1 = result_obj["custom1"]
		# scpl.skipcash_visaid = result_obj["visaId"]
		# scpl.skipcash_json = result_obj
		# scpl.flags.ignore_permissions = True
		# scpl.insert()
		# frappe.db.commit()


		return result_obj, result_obj["payUrl"]

	def b64_hmac_sha256(self, secret: str, data: str) -> str:
		digest = hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).digest()
		return base64.b64encode(digest).decode("utf-8")

	def build_signature_string_for_create(self, body: dict) -> str:
		key_map = {
			"Uid": "uid", "KeyId": "keyId", "Amount": "amount",
			"FirstName": "firstName", "LastName": "lastName", "Phone": "phone",
			"Email": "email", "Street": "street", "City": "city", "State": "state",
			"Country": "country", "PostalCode": "postalCode",
			"TransactionId": "transactionId", "Custom1": "custom1", "Custom2": "custom2", "Custom3": "custom3", "Custom4": "custom4", "Custom5": "custom5"
		}
		parts = []
		for title_key in CREATE_ORDER_SIGN_ORDER:
			json_key = key_map[title_key]
			val = body.get(json_key)
			if val is not None and str(val) != "":
				parts.append(f"{title_key}={val}")
		return ",".join(parts)


	def make_headers_for_create(self, signature: str) -> dict:
		return {"Authorization": signature, "Content-Type": "application/json"}

def build_signature_string_for_webhook(body: dict) -> str:
	key_map = {
		"PaymentId": "paymentId", "Amount": "amount", "StatusId": "statusId",
		"TransactionId": "transactionId", "Custom1": "custom1", "Custom2": "custom2", "Custom3": "custom3", "Custom4": "custom4", "Custom5": "custom5", "VisaId": "visaId"
	}
	parts = []
	for title_key in WEBHOOK_SIGN_ORDER:
		json_key = key_map[title_key]
		val = body.get(json_key)
		if val is not None and str(val) != "":
			parts.append(f"{title_key}={val}")
	return ",".join(parts)

def _make_headers_for_get_detail(client_id: str) -> dict:
	# Manual says the Authorization header contains the Client ID for this GET. 
	return {"Authorization": client_id, "Accept": "application/json"}

@frappe.whitelist(allow_guest=True)
def reciept(**kwargs):

	# {"id":"33089cb6-d563-4457-bc67-73ccd856b777","statusId":0,"created":"2025-09-21T15:06:09Z","payUrl":"https://skipcashtest.azurewebsites.net/pay/33089cb6-d563-4457-bc67-73ccd856b777","amount":"400.00","firstPaymentAmount":0,"currency":"QAR","transactionId":"SAL-ORD-2025-00003","finishedDate":null,"custom1":"SkipCash","custom2":"SAL-ORD-2025-00003","custom3":"SkipCash","custom4":"SkipCash Sandbox","custom5":"SkipCash","custom6":null,"custom7":null,"custom8":null,"custom9":null,"custom10":null,"visaId":null,"refundId":null,"refundStatusId":null,"tokenId":null,"status":"new","cardType":null,"cardNumber":null,"recurringSubscriptionId":"00000000-0000-0000-0000-000000000000","info":null,"brandName":null,"accountFundingSource":null,"cardProduct":null,"issuerName":null,"issuerCountry":null,"reasonCode":null}

	auth_header = (frappe.get_request_header("Authorization") or "").strip()
	data = frappe.request.data
	try:
		data = json.loads(data.decode("utf-8")) if isinstance(data, (bytes, bytearray)) else json.loads(data)
	except Exception:
		frappe.local.response["http_status_code"] = 400
		return "Invalid JSON"

	doctype = data.get("custom1")
	docname = data.get("custom2")
	gateway_settings = data.get("custom3")
	gateway_controller = data.get("custom4")
	payment_gateway = data.get("custom5")

	pg = frappe.get_doc("Payment Gateway", payment_gateway, ignore_permissions=True)
	settings = frappe.get_doc(pg.gateway_settings, pg.gateway_controller, ignore_permissions=True)

	sig_str = build_signature_string_for_webhook(data)
	expected = settings.b64_hmac_sha256(settings.webhook_key, sig_str)

	if not hmac.compare_digest(expected, auth_header):
		frappe.local.response["http_status_code"] = 401
		return "Unauthorized"

	if status_text != "paid":
		return "OK"


	doctype = docname

	prl = frappe.new_doc("Payment Response Log")
	prl.response_data = data
	prl.payment_type = "SkipCash"
	prl.insert(ignore_permissions=True)
	frappe.db.commit()


	pay_log = frappe.get_doc({
		'doctype': 'Payment Log',
		'payment_log_type': 'SkipCash',
		'document_type': doctype,
		'reference_doc': docname,
		'req_amount': doc.rounded_total,
		'reason_code': data.get("reasonCode"),
		'message': data.get("payUrl"),
		'payment_gateway': payment_gateway,
		'gateway_settings': gateway_settings.doctype,
		'gateway_controller': gateway_settings.name,
		'transaction_id' : data.get("transactionId"),
		'req_transaction_uuid' : data.get("payUrl"),
		'req_transaction_type' : "sale",
		'req_reference_number': "",
		'req_bill_to_forename': "",
		'req_bill_to_surname' : "",
		'req_bill_to_email' : "",
		'req_customer_ip_address' : "",
		'req_card_number' : "",
		'req_card_expiry_date' : "",
		'card_type' : "",
		'card_type_name' : "",
		'auth_amount' : data.get("amount"),
		'signed_field_names' : "",
		'signed_date_time' : "",
		'response_data': data,
		'payment_gateway_hash': "",
		'generated_hash': expected,
		'signature_verified': 1,
		'payment_response_log': prl.name
	})
	
	pay_log.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/payment-response/success/{0}".format(docname)

	return "OK"

def get_payment_detail_internal(payment_id: str) -> dict:
	settings = _settings()
	url = f"{settings.base_url}/api/v1/payments/{payment_id}"
	resp = requests.get(url, headers=_make_headers_for_get_detail(settings.client_id), timeout=15)
	payload = resp.json() if resp.headers.get("Content-Type","").startswith("application/json") else {}
	return payload

# @frappe.whitelist()
# def get_payment_detail(payment_id: str) -> dict:
# 	"""Manually query SkipCash for a payment detail (e.g., after return URL redirect)."""
# 	payload = get_payment_detail_internal(payment_id)
# 	if not payload:
# 		frappe.throw("No response from SkipCash.")
# 	return payload

# def on_skipcash_paid(skipcash_name: str):
# 	"""
# 	Your post-payment handler.
# 	Implement whatever you need (e.g., set Sales Invoice as paid, notify customer, etc.)
# 	"""
# 	doc = frappe.get_doc("SkipCash", skipcash_name)
# 	# Example: if linked to a Sales Invoice
# 	if getattr(doc, "ref_doctype", None) and getattr(doc, "ref_docname", None):
# 		try:
# 			ref = frappe.get_doc(doc.ref_doctype, doc.ref_docname)
# 			# Do your own business rule here
# 			# ref.submit() / mark as paid etc.
# 		except Exception:
# 			frappe.logger().error("Failed post-payment handling", exc_info=True)
