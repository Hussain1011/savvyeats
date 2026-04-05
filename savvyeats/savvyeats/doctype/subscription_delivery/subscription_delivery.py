# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime_str, get_datetime
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
import urllib.parse
import json


class SubscriptionDelivery(Document):
	def validate(self):
		self.validate_delivery_date()
		self.status = "Pending"
		self.title = getdate(self.delivery_date).strftime("%A, %B %d, %Y")

	def validate_delivery_date(self):
		exists = frappe.get_all("Subscription Delivery", filters={"delivery_date": self.delivery_date, "name": ["!=", self.name], "docstatus": ["!=", 2]})
		if exists:
			frappe.throw(_("Subscription Delivery already exists for Date: <b>{0}</b>".format(self.get_formatted("delivery_date"))))

	@frappe.whitelist()
	def get_letter_menu_url(self):
		delivery_notes = []
		for d in self.items:
			if d.delivery_note and not d.delivery_note in delivery_notes:
				delivery_notes.append(d.delivery_note)

		params = {
			"doctype": "Delivery Note",
			"name": json.dumps(delivery_notes),
			"format": "Letter Menu",
			"no_letterhead": "0",
			"letterhead":"",
			"options": json.dumps({"page-size": "A5"})
		}

		query = urllib.parse.urlencode(params)
		url = f"/api/method/frappe.utils.print_format.download_multi_pdf?{query}"
		return url

	@frappe.whitelist()
	def lock_delivery(self):
		frappe.db.set_value(self.doctype, self.name, "status", "Locked")

	@frappe.whitelist()
	def fetch_deliveries(self):
		sales_order = frappe.get_all("Sales Order", filters={"subscription_status": "Active", "docstatus": 1}, fields=["*"], order_by="creation asc")

		self.items = []
		for d in sales_order:
			so = frappe.get_doc("Sales Order", d.name)
			delivery = False
			for i in so.items:
				if getdate(i.delivery_date) == getdate(self.delivery_date):
					delivery = True
			if not delivery:
				continue

			existing_dn = frappe.db.get_value("Delivery Note", {"subscription": d.name, "posting_date": self.delivery_date, "docstatus": ["!=", 2]})
			if not existing_dn:
				delivery_date_str = str(self.delivery_date)
				frappe.flags.args = frappe._dict({"delivery_dates":[delivery_date_str],"for_reserved_stock":True})
				dn = make_delivery_note(d.name, kwargs={"delivery_dates":[delivery_date_str],"for_reserved_stock":True})
				if not dn.items:
					continue
				dn.set_posting_time = 1
				dn.posting_date = self.delivery_date
				dn.save()
			else:
				dn = frappe.get_doc("Delivery Note", existing_dn)

			for i in dn.items:
				self.append("items",{"customer": so.customer, "sales_order": so.name, "sales_order_item": i.so_detail, "item_code": i.item_code, "item_name": i.item_name, "uom": i.uom, "meal": i.meal, "note": i.note, "qty": i.qty, "delivery_note": dn.name, "delivery_note_item": i.name})

	
	def before_submit(self):
		self.status = "Locked"

	def on_submit(self):
		if not self.items:
			frappe.throw(_("Fetch Deliveries First"))
		delivery_notes = list({d.delivery_note for d in self.items})
		for d in delivery_notes:
			doc = frappe.get_doc("Delivery Note", d)
			doc.submit()


	def on_cancel(self):
		if not self.items:
			frappe.throw(_("Fetch Deliveries First"))
		delivery_notes = list({d.delivery_note for d in self.items})
		for d in delivery_notes:
			doc = frappe.get_doc("Delivery Note", d)
			doc.cancel()

		





