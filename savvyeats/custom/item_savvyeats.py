import frappe

@frappe.whitelist()
def get_item_recipe(item_id):
	boms = frappe.get_all("BOM", filters={"item": item_id, "is_default": 1, "is_active": 1})
	if boms:
		return frappe.get_doc("BOM", boms[0].name)

	doc = frappe.new_doc("BOM")
	doc.item = item_id
	doc.quantity = 1
	doc.gross_quantity = 1
	doc.is_active = 1
	doc.is_default = 1
	doc.set_rate_of_sub_assembly_item_based_on_bom = 1

	return doc