"""Subscription Report: subscribers per month, renewals, and an order export.

A subscription is a submitted Sales Order (docstatus 1); drafts and cancelled
documents never count. Its service period runs from actual_start_date to
actual_end_date (the first and last delivery), falling back to start_date /
end_date for orders that have none.

Plans are grouped by what the customer sees: Dish Plan.display_plan_name, so a
Ramadan variant counts with its regular plan, and every "My Way" plan under MY WAY.

Renewals: the app rarely links a renewal to the order it renews (renewal_of only
exists since pre-renewal), so customers renew by placing a new order. A
subscription counts as renewed when an order has renewal_of pointing at it, or
the same customer's next subscription starts no later than `renewal_window` days
after it ends. Starting before it ends (a renewal bought early) counts too.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, get_last_day, getdate, strip_html, today

from savvyeats.api.utils import MY_WAY_UI_TYPE

MY_WAY_LABEL = "MY WAY"
DEFAULT_FROM_DATE = "2025-11-01"
DEFAULT_RENEWAL_WINDOW = 7


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.from_date = getdate(filters.get("from_date") or DEFAULT_FROM_DATE)
	filters.to_date = getdate(filters.get("to_date") or today())
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date."))
	filters.renewal_window = max(cint(filters.get("renewal_window") or DEFAULT_RENEWAL_WINDOW), 0)

	plans = get_plan_groups_map()
	subscriptions = get_subscriptions(filters, plans)

	view = filters.get("view") or "Subscribers"
	if view == "Renewals":
		return renewals_view(filters, subscriptions)
	if view == "Orders":
		return orders_view(filters, subscriptions)
	return subscribers_view(filters, subscriptions, plans)


# --- shared ------------------------------------------------------------------


def get_plan_groups_map():
	"""{dish_plan: (group label, sort key)} for every Dish Plan."""
	plans = {}
	for p in frappe.get_all(
		"Dish Plan", fields=["name", "plan_name", "display_plan_name", "ui_type", "sorting_order", "enabled"]
	):
		if p.ui_type == MY_WAY_UI_TYPE:
			label = MY_WAY_LABEL
		else:
			label = (p.display_plan_name or p.plan_name or p.name).strip()
		plans[p.name] = frappe._dict(label=label, sort=cint(p.sorting_order), enabled=cint(p.enabled))
	return plans


@frappe.whitelist()
def get_plan_groups():
	"""Plan filter options, in the plans' sorting order."""
	frappe.has_permission("Sales Order", "read", throw=True)
	return _ordered_groups(get_plan_groups_map(), enabled_only=True)


def _ordered_groups(plans, enabled_only=False, extra=()):
	order = {}
	for p in plans.values():
		if enabled_only and not p.enabled:
			continue
		order[p.label] = min(order.get(p.label, p.sort), p.sort)
	for label in extra:
		order.setdefault(label, 10**6)
	return sorted(order, key=lambda label: (order[label], label))


def get_subscriptions(filters, plans):
	"""Every subscription, whatever its dates: renewals look past the date range."""
	rows = frappe.db.sql(
		"""
		SELECT name, customer, customer_name, transaction_date, dish_plan, period_type,
			period_count, delivery_days, total_days, subscription_status, renewal_of,
			COALESCE(actual_start_date, start_date) AS start,
			COALESCE(actual_end_date, end_date) AS end,
			DATE(modified) AS modified_on, currency, net_total, discount_amount,
			grand_total, rounded_total
		FROM `tabSales Order`
		WHERE docstatus = 1
		ORDER BY COALESCE(actual_start_date, start_date), transaction_date, name
		""",
		as_dict=True,
	)

	# Zero-value orders are mostly tests, so they are left out unless asked for. An
	# opt-in flag because the report page drops unchecked (falsy) filters entirely.
	include_zero = cint(filters.get("include_zero_value"))
	result = []
	for r in rows:
		r.value = flt(r.rounded_total) or flt(r.grand_total)
		if not include_zero and not r.value:
			continue
		plan = plans.get(r.dish_plan)
		r.plan = plan.label if plan else (r.dish_plan or _("No Plan"))
		r.start = getdate(r.start) if r.start else None
		r.end = getdate(r.end) if r.end else None
		# A Cancelled subscription stops being served when it was cancelled, which is
		# the last time it changed.
		r.stop = r.end
		if r.subscription_status == "Cancelled" and r.modified_on:
			r.stop = min(r.end, getdate(r.modified_on)) if r.end else getdate(r.modified_on)
		result.append(r)
	return result


def plan_matches(filters, row_plan):
	return not filters.get("plan") or row_plan == filters.plan


def duration_label(row):
	count = cint(row.period_count)
	if not row.period_type or not count:
		return ""
	unit = {"Week": (_("Week"), _("Weeks")), "Month": (_("Month"), _("Months"))}.get(
		row.period_type, (row.period_type, row.period_type)
	)
	return "{0} {1}".format(count, unit[0] if count == 1 else unit[1])


def month_starts(from_date, to_date):
	current = from_date.replace(day=1)
	while current <= to_date:
		yield current
		current = add_days(get_last_day(current), 1)


# --- 1. subscribers ----------------------------------------------------------


def subscribers_view(filters, subscriptions, plans):
	today_date = getdate(today())
	first_start = {}
	for s in subscriptions:
		if s.start and (s.customer not in first_start or s.start < first_start[s.customer]):
			first_start[s.customer] = s.start

	groups = _ordered_groups(plans, enabled_only=True, extra={s.plan for s in subscriptions})
	if filters.get("plan"):
		groups = [g for g in groups if g == filters.plan]
	# Prefixed so a plan named e.g. "Total" cannot overwrite a fixed column.
	keys = {g: "plan_{0}_{1}".format(i, frappe.scrub(g)) for i, g in enumerate(groups)}

	data = []
	for month_start in month_starts(filters.from_date, filters.to_date):
		if month_start > today_date:
			break
		# The current month only counts who has been active so far.
		month_end = min(get_last_day(month_start), today_date)

		active = {g: set() for g in groups}
		everyone = set()
		new = set()
		for s in subscriptions:
			if not (s.start and s.stop) or s.plan not in active:
				continue
			if s.start <= month_end and s.stop >= month_start:
				active[s.plan].add(s.customer)
				everyone.add(s.customer)
				if month_start <= first_start[s.customer] <= month_end:
					new.add(s.customer)

		row = {"month": month_start.strftime("%b %Y")}
		for g in groups:
			row[keys[g]] = len(active[g])
		row["total"] = len(everyone)
		row["new"] = len(new)
		row["returning"] = len(everyone) - len(new)
		data.append(row)

	columns = [{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 110}]
	columns += [{"fieldname": keys[g], "label": g, "fieldtype": "Int", "width": 110} for g in groups]
	columns += [
		{"fieldname": "total", "label": _("Total Active"), "fieldtype": "Int", "width": 120},
		{"fieldname": "new", "label": _("New"), "fieldtype": "Int", "width": 90},
		{"fieldname": "returning", "label": _("Continuing / Returning"), "fieldtype": "Int", "width": 170},
	]

	chart = {
		"data": {
			"labels": [r["month"] for r in data],
			"datasets": [{"name": g, "values": [r[keys[g]] for r in data]} for g in groups],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
	}

	summary = []
	if data:
		latest = data[-1]
		peak = max(data, key=lambda r: r["total"])
		summary = [
			{"label": _("Active in {0}").format(latest["month"]), "value": latest["total"], "datatype": "Int", "indicator": "Blue"},
			{"label": _("Peak ({0})").format(peak["month"]), "value": peak["total"], "datatype": "Int", "indicator": "Green"},
			{"label": _("New Subscribers in Period"), "value": sum(r["new"] for r in data), "datatype": "Int", "indicator": "Orange"},
		]

	message = _(
		"A subscriber is a customer with at least one paid subscription delivering in the month. "
		"Someone on two plans in a month counts under both plans but once in Total Active."
	)
	return columns, data, message, chart, summary


# --- 2. renewals -------------------------------------------------------------


def renewals_view(filters, subscriptions):
	today_date = getdate(today())
	window = filters.renewal_window

	by_customer = {}
	renewed_by_link = {}
	for s in subscriptions:
		by_customer.setdefault(s.customer, []).append(s)
		if s.renewal_of:
			renewed_by_link.setdefault(s.renewal_of, s)

	ended = [
		s
		for s in subscriptions
		if s.stop
		and filters.from_date <= s.stop <= filters.to_date
		and s.stop < today_date
		and plan_matches(filters, s.plan)
	]
	notes = get_latest_comments([s.name for s in ended])

	data = []
	for s in ended:
		nxt = renewed_by_link.get(s.name)
		if not nxt and s.start:
			deadline = add_days(s.stop, window)
			candidates = [
				t
				for t in by_customer[s.customer]
				if t.name != s.name and t.start and s.start < t.start <= deadline
			]
			nxt = candidates[0] if candidates else None

		if nxt:
			outcome = _("Renewed")
		elif add_days(s.stop, window) >= today_date:
			outcome = _("Awaiting")
		else:
			outcome = _("Stopped")

		data.append({
			"subscription": s.name,
			"customer": s.customer,
			"customer_name": s.customer_name,
			"plan": s.plan,
			"duration": duration_label(s),
			"start_date": s.start,
			"end_date": s.stop,
			"status": s.subscription_status,
			"outcome": outcome,
			"next_subscription": nxt.name if nxt else None,
			"next_plan": nxt.plan if nxt else None,
			"next_start_date": nxt.start if nxt else None,
			# 0 = the next one started the day after; negative = bought before the end.
			"gap_days": (date_diff(nxt.start, s.stop) - 1) if nxt and nxt.start else None,
			"notes": notes.get(s.name),
		})

	columns = [
		{"fieldname": "subscription", "label": _("Subscription"), "fieldtype": "Link", "options": "Sales Order", "width": 160},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 140},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "plan", "label": _("Plan"), "fieldtype": "Data", "width": 110},
		{"fieldname": "duration", "label": _("Duration"), "fieldtype": "Data", "width": 90},
		{"fieldname": "start_date", "label": _("Start"), "fieldtype": "Date", "width": 100},
		{"fieldname": "end_date", "label": _("End"), "fieldtype": "Date", "width": 100},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
		{"fieldname": "outcome", "label": _("Outcome"), "fieldtype": "Data", "width": 100},
		{"fieldname": "next_subscription", "label": _("Next Subscription"), "fieldtype": "Link", "options": "Sales Order", "width": 160},
		{"fieldname": "next_plan", "label": _("Next Plan"), "fieldtype": "Data", "width": 110},
		{"fieldname": "next_start_date", "label": _("Next Start"), "fieldtype": "Date", "width": 100},
		{"fieldname": "gap_days", "label": _("Gap (Days)"), "fieldtype": "Int", "width": 90},
		{"fieldname": "notes", "label": _("Reason / Notes"), "fieldtype": "Data", "width": 260},
	]

	counts = {o: [r for r in data if r["outcome"] == o] for o in (_("Renewed"), _("Stopped"), _("Awaiting"))}
	renewed, stopped, awaiting = (counts[_("Renewed")], counts[_("Stopped")], counts[_("Awaiting")])
	decided = len(renewed) + len(stopped)
	# A customer lost is one whose last subscription ending in the period stopped; one
	# who stopped once and came back later is not lost.
	last_by_customer = {}
	for r in data:
		if r["customer"] not in last_by_customer or r["end_date"] >= last_by_customer[r["customer"]]["end_date"]:
			last_by_customer[r["customer"]] = r
	lost = sum(1 for r in last_by_customer.values() if r["outcome"] == _("Stopped"))
	renewed_customers = len({r["customer"] for r in renewed})

	summary = [
		{"label": _("Subscriptions Ended"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Renewed"), "value": len(renewed), "datatype": "Int", "indicator": "Green"},
		{"label": _("Stopped"), "value": len(stopped), "datatype": "Int", "indicator": "Red"},
		{"label": _("Awaiting (within {0} days)").format(window), "value": len(awaiting), "datatype": "Int", "indicator": "Orange"},
		{
			"label": _("Renewal Rate"),
			"value": "{0:.1f}%".format(100.0 * len(renewed) / decided) if decided else "—",
			"datatype": "Data",
			"indicator": "Green",
		},
		{"label": _("Customers Who Renewed"), "value": renewed_customers, "datatype": "Int", "indicator": "Green"},
		{"label": _("Customers Lost"), "value": lost, "datatype": "Int", "indicator": "Red"},
	]

	chart = {
		"data": {
			"labels": [_("Renewed"), _("Stopped"), _("Awaiting")],
			"datasets": [{"name": _("Subscriptions"), "values": [len(renewed), len(stopped), len(awaiting)]}],
		},
		"type": "donut",
		"colors": ["#29CD42", "#E24C4C", "#ECAD4B"],
	}

	message = _(
		"Subscriptions that ended between the dates. Renewed: the customer's next subscription started "
		"within {0} days of the end (or was linked as its renewal). Stopped: nothing followed within that "
		"window. Awaiting: the window is still open. The app does not ask why a customer stops; "
		"Reason / Notes shows the latest comment added on the subscription."
	).format(window)
	return columns, data, message, chart, summary


def get_latest_comments(names):
	if not names:
		return {}
	notes = {}
	for c in frappe.get_all(
		"Comment",
		filters={"reference_doctype": "Sales Order", "reference_name": ["in", names], "comment_type": "Comment"},
		fields=["reference_name", "content"],
		order_by="creation desc",
	):
		notes.setdefault(c.reference_name, strip_html(c.content or "").strip())
	return notes


# --- 3. orders ---------------------------------------------------------------


def orders_view(filters, subscriptions):
	first_order = {}
	for s in sorted(subscriptions, key=lambda s: (s.transaction_date, s.name)):
		first_order.setdefault(s.customer, s.name)

	data = []
	for s in subscriptions:
		if not (s.transaction_date and filters.from_date <= getdate(s.transaction_date) <= filters.to_date):
			continue
		if not plan_matches(filters, s.plan):
			continue
		data.append({
			"order": s.name,
			"order_date": s.transaction_date,
			"customer": s.customer,
			"customer_name": s.customer_name,
			"plan": s.plan,
			"dish_plan": s.dish_plan,
			"duration": duration_label(s),
			"start_date": s.start,
			"end_date": s.end,
			"deliveries": cint(s.delivery_days),
			"status": s.subscription_status,
			"order_type": _("New") if first_order.get(s.customer) == s.name else _("Repeat"),
			"net_total": flt(s.net_total),
			"discount_amount": flt(s.discount_amount),
			"value": s.value,
			"currency": s.currency,
		})
	data.sort(key=lambda r: (r["order_date"], r["order"]))

	columns = [
		{"fieldname": "order", "label": _("Order"), "fieldtype": "Link", "options": "Sales Order", "width": 160},
		{"fieldname": "order_date", "label": _("Order Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 140},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "plan", "label": _("Plan"), "fieldtype": "Data", "width": 110},
		{"fieldname": "dish_plan", "label": _("Dish Plan"), "fieldtype": "Link", "options": "Dish Plan", "width": 140},
		{"fieldname": "duration", "label": _("Duration"), "fieldtype": "Data", "width": 90},
		{"fieldname": "start_date", "label": _("Start"), "fieldtype": "Date", "width": 100},
		{"fieldname": "end_date", "label": _("End"), "fieldtype": "Date", "width": 100},
		{"fieldname": "deliveries", "label": _("Deliveries"), "fieldtype": "Int", "width": 90},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
		{"fieldname": "order_type", "label": _("New / Repeat"), "fieldtype": "Data", "width": 100},
		{"fieldname": "net_total", "label": _("Net Total"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "discount_amount", "label": _("Discount"), "fieldtype": "Currency", "options": "currency", "width": 100},
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]

	total = sum(r["value"] for r in data)
	currency = data[0]["currency"] if data else None
	summary = [
		{"label": _("Orders"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Total Value"), "value": total, "datatype": "Currency", "currency": currency, "indicator": "Green"},
		{
			"label": _("Average Order Value"),
			"value": total / len(data) if data else 0,
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Orange",
		},
		{"label": _("New Customers"), "value": sum(1 for r in data if r["order_type"] == _("New")), "datatype": "Int", "indicator": "Purple"},
	]
	message = _("Paid subscriptions ordered between the dates. Value is the grand total after discounts and taxes.")
	return columns, data, message, None, summary
