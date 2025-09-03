# Copyright (c) 2025, Nouman and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SavvyEatsSettings(Document):
	def validate(self):
		self.clear_cache()

	def on_update(self):
		frappe.get_cached_doc("SavvyEats Settings", "SavvyEats Settings")
