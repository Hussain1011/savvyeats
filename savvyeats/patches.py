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


def update_item_kitchen_name():
	items = frappe.get_all("Item", filters={"variant_of": ["!=", ""]})
	attributes = frappe.get_doc("Item Attribute", "Dish Plan")
	att_dict = {}
	for at in attributes.item_attribute_values:
		att_dict[at.attribute_value] = at

	for d in items:
		doc = frappe.get_doc("Item", d.name)
		for a in doc.attributes:
			if a.attribute == "Dish Plan":
				doc.kitchen_name = "{0} - {1}".format(doc.variant_of, att_dict[a.attribute_value].abbr)
				break

		frappe.db.set_value("Item", doc.name, "kitchen_name", doc.kitchen_name)
		frappe.db.commit()
