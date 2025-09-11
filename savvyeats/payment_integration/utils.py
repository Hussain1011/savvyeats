import frappe

def get_payment_gateway_url(doc, payment_gateway):
	payment_gateway = frappe.get_doc("Payment Gateway", payment_gateway, ignore_permission=True)
	gateway_settings = frappe.get_doc(payment_gateway.gateway_settings, payment_gateway.gateway_controller)
	return gateway_settings.generate_hash(doc, payment_gateway.name)