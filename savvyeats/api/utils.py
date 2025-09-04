import frappe

def get_customers_for_user(user: str):
	contact = frappe.db.get_value("Contact", {"user": user}, "name")
	customers = []
	if contact:
		customers = frappe.get_all(
			"Dynamic Link",
			filters={
				"parenttype": "Contact",
				"parent": contact,
				"link_doctype": "Customer",
			},
			pluck="link_name",
		)
	if not customers:
		customers = frappe.get_all(
			"Customer",
			filters={"email_id": ["in", [user, frappe.db.get_value("User", user, "email")]]},
			pluck="name",
		)

    return customers
