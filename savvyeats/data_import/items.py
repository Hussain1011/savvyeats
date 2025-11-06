import frappe
import json
from savvyeats.data_import.connection import run_external_mysql_query
import time
import os
import math
from frappe.utils import flt

def execute():
	fetch_allergens()


def update_dish_plans_items():
	items = frappe.get_all("Item", filters={"has_variants": 0, "item_category": "Dish"})

	dish_plans = {
		"l": "LO-CAL",
		"b": "OPTI-MEAL",
		"s": "FULL-ON"
	}
	idx = 1
	for d in items:
		item = frappe.get_doc("Item", d.name)
		item_name = item.item_name.split("-")[-1].strip().lower()
		attribute = ""
		dish_plan = ""
		if not item.attributes:
			continue
		if item.attributes:
			attribute = item.attributes[0].attribute_value
		if item.dish_plans:
			dish_plan = item.dish_plans[0].dish_plan

		#print([item_name, dish_plan, attribute])
		if item_name in dish_plans and dish_plan != dish_plans[item_name]:
			print([idx, d.name])
			item.dish_plans = []
			item.append("dish_plans", {"dish_plan": dish_plans[item_name]})

			item.attributes[0].attribute_value = dish_plans[item_name]

			item.save()
			idx += 1





def update_missed_items():
	with open(get_file("filtered_ids_data.json"), "r", encoding="utf-8") as f:
		dishes = json.load(f)
		for i,v in dishes.items():
			if i in ("S328", "S207"):
				continue
			item = frappe.get_doc("Item", i)
			template = v[0]["`"].split("-")
			if len(template) > 2:
				template = "{0}-{1}".format(template[0].strip(), template[1].strip())
			else:
				template = template[0].strip()

			if i in ["S146", "S147", "S148"]:
				template = "SR0117"
				
			# frappe.db.set_value("Item", item.name, "item_name", v[0]["`"].strip())
			# frappe.db.set_value("Item", item.name, "variant_of", template)
			# frappe.db.set_value("Item", item.name, "description", "")
			# image = frappe.db.get_value("Item", template, "image")
			uom = frappe.db.get_value("Item", template, "stock_uom")
			# frappe.db.set_value("Item", item.name, "image", image)
			# frappe.db.set_value("Item", item.name, "image", image)
			if uom != item.stock_uom:
				print([i, template])


def update_item_boms():
	with open(get_file("filtered_ids_data.json"), "r", encoding="utf-8") as f:
		dishes = json.load(f)
		for i,v in dishes.items():
			boms = frappe.get_all("BOM", filters={"item": i})
			raw = {}
			for x in v:
				raw[x["Ingredient ID"]] = x
			if boms:
				bom = frappe.get_doc("BOM", boms[0].name)
				bom.items = []
				for x in v:
					row = bom.append("items", {})
					row.item_code = x["Ingredient ID"]
					row.gross_qty = flt(x["Gross"]) or 1
					if math.isnan(row.gross_qty):
						row.gross_qty = 1
					row.qty = flt(x["Net"]) or 1
					if math.isnan(row.qty):
						row.qty = 1
					row.rate = flt(x["Cost / UOM"])
					if row.rate > 0:
						frappe.db.set_value("Item", row.item_code, "valuation_rate", row.rate)
					if math.isnan(row.rate):
						row.rate = 1

				# for d in bom.items:
				# 	if d.item_code in raw:
				# 		d.gross_qty = flt(raw[d.item_code]["Gross"]) or 1
				# 		if math.isnan(d.gross_qty):
				# 			d.gross_qty = 1
				# 		d.qty = flt(raw[d.item_code]["Net"]) or 1
				# 		if math.isnan(d.qty):
				# 			d.qty = 1
				# 		d.rate = flt(raw[d.item_code]["Cost / UOM"])
				# 		if d.rate > 0:
				# 			frappe.db.set_value("Item", d.item_code, "valuation_rate", d.rate)
				# 		if math.isnan(d.rate):
				# 			d.rate = 1
				# 	else:
				# 		d.gross_qty = 0
				# 		d.qty = 0

				bom.save()


def update_image_url():
	with open(get_file("item_images.json"), "r", encoding="utf-8") as f:
		dishes = json.load(f)
		a = 1
		for i,v in dishes.items():
			if v["image_name"] and v["image_url"]:
				doc = frappe.get_doc("Item", i)
				doc.image = v["image_url"]
				doc.save()
			else:
				print(v["item_name"])

		#frappe.db.commit()

def update_variants_url():
	templates = frappe.get_all("Item", filters={"has_variants": 1, "image": ["!=", ""]}, fields=["name","image"])

	for d in templates:
		variants = frappe.get_all("Item", filters={"variant_of": d.name})
		for v in variants:
			doc = frappe.get_doc("Item", v.name)
			doc.image = d.image
			doc.save()

	frappe.db.commit()

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


def fetch_dish_master():
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

	with open(get_file("final_master_recipes.json"), "r", encoding="utf-8") as f:
		dishes = json.load(f)
		#print(dishes)
		for i,d in dishes.items():
			doc = frappe.new_doc("Item")
			doc.item_code = i
			doc.item_name = d["item_name"]
			doc.kitchen_name = d["item_name"]
			doc.item_category = "Dish"
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


def update_sub_recipe_uom():
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

	with open(get_file("sub_recipe_id_uom.json"), "r", encoding="utf-8") as f:
		sub_recipe_details = json.load(f)
		for i,v in sub_recipe_details.items():
			uom = uom_mapping[v]
			frappe.db.set_value("Item", i, "stock_uom", uom)



def update_bom():
	boms = frappe.get_all("BOM")
	for d in boms:
		bom = frappe.get_doc("BOM", d.name)
		for b in bom.items:
			if b.item_code.startswith("SR"):
				sr_bom = "BOM-{0}-001".format(b.item_code)
				if frappe.db.exists("BOM", sr_bom):
					frappe.db.set_value(b.doctype, b.name, "bom_no", sr_bom)
				else:
					print(b.item_code)

		# try:
		# 	bom.save()
		# except Exception as e:
		# 	print(e)



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
		"Protein": ["Protein (g)", "Protien / g", "Gram"],
		"Fats": ["Fat (g)", "Fat / g", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "Net Carbs / g", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers / g", "Gram"]
	}


	with open(get_file("sub_recipe_details_with_qty.json"), "r", encoding="utf-8") as f:
		sub_recipe_details = json.load(f)

		for i,v in sub_recipe_details.items():
			main_bom = frappe.get_doc("BOM", "BOM-{0}-001".format(i))

			for d in v["ingredients"]:
				pass


			try:
				pass
			except Exception as e:
				print(e)

			# doc = frappe.get_doc("Item", i)
			# valuation_rate = v["SR - Cost / UOM"]
			# doc.valuation_rate = float(valuation_rate) or 0
			# if math.isnan(doc.valuation_rate):
			# 	doc.valuation_rate = 0
			# print(doc.valuation_rate)
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

			# try:
			# 	#pass
			# 	doc.save()
			# except Exception as e:
			# 	print(e)


	# frappe.db.commit()


def fetch_master_recipe():
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
		"Protein": ["Protein (g)", "Protien / g", "Gram"],
		"Fats": ["Fat (g)", "Fat / g", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "Net Carbs / g", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers / g", "Gram"]
	}


	with open(get_file("recipes_str2_oldformat.json"), "r", encoding="utf-8") as f:
		sub_recipe_details = json.load(f)

		for i,v in sub_recipe_details.items():
			if not frappe.db.exists("Item", i):
				if not frappe.db.exists("Item", i):
					item = frappe.new_doc("Item")
					item.item_code = i
					item.item_name = v["item_name"]
					item.kitchen_name = v["item_name"]
					item.item_category = "Dish"
					item.item_group = "Mains"
					item.uom = "Nos"
					item.is_stock_item = 1

					for a,b in nutrients.items():
						r = item.append("nutrients", {})
						r.nutrient = a
						r.value = v["nutrients"][b[0]] or 0

					item.save()

			doc = frappe.new_doc("BOM")
			doc.item = i
			doc.is_active = 1
			doc.is_default = 1
			doc.set_rate_of_sub_assembly_item_based_on_bom = 1
			doc.quantity = 1
			doc.gross_quantity = 1

			for d in v["ingredients"]:
				if "Ingredient ID" not in d:
					continue
				if not frappe.db.exists("Item", d["Ingredient ID"]):
					raw = frappe.new_doc("Item")
					raw.item_code = d["Ingredient ID"]
					raw.item_name = d["Ingredient Name"]
					raw.kitchen_name = d["Ingredient Name"]
					raw.item_category = "Ingredient"
					raw.item_group = "Raw Material"
					raw.uom = uom_mapping[d["UOM"]]
					raw.is_stock_item = 1
					raw.valuation_rate = 1
					if "Cost / UOM" in d:
						raw.valuation_rate = d["Cost / UOM"]

					if "Net Qty" in d:
						raw.serving_size = d["Net Qty"]

					for a,b in nutrients.items():
						for f in b:
							if f in d:
								r = raw.append("nutrients", {})
								r.nutrient = a
								r.value = d[f]
								break

					raw.save()

				row = doc.append("items", {})
				row.item_code = d["Ingredient ID"]
				if "UOM" in d and d["UOM"].strip() in uom_mapping:
					frappe.db.set_value("Item", row.item_code, "stock_uom", uom_mapping[d["UOM"].strip()])
				row.qty = 1
				if "Net Qty" in d:
					row.qty = d["Net Qty"]
				if "Gross Qty" in d:
					row.gross_qty = d["Gross QTY"]
				row.rate = 1
				if "Cost / UOM" in d:
					row.rate = d["Cost / UOM"]
				if "UOM" in d and d["UOM"].strip() in uom_mapping:
					row.uom = uom_mapping[d["UOM"].strip()]


			try:
				if len(doc.items) > 0:
					doc.save()
			except Exception as e:
				print(e)

			# doc = frappe.get_doc("Item", i)
			# valuation_rate = v["SR - Cost / UOM"]
			# doc.valuation_rate = float(valuation_rate) or 0
			# if math.isnan(doc.valuation_rate):
			# 	doc.valuation_rate = 0
			# print(doc.valuation_rate)
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

			# try:
			# 	#pass
			# 	doc.save()
			# except Exception as e:
			# 	print(e)


	# frappe.db.commit()




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
		"Protein": ["Protein (g)", "Protien (g)", "Gram"],
		"Fats": ["Fat (g)", "Fat (g)", "Gram"],
		"Net Carbs": ["Net Carbs (g)", "Net Carbs (g)", "Gram"],
		"Fibers": ["Fibers (g)", "Fibers (g)", "Gram"]
	}


	with open(get_file("grouped_without_full_BLS_v2.json"), "r", encoding="utf-8") as f:
		sub_recipe_details = json.load(f)
		for v,i in sub_recipe_details.items():
			if v == "ADD ON":
				continue
			for d in i:
				if d["item_name"] == "Raspberry Rose Chia Jar":
					continue
				print(d["item_name"])
				# tp = d["item_name"].split(" - ")[1].strip()
				# if tp == "B":
				# 	it_type = "Balanced"
				# elif tp == "L":
				# 	it_type = "Light"
				# elif tp == "S":
				# 	it_type = "Strong"
				doc = frappe.new_doc("Item")
				doc.item_code = d["item_code"]
				doc.item_name = d["item_name"]
				doc.kitchen_name = d["item_name"]
				doc.description = d["item_name"]
				doc.item_category = "Dish"
				doc.item_group = "Mains"
				doc.uom = u[3]
				doc.is_stock_item = 1
				doc.has_variants = 0
				# doc.variant_of = v
				# doc.variant_based_on = "Item Attribute"
				# r = doc.append("attributes", {})
				# r.attribute = "Dish Plan"
				# r.attribute_value = type_mapping[it_type]



				valuation_rate = 1
				doc.valuation_rate = float(valuation_rate) or 0
				if math.isnan(doc.valuation_rate):
					doc.valuation_rate = 0
				for a,b in nutrients.items():
					r = doc.append("nutrients", {})
					r.nutrient = a
					r.value = d["nutrients"][b[0]] or 0
			

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


	#frappe.db.commit()



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


	with open(get_file("grouped_with_BLS_v2.json"), "r", encoding="utf-8") as f:
		item_template = json.load(f)
		for d,v in item_template.items():
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