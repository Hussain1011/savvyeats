frappe.listview_settings['Payment Log'] = {
    add_fields: ["title", "decision", "payment_updated", "auth_amount"],
    hide_name_column: true,
    get_indicator: function(doc) {
        if (doc.decision === "ACCEPT") {
            return [__("ACCEPT"), "green", "status,=,ACCEPT"];
        } else if (doc.decision === "ERROR") {
            return [__("ERROR"), "red", "status,=,ERROR"];
        }
    }
};