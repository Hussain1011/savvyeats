import frappe
from frappe.utils import now_datetime, getdate

def remove_expired_otp():
	frappe.db.sql("""
		delete from `tabOTP Verification` where expiry < %(time)s
	""", {"time": now_datetime()})


def remove_old_location():
	frappe.db.sql("""
		delete from `tabDriver Location` where DATE(creation) < %(date)s
	""", {"date": getdate()})