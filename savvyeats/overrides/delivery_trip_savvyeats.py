import frappe
from erpnext.stock.doctype.delivery_trip.delivery_trip import DeliveryTrip

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

		