import frappe
from frappe import _
from frappe.utils import getdate
from savvyeats.api.user import send_error_response, send_success_response
import json
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,
	get_payment_entry,
)

from savvyeats.api.order import validate_sales_order
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery, validate_addresses


@frappe.whitelist()
def get_payment_link(order_id):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	if order.docstatus != 0:
		message_en = "Order already paid or cancelled."
		message_ar = "تم دفع الطلب بالفعل أو تم إلغاؤه."

		errors = {
			"error": ["Order already paid or cancelled."]
		}
		return send_error_response(message_en, message_ar, errors)
	data = {"url": "/skip-cash/{0}".format(order.name), "payment_status": 0}
	if order.rounded_total == 0:
		data["payment_status"] = 1

	return send_success_response("", "", data)




@frappe.whitelist()
def verify_payment(order_id):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	if order.docstatus != 0:
		message_en = "Order already paid or cancelled."
		message_ar = "تم دفع الطلب بالفعل أو تم إلغاؤه."

		errors = {
			"error": ["Order already paid or cancelled."]
		}
		return send_error_response(message_en, message_ar, errors)

	order = validate_addresses(order)

	def process_order(order):
		if order.customer == "Online Customer":
			customer_data = frappe.get_all("Customer", filters={"user": frappe.session.user}, fields=["name", "customer_name"])
			if customer_data:
				customer = customer_data[0].name
				customer_name = customer_data[0].customer_name
			else:
				c = frappe.new_doc("Customer")
				c.customer_name = frappe.db.get_value("User", frappe.session.user, "full_name")
				c.user = frappe.session.user
				c.customer_type = "Individual"
				c.flags.ignore_permissions = True
				c.insert()
				frappe.db.commit()
				customer = c.name
				customer_name = c.customer_name

			order.customer = customer
			order.customer_name = customer_name
			order.title = customer_name
		return order

	if order.rounded_total == 0:

		order = process_order(order)
		message_en = "Payment verified successfully."
		message_ar = "تم التحقق من الدفع بنجاح."
		order.flags.ignore_permissions = True
		order.submit()
		frappe.db.commit()

		return send_success_response(message_en, message_ar, order)

	payment = False

	pl = frappe.get_all("Payment Log", filters={"document_type": order.doctype, "reference_doc": order.name, "decision": "ACCEPT"}, fields=["*"])
	if pl:
		payment = True
		mode_of_payment = frappe.db.get_value("Payment Gateway", pl[0].payment_gateway, "gateway_account")
		reference_name = pl[0].name
		reference_no = pl[0].req_transaction_uuid

	if not payment:
		message_en = "Payment not successful."
		message_ar = "لم تنجح عملية الدفع."

		errors = {
			"error": ["Payment not successful."]
		}
		return send_error_response(message_en, message_ar, errors)

	order = process_order(order)

	order.flags.ignore_permissions = True
	order.subscription_status = "Active"
	order.submit()
	user = frappe.session.user
	frappe.set_user("Administrator")
	pe = get_payment_entry(
			order.doctype,
			order.name
		)
	frappe.set_user(user)

	pe.update({
		"mode_of_payment": mode_of_payment,
		"reference_no": reference_no,
		"reference_date": getdate(),
		"remarks": "Payment Entry against {} {} via Payment Log {}".format(
			order.doctype, order.name, reference_name
		),
	})

	pe.set_missing_values()
	pe.flags.ignore_permissions = True
	pe.submit()
	frappe.db.set_value("Payment Log", pl[0].name, "payment_updated", 1)
	frappe.db.commit()

	message_en = "Payment verified successfully."
	message_ar = "تم التحقق من الدفع بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist()
def process_payment(order_id):
	payment_processed = True
	if not payment_processed:
		message_en = "Payment Not Processed"
		message_ar = "Payment Not Processed"

		errors = {
			"error": ["Payment Not Processed"]
		}
		return send_error_response(message_en, message_ar, errors)

	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
