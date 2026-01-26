// Copyright (c) 2025, Nouman and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dish Schedule", {
	refresh(frm) {
        if(!frm.is_new()){
            frm.add_custom_button(__("Add Dish"), function(){
                frm.trigger("add_dish");
            }).addClass("btn-primary");
        }

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
                            variant_of: ""
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
    const wrapper = frm.fields_dict['html'].wrapper;
    $(wrapper).empty();
    inject_ds_compact_styles_once();

    const items = frm.doc.items || [];
    if (!items.length) {
        $(wrapper).html(`<div class="ds-empty">No items added yet.</div>`);
        return;
    }

    const esc = (v) => frappe.utils.escape_html(v ?? "");

    // ---------- Sort helpers ----------
    const numOrBig = (v) => (v === 0 || v) ? Number(v) : 999999;

    // ---------- Collect dish_plan_types ----------
    const typeSet = new Set(items.map(r => (r.dish_plan_type || "Other").trim()));
    let types = Array.from(typeSet);

    // Standard SAVVY must be first + default
    const DEFAULT_TYPE = "Standard SAVVY";
    types.sort((a, b) => {
        if (a === DEFAULT_TYPE && b !== DEFAULT_TYPE) return -1;
        if (b === DEFAULT_TYPE && a !== DEFAULT_TYPE) return 1;
        return a.localeCompare(b);
    });

    // ---------- Render tabs shell ----------
    let html = `
      <div class="ds-wrap">
        <div class="ds-tabs">
          ${types.map((t, idx) => `
            <button type="button"
              class="ds-tab ${t === DEFAULT_TYPE ? "is-active" : ""}"
              data-type="${esc(t)}"
              data-type-raw="${esc(t)}">
              ${esc(t)}
            </button>
          `).join("")}
        </div>

        <div class="ds-panels">
          ${types.map((t, idx) => `
            <div class="ds-panel ${t === DEFAULT_TYPE ? "is-active" : ""}" data-type="${esc(t)}">
              ${renderTypePanel(t)}
            </div>
          `).join("")}
        </div>
      </div>
    `;

    $(wrapper).html(html);

    // ---------- Tab click ----------
    $(wrapper).find(".ds-tab").off("click").on("click", function () {
        const type = $(this).attr("data-type-raw");

        $(wrapper).find(".ds-tab").removeClass("is-active");
        $(this).addClass("is-active");

        $(wrapper).find(".ds-panel").removeClass("is-active");
        $(wrapper).find(`.ds-panel[data-type="${CSS.escape(type)}"]`).addClass("is-active");
    });

    // ---------- Collapse toggle inside current panel ----------
    $(wrapper).find(".ds-card-head").off("click").on("click", function () {
        const id = $(this).data("target");
        const $panel = $(this).closest(".ds-panel");
        const $body = $panel.find("#" + id);
        const $caret = $(this).find(".ds-caret");

        $body.stop(true, true).slideToggle(130);
        $caret.toggleClass("rot");
    });

    // ---------- Panel renderer (per dish_plan_type) ----------
    function renderTypePanel(typeName) {
        const filtered = items.filter(r => ((r.dish_plan_type || "Other").trim() === typeName.trim()));

        if (!filtered.length) {
            return `<div class="ds-empty">No items in ${esc(typeName)}.</div>`;
        }

        // Grouping: meal -> dish_plan -> rows
        const grouped = {};
        filtered.forEach(r => {
            const meal = r.meal || "Unassigned";
            const plan = r.dish_plan || "Unknown";
            grouped[meal] = grouped[meal] || {};
            grouped[meal][plan] = grouped[meal][plan] || [];
            grouped[meal][plan].push(r);
        });

        // Sort meals by meal_sort (min of rows), then by name
        const meals = Object.keys(grouped).sort((a, b) => {
            const aMin = minSortForMeal(a);
            const bMin = minSortForMeal(b);
            if (aMin !== bMin) return aMin - bMin;
            return a.localeCompare(b);
        });

        function minSortForMeal(mealName) {
            const plans = grouped[mealName];
            let min = 999999;
            Object.values(plans).forEach(rows => {
                rows.forEach(r => { min = Math.min(min, numOrBig(r.meal_sort)); });
            });
            return min;
        }

        // Render meal cards (ALL collapsed)
        let out = `<div class="ds-list-col">`;

        meals.forEach((meal, mi) => {
            const plansObj = grouped[meal];

            // counts
            const mealCount = Object.values(plansObj).reduce((sum, rows) => sum + rows.length, 0);
            const defaultCount = Object.values(plansObj).reduce((sum, rows) => sum + rows.filter(r => Number(r.default) === 1).length, 0);

            // unique id per panel+meal to avoid collisions
            const bodyId = `ds-body-${slug(typeName)}-${mi}`;

            out += `
              <section class="ds-card">
                <button type="button" class="ds-card-head" data-target="${bodyId}">
                  <div class="ds-head-left">
                    <div class="ds-meal">${esc(meal)}</div>
                    <div class="ds-meta">
                      <span>${mealCount}</span>
                      ${defaultCount ? `<span class="ds-dot">•</span><span class="ds-default-hint">${defaultCount} default</span>` : ``}
                    </div>
                  </div>
                  <div class="ds-head-right">
                    <span class="ds-caret">⌄</span>
                  </div>
                </button>

                <div class="ds-card-body" id="${bodyId}" style="display:none">
                  ${renderPlans(plansObj)}
                </div>
              </section>
            `;
        });

        out += `</div>`;
        return out;

        // Sort dish plans by dish_plan_sort (min of rows), then by name
        function renderPlans(plansObj) {
            const plans = Object.keys(plansObj).sort((a, b) => {
                const aMin = minSortForPlan(a);
                const bMin = minSortForPlan(b);
                if (aMin !== bMin) return aMin - bMin;
                return a.localeCompare(b);
            });

            function minSortForPlan(planName) {
                const rows = plansObj[planName] || [];
                let min = 999999;
                rows.forEach(r => { min = Math.min(min, numOrBig(r.dish_plan_sort)); });
                return min;
            }

            return plans.map(plan => {
                const rows = (plansObj[plan] || []).slice();

                // Optional: keep row order stable by idx (or item_name)
                rows.sort((x, y) => (Number(x.idx || 0) - Number(y.idx || 0)));

                const planClass = planClassName(plan);

                return `
                  <div class="ds-plan">
                    <div class="ds-plan-head">
                      <span class="ds-plan-badge ${planClass}">${esc(plan)}</span>
                      <span class="ds-plan-count">${rows.length}</span>
                    </div>

                    <ul class="ds-list">
                      ${rows.map(r => {
                        const isDef = Number(r.default) === 1;
                        return `
                          <li class="ds-item ${isDef ? "is-default" : ""}">
                            <div class="ds-item-main">
                              <div class="ds-item-title">${esc(r.item_name)}</div>
                              <div class="ds-item-sub">${esc(r.item_code || "")}</div>
                            </div>
                            ${isDef ? `<span class="ds-default-tag">Default</span>` : ``}
                          </li>
                        `;
                      }).join("")}
                    </ul>
                  </div>
                `;
            }).join("");
        }
    }

    function planClassName(plan) {
        const p = (plan || "").toLowerCase();
        if (p.includes("full")) return "full";
        if (p.includes("lo")) return "lo";
        if (p.includes("opti")) return "opti";
        return "unk";
    }

    function slug(s) {
        return String(s || "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/(^-|-$)/g, "");
    }
}

function inject_ds_compact_styles_once() {
    if (document.getElementById("ds-compact-styles")) return;

    const css = `
    .ds-wrap{ padding: 4px 0; }

    /* Tabs */
    .ds-tabs{
        display:flex;
        gap: 6px;
        flex-wrap: wrap;
        padding: 0 2px 8px 2px;
        border-bottom: 1px solid rgba(15,23,42,.08);
        margin-bottom: 8px;
    }

    .ds-tab{
        border: 1px solid rgba(15,23,42,.10);
        background: rgba(15,23,42,.03);
        color: rgba(15,23,42,.85);
        padding: 5px 10px;
        border-radius: 999px;
        font-weight: 800;
        font-size: 12px;
        cursor: pointer;
        line-height: 1.1;
    }

    .ds-tab.is-active{
        background: rgba(37,99,235,.10);
        border-color: rgba(37,99,235,.22);
        color: rgba(30,64,175,1);
    }

    .ds-panel{ display:none; }
    .ds-panel.is-active{ display:block; }

    /* Full width column list */
    .ds-list-col{
        display:flex;
        flex-direction: column;
        gap: 8px;            /* smaller gap */
        width: 100%;
    }

    .ds-card{
        width: 100%;
        background:#fff;
        border:1px solid rgba(15,23,42,.10);
        border-radius: 12px;
        overflow:hidden;
        box-shadow: 0 6px 14px rgba(2,6,23,.05);
    }

    .ds-card-head{
        width:100%;
        border:0;
        background: #fff;
        padding: 8px 10px;   /* compact */
        cursor:pointer;
        display:flex;
        align-items:center;
        justify-content:space-between;
        text-align:left;
    }

    .ds-meal{
        font-weight: 900;
        font-size: 13px;
        color:#0f172a;
    }

    .ds-meta{
        margin-top: 2px;
        font-size: 11px;
        color: rgba(15,23,42,.60);
        display:flex;
        align-items:center;
        gap: 6px;
    }

    .ds-dot{ opacity:.55; }
    .ds-default-hint{ color: rgba(37,99,235,.95); font-weight: 800; }

    .ds-caret{
        font-size: 15px;
        color: rgba(15,23,42,.55);
        transition: transform 140ms ease;
        line-height:1;
    }
    .ds-caret.rot{ transform: rotate(180deg); }

    .ds-card-body{
        padding: 8px 10px 10px 10px; /* compact */
        background: rgba(2,6,23,.015);
        border-top: 1px solid rgba(15,23,42,.06);
    }

    .ds-plan{ margin-top: 8px; }
    .ds-plan:first-child{ margin-top: 0; }

    .ds-plan-head{
        display:flex;
        align-items:center;
        justify-content:space-between;
        margin-bottom: 6px;
    }

    .ds-plan-badge{
        font-size: 11px;
        font-weight: 900;
        padding: 4px 9px;
        border-radius: 999px;
        border: 1px solid rgba(15,23,42,.10);
        background: #fff;
        color:#0f172a;
    }

    .ds-plan-badge.full{ border-color: rgba(16,185,129,.25); background: rgba(16,185,129,.10); color: rgba(6,95,70,1); }
    .ds-plan-badge.lo{ border-color: rgba(245,158,11,.28); background: rgba(245,158,11,.12); color: rgba(146,64,14,1); }
    .ds-plan-badge.opti{ border-color: rgba(139,92,246,.25); background: rgba(139,92,246,.12); color: rgba(91,33,182,1); }
    .ds-plan-badge.unk{ border-color: rgba(148,163,184,.40); background: rgba(148,163,184,.14); color: rgba(30,41,59,1); }

    .ds-plan-count{
        font-size: 11px;
        font-weight: 900;
        color: rgba(15,23,42,.55);
    }

    .ds-list{
        list-style:none;
        padding:0;
        margin:0;
        display:grid;
        gap: 6px; /* compact */
    }

    .ds-item{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap: 8px;
        padding: 8px 9px;   /* compact */
        border-radius: 10px;
        border: 1px solid rgba(15,23,42,.08);
        background: #fff;
    }

    .ds-item.is-default{
        border-color: rgba(37,99,235,.25);
        background: rgba(37,99,235,.06);
    }

    .ds-item-title{
        font-size: 12px;
        font-weight: 900;
        color:#0f172a;
        line-height: 1.15;
    }

    .ds-item-sub{
        font-size: 11px;
        color: rgba(15,23,42,.55);
        margin-top: 2px;
        line-height: 1.1;
    }

    .ds-default-tag{
        font-size: 11px;
        font-weight: 900;
        padding: 3px 8px;
        border-radius: 999px;
        background: rgba(37,99,235,.12);
        border: 1px solid rgba(37,99,235,.22);
        color: rgba(30,64,175,1);
        white-space:nowrap;
        line-height: 1.1;
    }

    .ds-empty{
        padding: 10px 10px;
        border-radius: 12px;
        border: 1px dashed rgba(15,23,42,.18);
        background: rgba(2,132,199,.05);
        font-weight: 900;
        font-size: 12px;
        color:#0f172a;
    }
    `;

    const style = document.createElement("style");
    style.id = "ds-compact-styles";
    style.innerHTML = css;
    document.head.appendChild(style);
}


