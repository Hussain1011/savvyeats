# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class DishPlanPricing(Document):
	def validate(self):
		self.validate_meals()
		self.clear_cache()

	def validate_meals(self):
		self.total_price = 0
		meals = []
		for d in self.meals:
			if d.meal in meals:
				frappe.throw(_("Duplicate entry for Meal: {0}".format(d.meal)))
			meals.append(d.meal)
			self.total_price += d.per_day_price or 0

	def on_update(self):
		frappe.get_cached_doc(self.doctype, self.name)
