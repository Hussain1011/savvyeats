import frappe
from frappe import _
from frappe import redirect_to_message
from savvyeats.payment_integration.utils import get_payment_gateway_url
import time

def get_context(context):
	context.no_cache = 1
	order = frappe.get_doc("Sales Order", frappe.form_dict.order_id, ignore_permmission=True)

	if order.docstatus != 0:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/payment-response/error/{0}".format(order.name)
		raise frappe.Redirect

	gateway = frappe.db.get_value("SavvyEats Settings", "SavvyEats Settings", "skip_cash_gateway")
	if not gateway:
		frappe.throw(_("Skip Cash Gateway not Found."))

	data, url = get_payment_gateway_url(order, gateway)

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = url
	raise frappe.Redirect