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
	delivery_creation_days = frappe.db.get_single_value("App Settings", "delivery_creation_days")
	if delivery_creation_days is None:
		delivery_creation_days = 2

	today = getdate()

	# Ensure a Subscription Delivery exists for EVERY date from today up to
	# today + delivery_creation_days. This makes the daily automation self-healing:
	# if the scheduler missed a run (server/worker down), the gap is backfilled on
	# the next run instead of permanently skipping a delivery day. Each date is
	# handled independently so one bad date cannot block the others.
	for offset in range(0, int(delivery_creation_days) + 1):
		target_date = getdate(add_days(today, offset))
		try:
			_create_delivery_for_date(target_date)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title="Subscription Delivery: daily creation failed",
				message="Delivery Date: {0}\n\n{1}".format(target_date, frappe.get_traceback()),
			)


def _create_delivery_for_date(target_date):
	# If one already exists (not cancelled) for this date, do nothing.
	exists = frappe.db.exists("Subscription Delivery", {"delivery_date": target_date, "docstatus": ["!=", 2]})
	if exists:
		return

	doc = frappe.new_doc("Subscription Delivery")
	doc.delivery_date = target_date
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.fetch_deliveries()
	if not doc.items:
		doc.delete()
		frappe.db.commit()
		return
	doc.save()
	doc.submit()
	frappe.db.commit()


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

	# Active and Pending (scheduled renewal) subscriptions — so customers are reminded
	# to select meals for an upcoming renewal's first deliveries too.
	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": ["in", ["Active", "Pending"]],
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


def notify_subscription_ending():
	if not frappe.db.get_single_value("App Settings", "enable_subscription_end_reminder"):
		return

	reminder_days = frappe.db.get_single_value("App Settings", "subscription_end_reminder_days") or 3
	today = getdate()
	target_date = getdate(add_days(today, reminder_days))

	# Use a date range (today .. target_date) instead of an exact match so that a
	# subscription is still caught even if the scheduler missed a day. Each
	# subscription is reminded only once (see de-dup below).
	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": "Active",
		"actual_end_date": ["between", [today, target_date]],
	}, fields=["name", "owner", "customer_name", "actual_end_date"])

	for order in orders:
		user = order.owner

		# Skip if this subscription was already reminded (one reminder per subscription,
		# regardless of which day the job ran).
		already_notified = frappe.db.exists("Notification Log", {
			"for_user": user,
			"type": "Alert",
			"subject": ["like", f"%subscription ending%{order.name}%"],
		})
		if already_notified:
			continue

		end_date = getdate(order.actual_end_date)
		title_en = "Subscription Ending Soon"
		body_en = f"Your subscription {order.name} is ending on {end_date}. Renew now to continue enjoying your meals without interruption."

		notification = frappe.new_doc("Notification Log")
		notification.for_user = user
		notification.type = "Alert"
		notification.subject = f"Your subscription ending soon - {order.name}"
		notification.email_content = body_en
		notification.flags.ignore_permissions = True
		notification.insert()

		# FCM push notification to user
		try:
			send_notification_to_user(user, title_en, body_en)
		except Exception:
			pass

		# Email to user (customer)
		try:
			frappe.sendmail(
				recipients=[user],
				subject=f"Subscription Ending Soon - {order.name}",
				message=f"""Dear {order.customer_name},<br><br>
Your subscription <a href="https://app.savvyeats.com/app/sales-order/{order.name}">{order.name}</a> is ending on {end_date}.<br>
Renew now to continue enjoying your meals without interruption.""",
				now=True,
			)
		except Exception:
			frappe.log_error("Subscription End User Email Failed")

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
					subject=f"Subscription Ending Soon - {order.name}",
					message=f"""Subscription ending soon <a href="https://app.savvyeats.com/app/sales-order/{order.name}">{order.name}</a><br><br>
Customer Name: {order.customer_name}<br>
End Date: {end_date}""",
					now=True,
				)
		except Exception:
			frappe.log_error("Subscription End System Manager Email Failed")

	frappe.db.commit()


def notify_unselected_next_delivery():
	"""Remind users when an UPCOMING delivery has no meals selected.

	This is a separate feature from `notify_incomplete_meal_plans` (which is a
	"running low on planned days" nudge based on a total count). This one targets a
	single upcoming delivery date and reminds the user only if every item for that
	date is still 'Item Not Selected'. Each delivery date triggers at most one reminder.
	"""
	if not frappe.db.get_single_value("App Settings", "enable_next_delivery_meal_reminder"):
		return

	# Only run during the configured hour (job is scheduled hourly).
	reminder_time = frappe.db.get_single_value("App Settings", "next_delivery_reminder_time")
	if reminder_time:
		now = now_datetime()
		time_parts = str(reminder_time).split(":")
		target_hour = int(time_parts[0])
		if now.hour != target_hour:
			return

	days_before = frappe.db.get_single_value("App Settings", "next_delivery_reminder_days_before")
	if days_before is None:
		days_before = 1
	target_date = getdate(add_days(getdate(), days_before))

	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": ["in", ["Active", "Pending"]],
	}, fields=["name", "owner"])

	for order in orders:
		# Does this subscription have a delivery on the target date at all?
		has_delivery = frappe.db.exists("Sales Order Item", {
			"parent": order.name,
			"delivery_date": target_date,
		})
		if not has_delivery:
			continue

		# Has the user selected at least one real item for that delivery?
		selected = frappe.db.sql("""
			SELECT COUNT(*) AS cnt
			FROM `tabSales Order Item`
			WHERE parent = %(order)s
			  AND delivery_date = %(date)s
			  AND item_code != 'Item Not Selected'
		""", {"order": order.name, "date": target_date}, as_dict=True)[0].cnt

		if selected:
			continue  # already chose meals for that delivery

		user = order.owner

		# One reminder per delivery date (de-dup across all runs).
		already_notified = frappe.db.exists("Notification Log", {
			"for_user": user,
			"type": "Alert",
			"subject": ["like", f"%select your meals%{target_date}%"],
		})
		if already_notified:
			continue

		title_en = "Select Your Meals"
		body_en = (
			f"You haven't selected your meals for your delivery on {target_date}. "
			"Please choose your meals before the cutoff so your delivery isn't missed."
		)
		body_ar = (
			f"لم تقم باختيار وجباتك لتوصيلة يوم {target_date}. "
			"يرجى اختيار وجباتك قبل الموعد النهائي حتى لا تفوتك التوصيلة."
		)

		notification = frappe.new_doc("Notification Log")
		notification.for_user = user
		notification.type = "Alert"
		notification.subject = f"Please select your meals for {target_date}"
		notification.email_content = body_en
		notification.flags.ignore_permissions = True
		notification.insert()

		# Send FCM push notification (best effort)
		try:
			send_notification_to_user(user, title_en, body_en)
		except Exception:
			pass

	frappe.db.commit()


def activate_scheduled_subscriptions():
	"""Pre-Renewal (Issue 9): on its start date, flip a scheduled renewal from
	Pending -> Active. The previous subscription is completed by
	auto_complete_active_orders once its actual_end_date passes."""
	if not frappe.db.get_single_value("App Settings", "enable_pre_renewal"):
		return

	today = getdate()
	pending = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": "Pending",
		"start_date": ["<=", today],
	}, pluck="name")

	for name in pending:
		frappe.db.set_value("Sales Order", name, "subscription_status", "Active", update_modified=True)

	frappe.db.commit()


def send_renewal_reminders():
	"""Pre-Renewal (Issue 9 / BR-8): once per day, remind every customer who is
	Active, inside renewal_window_days of their actual_end_date, and has no upcoming
	renewal yet. Backend owns the stop condition (stops once a renewal exists or the
	subscription ends)."""
	if not frappe.db.get_single_value("App Settings", "enable_pre_renewal"):
		return

	window = frappe.db.get_single_value("App Settings", "renewal_window_days") or 7
	today = getdate()
	window_end = getdate(add_days(today, window))

	orders = frappe.get_all("Sales Order", filters={
		"docstatus": 1,
		"subscription_status": "Active",
		"actual_end_date": ["between", [today, window_end]],
	}, fields=["name", "owner", "customer_name", "actual_end_date"])

	for order in orders:
		# Stop condition: a scheduled renewal already exists for this subscription.
		has_upcoming = frappe.db.exists("Sales Order", {
			"renewal_of": order.name,
			"subscription_status": "Pending",
			"docstatus": 1,
		})
		if has_upcoming:
			continue

		user = order.owner

		# One reminder per day per subscription.
		already_notified = frappe.db.exists("Notification Log", {
			"for_user": user,
			"type": "Alert",
			"subject": ["like", f"%renew%{order.name}%"],
			"creation": [">=", today],
		})
		if already_notified:
			continue

		end_date = getdate(order.actual_end_date)
		title_en = "Renew Your Subscription"
		body_en = (
			f"Your subscription ends on {end_date}. Renew now to keep your meals coming "
			"with no interruption."
		)

		notification = frappe.new_doc("Notification Log")
		notification.for_user = user
		notification.type = "Alert"
		notification.subject = f"Time to renew - {order.name}"
		notification.email_content = body_en
		notification.flags.ignore_permissions = True
		notification.insert()

		# Deep link payload routes the app to My Plan / Subscription Details (Renew CTA).
		try:
			send_notification_to_user(
				user, title_en, body_en,
				data_json=frappe.as_json({"route": "subscription_details", "order": order.name, "action": "renew"}),
			)
		except Exception:
			pass

	frappe.db.commit()