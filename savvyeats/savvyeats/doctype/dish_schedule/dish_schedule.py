# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate



class DishSchedule(Document):
	def validate(self):
		self.validate_duplicate()
		self.title = getdate(self.date).strftime("%A, %B %d, %Y")

	def validate_duplicate(self):
		duplicate = frappe.get_all("Dish Schedule", filters={"date": self.date, "name": ["!=", self.name]})

		if duplicate:
			frappe.throw(_("Dish Schedule for Date: <b>{0}</b> already exist."))
