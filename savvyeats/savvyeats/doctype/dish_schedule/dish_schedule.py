# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, cint

class DishSchedule(Document):
	def validate(self):
		self.validate_duplicate()
		self.ensure_single_default_per_group()
		self.status = "Unpublished"
		self.title = getdate(self.date).strftime("%A, %B %d, %Y")

	def set_meals_json(self):
		self.schedule_json = {}
		dish_plans = frappe.get_all("Dish Plan", filters={"enabled": 1}, order_by="sorting_order asc")
		for dp in dish_plans:
			self.schedule_json[dp.name] = self.get_items(dp.name)


	def ensure_single_default_per_group(self):
		groups = {}
		for row in (self.items or []):
			key = (row.meal or "", row.dish_plan or "")
			groups.setdefault(key, []).append(row)

		for key, rows in groups.items():
			if not rows:
				continue

			rows.sort(key=lambda r: (r.idx or 0))
			keep = next((r for r in rows if cint(r.default)), None)
			if not keep:
				keep = rows[0]
				keep.default = 1
			for r in rows:
				r.default = 1 if (r is keep) else 0

	def get_items(self, dish_plan):
		result = {}
		meals = frappe.get_all("Meal", filters={"enabled": 1}, order_by="sorting_order asc")
		for m in meals:
			result[m.name] = []
			for d in self.items:
				if d.dish_plan == dish_plan and m.name == d.meal:
					d = d.as_dict()
					del d["modified"]
					del d["creation"]
					result[m.name].append(d)

		return result



	def validate_duplicate(self):
		duplicate = frappe.get_all("Dish Schedule", filters={"date": self.date, "name": ["!=", self.name]})

		if duplicate:
			frappe.throw(_("Dish Schedule for Date: <b>{0}</b> already exist.".format(self.get_formatted("date"))))

	@frappe.whitelist()
	def add_items(self, meal, items):
		meals = {}
		for d in self.items:
			if not d.meal in meals:
				meals[d.meal] = []
			if d.dish_plan not in meals[d.meal]:
				meals[d.meal].append(d.dish_plan)

		idx = 0
		for d in items:
			variants = frappe.get_all("Item", filters={"disabled": 0, "variant_of": d})
			for v in variants:
				item = frappe.get_doc("Item", v.name)
				for dp in item.dish_plans:
					row = self.append("items", {})
					row.item_code = item.item_code
					row.item_name = item.item_name
					row.meal = meal
					row.dish_plan = dp.dish_plan

		self.save()

@frappe.whitelist()
def publish_dish_schedule(dish_schedule_id):
	dish_schedule = frappe.get_doc("Dish Schedule", dish_schedule_id)
	dish_schedule.set_meals_json()
	dish_schedule.status = "Published"
	dish_schedule.flags.ignore_validate = True
	dish_schedule.save()
	dish_schedule.clear_cache()
	frappe.get_cached_doc("Dish Schedule", dish_schedule_id)

