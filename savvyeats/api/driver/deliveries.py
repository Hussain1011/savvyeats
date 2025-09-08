import frappe
import random
from frappe.utils import add_to_date, now_datetime, escape_html
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"])
def get_delivery_trips(driver_id):
	delivery_trips_list = frappe.get_all("Delivery Trip", filters={"driver": driver_id, "docstatus": 1, "status": "Scheduled", "start_time": })
	if not delivery_trips_list:
		return send_success_response("", "", {"delivery_trips": []})
	delivery_trips = []
	for d in delivery_trips_list:
		doc = frappe.get_doc("Delivery Trip", d.name, ignore_permissions=True).as_dict()
		for ds in doc.delivery_stops:
			ds.delivery_note_doc = frappe.get_doc("Delivery Note", ds.delivery_note, ignore_permissions=True)

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
			ds.delivery_note_doc = frappe.get_doc("Delivery Note", ds.delivery_note, ignore_permissions=True)

		delivery_trips.append(doc)

	return send_success_response("", "", {"delivery_trips": delivery_trips})