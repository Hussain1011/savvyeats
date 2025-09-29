import frappe
from frappe.utils import getdate, add_to_date, date_diff
from datetime import timedelta
from frappe import _
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"])
def get_dashboard(today=None):
	today = getdate(today)
	orders = frappe.get_all("Sales Order", filters={"docstatus": 1, "owner": frappe.session.user, "status": ["not in", ["Completed", "Cancelled", "Closed"]]})
	if not orders:
		return send_success_response("", "", {})

	order = frappe.get_doc("Sales Order", orders[0].name, ignore_permissions=True)

	nutrients = frappe._dict()
	nutrients_list = frappe.db.sql(""" select * from delivery_daily_nutrients_view where subscription = %(order)s """, {
			"order": order.name
		}, as_dict=True)
	for n in nutrients_list:
		nutrients[n.posting_date] = n


	meal_nutrients = frappe._dict()
	meal_nutrients_list = frappe.db.sql(""" select * from delivery_meal_nutrients_view where subscription = %(order)s """, {
			"order": order.name
		}, as_dict=True)
	for n in meal_nutrients_list:
		if n.posting_date not in meal_nutrients:
			meal_nutrients[n.posting_date] = []
		meal_nutrients[n.posting_date].append(n)

	dates = frappe._dict()

	for d in order.delivery_dates:
		dates[str(d.delivery_date)] = {}
		if d.delivery_date in nutrients:
			dates[str(d.delivery_date)] = nutrients[d.delivery_date]
			dates[str(d.delivery_date)]["meals"] = meal_nutrients[d.delivery_date]

	today_delivery = {}
	deliveries = frappe.db.sql("""
		SELECT *
		FROM deliveries
		WHERE sales_order = %(sales_order)s
		ORDER BY delivery_date
		""", {
		"sales_order": order.name,
		"delivery_date": today
	}, as_dict=True)
	if deliveries:
		today_delivery = deliveries[0]

	data = {"order": order, "dates": dates, "today_delivery": today_delivery}

	return send_success_response("", "", data)