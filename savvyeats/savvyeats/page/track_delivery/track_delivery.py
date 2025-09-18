import frappe
from frappe import _
from datetime import datetime

def _trip_payload(t):
	"""internal helper: pack one Delivery Trip with stops + locations"""
	# resolve start lat/lng from Address safely
	start_lat, start_lng = None, None
	if getattr(t, "driver_address", None):
		try:
			addr = frappe.get_doc("Address", t.driver_address)
			start_lat = addr.latitude
			start_lng = addr.longitude
		except Exception:
			pass

	# stops (Delivery Stop) — note: distance stored in METERS in your schema
	stops = frappe.get_all(
		"Delivery Stop",
		filters={"parent": t.name, "parenttype": "Delivery Trip"},
		fields=[
			"name", "idx", "customer", "address",
			"latitude", "longitude", "delivery_note",
			"visited", "locked", "estimated_arrival", "distance"   # distance (meters)
		],
		order_by="idx asc"
	)

	delivered = sum(1 for s in stops if int(s.visited or 0) == 1)
	in_proc   = sum(1 for s in stops if int(s.visited or 0) == 0 and int(s.locked or 0) == 1)
	pending   = sum(1 for s in stops if int(s.visited or 0) == 0 and int(s.locked or 0) == 0)

	# full route points (chronological)
	locs = frappe.get_all(
		"Driver Location",
		filters={"delivery_trip": t.name},
		fields=["latitude", "longitude", "timestamp"],
		order_by="timestamp asc",
		limit_page_length=5000
	)

	for d in stops:
		d.customer_name = frappe.db.get_value("Customer", d.customer, "customer_name")

	# attach resolved start coords for the UI map
	t.start_latitude  = start_lat
	t.start_longitude = start_lng

	return {
		"trip": t,
		"counts": {"delivered": delivered, "in_process": in_proc, "pending": pending},
		"stops": stops,
		"locations": locs
	}


@frappe.whitelist()
def get_delivery_tracking(date_str: str):
	"""List all trips for a day (summary for left list) + full payloads for quick load."""
	if not date_str:
		frappe.throw(_("Please select a date"))

	date = frappe.utils.getdate(date_str)
	start = datetime.combine(date, datetime.min.time())
	end   = datetime.combine(date, datetime.max.time())

	trips = frappe.get_all(
		"Delivery Trip",
		filters={"departure_time": ["between", [start, end]], "docstatus": ["!=", 2]},
		fields=["name", "driver", "driver_name", "delivery_time_slot", "departure_time",
				"total_distance", "driver_address"],
		order_by="departure_time asc"
	)

	data = []
	for tinfo in trips:
		# make a doc-like object for uniform access
		t = frappe._dict(tinfo)
		data.append(_trip_payload(t))

	return {"trips": data}


@frappe.whitelist()
def get_single_trip(trip_name: str):
	"""Refresh only one trip (for the ‘Refresh Trip’ button)."""
	if not trip_name:
		frappe.throw(_("Trip name is required"))
	tdoc = frappe.get_doc("Delivery Trip", trip_name)
	# only pull fields we need into a dict-like (to match above)
	t = frappe._dict({
		"name": tdoc.name,
		"driver": tdoc.driver,
		"driver_name": tdoc.driver_name,
		"delivery_time_slot": tdoc.delivery_time_slot,
		"departure_time": tdoc.departure_time,
		"total_distance": tdoc.total_distance,   # meters
		"driver_address": tdoc.driver_address
	})
	return _trip_payload(t)

@frappe.whitelist()
def get_trip_locations_since(trip_name: str, since_ts: str | None = None):
	"""
	Return only NEW Driver Location points for this trip since `since_ts` (ISO or Frappe datetime).
	If `since_ts` is empty, returns the full series (limited).
	Responds with: {"locations": [...], "last_ts": "..."}
	"""
	if not trip_name:
		frappe.throw("trip_name is required")

	filters = {"delivery_trip": trip_name}
	if since_ts:
		try:
			since = get_datetime(since_ts)
			filters["timestamp"] = [">", since]
		except Exception:
			pass

	locs = frappe.get_all(
		"Driver Location",
		filters=filters,
		fields=["latitude", "longitude", "timestamp"],
		order_by="timestamp asc",
		limit_page_length=5000
	)

	last_ts = None
	if locs:
		last_ts = locs[-1]["timestamp"]

	return {"locations": locs, "last_ts": last_ts}
