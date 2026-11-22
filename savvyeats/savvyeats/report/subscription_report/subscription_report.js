// Subscription Report: subscribers per month, renewals and an order export.

frappe.query_reports["Subscription Report"] = {
	filters: [
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: ["Subscribers", "Renewals", "Orders"],
			default: "Subscribers",
			reqd: 1,
			on_change: (report) => {
				const view = report.get_filter_value("view");
				report.toggle_filter_display("renewal_window", view !== "Renewals");
				report.refresh();
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: "2025-11-01",
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "plan",
			label: __("Plan"),
			fieldtype: "Select",
			options: [""],
		},
		{
			fieldname: "renewal_window",
			label: __("Renewal Window (Days)"),
			fieldtype: "Int",
			default: 7,
			description: __("A subscription counts as renewed if the customer's next one starts within this many days of its end."),
		},
		{
			fieldname: "include_zero_value",
			label: __("Include Zero-Value Orders"),
			fieldtype: "Check",
			default: 0,
			description: __("Orders with no value are mostly tests, so they are left out by default."),
		},
	],

	onload(report) {
		report.toggle_filter_display("renewal_window", report.get_filter_value("view") !== "Renewals");
		frappe
			.call("savvyeats.savvyeats.report.subscription_report.subscription_report.get_plan_groups")
			.then((r) => {
				const filter = report.get_filter("plan");
				filter.df.options = [""].concat(r.message || []);
				filter.refresh();
			});
	},
};
