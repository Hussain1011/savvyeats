# Copyright (c) 2026, Nouman and contributors
# For license information, please see license.txt

"""MY WAY acceptance tests.

Two halves, and both matter:

* MY WAY does what it should — plates priced once, portions in grams, no filler
  rows, no component flagged as an extra, a configurable number of categories.
* **Nothing else broke.** The dish path shares add_items with MY WAY, so every run
  also puts a Standard-plan order through it and checks the pricing, the is_extra
  flagging and the filler rows are exactly as they were.

Run with:
    bench --site <site> run-tests --module savvyeats.tests.test_my_way
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from savvyeats import patches
from savvyeats.api import items as items_api
from savvyeats.api import order as order_api
from savvyeats.api.utils import MY_WAY_MEAL_ITEM_CODE, is_my_way_plan

PLAN = "MY WAY Test Plan"
PER_DAY_PRICE = 45.0
CATEGORIES = ["Test Protein", "Test Carbs", "Test Fats", "Test Fibers"]


class TestMyWay(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# add_items commits, which would escape the test transaction.
		cls._commit_patch = patch.object(frappe.db, "commit", lambda *a, **k: None)
		cls._commit_patch.start()

		cls.d1 = getdate(add_days(nowdate(), 7))
		cls.d2 = getdate(add_days(nowdate(), 8))
		cls.customer = frappe.get_all("Customer", pluck="name", limit=1)[0]

		cls.plan = cls._make_plan()
		patches.setup_my_way(cls.plan, PER_DAY_PRICE, meal_count=3, categories=CATEGORIES)
		cls.components = cls._make_components()

	@classmethod
	def tearDownClass(cls):
		cls._commit_patch.stop()
		super().tearDownClass()

	# -- fixtures ---------------------------------------------------------
	@classmethod
	def _make_plan(cls):
		plan = frappe.get_doc({
			"doctype": "Dish Plan",
			"plan_name": PLAN,
			"display_plan_name": PLAN,
			"plan_description": "MY WAY acceptance tests",
			"ui_type": "My Way",
			"enabled": 1,
			"sorting_order": 99,
			"min_calories": 1200,
			"max_calories": 2400,
			"week_plans": [{"week_plan": frappe.get_all("Week Plan", pluck="name", limit=1)[0]}],
		})
		# The meal rows are what setup_my_way adds next, so they cannot be here yet.
		plan.flags.ignore_mandatory = True
		plan.insert(ignore_permissions=True)
		return plan.name

	@classmethod
	def _make_components(cls):
		template = frappe.get_all("Item", filters={"disabled": 0}, fields=["item_group", "stock_uom"], limit=1)[0]
		nutrient = frappe.get_all("Nutrient", pluck="name", limit=1)[0]

		components = {}
		for i, category in enumerate(CATEGORIES, start=1):
			code = "TEST-COMPONENT-{0}".format(i)
			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": template.item_group,
				"stock_uom": template.stock_uom,
				"item_category": "Ingredient",
				"is_stock_item": 0,
				"serving_size": 100 * i,
				"component_category": category,
				"dish_plans": [{"dish_plan": cls.plan}],
				# value only, no per_gram: the endpoint has to derive it or the app
				# shows the customer 0 kcal with no error.
				"nutrients": [{"nutrient": nutrient, "value": 250}],
			})
			item.flags.ignore_mandatory = True
			item.insert(ignore_permissions=True)
			components[category] = code

		return components

	def _make_order(self, dish_plan, meals, dates):
		order = frappe.get_doc({
			"doctype": "Sales Order",
			"customer": self.customer,
			"is_online": 1,
			"expired": 0,
			"dish_plan": dish_plan,
			"transaction_date": nowdate(),
			"delivery_date": dates[0],
			"delivery_dates": [{"delivery_date": d} for d in dates],
			"meals": [{"meal": m} for m in meals],
		})
		order.flags.ignore_validate = True
		order.flags.ignore_mandatory = True
		order.flags.ignore_permissions = True
		order.insert()
		return order

	def _full_plate(self, meal, date, grams=150):
		return [
			{"item_code": self.components[c], "meal": meal, "delivery_date": str(date), "grams": grams}
			for c in CATEGORIES
		]

	# -- MY WAY works -----------------------------------------------------
	def test_plate_is_priced_once_not_once_per_component(self):
		"""The 4x trap: per_day_price prices a meal, not each of its components."""
		order = self._make_order(self.plan, ["Meal 1", "Meal 2"], [self.d1, self.d2])

		payload = []
		for date in (self.d1, self.d2):
			for meal in ("Meal 1", "Meal 2"):
				payload += self._full_plate(meal, date)

		order_api.add_items(order.name, payload)
		order.reload()

		# 2 meals x 2 days = 4 plates. Charging per component would give 720.
		self.assertEqual(order.grand_total, 4 * PER_DAY_PRICE)
		self.assertEqual(len([r for r in order.items if r.item_code == MY_WAY_MEAL_ITEM_CODE]), 4)
		self.assertEqual({r.rate for r in order.items if r.item_code != MY_WAY_MEAL_ITEM_CODE}, {0.0})

	def test_a_snack_costs_the_same_as_a_full_plate(self):
		"""Price attaches to the meal slot, not to how many categories were filled."""
		order = self._make_order(self.plan, ["Meal 1", "Meal 2"], [self.d1])

		payload = self._full_plate("Meal 1", self.d1)
		payload += self._full_plate("Meal 2", self.d1)[:2]      # a two-component snack

		order_api.add_items(order.name, payload)
		order.reload()

		self.assertEqual(order.grand_total, 2 * PER_DAY_PRICE)
		self.assertEqual(len([r for r in order.items if r.meal == "Meal 2" and r.grams]), 2)

	def test_grams_are_persisted_and_qty_stays_one(self):
		order = self._make_order(self.plan, ["Meal 1"], [self.d1])
		order_api.add_items(order.name, self._full_plate("Meal 1", self.d1, grams=175))
		order.reload()

		components = [r for r in order.items if r.item_code != MY_WAY_MEAL_ITEM_CODE]
		self.assertEqual(len(components), 4)
		self.assertEqual({r.grams for r in components}, {175.0})
		self.assertEqual({r.qty for r in components}, {1.0})
		self.assertEqual({r.meal for r in components}, {"Meal 1"})

	def test_no_component_is_flagged_as_an_extra(self):
		"""Components 2..N share a meal; flagging them would drop them from the macros."""
		order = self._make_order(self.plan, ["Meal 1"], [self.d1])
		order_api.add_items(order.name, self._full_plate("Meal 1", self.d1))
		order.reload()

		self.assertEqual(sum(r.is_extra for r in order.items), 0)

	def test_no_filler_rows_are_invented(self):
		"""A snack legitimately has fewer categories; padding it would print phantoms."""
		order = self._make_order(self.plan, ["Meal 1", "Meal 2"], [self.d1, self.d2])
		order_api.add_items(order.name, self._full_plate("Meal 1", self.d1)[:2])
		order.reload()

		self.assertEqual([r for r in order.items if r.item_code == "Item Not Selected"], [])

	def test_one_component_per_category_last_write_wins(self):
		"""BR-1 is enforced server-side; the client is not trusted with it."""
		order = self._make_order(self.plan, ["Meal 1"], [self.d1])
		protein = self.components[CATEGORIES[0]]

		order_api.add_items(order.name, [
			{"item_code": protein, "meal": "Meal 1", "delivery_date": str(self.d1), "grams": 70},
			{"item_code": protein, "meal": "Meal 1", "delivery_date": str(self.d1), "grams": 90},
		])
		order.reload()

		components = [r for r in order.items if r.item_code != MY_WAY_MEAL_ITEM_CODE]
		self.assertEqual([r.grams for r in components], [90.0])

	def test_get_plan_components_returns_the_catalogue(self):
		order = self._make_order(self.plan, ["Meal 1"], [self.d1])
		categories = items_api.get_plan_components(order.name)["data"]["categories"]

		self.assertEqual([c["code"] for c in categories], CATEGORIES)
		self.assertEqual([c["label"] for c in categories], CATEGORIES)
		self.assertTrue(all(c["required"] for c in categories))

		component = categories[0]["items"][0]
		self.assertEqual(component["serving_size"], 100.0)
		# 250 over a 100 g serving, derived because the import left per_gram blank.
		self.assertEqual(component["doc"]["nutrients"][0]["per_gram"], 2.5)

	def test_the_category_count_is_configuration_not_code(self):
		order = self._make_order(self.plan, ["Meal 1"], [self.d1])

		frappe.db.set_value("Component Category", CATEGORIES[-1], "enabled", 0)
		frappe.clear_cache()
		try:
			categories = items_api.get_plan_components(order.name)["data"]["categories"]
			self.assertEqual([c["code"] for c in categories], CATEGORIES[:3])
		finally:
			frappe.db.set_value("Component Category", CATEGORIES[-1], "enabled", 1)
			frappe.clear_cache()

	def test_a_non_my_way_plan_gets_an_empty_catalogue_not_an_error(self):
		dish_plan = frappe.get_all("Dish Plan", filters={"ui_type": "Standard", "enabled": 1}, pluck="name")[0]
		order = self._make_order(dish_plan, [], [self.d1])

		response = items_api.get_plan_components(order.name)

		self.assertEqual(response["status"], "success")
		self.assertEqual(response["data"]["categories"], [])

	# -- nothing else broke ------------------------------------------------
	def test_dish_plan_orders_are_untouched(self):
		"""Same pricing, same is_extra flagging, same filler rows as before MY WAY."""
		dish_plan = frappe.get_doc("Dish Plan", frappe.get_all(
			"Dish Plan", filters={"ui_type": "Standard", "enabled": 1}, pluck="name")[0])
		self.assertFalse(is_my_way_plan(dish_plan.name))

		meal_cfg = dish_plan.meals[0]
		dish_item = frappe.get_all(
			"Item", filters={"disabled": 0, "item_category": "Dish"}, pluck="name", limit=1)[0]

		order = self._make_order(dish_plan.name, [meal_cfg.meal], [self.d1, self.d2])
		# Two selections on d1, nothing on d2.
		order_api.add_items(order.name, [
			{"item_code": dish_item, "meal": meal_cfg.meal, "delivery_date": str(self.d1), "qty": 1},
			{"item_code": dish_item, "meal": meal_cfg.meal, "delivery_date": str(self.d1), "qty": 1},
		])
		order.reload()

		price = frappe.db.get_value(
			"Dish Plan Meals", {"parent": order.dish_plan_pricing, "meal": meal_cfg.meal}, "per_day_price"
		)
		selected = [r for r in order.items if r.item_code != "Item Not Selected"]
		fillers = [r for r in order.items if r.item_code == "Item Not Selected"]

		# every meal row still carries the per-day price, one row at a time
		self.assertEqual({r.rate for r in selected}, {price})
		# grams is additive: a dish line never gets one
		self.assertEqual({r.grams for r in order.items}, {0.0})

		if meal_cfg.max_qty == 1:
			self.assertEqual(sum(r.is_extra for r in selected), 1)
		if meal_cfg.min_qty > 0:
			self.assertTrue([r for r in fillers if r.delivery_date == self.d2])
