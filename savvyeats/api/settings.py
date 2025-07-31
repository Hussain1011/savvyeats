import frappe

@frappe.whitelist(methods=["GET"], allow_guest=True)
def get_settings():
	doc = frappe.get_cached_doc({"doctype": "App Settings", "name": "App Settings"}, ignore_permmission=True)
	return doc