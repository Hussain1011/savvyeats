import frappe
import json
from savvyeats.data_import.connection import run_external_mysql_query
import time
import os
import math

def execute():
	fetch_allergens()


def update_meal_plan():
	docs = frappe.get_all("Item", filters={"item_category": "Dish", "has_variants": 0})
	for d in docs:
		doc = frappe.get_doc("Item", d.name)
		doc.append("dish_plans", {"dish_plan": doc.attributes[0].attribute_value})
		doc.save()

	frappe.db.commit()


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


def get_file(filename):
	path = os.path.join(os.path.dirname(__file__))
	return os.path.join(path, filename)

def fetch_ingredients():
	u = {
		1: "Gram",
		2: "Kilocalorie",
		3: "Nos"
	}

	nutrients = {
		"Calories": ["Calories", "Cal / Gr", "Kilocalorie"],
		"Protein": ["Protein (g)", "Protein / g", "Gram"],
		"Fats": ["Fat (g)", "Fat / g", "Gram"],
		"Carbs": ["Carbs (g)", "N. Carbs / g", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "N. Carbs / g", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers / g", "Gram"]
	}

	with open(get_file("nutritional_list.json"), "r", encoding="utf-8") as f:
		nutritional_list = json.load(f)
		print(nutritional_list[0])
		for d in nutritional_list:
			doc = frappe.new_doc("Item")
			doc.item_code = d["Ingredient ID"]
			doc.item_name = d["Item"]
			doc.kitchen_name = d["Item"]
			doc.item_category = "Ingredient"
			doc.item_group = d["Category"] or "Other"
			doc.uom = u[1]
			doc.is_stock_item = 1
			doc.serving_size = d["Serving Size (g)"]

			for i,v in nutrients.items():
				r = doc.append("nutrients", {})
				r.nutrient = i
				r.value = d[v[0]] or 0
				r.per_gram = d[v[1]] or 0
			

	# n = {}
	# nutrients = run_external_mysql_query("select * from nutrients")
	# for nu in nutrients:
	# 	n[nu["id"]] = nu

	# records = run_external_mysql_query("select * from food where type = 'INGREDIENT' ")
	# for d in records:
	# 	data = json.loads(d["data"])
	# 	doc = frappe.new_doc("Item")
	# 	doc.item_code = d["client_name"]
	# 	doc.item_name = d["client_name"]
	# 	doc.kitchen_name = d["kitchen_name"]
	# 	doc.item_category = "Ingredient"
	# 	doc.item_group = "Raw Material"
	# 	doc.uom = u[data["unit_id"]]
	# 	doc.is_stock_item = 1
	# 	doc.valuation_rate = data["purchase_price"]
	# 	doc.serving_size = data["serving_size"]

	# 	for i in data["nutrients"]:
	# 		nut = n[i["id"]]
	# 		r = doc.append("nutrients", {})
	# 		r.nutrient = nut["name"]
	# 		r.value = i["value"]

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

	uom_mapping = {
		"Gr": "Gram",
		"gr": "Gram",
		"GR": "Gram",
		"Pcs": "Nos",
		"pcs": "Nos",
		"PCs": "Nos"
	}

	nutrients = {
		"Calories": ["Calories", "Calories / g", "Kilocalorie"],
		"Protein": ["Protien (g)", "Protien / g", "Gram"],
		"Fats": ["Fat (g)", "Fat / g", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "Net Carbs / g", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers / g", "Gram"]
	}


	with open(get_file("sub_recipe_master_keyed.json"), "r", encoding="utf-8") as f:
		sub_recipe_details = json.load(f)

		for i,v in sub_recipe_details.items():
			doc = frappe.get_doc("Item", i)
			valuation_rate = v["SR - Cost / UOM"]
			doc.valuation_rate = float(valuation_rate) or 0
			if math.isnan(doc.valuation_rate):
				doc.valuation_rate = 0
			print(doc.valuation_rate)
			# for a,b in nutrients.items():
			# 	r = doc.append("nutrients", {})
			# 	r.nutrient = a
			# 	r.value = v[b[0]] or 0
			# 	r.per_gram = v[b[1]] or 0
			

	# m = {}
	# materials = run_external_mysql_query("select * from food")
	# for mt in materials:
	# 	m[mt["id"]] = mt

	# records = run_external_mysql_query("select * from food where type = 'SUB_RECIPE' ")
	# for d in records:
	# 	data = json.loads(d["data"])
	# 	doc = frappe.new_doc("BOM")
	# 	doc.item = d["client_name"]
	# 	doc.is_active = 1
	# 	doc.is_default = 1
	# 	doc.set_rate_of_sub_assembly_item_based_on_bom = 1
	# 	doc.quantity = data["netQuantity"]
	# 	print(data["materials"])
	# 	for i in data["materials"]:
	# 		if i["food_id"] == 335:
	# 			i["food_id"] = 153
	# 		item = m[i["food_id"]]
	# 		row = doc.append("items", {})
	# 		row.item_code = item["client_name"]
	# 		row.qty = i["grossQuantity"]


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
				#pass
				doc.save()
			except Exception as e:
				print(e)


	frappe.db.commit()



def fetch_dishes():
	u = {
		1: "Gram",
		2: "Kilocalorie",
		3: "Nos"
	}

	type_mapping = {
		"Light": "LO-CAL",
		"Balanced": "OPTI-MEAL",
		"Strong": "FULL-ON"
	}

	uom_mapping = {
		"Gr": "Gram",
		"gr": "Gram",
		"GR": "Gram",
		"Pcs": "Nos",
		"pcs": "Nos",
		"PCs": "Nos"
	}

	nutrients = {
		"Calories": ["Calories", "Calories", "Kilocalorie"],
		"Protein": ["Protien (g)", "Protien (g)", "Gram"],
		"Fats": ["Fat (g)", "Fat (g)", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "Net Carbs (g)", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers (g)", "Gram"]
	}


	with open(get_file("summary_full.json"), "r", encoding="utf-8") as f:
		sub_recipe_details = json.load(f)
		print(sub_recipe_details[0])
		for d in sub_recipe_details:
			doc = frappe.new_doc("Item")
			doc.item_code = d["Item ID"]
			doc.item_name = d["Iteam Name"]
			doc.kitchen_name = d["Item Display Name"]
			doc.description = d["Description"]
			doc.item_category = "Dish"
			doc.item_group = d["Category"]
			doc.uom = u[3]
			doc.is_stock_item = 1
			doc.has_variants = 0
			doc.variant_of = d["Item Display Name"]
			doc.variant_based_on = "Item Attribute"
			r = doc.append("attributes", {})
			r.attribute = "Dish Plan"
			r.attribute_value = type_mapping[d["Type"]]



			valuation_rate = d["Cost (QAR)"]
			doc.valuation_rate = float(valuation_rate) or 0
			if math.isnan(doc.valuation_rate):
				doc.valuation_rate = 0
			print(doc.valuation_rate)
			for a,b in nutrients.items():
				r = doc.append("nutrients", {})
				r.nutrient = a
				r.value = d[b[0]] or 0
			

	# m = {}
	# materials = run_external_mysql_query("select * from food")
	# for mt in materials:
	# 	m[mt["id"]] = mt

	# records = run_external_mysql_query("select * from food where type = 'SUB_RECIPE' ")
	# for d in records:
	# 	data = json.loads(d["data"])
	# 	doc = frappe.new_doc("BOM")
	# 	doc.item = d["client_name"]
	# 	doc.is_active = 1
	# 	doc.is_default = 1
	# 	doc.set_rate_of_sub_assembly_item_based_on_bom = 1
	# 	doc.quantity = data["netQuantity"]
	# 	print(data["materials"])
	# 	for i in data["materials"]:
	# 		if i["food_id"] == 335:
	# 			i["food_id"] = 153
	# 		item = m[i["food_id"]]
	# 		row = doc.append("items", {})
	# 		row.item_code = item["client_name"]
	# 		row.qty = i["grossQuantity"]


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
				#pass
				doc.save()
			except Exception as e:
				print(e)


	frappe.db.commit()



def fetch_item_templates():
	u = {
		1: "Gram",
		2: "Kilocalorie",
		3: "Nos"
	}

	uom_mapping = {
		"Gr": "Gram",
		"gr": "Gram",
		"GR": "Gram",
		"Pcs": "Nos",
		"pcs": "Nos",
		"PCs": "Nos"
	}

	nutrients = {
		"Calories": ["Calories", "Calories / g", "Kilocalorie"],
		"Protein": ["Protien (g)", "Protien / g", "Gram"],
		"Fats": ["Fat (g)", "Fat / g", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "Net Carbs / g", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers / g", "Gram"]
	}


	with open(get_file("summary_unique_item_display_name_no_desc.json"), "r", encoding="utf-8") as f:
		item_template = json.load(f)
		for d in item_template:
			doc = frappe.new_doc("Item")
			doc.item_code = d
			doc.item_name = d
			doc.kitchen_name = d
			doc.item_category = "Dish"
			doc.item_group = "Dishes"
			doc.uom = u[3]
			doc.is_stock_item = 1
			doc.has_variants = 1
			doc.variant_based_on = "Item Attribute"
			r = doc.append("attributes", {})
			r.attribute = "Dish Plan"
			

	# m = {}
	# materials = run_external_mysql_query("select * from food")
	# for mt in materials:
	# 	m[mt["id"]] = mt

	# records = run_external_mysql_query("select * from food where type = 'SUB_RECIPE' ")
	# for d in records:
	# 	data = json.loads(d["data"])
	# 	doc = frappe.new_doc("BOM")
	# 	doc.item = d["client_name"]
	# 	doc.is_active = 1
	# 	doc.is_default = 1
	# 	doc.set_rate_of_sub_assembly_item_based_on_bom = 1
	# 	doc.quantity = data["netQuantity"]
	# 	print(data["materials"])
	# 	for i in data["materials"]:
	# 		if i["food_id"] == 335:
	# 			i["food_id"] = 153
	# 		item = m[i["food_id"]]
	# 		row = doc.append("items", {})
	# 		row.item_code = item["client_name"]
	# 		row.qty = i["grossQuantity"]


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
				#pass
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
		# try:
		# 	doc = frappe.get_doc("BOM", {"item": name})
		# 	for b in doc.items:
		# 		item = frappe.get_doc("Item", b.item_code)
		# 		if item.item_category == "Sub Recipe":
		# 			try:
		# 				b.bom_no = frappe.get_doc("BOM", {"item": b.item_code}).name
		# 			except Exception as e:
		# 				pass
		# except Exception as e:
		# 	pass
		doc = frappe.get_doc("Item", name)
		if data["dishImage"]:
			image = data["dishImage"].replace("savvy_eats_testing", "savvy_eats")
			doc.image = image

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
			#doc.flags.ignore_validate = True
			doc.save()
		except Exception as e:
			print("error")
			print(doc.name)
			print(e)
			print("error end")

		#time.sleep(1)


	frappe.db.commit()