import frappe
from frappe.utils import now_datetime, getdate, add_days, add_to_date
from savvyeats.api.payment import verify_payment
from savvyeats.fcm import send_notification_to_user
from frappe.utils import now_datetime
from savvyeats.custom.sales_order_savvyeats import delivery_schedule

def remove_expired_otp():
	frappe.db.sql("""
		delete from `tabOTP Verification` where expiry < %(time)s
	""", {"time": now_datetime()})

def update_expired_orders():
	buffer_days = frappe.db.get_single_value("App Settings", "buffer_days")
	buffer_date = getdate(add_days(getdate(), buffer_days or 0))
	rows = frappe.db.sql("""
		SELECT sod.parent AS sales_order
			FROM `tabSales Order Delivery Days` sod
			JOIN `tabSales Order` so ON so.name = sod.parent
		WHERE
			so.docstatus = 0
			AND so.expired = 0
			AND sod.parenttype = 'Sales Order'
			AND sod.delivery_date IS NOT NULL
		GROUP BY sod.parent
		HAVING %(buffer_date)s > MIN(sod.delivery_date)
	""", {
		"buffer_date": buffer_date
	}, as_dict=True)

	for r in rows:
		frappe.db.set_value("Sales Order", r.sales_order, "expired", 1)

	frappe.db.commit()


def auto_complete_active_orders():
	orders = frappe.get_all("Sales Order", filters={"docstatus": 1, "actual_end_date": ["<", getdate()], "subscription_status": "Active"})
	for d in orders:
		frappe.db.set_value("Sales Order", d.name, "status", "Completed")
		frappe.db.set_value("Sales Order", d.name, "subscription_status", "Completed")

	frappe.db.commit()


def auto_resume_paused_subscriptions():
	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": "Paused",
		"pause_end_date": ["<", getdate()],
	})
	for d in orders:
		frappe.db.set_value("Sales Order", d.name, {
			"subscription_status": "Active",
			"resume_date": getdate(),
		}, update_modified=True)

	frappe.db.commit()



def remove_old_location():
	frappe.db.sql("""
		delete from `tabDriver Location` where DATE(creation) < %(date)s
	""", {"date": getdate()})


def update_payment_logs():
	time = add_to_date(None, minutes=-2)
	pay_logs = frappe.get_all("Payment Log", filters={"modified": ["<=", time], "decision": "ACCEPT", "payment_updated": 0, "document_type": "Sales Order"}, fields=["reference_doc"])
	for d in pay_logs:
		try:
			customer = frappe.db.get_value("Sales Order", d.reference_doc, "customer")
			if customer == "Online Customer":
				frappe.set_user(frappe.db.get_value("Sales Order", d.reference_doc, "owner"))
			else:
				user = frappe.db.get_value("Customer", customer, "user") or "Administrator"
				frappe.set_user(user)
			verify_payment(d.reference_doc)
		except Exception as e:
			pass


def create_subscription_delivery():
	target_date = getdate(add_days(getdate(), 2))

	# If already exists (not cancelled), do nothing
	exists = frappe.db.exists("Subscription Delivery", {"delivery_date": target_date, "docstatus": ["!=", 2]})
	if exists:
		return

	doc = frappe.new_doc("Subscription Delivery")
	doc.delivery_date = target_date
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.fetch_deliveries()
	doc.save()
	doc.submit()


def clear_paused_delivery_items(simulate_date=None):

	today = getdate(simulate_date) if simulate_date else getdate()

	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": "Paused",
	}, fields=["name", "pause_start_date", "pause_end_date", "week_plan"])

	for order_data in orders:
		pause_start = getdate(order_data.pause_start_date)
		pause_end = getdate(order_data.pause_end_date)

		# Get paused delivery dates that still have items, sorted by date
		paused_dates_with_items = frappe.db.sql("""
			SELECT DISTINCT sdd.name AS dd_name, sdd.delivery_date
			FROM `tabSales Order Delivery Days` sdd
			WHERE sdd.parent = %(order)s AND sdd.status = 'Paused'
			  AND sdd.delivery_date >= %(pause_start)s AND sdd.delivery_date <= %(pause_end)s
			  AND sdd.delivery_date <= %(today)s
			  AND EXISTS (
			      SELECT 1 FROM `tabSales Order Item` soi
			      WHERE soi.parent = %(order)s AND soi.delivery_date = sdd.delivery_date
			  )
			ORDER BY sdd.delivery_date ASC
			LIMIT 1
		""", {
			"order": order_data.name,
			"pause_start": pause_start,
			"pause_end": pause_end,
			"today": today,
		}, as_dict=True)

		if not paused_dates_with_items:
			continue

		paused_date = getdate(paused_dates_with_items[0].delivery_date)

		# Get the current last delivery date for this order
		last_date_row = frappe.db.sql("""
			SELECT MAX(delivery_date) AS last_date, MAX(idx) AS max_idx
			FROM `tabSales Order Delivery Days`
			WHERE parent = %(order)s
		""", {"order": order_data.name}, as_dict=True)

		last_date = getdate(last_date_row[0].last_date)
		max_idx = last_date_row[0].max_idx or 0

		# Get week plan days
		week_plan = frappe.get_doc("Week Plan", order_data.week_plan)
		plan_days = [d.day for d in week_plan.days]

		# Generate the next valid delivery date after whichever is later: last date or pause end
		resume_after = max(last_date, pause_end)
		search_start = add_days(resume_after, 1)
		search_end = add_days(search_start, 14)  # search up to 2 weeks ahead
		new_dates, _ = delivery_schedule(search_start, search_end, plan_days, inclusive=True)

		if not new_dates:
			continue

		new_date = new_dates[0]
		day_name = new_date.strftime("%A")

		# Build address map from existing addresses on the order
		address_for_day = ""
		addresses = frappe.get_all("Sales Order Addresses", filters={
			"parent": order_data.name,
			"parenttype": "Sales Order",
		}, fields=["address"])

		for addr_row in addresses:
			try:
				address_doc = frappe.get_doc("Address", addr_row.address)
				for day in address_doc.delivery_days:
					if day.day == day_name:
						address_for_day = addr_row.address
						break
			except Exception:
				pass
			if address_for_day:
				break

		# Create new delivery date row at the bottom
		row = frappe.get_doc({
			"doctype": "Sales Order Delivery Days",
			"parent": order_data.name,
			"parenttype": "Sales Order",
			"parentfield": "delivery_dates",
			"idx": max_idx + 1,
			"delivery_date": new_date,
			"day": day_name,
			"status": "Pending",
			"address": address_for_day,
		})
		row.db_insert()

		# Move items from paused date to new date and set item_code = 'Item Not Selected'
		frappe.db.sql("""
			UPDATE `tabSales Order Item`
			SET delivery_date = %(new_date)s, item_code = 'Item Not Selected'
			WHERE parent = %(order)s AND delivery_date = %(old_date)s
		""", {
			"new_date": new_date,
			"old_date": paused_date,
			"order": order_data.name,
		})

		# Update actual_end_date and end_date
		frappe.db.set_value("Sales Order", order_data.name, {
			"actual_end_date": new_date,
			"end_date": new_date,
		}, update_modified=True)

	frappe.db.commit()



def notify_incomplete_meal_plans():
	# Check if notifications are enabled
	if not frappe.db.get_single_value("App Settings", "enable_meal_notifications"):
		return

	reminder_time = frappe.db.get_single_value("App Settings", "meal_reminder_time")
	if reminder_time:
		now = now_datetime()
		# Parse "HH:MM:SS" or "HH:MM" from the Time field
		time_parts = str(reminder_time).split(":")
		target_hour = int(time_parts[0])
		if now.hour != target_hour:
			return

	threshold = frappe.db.get_single_value("App Settings", "meal_reminder_threshold") or 2
	today = getdate()

	# All active submitted subscriptions
	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": "Active",
	}, fields=["name", "owner"])

	for order in orders:
		# Count future delivery dates that have at least one real item selected
		planned_days = frappe.db.sql("""
			SELECT COUNT(DISTINCT soi.delivery_date) AS cnt
			FROM `tabSales Order Item` soi
			WHERE soi.parent = %(order)s
			  AND soi.delivery_date >= %(today)s
			  AND soi.item_code != 'Item Not Selected'
		""", {"order": order.name, "today": today}, as_dict=True)

		planned_count = (planned_days[0].cnt if planned_days else 0)

		if planned_count >= threshold:
			continue

		user = order.owner

		# Skip if already notified today (check Frappe Notification Log)
		already_notified = frappe.db.exists("Notification Log", {
			"for_user": user,
			"type": "Alert",
			"subject": ["like", "%meals planned%"],
			"creation": [">=", today],
		})
		if already_notified:
			continue

		# Build messages
		title_en = "Plan Your Upcoming Meals"
		if planned_count == 0:
			body_en = "You have no meals planned for upcoming days. Please add meals to continue your service without interruption."
			body_ar = "ليس لديك وجبات مخططة للأيام القادمة. يرجى إضافة الوجبات لمواصلة خدمتك دون انقطاع."
		else:
			body_en = f"You only have meals planned for the next {planned_count} day(s). Please add meals for upcoming days to continue your service without interruption."
			body_ar = f"لديك وجبات مخططة لـ {planned_count} يوم/أيام قادمة فقط. يرجى إضافة الوجبات للأيام القادمة لمواصلة خدمتك دون انقطاع."

		notification = frappe.new_doc("Notification Log")
		notification.for_user = user
		notification.type = "Alert"
		notification.subject = f"You only have meals planned for {planned_count} upcoming day(s)"
		notification.email_content = body_en
		notification.flags.ignore_permissions = True
		notification.insert()

		# Send FCM push notification (best effort)
		try:
			send_notification_to_user(user, title_en, body_en, data_json=None)
		except Exception:
			pass

	frappe.db.commit()