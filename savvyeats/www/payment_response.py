import frappe
from frappe import _


def get_context(context):
	context.no_cache = 1
	order = frappe.get_doc("Sales Order", frappe.form_dict.order_id, ignore_permmission=True)
	if order.docstatus != 0:
		frappe.throw(_("Order Already Paid or Cancelled"))

	if order.rounded_total == order.advance_paid:
		frappe.throw(_("Order Already Paid"))

	context.amount_formatted = order.get_formatted("rounded_total")
	context.order = order.as_dict()
	context.order_id = order.name
	context.total_amount = order.get("rounded_total")
	context.currency = "QAR"
	context.success = True
	context.retry_url = "/pay/{0}".format(order.name)
	return context