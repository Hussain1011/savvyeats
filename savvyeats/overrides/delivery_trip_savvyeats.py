import frappe
from frappe import _
from erpnext.stock.doctype.delivery_trip.delivery_trip import DeliveryTrip
from frappe.utils import cint, get_datetime, get_link_to_form

class DeliveryTripOverride(DeliveryTrip):
	def form_route_list(self, optimize):
		"""
		Form a list of address routes based on the delivery stops. If locks
		are present, and the routes need to be optimized, then they will be
		split into sublists at the specified lock position(s).

		Args:
		        optimize (bool): `True` if route needs to be optimized, else `False`

		Returns:
		        (list of list of str): List of address routes split at locks, if optimize is `True`
		"""
		if not self.driver_address:
			frappe.throw(_("Cannot Calculate Arrival Time as Driver Address is Missing."))

		home_address = frappe.get_doc("Address", self.driver_address)
		if not home_address.latitude or not home_address.longitude:
			frappe.throw(_("Missing Latitude or Langitude for Driver Address"))

		home_address = "{0},{1}".format(home_address.latitude, home_address.longitude)

		route_list = []

		leg = [home_address]

		for stop in self.delivery_stops:
			ca_doc = frappe.get_doc("Address", stop.address)
			customer_address = "{0},{1}".format(ca_doc.latitude, ca_doc.longitude)
			leg.append(customer_address)

			if optimize and stop.locked:
				route_list.append(leg)
				leg = [customer_address]

		# For last leg, append home address as the destination
		# only if lock isn't on the final stop
		if len(leg) > 1:
			leg.append(home_address)
			route_list.append(leg)


		return route_list

	def update_delivery_notes(self, delete=False):
		"""
		Update all connected Delivery Notes with Delivery Trip details
		(Driver, Vehicle, etc.). If `delete` is `True`, then details
		are removed.

		Args:
		        delete (bool, optional): Defaults to `False`. `True` if driver details need to be emptied, else `False`.
		"""

		delivery_notes = list(set(stop.delivery_note for stop in self.delivery_stops if stop.delivery_note))

		update_fields = {
			"driver": self.driver,
			"driver_name": self.driver_name,
			"vehicle_no": self.vehicle,
			"lr_no": self.name,
			"lr_date": self.departure_time,
			"delivery_trip": self.name,
			"delivery_status": "Scheduled"
		}

		for delivery_note in self.delivery_stops:
			if not delivery_note.delivery_note:
				continue
			note_doc = frappe.get_doc("Delivery Note", delivery_note.delivery_note)
			update_fields = {
				"latitude": delivery_note.latitude,
				"longitude": delivery_note.longitude,
				"distance": delivery_note.distance,
				"distance_uom": delivery_note.uom,
				"estimated_arrival": delivery_note.estimated_arrival
			}
			for field, value in update_fields.items():
				value = None if delete else value
				setattr(note_doc, field, value)

			note_doc.flags.ignore_validate_update_after_submit = True
			note_doc.save()

		delivery_notes = [get_link_to_form("Delivery Note", note) for note in delivery_notes]
		frappe.msgprint(_("Delivery Notes {0} updated").format(", ".join(delivery_notes)))

		