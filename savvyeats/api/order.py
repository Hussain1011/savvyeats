import frappe
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"])
def get_draft_order():
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})
	order_details = {"docstatus": 0}
	if customer:
		order_details["customer"] = customer[0].name
	else:
		order_details["owner"] = frappe.session.user
		order_details["customer"] = "Online Customer"

	orders = frappe.get_all("Sales Order", filters=order_details)
	if orders:
		order = frappe.get_doc("Sales Order", orders[0].name, ignore_permmission=True)
	else:
		order_details["doctype"] = "Sales Order"
		order = frappe.get_doc(order_details)
		order.flags.ignore_validate = True
		order.flags.ignore_permissions = True
		order.flags.ignore_mandatory = True
		order.insert()
		frappe.db.commit()
	return send_success_response("", "", order)


@frappe.whitelist(methods=["POST"])
def update_draft_order(order_id, data):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	protected_keys = {"name", "doctype", "owner", "customer"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}

	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.update(clean_data)
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)



