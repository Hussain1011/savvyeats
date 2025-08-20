// Copyright (c) 2025, Nouman and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dish Schedule", {
	refresh(frm) {
		frm.add_custom_button(__("Add Dish"), function(){
			frm.trigger("add_dish");
		}).addClass("btn-primary");

        if(!frm.doc.__islocal){
            frm.add_custom_button(__("Publish"), function(){
                frm.trigger("publish_schedule");
            }).addClass("btn-warning");
        }


		frm.set_query("item_code", "items", function(doc, cdt, cdn) {
			var cdoc = locals[cdt][cdn];
			if (!cdoc.dish_plan){
				frappe.throw(__("Select Dish Plan First"))
			}
			filters = [["Item","item_category", "=", "Dish"]]
			if (cdoc.dish_plan){
				filters.push(["Item Dish Plans","dish_plan", "=", cdoc.dish_plan])
			}
			return {
				 "filters": filters
			}
		});
		render_meal_groups(frm);
	},


    publish_schedule: function(frm){
        frappe.call({
            method: "savvyeats.savvyeats.doctype.dish_schedule.dish_schedule.publish_dish_schedule",
            args: {
                dish_schedule_id:frm.doc.name
            },
            freeze: true,
            callback: function(r){
                frm.reload_doc();
            }
        });
    },


	add_dish: function(frm) {
		let d = new frappe.ui.Dialog({
            title: 'Select Dish',
            fields: [
                {
                    fieldname: 'meal',
                    label: 'Meal',
                    fieldtype: 'Link',
                    options: 'Meal',
                    reqd: 1
                },
                {
                    fieldname: 'item',
                    label: 'Items',
                    fieldtype: 'MultiSelectList',
                    reqd: 1,
                    description: __("First Selected Item is the Default Item."),
                    get_data: function (txt) {
                        return frappe.db.get_link_options('Item', txt, {
                            item_category: 'Dish',
                            has_variants: 1
                        });
                    }
                }
            ],
            primary_action_label: 'Add',
            primary_action(values) {
                if (!values.meal || !values.item || values.item.length === 0) {
                    frappe.msgprint(__('Please fill all mandatory fields.'));
                    return;
                }

                const selections = Array.isArray(values.item)
                    ? values.item.map(x => (typeof x === 'string' ? x : x.value))
                    : String(values.item).split(',').map(s => s.trim()).filter(Boolean);

                frm.call({
                    method: "add_items", 
                    doc: frm.doc,
                    args: {
                        meal: values.meal,
                        items: selections
                    },
                    freeze: true,
                    callback: function(r){
                        frm.reload_doc();
                    }
                });

                frm.refresh_fields();
                d.hide();
            }
        });


        d.show();
	}
});

function render_meal_groups(frm) {
    let wrapper = frm.fields_dict['html'].wrapper; // replace with your HTML fieldname
    $(wrapper).empty(); // clear previous content

    if (!frm.doc.items || frm.doc.items.length === 0) {
        $(wrapper).html('<p>No items added yet.</p>');
        return;
    }

    // Group child table entries by meal
    let grouped = {};
    frm.doc.items.forEach(row => {
        if (!grouped[row.meal]) {
            grouped[row.meal] = [];
        }
        grouped[row.meal].push(row);
    });

    // Build HTML
    let html = `<div class="meal-groups">`;
    Object.keys(grouped).forEach(meal => {
        html += `
        <div class="meal-group">
            <div class="meal-header" style="cursor:pointer; font-weight:bold; padding:5px; background:#f0f0f0; border:1px solid #ddd;">
                ${meal}
            </div>
            <div class="meal-items" style="display:none; padding:5px; border:1px solid #ddd; border-top:none;">
                <ul>
                    ${grouped[meal].map(row => `<li>${row.item_name} (${row.dish_plan})</li>`).join('')}
                </ul>
            </div>
        </div>
        `;
    });
    html += `</div>`;

    $(wrapper).html(html);

    // Collapsible toggle
    $(wrapper).find('.meal-header').on('click', function() {
        $(this).next('.meal-items').slideToggle();
    });
}

