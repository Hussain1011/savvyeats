# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class WeekPlan(Document):
	def validate(self):
		self.validate_duplicates()

	def validate_duplicates(self):
		days = []
		for d in self.days:
			if d.day in days:
				frappe.throw(_("Duplicate Entry for Day: <b>{0}</b>".format(d.day)))
			days.append(d.day)
			
