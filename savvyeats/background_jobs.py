import frappe
from frappe.utils import now_datetime, getdate, add_days, add_to_date
from savvyeats.api.payment import verify_payment

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



def remove_old_location():
	frappe.db.sql("""
		delete from `tabDriver Location` where DATE(creation) < %(date)s
	""", {"date": getdate()})


def update_payment_logs():
	time = add_to_date(None, minutes=-2)
	pay_logs = frappe.get_all("Payment Log", filters={"modified": ["<=", time], "decision": "ACCEPT", "payment_updated": 1, "document_type": "Sales Order"}, fields=["reference_doc"])
	for d in pay_logs:
		try:
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