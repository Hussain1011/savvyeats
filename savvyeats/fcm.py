import json
import requests
import frappe

from google.oauth2 import service_account
from google.auth.transport.requests import Request


FCM_SCOPE = ["https://www.googleapis.com/auth/firebase.messaging"]


def _get_fcm_settings():
	# Change DocType/fieldnames to match your setup
	# Example DocType: "FCM Notification Settings"
	doc = frappe.get_single("FCM Notification Settings")

	# Credentials could be stored as:
	# - a Text field containing JSON
	# - or a File attachment URL
	creds = doc.get("credentials")

	if not creds:
		frappe.throw("FCM Credentials is empty in FCM Notification Settings.")

	# If it's a JSON string in the field:
	if isinstance(creds, str) and creds.strip().startswith("{"):
		creds_json = json.loads(creds)
		return creds_json

	# If it's a File URL, fetch the file content from File doctype
	# (common when using Attach / Attach Image fields)
	file_doc = frappe.get_doc("File", {"file_url": creds})
	if file_doc and file_doc.get_content():
		return json.loads(file_doc.get_content())

	# Another common way: read file from disk path - not recommended unless you manage paths carefully
	frappe.throw("Could not parse Credentials. Store full JSON in the field or ensure File content is available.")


def _get_access_token(creds_json: dict) -> str:
	credentials = service_account.Credentials.from_service_account_info(
		creds_json, scopes=FCM_SCOPE
	)
	credentials.refresh(Request())
	return credentials.token


def send_fcm_to_token(device_token: str, title: str, body: str, data: dict | None = None):
	"""
	Send push notification to a single device token using FCM HTTP v1.
	"""
	creds_json = _get_fcm_settings()
	project_id = creds_json.get("project_id")
	if not project_id:
		frappe.throw("project_id not found in Service Account JSON.")

	access_token = _get_access_token(creds_json)
	print("project_id:", creds_json.get("project_id"))
	print("client_email:", creds_json.get("client_email"))
	print("token_len:", len(access_token or ""))
	print("token_head:", (access_token or "")[:20])

	url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
	headers = {
		"Authorization": f"Bearer {access_token}",
		"Content-Type": "application/json; charset=UTF-8",
	}

	payload = {
		"message": {
			"token": device_token,
			"notification": {
				"title": title,
				"body": body,
			},
			# optional custom key/values your app can read
			"data": {k: str(v) for k, v in (data or {}).items()},
		}
	}

	r = requests.post(url, headers=headers, json=payload, timeout=20)

	if r.status_code >= 300:
		# Log full response for debugging
		frappe.log_error(title="FCM Send Failed", message=r.text)
		frappe.throw(f"FCM send failed: {r.status_code} - {r.text}")

	return r.json()


@frappe.whitelist()
def send_notification_to_user(user: str, title: str, body: str, data_json: str | None = None):
	"""
	Example: send to all device tokens for a given user.
	You must adapt token storage to your system.

	Assumption: you have a DocType like "User Device Token"
	with fields: user (Link User), token (Data)
	"""
	data = json.loads(data_json) if data_json else {}
	tokens = frappe.get_all("FCM Token",filters={"user": user}, fields=["token"])

	if not tokens:
		frappe.throw(f"No device tokens found for user: {user}")

	results = []
	for t in tokens:
		results.append(send_fcm_to_token(t.token, title, body, data=data))

	return results