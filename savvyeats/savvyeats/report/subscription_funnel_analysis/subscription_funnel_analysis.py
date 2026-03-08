import frappe
from frappe import _


FUNNEL_STEPS = [
	(1,  "Started",               "Dropped at Step 1 – Plan Selection"),
	(2,  "Plan Selection",        "Dropped at Step 2 – Plan Selection"),
	(3,  "Phase Selection",       "Dropped at Step 3 – Phase Selection"),
	(4,  "Delivery Days",         "Dropped at Step 4 – Delivery Days"),
	(5,  "Package Selection",     "Dropped at Step 5 – Package Selection"),
	(6,  "Starting Day",          "Dropped at Step 6 – Starting Day"),
	(7,  "Allergen Selection",    "Dropped at Step 7 – Allergen Selection"),
	(8,  "Dish Selection",        "Dropped at Step 8 – Dish Selection"),
	(9,  "Contact Information",   "Dropped at Step 9 – Contact Information"),
	(10, "Address Information",   "Dropped at Step 10 – Address Information"),
	(11, "Payment & Submission",  "Completed – Payment & Submission"),
]

STEP_LABEL_MAP = {s: lbl for s, lbl, _ in FUNNEL_STEPS}
STEP_DROPOFF_MAP = {s: d for s, _, d in FUNNEL_STEPS}


def execute(filters=None):
	filters = filters or {}
	columns = get_columns(filters)
	data    = get_data(filters)
	chart   = get_chart(data, filters)
	summary = get_summary(data, filters)
	return columns, data, None, chart, summary


def get_columns(filters):
	show_details = frappe.utils.cint(filters.get("show_details"))

	if show_details:
		return [
			{
				"fieldname": "name",
				"label": _("Subscription"),
				"fieldtype": "Link",
				"options": "Sales Order",
				"width": 160,
			},
			{
				"fieldname": "customer",
				"label": _("Customer"),
				"fieldtype": "Link",
				"options": "Customer",
				"width": 160,
			},
			{
				"fieldname": "creation",
				"label": _("Started On"),
				"fieldtype": "Datetime",
				"width": 160,
			},
			{
				"fieldname": "dish_plan",
				"label": _("Plan"),
				"fieldtype": "Link",
				"options": "Dish Plan",
				"width": 130,
			},
			{
				"fieldname": "subscription_status",
				"label": _("Subscription Status"),
				"fieldtype": "Data",
				"width": 150,
			},
			{
				"fieldname": "last_step_no",
				"label": _("Last Step No."),
				"fieldtype": "Int",
				"width": 110,
			},
			{
				"fieldname": "last_step_label",
				"label": _("Last Completed Step"),
				"fieldtype": "Data",
				"width": 220,
			},
			{
				"fieldname": "drop_off_stage",
				"label": _("Drop-off Stage"),
				"fieldtype": "Data",
				"width": 270,
			},
			{
				"fieldname": "docstatus",
				"label": _("Doc Status"),
				"fieldtype": "Int",
				"width": 90,
			},
		]

	return [
		{
			"fieldname": "step_no",
			"label": _("Step No."),
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"fieldname": "step_name",
			"label": _("Step / Stage"),
			"fieldtype": "Data",
			"width": 230,
		},
		{
			"fieldname": "entered",
			"label": _("Customers Reached"),
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"fieldname": "completed",
			"label": _("Customers Completed"),
			"fieldtype": "Int",
			"width": 180,
		},
		{
			"fieldname": "dropped",
			"label": _("Customers Dropped"),
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"fieldname": "drop_rate",
			"label": _("Drop Rate (%)"),
			"fieldtype": "Percent",
			"width": 130,
		},
		{
			"fieldname": "conversion_rate",
			"label": _("Step Conversion (%)"),
			"fieldtype": "Percent",
			"width": 160,
		},
		{
			"fieldname": "cumulative_conv",
			"label": _("Cumulative Conversion (%)"),
			"fieldtype": "Percent",
			"width": 190,
		},
	]


def get_data(filters):
	rows = fetch_subscriptions(filters)

	if not rows:
		return []

	for row in rows:
		row["last_step_no"], row["last_step_label"] = get_last_step(row)
		if row["last_step_no"] == 11:
			row["drop_off_stage"] = "Completed – Payment & Submission"
		else:
			next_step = row["last_step_no"] + 1
			row["drop_off_stage"] = STEP_DROPOFF_MAP.get(next_step, "Unknown")

	show_details = frappe.utils.cint(filters.get("show_details"))
	if show_details:
		return rows

	return build_funnel_summary(rows)


def fetch_subscriptions(filters):
	conditions, values = build_conditions(filters)

	sql = """
		SELECT
			so.name,
			so.customer,
			so.creation,
			so.dish_plan,
			so.dish_plan_pricing,
			so.period_type,
			so.period_count,
			so.delivery_days,
			so.start_date,
			so.delivery_time_slot,
			so.contact_person_name,
			so.customer_address,
			so.subscription_status,
			so.docstatus,
			so.owner,

			COALESCE((
				SELECT COUNT(*)
				FROM `tabSales Order Item`
				WHERE parent = so.name
			), 0) AS item_count,

			COALESCE((
				SELECT COUNT(*)
				FROM `tabSales Order Delivery Days`
				WHERE parent = so.name
			), 0) AS delivery_dates_count,

			COALESCE((
				SELECT COUNT(*)
				FROM `tabSales Order Meals`
				WHERE parent = so.name
			), 0) AS meals_count,

			COALESCE((
				SELECT COUNT(*)
				FROM `tabSales Order Allergens`
				WHERE parent = so.name
			), 0) AS allergens_count,

			COALESCE((
				SELECT COUNT(*)
				FROM `tabSales Order Addresses`
				WHERE parent = so.name
			), 0) AS addresses_count

		FROM `tabSales Order` so
		WHERE
			1=1
			{conditions}
		ORDER BY so.creation DESC
	""".format(conditions=conditions)

	return frappe.db.sql(sql, values, as_dict=True)


def build_conditions(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("AND DATE(so.creation) >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("AND DATE(so.creation) <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("dish_plan"):
		conditions.append("AND so.dish_plan = %(dish_plan)s")
		values["dish_plan"] = filters["dish_plan"]

	if filters.get("customer"):
		conditions.append("AND so.customer = %(customer)s")
		values["customer"] = filters["customer"]

	if filters.get("subscription_status"):
		conditions.append("AND so.subscription_status = %(subscription_status)s")
		values["subscription_status"] = filters["subscription_status"]

	return " ".join(conditions), values


def get_last_step(row):
	step_checks = [
		(1,  True),
		(2,  bool(row.get("dish_plan") and row.get("dish_plan_pricing"))),
		(3,  bool(row.get("period_type") and row.get("period_count"))),
		(4,  bool(row.get("delivery_days") and int(row.get("delivery_days") or 0) > 0)),
		(5,  bool(int(row.get("meals_count") or 0) > 0)),
		(6,  bool(row.get("start_date") and row.get("delivery_time_slot"))),
		(7,  bool(
			int(row.get("allergens_count") or 0) > 0
			or int(row.get("item_count") or 0) > 0
		)),
		(8,  bool(int(row.get("item_count") or 0) > 0)),
		(9,  bool(row.get("contact_person_name"))),
		(10, bool(int(row.get("addresses_count") or 0) > 0)),
		(11, bool(int(row.get("docstatus") or 0) == 1)),
	]

	last_step = 0
	for step_no, condition in step_checks:
		if condition:
			last_step = step_no
		else:
			break

	return last_step, STEP_LABEL_MAP.get(last_step, "Started")


def build_funnel_summary(rows):
	total = len(rows)
	if not total:
		return []

	step_entered = {}
	step_completed = {}

	for step_no, _label, _drop in FUNNEL_STEPS:
		entered   = sum(1 for r in rows if r["last_step_no"] >= step_no)
		completed = sum(1 for r in rows if r["last_step_no"] > step_no
		                or (step_no == 11 and r["last_step_no"] == 11))
		step_entered[step_no]   = entered
		step_completed[step_no] = completed

	summary_rows = []
	for step_no, step_name, _drop in FUNNEL_STEPS:
		entered   = step_entered[step_no]
		completed = step_completed[step_no]
		dropped   = entered - completed

		if entered > 0:
			drop_rate       = round(dropped   / entered * 100, 2)
			conv_step       = round(completed / entered * 100, 2)
		else:
			drop_rate = conv_step = 0.0

		cumulative_conv = round(completed / total * 100, 2) if total else 0.0

		summary_rows.append({
			"step_no":         step_no,
			"step_name":       "Step {} – {}".format(step_no, step_name),
			"entered":         entered,
			"completed":       completed,
			"dropped":         dropped,
			"drop_rate":       drop_rate,
			"conversion_rate": conv_step,
			"cumulative_conv": cumulative_conv,
		})

	return summary_rows


def get_chart(data, filters):
	show_details = frappe.utils.cint(filters.get("show_details"))

	if show_details or not data:
		return None

	labels   = [r["step_name"] for r in data]
	entered  = [r["entered"]   for r in data]
	dropped  = [r["dropped"]   for r in data]
	completed = [r["completed"] for r in data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Customers Reached"),   "values": entered},
				{"name": _("Customers Completed"), "values": completed},
				{"name": _("Customers Dropped"),   "values": dropped},
			],
		},
		"type":   "bar",
		"colors": ["#5e64ff", "#2ecc71", "#e74c3c"],
		"barOptions": {"stacked": 0},
		"height": 360,
		"axisOptions": {
			"xAxisMode": "tick",
			"yAxisMode": "span",
		},
		"title": _("Subscription Funnel – Drop-off Analysis"),
	}


def get_summary(data, filters):
	show_details = frappe.utils.cint(filters.get("show_details"))

	if show_details:
		total = len(data)
		completed_count = sum(1 for r in data if r.get("last_step_no") == 11)
		return [
			{
				"value": total,
				"label": _("Total Subscriptions Analysed"),
				"datatype": "Int",
				"indicator": "Blue",
			},
			{
				"value": completed_count,
				"label": _("Fully Submitted"),
				"datatype": "Int",
				"indicator": "Green",
			},
			{
				"value": total - completed_count,
				"label": _("Incomplete / Dropped"),
				"datatype": "Int",
				"indicator": "Red",
			},
			{
				"value": (
					round(completed_count / total * 100, 1) if total else 0.0
				),
				"label": _("Overall Completion Rate (%)"),
				"datatype": "Percent",
				"indicator": "Blue",
			},
		]

	if not data:
		return []

	total_entered  = data[0]["entered"]   if data else 0
	total_complete = data[-1]["completed"] if data else 0
	eligible = [r for r in data if r["entered"] > 0 and r["dropped"] > 0]
	highest_drop_row = max(eligible, key=lambda r: r["drop_rate"]) if eligible else {}

	return [
		{
			"value": total_entered,
			"label": _("Total Started Subscription"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": total_complete,
			"label": _("Fully Completed & Submitted"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"value": (
				round(total_complete / total_entered * 100, 1)
				if total_entered else 0.0
			),
			"label": _("Overall Completion Rate (%)"),
			"datatype": "Percent",
			"indicator": "Blue",
		},
		{
			"value": highest_drop_row.get("step_name", "N/A"),
			"label": _("Biggest Drop-off Step"),
			"datatype": "Data",
			"indicator": "Red",
		},
	]
