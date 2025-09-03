app_name = "savvyeats"
app_title = "SavvyEats"
app_publisher = "Nouman"
app_description = "ERPNext App for SavvyEats"
app_email = "nomi9639@yahoo.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "savvyeats",
# 		"logo": "/assets/savvyeats/logo.png",
# 		"title": "SavvyEats",
# 		"route": "/savvyeats",
# 		"has_permission": "savvyeats.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/savvyeats/css/savvyeats.css"
# app_include_js = "/assets/savvyeats/js/savvyeats.js"

# include js, css files in header of web template
# web_include_css = "/assets/savvyeats/css/savvyeats.css"
# web_include_js = "/assets/savvyeats/js/savvyeats.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "savvyeats/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Address" : "public/js/address_savvy_eats.js",
	"Sales Order" : "public/js/sales_order_savvy_eats.js"
}
doctype_list_js = {
	"Delivery Note" : "public/js/delivery_note_savvy_eats_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "savvyeats/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

website_route_rules = [
    {"from_route": "/pay/<order_id>", "to_route": "pay"},
    {"from_route": "/payment-response/<order_id>", "to_route": "payment-response"},
]

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "savvyeats.utils.jinja_methods",
# 	"filters": "savvyeats.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "savvyeats.install.before_install"
# after_install = "savvyeats.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "savvyeats.uninstall.before_uninstall"
# after_uninstall = "savvyeats.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "savvyeats.utils.before_app_install"
# after_app_install = "savvyeats.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "savvyeats.utils.before_app_uninstall"
# after_app_uninstall = "savvyeats.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "savvyeats.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Address": {
		"validate": "savvyeats.custom.address_savvyeats.validate"
	},
	"Sales Order": {
		"validate": "savvyeats.custom.sales_order_savvyeats.validate"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"savvyeats.background_jobs.remove_expired_otp"
	]
}

# Testing
# -------

# before_tests = "savvyeats.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "savvyeats.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "savvyeats.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["savvyeats.utils.before_request"]
# after_request = ["savvyeats.utils.after_request"]

# Job Events
# ----------
# before_job = ["savvyeats.utils.before_job"]
# after_job = ["savvyeats.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"savvyeats.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

