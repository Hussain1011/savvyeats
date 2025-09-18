// Copyright (c) 2025, Nouman and contributors
// For license information, please see license.txt

frappe.ui.form.on("Delivery Schedule", {
	refresh(frm) {
		if(!frm.is_new()){
			frm.toggle_enable(["delivery_date"], 0);
			if(frm.doc.docstatus == 0 && frm.doc.deliveries.length == 0){
				frm.add_custom_button(__("Fetch Deliveries"), function() {
					frm.trigger("fetch_deliveries");
				}).addClass("btn-primary");
			}
			if(frm.doc.docstatus == 0 && frm.doc.deliveries.length > 0 && frm.doc.drivers.length > 0){
				frm.add_custom_button(__("Assign Deliveries"), function() {
					frm.trigger("assign_deliveries");
				}).addClass("btn-primary");
			}
		}
	},
	fetch_deliveries: function(frm) {
		frappe.call({
			method: "fetch_deliveries",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Fetching Deliveries"),
			callback: function(r){
				frm.refresh_field("deliveries");
				frm.refresh_field("drivers");
				frm.dirty();
				frm.save();
			}
		})
	},
	assign_deliveries: function(frm) {
		frappe.call({
			method: "assign_deliveries",
			doc: frm.doc,
			args: {
				use_google_roads: 1
			},
			freeze: true,
			freeze_message: __("Assigning Deliveries"),
			callback: function(r){
				frm.refresh_field("deliveries");
				frm.refresh_field("drivers");
				frm.dirty();
				frm.save();
			}
		})
	}
});
