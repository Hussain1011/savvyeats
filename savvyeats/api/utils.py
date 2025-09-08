import frappe

@frappe.whitelist(methods=["POST"])
def log_error(error):
	frappe.log_error(title="SavvyEats App Error", message=str(error))
	frappe.db.commit()