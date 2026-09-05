import frappe
from frappe.utils import getdate, flt
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery


def update_actual_date_sales_order():
	orders = frappe.get_all("Sales Order", filters={"docstatus": 1, "subscription_status": "Active"})
	for d in orders:
		doc = frappe.get_doc("Sales Order", d.name)
		sales_order_delivery(doc)
		frappe.db.set_value("Sales Order", d.name, "actual_start_date", doc.actual_start_date)
		frappe.db.set_value("Sales Order", d.name, "actual_end_date", doc.actual_end_date)

	frappe.db.commit()


def update_item_kitchen_name():
	items = frappe.get_all("Item", filters={"variant_of": ["!=", ""]})
	attributes = frappe.get_doc("Item Attribute", "Dish Plan")
	att_dict = {}
	for at in attributes.item_attribute_values:
		att_dict[at.attribute_value] = at

	for d in items:
		doc = frappe.get_doc("Item", d.name)
		for a in doc.attributes:
			if a.attribute == "Dish Plan":
				doc.kitchen_name = "{0} - {1}".format(doc.variant_of, att_dict[a.attribute_value].abbr)
				break

		frappe.db.set_value("Item", doc.name, "kitchen_name", doc.kitchen_name)
		frappe.db.commit()


# --- MY WAY setup -----------------------------------------------------------
# MY WAY is configuration, not code: the categories and the meal slots are records.
# These helpers create them idempotently so a site can be brought up (or a category
# added) without hand-building a dozen documents. Pricing is not among them — MY WAY
# is priced per component, straight off each component's Item Price.
# Run with: bench --site <site> execute savvyeats.patches.setup_my_way --kwargs "{...}"

MY_WAY_DEFAULT_CATEGORIES = ["Protein", "Carbs", "Fats", "Fibers"]


def setup_my_way(dish_plan, meal_count=12, categories=None):
	"""Configure a Dish Plan for MY WAY: component categories and meal slots.

	`meal_count` is a seeding decision, not a limit — the client set no maximum meals
	per day, so running out is a config task (raise it and re-run), never a code
	change. The app renders whatever Dish Plan.meals contains.

	No pricing is created. MY WAY costs the sum of the components on the plate, so
	the price lives on each component's Item Price and a Dish Plan Pricing would only
	double-charge; any per-meal pricing left over from an earlier run is retired here.
	"""
	from savvyeats.api.utils import MY_WAY_UI_TYPE

	plan = frappe.get_doc("Dish Plan", dish_plan)
	if plan.ui_type != MY_WAY_UI_TYPE:
		frappe.throw("Dish Plan {0} has ui_type {1}, expected {2}".format(dish_plan, plan.ui_type, MY_WAY_UI_TYPE))

	categories = categories or MY_WAY_DEFAULT_CATEGORIES
	for i, name in enumerate(categories, start=1):
		if not frappe.db.exists("Component Category", name):
			frappe.get_doc({
				"doctype": "Component Category",
				"category_name": name,
				"sorting_order": i,
				"required": 1,
				"enabled": 1,
			}).insert(ignore_permissions=True)

	# max_qty has to clear the category count: the dish path flags every selection
	# past it as an extra, which for a plate would mean components 2..N.
	max_qty = max(len(categories), frappe.db.count("Component Category", {"enabled": 1}))

	existing_meals = {m.meal for m in plan.meals}
	for i in range(1, int(meal_count) + 1):
		meal_name = "Meal {0}".format(i)
		if not frappe.db.exists("Meal", meal_name):
			frappe.get_doc({
				"doctype": "Meal",
				"meal_name": meal_name,
				"mandatory": 0,
				"enabled": 1,
				"sorting_order": i,
			}).insert(ignore_permissions=True)

		# Without a Dish Plan Meals row the meal-membership filter in add_items drops
		# every item sent for that meal and the customer gets an empty order.
		if meal_name not in existing_meals:
			plan.append("meals", {
				"meal": meal_name,
				"mandatory": 0,
				"min_qty": 0,
				"max_qty": max_qty,
				"per_day_price": 0,
			})

	# A per-meal price on a MY WAY slot is a number nothing charges any more, and the
	# app would still show it next to a plate whose real price is its components.
	for m in plan.meals:
		m.per_day_price = 0

	plan.save(ignore_permissions=True)

	retired = retire_my_way_pricing(plan.name)

	frappe.db.commit()

	return {
		"dish_plan": plan.name,
		"meals": int(meal_count),
		"max_qty": max_qty,
		"retired_pricing": retired,
	}


def retire_my_way_pricing(dish_plan):
	"""Take a MY WAY plan off per-meal pricing, without deleting anything.

	Sites configured before component pricing carry a "MY WAY-<plan>" Dish Plan
	Pricing and a default_pricing_plan pointing at it. add_items ignores both for MY
	WAY now, but get_setup_data_v2 would keep serving them to the app as if a plate
	had a flat per-meal price. Disable rather than delete: the rows are still the
	record of what the plan used to charge.
	"""
	retired = []

	for name in frappe.get_all(
		"Dish Plan Pricing", filters={"dish_plan": dish_plan, "enabled": 1}, pluck="name"
	):
		frappe.db.set_value("Dish Plan Pricing", name, "enabled", 0)
		retired.append(name)

	if frappe.db.get_value("Dish Plan", dish_plan, "default_pricing_plan"):
		frappe.db.set_value("Dish Plan", dish_plan, "default_pricing_plan", None)

	return retired


def backfill_component_per_gram():
	"""Fill Item Nutrients.per_gram wherever the import left it blank.

	The app scales every live macro by grams, so a nutrient row with a value and no
	per_gram shows the customer 0 kcal with no error — the quietest way this feature
	can fail.
	"""
	rows = frappe.db.sql("""
		SELECT n.name, n.value, i.serving_size, n.parent
		FROM `tabItem Nutrients` n
		INNER JOIN `tabItem` i ON i.name = n.parent
		WHERE n.parenttype = 'Item'
			AND IFNULL(n.per_gram, 0) = 0
			AND IFNULL(n.value, 0) != 0
			AND IFNULL(i.serving_size, 0) > 0
	""", as_dict=True)

	for r in rows:
		frappe.db.set_value(
			"Item Nutrients", r.name, "per_gram", flt(r.value) / flt(r.serving_size), update_modified=False
		)

	frappe.db.commit()

	missing = frappe.db.sql("""
		SELECT DISTINCT n.parent
		FROM `tabItem Nutrients` n
		INNER JOIN `tabItem` i ON i.name = n.parent
		WHERE n.parenttype = 'Item'
			AND i.component_category IS NOT NULL AND i.component_category != ''
			AND IFNULL(i.serving_size, 0) <= 0
	""", pluck="parent")

	return {"backfilled": len(rows), "components_without_serving_size": missing}
