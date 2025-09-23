import frappe
import random
from frappe.utils import add_to_date, now_datetime, escape_html, getdate, get_datetime
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"])
def get_delivery_trips(driver_id):
	today = getdate()
	start_time = get_datetime("{0} 00:00:00".format(str(today)))
	end_time = get_datetime("{0} 23:59:59".format(str(today)))
	delivery_trips_list = frappe.get_all("Delivery Trip", filters={"driver": driver_id, "docstatus": 1, "status": "Scheduled", "departure_time": ["between", [start_time, end_time]]})
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


@frappe.whitelist(methods=["POST"])
def start_delivery(driver_id, delivery_trip_id, delivery_stop_id, data):
	try:
		frappe.db.set_value("Delivery Stop", delivery_stop_id, "delivery_status", "In Transit")
		frappe.db.set_value("Delivery Stop", delivery_stop_id, "locked", 1)
		doc = update_driver_location(driver_id, delivery_trip_id, delivery_stop_id, data, return_data=True, start=True)
	except Exception as e:
		message_en = "Error starting delivery."
		message_ar = "خطأ في بدء التوصيل."
		errors = {
			"error": ["Error starting delivery."]
		}
		return send_error_response(message_en, message_ar, errors)

	return send_success_response("", "", doc)


@frappe.whitelist(methods=["POST"])
def update_delivery_status(driver_id, delivery_trip_id, delivery_stop_id, data):
	try:
		allowed_fields = {"delivery_status", "failure_reason", "failure_reason_details", "delivery_proof", "driver_notes"}
		clean_data = {k: v for k, v in data.items() if k in allowed_fields}

		for i,v in clean_data.items():
			frappe.db.set_value("Delivery Stop", delivery_stop_id, i, v)
			if i == "delivery_status" and v == "Delivered":
				frappe.db.set_value("Delivery Stop", delivery_stop_id, "visited", 1)
				frappe.db.set_value("Delivery Stop", delivery_stop_id, "end_time", get_datetime())
				
	except Exception as e:
		message_en = "Error updating delivery status."
		message_ar = "خطأ في تحديث حالة التوصيل."

		errors = {
			"error": ["Error updating delivery status."]
		}
		return send_error_response(message_en, message_ar, errors)

	return send_success_response("", "", {})


@frappe.whitelist(methods=["POST"])
def update_driver_location(driver_id, delivery_trip_id, delivery_stop_id, data, return_data=False, start=False):
	try:
		doc = frappe.new_doc("Driver Location")
		doc.driver = driver_id
		doc.delivery_trip = delivery_trip_id
		doc.delivery_stop = delivery_stop_id
		doc.update(data)
		doc.flags.ignore_permissions = True
		if start:
			doc.flags.start = True
		doc.save()
		frappe.db.commit()
		if return_data:
			return doc
	except Exception as e:
		message_en = "Error updating driver location."
		message_ar = "خطأ في تحديث موقع السائق."

		errors = {
			"error": ["Error updating delivery status."]
		}
		return send_error_response(message_en, message_ar, errors)

	return send_success_response("", "", {})

