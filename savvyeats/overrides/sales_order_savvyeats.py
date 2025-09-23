import frappe
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from frappe.utils import cint, get_datetime, get_link_to_form


class SalesOrderOverride(SalesOrder):
	pass
		