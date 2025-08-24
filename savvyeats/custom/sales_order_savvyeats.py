import frappe
from frappe.utils import getdate, add_to_date, date_diff
from datetime import timedelta

WEEKDAY_MAP = {
	"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
	"Friday": 4, "Saturday": 5, "Sunday": 6
}

def validate(self, method):
	sales_order_delivery(self)

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

