import frappe
from frappe.utils import getdate
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery


def update_actual_date_sales_order():
	orders = frappe.get_all("Sales Order", filters={"docstatus": 1, "subscription_status": "Active"})
	for d in orders:
		doc = frappe.get_doc("Sales Order", d.name)
		sales_order_delivery(doc)
		frappe.db.set_value("Sales Order", d.name, "actual_start_date", doc.actual_start_date)
		frappe.db.set_value("Sales Order", d.name, "actual_end_date", doc.actual_end_date)

	frappe.db.commit()

