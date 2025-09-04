import frappe
from frappe import _
from frappe import redirect_to_message

def get_context(context):
	context.no_cache = 1
	order = frappe.get_doc("Sales Order", frappe.form_dict.order_id, ignore_permmission=True)
	if order.docstatus != 0:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/{0}".format(order.name)
		raise frappe.Redirect

	context.amount_formatted = order.get_formatted("rounded_total")
	context.order = order.as_dict()
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context

@frappe.whitelist(allow_guest=True)
def get_payment_url(order_id, payment_method):
	order = frappe.get_doc("Sales Order", frappe.form_dict.order_id, ignore_permmission=True)
	return "/payment-response/success/{0}".format(order.name)