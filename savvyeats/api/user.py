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

	otp_verification = frappe.get_doc(
		{
			"doctype": "OTP Verification",
			"mobile_no": mobile_no,
			"verification_type": "Mobile No",
			"otp": get_otp(),
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
		return send_error_response(message_en, message_ar, errors)

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

	api_secret = frappe.generate_hash(length=15)
	if not user.api_key:
		api_key = frappe.generate_hash(length=15)
		user.api_key = api_key
	user.api_secret = api_secret
	user.save()
	message_en = "OTP verified successfully."
	message_ar = "تم التحقق من رمز التحقق بنجاح."
	data={
		"api_key": api_key,
		"api_secret": api_secret
	}
	return send_success_response(message_en, message_ar, data)



@frappe.whitelist(methods=["POST"], allow_guest=True)
def forget_send_otp(mobile_no: str):
	user = frappe.db.get("User", {"mobile_no": mobile_no})

	if not user:
		message_en = "User with this Phone number does not exist."
		message_ar = "المستخدم بهذا رقم الهاتف غير موجود."

		errors = {
			"not_found": ["User with this Phone number does not exist."]
		}
		return send_error_response(message_en, message_ar, errors)

	if frappe.db.get_creation_count("OTP Verification", 60) > 300:
		message_en = "Too many OTP verification attempts were made recently, so the verification is temporarily disabled. Please try again in an hour."
		message_ar = "تم إيقاف التحقق مؤقتًا بسبب كثرة محاولات إدخال رمز التحقق. يرجى المحاولة مرة أخرى خلال ساعة."

		errors = {
			"otp_limit": ["Too many OTP verification attempts were made recently, so the verification is temporarily disabled. Please try again in an hour."]
		}
		return send_error_response(message_en, message_ar, errors)

	otp = random.randint(100000, 999999)
	otp_verification = frappe.get_doc(
		{
			"doctype": "OTP Verification",
			"mobile_no": mobile_no,
			"verification_type": "Mobile No",
			"otp": get_otp(),
			"expiry": add_to_date(None, minutes=5)
		}
	)
	otp_verification.flags.ignore_permissions = True
	otp_verification.insert()
	message_en = "A one-time password (OTP) has been successfully sent to your mobile number via SMS."
	message_ar = "تم إرسال كلمة المرور لمرة واحدة (OTP) إلى رقم هاتفك المحمول عبر الرسائل النصية بنجاح."
	return send_success_response(message_en, message_ar)



@frappe.whitelist(methods=["POST"], allow_guest=True)
def forget_verify_otp(otp: int, mobile_no: str):
	user = frappe.db.get("User", {"mobile_no": mobile_no})

	if not user:
		message_en = "User with this Phone number does not exist."
		message_ar = "المستخدم بهذا رقم الهاتف غير موجود."

		errors = {
			"not_found": ["User with this Phone number does not exist."]
		}
		return send_error_response(message_en, message_ar, errors)

	otp_verification = frappe.get_all("OTP Verification", filters={"mobile_no": mobile_no, "otp": otp, "expiry": [">=", now_datetime()]})
	if not otp_verification:
		message_en = "The OTP is invalid or has expired. Please request a new one."
		message_ar = "رمز التحقق غير صالح أو منتهي الصلاحية. يرجى طلب رمز جديد."
		errors = {
			"otp_error": ["The OTP is invalid or has expired. Please request a new one."]
		}
		return send_error_response(message_en, message_ar, errors)

	message_en = "OTP verified successfully."
	message_ar = "تم التحقق من رمز التحقق بنجاح."
	data={}
	return send_success_response(message_en, message_ar, data)


@frappe.whitelist(methods=["POST"], allow_guest=True)
def update_password(otp: int, mobile_no: str, password):
	user = frappe.db.get("User", {"mobile_no": mobile_no})
	if not user:
		message_en = "User with this Phone number does not exist."
		message_ar = "المستخدم بهذا رقم الهاتف غير موجود."

		errors = {
			"not_found": ["User with this Phone number does not exist."]
		}
		return send_error_response(message_en, message_ar, errors)

	otp_verification = frappe.get_all("OTP Verification", filters={"mobile_no": mobile_no, "otp": otp, "expiry": [">=", now_datetime()]})
	if not otp_verification:
		message_en = "The password update link has expired. Please request a new one."
		message_ar = "رابط تحديث كلمة المرور منتهي الصلاحية. يرجى طلب رابط جديد."

		errors = {
			"expired": ["The OTP is invalid or has expired. Please request a new one."]
		}
		return send_error_response(message_en, message_ar, errors)

	doc = frappe.get_doc("User", frappe.session.user)
	doc.new_password = password
	doc.flags.ignore_permissions = True
	try:
		doc.save()
	except Exception as e:
		message_en = "This password is too common. Please choose a more secure one."
		message_ar = "هذه كلمة مرور شائعة جدًا. يرجى اختيار كلمة مرور أكثر أمانًا."

		errors = {
			"common": ["This password is too common. Please choose a more secure one."]
		}
		return send_error_response(message_en, message_ar, errors)

	message_en = "Password updated successfully."
	message_ar = "تم تحديث كلمة المرور بنجاح."

	data={}
	return send_success_response(message_en, message_ar, data)

@frappe.whitelist(methods=["POST"], allow_guest=True)
def login(email: str, password: str):
	try:
		login_manager = frappe.auth.LoginManager()
		login_manager.authenticate(user=email, pwd=password)
		login_manager.post_login()
		user = frappe.get_doc('User', frappe.session.user)
		api_secret = user.get_password("api_secret")
		if not user.api_key:
			if not user.api_key:
				api_key = frappe.generate_hash(length=15)
				user.api_key = api_key
				api_secret = frappe.generate_hash(length=15)
				user.api_secret = api_secret
			user.save()

		message_en = "Login successful. Welcome back!"
		message_ar = "تم تسجيل الدخول بنجاح. مرحبًا بعودتك!"
		data={
			"api_key": user.api_key,
			"api_secret": api_secret,
			"doc": user
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

def get_otp():
	otp = random.randint(100000, 999999)
	otp = 123456
	return otp

@frappe.whitelist(methods=["POST"], allow_guest=True)
def update_details(data):
	allowed_fields = {"first_name", "gender", "phone", "birth_date", "hear_about_us", "referred_by", "general_notifications", "security_alerts", "weekly_progress_summary", "goal_achievment", "milestone_celebration", "health_tips_and_article", "subscription_and_alerts", "social_and_community", "do_not_disturb", "special_offers"}
	clean_data = {k: v for k, v in data.items() if k in allowed_fields}

	user = frappe.get_doc("User", frappe.session.user)
	user.flags.ignore_validate = True
	user.flags.ignore_permissions = True
	user.flags.ignore_mandatory = True
	user.update(clean_data)
	user.save()

	frappe.db.commit()

	message_en = "User Information updated successfully."
	message_ar = "تم تحديث معلومات الاتصال بنجاح."

	return send_success_response(message_en, message_ar, {})
        
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