frappe.listview_settings["Sales Order"] = {
	add_fields: [
		"base_grand_total",
		"customer_name",
		"currency",
		"delivery_date",
		"per_delivered",
		"per_billed",
		"subscription_status",
		"order_type",
		"name",
		"skip_delivery_note",
	],
	get_indicator: function (doc) {
		if (doc.subscription_status === "Completed") {
			// Closed
			return [__("Completed"), "green", "subscription_status,=,Completed"];
		} else if (doc.subscription_status === "Pending") {
			// on hold
			return [__("Pending"), "grey", "subscription_status,=,Pending"];
		} else if (doc.subscription_status === "Active") {
			return [__("Active"), "blue", "subscription_status,=,Active"];
		} else if (doc.subscription_status === "Paused") {
			return [__("Paused"), "orange", "subscription_status,=,Paused"];
		} else if (doc.subscription_status === "Cancelled") {
			return [__("Cancelled"), "red", "subscription_status,=,Cancelled"];
		}
	},
	onload: function (listview) {
		var method = "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders";

		listview.page.add_menu_item(__("Close"), function () {
			listview.call_for_selected_items(method, { status: "Closed" });
		});

		listview.page.add_menu_item(__("Re-open"), function () {
			listview.call_for_selected_items(method, { status: "Submitted" });
		});

		listview.page.add_action_item(__("Sales Invoice"), () => {
			erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Sales Invoice");
		});

		listview.page.add_action_item(__("Delivery Note"), () => {
			erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Delivery Note");
		});

		listview.page.add_action_item(__("Advance Payment"), () => {
			erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Payment Entry");
		});
	},
};
