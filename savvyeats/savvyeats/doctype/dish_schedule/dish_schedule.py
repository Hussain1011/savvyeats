# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, cint

class DishSchedule(Document):
	def onload(self):
		for d in self.items:
			d.item_name = frappe.db.get_value("Item", d.item_code, "item_name")

	def validate(self):
		self.validate_duplicate()
		self.ensure_default_count_per_group()
		self.status = "Unpublished"
		self.title = getdate(self.date).strftime("%A, %B %d, %Y")

	def set_meals_json(self):
		self.schedule_json = {}
		dish_plans = frappe.get_all("Dish Plan", filters={"enabled": 1}, order_by="sorting_order asc")
		for dp in dish_plans:
			self.schedule_json[dp.name] = self.get_items(dp.name)

	def ensure_default_count_per_group(self):
		"""
		Enforce default count per (dish_plan, meal) based on Dish Plan Meals.min_qty
		Example: FULL-ON + Breakfast => 1 default
		         FULL-ON + Meals     => 2 defaults
		         FULL-ON + Snacks    => 2 defaults
		"""

		# Build requirements: {(dish_plan, meal): min_qty}
		req = {}
		plans = {r.dish_plan for r in (self.items or []) if r.dish_plan}
		if plans:
			# Dish Plan Meals is the child table doctype in your JSON: "Dish Plan Meals"
			rows = frappe.get_all(
				"Dish Plan Meals",
				filters={"parent": ["in", list(plans)], "parenttype": "Dish Plan"},
				fields=["parent as dish_plan", "meal", "min_qty", "mandatory"]
			)
			for r in rows:
				req[(r.dish_plan or "", r.meal or "")] = cint(r.min_qty)  # mandatory can be used later if needed

		# Group schedule rows by (meal, dish_plan)
		groups = {}
		for row in (self.items or []):
			key = (row.dish_plan or "", row.meal or "")
			groups.setdefault(key, []).append(row)

		# Enforce defaults per group
		for key, rows in groups.items():
			if not rows:
				continue

			required = cint(req.get(key, 1))  # fallback to 1 if not found (or set to 0 if you prefer)
			rows.sort(key=lambda r: (cint(r.idx) or 0))

			# Current default rows in stable order
			default_rows = [r for r in rows if cint(r.default)]
			non_default_rows = [r for r in rows if not cint(r.default)]

			# Trim defaults if too many
			kept = default_rows[:required]

			# Add more defaults if too few
			if len(kept) < required:
				need = required - len(kept)
				kept.extend(non_default_rows[:need])

			kept_set = set(id(r) for r in kept)
			for r in rows:
				r.default = 1 if id(r) in kept_set else 0

			# Optional: if you want to warn when you don't even have enough items to satisfy min_qty
			if required > len(rows):
				frappe.msgprint(
					_("Not enough items for {0} / {1}. Required {2}, found {3}. Defaults set to all available.")
					.format(key[0], key[1], required, len(rows))
				)


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


		dish_plans_list = frappe.get_all("Dish Plan")
		dish_plan_meals = frappe._dict()
		for dpl in dish_plans_list:
			dish_plan = frappe.get_doc("Dish Plan", dpl.name)
			dish_plan_meals[dpl.name] = []
			for m in dish_plan.meals:
				dish_plan_meals[dpl.name].append(m.meal)

		idx = 0
		for d in items:
			variants = frappe.get_all("Item", filters={"disabled": 0, "variant_of": d})
			if variants:
				for v in variants:
					item = frappe.get_doc("Item", v.name)
					for dp in item.dish_plans:
						dish_plan_meal = dish_plan_meals[dp.dish_plan]

						if meal not in dish_plan_meal:
							continue

						row = self.append("items", {})
						row.item_code = item.item_code
						row.item_name = item.item_name
						row.meal = meal
						row.dish_plan = dp.dish_plan
			else:
				item = frappe.get_doc("Item", d)
				if not item.variant_of and not item.has_variants:
					for dp in item.dish_plans:
						dish_plan_meal = dish_plan_meals[dp.dish_plan]

						if meal not in dish_plan_meal:
							continue
						row = self.append("items", {})
						row.item_code = item.item_code
						row.item_name = item.item_name
						row.meal = meal
						row.dish_plan = dp.dish_plan

		self.save()

	def validate_default_counts_for_publish(self):
		"""
		At publish time:
		For each (dish_plan, meal) in this schedule, ensure #defaults == Dish Plan Meals.min_qty.
		Throw an error if mismatch.
		"""

		# Build required defaults: {(dish_plan, meal): min_qty}
		req = {}
		plans = {r.dish_plan for r in (self.items or []) if r.dish_plan}
		if plans:
			rows = frappe.get_all(
				"Dish Plan Meals",
				filters={"parent": ["in", list(plans)], "parenttype": "Dish Plan"},
				fields=["parent as dish_plan", "meal", "min_qty", "mandatory"]
			)
			for r in rows:
				# If you only want to enforce mandatory ones, check r.mandatory here
				req[(r.dish_plan or "", r.meal or "")] = cint(r.min_qty)

		# Count defaults per (dish_plan, meal)
		counts = {}
		totals = {}
		for row in (self.items or []):
			key = (row.dish_plan or "", row.meal or "")
			totals[key] = totals.get(key, 0) + 1
			if cint(row.default):
				counts[key] = counts.get(key, 0) + 1

		# Validate
		errors = []
		for key, required in req.items():
			got = cint(counts.get(key, 0))
			total = cint(totals.get(key, 0))
			if got != required:
				errors.append(
					f"- Dish Plan <b>{key[0]}</b>, Meal <b>{key[1]}</b>: "
					f"required defaults <b>{required}</b>, found <b>{got}</b> (items: {total})"
				)

		if errors:
			frappe.throw(
				_("Cannot publish. Default item selection does not match Dish Plan Minimum QTY:<br>{0}")
				.format("<br>".join(errors))
			)

@frappe.whitelist()
def publish_dish_schedule(dish_schedule_id):
	dish_schedule = frappe.get_doc("Dish Schedule", dish_schedule_id)
	dish_schedule.validate_default_counts_for_publish()
	dish_schedule.set_meals_json()
	dish_schedule.status = "Published"
	dish_schedule.flags.ignore_validate = True
	dish_schedule.save()
	dish_schedule.clear_cache()
	frappe.get_cached_doc("Dish Schedule", dish_schedule_id)

