"""Subscription Dashboard: staff create a subscription on a customer's behalf.

Phase 1 (live): staff create or pick a Customer and open an empty draft
subscription for them — the same draft the app's get_draft_order starts from.
When that person signs up or logs in to the app with the same mobile number,
link_customer_by_mobile (wired through hooks, not the app's API) attaches the
Customer to their User and the draft shows up in the app, where they finish the
plan and pay. See create_draft_subscription.

Everything the dashboard needs lives in this module; the mobile app's API
(savvyeats.api.*) is only imported from, never changed.

Full flow (built, hidden on the page until a later phase) covers what the mobile
app does up to checkout — customer details, plan, period, delivery addresses — and
leaves the order as an unpaid draft. Meals are
not picked here: every delivery date gets the same "Item Not Selected" rows the
app's add_items produces when nothing is chosen, so the order is priced exactly
as it would be from the app and dishes can be swapped in later.

MY WAY plans are excluded: they are priced per component, so an order with no
components selected would come out at zero.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from savvyeats.api.order import _add_dish_plan_items
from savvyeats.api.utils import MY_WAY_UI_TYPE
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery

WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _check_access():
	# Every endpoint here is staff-only. Being whitelisted, they are otherwise callable
	# by any logged-in user — app customers included.
	frappe.has_permission("Sales Order", "create", throw=True)


@frappe.whitelist()
def get_setup_data():
	_check_access()
	settings = frappe.get_cached_doc("App Settings")
	today_date = getdate(today())

	dish_plans = []
	for name in frappe.get_all(
		"Dish Plan",
		filters={"enabled": 1, "ui_type": ["!=", MY_WAY_UI_TYPE]},
		order_by="sorting_order asc",
		pluck="name",
	):
		plan = frappe.get_cached_doc("Dish Plan", name)
		if plan.has_date_limit and plan.end_date and getdate(plan.end_date) < today_date:
			continue

		week_plans = []
		for wp in plan.week_plans:
			days = [d.day for d in frappe.get_cached_doc("Week Plan", wp.week_plan).days]
			week_plans.append({"name": wp.week_plan, "days": days})

		dish_plans.append({
			"name": plan.name,
			"label": plan.display_plan_name or plan.plan_name,
			"ui_type": plan.ui_type,
			"has_date_limit": cint(plan.has_date_limit),
			"start_date": plan.start_date,
			"end_date": plan.end_date,
			"min_calories": cint(plan.min_calories),
			"max_calories": cint(plan.max_calories),
			"meals": [
				{"meal": m.meal, "mandatory": cint(m.mandatory), "min_qty": cint(m.min_qty), "max_qty": cint(m.max_qty)}
				for m in plan.meals
			],
			"week_plans": week_plans,
		})

	return {
		"dish_plans": dish_plans,
		"delivery_time_slots": frappe.get_all(
			"Delivery Time Slot",
			filters={"enabled": 1},
			fields=["name", "from_time", "to_time"],
			order_by="sorting_order asc",
		),
		"allergens": frappe.get_all("Allergen", filters={"enabled": 1}, order_by="allergen asc", pluck="name"),
		"health_goals": frappe.get_all("Health Goal", filters={"enabled": 1}, order_by="health_goal asc", pluck="name"),
		"max_weeks": cint(settings.max_weeks),
		"max_months": cint(settings.max_months),
		"buffer_days": cint(settings.buffer_days),
		"week_days": WEEK_DAYS,
	}


@frappe.whitelist()
def get_customer_details(customer):
	_check_access()
	frappe.has_permission("Customer", "read", customer, throw=True)
	cust = frappe.db.get_value(
		"Customer", customer, ["name", "customer_name", "mobile_no", "email_id", "gender", "user"], as_dict=True
	)
	if not cust:
		frappe.throw(_("Customer {0} not found").format(customer))

	cust.addresses = [_address_summary(name) for name in _customer_address_names(cust)]
	cust.draft_order = _open_draft(cust.name)
	return cust


@frappe.whitelist(methods=["POST"])
def create_draft_subscription(data):
	"""Phase 1: a Customer plus an empty draft subscription for the app to pick up.

	The draft has exactly the shape get_draft_order creates (is_online, not expired,
	no plan), so the app resumes it as the customer's checkout. A customer keeps a
	single open draft — get_draft_order only ever reads one — so an existing one is
	returned instead of creating another.
	"""
	_check_access()
	data = frappe._dict(frappe.parse_json(data))

	customer = _get_or_create_customer(data)
	cust = frappe.db.get_value("Customer", customer, ["customer_name", "mobile_no", "user"], as_dict=True)
	if not cust.user and not cust.mobile_no:
		frappe.throw(_("Customer {0} has no mobile no, so the draft could never reach their app.").format(customer))

	name = _open_draft(customer)
	reused = bool(name)
	if not reused:
		order = frappe.get_doc({
			"doctype": "Sales Order",
			"customer": customer,
			"customer_name": cust.customer_name,
			"title": cust.customer_name,
			"is_online": 1,
			"expired": 0,
			"transaction_date": today(),
		})
		order.flags.ignore_validate = True
		order.flags.ignore_mandatory = True
		order.insert()
		name = order.name

	# Already an app user: hand the order over now, as link_customer_by_mobile would.
	if cust.user:
		frappe.db.set_value("Sales Order", name, "owner", cust.user, update_modified=False)

	return {
		"name": name,
		"reused": reused,
		"customer": customer,
		"customer_name": cust.customer_name,
		"mobile_no": cust.mobile_no,
		"user": cust.user,
	}


def _open_draft(customer):
	return frappe.db.get_value(
		"Sales Order", {"customer": customer, "docstatus": 0, "is_online": 1, "expired": 0}, "name"
	)


@frappe.whitelist()
def preview_subscription(data):
	"""Price and schedule the subscription without saving anything."""
	_check_access()
	data = frappe._dict(frappe.parse_json(data))
	errors = _plan_errors(data)
	if errors:
		return {"errors": errors}

	order = _make_order(data, data.get("customer") or "Online Customer")

	lines = {}
	for row in order.items:
		line = lines.setdefault(row.meal, {"meal": row.meal, "qty": 0, "rate": flt(row.rate), "amount": 0})
		line["qty"] += flt(row.qty)
		line["amount"] += flt(row.qty) * flt(row.rate)

	return {
		"errors": [],
		"dish_plan_pricing": order.dish_plan_pricing,
		"start_date": order.actual_start_date,
		"end_date": order.actual_end_date,
		"delivery_count": len(order.delivery_dates),
		"lines": list(lines.values()),
		"subtotal": sum(line["amount"] for line in lines.values()),
		**_address_coverage(data, {d.day for d in order.delivery_dates}),
	}


@frappe.whitelist(methods=["POST"])
def create_subscription(data):
	_check_access()
	data = frappe._dict(frappe.parse_json(data))

	errors = _plan_errors(data)
	if errors:
		frappe.throw("<br>".join(errors), title=_("Cannot create subscription"))

	customer = _get_or_create_customer(data)
	customer_name = frappe.db.get_value("Customer", customer, "customer_name")
	mobile_no = frappe.db.get_value("Customer", customer, "mobile_no")

	order = _make_order(data, customer)
	order.contact_person_name = data.get("contact_person_name") or customer_name
	order.contact_phone = data.get("contact_phone") or mobile_no

	for address in _resolve_addresses(data, customer, customer_name, mobile_no):
		order.append("addresses", {"address": address})

	# Same flags as the app's add_items: rates come from the Dish Plan Pricing, not the
	# price list, and must not be re-derived by pricing rules on save. Addresses are
	# deliberately *not* skipped — the validate hook checks every delivery day is
	# covered by exactly one address.
	order.ignore_pricing_rule = 1
	order.flags.rates_set_by_api = True
	order.insert()

	return {
		"name": order.name,
		"customer": order.customer,
		"customer_name": order.customer_name,
		"dish_plan_pricing": order.dish_plan_pricing,
		"start_date": order.actual_start_date,
		"end_date": order.actual_end_date,
		"delivery_count": len(order.delivery_dates),
		"net_total": order.net_total,
		"total_taxes_and_charges": order.total_taxes_and_charges,
		"grand_total": order.rounded_total or order.grand_total,
		"currency": order.currency,
	}


def _plan_errors(data):
	errors = []
	plan_name = data.get("dish_plan")
	if not plan_name or not frappe.db.exists("Dish Plan", plan_name):
		return [_("Select a Dish Plan.")]

	plan = frappe.get_cached_doc("Dish Plan", plan_name)
	if not plan.enabled:
		errors.append(_("Dish Plan {0} is disabled.").format(plan_name))
	if plan.ui_type == MY_WAY_UI_TYPE:
		errors.append(_("MY WAY plans cannot be created from the Subscription Dashboard yet."))

	plan_meals = {m.meal: m for m in plan.meals}
	selected = data.get("meals") or []
	if not selected:
		errors.append(_("Select at least one meal."))
	for meal in selected:
		if meal not in plan_meals:
			errors.append(_("Meal {0} is not part of {1}.").format(meal, plan_name))
	for meal, row in plan_meals.items():
		if row.mandatory and meal not in selected:
			errors.append(_("Meal {0} is mandatory for {1}.").format(meal, plan_name))

	if data.get("week_plan") not in [wp.week_plan for wp in plan.week_plans]:
		errors.append(_("Select a Week Plan of {0}.").format(plan_name))

	settings = frappe.get_cached_doc("App Settings")
	period_type = data.get("period_type")
	period_count = cint(data.get("period_count"))
	limit = {"Week": cint(settings.max_weeks), "Month": cint(settings.max_months)}.get(period_type)
	if limit is None:
		errors.append(_("Select a period (Week or Month)."))
	elif period_count < 1 or (limit and period_count > limit):
		errors.append(_("Number of {0}s must be between 1 and {1}.").format(period_type.lower(), limit or "∞"))

	if not data.get("start_date"):
		errors.append(_("Select a Start Date."))
	else:
		start = getdate(data.start_date)
		if start < getdate(today()):
			errors.append(_("Start Date cannot be in the past."))
		if plan.has_date_limit and plan.start_date and plan.end_date and not (
			getdate(plan.start_date) <= start <= getdate(plan.end_date)
		):
			errors.append(
				_("{0} can only start between {1} and {2}.").format(
					plan_name, frappe.format(plan.start_date, "Date"), frappe.format(plan.end_date, "Date")
				)
			)

	if not data.get("delivery_time_slot"):
		errors.append(_("Select a Delivery Time Slot."))

	if not errors:
		pricing = _resolve_pricing(plan_name, selected)
		if not pricing:
			errors.append(_("No Dish Plan Pricing is configured for {0}.").format(plan_name))
		else:
			priced = {m.meal for m in frappe.get_cached_doc("Dish Plan Pricing", pricing).meals}
			for meal in selected:
				if meal not in priced:
					errors.append(_("Dish Plan Pricing {0} has no price for {1}.").format(pricing, meal))

	return errors


def _resolve_pricing(dish_plan, meals):
	"""Same lookup as api.order.add_items: the enabled pricing whose meal set matches
	exactly, else the plan's default pricing."""
	meals = set(meals)
	matches = [
		name
		for name in frappe.get_all(
			"Dish Plan Pricing",
			filters={"dish_plan": dish_plan, "enabled": 1, "docstatus": ["<", 2]},
			pluck="name",
		)
		if {row.meal for row in frappe.get_cached_doc("Dish Plan Pricing", name).meals} == meals
	]
	if len(matches) > 1:
		frappe.throw(
			_("Multiple Dish Plan Pricings found for Dish Plan {0} with meals: {1}. Please fix duplicates.").format(
				dish_plan, ", ".join(sorted(meals))
			)
		)
	return (matches[0] if matches else None) or frappe.db.get_value("Dish Plan", dish_plan, "default_pricing_plan")


def _make_order(data, customer):
	"""Build the unsaved Sales Order: plan fields, delivery schedule and priced rows."""
	plan = frappe.get_cached_doc("Dish Plan", data.dish_plan)
	plan_meals = {m.meal: m for m in plan.meals}
	selected = [m.meal for m in plan.meals if m.meal in (data.get("meals") or [])]

	order = frappe.new_doc("Sales Order")
	order.customer = customer
	order.transaction_date = today()
	order.order_type = "Sales"
	order.is_online = 0
	order.dish_plan = plan.name
	order.week_plan = data.week_plan
	order.period_type = data.period_type
	order.period_count = cint(data.period_count)
	order.start_date = getdate(data.start_date)
	order.delivery_time_slot = data.delivery_time_slot
	order.meal_choice = data.get("meal_choice") or "User Select Meal"

	for meal in selected:
		order.append("meals", {"meal": meal})
	for allergen in data.get("allergens") or []:
		order.append("allergens", {"allergen": allergen})
	for goal in data.get("health_goals") or []:
		order.append("health_goals", {"health_goal": goal})

	sales_order_delivery(order)

	order.dish_plan_pricing = _resolve_pricing(plan.name, selected)
	pricing = frappe.get_cached_doc("Dish Plan Pricing", order.dish_plan_pricing)
	pricing_meals = {p.meal: p.per_day_price for p in pricing.meals}

	# No items selected: every delivery date gets the meal's min_qty placeholder rows.
	_add_dish_plan_items(order, [], plan_meals, selected, pricing_meals)
	return order


def _get_or_create_customer(data):
	if data.get("customer"):
		if data.customer == "Online Customer" or not frappe.db.exists("Customer", data.customer):
			frappe.throw(_("Select a valid customer."))
		frappe.has_permission("Customer", "read", data.customer, throw=True)
		if frappe.db.get_value("Customer", data.customer, "disabled"):
			frappe.throw(_("Customer {0} is disabled.").format(data.customer))
		return data.customer

	details = frappe._dict(data.get("new_customer") or {})
	customer_name = (details.customer_name or "").strip()
	# Stored the way the app stores User.mobile_no, so signup can match on it.
	mobile_no = normalize_mobile(details.mobile_no)
	email_id = (details.email_id or "").strip()

	if not customer_name:
		frappe.throw(_("Customer Name is required."))
	if not mobile_no:
		frappe.throw(_("Mobile No is required."))

	existing = frappe.db.get_value(
		"Customer", {"mobile_no": ["in", [mobile_no, "974" + mobile_no, "+974" + mobile_no]]}, "name"
	)
	if existing:
		frappe.throw(
			_("Customer {0} already has mobile no {1}. Select the existing customer instead.").format(
				frappe.bold(existing), mobile_no
			)
		)

	customer = frappe.new_doc("Customer")
	customer.customer_name = customer_name
	customer.customer_type = "Individual"
	customer.gender = details.gender or None
	# Customer.on_update turns these into the primary Contact.
	customer.mobile_no = mobile_no
	customer.email_id = email_id or None
	customer.insert()
	return customer.name


def _resolve_addresses(data, customer, customer_name, mobile_no):
	allowed = set(_customer_address_names(frappe._dict(name=customer, user=frappe.db.get_value("Customer", customer, "user"))))
	names = []
	for name in data.get("addresses") or []:
		if name not in allowed:
			frappe.throw(_("Address {0} does not belong to customer {1}.").format(name, customer))
		names.append(name)

	for row in data.get("new_addresses") or []:
		row = frappe._dict(row)
		address = frappe.new_doc("Address")
		address.address_title = row.address_title or customer_name
		address.address_type = "Shipping"
		address.zone = row.zone
		address.street_no = row.street_no
		address.building_no = row.building_no
		address.unit_no = row.unit_no
		address.city = row.city or "Doha"
		address.country = frappe.db.get_default("country") or "Qatar"
		address.phone = mobile_no
		address.delivery_instructions = row.delivery_instructions
		address.latitude = row.latitude
		address.longitude = row.longitude
		for day in row.delivery_days or []:
			address.append("delivery_days", {"day": day})
		address.append("links", {"link_doctype": "Customer", "link_name": customer})
		address.insert()
		names.append(address.name)

	return names


def _customer_address_names(customer):
	"""Addresses linked to the Customer, plus those the app linked to its User."""
	links = [["Customer", customer.name]]
	if customer.get("user"):
		links.append(["User", customer.user])

	names = []
	for link_doctype, link_name in links:
		for name in frappe.get_all(
			"Address",
			filters=[
				["Dynamic Link", "link_doctype", "=", link_doctype],
				["Dynamic Link", "link_name", "=", link_name],
				["Address", "disabled", "=", 0],
			],
			pluck="name",
		):
			if name not in names:
				names.append(name)
	return names


def _address_summary(name):
	address = frappe.get_doc("Address", name)
	return {
		"name": address.name,
		"address_title": address.address_title,
		"address_line1": address.address_line1,
		"city": address.city,
		"delivery_instructions": address.get("delivery_instructions"),
		"delivery_days": [d.day for d in address.get("delivery_days") or []],
	}


def _address_coverage(data, needed_days):
	"""Mirror of validate_addresses for addresses that may not exist yet.

	Returns which address delivers on each weekday plus the problems that would make
	the Sales Order's validate hook reject the order.
	"""
	coverage = {day: [] for day in WEEK_DAYS}
	issues = []
	sources = [(frappe.db.get_value("Address", name, "address_title") or name, frappe.get_all("Address Delivery Days", filters={"parent": name, "parenttype": "Address"}, pluck="day"))
		for name in data.get("addresses") or []]
	sources += [((r.get("address_title") or _("New address")), r.get("delivery_days") or [])
		for r in data.get("new_addresses") or []]

	for label, days in sources:
		for day in days:
			if day in coverage:
				coverage[day].append(label)

	if not sources:
		issues.append(_("Add at least one delivery address."))
	for day in WEEK_DAYS:
		if len(coverage[day]) > 1:
			issues.append(_("{0} is set on more than one address: {1}.").format(day, ", ".join(coverage[day])))
		elif day in needed_days and not coverage[day]:
			issues.append(_("No address delivers on {0}.").format(day))

	return {
		"needed_days": [day for day in WEEK_DAYS if day in needed_days],
		"coverage": coverage,
		"address_issues": issues,
	}


# --- Linking a dashboard customer to the app user ---------------------------


def normalize_mobile(mobile_no):
	"""Local 8-digit form of a Qatar mobile number, as the app stores it on the User.

	Staff may type it with the country code ("+974 5551 2345", "0097455512345").
	"""
	digits = "".join(c for c in (mobile_no or "") if c.isdigit())
	if digits.startswith("00"):
		digits = digits[2:]
	if digits.startswith("974") and len(digits) > 8:
		digits = digits[3:]
	return digits


def link_customer_on_signup(doc, method=None):
	"""User after_insert hook — the app's signup (api.user.verify_otp) creates the User."""
	link_customer_by_mobile(doc.name)


def link_customer_on_login(login_manager):
	"""on_login hook — covers people who already had an app account."""
	link_customer_by_mobile(login_manager.user)


def link_customer_by_mobile(user):
	"""Attach a dashboard-created Customer to the app User with the same mobile number
	and hand that User the Customer's draft subscription.

	The app finds orders by owner and validate_sales_order rejects any order the
	session user does not own, so setting Customer.user alone would leave the draft
	invisible. Deliberately narrow, so it cannot touch anyone else's data:

	* only Website Users (app accounts) that have no Customer yet;
	* only Customers with no User whose mobile matches *and* that hold an open
	  dashboard draft — an ordinary desk Customer with the same number is left alone;
	* exactly one match, never a guess;
	* only draft orders change owner; submitted history is untouched.

	Runs inside the app's signup and login, so it must never break them.
	"""
	frappe.db.savepoint("dashboard_link_customer")
	try:
		if not user or frappe.db.get_value("User", user, "user_type") != "Website User":
			return
		if frappe.db.exists("Customer", {"user": user}):
			return

		mobile = normalize_mobile(frappe.db.get_value("User", user, "mobile_no"))
		if not mobile:
			return

		customers = [
			name
			for name in frappe.get_all(
				"Customer",
				filters={
					"mobile_no": ["in", [mobile, "974" + mobile, "+974" + mobile]],
					"user": ["is", "not set"],
					"disabled": 0,
				},
				pluck="name",
			)
			if _open_draft(name)
		]
		if len(customers) != 1:
			if customers:
				frappe.log_error(
					title="Subscription Dashboard: customer link skipped",
					message="User {0} matches several customers with mobile {1}: {2}".format(
						user, mobile, ", ".join(customers)
					),
				)
			return

		customer = customers[0]
		frappe.db.set_value("Customer", customer, "user", user, update_modified=False)
		for order in frappe.get_all("Sales Order", filters={"customer": customer, "docstatus": 0}, pluck="name"):
			frappe.db.set_value("Sales Order", order, "owner", user, update_modified=False)
	except Exception:
		frappe.db.rollback(save_point="dashboard_link_customer")
		frappe.log_error(title="Subscription Dashboard: customer link failed")
