import frappe
import json
from savvyeats.data_import.connection import run_external_mysql_query
import time

def execute():
	fetch_allergens()


def fetch_allergens():
	records = run_external_mysql_query("select * from allergens")
	for d in records:
		doc = frappe.new_doc("Allergen")
		doc.allergen = d["name"]
		doc.save()

	frappe.db.commit()

def fetch_nutrients():
	records = run_external_mysql_query("select * from nutrients")
	units = run_external_mysql_query("select * from units")
	for i in units:
		print(units)

	u = {
		1: "Gram",
		2: "Kilocalorie"
	}
	for d in records:
		print(d)
		doc = frappe.new_doc("Nutrient")
		doc.nutrient = d["name"]
		doc.uom = u[d["unit_id"]]
		doc.save()

	frappe.db.commit()


def fetch_ingredients():
	u = {
		1: "Gram",
		2: "Kilocalorie",
		3: "Nos"
	}
	n = {}
	nutrients = run_external_mysql_query("select * from nutrients")
	for nu in nutrients:
		n[nu["id"]] = nu

	records = run_external_mysql_query("select * from food where type = 'INGREDIENT' ")
	for d in records:
		data = json.loads(d["data"])
		doc = frappe.new_doc("Item")
		doc.item_code = d["client_name"]
		doc.item_name = d["client_name"]
		doc.kitchen_name = d["kitchen_name"]
		doc.item_category = "Ingredient"
		doc.item_group = "Raw Material"
		doc.uom = u[data["unit_id"]]
		doc.is_stock_item = 1
		doc.valuation_rate = data["purchase_price"]
		doc.serving_size = data["serving_size"]

		for i in data["nutrients"]:
			nut = n[i["id"]]
			r = doc.append("nutrients", {})
			r.nutrient = nut["name"]
			r.value = i["value"]

		try:
			doc.save()
		except Exception as e:
			pass


	frappe.db.commit()


def fetch_sub_recipe():
	u = {
		1: "Gram",
		2: "Kilocalorie",
		3: "Nos"
	}
	m = {}
	materials = run_external_mysql_query("select * from food")
	for mt in materials:
		m[mt["id"]] = mt

	records = run_external_mysql_query("select * from food where type = 'SUB_RECIPE' ")
	for d in records:
		data = json.loads(d["data"])
		doc = frappe.new_doc("BOM")
		doc.item = d["client_name"]
		doc.is_active = 1
		doc.is_default = 1
		doc.set_rate_of_sub_assembly_item_based_on_bom = 1
		doc.quantity = data["netQuantity"]
		print(data["materials"])
		for i in data["materials"]:
			if i["food_id"] == 335:
				i["food_id"] = 153
			item = m[i["food_id"]]
			row = doc.append("items", {})
			row.item_code = item["client_name"]
			row.qty = i["grossQuantity"]


		# doc.item_code = d["client_name"]
		# doc.item_name = d["client_name"]
		# doc.kitchen_name = d["kitchen_name"]
		# doc.item_category = "Sub Recipe"
		# doc.item_group = "Sub Assemblies"
		# doc.uom = u[data["unit_id"]]
		# doc.is_stock_item = 1
		#doc.valuation_rate = data["purchase_price"]
		# doc.serving_size = data["serving_size"]

	# 	for i in data["nutrients"]:
	# 		nut = n[i["id"]]
	# 		r = doc.append("nutrients", {})
	# 		r.nutrient = nut["name"]
	# 		r.value = i["value"]

		try:
			doc.save()
		except Exception as e:
			print(e)


	frappe.db.commit()


def fetch_meals():
	records = run_external_mysql_query("select * from meals")
	for d in records:
		print(d)
		doc = frappe.new_doc("Meal")
		doc.meal_name = d["name"]
		quotes = json.loads(d["quotes"])
		for q in quotes:
			row = doc.append("quotes", {})
			row.quote = q.replace("\\", "")
			
		doc.save()

	frappe.db.commit()

def fetch_dish_plans():
	m = {}
	meals = run_external_mysql_query("select * from meals")
	for ml in meals:
		m[ml["id"]] = ml
	records = run_external_mysql_query("select * from dish_plans")
	for d in records:
		doc = frappe.new_doc("Dish Plan")
		doc.plan_name = d["name"]
		doc.week_plan = "Sun - Thu"
		doc.plan_description = d["description"].replace("\\", "")
		doc.min_calories = d["minCalories"]
		doc.max_calories = d["maxCalories"]
		for i in json.loads(d["meals"]):
			row = doc.append("meals", {})
			row.meal = m[int(i)]["name"]
		doc.save()

	frappe.db.commit()

def fetch_dish():
	u = {
		1: "Gram",
		2: "Kilocalorie",
		3: "Nos"
	}

	a = {}
	allergens = run_external_mysql_query("select * from allergens")
	for al in allergens:
		a[al["id"]] = al

	dp = {}
	dish_plans = run_external_mysql_query("select * from dish_plans")
	for dl in dish_plans:
		dp[dl["id"]] = dl

	m = {}
	materials = run_external_mysql_query("select * from food")
	for mt in materials:
		m[mt["id"]] = mt

	records = run_external_mysql_query("select * from food where type = 'DISH' ")
	duplicates = {}
	for dpl in records:
		if dpl["client_name"] in duplicates:
			duplicates[dpl["client_name"]].append(dpl["client_name"])
		else:
			duplicates[dpl["client_name"]] = [dpl["client_name"]]


	dish_plans_id = run_external_mysql_query("select * from dish_plan_food")

	dish_plan_id = {}
	for dpi in dish_plans_id:
		if not dpi["food_id"] in dish_plan_id:
			dish_plan_id[dpi["food_id"]] = []

		dish_plan_id[dpi["food_id"]].append(dpi)


	for d in records:
		data = json.loads(d["data"])
		# doc = frappe.new_doc("BOM")
		# doc.item = d["client_name"]
		# doc.is_active = 1
		# doc.is_default = 1
		# doc.set_rate_of_sub_assembly_item_based_on_bom = 1
		# doc.quantity = 1
		# print(data["materials"])

		# if len(data["materials"]) == 1:
		# 	item = m[int(data["materials"][0]["food_id"])]
		# 	if item["client_name"] == d["client_name"]:
		# 		continue

		# for i in data["materials"]:
		# 	if i["food_id"] == 335:
		# 		i["food_id"] = 153
		# 	if i["food_id"] == 303:
		# 		i["food_id"] = 448
		# 	item = m[int(i["food_id"])]
		# 	row = doc.append("items", {})
		# 	row.item_code = item["client_name"]
		# 	row.qty = i["grossQuantity"]

		# doc = frappe.new_doc("Item")
		# doc.item_code = d["client_name"]
		# doc.item_name = d["client_name"]
		# doc.kitchen_name = d["kitchen_name"]
		# doc.item_category = "Dish"
		# doc.item_group = "Products"
		# doc.uom = u[3]
		# doc.is_stock_item = 1
		name = d["client_name"]
		if d["id"] in dish_plan_id:
			for ds in dish_plan_id[d["id"]]:
				# row = doc.append("dish_plans", {})
				# row.dish_plan = dp[ds["dish_plan_id"]]["name"]
				dish_plan_attached = dp[ds["dish_plan_id"]]["name"]

		if d["client_name"] in duplicates and len(duplicates[d["client_name"]]) > 1:
			name = "{0} - {1}".format(d["client_name"], dish_plan_attached)
		try:
			doc = frappe.get_doc("BOM", {"item": name})
			for b in doc.items:
				item = frappe.get_doc("Item", b.item_code)
				if item.item_category == "Sub Recipe":
					try:
						b.bom_no = frappe.get_doc("BOM", {"item": b.item_code}).name
					except Exception as e:
						pass
		except Exception as e:
			pass
		# doc = frappe.get_doc("Item", name)
		# doc.image = "/files/Dish.png"
		# print(doc.item_code)

		# if "allergens" in data:
		# 	for i in data["allergens"]:
		# 		if i == 31:
		# 			continue
		# 		r = doc.append("allergens", {})
		# 		r.allergen = a[int(i)]["name"]

	# 	for i in data["nutrients"]:
	# 		nut = n[i["id"]]
	# 		r = doc.append("nutrients", {})
	# 		r.nutrient = nut["name"]
	# 		r.value = i["value"]

		try:
			doc.flags.ignore_validate = True
			doc.save()

		except Exception as e:
			print("error")
			print(doc.name)
			print(e)
			print("error end")

		#time.sleep(1)


	frappe.db.commit()