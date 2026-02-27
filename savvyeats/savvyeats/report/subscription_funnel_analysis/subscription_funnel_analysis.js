frappe.query_reports["Subscription Funnel Analysis"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
			reqd: 0,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 0,
		},
		{
			fieldname: "dish_plan",
			label: __("Plan"),
			fieldtype: "Link",
			options: "Dish Plan",
			reqd: 0,
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			reqd: 0,
		},
		{
			fieldname: "subscription_status",
			label: __("Subscription Status"),
			fieldtype: "Select",
			options: [
				"",
				"Active",
				"Paused",
				"Cancelled",
				"Expired",
				"Completed",
			].join("\n"),
			reqd: 0,
		},
		{
			fieldname: "show_details",
			label: __("Show Customer Detail"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		if (column.fieldname === "drop_rate") {
			const rate = parseFloat(data.drop_rate) || 0;
			if (rate >= 50) {
				value = `<span style="color:var(--red-500);font-weight:600;">${value}</span>`;
			} else if (rate >= 25) {
				value = `<span style="color:var(--orange-500);font-weight:600;">${value}</span>`;
			} else {
				value = `<span style="color:var(--green-500);">${value}</span>`;
			}
		}

		if (column.fieldname === "conversion_rate" || column.fieldname === "cumulative_conv") {
			const rate = parseFloat(data[column.fieldname]) || 0;
			const color =
				rate >= 75 ? "var(--green-500)"
				: rate >= 40 ? "var(--orange-500)"
				: "var(--red-500)";
			value = `<span style="color:${color};font-weight:600;">${value}</span>`;
		}

		if (column.fieldname === "drop_off_stage" && data.drop_off_stage) {
			if (data.drop_off_stage.startsWith("Completed")) {
				value = `<span style="color:var(--green-500);font-weight:600;">${value}</span>`;
			} else {
				value = `<span style="color:var(--red-500);">${value}</span>`;
			}
		}

		if (column.fieldname === "last_step_no") {
			const step = parseInt(data.last_step_no) || 0;
			const color =
				step === 11 ? "var(--green-500)"
				: step >= 8  ? "var(--blue-500)"
				: step >= 5  ? "var(--orange-500)"
				: "var(--red-500)";
			value = `<span style="color:${color};font-weight:700;">${value}</span>`;
		}

		return value;
	},

	onload(report) {
		report.page.fields_dict.show_details &&
			report.page.fields_dict.show_details.$input.on("change", () => {
				report.refresh();
			});
	},

	get_chart_data(columns, result) {
		if (!result || !result.length) return null;

		const hasSummary = result[0] && result[0].step_no !== undefined;
		if (!hasSummary) return null;

		const labels    = result.map((r) => r.step_name);
		const entered   = result.map((r) => r.entered   || 0);
		const completed = result.map((r) => r.completed || 0);
		const dropped   = result.map((r) => r.dropped   || 0);

		return {
			data: {
				labels,
				datasets: [
					{ name: __("Customers Reached"),   values: entered   },
					{ name: __("Customers Completed"), values: completed },
					{ name: __("Customers Dropped"),   values: dropped   },
				],
			},
			type: "bar",
			colors: ["#5e64ff", "#2ecc71", "#e74c3c"],
			height: 360,
			axisOptions: {
				xAxisMode: "tick",
			},
			tooltipOptions: {
				formatTooltipX : (d) => __("Step: ") + d,
				formatTooltipY : (d) => d + __(" customers"),
			},
			title: __("Subscription Funnel – Drop-off Analysis"),
		};
	},
};
