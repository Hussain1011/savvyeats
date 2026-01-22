import frappe
from savvyeats.api.user import send_error_response, send_success_response
from frappe.utils import flt, cint

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_app_settings():
	doc = frappe.get_cached_doc("App Settings", "App Settings", ignore_permmission=True)
	return send_success_response("", "",doc)

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_about_savvy():
	doc = frappe.get_cached_doc("Web Page", "about-savvy", ignore_permmission=True)

	return send_success_response("", "",doc.main_section_html)

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_terms_and_conditions():
	doc = frappe.get_cached_doc("Web Page", "terms-and-conditions", ignore_permmission=True)

	return send_success_response("", "",doc.main_section_html)

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_privacy_policy():
	doc = frappe.get_cached_doc("Web Page", "terms-and-conditions", ignore_permmission=True)

	return send_success_response("", "",doc.main_section_html)


@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_customer_support_details():
	doc = frappe.get_cached_doc("Customer Support", "Customer Support", ignore_permmission=True)
	return send_success_response("", "",doc)

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_setup_data_v2():
	app_settings = frappe.get_cached_doc("App Settings", "App Settings", ignore_permmission=True)
	dish_plans = frappe.get_all("Dish Plan", filters={"enabled": 1},order_by="sorting_order asc")
	dish_plan_types = frappe.get_all("Dish Plan Type", fields=["*"], filters={"enabled": 1}, order_by="sorting_order asc")
	allergens = frappe.get_all("Allergen", filters={"enabled": 1}, order_by="allergen asc")
	improved_suggestions = frappe.get_all("Improved Suggestions", filters={"enabled": 1}, order_by="improved_suggestion asc")
	delivery_time_slots = frappe.get_all("Delivery Time Slot", filters={"enabled": 1}, fields=["*"], order_by="sorting_order asc")
	data = {"allergens": allergens, "delivery_time_slots": delivery_time_slots, "dish_plans": [], "improved_suggestions": improved_suggestions, "dish_plan_types": []}

	def get_pricing(dish_plan_pricing):
		if not dish_plan_pricing:
			return {}
		a = frappe.get_cached_doc("Dish Plan Pricing", dish_plan_pricing, ignore_permmission=True).as_dict()
		for d in a.meals:
			d.doc = frappe.get_cached_doc("Meal", d.meal, ignore_permmission=True)
		return a

	dish_plan_types_dict = {}

	for dpt in dish_plan_types:
		dish_plan_types_dict[dpt.name] = dpt
		dish_plan_types_dict[dpt.name]["dish_plans"] = []

	for ds in dish_plans:
		dish_plan = frappe.get_cached_doc("Dish Plan", ds.name, ignore_permmission=True).as_dict()
		dish_plan.min_calories = cint(dish_plan.min_calories)
		dish_plan.max_calories = cint(dish_plan.max_calories)
		dish_plan.default_pricing_plan_doc = get_pricing(dish_plan.default_pricing_plan)
		pricings = frappe.get_all("Dish Plan Pricing", filters={"enabled": 1, "dish_plan": dish_plan.name})
		dish_plan.pricings = []
		for d in pricings:
			dish_plan.pricings.append(get_pricing(d.name))
		for wp in dish_plan.week_plans:
			week_plan = frappe.get_cached_doc("Week Plan", wp.week_plan, ignore_permmission=True)
			wp.doc = week_plan
			wp.no_of_days = len(week_plan.days)

		for d in dish_plan.meals:
			d.doc = frappe.get_cached_doc("Meal", d.meal, ignore_permmission=True)
		if app_settings.ui_type == "Standard":
			data["dish_plans"].append(dish_plan)
		elif app_settings.ui_type == "Dish Plan Type":
			if dish_plan.dish_plan_type and dish_plan.dish_plan_type in dish_plan_types_dict:
				dish_plan_types_dict[dish_plan.dish_plan_type]["dish_plans"].append(dish_plan)

	if app_settings.ui_type == "Dish Plan Type":
		for i,v in dish_plan_types_dict.items():
			data["dish_plan_types"].append(v)

	return send_success_response("", "",data)


@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_setup_data():
	dish_plans = frappe.get_all("Dish Plan", filters={"enabled": 1}, order_by="sorting_order asc")
	allergens = frappe.get_all("Allergen", filters={"enabled": 1}, order_by="allergen asc")
	improved_suggestions = frappe.get_all("Improved Suggestions", filters={"enabled": 1}, order_by="improved_suggestion asc")
	delivery_time_slots = frappe.get_all("Delivery Time Slot", filters={"enabled": 1}, fields=["*"], order_by="sorting_order asc")
	data = {"allergens": allergens, "delivery_time_slots": delivery_time_slots, "dish_plans": [], "improved_suggestions": improved_suggestions}

	def get_pricing(dish_plan_pricing):
		if not dish_plan_pricing:
			return {}
		a = frappe.get_cached_doc("Dish Plan Pricing", dish_plan_pricing, ignore_permmission=True).as_dict()
		for d in a.meals:
			d.doc = frappe.get_cached_doc("Meal", d.meal, ignore_permmission=True)
		return a

	for ds in dish_plans:
		dish_plan = frappe.get_cached_doc("Dish Plan", ds.name, ignore_permmission=True).as_dict()
		dish_plan.min_calories = cint(dish_plan.min_calories)
		dish_plan.max_calories = cint(dish_plan.max_calories)
		dish_plan.default_pricing_plan_doc = get_pricing(dish_plan.default_pricing_plan)
		pricings = frappe.get_all("Dish Plan Pricing", filters={"enabled": 1, "dish_plan": dish_plan.name})
		dish_plan.pricings = []
		for d in pricings:
			dish_plan.pricings.append(get_pricing(d.name))
		for wp in dish_plan.week_plans:
			week_plan = frappe.get_cached_doc("Week Plan", wp.week_plan, ignore_permmission=True)
			wp.doc = week_plan
			wp.no_of_days = len(week_plan.days)

		for d in dish_plan.meals:
			d.doc = frappe.get_cached_doc("Meal", d.meal, ignore_permmission=True)
			
		data["dish_plans"].append(dish_plan)


	return send_success_response("", "",data)


