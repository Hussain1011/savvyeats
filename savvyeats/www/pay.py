import frappe
from frappe import _
from frappe import redirect_to_message
from savvyeats.payment_integration.utils import get_payment_gateway_url
import time

def get_context(context):
	context.no_cache = 1
	order = frappe.get_doc("Sales Order", frappe.form_dict.order_id, ignore_permmission=True)
	settings = frappe.get_doc("SavvyEats Settings", "SavvyEats Settings", ignore_permmission=True)
	if order.docstatus != 0:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/{0}".format(order.name)
		raise frappe.Redirect

	context.amount_formatted = order.get_formatted("rounded_total")
	context.order = order.as_dict()
	context.settings = settings.as_dict()
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context

@frappe.whitelist(allow_guest=True)
def get_payment_url(order_id, payment_method):
	payment_gateway = frappe.get_doc("Payment Gateway", payment_method, ignore_permission=True)
	if payment_gateway.gateway_settings == "Cybersource":
		return "/redirect/cybersource/{0}/{1}".format(payment_gateway.name, order_id)
	if payment_gateway.gateway_settings == "QPay":
		return "/redirect/qpay/{0}/{1}".format(payment_gateway.name, order_id)

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/redirect/cybersource"
	raise frappe.Redirect

	return {"data": data, "url": url}