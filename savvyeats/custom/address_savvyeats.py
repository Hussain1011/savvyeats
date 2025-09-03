import frappe
from frappe import _

def validate(self, method):
	self.address_line1 = "Zone {0}, Street No {1}, Building No {2}, Unit No {3}".format(self.zone, self.street_no, self.building_no, self.unit_no)
	days = []
	for d in self.delivery_days:
		if d.day in days:
			frappe.throw(_("Duplicate Day : <b>{0}</b> in Delivery Days".format(d.day)))
		days.append(d.day)