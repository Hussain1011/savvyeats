import frappe
from frappe import _
from frappe.utils import getdate
from savvyeats.api.user import send_error_response, send_success_response
import json

@frappe.whitelist(methods=["GET"])
def get_current_subscription():
	orders = frappe.get_all("Sales Order", filters={"docstatus": 1, "owner": frappe.session.user, "status": ["not in", ["Completed", "Cancelled", "Closed"]]})
	if not orders:
		return send_success_response("", "", {})

	order = frappe.get_doc("Sales Order", orders[0].name, ignore_permissions=True)

	return send_success_response("", "", order)

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
	return send_success_response(
		"Subscription paused successfully.",
		"تم إيقاف الاشتراك بنجاح.",
		order
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
