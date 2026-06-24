# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import base64, hashlib, hmac, json, uuid
import requests
import frappe
from frappe.utils.password import get_decrypted_password
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import get_datetime, getdate
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,
	get_payment_entry,
)

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
			charge_amount = doc.rounded_total

			if doc.doctype == "Sales Order":
				if doc.advance_paid == doc.rounded_total:
					frappe.local.response["type"] = "redirect"
					frappe.local.response["location"] = "/payment-response/error/{0}".format(doc.name)
					raise frappe.Redirect

				# Lock the amount on the first payment initiation so the charged amount
				# cannot drift afterwards; reuse the locked amount on later attempts.
				locked = doc.get("locked_amount")
				if locked and float(locked) > 0:
					charge_amount = locked
				else:
					frappe.db.set_value("Sales Order", doc.name, "locked_amount", doc.rounded_total, update_modified=False)
					doc.locked_amount = doc.rounded_total

			amount = format(float(charge_amount), '.2f')


		currency = doc.currency

		first_name, last_name, phone, email = self._get_payer_details(doc)

		body = {
			"uid": transaction_uuid,
			"keyId": self.key_id,
			"amount": amount,
			"firstName": first_name,
			"lastName": last_name or first_name,
			"phone": phone,
			"email": email,
			"street": None,
			"city": None,
			"state": None,
			"country": "QA",
			"postalCode": None,
			"transactionId": reference_number,
			"custom1": payment_gateway,
			"custom2": doc.name,
			"custom3": self.doctype,
			"custom4": self.name,
			"custom5": doc.doctype
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

	def _get_payer_details(self, doc):

		# Default to the order owner (correct for online self-signup).
		owner = frappe.db.get_value(
			"User", doc.owner, ["first_name", "last_name", "mobile_no", "email"], as_dict=True
		) or frappe._dict()
		first_name = owner.first_name
		last_name = owner.last_name or owner.first_name
		phone = owner.mobile_no
		email = owner.email

		customer = doc.get("customer")
		if customer and customer != "Online Customer":
			cust = frappe.db.get_value(
				"Customer", customer, ["customer_name", "user", "mobile_no", "email_id"], as_dict=True
			) or frappe._dict()

			# Name from the order / customer record.
			display_name = (doc.get("customer_name") or cust.customer_name or "").strip()
			if display_name:
				parts = display_name.split(" ", 1)
				first_name = parts[0]
				last_name = parts[1] if len(parts) > 1 else parts[0]

			# Contact details: prefer the customer's linked app user, then the Customer
			# record's own fields, then fall back to the owner's.
			cust_phone = cust_email = None
			if cust.user:
				cust_user = frappe.db.get_value(
					"User", cust.user, ["mobile_no", "email"], as_dict=True
				) or frappe._dict()
				cust_phone = cust_user.mobile_no
				cust_email = cust_user.email
			phone = cust_phone or cust.mobile_no or phone
			email = cust_email or cust.email_id or email

		return first_name, last_name, phone, email

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
	return {"Authorization": client_id, "Accept": "application/json"}



# {"id":"33089cb6-d563-4457-bc67-73ccd856b777","statusId":0,"created":"2025-09-21T15:06:09Z","payUrl":"https://skipcashtest.azurewebsites.net/pay/33089cb6-d563-4457-bc67-73ccd856b777","amount":"400.00","firstPaymentAmount":0,"currency":"QAR","transactionId":"SAL-ORD-2025-00003","finishedDate":null,"custom1":"SkipCash","custom2":"SAL-ORD-2025-00003","custom3":"SkipCash","custom4":"SkipCash Sandbox","custom5":"SkipCash","custom6":null,"custom7":null,"custom8":null,"custom9":null,"custom10":null,"visaId":null,"refundId":null,"refundStatusId":null,"tokenId":null,"status":"new","cardType":null,"cardNumber":null,"recurringSubscriptionId":"00000000-0000-0000-0000-000000000000","info":null,"brandName":null,"accountFundingSource":null,"cardProduct":null,"issuerName":null,"issuerCountry":null,"reasonCode":null}

@frappe.whitelist(allow_guest=True)
def webhook(**kwargs):
	frappe.local.flags.ignore_csrf = True

	auth_header = (
		frappe.get_request_header("Authorization")
		or frappe.get_request_header("authorization")
		or frappe.get_request_header("HTTP_AUTHORIZATION")
		or ""
	).strip()

	raw = frappe.request.data
	body = None
	if raw:
		try:
			body = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
		except Exception as e:
			frappe.logger().warning({"msg": "Webhook raw body not JSON; falling back to form_dict", "err": str(e)})
			body = None

	if body is None:
		fd = frappe.local.form_dict or {}
		body = {k: v for k, v in fd.items() if k != "cmd"}
		if kwargs:
			body.update(kwargs)

	if not body:
		frappe.local.response["http_status_code"] = 400
		return "Empty body"

	def pick(d, *keys):
		for k in keys:
			if k in d and d[k] not in (None, "", []):
				return d[k]
		return None

	payment_id = pick(body, "paymentId", "id", "PaymentId")
	amount = pick(body, "amount", "Amount")
	status_id = pick(body, "statusId", "StatusId")
	transaction_id = pick(body, "transactionId", "transId", "TransactionId")
	custom1 = pick(body, "custom1", "Custom1")
	custom2 = pick(body, "custom2", "Custom2")
	custom3 = pick(body, "custom3", "Custom3")
	custom4 = pick(body, "custom4", "Custom4")
	custom5 = pick(body, "custom5", "Custom5")
	visa_id = pick(body, "visaId", "VisaId")

	canonical = {
		"paymentId": payment_id,
		"amount": amount,
		"statusId": status_id,
		"transactionId": transaction_id,
		"custom1": custom1,
		"custom2": custom2,
		"custom3": custom3,
		"custom4": custom4,
		"custom5": custom5,
		"visaId": visa_id,
	}
	data = body
	prl = frappe.new_doc("Payment Response Log")
	prl.response_data = json.dumps(data)
	prl.payment_type = "SkipCash"
	prl.insert(ignore_permissions=True)
	frappe.db.commit()

	doctype = data.get("Custom5")
	docname = data.get("Custom2")
	gateway_settings = data.get("Custom3")
	gateway_controller = data.get("Custom4")
	payment_gateway = data.get("Custom1")

	doc = frappe.get_doc(doctype, docname, ignore_permissions=True)

	pg = frappe.get_doc("Payment Gateway", payment_gateway, ignore_permissions=True)
	settings = frappe.get_doc(pg.gateway_settings, pg.gateway_controller, ignore_permissions=True)

	sig_str = build_signature_string_for_webhook(data)
	expected = settings.b64_hmac_sha256(settings.webhook_key, sig_str)

	if not hmac.compare_digest(expected, auth_header):
		frappe.local.response["http_status_code"] = 401
		return "Unauthorized"

	status_text = STATUS_MAP[data.get("StatusId")]
	if status_text != "paid":
		return "OK"

	# Safety net: the amount SkipCash reports as paid should match the amount we locked
	# for this order. A mismatch means the price drifted or was tampered with after the
	# payment link was generated — record it for review (non-blocking, money is taken).
	try:
		reported_amount = data.get("Amount") or data.get("amount")
		expected_amount = doc.get("locked_amount") or doc.get("rounded_total")
		if reported_amount is not None and expected_amount and abs(float(reported_amount) - float(expected_amount)) > 0.01:
			frappe.log_error(
				title="SkipCash amount mismatch",
				message="Order {0}: expected {1}, paid {2}".format(docname, expected_amount, reported_amount),
			)
	except Exception:
		pass

	#{"PaymentId": "c3f65d87-2d5d-4f97-8b85-d93008de3b9d", "Amount": "15.00", "StatusId": 2, "TransactionId": "Sales Order/SAL-ORD-2025-00049", "FinishedDate": "2025-09-22T11:35:18.9133333", "Custom1": "Sales Order", "Custom2": "SAL-ORD-2025-00049", "Custom3": "SkipCash", "Custom4": "SkipCash SandBox", "Custom5": "SkipCash Sandbox", "Custom6": null, "Custom7": null, "Custom8": null, "Custom9": null, "Custom10": null, "VisaId": "7585301175546640804606", "TokenId": "", "CardType": "Credit Card", "CardNubmer": "411111XXXXXX1111", "RecurringSubscriptionId": "00000000-0000-0000-0000-000000000000"}


	pay_log = frappe.get_doc({
		'doctype': 'Payment Log',
		'payment_log_type': 'SkipCash',
		'document_type': doctype,
		'reference_doc': docname,
		'req_amount': doc.rounded_total,
		'reason_code': data.get("StatusId"),
		'message': data.get("payUrl"),
		'payment_gateway': payment_gateway,
		'gateway_settings': gateway_settings.doctype,
		'gateway_controller': gateway_settings.name,
		'transaction_id' : data.get("transactionId"),
		'req_transaction_uuid' : data.get("PaymentId"),
		'req_transaction_type' : "sale",
		'req_reference_number': "",
		'req_bill_to_forename': "",
		'req_bill_to_surname' : "",
		'req_bill_to_email' : "",
		'req_customer_ip_address' : "",
		'req_card_number' : "",
		'req_card_expiry_date' : "",
		'card_type' : data.get("CardType"),
		'card_type_name' : data.get("CardNubmer"),
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




@frappe.whitelist(allow_guest=True)
def reciept(**kwargs):
	try:
		data = frappe.form_dict
		data = frappe._dict(data)
		prl = frappe.new_doc("Payment Response Log")
		prl.response_data = json.dumps(data)
		prl.payment_type = "SkipCash"
		prl.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(e)
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/00000000"
		raise frappe.Redirect


	if data["statusId"] != '2':
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/failure/{0}".format(data["transId"].split("/")[1])
		raise frappe.Redirect

	pg = frappe.get_doc("Payment Gateway", data["custom1"], ignore_permissions=True)

	settings = frappe.get_doc(pg.gateway_settings, pg.gateway_controller, ignore_permissions=True)
	payment_id = data["id"]
	url = f"{settings.base_url}/api/v1/payments/{payment_id}"

	try:
		resp = requests.get(url, headers=_make_headers_for_get_detail(settings.client_id), timeout=15)
	except Exception as e:
		frappe.log_error(e)
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/00000000"
		raise frappe.Redirect

	payload = resp.json() if resp.headers.get("Content-Type","").startswith("application/json") else {}
	data = payload["resultObj"]

	exist = frappe.get_all("Payment Log", filters={"req_transaction_uuid": data["id"]})
	if exist:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/{0}".format(data.get("custom2"))
		return frappe.Redirect

	doctype = data.get("custom5")
	docname = data.get("custom2")
	gateway_settings = data.get("custom3")
	gateway_controller = data.get("custom4")
	payment_gateway = data.get("custom1")

	doc = frappe.get_doc(doctype, docname, ignore_permissions=True)


	try:
		pay_log = frappe.get_doc({
			'doctype': 'Payment Log',
			'payment_log_type': 'SkipCash',
			'document_type': doctype,
			'reference_doc': docname,
			'req_amount': doc.rounded_total,
			'decision': 'ACCEPT',
			'reason_code': data.get("statusId"),
			'message': data.get("payUrl"),
			'payment_gateway': payment_gateway,
			'gateway_settings': gateway_settings,
			'gateway_controller': gateway_controller,
			'transaction_id' : data.get("transactionId"),
			'req_transaction_uuid' : data.get("id"),
			'req_transaction_type' : "sale",
			'req_reference_number': "",
			'req_bill_to_forename': "",
			'req_bill_to_surname' : "",
			'req_bill_to_email' : "",
			'req_customer_ip_address' : "",
			'req_card_number' : "",
			'req_card_expiry_date' : "",
			'card_type' : data.get("cardType"),
			'card_type_name' : data.get("cardNumber"),
			'auth_amount' : data.get("amount"),
			'signed_field_names' : "",
			'signed_date_time' : "",
			'response_data': data,
			'payment_gateway_hash': "",
			'generated_hash': '',
			'signature_verified': 1,
			'payment_response_log': prl.name
		})

		pay_log.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(e)
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/00000000"
		return frappe.Redirect

	# order = doc
	# if order.docstatus != 0:
	# 	frappe.local.response["type"] = "redirect"
	# 	frappe.local.response["location"] = "/payment-response/error/{0}".format(data.get("custom2"))
	# 	return frappe.Redirect

	# if order.rounded_total != float(data.get("amount")):
	# 	frappe.local.response["type"] = "redirect"
	# 	frappe.local.response["location"] = "/payment-response/error/{0}".format(data.get("custom2"))
	# 	return frappe.Redirect


	# if order.customer == "Online Customer":
	# 	customer_data = frappe.get_all("Customer", filters={"user": order.owner}, fields=["name", "customer_name"])
	# 	if customer_data:
	# 		customer = customer_data[0].name
	# 		customer_name = customer_data[0].customer_name
	# 	else:
	# 		try:
	# 			c = frappe.new_doc("Customer")
	# 			c.customer_name = frappe.db.get_value("User", order.owner, "full_name")
	# 			c.user = order.owner
	# 			c.customer_type = "Individual"
	# 			c.flags.ignore_permissions = True
	# 			c.insert()
	# 			frappe.db.commit()
	# 			customer = c.name
	# 			customer_name = c.customer_name
	# 		except Exception as e:
	# 			frappe.log_error(e)
	# 			frappe.local.response["type"] = "redirect"
	# 			frappe.local.response["location"] = "/payment-response/error/00000000"
	# 			raise frappe.Redirect


	# 	order.customer = customer
	# 	order.customer_name = customer_name
	# 	order.title = customer_name


	# try:
	# 	order.flags.ignore_permissions = True
	# 	order.subscription_status = "Active"
	# 	order.submit()
	# except Exception as e:
	# 	frappe.log_error(e)
	# 	frappe.local.response["type"] = "redirect"
	# 	frappe.local.response["location"] = "/payment-response/error/00000000"
	# 	raise frappe.Redirect

	# try:
	# 	user = order.owner

	# 	frappe.set_user("Administrator")
	# 	pe = get_payment_entry(
	# 			order.doctype,
	# 			order.name
	# 		)
	# 	frappe.set_user(user)

	# 	pe.update({
	# 		"mode_of_payment": pg.gateway_account,
	# 		"reference_no": data.get("id"),
	# 		"reference_date": getdate(),
	# 		"remarks": "Payment Entry against {} {} via Payment Log {}".format(
	# 			order.doctype, order.name, pay_log.name
	# 		),
	# 	})

	# 	pe.set_missing_values()
	# 	pe.flags.ignore_permissions = True
	# 	pe.submit()
	# 	pay_log.flags.ignore_permissions = True
	# 	pay_log.payment_updated = 1
	# 	pay_log.save()
	# 	frappe.db.commit()
	# except Exception as e:
	# 	frappe.log_error(e)
	# 	frappe.local.response["type"] = "redirect"
	# 	frappe.local.response["location"] = "/payment-response/error/00000000"
	# 	return frappe.Redirect

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/payment-response/success/{0}".format(docname)
	return frappe.Redirect
	

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
