# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document


class AppSettings(Document):
	def validate(self):
		self.clear_cache()
		self.validate_renewal_cutoff()

	def validate_renewal_cutoff(self):
		# BR-10: a cutoff shorter than the kitchen-prep buffer can never guarantee a
		# zero-gap renewal, so reject it at config time.
		if not self.get("enable_pre_renewal"):
			return
		buffer_days = cint(self.get("buffer_days"))
		cutoff = cint(self.get("renewal_cutoff_days"))
		if cutoff < buffer_days:
			frappe.throw(
				_("Renewal Cutoff Days ({0}) must be greater than or equal to Buffer Days ({1}).").format(
					cutoff, buffer_days
				)
			)

	def on_update(self):
		frappe.get_cached_doc("App Settings", "App Settings")
