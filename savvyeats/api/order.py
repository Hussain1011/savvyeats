import frappe
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["GET"])
def get_draft_order(new=False):
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})

	order_filters = {"docstatus": 0}

	if customer:
		order_filters["customer"] = customer[0].name
	else:
		order_filters["owner"] = frappe.session.user
		order_filters["customer"] = "Online Customer"

	orders = frappe.get_all("Sales Order", filters=order_filters, fields=["name"], limit=1)

	if orders:
		order = frappe.get_doc("Sales Order", orders[0].name, ignore_permissions=True)

		if frappe.utils.cint(new):
			_reset_sales_order_in_place(order)
			order.flags.ignore_validate = True
			order.flags.ignore_permissions = True
			order.flags.ignore_mandatory = True
			order.save()
			frappe.db.commit()
	else:
		order_filters["doctype"] = "Sales Order"
		order = frappe.get_doc(order_filters)
		order.flags.ignore_validate = True
		order.flags.ignore_permissions = True
		order.flags.ignore_mandatory = True
		order.insert()
		frappe.db.commit()

	return send_success_response("", "", order)


def _reset_sales_order_in_place(order):
	order.po_no = None
	order.po_date = None
	order.shipping_address_name = None
	order.shipping_address = None
	order.billing_address_name = None
	order.billing_address = None
	order.total_qty = 0
	order.total_net_weight = 0
	order.base_total = 0
	order.base_net_total = 0
	order.total = 0
	order.net_total = 0
	order.base_total_taxes_and_charges = 0
	order.total_taxes_and_charges = 0
	order.base_grand_total = 0
	order.base_rounding_adjustment = 0
	order.base_rounded_total = 0
	order.grand_total = 0
	order.rounding_adjustment = 0
	order.rounded_total = 0
	order.advance_paid = 0
	order.base_discount_amount = 0
	order.additional_discount_percentage = 0
	order.discount_amount = 0
	order.per_delivered = 0
	order.per_billed = 0
	order.per_picked = 0
	order.amount_eligible_for_commission = 0
	order.commission_rate = 0
	order.total_commission = 0
	order.loyalty_points = 0
	order.loyalty_amount = 0
	order.delivery_days = 0
	order.total_days = 0
	order.status = "Draft"
	order.delivery_status = "Not Delivered"
	order.billing_status = "Not Billed"
	order.order_type = "Sales"
	order.apply_discount_on = "Grand Total"
	order.disable_rounded_total = 0
	order.ignore_pricing_rule = 0
	order.reserve_stock = 0
	order.group_same_items = 0
	order.is_internal_customer = 0
	order.dish_plan = None
	order.period_type = None
	order.period_count = 0
	order.transaction_date = frappe.utils.nowdate()
	order.pricing_rules = []
	order.allergens = []
	order.items = []
	order.meals = []
	order.taxes = []
	order.payment_schedule = []
	order.packed_items = []
	order.delivery_dates = []
	order.sales_team = []
	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()


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



