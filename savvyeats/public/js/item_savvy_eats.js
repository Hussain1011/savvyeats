frappe.ui.form.on('Item', {
  refresh: function(frm){
    if(!frm.is_new() && ["Dish", "Sub Recipe"].includes(frm.doc.item_category)){
      frm.add_custom_button(__("Recipe"), function(){
        frm.trigger("load_recipe");
      }).addClass("btn-primary");
    }
  },
  load_recipe: function(frm) {
    frappe.call({
      "method": "savvyeats.custom.item_savvyeats.get_item_recipe",
      "args": {
        "item_id": frm.doc.name
      },
      callback: function(r){
        var doclist = frappe.model.sync(r.message);
        frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
      }
    })
  }
});