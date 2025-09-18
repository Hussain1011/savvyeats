# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime, format_datetime
import math
try:
	import googlemaps
except Exception:
	googlemaps = None

class DeliverySchedule(Document):
	def validate(self):
		self.validate_delivery_date()
		self.validate_drivers()
		self.status = "Pending"
		self.title = getdate(self.delivery_date).strftime("%A, %B %d, %Y")

	def validate_delivery_date(self):
		exists = frappe.get_all("Delivery Schedule", filters={"delivery_date": self.delivery_date, "name": ["!=", self.name], "docstatus": ["!=", 2]})
		if exists:
			frappe.throw(_("Delivery Schedule already exists for Date: <b>{0}</b>".format(self.get_formatted("delivery_date"))))


	def validate_subscription_delivery(self):
		sd = frappe.get_all("Subscription Delivery", filters={"delivery_date": self.delivery_date, "status": "Locked", "docstatus": 1})
		if not sd:
			frappe.throw(_("Subscription Delivery not found or Pending for Date: <b>{0}</b>".format(self.get_formatted("delivery_date"))))

		self.subscription_delivery = sd[0].name

	def validate_drivers(self):
		drivers = []
		for d in self.drivers:
			key = (d.driver, d.delivery_time_slot)
			if key in drivers:
				frappe.throw(_("Duplicate Driver:{0} and Time Slot:{1} in Row: {2} ".format(d.driver, d.delivery_time_slot, d.idx)))
			drivers.append(key)

			dts = frappe.get_doc("Delivery Time Slot", d.delivery_time_slot)
			dts_start = "{0} {1}".format(self.delivery_date, dts.from_time)
			dts_end = "{0} {1}".format(self.delivery_date, dts.to_time)

			if not get_datetime(dts_start) <= get_datetime(d.departure_time) <= get_datetime(dts_end):
				frappe.throw(_("Departure Time: {0} must be in between {1} and {2} ".format(d.get_formatted("departure_time"), format_datetime(dts_start), format_datetime(dts_end))))


	@frappe.whitelist()
	def fetch_deliveries(self):
		self.validate_subscription_delivery()
		self.deliveries = []
		dns = frappe.get_all("Delivery Note", filters={"posting_date": self.delivery_date, "docstatus": 1},fields=["*"], order_by="creation asc")
		for d in dns:
			self.append("deliveries", {"customer": d.customer, "delivery_note": d.name, "sales_order": d.subscription})



	@frappe.whitelist()
	def assign_deliveries(self, use_google_roads: bool = False, optimize_waypoints: bool = True):
		"""
		Creates one Delivery Trip per driver row (time slot + departure time),
		assigns deliveries to the nearest eligible driver, builds trip stops,
		optionally optimizes order via Google Directions, and writes back references.
		"""
		if not self.deliveries:
			frappe.throw(_("Fetch Deliveries First"))
		if not self.drivers:
			frappe.throw(_("Add Drivers First"))

		# 1) Build driver profiles (start point, all area pins, and their time slots from this schedule)
		drivers = self._build_driver_profiles()

		# 2) Assign each delivery to nearest eligible driver (by time slot)
		assignments = self._assign_deliveries_to_drivers(drivers)

		# 3) For each driver row on the schedule → create a Delivery Trip with its assigned stops
		created = []
		for drow in self.drivers:
			drv_id = drow.driver
			drv = drivers.get(drv_id)
			if not drv:
				continue

			# deliveries that were assigned to this driver & match this driver row's slot
			slot = (drow.delivery_time_slot or "").strip() or "All Day"
			assigned_rows = [
				a for a in assignments
				if a["driver"] == drv_id and (a["delivery"].delivery_time_slot or "All Day") == slot
			]
			if not assigned_rows:
				# no deliveries for this driver row/slot; skip creating a trip
				continue

			# 3a) derive stop list (lat/lng + meta)
			stops = []
			for a in assigned_rows:
				dlv = a["delivery"]
				stops.append({
					"sales_order": dlv.sales_order,
					"delivery_note": getattr(dlv, "delivery_note", None),
					"customer": dlv.customer,
					"customer_name": dlv.customer_name,
					"address": dlv.address,
					"latitude": float(dlv.latitude),
					"longitude": float(dlv.longitude),
				})

			# 3b) order stops + compute totals
			ordered_stops, tot_km, tot_min = self._order_and_measure(
				start=(float(drow.latitude), float(drow.longitude)),
				stops=stops,
				use_google_roads=use_google_roads,
				optimize_waypoints=optimize_waypoints
			)

			# 3c) create Delivery Trip
			trip_name = self._create_delivery_trip_doc(
				driver_id=drv_id,
				driver_name=drow.driver_name,
				time_slot=slot,
				departure_time=drow.departure_time,
				start_lat=float(drow.latitude),
				start_lng=float(drow.longitude),
				ordered_stops=ordered_stops,
				total_km=tot_km,
				total_min=tot_min,
				vehicle=drow.vehicle
			)

			# 3d) write references back
			# driver row
			if hasattr(drow, "delivery_trip"):
				drow.delivery_trip = trip_name.name
			# per-delivery child updates
			for seq, a in enumerate(assigned_rows, start=1):
				dlv = a["delivery"]
				if hasattr(dlv, "delivery_trip"):
					dlv.delivery_trip = trip_name.name

				for d in trip_name.delivery_stops:
					if dlv.delivery_note == d.delivery_note:
						dlv.delivery_stop = d.name

				# write distance on delivery row (Haversine between start and assigned delivery, not the whole route)
				dlv.distance = round(a["distance_km"], 2)

			# also set driver total_estimated_distance for this row
			drow.total_estimated_distance = round(tot_km, 2)

			created.append({"driver": drv_id, "trip": trip_name.name, "stops": len(ordered_stops), "km": round(tot_km, 2)})

			# persist child-table changes
			self.save(ignore_permissions=True)
			frappe.db.commit()

		return {
			"created_trips": created,
			"message": _("Created {0} trip(s)").format(len(created))
		}

	# ---------------- internal helpers ----------------

	def _build_driver_profiles(self):
		profiles = {}
		for d in self.drivers:
			if not (d.driver and d.latitude and d.longitude):
				# skip incomplete rows
				continue
			drv = profiles.setdefault(d.driver, {
				"start": (float(d.latitude), float(d.longitude)),
				"areas": [],
				"slots": set(),
			})
			# collect slots from this schedule row
			slot = (d.delivery_time_slot or "").strip() or "All Day"
			drv["slots"].add(slot)

			# pull driver zones (pins) once
			if not drv["areas"]:
				driver_doc = frappe.get_doc("Driver", d.driver)
				for z in getattr(driver_doc, "zones", []) or []:
					if z.latitude and z.longitude:
						drv["areas"].append((float(z.latitude), float(z.longitude)))

		return profiles

	def _assign_deliveries_to_drivers(self, drivers):
		"""
		For every delivery row, find nearest eligible driver (time slot match or 'All Day').
		Distance is to the nearest of driver.start and driver.areas pins (Haversine).
		Returns a list of assignment dicts:
		[{"delivery": dlv_row, "driver": driver_id, "distance_km": x}, ...]
		"""
		assignments = []
		for dlv in self.deliveries:
			if not (dlv.latitude and dlv.longitude):
				continue
			dlat, dlng = float(dlv.latitude), float(dlv.longitude)
			slot = (dlv.delivery_time_slot or "").strip() or "All Day"

			best = None
			for drv_id, prof in drivers.items():
				if (slot in prof["slots"]) or ("All Day" in prof["slots"]):
					# distance to nearest driver pin
					mins = [self._haversine_km(dlat, dlng, *prof["start"])]
					for alat, alng in prof["areas"]:
						mins.append(self._haversine_km(dlat, dlng, alat, alng))
					dist = min(mins)
					if (best is None) or (dist < best["distance_km"]):
						best = {"delivery": dlv, "driver": drv_id, "distance_km": dist}

			if best:
				assignments.append(best)

		return assignments

	def _order_and_measure(self, start, stops, use_google_roads=False, optimize_waypoints=True):
		"""
		Returns (ordered_stops, total_km, total_min).
		If use_google_roads=True and googlemaps is available + key is configured,
		uses Directions with optimize_waypoints to order and get real road distance & duration.
		Otherwise, greedy nearest-neighbor order with Haversine sums.
		"""
		# nothing to do
		if not stops:
			return [], 0.0, 0.0

		if use_google_roads and googlemaps:
			key = frappe.db.get_single_value("Google Settings", "api_key")
			if key:
				client = googlemaps.Client(key=key)
				origin = f"{start[0]},{start[1]}"
				waypoints = [f"{s['latitude']},{s['longitude']}" for s in stops]

				try:
					directions = client.directions(
						origin=origin,
						destination=waypoints[-1],
						waypoints=waypoints[:-1] if len(waypoints) > 1 else None,
						optimize_waypoints=bool(optimize_waypoints),
						mode="driving"
					)
				except Exception as e:
					frappe.log_error(str(e), "DeliverySchedule.assign_deliveries Google Directions error")
					directions = None

				if directions:
					leg_order = []
					if optimize_waypoints and "routes" in directions[0] if isinstance(directions, dict) else True:
					# new client returns list, classic returns list; both include waypoint_order on route
						route = directions[0]
						waypoint_order = route.get("waypoint_order")
						if waypoint_order:
							leg_order = waypoint_order + [len(waypoints) - 1]
						else:
							leg_order = list(range(len(waypoints)))
					else:
						leg_order = list(range(len(waypoints)))

					# order stops
					ordered = [stops[i] for i in leg_order]
					# total distance / duration from legs
					total_m = 0
					total_s = 0
					for leg in directions[0]["legs"]:
						total_m += leg["distance"]["value"]	  # meters
						total_s += leg["duration"]["value"]	  # seconds
					return ordered, round(total_m / 1000.0, 2), round(total_s / 60.0, 1)

		# fallback: greedy nearest-neighbor from start
		remaining = stops[:]
		cur = {"latitude": start[0], "longitude": start[1]}
		ordered = []
		total_km = 0.0

		while remaining:
			# pick closest next
			nxt, d = min(
				((s, self._haversine_km(cur["latitude"], cur["longitude"], s["latitude"], s["longitude"]))
				 for s in remaining),
				key=lambda t: t[1]
			)
			ordered.append(nxt)
			total_km += d
			cur = nxt
			remaining.remove(nxt)

		return ordered, round(total_km, 2), 0.0  # duration unknown in haversine mode

	def _create_delivery_trip_doc(self, driver_id, driver_name, time_slot, departure_time,
								  start_lat, start_lng, ordered_stops, total_km, total_min, vehicle):
		"""
		Creates and saves a Delivery Trip with its child stops.
		Returns the new docname.
		"""
		trip = frappe.new_doc("Delivery Trip")
		# Map core fields (rename if your schema differs)
		if hasattr(trip, "driver"):			   trip.driver = driver_id
		if hasattr(trip, "driver_name"):		  trip.driver_name = driver_name
		if hasattr(trip, "delivery_time_slot"):   trip.delivery_time_slot = time_slot
		if hasattr(trip, "departure_time"):	   trip.departure_time = departure_time
		if hasattr(trip, "start_latitude"):	   trip.start_latitude = start_lat
		if hasattr(trip, "start_longitude"):	  trip.start_longitude = start_lng
		if hasattr(trip, "total_distance_km"):	trip.total_distance_km = total_km
		if hasattr(trip, "total_duration_min"):   trip.total_duration_min = total_min

		trip.vehicle = vehicle

		# Append stops
		child_fieldname = "stops" if "stops" in (trip.as_dict().keys()) else None
		if not child_fieldname:
			# try to find a child table field by type
			for df in trip.meta.fields:
				if df.fieldtype == "Table":
					child_fieldname = df.fieldname
					break

		seq = 1
		prev = {"latitude": start_lat, "longitude": start_lng}
		for s in ordered_stops:
			dist_km = self._haversine_km(prev["latitude"], prev["longitude"], s["latitude"], s["longitude"])
			row = {
				"sequence": seq,
				"sales_order": s.get("sales_order"),
				"delivery_note": s.get("delivery_note"),
				"customer": s.get("customer"),
				"customer_name": s.get("customer_name"),
				"address": s.get("address"),
				"latitude": s.get("latitude"),
				"longitude": s.get("longitude"),
				"distance_km": round(dist_km, 2),
			}
			trip.append(child_fieldname, row)
			prev = s
			seq += 1

		trip.insert(ignore_permissions=True)
		trip.process_route(True)
		trip.save()
		return trip

	@staticmethod
	def _haversine_km(lat1, lng1, lat2, lng2):
		R = 6371.0  # km
		phi1, phi2 = math.radians(lat1), math.radians(lat2)
		dphi = math.radians(lat2 - lat1)
		dlmb = math.radians(lng2 - lng1)
		a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb/2)**2
		return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


	def before_submit(self):
		if not self.subscription_delivery:
			frappe.throw(_("Fetch Deliveries First"))

	def on_submit(self):
		if not self.subscription_delivery:
			frappe.throw(_("Fetch Deliveries First"))

		if not self.drivers:
			frappe.throw(_("Add Drivers First"))

		delivery_trips = list({d.delivery_trip for d in self.drivers})
		for d in delivery_trips:
			doc = frappe.get_doc("Delivery Trip", d)
			doc.submit()


	def on_cancel(self):
		delivery_trips = list({d.delivery_trip for d in self.drivers})
		for d in delivery_trips:
			doc = frappe.get_doc("Delivery Trip", d)
			doc.cancel()


	


