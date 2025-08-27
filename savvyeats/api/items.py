import frappe
from savvyeats.api.user import send_error_response, send_success_response
from frappe.utils import getdate, get_date_str
import json
from erpnext.stock.get_item_details import get_item_price

@frappe.whitelist(methods=["GET"])
def get_plan_items(order_id):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)


	dish_schedule = frappe.get_all("Dish Schedule", filters={"status": "Published", "date": ["between", [order.start_date, order.end_date]]}, fields="*")
	schedule = {}
	data = {}
	week_plan = frappe.get_cached_doc("Week Plan", order.week_plan)
	counter = len(week_plan.days)
	for d in dish_schedule:
		schedule[getdate(d.date)] = d
	count = 1
	for d in order.delivery_dates:
		if count > counter:
			break
		count += 1
		data[get_date_str(d.delivery_date)] = {}
		if getdate(d.delivery_date) in schedule:
			s = json.loads(schedule[getdate(d.delivery_date)]["schedule_json"])
			if order.dish_plan in s:
				dish_plan = s[order.dish_plan]
				for i,v in dish_plan.items():
					for x in v:
						x["doc"] = frappe.get_cached_doc("Item", x["item_code"]).as_dict()

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



