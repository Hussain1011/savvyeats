import frappe
from frappe import _


def get_context(context):
	context.no_cache = 1
	if frappe.form_dict.order_id != "00000000":
		order = frappe.get_doc("Sales Order", frappe.form_dict.order_id, ignore_permmission=True)
		context.amount_formatted = order.get_formatted("rounded_total")
		context.order = order.as_dict()
		context.order_id = order.name
		context.total_amount = order.get("rounded_total")
		context.currency = "QAR"
	return context