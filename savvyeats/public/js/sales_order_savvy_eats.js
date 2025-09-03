frappe.ui.form.on('Sales Order', {
  refresh(frm) {
    if (!frm.is_new()) {
      frm.add_custom_button('Plan Meals', () => open_meal_dialog(frm)).addClass("btn-primary");
      frm.add_custom_button('Update Owner', function(){
        frm.trigger("update_owner");
      }).addClass("btn-primary");

    }
  },
  update_owner: function(frm){
    const d = new frappe.ui.Dialog({
      title: 'Update Owner',
      fields: [{
              "fieldtype": "Link",
              "fieldname": "owner",
              "label": __("Owner"),
              "options": "User",
              "reqd": 1
            }],
      primary_action_label: 'Update',
      primary_action(values) {
        frappe.call({
          method: "savvyeats.custom.sales_order_savvyeats.update_owner",
          args: {
            sales_order: frm.doc.name,
            owner: values.owner
          },
          freeze: true,
          callback: function(r){
            frm.reload_doc();
            d.hide();
          }
        })
      }
    });
    d.show();
  }
});
function open_meal_dialog(frm) {
  if (!Array.isArray(frm.doc.meals) || frm.doc.meals.length === 0) {
    frappe.msgprint(__('Please add rows to the "meals" child table first.'));
    return;
  }

  const fields = [
    { fieldtype: 'Date', fieldname: 'delivery_date', label: 'Date', reqd: 1 },
    { fieldtype: 'Section Break', label: 'Meals for this date' }
  ];

  frm.doc.meals.forEach((row, i) => {
    fields.push(
      {
        fieldtype: 'Link',
        fieldname: `meal_${row.name}`,
        label: row.meal || `Meal ${i + 1}`,
        options: 'Item',
        reqd: 1,
        get_query: () => ({
          filters: {
            disabled: 0,
          }
        })
      }
    );
  });

  const d = new frappe.ui.Dialog({
    title: 'Select Date & Meals (Items)',
    fields,
    primary_action_label: 'Add',
    primary_action(values) {
      const plan = [];
      frm.doc.meals.forEach(row => {
        const fn = `meal_${row.name}`;
        if (values[fn]) {
          plan.push({
            date: values.delivery_date,
            meal_label: row.meal,
            item: values[fn],
            child_row: row.name
          });
        }
      });

      if (!plan.length) {
        frappe.msgprint(__('Please pick at least one Item.'));
        return;
      }
      
      plan.forEach(p => {
        var doc = frm.add_child('items', {
          delivery_date: p.date,
          qty: 1,
          meal: p.meal_label
        });
        frappe.model.set_value(doc.doctype, doc.name, "item_code", p.item);
      });
      frm.refresh_field('items');
      
      frappe.show_alert({ message: __('Meal plan added'), indicator: 'green' });
      d.hide();

    }
  });

  d.show();
}
