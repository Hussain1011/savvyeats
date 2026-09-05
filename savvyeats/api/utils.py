import frappe

def split_current_and_upcoming(orders):
	"""Return (current, upcoming) for a customer's open Sales Orders.

	`current` is what every app version renders as "my subscription": Active, else
	Paused, else a blank/legacy status, else — when nothing has started yet — the
	Pending one. Cancelled and Completed subscriptions are never returned.
	`upcoming` is set only when a Pending renewal sits *behind* a distinct current
	order; old app builds have no Pending concept, so a lone Pending order must
	surface as `current` or it renders as an empty plan card.

	Shared by get_dashboard and get_current_subscription so the two cannot drift.
	"""
	active = paused = pending = other = None
	for o in orders:
		doc = frappe.get_doc("Sales Order", o.name, ignore_permissions=True)
		status = doc.subscription_status
		if status == "Active":
			active = active or doc
		elif status == "Paused":
			paused = paused or doc
		elif status == "Pending":
			pending = pending or doc
		elif status not in ("Cancelled", "Completed"):
			# Blank/unrecognised legacy status — pre-Issue-9 returned these as `order`,
			# so keep doing that. Cancelled and Completed are deliberately excluded:
			# a cancelled subscription must never resurface as the customer's plan.
			other = other or doc

	current = active or paused or other
	if current:
		return current, pending
	return pending, None

@frappe.whitelist(methods=["POST"])
def log_error(error):
	frappe.log_error(title="SavvyEats App Error", message=str(error))
	frappe.db.commit()

# --- MY WAY -----------------------------------------------------------------
# MY WAY is the build-your-own-meal plan: the customer assembles a plate from
# components (Protein / Carbs / ...) instead of picking a finished dish. It is
# identified by the plan's ui_type and is gated everywhere it diverges from the
# dish path, so dish plans keep their exact current behaviour.

MY_WAY_UI_TYPE = "My Way"


def is_my_way_plan(dish_plan):
	"""True when the Dish Plan is a MY WAY (build-your-own) plan.

	Gate every MY WAY divergence on this, never on the presence of a `grams` key:
	an old app build sending no grams must still take the dish path unchanged.
	"""
	if not dish_plan:
		return False

	return (frappe.db.get_value("Dish Plan", dish_plan, "ui_type") or "") == MY_WAY_UI_TYPE
