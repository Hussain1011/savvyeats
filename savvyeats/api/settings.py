import frappe
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_app_settings():
	doc = frappe.get_cached_doc("App Settings", "App Settings", ignore_permmission=True)
	return send_success_response("", "",doc)

@frappe.whitelist(methods=["GET"])
def get_setup_data():
	dish_plans = frappe.get_all("Dish Plan", filters={"enabled": 1})
	allergens = frappe.get_all("Allergen", filters={"enabled": 1})
	delivery_time_slots = frappe.get_all("Delivery Time Slot", filters={"enabled": 1}, fields=["*"])
	data = {"allergens": allergens, "delivery_time_slots": delivery_time_slots, "dish_plans": []}

	for ds in dish_plans:
		dish_plan = frappe.get_cached_doc("Dish Plan", ds.name, ignore_permmission=True).as_dict()
		for m in dish_plan.meals:
			m.doc = frappe.get_cached_doc("Meal", m.meal, ignore_permmission=True)
		for wp in dish_plan.week_plans:
			week_plan = frappe.get_cached_doc("Week Plan", wp.week_plan, ignore_permmission=True)
			wp.doc = week_plan
			wp.no_of_days = len(week_plan.days)
		data["dish_plans"].append(dish_plan)


	return send_success_response("", "",data)


