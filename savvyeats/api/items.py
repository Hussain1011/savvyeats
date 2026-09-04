import frappe
from savvyeats.api.user import send_error_response, send_success_response
from frappe.utils import getdate, get_date_str, flt
import json
from erpnext.stock.get_item_details import get_item_price
from savvyeats.api.order import validate_sales_order
from savvyeats.api.utils import is_my_way_plan
import re

@frappe.whitelist(methods=["GET"])
def get_plan_items(order_id):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order


	dish_schedule = frappe.get_all("Dish Schedule", filters={"status": "Published", "date": ["between", [order.start_date, order.end_date]]}, fields="*")
	schedule = {}
	data = {}
	week_plan = frappe.get_cached_doc("Week Plan", order.week_plan)
	counter = len(week_plan.days)
	for d in dish_schedule:
		schedule[getdate(d.date)] = d
	count = 1
	for d in order.delivery_dates:
		# if count > counter:
		# 	break
		count += 1
		data[get_date_str(d.delivery_date)] = {}
		if getdate(d.delivery_date) in schedule:
			s = json.loads(schedule[getdate(d.delivery_date)]["schedule_json"])
			if order.dish_plan in s:
				dish_plan = s[order.dish_plan]
				for i,v in dish_plan.items():
					for x in v:
						x["doc"] = frappe.get_cached_doc("Item", x["item_code"]).as_dict()
						item_name = x["doc"].item_name.rsplit("-", 1)[0].strip()
						x["doc"].item_name = item_name
						x["item_name"] = item_name

				data[get_date_str(d.delivery_date)] = dish_plan

	return send_success_response("", "", {"dates":data, "addons": get_add_ons(as_dict=True)})

@frappe.whitelist(methods=["GET"])
def get_add_ons(as_dict=False):
	addons = frappe.get_all("Item", filters={"disabled": 0, "item_category": "Add-on"})
	selling_price_list = frappe.db.get_value("Selling Settings", None, "selling_price_list")
	args = {
		"price_list": selling_price_list,
		"transaction_date": getdate()
	}

	for d in addons:
		d.doc = frappe.get_cached_doc("Item", d.name)
		args["uom"] = d.doc.stock_uom
		price = get_item_price(args, d.name)
		if price:
			d.rate = price[0][1]

	if as_dict:
		return addons

	return send_success_response("", "", addons)





@frappe.whitelist(methods=["GET"])
def get_plan_components(order_id):
	"""Catalogue for the MY WAY builder: components grouped by Component Category.

	Deliberately not folded into get_plan_items. That endpoint is built entirely
	around Dish Schedule — it walks the order's delivery dates and reads a Published
	schedule per date. MY WAY has no per-date schedule: its catalogue is flat and
	identical on every delivery day, so routing it through the dated path would mean
	fabricating a schedule row per date for a list that never changes.
	"""
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	if not is_my_way_plan(order.dish_plan):
		# Not an error. The app shows its empty state for a plan with nothing to build,
		# and this keeps an older/other plan from getting a hard failure if it ever asks.
		return send_success_response("", "", {"categories": []})

	# Components are scoped to the plan through Item.dish_plans, the same Table
	# MultiSelect the dish items already use.
	plan_item_codes = frappe.get_all(
		"Item Dish Plans",
		filters={"dish_plan": order.dish_plan, "parenttype": "Item"},
		pluck="parent",
	)

	items = []
	if plan_item_codes:
		items = frappe.get_all(
			"Item",
			filters={
				"name": ["in", plan_item_codes],
				"disabled": 0,
				"item_category": "Ingredient",
				"component_category": ["is", "set"],
			},
			fields=[
				"name",
				"item_code",
				"item_name",
				"component_category",
				"serving_size",
				"step_grams",
				"max_portion_grams",
			],
			order_by="item_name asc",
		)

	if not items:
		message_en = "No components are configured for this plan."
		message_ar = "لا توجد مكونات مهيأة لهذه الخطة."
		errors = {
			"no_components_configured": ["No components are configured for this plan."]
		}
		return send_error_response(message_en, message_ar, errors)

	selling_price_list = frappe.db.get_value("Selling Settings", None, "selling_price_list")
	price_args = {
		"price_list": selling_price_list,
		"transaction_date": getdate(),
	}

	grouped = {}
	skipped = []

	for d in items:
		# serving_size is the divisor behind every per-gram number the app shows.
		# A zero would render the whole component as 0 kcal, so leave it out and say so.
		if not d.serving_size or d.serving_size <= 0:
			skipped.append(d.name)
			continue

		doc = frappe.get_cached_doc("Item", d.name).as_dict()

		# The app scales all live macros by grams, so per_gram must never be blank.
		# It is meant to arrive populated from the import; this is the safety net.
		for n in doc.get("nutrients") or []:
			if not n.get("per_gram") and n.get("value"):
				n["per_gram"] = flt(n["value"]) / d.serving_size

		# NOTE: get_plan_items strips a "-suffix" from dish names. Components do not
		# carry that convention, so their names are passed through untouched.

		price = None
		price_row = get_item_price(dict(price_args, uom=doc.stock_uom), d.name)
		if price_row:
			price = price_row[0][1]
		elif doc.standard_rate:
			price = doc.standard_rate

		grouped.setdefault(d.component_category, []).append({
			"item_code": d.item_code or d.name,
			"item_name": d.item_name,
			"serving_size": d.serving_size,
			"step_grams": d.step_grams or None,
			"max_portion_grams": d.max_portion_grams or None,
			"price": price,
			"doc": doc,
		})

	if skipped:
		frappe.log_error(
			title="MY WAY: components without a serving size",
			message="Order {0}: excluded from the builder because serving_size is not set: {1}".format(
				order.name, ", ".join(skipped)
			),
		)

	categories = []
	for c in frappe.get_all(
		"Component Category",
		filters={"enabled": 1},
		fields=["name", "category_name", "sorting_order", "required"],
		order_by="sorting_order asc, category_name asc",
	):
		# A category with nothing available in it has no place in the builder.
		if not grouped.get(c.name):
			continue

		categories.append({
			"code": c.name,
			"label": c.category_name or c.name,
			"sort_order": c.sorting_order,
			"required": c.required,
			"items": grouped[c.name],
		})

	if not categories:
		message_en = "No components are configured for this plan."
		message_ar = "لا توجد مكونات مهيأة لهذه الخطة."
		errors = {
			"no_components_configured": ["No components are configured for this plan."]
		}
		return send_error_response(message_en, message_ar, errors)

	return send_success_response("", "", {"categories": categories})
