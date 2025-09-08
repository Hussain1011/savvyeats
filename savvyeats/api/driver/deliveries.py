import frappe
import random
from frappe.utils import add_to_date, now_datetime, escape_html, getdate
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"])
def get_delivery_trips(driver_id):
	today = getdate()
	start_time = "{0} 00:00:00".format(str(today))
	end_time = "{0} 23:59:59".format(str(today))
	delivery_trips_list = frappe.get_all("Delivery Trip", filters={"driver": driver_id, "docstatus": 1, "status": "Scheduled", "departure_time": [">=", start_time], "departure_time": ["<=", end_time]})
	if not delivery_trips_list:
		return send_success_response("", "", {"delivery_trips": []})
	delivery_trips = []
	for d in delivery_trips_list:
		doc = frappe.get_doc("Delivery Trip", d.name, ignore_permissions=True).as_dict()
		for ds in doc.delivery_stops:
			ds.address_doc = frappe.get_doc("Address", ds.address, ignore_permissions=True)
			ds.address_doc = frappe.get_doc("Address", ds.address, ignore_permissions=True)

		delivery_trips.append(doc)

	return send_success_response("", "", {"delivery_trips": delivery_trips})


@frappe.whitelist(methods=["GET"])
def start_delivery(driver_id):
	delivery_trips_list = frappe.get_all("Delivery Trip", filters={"driver": driver_id, "docstatus": 1})
	if not delivery_trips_list:
		return send_success_response("", "", {"delivery_trips": []})
	delivery_trips = []
	for d in delivery_trips_list:
		doc = frappe.get_doc("Delivery Trip", d.name, ignore_permissions=True).as_dict()
		for ds in doc.delivery_stops:
			ds.address_doc = frappe.get_doc("Address", ds.address, ignore_permissions=True)

		delivery_trips.append(doc)

	return send_success_response("", "", {"delivery_trips": delivery_trips})