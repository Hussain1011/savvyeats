import frappe
import random
from frappe.utils import add_to_date, now_datetime, escape_html
from savvyeats.api.user import send_error_response, send_success_response

@frappe.whitelist(methods=["POST"], allow_guest=True)
def login(email: str, password: str):
	try:
		login_manager = frappe.auth.LoginManager()
		login_manager.authenticate(user=email, pwd=password)
		login_manager.post_login()
		user = frappe.get_doc('User', frappe.session.user)
		if not user.api_key:
			if not user.api_key:
				api_key = frappe.generate_hash(length=15)
				user.api_key = api_key
				api_secret = frappe.generate_hash(length=15)
				user.api_secret = api_secret
			user.save()

		api_secret = user.get_password("api_secret")

		employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user})
		if not employee:
			message_en = "Driver not found."
			message_ar = "لم يتم العثور على السائق."

			errors = {
				"not_found": ["Driver not found."]
			}
			return send_error_response(message_en, message_ar, errors)

		driver = frappe.db.get_value("Driver", {"employee": employee})
		if not driver:
			message_en = "Driver not found."
			message_ar = "لم يتم العثور على السائق."

			errors = {
				"not_found": ["Driver not found."]
			}
			return send_error_response(message_en, message_ar, errors)

		doc = frappe.get_doc("Driver", driver, ignore_permissions=True)

		message_en = "Login successful. Welcome back!"
		message_ar = "تم تسجيل الدخول بنجاح. مرحبًا بعودتك!"
		data={
			"api_key": user.api_key,
			"api_secret": api_secret,
			"doc": user,
			"driver": doc
		}
		return send_success_response(message_en, message_ar, data)

	except frappe.exceptions.SecurityException:
		message_en = "Your account has been locked for security reasons. Please try again in 5 minutes."
		message_ar = "تم قفل حسابك لأسباب أمنية. يرجى المحاولة مرة أخرى بعد 5 دقائق."
		errors = {
			"account_locked": ["Your account has been locked for security reasons. Please try again in 5 minutes."]
		}
		return send_error_response(message_en, message_ar, errors)

	except frappe.exceptions.AuthenticationError:
		message_en = "Authentication failed. Please check your credentials and try again."
		message_ar = "فشل التحقق من الهوية. يرجى التحقق من بيانات الدخول والمحاولة مرة أخرى."
		errors = {
			"authenticate_failed": ["Authentication failed. Please check your credentials and try again."]
		}
		return send_error_response(message_en, message_ar, errors)


