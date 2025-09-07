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
def get_deliveries(limit_start=0):
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})
	if not customer:
		return send_success_response("", "", {})
		
	deliveries = frappe.get_all("Delivery Note", filters={"docstatus": 1, "customer": customer[0].name}, limit_page_length=10, limit_start=limit_start)
	if not deliveries:
		return send_success_response("", "", {})

	today_delivery = {}

	data = []
	for d in deliveries:
		doc = frappe.get_doc("Delivery Note", d.name, ignore_permissions=True)
		doc.shipping_address_doc = {}
		if doc.shipping_address_name:
			doc.shipping_address_doc = frappe.get_doc("Address", doc.shipping_address_name, ignore_permissions=True)

		doc.customer_address_doc = {}
		if doc.customer_address:
			doc.customer_address_doc = frappe.get_doc("Address", doc.customer_address, ignore_permissions=True)


		data.append(doc)
		if getdate(doc.posting_date) == getdate():
			delivery_trip = frappe.get_all("Delivery Trip", filters=[["Delivery Stop", "delivery_note", "=", doc.name], ["Delivery Trip", "docstatus", "=", 1]])
			if delivery_trip:
				doc.delivery_trip = frappe.get_doc("Delivery Trip", delivery_trip[0].name, ignore_permissions=True)
			today_delivery = doc

	return send_success_response("", "", {"today": today_delivery, "all": data})


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
