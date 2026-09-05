import frappe
from frappe import _
from frappe.utils import getdate, today, flt
from savvyeats.api.user import send_error_response, send_success_response
import json
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery, validate_addresses
from savvyeats.api.utils import MY_WAY_MEAL_ITEM_CODE, is_my_way_plan

def validate_sales_order(order_id):
	try:
		order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
		if order.owner != frappe.session.user:
			message_en = "Access denied. This order does not belong to your account."
			message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

			errors = {
				"access_denied": ["Access denied. This order does not belong to your account."]
			}
			return send_error_response(message_en, message_ar, errors)
	except Exception as e:
		message_en = "Order not found."
		message_ar = "لم يتم العثور على الطلب."
		errors = {
			"not_found": ["Order not found."]
		}
		return send_error_response(message_en, message_ar, errors)

	return order

@frappe.whitelist(methods=["GET"])
def get_draft_order(new=False):
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})

	order_filters = {"docstatus": 0, "is_online": 1, "expired": 0}

	if customer:
		order_filters["customer"] = customer[0].name
	else:
		order_filters["owner"] = frappe.session.user
		order_filters["customer"] = "Online Customer"

	orders = frappe.get_all("Sales Order", filters=order_filters, fields=["name"], limit=1)

	if orders:
		order = frappe.get_doc("Sales Order", orders[0].name, ignore_permissions=True)

		if frappe.utils.cint(new):
			_reset_sales_order_in_place(order)
			order.flags.ignore_validate = True
			order.flags.ignore_permissions = True
			order.flags.ignore_mandatory = True
			order.save()
			frappe.db.commit()
	else:
		order_filters["doctype"] = "Sales Order"
		order = frappe.get_doc(order_filters)
		order.flags.ignore_validate = True
		order.flags.ignore_permissions = True
		order.flags.ignore_mandatory = True
		order.insert()
		frappe.db.commit()

	return send_success_response("", "", order)


def _reset_sales_order_in_place(order):
	order.po_no = None
	order.po_date = None
	order.is_online = 1
	order.expired = 0
	order.shipping_address_name = None
	order.shipping_address = None
	order.billing_address_name = None
	order.billing_address = None
	order.total_qty = 0
	order.total_net_weight = 0
	order.base_total = 0
	order.base_net_total = 0
	order.total = 0
	order.net_total = 0
	order.base_total_taxes_and_charges = 0
	order.total_taxes_and_charges = 0
	order.base_grand_total = 0
	order.base_rounding_adjustment = 0
	order.base_rounded_total = 0
	order.grand_total = 0
	order.rounding_adjustment = 0
	order.rounded_total = 0
	order.advance_paid = 0
	order.base_discount_amount = 0
	order.additional_discount_percentage = 0
	order.discount_amount = 0
	order.per_delivered = 0
	order.per_billed = 0
	order.per_picked = 0
	order.amount_eligible_for_commission = 0
	order.commission_rate = 0
	order.total_commission = 0
	order.loyalty_points = 0
	order.loyalty_amount = 0
	order.delivery_days = 0
	order.total_days = 0
	order.status = "Draft"
	order.delivery_status = "Not Delivered"
	order.billing_status = "Not Billed"
	order.order_type = "Sales"
	order.apply_discount_on = "Grand Total"
	order.disable_rounded_total = 0
	order.ignore_pricing_rule = 0
	order.reserve_stock = 0
	order.group_same_items = 0
	order.is_internal_customer = 0
	order.dish_plan = None
	order.dish_plan_pricing = ""
	order.period_type = None
	order.period_count = 0
	order.transaction_date = frappe.utils.nowdate()
	order.pricing_rules = []
	order.allergens = []
	order.health_goals = []
	order.items = []
	order.meals = []
	order.taxes = []
	order.addresses = []
	order.customer_address = ""
	order.week_plan = ""
	order.delivery_time_slot = ""
	order.start_date = ""
	order.end_date = ""
	order.payment_schedule = []
	order.packed_items = []
	order.delivery_dates = []
	order.delivery_date = ""
	order.sales_team = []
	order.coupon_code = ""
	order.additional_discount_percentage = 0
	order.discount_amount = 0
	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()


@frappe.whitelist(methods=["POST"])
def update_draft_order(order_id, data):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	protected_keys = {"name", "doctype", "owner", "customer", "items", "ignore_pricing_rule"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}

	if "meals" in clean_data:
		order.meals = []

	if "allergens" in clean_data:
		order.allergens = []

	if "addresses" in clean_data:
		order.addresses = []

	order.update(clean_data)

	sales_order_delivery(order)

	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist(methods=["POST"])
def validate_draft_order(order_id, data):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	protected_keys = {"name", "doctype", "owner", "customer", "items", "ignore_pricing_rule"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}

	if "meals" in clean_data:
		order.meals = []

	if "allergens" in clean_data:
		order.allergens = []

	if "addresses" in clean_data:
		order.addresses = []

	order.update(clean_data)

	sales_order_delivery(order)

	order.flags.ignore_permissions = True
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist(methods=["POST"])
def apply_voucher_code(order_id, voucher_code):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	if order.docstatus != 0:
		return send_error_response(
			"This order can no longer be modified.",
			"لا يمكن تعديل هذا الطلب بعد الآن.",
			{"error": ["This order can no longer be modified."]},
		)

	if not voucher_code or not frappe.db.exists("Coupon Code", voucher_code):
		return send_error_response(
			"Invalid or missing voucher code.",
			"رمز القسيمة غير صالح أو مفقود.",
			{"not_found": ["Invalid or missing voucher code."]},
		)

	coupon = frappe.get_doc("Coupon Code", voucher_code)
	today_date = getdate(today())

	# --- Validation (independent checks, not elif: each condition is its own gate) ---
	if coupon.valid_from and getdate(coupon.valid_from) > today_date:
		return send_error_response(
			"Coupon code validity has not started.",
			"لم تبدأ صلاحية رمز القسيمة بعد.",
			{"validity_issue": ["Coupon code validity has not started."]},
		)

	if coupon.valid_upto and getdate(coupon.valid_upto) < today_date:
		return send_error_response(
			"The coupon code has expired.",
			"انتهت صلاحية رمز القسيمة.",
			{"expired": ["The coupon code has expired."]},
		)

	if coupon.maximum_use and (coupon.used or 0) >= coupon.maximum_use:
		return send_error_response(
			"This coupon is no longer valid.",
			"لم تعد هذه القسيمة صالحة.",
			{"expired": ["This coupon is no longer valid."]},
		)

	# --- Apply the discount from the coupon's linked Pricing Rule ---
	error = _apply_coupon_discount(order, coupon)
	if error is not None:
		return error

	try:
		order.coupon_code = coupon.name
		order.flags.ignore_permissions = True
		order.save()
		frappe.db.commit()
	except Exception:
		frappe.log_error("Apply Voucher Failed")
		return send_error_response(
			"Could not apply this coupon. Please try again.",
			"تعذر تطبيق هذه القسيمة. يرجى المحاولة مرة أخرى.",
			{"error": ["Could not apply this coupon."]},
		)

	return send_success_response(
		"Coupon applied successfully.",
		"تم تطبيق القسيمة بنجاح.",
		order,
	)


def _apply_coupon_discount(order, coupon):

	if not coupon.pricing_rule:
		return send_error_response(
			"This coupon is not configured correctly.",
			"لم يتم إعداد هذه القسيمة بشكل صحيح.",
			{"error": ["This coupon is not configured correctly (no pricing rule)."]},
		)

	pricing_rule = frappe.get_cached_doc("Pricing Rule", coupon.pricing_rule)

	# Reset any previous order-level discount before applying the new one.
	order.apply_discount_on = pricing_rule.apply_discount_on or "Grand Total"
	order.additional_discount_percentage = 0
	order.discount_amount = 0

	if pricing_rule.rate_or_discount == "Discount Percentage":
		order.additional_discount_percentage = min(flt(pricing_rule.discount_percentage), 100)
	elif pricing_rule.rate_or_discount == "Discount Amount":
		order.discount_amount = flt(pricing_rule.discount_amount)
	else:
		return send_error_response(
			"This coupon type is not supported.",
			"نوع القسيمة هذا غير مدعوم.",
			{"error": ["This coupon discount type is not supported."]},
		)

	return None



@frappe.whitelist(methods=["POST"])
def update_items(order_id, items):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	for d in items:
		frappe.db.set_value("Sales Order Item", d["name"], "item_code", d["item_code"])
		item = frappe.get_doc("Item", d["item_code"])
		frappe.db.set_value("Sales Order Item", d["name"], "item_name", item.item_name)
		frappe.db.set_value("Sales Order Item", d["name"], "description", item.description)

		# A swapped MY WAY component brings its own portion. Without this the row keeps
		# the grams of the component it replaced, which the kitchen would then pack.
		if "grams" in d:
			frappe.db.set_value("Sales Order Item", d["name"], "grams", flt(d.get("grams")))
		elif item.serving_size and frappe.db.get_value("Sales Order Item", d["name"], "grams"):
			frappe.db.set_value("Sales Order Item", d["name"], "grams", flt(item.serving_size))

	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


def _add_dish_plan_items(order, items, meals, meals_list, pricing_plan_meals):
	"""Build the item rows for a dish-plan order.

	Lifted verbatim out of add_items so the MY WAY build can sit beside it rather
	than be threaded through it. Behaviour is unchanged.
	"""
	dates = []
	dates_data = {}
	for v in items:
		meal = v.get("meal", "")
		if meal and meal not in meals_list:
			continue

		row = order.append("items")
		row.item_code = v["item_code"]
		row.meal = v.get("meal", "")

		row.delivery_date = getdate(v["delivery_date"])
		row.note = v.get("note", "")
		row.qty = int(v["qty"]) if v.get("qty") and int(v["qty"]) > 1 else 1
		row.extra_portion = 1 if v.get("extra_portion") and row.qty > 1 else 0
		row.is_extra = 0

		if row.meal:
			row.rate = pricing_plan_meals.get(row.meal)
			row.price_list_rate = row.rate

		if row.delivery_date not in dates:
			dates.append(row.delivery_date)

		if not row.meal:
			continue

		if row.delivery_date not in dates_data:
			dates_data[row.delivery_date] = {}

		if row.meal not in dates_data[row.delivery_date]:
			dates_data[row.delivery_date][row.meal] = 0

		dates_data[row.delivery_date][row.meal] += 1

		# Selections beyond the meal's included maximum (max_qty) are allowed but
		# flagged as extra: they are still charged at the meal's per-day price, while
		# the app excludes is_extra items from the calorie count.
		meal_cfg = meals.get(row.meal)
		if meal_cfg and meal_cfg.max_qty and dates_data[row.delivery_date][row.meal] > meal_cfg.max_qty:
			row.is_extra = 1


	for d in order.delivery_dates:
		if not getdate(d.delivery_date) in dates:
			for m in order.meals:
				qty = meals[m.meal].min_qty
				if qty > 0:
					for r in range(0, qty):
						row = order.append("items")
						row.item_code = "Item Not Selected"
						row.meal = m.meal
						row.delivery_date = getdate(d.delivery_date)
						row.qty = 1
						row.rate = pricing_plan_meals.get(row.meal)
						row.price_list_rate = row.rate

		else:
			dd = dates_data[d.delivery_date]

			for i,v in dd.items():
				for r in range(0, meals[i].max_qty - v):
					row = order.append("items")
					row.item_code = "Item Not Selected"
					row.meal = i
					row.delivery_date = getdate(d.delivery_date)
					row.qty = 1
					row.rate = pricing_plan_meals.get(i)
					row.price_list_rate = row.rate


def _add_my_way_items(order, items, meals_list, pricing_plan_meals):
	"""Build the item rows for a MY WAY (build-your-own) order.

	Three things the dish path does are deliberately not done here:

	* **The per-row rate assignment.** `per_day_price` prices one *meal*, and a dish
	  meal is one row, so charging every row is correct there. A MY WAY meal is N
	  component rows in the same meal, so the same rule would bill a plate N times.
	  One header row per (delivery_date, meal) carries the price instead and the
	  components ride at zero, which keeps the total right however many categories
	  a plate happens to have.
	* **`is_extra` flagging.** A dish meal holds one item; a MY WAY meal holds one
	  per category. Flagging components 2..N as extras would bill them separately
	  and drop them from the calorie count — the number the feature exists to show.
	* **Filler "Item Not Selected" rows.** A snack legitimately carries fewer
	  categories than a main meal, so padding every meal out to max_qty would invent
	  phantom lines. The app blocks checkout until each day is complete.

	Returns an error response dict when the order cannot be priced, else None.
	"""
	# Categories come from the Item, never from the payload: BR-1 (one component per
	# category per meal) is a server-side rule and the client is not trusted with it.
	item_codes = {v["item_code"] for v in items if v.get("item_code")}
	categories = {}
	if item_codes:
		for r in frappe.get_all(
			"Item", filters={"name": ["in", list(item_codes)]}, fields=["name", "component_category"]
		):
			categories[r.name] = r.component_category

	plates = {}
	loose = []

	for v in items:
		meal = v.get("meal", "")
		if meal and meal not in meals_list:
			continue

		if not meal:
			# Add-ons and anything else not tied to a meal: no plate, no meal price,
			# and the rate is left for ERPNext to resolve from the price list.
			loose.append(v)
			continue

		delivery_date = getdate(v["delivery_date"])
		plate = plates.setdefault((delivery_date, meal), {})
		# BR-1, last write wins. Falling back to the item code keeps an uncategorised
		# component rather than collapsing it into whatever else has no category.
		plate[categories.get(v["item_code"]) or v["item_code"]] = v

	if plates:
		# A meal with no per-day price would fall through to the price list and bill
		# the plate at whatever the header item happens to cost — usually nothing.
		unpriced = sorted({meal for (_date, meal) in plates if pricing_plan_meals.get(meal) is None})
		if unpriced:
			message_en = "No per-day price is configured for: {0}.".format(", ".join(unpriced))
			message_ar = "لا يوجد سعر يومي مهيأ لـ: {0}.".format("، ".join(unpriced))
			return send_error_response(
				message_en, message_ar, {"meal_price_not_configured": [message_en]}
			)

		if not frappe.db.exists("Item", MY_WAY_MEAL_ITEM_CODE):
			message_en = "Item '{0}' is missing. MY WAY orders cannot be priced without it.".format(
				MY_WAY_MEAL_ITEM_CODE
			)
			message_ar = "الصنف '{0}' غير موجود. لا يمكن تسعير طلبات MY WAY بدونه.".format(
				MY_WAY_MEAL_ITEM_CODE
			)
			return send_error_response(
				message_en, message_ar, {"my_way_meal_item_missing": [message_en]}
			)

	for (delivery_date, meal), components in plates.items():
		header = order.append("items")
		header.item_code = MY_WAY_MEAL_ITEM_CODE
		header.meal = meal
		header.delivery_date = delivery_date
		header.qty = 1
		header.extra_portion = 0
		header.is_extra = 0
		header.rate = pricing_plan_meals.get(meal)
		header.price_list_rate = header.rate

		for v in components.values():
			row = order.append("items")
			row.item_code = v["item_code"]
			row.meal = meal
			row.delivery_date = delivery_date
			row.note = v.get("note", "")
			# BR-2: qty stays a portion count of 1 whatever the portion is; grams
			# carry the size and are what the kitchen and the macros read.
			row.qty = 1
			row.grams = flt(v.get("grams"))
			row.extra_portion = 0
			row.is_extra = 0
			row.rate = 0
			row.price_list_rate = 0

	for v in loose:
		row = order.append("items")
		row.item_code = v["item_code"]
		row.meal = ""
		row.delivery_date = getdate(v["delivery_date"])
		row.note = v.get("note", "")
		row.qty = int(v["qty"]) if v.get("qty") and int(v["qty"]) > 1 else 1
		row.extra_portion = 1 if v.get("extra_portion") and row.qty > 1 else 0
		row.is_extra = 0


@frappe.whitelist(methods=["POST"])
def add_items(order_id, items):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	def get_pricing_for_required_meals(dish_plan, selected_meals):
		"""Return name of Dish Plan Pricing whose mandatory meals set matches selected_meals."""
		if not dish_plan or not selected_meals:
			return None

		# get all enabled pricing for this dish plan
		pricing_names = frappe.get_all(
			"Dish Plan Pricing",
			filters={
				"dish_plan": dish_plan,
				"enabled": 1,
				"docstatus": ["<", 2],
			},
			pluck="name",
		)

		matches = []

		for name in pricing_names:
			pricing = frappe.get_cached_doc("Dish Plan Pricing", name)

			# required meals for this pricing = those with mandatory == 1
			required_meals = {row.meal for row in pricing.meals}

			if required_meals == selected_meals:
				matches.append(name)

		if not matches:
			return None

		if len(matches) > 1:
			# Ideally this never happens if you enforce uniqueness in Dish Plan Pricing
			frappe.throw(
				_(
					"Multiple Dish Plan Pricings found for Dish Plan {dish_plan} "
					"with required meals: {meals}. Please fix duplicates."
				).format(
					dish_plan=dish_plan,
					meals=", ".join(sorted(selected_meals)),
				)
			)

		return matches[0]


	
	selected_meals = {m.meal for m in order.meals if m.meal}

	pricing_name = None
	if selected_meals and not is_my_way_plan(order.dish_plan):
		# MY WAY has no maximum meals per day, so matching a Dish Plan Pricing by its
		# exact meal set would need one pricing document per possible meal count —
		# unbounded, and a missing one falls through to default_pricing_plan at a
		# silently wrong price. MY WAY is priced per meal at a flat rate, so it goes
		# straight to the plan's default pricing.
		pricing_name = get_pricing_for_required_meals(order.dish_plan, selected_meals)

	if not pricing_name:
		pricing_name = frappe.db.get_value("Dish Plan", order.dish_plan, "default_pricing_plan")

	order.dish_plan_pricing = pricing_name

	pricing_plan = frappe.get_cached_doc("Dish Plan Pricing", order.dish_plan_pricing)

	pricing_plan_meals = {p.meal: p.per_day_price for p in pricing_plan.meals}

	order.items = []

	dish_plan = frappe.get_cached_doc("Dish Plan", order.dish_plan)
	meals = {}

	for m in dish_plan.meals:
		meals[m.meal] = m

	meals_list = [d.meal for d in order.meals]

	if is_my_way_plan(order.dish_plan):
		error = _add_my_way_items(order, items, meals_list, pricing_plan_meals)
		if error:
			return error
	else:
		_add_dish_plan_items(order, items, meals, meals_list, pricing_plan_meals)

	order.ignore_pricing_rule = 1
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.flags.ignore_addresses = True
	order.flags.rates_set_by_api = True
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist(methods=["GET"])
def get_addresses():
	addresses = frappe.get_all("Address", filters=[["Dynamic Link", "link_doctype", "=", "User"], ["Dynamic Link", "link_name", "=", frappe.session.user]], fields=[])
	for d in addresses:
		d.doc = frappe.get_doc("Address", d.name)

	return send_success_response("", "", addresses)


@frappe.whitelist(methods=["POST"])
def update_address(address_id, data):
	doc = frappe.get_doc("Address", address_id)
	protected_keys = {"name", "doctype", "owner", "links"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}
	if "delivery_days" in clean_data:
		doc.delivery_days = []
	doc.update(clean_data)
	doc.flags.ignore_validate = True
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.update(clean_data)
	doc.address_line1 = "Zone {0}, Street No {1}, Building No {2}, Unit No {3}".format(doc.zone, doc.street_no, doc.building_no, doc.unit_no)
	doc.save()
	frappe.db.commit()
	message_en = "Address updated successfully."
	message_ar = "تم تحديث العنوان بنجاح."
	return send_success_response(message_en, message_ar, doc)

@frappe.whitelist(methods=["POST"])
def add_address(data):
	protected_keys = {"name", "doctype", "owner", "links"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}
	doc = frappe.new_doc("Address")
	doc.update(clean_data)
	doc.links = []
	doc.append("links",{"link_doctype": "User", "link_name": frappe.session.user})
	doc.address_line1 = "Zone {0}, Street No {1}, Building No {2}, Unit No {3}".format(doc.zone, doc.street_no, doc.building_no, doc.unit_no)
	doc.flags.ignore_validate = True
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	frappe.db.commit()

	message_en = "Address created successfully."
	message_ar = "تم إنشاء العنوان بنجاح."

	return send_success_response(message_en, message_ar, doc)


@frappe.whitelist(methods=["POST"])
def remove_address(address_id):
	address = frappe.get_all("Address", filters=[["Dynamic Link", "link_doctype", "=", "User"], ["Dynamic Link", "link_name", "=", frappe.session.user], ["Address", "name", "=", address_id]], fields=[])
	if not address:
		message_en = "Address not found or does not belong to your account."
		message_ar = "العنوان غير موجود أو لا يخص حسابك."

		errors = {
			"access_denied": ["Address not found or does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	doc = frappe.get_doc("Address", address_id)
	doc.links = []
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	message_en = "Address removed successfully."
	message_ar = "تم حذف العنوان بنجاح."

	return send_success_response(message_en, message_ar, doc)


@frappe.whitelist(methods=["GET"])
def verify_addresses(order_id):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	data = validate_addresses(order, throw=False)
	if data["status"] == "success":
		order = data["data"]
		order.flags.ignore_permissions = True
		order.save()
		frappe.db.commit()

	return data

@frappe.whitelist(methods=["POST"])
def update_contact_information(order_id, data):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	allowed_fields = {"first_name", "gender", "phone", "birth_date", "hear_about_us", "referred_by"}
	clean_data = {k: v for k, v in data.items() if k in allowed_fields}

	user = frappe.get_doc("User", frappe.session.user)
	user.flags.ignore_validate = True
	user.flags.ignore_permissions = True
	user.flags.ignore_mandatory = True
	user.update(clean_data)
	user.save()
	if "first_name" in clean_data:
		order.contact_person_name = clean_data["first_name"]

	if "phone" in clean_data:
		order.contact_phone = clean_data["phone"]

	if not order.contact_person_name:
		order.contact_person_name = user.full_name

	if not order.contact_phone:
		order.contact_phone = user.mobile_no

	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()

	message_en = "Contact Information updated successfully."
	message_ar = "تم تحديث معلومات الاتصال بنجاح."

	return send_success_response(message_en, message_ar, {})

@frappe.whitelist(methods=["GET"])
def get_invoice_print(order_id, lang="en"):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	ss = frappe.get_cached_doc("SavvyEats Settings", "SavvyEats Settings", ignore_permmission=True)

	url = "/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={0}&format={1}&no_letterhead=1&letterhead=No%20Letterhead&settings=%7B%7D&_lang={2}".format(order.name, ss.invoice_print_format, lang)

	return send_success_response("", "", {"url": url})

@frappe.whitelist(methods=["POST"])
def submit_order(order_id):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	order.flags.ignore_permissions = True
	order.submit()
	frappe.db.commit()

	message_en = "Order Created Successfully."
	message_ar = "تم إنشاء الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


