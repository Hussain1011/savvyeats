frappe.ui.form.on('Sales Order', {
  refresh(frm) {
    frm.add_custom_button("Add Meals", function() {
        frm.trigger("add_meals");
    }, __("Dish Plan Meals"));
    if (!frm.is_new()) {
      // frm.add_custom_button('Plan Meals', () => open_meal_dialog(frm)).addClass("btn-primary");

      frm.add_custom_button("Update Meals", function() {
        
      }, __("Dish Plan Meals"));

      frm.add_custom_button('Update Owner', function(){
        frm.trigger("update_owner");
      }).addClass("btn-primary");
    }
  },
  add_meals: function(frm){
      if(!frm.doc.start_date || !frm.doc.dish_plan || !frm.doc.dish_plan_pricing || !frm.doc.period_count || !frm.doc.week_plan || frm.doc.meals.length == 0 || !frm.doc.customer){
        frappe.throw(__("To add Items : Customer, Dish Plan, Dish Plan Pricing, Meals, Period Count, Week Plan and Start Date is Mandatory"));
        return;
      }
      frm.call({
        method: "savvyeats.custom.sales_order_savvyeats.get_delivery_dates",
        args: {
          doc: frm.doc
        },
        freeze: true,
        callback: function(r){
          frappe.model.sync(r.message);
          frm.refresh_fields();
          frappe.db.get_doc("Dish Plan Pricing", frm.doc.dish_plan_pricing).then(doc => {
            frm.dish_plan_pricing = doc;
            open_meal_dialog(frm);
          });
        }
      });
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
  const delivery_dates = (frm.doc.delivery_dates || [])
    .map(r => r["delivery_date"])
    .filter(Boolean);

  const meal_options = (frm.doc.meals || [])
    .map(r => r["meal"])
    .filter(Boolean);

  if (!delivery_dates.length) {
    frappe.msgprint(__('Please select Start Date first.'));
    return;
  }
  if (!meal_options.length) {
    frappe.msgprint(__('Please select Meals First'));
    return;
  }

  const d = new frappe.ui.Dialog({
    title: __('Add Meal Items'),
    size: 'extra-large',
    fields: [
      {
        fieldtype: 'Select',
        label: __('Date'),
        reqd: 1,
        fieldname: 'delivery_date',
        options: [''].concat(unique(delivery_dates)).join('\n')
      },
      { fieldtype: 'Column Break' },
      { fieldtype: 'Column Break' },
      { fieldtype: 'Section Break' },
      {
        fieldtype: 'Table',
        label: __('Plan'),
        fieldname: 'plan',
        cannot_add_rows: 0,
        in_place_edit: true,
        data: [],
        fields: [
          {
            fieldtype: 'Select',
            fieldname: 'meal',
            label: __('Meal'),
            options: [''].concat(unique(meal_options)).join('\n'),
            in_list_view: 1,
            reqd: 1
          },
          {
            fieldtype: 'Link',
            fieldname: 'item_code',
            label: __('Item'),
            options: 'Item',
            in_list_view: 1,
            reqd: 1
          },
          {
            fieldtype: 'Float',
            fieldname: 'qty',
            label: __('Qty'),
            in_list_view: 1,
            reqd: 1,
            default: 1
          },
          {
            fieldtype: 'Check',
            fieldname: 'extra_portion',
            label: __('Extra Portion'),
            in_list_view: 1,
            default: 0
          },
          {
            fieldtype: 'Small Text',
            fieldname: 'note',
            label: __('Note'),
            in_list_view: 1,
          }
        ]
      }
    ],
    primary_action_label: __('Add to Items'),
    primary_action: (values) => {
      if (!values.delivery_date) {
        frappe.msgprint(__('Please select a Date'));
        return;
      }
      const rows = values.plan || [];
      if (!rows.length) {
        frappe.msgprint(__('Add at least one row to the table.'));
        return;
      }

      var meals = [];
      var all_meals = frm.doc.meals.map(item => item.meal);
      var add_meals = rows.map(item => item.meal);
      var allPresent = all_meals.every(meal => add_meals.includes(meal));

      const meal_prices = frm.dish_plan_pricing.meals.reduce((acc, item) => {
        acc[item.meal] = item.per_day_price;
        return acc;
      }, {});

      if(!allPresent){
        frappe.throw(__("All Meals must be selected for the Date."));
      }
      frm.doc.items.forEach( i => {
        if(i.delivery_date == values.delivery_date){
          frappe.throw(__("Items Already added for Delivery Date."));
        }
        if (meals.includes(i.meal)){
          frappe.throw(__("Only 1 Item Per Meal is Allowed"));
        }
      });

      rows.forEach(r => {
        const child = frm.add_child('items');
        frappe.model.set_value(child.doctype, child.name, 'item_code', r.item_code);
        frappe.model.set_value(child.doctype, child.name, 'qty', r.qty || 1);
        frappe.model.set_value(child.doctype, child.name, 'delivery_date', values.delivery_date);
        frappe.model.set_value(child.doctype, child.name, 'rate', meal_prices[r.meal]);
        frappe.model.set_value(child.doctype, child.name, "meal", r.meal);
        frappe.model.set_value(child.doctype, child.name, "extra_portion", r.extra_portion ? 1 : 0);
        frappe.model.set_value(child.doctype, child.name, "note", r.note);
      });

      frm.refresh_field('items');
      d.hide();
    }
  });

  const grid = d.fields_dict.plan.grid;
  d.get_field('delivery_date').$input.on('change', () => {
    (grid.grid_rows || []).forEach(r => {
      try { frappe.model.set_value(r.doc.doctype, r.doc.name, 'item_code', ''); } catch(e) {}
    });
    grid.refresh();
  });
  grid.get_field('item_code').get_query = function (doc, cdt, cdn) {
    const row = doc;
    const selected_date = d.get_value('delivery_date');
    if(!selected_date){
      frappe.throw(__("Select Date First."));
    }
    if(!row.meal){
      frappe.throw(__("Select Meal in the row First."));
    }
    return {
      query: 'savvyeats.custom.sales_order_savvyeats.item_query',
      filters: {
        meal: row.meal,
        available_on: selected_date,
        dish_plan: frm.doc.dish_plan,
        status: "Published"
      }
    };
  };

  d.show();
}

function unique(a) {
  return [...new Set(a)];
}


