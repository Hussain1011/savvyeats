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

	if order.docstatus == 0 and order.rounded_total > 0:
		message_en = "Payment not successful."
		message_ar = "لم تنجح عملية الدفع."

		errors = {
			"error": ["Payment not successful."]
		}
		return send_error_response(message_en, message_ar, errors)

	if order.docstatus == 1:
		message_en = "Payment verified successfully."
		message_ar = "تم التحقق من الدفع بنجاح."

		return send_success_response(message_en, message_ar, order)

	if order.rounded_total == 0 and doc.docstatus == 0:
		message_en = "Payment verified successfully."
		message_ar = "تم التحقق من الدفع بنجاح."
		order.flags.ignore_permissions = True
		order.submit()
		frappe.db.commit()

		return send_success_response(message_en, message_ar, order)


	message_en = "Payment not successful."
	message_ar = "لم تنجح عملية الدفع."
	errors = {
		"error": ["Payment not successful."]
	}
	return send_error_response(message_en, message_ar, errors)


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
