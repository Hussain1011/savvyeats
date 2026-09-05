import frappe
from frappe import _
from frappe.utils import getdate, today, flt, cint
from savvyeats.api.user import send_error_response, send_success_response
import json
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery, validate_addresses
from savvyeats.api.utils import is_my_way_plan
from erpnext.stock.get_item_details import get_item_price

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



def _reprice_my_way_draft(order):
	"""Re-price a draft MY WAY order after a component swap.

	Component pricing means a swap can change what the plate costs, and update_items
	writes its rows with db.set_value — the only way to touch a submitted order — so
	nothing recalculates the totals on its own. On a draft, re-save the order and let
	ERPNext recompute them from the new components. A **submitted** order is left
	alone on purpose: that plate is already paid for, and swapping chicken for beef
	is a kitchen instruction, not a re-billing event.
	"""
	doc = frappe.get_doc("Sales Order", order.name)
	changed = False

	for row in doc.items:
		meta = frappe.db.get_value(
			"Item", row.item_code, ["serving_size", "stock_uom", "component_category"], as_dict=True
		)
		if not meta or not meta.component_category:
			continue

		price = _component_price(doc, row.item_code, meta.stock_uom)
		if price is None:
			continue

		# The serving count is what the customer chose; a swap keeps it and moves the
		# grams to the new component's serving size.
		grams = flt(row.qty * flt(meta.serving_size)) or flt(row.grams)
		if row.rate == price and row.grams == grams:
			continue

		row.grams = grams
		row.rate = price
		row.price_list_rate = price
		changed = True

	if not changed:
		return

	doc.ignore_pricing_rule = 1
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_addresses = True
	doc.flags.rates_set_by_api = True
	doc.save()


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
		# Portions step by whole servings, so it is the row's serving count that
		# carries over and the grams move to the new component's serving size.
		row_qty = flt(frappe.db.get_value("Sales Order Item", d["name"], "qty")) or 1

		# Re-portioning changes what the plate costs, so it is only honoured while the
		# order is still a draft. On a submitted order a swap is a kitchen instruction,
		# not a re-billing event — see _reprice_my_way_draft.
		if d.get("qty") and order.docstatus == 0:
			row_qty = max(cint(d.get("qty")), 1)
			frappe.db.set_value("Sales Order Item", d["name"], "qty", row_qty)

		if "grams" in d:
			frappe.db.set_value("Sales Order Item", d["name"], "grams", flt(d.get("grams")))
		elif item.serving_size and frappe.db.get_value("Sales Order Item", d["name"], "grams"):
			frappe.db.set_value("Sales Order Item", d["name"], "grams", flt(row_qty * item.serving_size))

	if order.docstatus == 0 and is_my_way_plan(order.dish_plan):
		_reprice_my_way_draft(order)

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


def _component_price(order, item_code, uom):
	"""Selling price of one serving of a MY WAY component, or None if it has none.

	Resolved exactly the way the builder catalogue resolves it
	(`api/items.get_plan_components`), so the price the customer is shown while
	building the plate is the price the plate is charged at (BR-7).
	"""
	price_list = order.selling_price_list or frappe.db.get_value(
		"Selling Settings", None, "selling_price_list"
	)
	price_row = get_item_price(
		{"price_list": price_list, "transaction_date": getdate(), "uom": uom}, item_code
	)
	if price_row:
		return flt(price_row[0][1])

	standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
	return flt(standard_rate) if standard_rate else None


def _portion_qty(grams, serving_size):
	"""A gram figure expressed as a multiple of the component's serving size.

	Only for payloads that carry grams and no qty — an app build older than portion
	stepping. The portion may not land on a whole serving there, hence the fraction.
	"""
	grams = flt(grams)
	serving_size = flt(serving_size)
	if not grams or not serving_size:
		return 1

	qty = flt(grams / serving_size, frappe.get_precision("Sales Order Item", "qty"))
	# A portion that rounds away to nothing would trip ERPNext's zero-qty validation
	# and take the whole order down with it.
	return qty or 1


def _portion(payload, meta):
	"""How many servings the customer asked for, and how many grams that is.

	Portions step by whole servings — a 50 g component is offered as 50 / 100 / 150 /
	200 g — so the app sends `qty` as a count of servings and the grams follow from
	it. That keeps the rate the plain per-serving price from the price list and the
	amount ERPNext's own rate x qty.

	`grams` is still the number the kitchen packs and the macros scale by (BR-2), but
	it is *derived* here rather than taken from the payload, so the two can never
	disagree about the same portion. An app build older than portion stepping sends
	grams and no qty; that path still works, fraction and all.
	"""
	serving_size = flt(meta.get("serving_size"))

	if payload.get("qty"):
		qty = max(cint(payload.get("qty")), 1)
		return qty, (flt(qty * serving_size) or flt(payload.get("grams")))

	grams = flt(payload.get("grams")) or serving_size
	return _portion_qty(grams, serving_size), grams


def _add_my_way_items(order, items, meals_list):
	"""Build the item rows for a MY WAY (build-your-own) order.

	MY WAY is priced at the **component** level: each component carries its own Item
	Price and a plate costs the sum of what is actually on it, so a two-component
	snack is genuinely cheaper than a four-component main meal. Four consequences,
	all deliberate:

	* **No meal header row and no Dish Plan Pricing.** `per_day_price` prices a meal
	  *slot*, which on top of priced components would bill every plate twice. An
	  order's `grand_total` is already nothing but sum(rate x qty) over its rows, so
	  the components alone are the whole price — MY WAY needs no pricing document,
	  and none of the combinatorial "one pricing per meal count" problem with it.
	* **qty is the serving count.** Portions step by whole servings, so qty is how
	  many servings are on the plate and the rate stays the per-serving catalogue
	  price the app shows in the builder. `grams` (qty x serving_size) still carries
	  the portion the kitchen packs and the macros scale by.
	* **`is_extra` flagging.** A dish meal holds one item; a MY WAY meal holds one
	  per category. Flagging components 2..N as extras would bill them separately
	  and drop them from the calorie count — the number the feature exists to show.
	* **Filler "Item Not Selected" rows.** A snack legitimately carries fewer
	  categories than a main meal, so padding every meal out to max_qty would invent
	  phantom lines. The app blocks checkout until each day is complete.

	Returns an error response dict when the order cannot be priced, else None.
	"""
	# Category, serving size and UOM all come from the Item, never from the payload:
	# BR-1 (one component per category per meal) is a server-side rule and BR-7 makes
	# the price ours to compute. The client is trusted with neither.
	item_codes = {v["item_code"] for v in items if v.get("item_code")}
	item_meta = {}
	if item_codes:
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", list(item_codes)]},
			fields=["name", "component_category", "serving_size", "stock_uom"],
		):
			item_meta[r.name] = r

	plates = {}
	loose = []

	for v in items:
		meal = v.get("meal", "")
		if meal and meal not in meals_list:
			continue

		if not meal:
			# Add-ons and anything else not tied to a meal: no plate, and the rate is
			# left for ERPNext to resolve from the price list.
			loose.append(v)
			continue

		delivery_date = getdate(v["delivery_date"])
		plate = plates.setdefault((delivery_date, meal), {})
		meta = item_meta.get(v["item_code"]) or frappe._dict()
		# BR-1, last write wins. Falling back to the item code keeps an uncategorised
		# component rather than collapsing it into whatever else has no category.
		plate[meta.get("component_category") or v["item_code"]] = v

	rows = []
	for (delivery_date, meal), components in plates.items():
		for v in components.values():
			meta = item_meta.get(v["item_code"]) or frappe._dict()
			qty, grams = _portion(v, meta)
			rows.append(frappe._dict({
				"item": v,
				"meta": meta,
				"meal": meal,
				"delivery_date": delivery_date,
				"grams": grams,
				"qty": qty,
			}))

	# Under component pricing an unpriced component is not a cosmetic problem: the
	# row falls through to zero and the customer is handed that part of the plate for
	# free. Fail the whole order instead of quietly under-charging it.
	prices = {}
	unpriced = set()
	for code in {r.item.get("item_code") for r in rows}:
		price = _component_price(order, code, (item_meta.get(code) or frappe._dict()).get("stock_uom"))
		if price is None:
			unpriced.add(code)
		else:
			prices[code] = price

	if unpriced:
		codes = ", ".join(sorted(unpriced))
		message_en = "No price is configured for: {0}.".format(codes)
		message_ar = "لا يوجد سعر مهيأ لـ: {0}.".format(codes)
		return send_error_response(
			message_en, message_ar, {"component_price_not_configured": [message_en]}
		)

	# Serving counts are whole numbers, so this only bites the grams-only path above.
	# ERPNext refuses a fractional qty outright on a whole-number UOM; say it here,
	# naming the setup that has to change, rather than letting save() throw an error
	# that points at the UOM alone.
	fractional_uoms = {
		r.meta.get("stock_uom")
		for r in rows
		if r.meta.get("stock_uom") and cint(r.qty) != r.qty
	}
	whole_number_uoms = set()
	if fractional_uoms:
		whole_number_uoms = set(frappe.get_all(
			"UOM",
			filters={"name": ["in", list(fractional_uoms)], "must_be_whole_number": 1},
			pluck="name",
		))

	if whole_number_uoms:
		offenders = ", ".join(sorted({
			r.item["item_code"] for r in rows if r.meta.get("stock_uom") in whole_number_uoms
		}))
		uoms = ", ".join(sorted(whole_number_uoms))
		message_en = (
			"A portion needs a fractional quantity, but the UOM of {0} must be a whole "
			"number. Give these components a UOM such as Gram, or clear 'Must be Whole "
			"Number' on UOM {1}."
		).format(offenders, uoms)
		message_ar = (
			"الحصة تحتاج كمية كسرية، لكن وحدة القياس للأصناف {0} يجب أن تكون رقماً صحيحاً. "
			"استخدم وحدة مثل الجرام لهذه المكونات، أو أزل خيار 'يجب أن يكون رقماً صحيحاً' من وحدة القياس {1}."
		).format(offenders, uoms)
		return send_error_response(
			message_en, message_ar, {"component_uom_not_fractional": [message_en]}
		)

	for r in rows:
		row = order.append("items")
		row.item_code = r.item["item_code"]
		row.meal = r.meal
		row.delivery_date = r.delivery_date
		row.note = r.item.get("note", "")
		# BR-2: grams stay authoritative for the kitchen and the macros; qty carries
		# the same portion in a shape ERPNext can price.
		row.grams = r.grams
		row.qty = r.qty
		row.extra_portion = 0
		row.is_extra = 0
		row.rate = prices[r.item["item_code"]]
		row.price_list_rate = row.rate

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
	my_way = is_my_way_plan(order.dish_plan)

	pricing_plan_meals = {}

	if my_way:
		# MY WAY is priced per component, so it has no Dish Plan Pricing to look up —
		# and matching one by exact meal set could not work anyway: with no maximum
		# meals per day that needs one pricing document per possible meal count.
		order.dish_plan_pricing = None
	else:
		pricing_name = None
		if selected_meals:
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

	if my_way:
		error = _add_my_way_items(order, items, meals_list)
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


