frappe.listview_settings["Subscription Delivery"] = {
	get_indicator: function (doc) {
		if (doc.status === "Pending") {
			return [__("Pending"), "orange", "status,=,Pending"];
		} else if (doc.status === "Locked") {
			// on hold
			return [__("Locked"), "green", "status,=,Locked"];
		}
	}
};