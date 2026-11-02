// Page: Subscription Dashboard
// Staff create a subscription on a customer's behalf.
// Phase 1 (live): create or pick a customer, optionally with delivery addresses ->
// draft subscription with no plan, which the customer finishes in the app once they
// sign up with the same mobile number.
// Full flow (plan, preferences -> priced draft) is built but hidden until a later
// phase; set SWB_FULL_FLOW to true to show it.
// Server API: savvyeats.savvyeats.page.subscription_dashboard.subscription_dashboard.*

const SWB_API = "savvyeats.savvyeats.page.subscription_dashboard.subscription_dashboard.";
const SWB_FULL_FLOW = false;

// Qatar only for now: an 8-digit mobile starting with 3, 5, 6 or 7, sent to the
// server as +974XXXXXXXX.
const SWB_COUNTRY_CODE = "974";

// Mirror of normalize_mobile on the server: the local 8-digit part.
function swb_local_mobile(value) {
	let digits = String(value || "").replace(/\D/g, "");
	if (digits.startsWith("00")) digits = digits.slice(2);
	if (digits.startsWith(SWB_COUNTRY_CODE) && digits.length > 8) digits = digits.slice(SWB_COUNTRY_CODE.length);
	return digits;
}

function swb_mobile_error(local) {
	if (!local) return __("Enter the customer's mobile no.");
	if (local.length !== 8) return __("Mobile no must be 8 digits.");
	if (!/^[3567]/.test(local)) return __("Qatar mobile numbers start with 3, 5, 6 or 7.");
	return null;
}

function swb_format_mobile(value) {
	const local = swb_local_mobile(value);
	return swb_mobile_error(local) ? value : `+${SWB_COUNTRY_CODE} ${local.slice(0, 4)} ${local.slice(4)}`;
}

frappe.pages["subscription-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Subscription Dashboard"),
		single_column: true,
	});
	wrapper.dashboard = new SubscriptionDashboard(page, wrapper);
};

class SubscriptionDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.$body = $(wrapper).find(".layout-main-section");
		this.currency = frappe.defaults.get_default("currency");
		this.page.set_secondary_action(__("Start Over"), () => this.reset());

		frappe.call(SWB_API + "get_setup_data").then((r) => {
			this.setup = r.message;
			this.reset();
		});
	}

	reset() {
		this.mode = "new";
		this.customer = null;
		this.meals = new Set();
		this.addresses = new Set();
		this.new_addresses = [];
		this.allergens = new Set();
		this.health_goals = new Set();
		this.preview = null;
		this.render();
	}

	// ---------- layout ----------

	render() {
		this.$body.html(`
			<style>${SWB_CSS}</style>
			<div class="swb">
				<div class="swb-main">
					${this.card(1, __("Customer"), `
						<div class="swb-toggle" data-role="mode">
							<button data-mode="new">${__("New customer")}</button>
							<button data-mode="existing">${__("Existing customer")}</button>
						</div>
						<div data-role="customer-new"></div>
						<div data-role="customer-existing"></div>
						<div data-role="customer-profile"></div>`)}
					${SWB_FULL_FLOW ? this.plan_card() : ""}
					${this.address_card(SWB_FULL_FLOW ? 3 : 2)}
					${SWB_FULL_FLOW ? this.preference_card() : ""}
				</div>
				<div class="swb-side"><div class="swb-card swb-summary" data-role="summary"></div></div>
			</div>
		`);
		this.$ = (role) => this.$body.find(`[data-role="${role}"]`);

		this.make_customer_section();
		if (SWB_FULL_FLOW) {
			this.make_plan_section();
			this.make_preference_section();
		}
		this.$("add-address").on("click", () => this.edit_new_address());
		this.set_mode("new");
		this.refresh();
	}

	plan_card() {
		return this.card(2, __("Plan"), `
			<div data-role="plan"></div>
			<div class="swb-label">${__("Meals")}</div>
			<div class="swb-chips" data-role="meals"></div>
			<div class="swb-hint" data-role="plan-hint"></div>`);
	}

	address_card(step) {
		return this.card(step, SWB_FULL_FLOW ? __("Delivery Addresses") : __("Delivery Addresses (optional)"), `
			<div class="swb-days" data-role="coverage"></div>
			<div class="swb-addresses" data-role="addresses"></div>
			<button class="btn btn-default btn-sm" data-role="add-address">
				${frappe.utils.icon("add", "sm")} ${__("Add address")}
			</button>`);
	}

	preference_card() {
		return this.card(4, __("Preferences"), `
			<div class="swb-label">${__("Allergens")}</div>
			<div class="swb-chips" data-role="allergens"></div>
			<div class="swb-label">${__("Health Goals")}</div>
			<div class="swb-chips" data-role="health_goals"></div>
			<div data-role="contact"></div>`);
	}

	card(step, title, body) {
		return `<section class="swb-card">
			<div class="swb-card-head"><span class="swb-step">${step}</span>${title}</div>
			<div class="swb-card-body">${body}</div>
		</section>`;
	}

	field_group(role, fields) {
		const fg = new frappe.ui.FieldGroup({ fields, body: this.$(role) });
		fg.make();
		return fg;
	}

	// ---------- 1. customer ----------

	make_customer_section() {
		const changed = () => this.refresh();
		this.new_customer = this.field_group("customer-new", [
			{ fieldtype: "Data", fieldname: "customer_name", label: __("Full Name"), reqd: 1, onchange: changed },
			{ fieldtype: "Data", fieldname: "mobile_no", label: __("Mobile No"), reqd: 1, description: __("Qatar mobile, 8 digits") },
			{ fieldtype: "Column Break" },
			{ fieldtype: "Data", fieldname: "email_id", label: __("Email"), options: "Email" },
			{ fieldtype: "Link", fieldname: "gender", label: __("Gender"), options: "Gender" },
		]);
		const mobile = this.new_customer.get_field("mobile_no");
		mobile.$input
			.attr({ inputmode: "numeric", autocomplete: "tel-national", placeholder: "5555 1234" })
			.wrap('<div class="swb-phone"></div>')
			.before(`<span>+${SWB_COUNTRY_CODE}</span>`)
			.on("input", () => {
				// Digits only, and a pasted "+974 5555 1234" keeps just the local part.
				const local = swb_local_mobile(mobile.$input.val()).slice(0, 8);
				if (mobile.$input.val() !== local) mobile.$input.val(local);
				mobile.$wrapper.toggleClass("has-error", local.length === 8 && !!swb_mobile_error(local));
				this.refresh();
			})
			.on("blur", () => mobile.$wrapper.toggleClass("has-error", !!mobile.$input.val() && !!swb_mobile_error(this.new_mobile())));
		this.existing_customer = this.field_group("customer-existing", [
			{
				fieldtype: "Link",
				fieldname: "customer",
				label: __("Customer"),
				options: "Customer",
				reqd: 1,
				get_query: () => ({ filters: { name: ["!=", "Online Customer"], disabled: 0 } }),
				onchange: () => this.load_customer(),
			},
		]);
		this.$("mode").on("click", "button", (e) => this.set_mode($(e.currentTarget).data("mode")));
	}

	new_mobile() {
		return swb_local_mobile(this.new_customer.get_field("mobile_no").$input.val());
	}

	// Read from the input, not the control value, which only updates on change.
	new_customer_values() {
		const local = this.new_mobile();
		return { ...(this.new_customer.get_values(true) || {}), mobile_no: local ? `+${SWB_COUNTRY_CODE}${local}` : "" };
	}

	set_mode(mode) {
		this.mode = mode;
		this.$("mode").find("button").each((_, b) => $(b).toggleClass("active", $(b).data("mode") === mode));
		this.$("customer-new").toggle(mode === "new");
		this.$("customer-existing").toggle(mode === "existing");
		if (mode === "new") {
			this.customer = null;
			this.addresses.clear();
		} else {
			this.load_customer();
		}
		this.refresh();
	}

	load_customer() {
		const name = this.existing_customer.get_value("customer");
		if (!name) {
			this.customer = null;
			this.addresses.clear();
			return this.refresh();
		}
		if (this.customer && this.customer.name === name) return;
		frappe.call(SWB_API + "get_customer_details", { customer: name }).then((r) => {
			this.customer = r.message;
			this.addresses = new Set(this.customer.addresses.length === 1 ? [this.customer.addresses[0].name] : []);
			this.refresh();
		});
	}

	render_customer_profile() {
		const c = this.mode === "existing" && this.customer;
		this.$("customer-profile").html(
			c
				? `<div class="swb-profile">
					<div class="swb-avatar">${frappe.get_abbr(c.customer_name)}</div>
					<div>
						<div class="swb-strong">${frappe.utils.escape_html(c.customer_name)}</div>
						<div class="swb-muted">${[c.mobile_no && swb_format_mobile(c.mobile_no), c.email_id].filter(Boolean).map(frappe.utils.escape_html).join(" · ") || __("No contact details")}</div>
						<div class="swb-small">${
							c.user
								? `<span class="indicator-pill green">${__("App account linked")}</span>`
								: !c.mobile_no
									? `<span class="indicator-pill red">${__("No mobile no — cannot link to the app")}</span>`
									: swb_mobile_error(swb_local_mobile(c.mobile_no))
										? `<span class="indicator-pill red">${__("Not a valid Qatar mobile no — cannot link to the app")}</span>`
										: `<span class="indicator-pill orange">${__("No app account yet — links on signup with {0}", [frappe.utils.escape_html(swb_format_mobile(c.mobile_no))])}</span>`
						}</div>
					</div>
					<a class="swb-muted" href="/app/customer/${encodeURIComponent(c.name)}" target="_blank">${__("Open")}</a>
				</div>`
				: ""
		);
	}

	// ---------- 2. plan ----------

	make_plan_section() {
		const s = this.setup;
		const changed = () => this.refresh();
		this.plan = this.field_group("plan", [
			{
				fieldtype: "Select",
				fieldname: "dish_plan",
				label: __("Dish Plan"),
				reqd: 1,
				options: [{ label: "", value: "" }].concat(s.dish_plans.map((p) => ({ label: p.label, value: p.name }))),
				onchange: () => this.on_plan_change(),
			},
			{ fieldtype: "Select", fieldname: "week_plan", label: __("Week Plan"), reqd: 1, onchange: changed },
			{
				fieldtype: "Select",
				fieldname: "delivery_time_slot",
				label: __("Delivery Time Slot"),
				reqd: 1,
				options: [""].concat(s.delivery_time_slots.map((t) => t.name)),
				onchange: changed,
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Select",
				fieldname: "period_type",
				label: __("Period"),
				reqd: 1,
				options: ["Week", "Month"],
				default: "Week",
				onchange: changed,
			},
			{ fieldtype: "Int", fieldname: "period_count", label: __("Number of Periods"), reqd: 1, default: 1, onchange: changed },
			{
				fieldtype: "Date",
				fieldname: "start_date",
				label: __("Start Date"),
				reqd: 1,
				default: frappe.datetime.add_days(frappe.datetime.get_today(), 1 + (s.buffer_days || 0)),
				onchange: changed,
			},
			{
				fieldtype: "Select",
				fieldname: "meal_choice",
				label: __("Meal Choice"),
				options: ["User Select Meal", "Savvy Choice"],
				default: "User Select Meal",
				onchange: changed,
			},
		]);
		this.$("meals").on("click", ".swb-chip", (e) => {
			const $c = $(e.currentTarget);
			if ($c.hasClass("locked")) return;
			this.toggle(this.meals, $c.data("value"));
			this.refresh();
		});
	}

	current_plan() {
		const name = this.plan.get_value("dish_plan");
		return this.setup.dish_plans.find((p) => p.name === name);
	}

	on_plan_change() {
		const plan = this.current_plan();
		this.meals = new Set(plan ? plan.meals.filter((m) => m.mandatory).map((m) => m.meal) : []);
		const weeks = plan ? plan.week_plans.map((w) => w.name) : [];
		this.plan.set_df_property("week_plan", "options", [""].concat(weeks));
		this.plan.set_value("week_plan", weeks.length === 1 ? weeks[0] : "");
		if (plan && plan.has_date_limit && plan.start_date) {
			const start = frappe.datetime.str_to_obj(plan.start_date) > new Date() ? plan.start_date : this.plan.get_value("start_date");
			this.plan.set_value("start_date", start);
		}
		this.refresh();
	}

	render_meals() {
		const plan = this.current_plan();
		if (!plan) {
			this.$("meals").html(`<span class="swb-muted">${__("Select a dish plan first.")}</span>`);
			this.$("plan-hint").html("");
			return;
		}
		this.$("meals").html(
			plan.meals
				.map((m) => {
					const on = this.meals.has(m.meal);
					return `<span class="swb-chip ${on ? "on" : ""} ${m.mandatory ? "locked" : ""}" data-value="${frappe.utils.escape_html(m.meal)}"
						title="${m.mandatory ? __("Mandatory for this plan") : ""}">
						${frappe.utils.escape_html(m.meal)} <small>×${m.min_qty}/${__("day")}</small>
						${m.mandatory ? frappe.utils.icon("lock", "xs") : ""}
					</span>`;
				})
				.join("")
		);
		const week = plan.week_plans.find((w) => w.name === this.plan.get_value("week_plan"));
		const bits = [`${plan.min_calories}–${plan.max_calories} kcal`];
		if (week) bits.push(__("Delivers {0}", [week.days.map((d) => d.slice(0, 3)).join(", ")]));
		if (plan.has_date_limit) {
			bits.push(__("Available {0} – {1}", [frappe.datetime.str_to_user(plan.start_date), frappe.datetime.str_to_user(plan.end_date)]));
		}
		const limit = this.plan.get_value("period_type") === "Month" ? this.setup.max_months : this.setup.max_weeks;
		if (limit) bits.push(__("Max {0} {1}(s)", [limit, __(this.plan.get_value("period_type") || "Week").toLowerCase()]));
		this.$("plan-hint").html(bits.join(" · "));
	}

	// ---------- 3. addresses ----------

	edit_new_address(index) {
		const existing = index !== undefined ? this.new_addresses[index] : null;
		const free_days = this.uncovered_days();
		const d = new frappe.ui.Dialog({
			title: existing ? __("Edit Address") : __("New Delivery Address"),
			fields: [
				{ fieldtype: "Data", fieldname: "address_title", label: __("Label"), description: __("e.g. Home, Office") },
				{ fieldtype: "Data", fieldname: "zone", label: __("Zone"), reqd: 1 },
				{ fieldtype: "Data", fieldname: "street_no", label: __("Street No"), reqd: 1 },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Data", fieldname: "city", label: __("City"), default: "Doha" },
				{ fieldtype: "Data", fieldname: "building_no", label: __("Building No"), reqd: 1 },
				{ fieldtype: "Data", fieldname: "unit_no", label: __("Unit No") },
				{ fieldtype: "Section Break" },
				{
					fieldtype: "MultiCheck",
					fieldname: "delivery_days",
					label: __("Delivery Days"),
					reqd: 1,
					columns: 4,
					options: this.setup.week_days.map((day) => ({
						label: __(day),
						value: day,
						checked: existing ? existing.delivery_days.includes(day) : free_days.includes(day),
					})),
				},
				{ fieldtype: "Small Text", fieldname: "delivery_instructions", label: __("Delivery Instructions") },
				{ fieldtype: "Section Break", label: __("Location (optional)"), collapsible: 1 },
				{ fieldtype: "Data", fieldname: "latitude", label: __("Latitude") },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Data", fieldname: "longitude", label: __("Longitude") },
			],
			primary_action_label: existing ? __("Update") : __("Add"),
			primary_action: (values) => {
				if (!values.delivery_days || !values.delivery_days.length) {
					frappe.msgprint(__("Select at least one delivery day."));
					return;
				}
				if (existing) this.new_addresses[index] = values;
				else this.new_addresses.push(values);
				d.hide();
				this.refresh();
			},
		});
		// delivery_days is pre-checked through the MultiCheck options above.
		if (existing) d.set_values((({ delivery_days, ...rest }) => rest)(existing));
		d.show();
	}

	uncovered_days() {
		if (!SWB_FULL_FLOW) {
			const p = this.local_coverage();
			return this.setup.week_days.filter((day) => !p || !p.coverage[day].length);
		}
		const p = this.preview;
		if (!p || !p.needed_days) return [];
		return p.needed_days.filter((day) => !p.coverage[day].length);
	}

	render_addresses() {
		const existing = (this.mode === "existing" && this.customer && this.customer.addresses) || [];
		const day_pills = (days) =>
			`<div class="swb-mini-days">${this.setup.week_days
				.map((day) => `<span class="${days.includes(day) ? "on" : ""}">${__(day).slice(0, 2)}</span>`)
				.join("")}</div>`;
		const esc = frappe.utils.escape_html;

		const cards = existing.map((a) => {
			const on = this.addresses.has(a.name);
			return `<label class="swb-address ${on ? "on" : ""}">
				<input type="checkbox" data-address="${esc(a.name)}" ${on ? "checked" : ""}>
				<div class="swb-address-body">
					<div class="swb-strong">${esc(a.address_title || a.name)}</div>
					<div class="swb-muted">${esc(a.address_line1 || "")}</div>
					${day_pills(a.delivery_days)}
				</div>
			</label>`;
		});
		this.new_addresses.forEach((a, i) => {
			cards.push(`<div class="swb-address on">
				<div class="swb-address-body">
					<div class="swb-strong">${esc(a.address_title || __("New address"))} <span class="swb-tag">${__("New")}</span></div>
					<div class="swb-muted">${esc(__("Zone {0}, Street {1}, Building {2}", [a.zone, a.street_no, a.building_no]))}${a.unit_no ? esc(", " + __("Unit {0}", [a.unit_no])) : ""}</div>
					${day_pills(a.delivery_days)}
					<div class="swb-address-actions">
						<a data-edit="${i}">${__("Edit")}</a>
						<a data-remove="${i}">${__("Remove")}</a>
					</div>
				</div>
			</div>`);
		});

		this.$("addresses").html(cards.join("") || `<div class="swb-muted">${__("No addresses yet — add one to cover the delivery days.")}</div>`);
		this.$("addresses").find("input[data-address]").on("change", (e) => {
			this.toggle(this.addresses, $(e.currentTarget).data("address"));
			this.refresh();
		});
		this.$("addresses").find("[data-edit]").on("click", (e) => this.edit_new_address(cint($(e.currentTarget).data("edit"))));
		this.$("addresses").find("[data-remove]").on("click", (e) => {
			this.new_addresses.splice(cint($(e.currentTarget).data("remove")), 1);
			this.refresh();
		});
	}

	// Phase 1 has no plan to preview, so coverage is worked out here from the picked
	// addresses; with no needed_days, every day an address covers counts as needed.
	local_coverage() {
		const existing = ((this.mode === "existing" && this.customer && this.customer.addresses) || []).filter((a) =>
			this.addresses.has(a.name)
		);
		const sources = existing
			.map((a) => [a.address_title || a.name, a.delivery_days])
			.concat(this.new_addresses.map((a) => [a.address_title || __("New address"), a.delivery_days || []]));
		if (!sources.length) return null;

		const coverage = Object.fromEntries(this.setup.week_days.map((day) => [day, []]));
		sources.forEach(([label, days]) => days.forEach((day) => coverage[day] && coverage[day].push(label)));
		return { coverage, needed_days: null };
	}

	address_errors() {
		const p = this.local_coverage();
		if (!p) return [];
		return this.setup.week_days
			.filter((day) => p.coverage[day].length > 1)
			.map((day) => frappe.utils.escape_html(__("{0} is set on more than one address: {1}.", [__(day), p.coverage[day].join(", ")])));
	}

	render_coverage() {
		const p = SWB_FULL_FLOW ? this.preview : this.local_coverage();
		if (!p || !p.coverage) {
			this.$("coverage").html("");
			return;
		}
		this.$("coverage").html(
			this.setup.week_days
				.map((day) => {
					const owners = p.coverage[day];
					const needed = p.needed_days ? p.needed_days.includes(day) : owners.length > 0;
					const state = owners.length > 1 ? "clash" : needed ? (owners.length ? "ok" : "missing") : "off";
					const tip = owners.length ? owners.join(", ") : needed ? __("No address") : __("No delivery");
					return `<div class="swb-day ${state}" title="${frappe.utils.escape_html(tip)}">
						<b>${__(day).slice(0, 3)}</b><small>${frappe.utils.escape_html(owners[0] || (needed ? __("missing") : "—"))}</small>
					</div>`;
				})
				.join("")
		);
	}

	// ---------- 4. preferences ----------

	make_preference_section() {
		["allergens", "health_goals"].forEach((key) => {
			this.$(key)
				.html(
					this.setup[key].length
						? this.setup[key].map((v) => `<span class="swb-chip" data-value="${frappe.utils.escape_html(v)}">${frappe.utils.escape_html(v)}</span>`).join("")
						: `<span class="swb-muted">${__("None configured")}</span>`
				)
				.on("click", ".swb-chip", (e) => {
					const $c = $(e.currentTarget);
					this.toggle(this[key], $c.data("value"));
					$c.toggleClass("on", this[key].has($c.data("value")));
				});
		});
		this.contact = this.field_group("contact", [
			{
				fieldtype: "Data",
				fieldname: "contact_person_name",
				label: __("Delivery Contact Person"),
				description: __("Leave empty to use the customer's name and mobile"),
			},
			{ fieldtype: "Column Break" },
			{ fieldtype: "Data", fieldname: "contact_phone", label: __("Contact Phone"), options: "Phone" },
		]);
	}

	// ---------- payload / preview ----------

	payload() {
		const plan = this.plan.get_values(true) || {};
		const contact = this.contact.get_values(true) || {};
		return {
			customer: this.mode === "existing" ? this.existing_customer.get_value("customer") || null : null,
			new_customer: this.mode === "new" ? this.new_customer_values() : null,
			dish_plan: plan.dish_plan,
			meals: [...this.meals],
			week_plan: plan.week_plan,
			period_type: plan.period_type,
			period_count: plan.period_count,
			start_date: plan.start_date,
			delivery_time_slot: plan.delivery_time_slot,
			meal_choice: plan.meal_choice,
			allergens: [...this.allergens],
			health_goals: [...this.health_goals],
			addresses: [...this.addresses],
			new_addresses: this.new_addresses,
			contact_person_name: contact.contact_person_name,
			contact_phone: contact.contact_phone,
		};
	}

	customer_errors() {
		if (this.mode === "existing") {
			if (!this.customer) return [__("Select a customer.")];
			if (!SWB_FULL_FLOW && !this.customer.user) {
				if (!this.customer.mobile_no) return [__("Add a mobile no to this customer first, so the draft can reach their app.")];
				if (swb_mobile_error(swb_local_mobile(this.customer.mobile_no))) {
					return [
						__("Mobile no {0} on this customer is not a valid Qatar mobile. Fix it on the customer first, so the draft can reach their app.", [
							frappe.utils.escape_html(this.customer.mobile_no),
						]),
					];
				}
			}
			return [];
		}
		const c = this.new_customer.get_values(true) || {};
		const errors = [];
		if (!c.customer_name) errors.push(__("Enter the customer's full name."));
		const mobile_error = swb_mobile_error(this.new_mobile());
		if (mobile_error) errors.push(mobile_error);
		return errors;
	}

	// Re-render what depends on local state now, then re-price on the server.
	refresh() {
		this.render_customer_profile();
		this.render_addresses();
		this.render_coverage();
		if (!SWB_FULL_FLOW) return this.render_draft_summary();

		this.render_meals();
		this.render_summary();

		clearTimeout(this._preview_timer);
		this._preview_timer = setTimeout(() => this.fetch_preview(), 350);
	}

	fetch_preview() {
		const payload = this.payload();
		if (!payload.dish_plan) {
			this.preview = null;
			return this.render_summary();
		}
		const seq = (this._preview_seq = (this._preview_seq || 0) + 1);
		frappe.call({ method: SWB_API + "preview_subscription", args: { data: payload } }).then((r) => {
			if (seq !== this._preview_seq) return; // a newer request is in flight
			this.preview = r.message;
			this.render_coverage();
			this.render_summary();
		});
	}

	render_summary() {
		const p = this.preview;
		const plan = this.current_plan();
		const fmt = (v) => format_currency(v, this.currency);
		const esc = frappe.utils.escape_html;
		const name = this.mode === "existing" ? this.customer && this.customer.customer_name : (this.new_customer.get_values(true) || {}).customer_name;

		const blockers = [...this.customer_errors()];
		if (!plan) blockers.push(__("Select a dish plan."));
		// Server messages can carry staff-typed text (address labels): escape them.
		else if (p) blockers.push(...[...(p.errors || []), ...(p.address_issues || [])].map(esc));

		const row = (label, value) => `<div class="swb-row"><span>${label}</span><span>${value || "—"}</span></div>`;
		const priced = p && !(p.errors || []).length;

		this.$("summary").html(`
			<div class="swb-card-head">${__("Summary")}</div>
			<div class="swb-card-body">
				${row(__("Customer"), name && esc(name))}
				${row(__("Plan"), plan && esc(plan.label))}
				${row(__("Pricing"), priced && esc(p.dish_plan_pricing))}
				${row(__("Period"), plan && `${cint(this.plan.get_value("period_count"))} × ${__(this.plan.get_value("period_type"))}`)}
				${row(__("Dates"), priced && `${frappe.datetime.str_to_user(p.start_date)} → ${frappe.datetime.str_to_user(p.end_date)}`)}
				${row(__("Deliveries"), priced && p.delivery_count)}
				${
					priced
						? `<table class="swb-lines">
							<thead><tr><th>${__("Meal")}</th><th>${__("Qty")}</th><th>${__("Rate")}</th><th>${__("Amount")}</th></tr></thead>
							<tbody>${p.lines.map((l) => `<tr><td>${esc(l.meal)}</td><td>${l.qty}</td><td>${fmt(l.rate)}</td><td>${fmt(l.amount)}</td></tr>`).join("")}</tbody>
						</table>
						<div class="swb-total"><span>${__("Subtotal")}</span><span>${fmt(p.subtotal)}</span></div>
						<div class="swb-muted swb-small">${__("Taxes and discounts are applied when the order is saved. Dishes can be selected later — every meal starts as \"Item Not Selected\".")}</div>`
						: ""
				}
				${blockers.length ? `<ul class="swb-blockers">${blockers.map((b) => `<li>${b}</li>`).join("")}</ul>` : ""}
				<button class="btn btn-primary btn-block" data-role="create" ${blockers.length || !priced ? "disabled" : ""}>
					${__("Create Subscription")}
				</button>
			</div>
		`);
		this.$("create").on("click", () => this.create());
	}

	create() {
		frappe.call({
			method: SWB_API + "create_subscription",
			args: { data: this.payload() },
			freeze: true,
			freeze_message: __("Creating subscription…"),
		}).then((r) => r.message && this.render_success(r.message));
	}

	render_success(o) {
		const fmt = (v) => format_currency(v, o.currency);
		const esc = frappe.utils.escape_html;
		this.$body.html(`
			<style>${SWB_CSS}</style>
			<div class="swb-card swb-success">
				<div class="swb-success-icon">${frappe.utils.icon("check", "lg")}</div>
				<h3>${__("Subscription created")}</h3>
				<p class="swb-muted">${__("{0} was saved as a draft for {1}.", [this.order_anchor(o.name), `<b>${esc(o.customer_name)}</b>`])}</p>
				<div class="swb-success-grid">
					<div><small>${__("Pricing")}</small><b>${esc(o.dish_plan_pricing)}</b></div>
					<div><small>${__("Dates")}</small><b>${frappe.datetime.str_to_user(o.start_date)} → ${frappe.datetime.str_to_user(o.end_date)}</b></div>
					<div><small>${__("Deliveries")}</small><b>${o.delivery_count}</b></div>
					<div><small>${__("Grand Total")}</small><b>${fmt(o.grand_total)}</b></div>
				</div>
				${this.order_link_box(o.name)}
				<div class="swb-success-actions">
					<a class="btn btn-primary" href="/app/sales-order/${encodeURIComponent(o.name)}">${__("Open Sales Order")}</a>
					<button class="btn btn-default" data-role="again">${__("Create another")}</button>
				</div>
			</div>
		`);
		this.$body.find('[data-role="again"]').on("click", () => this.reset());
		this.bind_order_link(o.name);
	}

	// ---------- phase 1: draft only ----------

	render_draft_summary() {
		const esc = frappe.utils.escape_html;
		const c = this.mode === "existing" ? this.customer : this.new_customer_values();
		const errors = [...this.customer_errors(), ...this.address_errors()];
		const draft = this.mode === "existing" && this.customer && this.customer.draft_order;
		const address_count = this.addresses.size + this.new_addresses.length;
		const row = (label, value) => `<div class="swb-row"><span>${label}</span><span>${value || "—"}</span></div>`;

		this.$("summary").html(`
			<div class="swb-card-head">${__("Draft Subscription")}</div>
			<div class="swb-card-body">
				${row(__("Customer"), c && c.customer_name && esc(c.customer_name))}
				${row(__("Mobile No"), c && c.mobile_no && esc(swb_format_mobile(c.mobile_no)))}
				${row(__("Addresses"), address_count)}
				${draft ? row(__("Open draft"), `<a href="/app/sales-order/${encodeURIComponent(draft)}">${esc(draft)}</a>`) : ""}
				<div class="swb-muted swb-small">${
					draft
						? address_count
							? __("This customer already has an open draft; it will be reused and its addresses replaced.")
							: __("This customer already has an open draft; it will be reused.")
						: __("A draft without a plan is created. The customer finishes the plan and payment in the app after signing up with this mobile number.")
				}</div>
				${errors.length ? `<ul class="swb-blockers">${errors.map((e) => `<li>${e}</li>`).join("")}</ul>` : ""}
				<button class="btn btn-primary btn-block" data-role="create" ${errors.length ? "disabled" : ""}>
					${draft ? (address_count ? __("Update Existing Draft") : __("Use Existing Draft")) : __("Create Draft Subscription")}
				</button>
			</div>
		`);
		this.$("create").on("click", () => this.create_draft());
	}

	create_draft() {
		frappe.call({
			method: SWB_API + "create_draft_subscription",
			args: {
				data: {
					customer: this.payload_customer(),
					new_customer: this.mode === "new" ? this.new_customer_values() : null,
					addresses: [...this.addresses],
					new_addresses: this.new_addresses,
				},
			},
			freeze: true,
			freeze_message: __("Creating draft subscription…"),
		}).then((r) => r.message && this.render_draft_success(r.message));
	}

	payload_customer() {
		return this.mode === "existing" ? this.existing_customer.get_value("customer") || null : null;
	}

	render_draft_success(o) {
		const esc = frappe.utils.escape_html;
		this.$body.html(`
			<style>${SWB_CSS}</style>
			<div class="swb-card swb-success">
				<div class="swb-success-icon">${frappe.utils.icon("check", "lg")}</div>
				<h3>${o.reused ? __("Draft already exists") : __("Draft subscription created")}</h3>
				<p class="swb-muted">${__("{0} is a draft for {1}.", [this.order_anchor(o.name), `<b>${esc(o.customer_name)}</b>`])}${
					o.address_count ? " " + __("{0} delivery address(es) attached.", [o.address_count]) : ""
				}</p>
				<p class="swb-muted">${
					o.user
						? __("The customer already has an app account — the draft is in their app now.")
						: __("It appears in the app once the customer signs up or logs in with mobile no {0}.", [`<b>${esc(swb_format_mobile(o.mobile_no || ""))}</b>`])
				}</p>
				${this.order_link_box(o.name)}
				<div class="swb-success-actions">
					<a class="btn btn-primary" href="/app/sales-order/${encodeURIComponent(o.name)}">${__("Open Sales Order")}</a>
					<button class="btn btn-default" data-role="again">${__("Create another")}</button>
				</div>
			</div>
		`);
		this.$body.find('[data-role="again"]').on("click", () => this.reset());
		this.bind_order_link(o.name);
	}

	// ---------- order link (success screens) ----------

	order_url(name) {
		return `${window.location.origin}/app/sales-order/${encodeURIComponent(name)}`;
	}

	order_anchor(name) {
		return `<a class="swb-strong" href="/app/sales-order/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`;
	}

	order_link_box(name) {
		return `<div class="swb-link">
			<input type="text" readonly value="${frappe.utils.escape_html(this.order_url(name))}" data-role="order-url">
			<button class="btn btn-default btn-sm" data-role="copy-link">${frappe.utils.icon("link-url", "sm")} ${__("Copy link")}</button>
		</div>`;
	}

	bind_order_link(name) {
		this.$body.find('[data-role="order-url"]').on("focus", (e) => e.currentTarget.select());
		this.$body.find('[data-role="copy-link"]').on("click", () => frappe.utils.copy_to_clipboard(this.order_url(name)));
	}

	toggle(set, value) {
		set.has(value) ? set.delete(value) : set.add(value);
	}
}

const SWB_CSS = `
.swb { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:16px; align-items:start; padding-bottom:40px; }
.swb-main { display:flex; flex-direction:column; gap:16px; min-width:0; }
.swb-side { position:sticky; top:calc(var(--navbar-height, 48px) + 16px); }
.swb-card { background:var(--card-bg); border:1px solid var(--border-color); border-radius:var(--border-radius-lg, 12px); }
.swb-card-head { display:flex; align-items:center; gap:10px; padding:12px 16px; border-bottom:1px solid var(--border-color); font-weight:600; font-size:var(--text-md, 14px); }
.swb-card-body { padding:16px; }
.swb-step { width:24px; height:24px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; background:var(--primary); color:var(--white, #fff); font-size:12px; }
.swb-toggle { display:inline-flex; padding:3px; margin-bottom:12px; border-radius:8px; background:var(--control-bg); }
.swb-toggle button { border:0; background:transparent; padding:5px 14px; border-radius:6px; font-size:var(--text-sm, 13px); color:var(--text-muted); }
.swb-toggle button.active { background:var(--card-bg); color:var(--text-color); box-shadow:var(--shadow-sm); font-weight:500; }
.swb-label { font-size:var(--text-sm, 13px); color:var(--text-muted); margin:4px 0 8px; }
.swb-chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.swb-chip { display:inline-flex; align-items:center; gap:6px; padding:5px 12px; border-radius:999px; border:1px solid var(--border-color); cursor:pointer; user-select:none; font-size:var(--text-sm, 13px); }
.swb-chip small { color:var(--text-muted); }
.swb-chip.on { border-color:var(--primary); background:var(--bg-blue, rgba(59,130,246,.1)); color:var(--text-color); }
.swb-chip.locked { cursor:default; }
.swb-hint, .swb-muted { color:var(--text-muted); font-size:var(--text-sm, 13px); }
.swb-small { font-size:var(--text-xs, 11px); margin-top:8px; }
.swb-strong { font-weight:600; }
.swb-profile { display:flex; align-items:center; gap:12px; padding:10px 12px; border-radius:8px; background:var(--control-bg); }
.swb-profile > div:nth-child(2) { flex:1; min-width:0; }
.swb-avatar { width:36px; height:36px; border-radius:50%; display:flex; align-items:center; justify-content:center; background:var(--primary); color:var(--white, #fff); font-weight:600; }
.swb-days { display:grid; grid-template-columns:repeat(7, minmax(0,1fr)); gap:6px; margin-bottom:14px; }
.swb-day { border-radius:8px; padding:6px 4px; text-align:center; border:1px solid var(--border-color); display:flex; flex-direction:column; min-width:0; }
.swb-day small { font-size:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--text-muted); }
.swb-day.ok { background:var(--bg-green); border-color:var(--green-300, #86efac); }
.swb-day.missing { background:var(--bg-red); border-color:var(--red-300, #fca5a5); }
.swb-day.clash { background:var(--bg-orange); border-color:var(--orange-300, #fdba74); }
.swb-day.off { opacity:.55; }
.swb-addresses { display:grid; grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); gap:10px; margin-bottom:12px; }
.swb-address { display:flex; gap:10px; align-items:flex-start; padding:12px; border:1px solid var(--border-color); border-radius:10px; margin:0; cursor:pointer; font-weight:normal; }
.swb-address.on { border-color:var(--primary); }
.swb-address-body { flex:1; min-width:0; }
.swb-address-actions { display:flex; gap:12px; margin-top:8px; font-size:var(--text-sm, 13px); }
.swb-tag { font-size:10px; font-weight:500; padding:1px 6px; border-radius:4px; background:var(--bg-blue); color:var(--text-color); vertical-align:middle; }
.swb-mini-days { display:flex; gap:4px; margin-top:8px; }
.swb-mini-days span { font-size:10px; line-height:18px; width:24px; text-align:center; border-radius:4px; background:var(--control-bg); color:var(--text-light, var(--text-muted)); }
.swb-mini-days span.on { background:var(--bg-green); color:var(--text-color); font-weight:600; }
.swb-row { display:flex; justify-content:space-between; gap:12px; padding:5px 0; font-size:var(--text-sm, 13px); }
.swb-row span:first-child { color:var(--text-muted); }
.swb-row span:last-child { text-align:right; font-weight:500; overflow-wrap:anywhere; }
.swb-lines { width:100%; margin-top:10px; font-size:var(--text-sm, 13px); }
.swb-lines th { color:var(--text-muted); font-weight:500; border-bottom:1px solid var(--border-color); padding:4px 0; }
.swb-lines td { padding:4px 0; }
.swb-lines th:not(:first-child), .swb-lines td:not(:first-child) { text-align:right; }
.swb-total { display:flex; justify-content:space-between; border-top:1px solid var(--border-color); margin-top:6px; padding-top:8px; font-weight:600; font-size:var(--text-md, 14px); }
.swb-blockers { margin:12px 0; padding:10px 10px 10px 28px; border-radius:8px; background:var(--bg-orange); font-size:var(--text-sm, 13px); }
.swb-summary .btn-block { margin-top:12px; }
.swb-success { max-width:560px; margin:24px auto; padding:32px; text-align:center; }
.swb-success-icon { width:56px; height:56px; margin:0 auto 12px; border-radius:50%; display:flex; align-items:center; justify-content:center; background:var(--bg-green); color:var(--green-600, #16a34a); }
.swb-success-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:20px 0; text-align:left; }
.swb-success-grid div { padding:10px 12px; border-radius:8px; background:var(--control-bg); display:flex; flex-direction:column; }
.swb-success-grid small { color:var(--text-muted); }
.swb-phone { display:flex; align-items:stretch; }
.swb-phone > span { display:flex; align-items:center; padding:0 10px; border-radius:var(--border-radius, 6px) 0 0 var(--border-radius, 6px); background:var(--control-bg); border-right:1px solid var(--border-color); color:var(--text-muted); font-size:var(--text-sm, 13px); }
.swb-phone > input { border-top-left-radius:0; border-bottom-left-radius:0; }
.swb-link { display:flex; gap:8px; align-items:center; margin:0 0 16px; padding:6px 6px 6px 12px; border-radius:8px; background:var(--control-bg); }
.swb-link input { flex:1; min-width:0; border:0; background:transparent; color:var(--text-color); font-size:var(--text-sm, 13px); outline:none; }
.swb-success-actions { display:flex; gap:8px; justify-content:center; }
@media (max-width: 991px) {
	.swb { grid-template-columns:1fr; }
	.swb-side { position:static; }
	.swb-days small { display:none; }
}
`;
