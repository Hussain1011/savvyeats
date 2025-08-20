import frappe
from savvyeats.api.user import send_error_response, send_success_response
from frappe.utils import getdate,get_date_str
import json

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
	for d in dish_schedule:
		schedule[getdate(d.date)] = d

	for d in order.delivery_dates:
		data[get_date_str(d.delivery_date)] = {}
		if getdate(d.delivery_date) in schedule:
			s = json.loads(schedule[getdate(d.delivery_date)]["schedule_json"])
			if order.dish_plan in s:
				dish_plan = s[order.dish_plan]
				for i,v in dish_plan.items():
					for x in v:
						x["doc"] = frappe.get_cached_doc("Item", x["item_code"]).as_dict()

				data[get_date_str(d.delivery_date)] = dish_plan

	return send_success_response("", "", data)





