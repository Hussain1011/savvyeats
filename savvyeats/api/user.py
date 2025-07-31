import frappe
import random
from frappe.utils import add_to_date, now_datetime, escape_html


@frappe.whitelist(methods=["POST"], allow_guest=True)
def send_otp(email: str, mobile_no: str):
	user = frappe.db.get("User", {"email": email})
	if user:
		message_en = "An account with this email already exists."
		message_ar = "يوجد حساب بهذا البريد الإلكتروني بالفعل."
		errors = {
			"email_exists": ["An account with this email already exists."]
		}
		return send_error_response(message_en, message_ar, errors)


	user = frappe.db.get("User", {"mobile_no": mobile_no})
	if user:
		message_en = "An account with this mobile number already exists."
		message_ar = "يوجد حساب بهذا رقم الجوال بالفعل."
		errors = {
			"mobile_no_exists": ["An account with this mobile number already exists."]
		}
		return send_error_response(message_en, message_ar, errors)

	if frappe.db.get_creation_count("OTP Verification", 60) > 300:
		message_en = "Too many users signed up recently, so the registration is temporarily disabled. Please try again in an hour."
		message_ar = "تم إيقاف التسجيل مؤقتًا بسبب كثرة المستخدمين الجدد. يرجى المحاولة مرة أخرى خلال ساعة."
		errors = {
			"singup_limit": ["Too many users signed up recently, so the registration is temporarily disabled. Please try again in an hour."]
		}
		return send_error_response(message_en, message_ar, errors)
	otp = random.randint(100000, 999999)
	otp_verification = frappe.get_doc(
		{
			"doctype": "OTP Verification",
			"mobile_no": mobile_no,
			"verification_type": "Mobile No",
			"otp": 123456,
			"expiry": add_to_date(None, minutes=5)
		}
	)
	otp_verification.flags.ignore_permissions = True
	otp_verification.insert()
	message_en = "A one-time password (OTP) has been successfully sent to your mobile number via SMS."
	message_ar = "تم إرسال كلمة المرور لمرة واحدة (OTP) إلى رقم هاتفك المحمول عبر الرسائل النصية بنجاح."
	return send_success_response(message_en, message_ar)



@frappe.whitelist(methods=["POST"], allow_guest=True)
def verify_otp(otp: int, email: str, mobile_no: str, full_name: str, password: str):
	user = frappe.db.get("User", {"email": email})
	if user:
		message_en = "An account with this email already exists."
		message_ar = "يوجد حساب بهذا البريد الإلكتروني بالفعل."
		errors = {
			"email_exists": ["An account with this email already exists."]
		}
		return send_error_response(message_en, message_ar, errors)


	user = frappe.db.get("User", {"mobile_no": mobile_no})
	if user:
		message_en = "An account with this mobile number already exists."
		message_ar = "يوجد حساب بهذا رقم الجوال بالفعل."
		errors = {
			"mobile_no_exists": ["An account with this mobile number already exists."]
		}
		frappe.response["message"] = send_error_response(message_en, message_ar, errors)

	otp_verification = frappe.get_all("OTP Verification", filters={"mobile_no": mobile_no, "otp": otp, "expiry": [">=", now_datetime()]})
	if not otp_verification:
		message_en = "The OTP is invalid or has expired. Please request a new one."
		message_ar = "رمز التحقق غير صالح أو منتهي الصلاحية. يرجى طلب رمز جديد."
		errors = {
			"otp_error": ["The OTP is invalid or has expired. Please request a new one."]
		}
		return send_error_response(message_en, message_ar, errors)

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"mobile_no": mobile_no,
			"mobile_verified": 1,
			"first_name": escape_html(full_name),
			"enabled": 1,
			"new_password": password,
			"user_type": "Website User",
			"send_welcome_email": 0
		}
	)
	user.flags.ignore_permissions = True
	user.flags.ignore_password_policy = True
	user.insert()

	message_en = "OTP verified successfully."
	message_ar = "تم التحقق من رمز التحقق بنجاح."
	return send_success_response(message_en, message_ar)




def send_error_response(message_en, message_ar, errors, code=417):
	return {
		"status": "error",
		"message_en": message_en,
		"message_ar": message_ar,
		"errors": errors,
		"code" : 417
	}

def send_success_response(message_en, message_ar, data={}):
	return {
		"status": "success",
		"message_en": message_en,
		"message_ar": message_ar,
		"data": data
	}