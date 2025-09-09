import frappe
from frappe.utils import getdate, add_to_date, date_diff, nowdate
from datetime import timedelta
from frappe import _
from savvyeats.api.user import send_error_response, send_success_response
import json

WEEKDAY_MAP = {
	"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
	"Friday": 4, "Saturday": 5, "Sunday": 6
}

def validate(self, method):
	sales_order_delivery(self)

def before_submit(self, method):
	validate_addresses(self)

@frappe.whitelist()
def update_owner(sales_order, owner):
	frappe.db.set_value("Sales Order",sales_order, "owner", owner, update_modified=False)

def sales_order_delivery(self):
	if self.period_type and self.period_count and self.start_date:
		if self.period_type.lower() == "week":
			self.end_date = add_to_date(self.start_date, weeks=self.period_count)
		elif self.period_type.lower() == "month":
			self.end_date = add_to_date(self.start_date, months=self.period_count)

		self.end_date = add_to_date(self.end_date, days=-1)
		self.total_days = date_diff(self.end_date, self.start_date) + 1

	if self.start_date and self.end_date and self.week_plan:
		week_plan = frappe.get_doc("Week Plan", self.week_plan)
		days = [d.day for d in week_plan.days]
		dates, self.delivery_days = delivery_schedule(self.start_date, self.end_date, days, inclusive=True)
		self.delivery_dates = []
		for d in dates:
			self.append("delivery_dates", {"delivery_date": d, "day": d.strftime("%A"), "status": "Pending"})
	
	if self.pause_start_date and self.pause_end_date:
		pass


def validate_addresses(self, throw=True):
	if not self.addresses:
		if throw:
			frappe.throw(_("Addresses are mandatory to Proceed"))
		else:
			message_en = "Addresses are mandatory to proceed."
			message_ar = "العناوين إلزامية للمتابعة."

			errors = {
				"error": ["Addresses are mandatory to proceed."]
			}
			return send_error_response(message_en, message_ar, errors)

	days = {"Monday": None, "Tuesday": None, "Wednesday": None, "Thursday": None, "Friday": None, "Saturday": None, "Sunday": None}

	for d in self.addresses:
		address = frappe.get_doc("Address", d.address, ignore_permmission=True)
		for day in address.delivery_days:
			if days[day.day]:
				error = _("Day <b>{0}</b> Already in Address <b>{1}</b>".format(day, days[day.day]))
				if throw:
					frappe.throw(error)
				else:
					message_en = "Duplicate day detected across addresses."
					message_ar = "تم اكتشاف يوم مكرر بين العناوين."

					errors = {
						"error": ["Duplicate day detected across addresses."]
					}
					return send_error_response(message_en, message_ar, errors)

			days[day.day] = address.name

	for d in self.delivery_dates:
		if not days[d.day]:
			error = _("No Address Found for Day <b>{0}</b>".format(d.day))
			if throw:
				frappe.throw(error)
			else:
				message_en = "Select an address for all days before proceeding."
				message_ar = "حدد عنوانًا لجميع الأيام قبل المتابعة."

				errors = {
					"error": ["Select an address for all days before proceeding."]
				}
				return send_error_response(message_en, message_ar, errors)
		d.address = days[d.day]

	if throw:
		return self

	return send_success_response("", "", self)


def delivery_schedule(start_date, end_date, planned_days, inclusive=True):
	if not (start_date and end_date and planned_days):
		return [], 0

	start_date = getdate(start_date)
	end_date = getdate(end_date)

	if end_date < start_date:
		return [], 0

	allowed = {WEEKDAY_MAP[d] for d in planned_days if d in WEEKDAY_MAP}
	if not allowed:
		return [], 0

	last = end_date if inclusive else end_date - timedelta(days=1)
	cur = start_date
	dates = []
	while cur <= last:
		if cur.weekday() in allowed:
			dates.append(cur)
		cur += timedelta(days=1)
	return dates, len(dates)


@frappe.whitelist()
def get_delivery_dates(doc):
	if isinstance(doc, str):
		doc = json.loads(doc)
	if doc:
		doc = frappe.get_doc(doc)
	sales_order_delivery(doc)
	return doc


def add_items_to_order(doc):
	if isinstance(doc, str):
		doc = json.loads(doc)
	if doc:
		doc = frappe.get_doc(doc)

	pricing = frappe.get_doc("Dish Plan Pricing", doc.dish_plan_pricing)
	


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	return frappe.db.sql("""
		SELECT 
			t1.item_code, 
			t1.item_name, 
			t1.meal, 
		CASE 
			WHEN t1.default = 1 THEN 'Default' 
			ELSE ''
			END AS default_label
		FROM `tabDish Schedule Items` AS t1
		INNER JOIN `tabDish Schedule` AS t2
			ON t1.parent = t2.name
		WHERE t2.status = 'Published'
			AND t1.meal = %(meal)s
			AND t2.date = %(date)s
			AND t1.dish_plan = %(dish_plan)s
		ORDER BY
			IF(LOCATE(%(_txt)s, t1.item_code), LOCATE(%(_txt)s, t1.item_code), 99999),
			IF(LOCATE(%(_txt)s, t1.item_name), LOCATE(%(_txt)s, t1.item_name), 99999),
			t1.default DESC
	""", {
		"meal": filters["meal"],
		"date": filters["available_on"],
		"dish_plan": filters["dish_plan"],
		"txt": "%%%s%%" % txt,
		"_txt": txt.replace("%", ""),
	},
	as_dict=as_dict)



