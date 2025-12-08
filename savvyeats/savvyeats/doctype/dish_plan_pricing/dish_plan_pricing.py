# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class DishPlanPricing(Document):
	def validate(self):
		self.validate_meals()
		self.validate_duplicate()
		self.clear_cache()

	def validate_meals(self):
		self.total_price = 0
		meals = []
		for d in self.meals:
			if d.meal in meals:
				frappe.throw(_("Duplicate entry for Meal: {0}").format(d.meal))
			meals.append(d.meal)
			self.total_price += d.per_day_price or 0

	def _meal_signature(self, doc=None):
		doc = doc or self
		sig = []

		for d in doc.meals:
			sig.append((d.meal, int(d.mandatory or 0)))

		sig.sort()
		return tuple(sig)

	def validate_duplicate(self):
		if not self.enabled:
			return

		current_sig = self._meal_signature()

		other_pricings = frappe.get_all(
			self.doctype,
			filters={
				"dish_plan": self.dish_plan,
				"enabled": 1,
				"name": ["!=", self.name],
				"docstatus": ["<", 2],
			},
			pluck="name",
		)

		for name in other_pricings:
			other = frappe.get_doc(self.doctype, name)
			other_sig = self._meal_signature(other)

			if other_sig == current_sig:
				frappe.throw(
					_(
						"Duplicate pricing found for Dish Plan {dish_plan}. "
						"Pricing <b>'{pricing}'</b> already has the same meals and required state."
					).format(
						dish_plan=self.dish_plan,
						pricing=other.pricing_name or other.name,
					)
				)

	def on_update(self):
		frappe.get_cached_doc(self.doctype, self.name)
