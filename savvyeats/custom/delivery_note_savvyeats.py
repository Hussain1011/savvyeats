import frappe
from frappe.utils import getdate, add_to_date, date_diff
from datetime import timedelta
from frappe import _
from savvyeats.api.user import send_error_response, send_success_response

WEEKDAY_MAP = {
	"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
	"Friday": 4, "Saturday": 5, "Sunday": 6
}

def validate(self, method):
	sales_order = None
	self.delivery_status = "Scheduled"
	for d in self.items:
		if not d.against_sales_order:
			frappe.throw(_("Sales Order is Mandatory for Item: {0} in Row: {1}.".format(d.item_name, d.idx)))
		if not sales_order:
			sales_order = d.against_sales_order

		if d.against_sales_order != sales_order:
			frappe.throw(_("Only 1 Sales Order is allowed in 1 Delivery."))

		item_doc = frappe.get_doc("Sales Order Item", d.so_detail)
		if getdate(item_doc.delivery_date) != getdate(self.posting_date):
			frappe.throw(_("Items Only allowed for Delivery Date <b>{0}<b>.".format(self.get_formatted("posting_date"))))
		if not d.meal:
			d.meal = item_doc.meal

		if not d.note:
			d.note = item_doc.note

	self.subscription = sales_order
	order = frappe.get_doc("Sales Order", self.subscription)
	self.dish_plan = order.dish_plan
	address = None
	for d in order.delivery_dates:
		if getdate(self.posting_date) == getdate(d.delivery_date):
			address = d.address

	self.shipping_address_name = address
	self.customer_address = address



def on_submit(self, method):
	order = frappe.get_doc("Sales Order", self.subscription)
	for d in order.delivery_dates:
		if getdate(self.posting_date) == getdate(d.delivery_date):
			frappe.db.set_value(d.doctype, d.name, "status", "Scheduled")

def on_cancel(self, method):
	order = frappe.get_doc("Sales Order", self.subscription)
	for d in order.delivery_dates:
		if getdate(self.posting_date) == getdate(d.delivery_date):
			frappe.db.set_value(d.doctype, d.name, "status", "Pending")

def after_insert(self, method):
	sales_order = self.items[0].against_sales_order
	order = frappe.get_doc("Sales Order", sales_order)
	address = None
	for d in order.delivery_dates:
		if getdate(self.posting_date) == getdate(d.delivery_date):
			address = d.address

	frappe.db.set_value(self.doctype, self.name, "shipping_address_name", address, update_modified=False)
	frappe.db.set_value(self.doctype, self.name, "customer_address", address, update_modified=False)
	frappe.db.set_value(self.doctype, self.name, "subscription", order.name, update_modified=False)
	