import frappe
from frappe import _
from frappe.utils import getdate
from savvyeats.api.user import send_error_response, send_success_response
import json

@frappe.whitelist(methods=["GET"])
def get_current_subscription():
	orders = frappe.get_all("Sales Order", filters={"docstatus": 1, "owner": frappe.session.user, "status": ["not in", ["Completed", "Cancelled", "Closed"]]})
	if not orders:
		return send_success_response("", "", {})

	order = frappe.get_doc("Sales Order", orders[0].name, ignore_permissions=True)

	return send_success_response("", "", order)

@frappe.whitelist(methods=["GET"])
def get_deliveries(limit_start=0, today=None):
	today = getdate(today)
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})
	if not customer:
		return send_success_response("", "", {})

	limit_start = int(limit_start) if limit_start else 0
	limit_page_length = 10

	deliveries = frappe.db.sql("""
		SELECT *
		FROM deliveries
		WHERE customer = %(customer)s
		ORDER BY delivery_date
		LIMIT %(limit_start)s, %(page_length)s
		""", {
		"customer": customer[0].name,
		"limit_start": limit_start,
		"page_length": limit_page_length
	}, as_dict=True)
		
	if not deliveries:
		return send_success_response("", "", {})

	today_delivery = [d for d in deliveries if getdate(d.delivery_date) == today]

	return send_success_response("", "", {"today": today_delivery[0] if today_delivery else {}, "all": deliveries})

@frappe.whitelist(methods=["GET"])
def get_delivery_details(delivery_id):
	doc = frappe.get_doc("Delivery Note", delivery_id, ignore_permissions=True).as_dict()
	doc.shipping_address_doc = {}
	if doc.shipping_address_name:
		doc.shipping_address_doc = frappe.get_doc("Address", doc.shipping_address_name, ignore_permissions=True)

	doc.customer_address_doc = {}
	if doc.customer_address:
		doc.customer_address_doc = frappe.get_doc("Address", doc.customer_address, ignore_permissions=True)

	deliveries = frappe.db.sql("""
		SELECT *
		FROM deliveries
		WHERE delivery_note = %(delivery_note)s
		ORDER BY delivery_date
		""", {
		"delivery_note": doc.name
	}, as_dict=True)

	doc.delivery_details = deliveries[0] if deliveries else {}

	return send_success_response("", "", doc)


@frappe.whitelist(methods=["GET"])
def get_delivery_location(delivery_id):
	location = frappe.get_all("Driver Location", filters={"delivery_note": delivery_id, "actual": 1}, fields=["*"], order_by="timestamp asc", limit_page_length=1)
	return send_success_response("", "", {"location": location})

@frappe.whitelist(methods=["POST"])
def rate_delivery_item(delivery_id, item_row_id, rating):
	if not frappe.db.exists("Delivery Note Item", item_row_id):
		message_en = "Delivery item not found."
		message_ar = "لم يتم العثور على عنصر التسليم."
		errors = {
			"not_found": ["Delivery item not found."]
		}
		return send_error_response(message_en, message_ar, errors)
	
	frappe.db.set_value("Delivery Note Item", item_row_id, "rating", rating)
	frappe.db.commit()
	message_en = "Rating updated successfully."
	message_ar = "تم تحديث التقييم بنجاح."
	return send_success_response(message_en, message_ar, {})



@frappe.whitelist(methods=["POST"])
def rate_delivery(delivery_id, data):
	if not frappe.db.exists("Delivery Note", delivery_id):
		message_en = "Delivery not found."
		message_ar = "لم يتم العثور على عملية التسليم."
		errors = {
			"not_found": ["Delivery not found."]
		}
		return send_error_response(message_en, message_ar, errors)
	
	doc = frappe.get_doc("Delivery Note", delivery_id)
	doc.rating = data["rating"]
	doc.comments = data["comments"]
	doc.improved_suggestions = []
	for d in data["improved_suggestions"]:
		doc.append("improved_suggestions", {"improved_suggestion": d})
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	message_en = "Rating updated successfully."
	message_ar = "تم تحديث التقييم بنجاح."
	return send_success_response(message_en, message_ar, {})
