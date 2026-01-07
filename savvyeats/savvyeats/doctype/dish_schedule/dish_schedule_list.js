frappe.listview_settings["Dish Schedule"] = {
	get_indicator: function (doc) {
		if (doc.status === "Published") {
			// Closed
			return [__("Published"), "green", "status,=,Published"];
		} else if (doc.status === "Unpublished") {
			// on hold
			return [__("Unpublished"), "red", "status,=,Unpublished"];
		}
	}
};
