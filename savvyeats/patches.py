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
# MY WAY is configuration, not code: the categories, the meal slots and the meal
# header item are all records. These helpers create them idempotently so a site
# can be brought up (or a category added) without hand-building a dozen documents.
# Run with: bench --site <site> execute savvyeats.patches.setup_my_way --kwargs "{...}"

MY_WAY_DEFAULT_CATEGORIES = ["Protein", "Carbs", "Fats", "Fibers"]


def setup_my_way(dish_plan, per_day_price, meal_count=12, categories=None):
	"""Configure a Dish Plan for MY WAY: categories, meal slots, pricing, header item.

	`meal_count` is a seeding decision, not a limit — the client set no maximum meals
	per day, so running out is a config task (raise it and re-run), never a code
	change. The app renders whatever Dish Plan.meals contains.
	"""
	from savvyeats.api.utils import MY_WAY_MEAL_ITEM_CODE, MY_WAY_UI_TYPE

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

	create_my_way_meal_item()

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
				"per_day_price": per_day_price,
			})

	plan.save(ignore_permissions=True)

	pricing_name = create_my_way_pricing(plan, per_day_price, meal_count)
	if plan.default_pricing_plan != pricing_name:
		frappe.db.set_value("Dish Plan", plan.name, "default_pricing_plan", pricing_name)

	frappe.db.commit()

	return {"dish_plan": plan.name, "pricing": pricing_name, "meals": int(meal_count), "max_qty": max_qty}


def create_my_way_pricing(plan, per_day_price, meal_count):
	"""One pricing document for the whole plan, every meal at the same per-day price.

	MY WAY has no maximum meals per day, so pricing cannot be matched by exact meal
	set the way dish plans are — that needs one document per possible meal count.
	add_items skips the set match for MY WAY and reads this as default_pricing_plan.
	"""
	pricing_name = "MY WAY-{0}".format(plan.name)

	if frappe.db.exists("Dish Plan Pricing", pricing_name):
		pricing = frappe.get_doc("Dish Plan Pricing", pricing_name)
		pricing.meals = []
	else:
		pricing = frappe.new_doc("Dish Plan Pricing")
		pricing.pricing_name = "MY WAY"
		pricing.dish_plan = plan.name

	pricing.enabled = 1
	for i in range(1, int(meal_count) + 1):
		pricing.append("meals", {
			"meal": "Meal {0}".format(i),
			"mandatory": 0,
			"min_qty": 0,
			"max_qty": 1,
			"per_day_price": per_day_price,
		})

	pricing.save(ignore_permissions=True)

	return pricing.name


def create_my_way_meal_item():
	"""The non-food row that carries a plate's price, one per (delivery date, meal).

	Modelled on the existing "Item Not Selected" placeholder: not stocked, not sold
	on its own. Show it on the kitchen ticket as the meal heading; suppress it on the
	customer-facing delivery label and menu.
	"""
	from savvyeats.api.utils import MY_WAY_MEAL_ITEM_CODE

	if frappe.db.exists("Item", MY_WAY_MEAL_ITEM_CODE):
		return MY_WAY_MEAL_ITEM_CODE

	# Follow whatever the placeholder item already uses on this site, so the new row
	# lands in the same item group and UOM as the one add_items already inserts.
	template = frappe.db.get_value(
		"Item", "Item Not Selected", ["item_group", "stock_uom"], as_dict=True
	) or frappe._dict()

	item = frappe.new_doc("Item")
	item.item_code = MY_WAY_MEAL_ITEM_CODE
	item.item_name = MY_WAY_MEAL_ITEM_CODE
	item.item_group = template.get("item_group") or frappe.db.get_single_value(
		"Stock Settings", "item_group"
	) or "All Item Groups"
	item.stock_uom = template.get("stock_uom") or frappe.db.get_single_value(
		"Stock Settings", "stock_uom"
	) or "Nos"
	item.item_category = "Dish"
	item.is_stock_item = 0
	item.is_sales_item = 1
	item.is_purchase_item = 0
	item.include_item_in_manufacturing = 0
	item.description = "MY WAY meal. Carries the per-meal price; the components under it are priced at zero."
	item.insert(ignore_permissions=True)

	return item.name


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
