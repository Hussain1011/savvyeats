import frappe
from frappe import _
from frappe.utils import getdate, add_days, date_diff, cint
from savvyeats.api.user import send_error_response, send_success_response
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery, delivery_schedule
import json

@frappe.whitelist(methods=["GET"])
def get_current_subscription():
	orders = frappe.get_all(
		"Sales Order",
		filters={"docstatus": 1, "owner": frappe.session.user, "status": ["not in", ["Completed", "Cancelled", "Closed"]]},
		order_by="creation asc",
	)

	current = None
	upcoming = None
	for o in orders:
		doc = frappe.get_doc("Sales Order", o.name, ignore_permissions=True)
		if doc.subscription_status == "Pending":
			if upcoming is None:
				upcoming = doc
		elif doc.subscription_status in ("Active", "Paused"):
			if current is None:
				current = doc

	return send_success_response("", "", {
		"current": current or {},
		"upcoming": upcoming or {},
	})

@frappe.whitelist(methods=["GET"])
def get_deliveries(limit_start=0, today=None):
	today = getdate(today)
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})
	if not customer:
		return send_success_response("", "", {})

	limit_start = int(limit_start) if limit_start else 0
	limit_page_length = 10

	deliveries = frappe.db.sql("""
		SELECT *
		FROM deliveries
		WHERE customer = %(customer)s
		ORDER BY delivery_date
		LIMIT %(limit_start)s, %(page_length)s
		""", {
		"customer": customer[0].name,
		"limit_start": limit_start,
		"page_length": limit_page_length
	}, as_dict=True)
		
	if not deliveries:
		return send_success_response("", "", {})

	today_delivery = [d for d in deliveries if getdate(d.delivery_date) == today]

	return send_success_response("", "", {"today": today_delivery[0] if today_delivery else {}, "all": deliveries})

@frappe.whitelist(methods=["GET"])
def get_delivery_details(delivery_id):
	doc = frappe.get_doc("Delivery Note", delivery_id, ignore_permissions=True).as_dict()
	doc.shipping_address_doc = {}
	if doc.shipping_address_name:
		doc.shipping_address_doc = frappe.get_doc("Address", doc.shipping_address_name, ignore_permissions=True)

	doc.customer_address_doc = {}
	if doc.customer_address:
		doc.customer_address_doc = frappe.get_doc("Address", doc.customer_address, ignore_permissions=True)

	deliveries = frappe.db.sql("""
		SELECT *
		FROM deliveries
		WHERE delivery_note = %(delivery_note)s
		ORDER BY delivery_date
		""", {
		"delivery_note": doc.name
	}, as_dict=True)

	doc.delivery_details = deliveries[0] if deliveries else {}

	return send_success_response("", "", doc)


@frappe.whitelist(methods=["GET"])
def get_delivery_location(delivery_id):
	location = frappe.get_all("Driver Location", filters={"delivery_note": delivery_id, "actual": 1}, fields=["*"], order_by="timestamp asc", limit_page_length=1)
	return send_success_response("", "", {"location": location})

@frappe.whitelist(methods=["POST"])
def rate_delivery_item(delivery_id, item_row_id, rating):
	if not frappe.db.exists("Delivery Note Item", item_row_id):
		message_en = "Delivery item not found."
		message_ar = "لم يتم العثور على عنصر التسليم."
		errors = {
			"not_found": ["Delivery item not found."]
		}
		return send_error_response(message_en, message_ar, errors)
	
	frappe.db.set_value("Delivery Note Item", item_row_id, "rating", rating)
	frappe.db.commit()
	message_en = "Rating updated successfully."
	message_ar = "تم تحديث التقييم بنجاح."
	return send_success_response(message_en, message_ar, {})



@frappe.whitelist(methods=["POST"])
def rate_delivery(delivery_id, data):
	if not frappe.db.exists("Delivery Note", delivery_id):
		message_en = "Delivery not found."
		message_ar = "لم يتم العثور على عملية التسليم."
		errors = {
			"not_found": ["Delivery not found."]
		}
		return send_error_response(message_en, message_ar, errors)
	
	doc = frappe.get_doc("Delivery Note", delivery_id)
	doc.rating = data["rating"]
	doc.comments = data["comments"]
	doc.improved_suggestions = []
	for d in data["improved_suggestions"]:
		doc.append("improved_suggestions", {"improved_suggestion": d})
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	message_en = "Rating updated successfully."
	message_ar = "تم تحديث التقييم بنجاح."
	return send_success_response(message_en, message_ar, {})


@frappe.whitelist(methods=["POST"])
def pause_subscription(order_id, pause_start_date, pause_end_date):
	if not frappe.db.get_single_value("App Settings", "enable_pause_subscription_feature"):
		return send_error_response(
			"Pause subscription feature is currently disabled.",
			"ميزة إيقاف الاشتراك معطلة حاليًا.",
			{"error": ["Pause subscription feature is currently disabled."]}
		)

	order = frappe.get_doc("Sales Order", order_id)
	if order.owner != frappe.session.user:
		return send_error_response(
			"Access denied. This order does not belong to your account.",
			"تم رفض الوصول. هذا الطلب لا يخص حسابك.",
			{"access_denied": ["Access denied. This order does not belong to your account."]}
		)

	if order.docstatus != 1:
		return send_error_response(
			"Order is not submitted.",
			"الطلب غير مقدم.",
			{"error": ["Order is not submitted."]}
		)

	if order.subscription_status != "Active":
		return send_error_response(
			"Subscription is not active.",
			"الاشتراك غير نشط.",
			{"error": ["Subscription is not active."]}
		)

	max_pause = frappe.db.get_single_value("App Settings", "max_pause_count") or 1
	if (order.pause_count or 0) >= max_pause:
		return send_error_response(
			f"Subscription has already been paused {max_pause} time(s). No more pauses allowed.",
			f"تم إيقاف الاشتراك {max_pause} مرة/مرات. لا يُسمح بمزيد من الإيقاف.",
			{"error": [f"Subscription has already been paused {max_pause} time(s). No more pauses allowed."]}
		)

	pause_start = getdate(pause_start_date)
	pause_end = getdate(pause_end_date)

	if pause_end <= pause_start:
		return send_error_response(
			"Pause end date must be after the start date.",
			"يجب أن يكون تاريخ انتهاء الإيقاف بعد تاريخ البداية.",
			{"error": ["Pause end date must be after the start date."]}
		)

	# Find delivery dates within the pause period that are still Pending
	paused_delivery_dates = []
	for dd in order.delivery_dates:
		dd_date = getdate(dd.delivery_date)
		if pause_start <= dd_date <= pause_end and dd.status == "Pending":
			paused_delivery_dates.append(dd)

	if not paused_delivery_dates:
		return send_error_response(
			"No pending deliveries found in the pause period.",
			"لم يتم العثور على عمليات تسليم معلقة في فترة الإيقاف.",
			{"error": ["No pending deliveries found in the pause period."]}
		)

	# Mark paused delivery dates as "Paused"
	for dd in paused_delivery_dates:
		frappe.db.set_value("Sales Order Delivery Days", dd.name, "status", "Paused")

	# Update order fields (no replacement dates yet — cron will add them one by one)
	frappe.db.set_value("Sales Order", order.name, {
		"subscription_status": "Paused",
		"pause_start_date": pause_start,
		"pause_end_date": pause_end,
		"pause_count": (order.pause_count or 0) + 1,
	}, update_modified=True)

	frappe.db.commit()

	send_pause_notification(order, pause_start, pause_end)

	order.reload()

	# BR-7: pausing extends the subscription, so a queued renewal must shift later.
	# Do NOT block the pause when a renewal exists — shift the renewal instead.
	upcoming = _shift_renewal_after_change(order)
	frappe.db.commit()

	data = order.as_dict()
	data["upcoming"] = upcoming
	return send_success_response(
		"Subscription paused successfully.",
		"تم إيقاف الاشتراك بنجاح.",
		data
	)


@frappe.whitelist(methods=["POST"])
def resume_subscription(order_id):
	order = frappe.get_doc("Sales Order", order_id)
	if order.owner != frappe.session.user:
		return send_error_response(
			"Access denied. This order does not belong to your account.",
			"تم رفض الوصول. هذا الطلب لا يخص حسابك.",
			{"access_denied": ["Access denied. This order does not belong to your account."]}
		)

	if order.subscription_status != "Paused":
		return send_error_response(
			"Subscription is not paused.",
			"الاشتراك غير متوقف.",
			{"error": ["Subscription is not paused."]}
		)

	pause_start = getdate(order.pause_start_date)
	pause_end = getdate(order.pause_end_date)

	# Collect paused delivery date rows
	paused_rows = [
		dd for dd in order.delivery_dates
		if dd.status == "Paused" and pause_start <= getdate(dd.delivery_date) <= pause_end
	]

	# Restore unprocessed paused dates (those that still have items) back to Pending
	for dd in paused_rows:
		has_items = frappe.db.exists("Sales Order Item", {
			"parent": order.name,
			"delivery_date": getdate(dd.delivery_date),
		})
		if has_items:
			frappe.db.set_value("Sales Order Delivery Days", dd.name, "status", "Pending")

	# Recalculate actual_end_date from all delivery date rows
	all_dates = [getdate(dd.delivery_date) for dd in order.delivery_dates]
	new_end = max(all_dates) if all_dates else getdate(order.end_date)

	frappe.db.set_value("Sales Order", order.name, {
		"subscription_status": "Active",
		"resume_date": getdate(),
		"actual_end_date": new_end,
		"end_date": new_end,
	}, update_modified=True)

	frappe.db.commit()

	order.reload()
	return send_success_response(
		"Subscription resumed successfully.",
		"تم استئناف الاشتراك بنجاح.",
		order
	)


def send_pause_notification(order, pause_start, pause_end):
	if not frappe.db.get_single_value("App Settings", "enable_pause_notifications"):
		return

	# Email to System Managers
	try:
		system_managers = frappe.get_all(
			"Has Role",
			filters={"role": "System Manager", "parenttype": "User"},
			pluck="parent",
		)
		system_managers = [u for u in system_managers if frappe.db.get_value("User", u, "enabled")]
		if system_managers:
			frappe.sendmail(
				recipients=system_managers,
				subject=f"Subscription Paused {order.name}",
				message=f"""Subscription Paused <a href="https://app.savvyeats.com/app/sales-order/{order.name}">{order.name}</a><br><br>
Customer Name: {order.customer_name}<br>
Pause Start Date: {pause_start}<br>
Pause End Date: {pause_end}""",
				now=True,
			)
	except Exception:
		frappe.log_error("Pause Subscription Email Failed")


# ---------------------------------------------------------------------------
# Pre-Renewal (Issue 9)
# ---------------------------------------------------------------------------

def _compute_renewal_start(current, buffer_days):
	"""BR-2: start_date = max(current.actual_end_date + 1, today + 1 + buffer_days).

	Returns (start_date, has_gap, gap_days). has_gap is True when the kitchen-prep
	buffer pushed the start past the day after the current subscription ends.
	"""
	base_start = add_days(getdate(current.actual_end_date), 1)
	buffer_start = add_days(getdate(), 1 + cint(buffer_days))
	start_date = max(base_start, buffer_start)
	has_gap = start_date > base_start
	gap_days = date_diff(start_date, base_start) if has_gap else 0
	return start_date, has_gap, gap_days


def _renewal_payload(draft, has_gap, gap_days):
	data = draft.as_dict()
	data["subscription_status"] = "Draft"  # unpaid draft renewal (docstatus 0)
	data["has_gap"] = has_gap
	data["gap_days"] = gap_days
	return data


def _copy_renewal_items(current, draft):
	"""Copy the current plan's meal selections onto the renewal's new delivery dates,
	mapped positionally. Same week plan + period => same count + weekday alignment.
	If counts differ (e.g. the current subscription was paused/extended), skip and let
	the app's builder populate the items."""
	current_dates = sorted({getdate(dd.delivery_date) for dd in current.delivery_dates})
	new_dates = sorted({getdate(dd.delivery_date) for dd in draft.delivery_dates})
	if not current_dates or not new_dates or len(current_dates) != len(new_dates):
		return
	date_map = {current_dates[i]: new_dates[i] for i in range(len(current_dates))}
	for it in current.items:
		nd = date_map.get(getdate(it.delivery_date))
		if not nd:
			continue
		draft.append("items", {
			"item_code": it.item_code,
			"item_name": it.item_name,
			"meal": it.meal,
			"delivery_date": nd,
			"qty": it.qty,
			"rate": it.rate,
			"price_list_rate": it.price_list_rate,
			"note": it.note,
			"extra_portion": it.extra_portion,
			"is_extra": it.get("is_extra") or 0,
		})


@frappe.whitelist(methods=["POST"])
def create_renewal(order_id):
	if not frappe.db.get_single_value("App Settings", "enable_pre_renewal"):
		return send_error_response(
			"Pre-renewal is currently disabled.",
			"ميزة التجديد المسبق معطلة حاليًا.",
			{"error": ["Pre-renewal is currently disabled."]},
		)

	current = frappe.get_doc("Sales Order", order_id)

	if current.owner != frappe.session.user:
		return send_error_response(
			"Access denied. This order does not belong to your account.",
			"تم رفض الوصول. هذا الطلب لا يخص حسابك.",
			{"not_owner": ["Access denied. This order does not belong to your account."]},
		)

	if current.subscription_status == "Paused":
		return send_error_response(
			"You cannot renew while your subscription is paused.",
			"لا يمكنك التجديد أثناء إيقاف اشتراكك مؤقتًا.",
			{"paused": ["You cannot renew while your subscription is paused."]},
		)

	if current.docstatus != 1 or current.subscription_status != "Active":
		return send_error_response(
			"Only an active subscription can be renewed.",
			"يمكن تجديد الاشتراك النشط فقط.",
			{"not_active": ["Only an active subscription can be renewed."]},
		)

	# BR-3: at most one Pending renewal per customer.
	existing_pending = frappe.get_all("Sales Order", filters={
		"owner": frappe.session.user,
		"subscription_status": "Pending",
		"docstatus": 1,
	}, limit=1)
	if existing_pending:
		return send_error_response(
			"You already have a scheduled renewal.",
			"لديك بالفعل تجديد مجدول.",
			{"already_scheduled": ["You already have a scheduled renewal."]},
		)

	buffer_days = frappe.db.get_single_value("App Settings", "buffer_days")
	start_date, has_gap, gap_days = _compute_renewal_start(current, buffer_days)

	# Idempotency: if an unpaid draft renewal already exists, return it (refreshed)
	# instead of creating a duplicate. The app resumes it.
	existing_draft = frappe.get_all("Sales Order", filters={
		"owner": frappe.session.user,
		"renewal_of": current.name,
		"docstatus": 0,
	}, limit=1)
	if existing_draft:
		draft = frappe.get_doc("Sales Order", existing_draft[0].name)
		draft.start_date = start_date
		sales_order_delivery(draft)
		draft.flags.ignore_validate = True
		draft.flags.ignore_permissions = True
		draft.flags.ignore_mandatory = True
		draft.flags.ignore_addresses = True
		draft.save()
		frappe.db.commit()
		return send_success_response("", "", _renewal_payload(draft, has_gap, gap_days))

	draft = frappe.new_doc("Sales Order")
	draft.customer = current.customer
	draft.customer_name = current.customer_name
	draft.is_online = 1
	draft.renewal_of = current.name
	draft.dish_plan = current.dish_plan
	draft.dish_plan_pricing = current.dish_plan_pricing
	draft.week_plan = current.week_plan
	draft.period_type = current.period_type
	draft.period_count = current.period_count
	draft.delivery_time_slot = current.delivery_time_slot
	draft.start_date = start_date

	for m in current.meals:
		draft.append("meals", {"meal": m.meal})
	for a in current.allergens:
		draft.append("allergens", {"allergen": a.allergen})
	for h in current.get("health_goals", []):
		draft.append("health_goals", {"health_goal": h.health_goal})
	for ad in current.addresses:
		draft.append("addresses", {"address": ad.address})

	# Compute end_date + delivery_dates from the new start, then copy meals onto them.
	sales_order_delivery(draft)
	_copy_renewal_items(current, draft)

	draft.flags.ignore_validate = True
	draft.flags.ignore_permissions = True
	draft.flags.ignore_mandatory = True
	draft.flags.ignore_addresses = True
	draft.flags.rates_set_by_api = True
	draft.insert()
	frappe.db.commit()

	return send_success_response("", "", _renewal_payload(draft, has_gap, gap_days))


def _project_end_after_pause(order, num_paused):
	"""Project the current subscription's new end date after `num_paused` delivery
	days are pushed past the current end (following the week plan)."""
	if not num_paused:
		return getdate(order.actual_end_date)
	week_plan = frappe.get_doc("Week Plan", order.week_plan)
	plan_days = [d.day for d in week_plan.days]
	search_start = add_days(getdate(order.actual_end_date), 1)
	search_end = add_days(search_start, num_paused * 10 + 30)
	new_dates, _count = delivery_schedule(search_start, search_end, plan_days, inclusive=True)
	if len(new_dates) >= num_paused:
		return new_dates[num_paused - 1]
	return new_dates[-1] if new_dates else getdate(order.actual_end_date)


def _reschedule_renewal(renewal_name, new_start):
	"""Move a Pending renewal to a new start date, remapping its delivery dates and
	items positionally (preserving meal selections and weekday alignment)."""
	renewal = frappe.get_doc("Sales Order", renewal_name)
	old_dates = sorted({getdate(dd.delivery_date) for dd in renewal.delivery_dates})
	if not old_dates:
		return None

	week_plan = frappe.get_doc("Week Plan", renewal.week_plan)
	plan_days = [d.day for d in week_plan.days]
	count = len(old_dates)
	search_end = add_days(getdate(new_start), count * 10 + 30)
	new_dates, _count = delivery_schedule(new_start, search_end, plan_days, inclusive=True)
	new_dates = new_dates[:count]
	if len(new_dates) < count:
		return None

	date_map = {old_dates[i]: new_dates[i] for i in range(count)}

	for dd in renewal.delivery_dates:
		nd = date_map.get(getdate(dd.delivery_date))
		if nd:
			frappe.db.set_value("Sales Order Delivery Days", dd.name,
				{"delivery_date": nd, "day": nd.strftime("%A")}, update_modified=False)

	for it in frappe.get_all("Sales Order Item", filters={"parent": renewal_name}, fields=["name", "delivery_date"]):
		nd = date_map.get(getdate(it.delivery_date))
		if nd:
			frappe.db.set_value("Sales Order Item", it.name, "delivery_date", nd, update_modified=False)

	frappe.db.set_value("Sales Order", renewal_name, {
		"start_date": new_start,
		"actual_start_date": new_dates[0],
		"actual_end_date": new_dates[-1],
		"end_date": new_dates[-1],
	}, update_modified=True)

	renewal.reload()
	return renewal


def _shift_renewal_after_change(current_order):
	"""When the current subscription's end shifts (e.g. a pause), move the queued
	renewal's start so it still begins after the now-longer subscription (BR-7).
	Returns the updated upcoming renewal dict, or None if there is no renewal."""
	pending = frappe.get_all("Sales Order", filters={
		"owner": current_order.owner,
		"renewal_of": current_order.name,
		"subscription_status": "Pending",
		"docstatus": 1,
	}, limit=1, pluck="name")
	if not pending:
		return None

	num_paused = len([dd for dd in current_order.delivery_dates if dd.status == "Paused"])
	projected_end = _project_end_after_pause(current_order, num_paused)

	buffer_days = frappe.db.get_single_value("App Settings", "buffer_days")
	base_start = add_days(getdate(projected_end), 1)
	buffer_start = add_days(getdate(), 1 + cint(buffer_days))
	new_start = max(base_start, buffer_start)

	renewal = _reschedule_renewal(pending[0], new_start)
	if not renewal:
		return None

	has_gap = getdate(renewal.start_date) > base_start
	gap_days = date_diff(getdate(renewal.start_date), base_start) if has_gap else 0
	data = renewal.as_dict()
	data["has_gap"] = has_gap
	data["gap_days"] = gap_days
	return data
