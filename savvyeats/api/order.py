import frappe
from frappe import _
from frappe.utils import getdate, today
from savvyeats.api.user import send_error_response, send_success_response
import json
from savvyeats.custom.sales_order_savvyeats import sales_order_delivery, validate_addresses

def validate_sales_order(order_id):
	try:
		order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
		if order.owner != frappe.session.user:
			message_en = "Access denied. This order does not belong to your account."
			message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

			errors = {
				"access_denied": ["Access denied. This order does not belong to your account."]
			}
			return send_error_response(message_en, message_ar, errors)
	except Exception as e:
		message_en = "Order not found."
		message_ar = "لم يتم العثور على الطلب."
		errors = {
			"not_found": ["Order not found."]
		}
		return send_error_response(message_en, message_ar, errors)

	return order

@frappe.whitelist(methods=["GET"])
def get_draft_order(new=False):
	customer = frappe.get_all("Customer", filters={"user": frappe.session.user})

	order_filters = {"docstatus": 0, "is_online": 1}

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
	order.is_online = 1
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
	order.dish_plan_pricing = ""
	order.period_type = None
	order.period_count = 0
	order.transaction_date = frappe.utils.nowdate()
	order.pricing_rules = []
	order.allergens = []
	order.items = []
	order.meals = []
	order.taxes = []
	order.addresses = []
	order.customer_address = ""
	order.week_plan = ""
	order.delivery_time_slot = ""
	order.start_date = ""
	order.end_date = ""
	order.payment_schedule = []
	order.packed_items = []
	order.delivery_dates = []
	order.delivery_date = ""
	order.sales_team = []
	order.coupon_code = ""
	order.additional_discount_percentage = 0
	order.discount_amount = 0
	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()


@frappe.whitelist(methods=["POST"])
def update_draft_order(order_id, data):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	protected_keys = {"name", "doctype", "owner", "customer", "items", "ignore_pricing_rule"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}

	if "meals" in clean_data:
		order.meals = []

	if "allergens" in clean_data:
		order.allergens = []

	if "addresses" in clean_data:
		order.addresses = []

	order.update(clean_data)

	sales_order_delivery(order)

	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist(methods=["POST"])
def validate_draft_order(order_id, data):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	protected_keys = {"name", "doctype", "owner", "customer", "items", "ignore_pricing_rule"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}

	if "meals" in clean_data:
		order.meals = []

	if "allergens" in clean_data:
		order.allergens = []

	if "addresses" in clean_data:
		order.addresses = []

	order.update(clean_data)

	sales_order_delivery(order)

	order.flags.ignore_permissions = True
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist(methods=["POST"])
def apply_voucher_code(order_id, voucher_code):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	if not frappe.db.exists("Coupon Code", voucher_code):
		message_en = "Invalid or missing voucher code."
		message_ar = "رمز القسيمة غير صالح أو مفقود."

		errors = {
			"not_found": ["Invalid or missing voucher code."]
		}
		return send_error_response(message_en, message_ar, errors)

	coupon = frappe.get_doc("Coupon Code", voucher_code )

	if coupon.valid_from:
		if coupon.valid_from > getdate(today()):
			message_en = "Coupon code validity has not started."
			message_ar = "رمز القسيمة غير صالح أو مفقود."

			errors = {
				"validity_issue": ["Coupon code validity has not started."]
			}
			return send_error_response(message_en, message_ar, errors)
	elif coupon.valid_upto:
		if coupon.valid_upto < getdate(today()):
			message_en = "The coupon code has expired."
			message_ar = "انتهت صلاحية رمز القسيمة."

			errors = {
				"expired": ["The coupon code has expired."]
			}
			return send_error_response(message_en, message_ar, errors)
	elif coupon.used >= coupon.maximum_use:
		message_en = "This coupon is no longer valid."
		message_ar = "لم تعد هذه القسيمة صالحة."

		errors = {
			"expired": ["This coupon is no longer valid."]
		}
		return send_error_response(message_en, message_ar, errors)


	try:
		order.flags.ignore_permissions = True
		order.coupon_code = coupon.name
		order.save()
		frappe.db.commit()
		message_en = "Order updated successfully."
		message_ar = "تم تحديث الطلب بنجاح."
		return send_success_response(message_en, message_ar, order)
	except Exception as e:
		message_en = "This coupon is no longer valid."
		message_ar = "لم تعد هذه القسيمة صالحة."

		errors = {
			"expired": ["This coupon is no longer valid."]
		}
		return send_error_response(message_en, message_ar, errors)

@frappe.whitelist(methods=["POST"])
def add_items(order_id, items):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	if not order.dish_plan_pricing:
		order.dish_plan_pricing = frappe.db.get_value("Dish Plan", order.dish_plan, "default_pricing_plan")
	pricing_plan = frappe.get_cached_doc("Dish Plan Pricing", order.dish_plan_pricing)

	pricing_plan_meals = {p.meal: p.per_day_price for p in pricing_plan.meals}

	order.items = []

	dish_plan = frappe.get_cached_doc("Dish Plan", order.dish_plan)
	meals = {}

	for m in dish_plan.meals:
		meals[m.meal] = m

	dates = []
	dates_data = {}
	for v in items:
		row = order.append("items")
		row.item_code = v["item_code"]
		row.meal = v.get("meal", "")
		row.delivery_date = getdate(v["delivery_date"])
		row.note = v.get("note", "")
		row.qty = int(v["qty"]) if v.get("qty") and int(v["qty"]) > 1 else 1
		row.extra_portion = 1 if v.get("extra_portion") and row.qty > 1 else 0

		if row.meal:
			row.rate = pricing_plan_meals.get(row.meal)

		if row.delivery_date not in dates:
			dates.append(row.delivery_date)

		if not row.meal:
			continue

		if row.delivery_date not in dates_data:
			dates_data[row.delivery_date] = {}

		if row.meal not in dates_data[row.delivery_date]:
			dates_data[row.delivery_date][row.meal] = 0

		dates_data[row.delivery_date][row.meal] += 1


	for d in order.delivery_dates:
		if not getdate(d.delivery_date) in dates:
			for m in order.meals:
				qty = meals[m.meal].min_qty
				if qty > 0:
					row = order.append("items")
					row.item_code = "Item Not Selected"
					row.meal = m.meal
					row.delivery_date = getdate(d.delivery_date)
					row.qty = qty
					row.rate = pricing_plan_meals.get(row.meal)

		else:
			dd = dates_data[d.delivery_date]

			for i,v in dd.items():
				for r in range(0, meals[i].max_qty - v):
					row = order.append("items")
					row.item_code = "Item Not Selected"
					row.meal = i
					row.delivery_date = getdate(d.delivery_date)
					row.qty = 1
					row.rate = pricing_plan_meals.get(i)

	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.flags.ignore_addresses = True
	order.save()
	frappe.db.commit()

	message_en = "Order updated successfully."
	message_ar = "تم تحديث الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


@frappe.whitelist(methods=["GET"])
def get_addresses():
	addresses = frappe.get_all("Address", filters=[["Dynamic Link", "link_doctype", "=", "User"], ["Dynamic Link", "link_name", "=", frappe.session.user]], fields=[])
	for d in addresses:
		d.doc = frappe.get_doc("Address", d.name)

	return send_success_response("", "", addresses)


@frappe.whitelist(methods=["POST"])
def update_address(address_id, data):
	doc = frappe.get_doc("Address", address_id)
	protected_keys = {"name", "doctype", "owner", "links"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}
	if "delivery_days" in clean_data:
		doc.delivery_days = []
	doc.update(clean_data)
	doc.flags.ignore_validate = True
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.update(clean_data)
	doc.address_line1 = "Zone {0}, Street No {1}, Building No {2}, Unit No {3}".format(doc.zone, doc.street_no, doc.building_no, doc.unit_no)
	doc.save()
	frappe.db.commit()
	message_en = "Address updated successfully."
	message_ar = "تم تحديث العنوان بنجاح."
	return send_success_response(message_en, message_ar, doc)

@frappe.whitelist(methods=["POST"])
def add_address(data):
	protected_keys = {"name", "doctype", "owner", "links"}
	clean_data = {k: v for k, v in data.items() if k not in protected_keys}
	doc = frappe.new_doc("Address")
	doc.update(clean_data)
	doc.links = []
	doc.append("links",{"link_doctype": "User", "link_name": frappe.session.user})
	doc.address_line1 = "Zone {0}, Street No {1}, Building No {2}, Unit No {3}".format(doc.zone, doc.street_no, doc.building_no, doc.unit_no)
	doc.flags.ignore_validate = True
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	frappe.db.commit()

	message_en = "Address created successfully."
	message_ar = "تم إنشاء العنوان بنجاح."

	return send_success_response(message_en, message_ar, doc)


@frappe.whitelist(methods=["POST"])
def remove_address(address_id):
	address = frappe.get_all("Address", filters=[["Dynamic Link", "link_doctype", "=", "User"], ["Dynamic Link", "link_name", "=", frappe.session.user], ["Address", "name", "=", address_id]], fields=[])
	if not address:
		message_en = "Address not found or does not belong to your account."
		message_ar = "العنوان غير موجود أو لا يخص حسابك."

		errors = {
			"access_denied": ["Address not found or does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	doc = frappe.get_doc("Address", address_id)
	doc.links = []
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	message_en = "Address removed successfully."
	message_ar = "تم حذف العنوان بنجاح."

	return send_success_response(message_en, message_ar, doc)


@frappe.whitelist(methods=["GET"])
def verify_addresses(order_id):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	data = validate_addresses(order, throw=False)
	if data["status"] == "success":
		order = data["data"]
		order.flags.ignore_permissions = True
		order.save()
		frappe.db.commit()

	return data

@frappe.whitelist(methods=["POST"])
def update_contact_information(order_id, data):
	order = validate_sales_order(order_id)
	if isinstance(order, dict):
		return order

	allowed_fields = {"first_name", "gender", "phone", "birth_date", "hear_about_us", "referred_by"}
	clean_data = {k: v for k, v in data.items() if k in allowed_fields}

	user = frappe.get_doc("User", frappe.session.user)
	user.flags.ignore_validate = True
	user.flags.ignore_permissions = True
	user.flags.ignore_mandatory = True
	user.update(clean_data)
	user.save()
	if "first_name" in clean_data:
		order.contact_person_name = clean_data["first_name"]

	if "phone" in clean_data:
		order.contact_phone = clean_data["phone"]

	if not order.contact_person_name:
		order.contact_person_name = user.full_name

	if not order.contact_phone:
		order.contact_phone = user.mobile_no

	order.flags.ignore_validate = True
	order.flags.ignore_permissions = True
	order.flags.ignore_mandatory = True
	order.save()
	frappe.db.commit()

	message_en = "Contact Information updated successfully."
	message_ar = "تم تحديث معلومات الاتصال بنجاح."

	return send_success_response(message_en, message_ar, {})

@frappe.whitelist(methods=["GET"])
def get_invoice_print(order_id, lang="en"):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	ss = frappe.get_cached_doc("SavvyEats Settings", "SavvyEats Settings", ignore_permmission=True)

	url = "/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={0}&format={1}&no_letterhead=1&letterhead=No%20Letterhead&settings=%7B%7D&_lang={2}".format(order.name, ss.invoice_print_format, lang)

	return send_success_response("", "", {"url": url})

@frappe.whitelist(methods=["POST"])
def submit_order(order_id):
	order = frappe.get_doc("Sales Order", order_id, ignore_permmission=True)
	if order.owner != frappe.session.user:
		message_en = "Access denied. This order does not belong to your account."
		message_ar = "تم رفض الوصول. هذا الطلب لا يخص حسابك."

		errors = {
			"access_denied": ["Access denied. This order does not belong to your account."]
		}
		return send_error_response(message_en, message_ar, errors)

	order.flags.ignore_permissions = True
	order.submit()
	frappe.db.commit()

	message_en = "Order Created Successfully."
	message_ar = "تم إنشاء الطلب بنجاح."

	return send_success_response(message_en, message_ar, order)


