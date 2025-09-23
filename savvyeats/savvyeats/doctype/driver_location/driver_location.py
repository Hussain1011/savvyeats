# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime
import datetime


class DriverLocation(Document):
	def validate(self):
		if self.flags.start:
			calculate_distance(self)
			frappe.db.set_value("Delivery Stop", self.delivery_stop, "start_time", self.timestamp)

	def after_insert(self):
		frappe.enqueue(calculate_distance, doc=self, queue="long", enqueue_after_commit=True)

def calculate_distance(doc):
	if doc.flags.start:
		doc.flags.start = False
	import googlemaps

	try:
		maps_client = googlemaps.Client(key=frappe.db.get_single_value("Google Settings", "api_key"))
	except Exception as e:
		frappe.log_error(e)

	origin = f"{doc.latitude},{doc.longitude}"
	destination = f"{doc.customer_latitude},{doc.customer_longitude}"

	try:
		dm = maps_client.distance_matrix(
			origins=[origin],
			destinations=[destination],
			mode="driving",
			units="metric",
			departure_time=get_datetime(doc.timestamp)
		)
		element = dm["rows"][0]["elements"][0]
		distance_m = element["distance"]["value"]
		duration_s = element["duration"]["value"]
		duration_in_traffic_s = element.get("duration_in_traffic", {}).get("value")

		estimated_arrival = get_datetime(doc.timestamp) + datetime.timedelta(seconds=int(duration_s))
		estimated_arrival_max = get_datetime(doc.timestamp) + datetime.timedelta(seconds=int(duration_in_traffic_s if duration_in_traffic_s else duration_s))
		doc.distance = distance_m
		doc.estimated_arrival = estimated_arrival
		doc.estimated_arrival_max = estimated_arrival_max
		doc.actual = 1
		doc.save()
		frappe.db.set_value("Delivery Stop", doc.delivery_stop, "actual_arrival", estimated_arrival_max)
		frappe.db.set_value("Delivery Stop", doc.delivery_stop, "remaining_distance", doc.distance)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(e)

