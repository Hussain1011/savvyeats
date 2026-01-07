import frappe
from frappe.utils import now_datetime, getdate, add_days

def remove_expired_otp():
	frappe.db.sql("""
		delete from `tabOTP Verification` where expiry < %(time)s
	""", {"time": now_datetime()})


def remove_old_location():
	frappe.db.sql("""
		delete from `tabDriver Location` where DATE(creation) < %(date)s
	""", {"date": getdate()})

def create_subscription_delivery():
	target_date = getdate(add_days(getdate(), 2))

	# If already exists (not cancelled), do nothing
	exists = frappe.db.exists("Subscription Delivery", {"delivery_date": target_date, "docstatus": ["!=", 2]})
	if exists:
		return

	doc = frappe.new_doc("Subscription Delivery")
	doc.delivery_date = target_date
	doc.insert(ignore_permissions=True)

	# This will create draft Delivery Notes + now also auto-replace placeholders
	doc.fetch_deliveries()
	doc.save(ignore_permissions=True)
	doc.submit(ignore_permissions=True)