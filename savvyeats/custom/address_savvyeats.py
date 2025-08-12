import frappe

def validate(self, method):
	self.address_line1 = "Zone {0}, Street No {1}, Building No {2}, Unit No {3}".format(self.zone, self.street_no, self.building_no, self.unit_no)