import frappe
from frappe import _
from frappe.utils import getdate
from savvyeats.api.user import send_error_response, send_success_response
import json
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,
	get_payment_entry,
)


@frappe.whitelist()
def get_payment_link(order_id):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	if order.docstatus != 0:
		message_en = "Order already paid or cancelled."
		message_ar = "تم دفع الطلب بالفعل أو تم إلغاؤه."

		errors = {
			"error": ["Order already paid or cancelled."]
		}
		return send_error_response(message_en, message_ar, errors)

	url = "/pay/{0}".format(order.name)
	return send_success_response("", "", {"url": url})




@frappe.whitelist()
def verify_payment(order_id):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	if order.docstatus != 0:
		message_en = "Order already paid or cancelled."
		message_ar = "تم دفع الطلب بالفعل أو تم إلغاؤه."

		errors = {
			"error": ["Order already paid or cancelled."]
		}
		return send_error_response(message_en, message_ar, errors)

	payment = True

	mode_of_payment = "Online"
	reference_name = "Test Reference Name"
	reference_no = "12312312313"

	if not payment:
		message_en = "Payment not successful."
		message_ar = "لم تنجح عملية الدفع."

		errors = {
			"error": ["Payment not successful."]
		}
		return send_error_response(message_en, message_ar, errors)

	if order.customer == "Online Customer":
		customer = frappe.get_all("Customer", filters={"user": frappe.session.user})
		if customer:
			customer = customer[0].name
		else:
			c = frappe.new_doc("Customer")
			c.customer_name = frappe.db.get_value("User", frappe.session.user, "full_name")
			c.user = frappe.session.user
			c.customer_type = "Individual"
			c.flags.ignore_permissions = True
			c.insert()
			frappe.db.commit()
			customer = c.name

		order.customer = customer

	order.flags.ignore_permissions = True
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
	frappe.db.commit()

	message_en = "Payment verified successfully."
	message_ar = "تم التحقق من الدفع بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist()
def process_payment(order_id):
	#logic for payment capturing and processing
	payment_processed = True
	if not payment_processed:
		message_en = "Payment Not Processed"
		message_ar = "Payment Not Processed"

		errors = {
			"error": ["Payment Not Processed"]
		}
		return send_error_response(message_en, message_ar, errors)

	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
