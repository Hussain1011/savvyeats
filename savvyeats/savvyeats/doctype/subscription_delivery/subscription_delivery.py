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
		sales_orders = frappe.get_all(
			"Sales Order",
			filters={"subscription_status": ["in", ["Active", "Paused"]], "docstatus": 1},
			pluck="name",
			order_by="creation asc",
		)

		self.items = []
		failed_orders = []

		for so_name in sales_orders:
			# Process each subscription in its own savepoint so that one bad order
			# does not abort the whole day's delivery batch and does not leave any
			# partial writes (e.g. a half-created Delivery Note) behind.
			savepoint = "sd_" + frappe.generate_hash(length=8)
			frappe.db.savepoint(savepoint)
			try:
				rows = self._fetch_delivery_rows_for_order(so_name)
				for row in rows:
					self.append("items", row)
			except Exception:
				frappe.db.rollback(save_point=savepoint)
				failed_orders.append(so_name)
				frappe.log_error(
					title="Subscription Delivery: order skipped",
					message="Delivery Date: {0}\nSales Order: {1}\n\n{2}".format(
						self.delivery_date, so_name, frappe.get_traceback()
					),
				)

		if failed_orders:
			frappe.log_error(
				title="Subscription Delivery: orders skipped summary",
				message="Delivery Date {0}: {1} subscription(s) failed and were skipped:\n{2}".format(
					self.delivery_date, len(failed_orders), ", ".join(failed_orders)
				),
			)
			# Surface to the operator when run interactively (manual "Fetch Deliveries").
			if frappe.request:
				frappe.msgprint(
					_("{0} subscription(s) were skipped due to errors and need attention: {1}").format(
						len(failed_orders), ", ".join(failed_orders)
					),
					indicator="orange",
				)

	def _fetch_delivery_rows_for_order(self, so_name):
		"""Build the delivery item rows for a single subscription on this delivery date.

		Returns a list of row dicts (empty if the order has nothing due on this date).
		Raises on failure so the caller can isolate and skip the order.
		"""
		so = frappe.get_doc("Sales Order", so_name)

		for dd in so.delivery_dates:
			if getdate(dd.delivery_date) == getdate(self.delivery_date) and dd.status == "Paused":
				return []

		has_delivery = any(
			getdate(i.delivery_date) == getdate(self.delivery_date) for i in so.items
		)
		if not has_delivery:
			return []

		existing_dn = frappe.db.get_value(
			"Delivery Note",
			{"subscription": so_name, "posting_date": self.delivery_date, "docstatus": ["!=", 2]},
		)
		if not existing_dn:
			delivery_date_str = str(self.delivery_date)
			frappe.flags.args = frappe._dict({"delivery_dates": [delivery_date_str], "for_reserved_stock": True})
			dn = make_delivery_note(so_name, kwargs={"delivery_dates": [delivery_date_str], "for_reserved_stock": True})
			if not dn.items:
				return []
			dn.set_posting_time = 1
			dn.posting_date = self.delivery_date
			dn.save()
		else:
			dn = frappe.get_doc("Delivery Note", existing_dn)

		rows = []
		for i in dn.items:
			rows.append({
				"customer": so.customer,
				"sales_order": so.name,
				"sales_order_item": i.so_detail,
				"item_code": i.item_code,
				"item_name": i.item_name,
				"uom": i.uom,
				"meal": i.meal,
				"note": i.note,
				"qty": i.qty,
				"delivery_note": dn.name,
				"delivery_note_item": i.name,
			})
		return rows


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

		





