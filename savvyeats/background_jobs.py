import frappe
from frappe.utils import now_datetime

def remove_expired_otp():
	frappe.db.sql("""
		delete from `tabOTP Verification` where expiry < %(time)s
	""", {"time": now_datetime()})