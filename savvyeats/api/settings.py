import frappe
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_app_settings():
	doc = frappe.get_cached_doc("App Settings", "App Settings", ignore_permmission=True)
	return send_success_response("", "",doc)


@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_customer_support_details():
	doc = frappe.get_cached_doc("Customer Support", "Customer Support", ignore_permmission=True)
	return send_success_response("", "",doc)

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_setup_data():
	dish_plans = frappe.get_all("Dish Plan", filters={"enabled": 1}, order_by="sorting_order asc")
	allergens = frappe.get_all("Allergen", filters={"enabled": 1}, order_by="allergen asc")
	delivery_time_slots = frappe.get_all("Delivery Time Slot", filters={"enabled": 1}, fields=["*"], order_by="sorting_order asc")
	data = {"allergens": allergens, "delivery_time_slots": delivery_time_slots, "dish_plans": []}

	def get_pricing(dish_plan_pricing):
		if not dish_plan_pricing:
			return {}
		a = frappe.get_cached_doc("Dish Plan Pricing", dish_plan_pricing, ignore_permmission=True).as_dict()
		for d in a.meals:
			d.doc = frappe.get_cached_doc("Meal", d.meal, ignore_permmission=True)
		return a

	for ds in dish_plans:
		dish_plan = frappe.get_cached_doc("Dish Plan", ds.name, ignore_permmission=True).as_dict()

		dish_plan.default_pricing_plan_doc = get_pricing(dish_plan.default_pricing_plan)
		pricings = frappe.get_all("Dish Plan Pricing", filters={"enabled": 1, "dish_plan": dish_plan.name})
		dish_plan.pricings = []
		for d in pricings:
			dish_plan.pricings.append(get_pricing(d.name))
		for wp in dish_plan.week_plans:
			week_plan = frappe.get_cached_doc("Week Plan", wp.week_plan, ignore_permmission=True)
			wp.doc = week_plan
			wp.no_of_days = len(week_plan.days)
		data["dish_plans"].append(dish_plan)


	return send_success_response("", "",data)


