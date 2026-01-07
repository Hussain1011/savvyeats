// Copyright (c) 2025, Nouman and contributors
// For license information, please see license.txt

frappe.ui.form.on("Subscription Delivery", {
	refresh(frm) {
		if(!frm.is_new()){
			frm.toggle_enable(["delivery_date"], 0);
			console.log(frm.doc.items.length);
			// if(frm.doc.items.length > 0 && frm.doc.status == "Pending"){
			// 	frm.add_custom_button(__("Lock Delivery"), function(){
			// 		frm.trigger("lock_delivery");
			// 	});
			// }
      if(frm.doc.items.length == 0){
			 frm.add_custom_button(__("Fetch Deliveries"), function(){
				  frm.trigger("fetch_deliveries");
			 }).addClass("btn-warning");
      }
		  render_deliveries_section(frm);
		}
	},
	fetch_deliveries: function(frm){
		frm.call({
			method: "fetch_deliveries",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Fetching Deliveries"),
			callback: function(r){
				frm.refresh_field("items");
				frm.dirty();
				frm.save();
			}
		})
	},
	lock_delivery: function(frm){
		frappe.confirm(`Are you sure you want to lock deliveries for ${frm.get_formatted("delivery_date")}?`, () => {
			frm.call({
				method: "lock_delivery",
				doc: frm.doc,
				freeze: true,
				freeze_message: __("Locking Deliveries"),
				callback: function(r){
					frm.reload_doc();
				}
			})
		}, () => {
			
		});
	}
});

function render_deliveries_section(frm) {
  const html_field = frm.fields_dict['deliveries_section'];
  if (!html_field || !html_field.$wrapper) return;

  const items = (frm.doc.items || []).slice();
  const MEAL_ORDER = ['Breakfast','Meals', 'Snacks','Add-ons'];

  // -------- Aggregations --------
  const by_so = {};
  const dn_by_so = {};
  const unique_users = new Set();
  const meal_counts = { 'Breakfast':0,'Meals':0,'Snacks':0, 'Add-ons':0 };

  for (const it of items) {
    if (it.customer) unique_users.add(it.customer);
    const meal = (it.meal && String(it.meal).trim()) ? String(it.meal).trim() : 'Add-ons';
    if (meal_counts[meal] == null) meal_counts[meal] = 0;
    meal_counts[meal] += 1;

    const so = it.sales_order || 'No Sales Order';
    by_so[so] = by_so[so] || {};
    by_so[so][meal] = by_so[so][meal] || [];
    by_so[so][meal].push(it);

    dn_by_so[so] = dn_by_so[so] || new Set();
    if (it.delivery_note) dn_by_so[so].add(it.delivery_note);
  }

  const total_meal_items = meal_counts['Breakfast'] + meal_counts['Meals'] + meal_counts['Snacks'];
  const total_addons = meal_counts['Add-ons'];
  const total_users = unique_users.size;

  // -------- UI Build --------
  const acc_id = `delivery-accordion-${frappe.dom.get_unique_id()}`;
  let html = `
    <div class="delivery-summary mb-3">
      <div class="row">
        ${summaryCard('👥 Total Users', total_users, 'users')}
        ${summaryCard('🍽️ Total Dishes (Meals)', total_meal_items, 'meals')}
        ${summaryCard('➕ Total Add-ons', total_addons, 'addons')}
      </div>
      <div class="row mt-2">
        ${MEAL_ORDER.map(m => quickPill(m, meal_counts[m] || 0)).join('')}
      </div>
    </div>

    <div class="delivery-accordion" id="${acc_id}">
  `;

  let so_index = 0;
  for (const so of Object.keys(by_so)) {
    const card_id = `so-${frappe.dom.get_unique_id()}`;
    const item_count = Object.values(by_so[so]).flat().length;

    const dn_list = Array.from(dn_by_so[so] || []);
    const dnPills = dn_list.length
      ? dn_list.map(dn =>
          `<a href="javascript:void(0)" class="btn btn-sm btn-outline-secondary ml-2 js-route btn-chip"
              data-doctype="Delivery Note" data-name="${frappe.utils.escape_html(dn)}">
              <span class="chip-dot"></span> ${frappe.utils.escape_html(dn)}
           </a>`
        ).join('')
      : '';

    const soBtn = (so !== 'No Sales Order')
      ? `<a href="javascript:void(0)" class="btn btn-sm btn-primary js-route elevate"
            data-doctype="Sales Order" data-name="${frappe.utils.escape_html(so)}">
            🔎 View Sales Order
         </a>`
      : '';

    html += `
      <div class="card mb-4 border-0 elevate">
        <div class="card-header header-gradient text-dark py-2 d-flex flex-wrap justify-content-between align-items-center"
             data-toggle="collapse" data-target="#${card_id}" style="cursor:pointer; border-top-left-radius:1rem; border-top-right-radius:1rem;">
          <div class="d-flex align-items-center">
            <span class="mr-2" style="font-size:1.15rem;">📦</span>
            <span class="font-weight-bold h6 mb-0">${frappe.utils.escape_html(so)}</span>
          </div>
          <div class="d-flex align-items-center">
            <span class="badge badge-pill badge-soft-info mr-2">${item_count} item${item_count !== 1 ? 's' : ''}</span>
          </div>
        </div>

        <div id="${card_id}" class="collapse ${so_index === 0 ? 'show' : ''}" data-parent="#${acc_id}">
          <div class="card-body pt-3">
            <div class="d-flex flex-wrap mb-3 action-row">
              ${soBtn}
              ${dnPills}
            </div>

            <div class="container-fluid px-0">
              <div class="row">
                ${MEAL_ORDER.map(meal => {
                  const list = by_so[so][meal] || [];
                  if (!list.length) return '';
                  const is_addon = meal === 'Add-ons';
                  const badgeClass = is_addon ? 'badge-soft-dark' : badgeForMeal(meal);

                  let col = `
                    <div class="col-12 col-md-6 col-lg-4 mb-3">
                      <div class="meal-card h-100">
                        <div class="d-flex align-items-center mb-2">
                          <span class="badge ${badgeClass} mr-2 px-2 py-1">${frappe.utils.escape_html(meal)}</span>
                          <span class="text-muted small">${list.length} item${list.length !== 1 ? 's' : ''}</span>
                        </div>
                        <ul class="fancy-list">`;

                  list.forEach((it, idx) => {
                    const name_display = it.item_name || it.item_code || 'Item';
                    const note_html = it.note ? `<div class="small text-muted mt-1">${frappe.utils.escape_html(it.note)}</div>` : '';
                    const uom = it.uom ? ` <span class="text-muted">${frappe.utils.escape_html(it.uom)}</span>` : '';
                    const zebra = idx % 2 === 0 ? 'zebra' : '';

                    col += `
                      <li class="${zebra}">
                        <div class="d-flex justify-content-between align-items-start">
                          <div class="item-title">
                            ${frappe.utils.escape_html(name_display)}
                            ${note_html}
                          </div>
                          <div class="qty-chip" title="Quantity">
                            ${it.qty || 0}${uom}
                          </div>
                        </div>
                      </li>`;
                  });

                  col += `
                        </ul>
                      </div>
                    </div>`;
                  return col;
                }).join('')}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    so_index++;
  }

  html += `
    </div>

    <style>
      /* ---------- Color System ---------- */
      :root {
        --c-bg: #f7f9fc;
        --c-card: #ffffff;
        --c-border: #eef0f3;
        --c-shadow: 0 8px 20px rgba(16,24,40,0.08);
        --c-shadow-soft: 0 4px 12px rgba(16,24,40,0.06);
        --c-text-muted: #667085;

        /* Pills / badges */
        --c-users: #4f46e5;     /* indigo */
        --c-meals: #16a34a;     /* green  */
        --c-addons: #f59e0b;    /* amber  */

        --c-breakfast: #22c55e; /* green */
        --c-lunch: #06b6d4;     /* cyan  */
        --c-dinner: #f43f5e;    /* rose  */
        --c-snack1: #a855f7;    /* purple*/
        --c-snack2: #eab308;    /* yellow*/

        --c-soft: #fafbfc;
      }

      .elevate { box-shadow: var(--c-shadow-soft); border-radius: 1rem; }
      .header-gradient {
        background: linear-gradient(90deg, #eef2ff, #ecfeff, #fff7ed);
      }
      .delivery-accordion .card { border-radius: 1rem; overflow: hidden; }
      .delivery-accordion .card-header { border-bottom: 1px solid var(--c-border); }

      /* ---------- Summary ---------- */
      .delivery-summary .summary-card {
        border-radius: 1rem;
        padding: 1rem 1.25rem;
        background: var(--c-card);
        border: 1px solid var(--c-border);
        box-shadow: var(--c-shadow-soft);
        display: flex; justify-content: space-between; align-items: center;
        min-height: 68px;
      }
      .delivery-summary .summary-title { font-size: 0.85rem; color: var(--c-text-muted); }
      .delivery-summary .summary-value {
        font-weight: 800; font-size: 1.25rem; letter-spacing: .2px;
      }
      .summary-card.users .summary-value { color: var(--c-users); }
      .summary-card.meals .summary-value { color: var(--c-meals); }
      .summary-card.addons .summary-value { color: var(--c-addons); }

      .delivery-summary .pill {
        display: inline-flex; align-items: center; gap: .35rem;
        border: 1px solid var(--c-border);
        padding: .35rem .7rem; border-radius: 999px;
        margin: 0 .5rem .5rem 0; background: var(--c-soft); font-size: .82rem;
        box-shadow: 0 1px 2px rgba(16,24,40,0.04);
      }
      .delivery-summary .pill .dot {
        width: .55rem; height: .55rem; border-radius: 50%;
        display: inline-block;
      }

      .pill-breakfast .dot { background: var(--c-breakfast); }
      .pill-lunch .dot { background: var(--c-lunch); }
      .pill-dinner .dot { background: var(--c-dinner); }
      .pill-snack1 .dot { background: var(--c-snack1); }
      .pill-snack2 .dot { background: var(--c-snack2); }
      .pill-addons .dot { background: var(--c-addons); }

      /* ---------- Actions ---------- */
      .action-row .btn { border-radius: 999px; }
      .btn-chip {
        background: var(--c-card);
        border-color: var(--c-border);
        box-shadow: 0 1px 2px rgba(16,24,40,0.05);
      }
      .btn-chip .chip-dot {
        width: .5rem; height: .5rem; border-radius: 50%; background: #94a3b8; display: inline-block; margin-right: .35rem;
      }
      .btn-primary.elevate { box-shadow: 0 2px 8px rgba(79,70,229,.25); }
      .btn-primary.elevate:hover { transform: translateY(-1px); box-shadow: 0 6px 14px rgba(79,70,229,.30); }

      /* ---------- Meal Columns ---------- */
      .meal-card {
        background: var(--c-card);
        border: 1px solid var(--c-border);
        border-radius: 1rem;
        padding: .8rem 1rem;
        box-shadow: var(--c-shadow-soft);
      }
      .badge-soft-info {
        background: #e0f2fe; color: #075985; padding: .35rem .6rem;
      }
      .badge-soft-dark {
        background: #f4f4f5; color: #27272a; padding: .35rem .6rem;
      }
      .badge-meal-breakfast { background: rgba(34,197,94,.12); color: #166534; }
      .badge-meal-lunch     { background: rgba(6,182,212,.12); color: #155e75; }
      .badge-meal-dinner    { background: rgba(244,63,94,.12); color: #9f1239; }
      .badge-meal-snack1    { background: rgba(168,85,247,.12); color: #5b21b6; }
      .badge-meal-snack2    { background: rgba(234,179,8,.16);  color: #854d0e; }

      /* ---------- Item List ---------- */
      .fancy-list { list-style: none; padding: 0; margin: 0; }
      .fancy-list li {
        padding: .6rem .2rem; border-bottom: 1px dashed var(--c-border);
      }
      .fancy-list li.zebra { background: #fafafa; }
      .fancy-list li:last-child { border-bottom: 0; }
      .item-title { font-weight: 600; line-height: 1.1; }
      .qty-chip {
        font-weight: 700; padding: .25rem .5rem; border-radius: .5rem;
        background: #eef2ff; color: #3730a3; min-width: 3rem; text-align: center;
        box-shadow: inset 0 0 0 1px #e0e7ff;
      }
    </style>
  `;

  html_field.$wrapper.html(html);

  // Route handlers
  html_field.$wrapper.find('.js-route').on('click', function (e) {
    e.stopPropagation(); // don’t toggle collapse when clicking buttons
    const doctype = $(this).data('doctype');
    const name = $(this).data('name');
    if (doctype && name) frappe.set_route('Form', doctype, name);
  });
}

/* -------- helpers -------- */
function summaryCard(title, value, kind) {
  const klass = `summary-card ${kind}`;
  return `
    <div class="col-12 col-md-4 mb-2">
      <div class="${klass}">
        <div class="summary-title">${frappe.utils.escape_html(title)}</div>
        <div class="summary-value">${value}</div>
      </div>
    </div>
  `;
}
function quickPill(label, value) {
  const safe = frappe.utils.escape_html(label);
  const slug = safe.toLowerCase().replace(/\s+/g,'').replace('-', '');
  const cls =
    safe === 'Breakfast' ? 'pill-breakfast' :
    safe === 'Lunch'     ? 'pill-lunch'     :
    safe === 'Dinner'    ? 'pill-dinner'    :
    safe === 'Snack 1'   ? 'pill-snack1'    :
    safe === 'Snack 2'   ? 'pill-snack2'    : 'pill-addons';

  return `
    <div class="col-auto">
      <span class="pill ${cls}">
        <span class="dot"></span>
        <strong>${safe}:</strong> ${value}
      </span>
    </div>
  `;
}
function badgeForMeal(meal) {
  switch (meal) {
    case 'Breakfast': return 'badge badge-meal-breakfast';
    case 'Lunch': return 'badge badge-meal-lunch';
    case 'Dinner': return 'badge badge-meal-dinner';
    case 'Snack 1': return 'badge badge-meal-snack1';
    case 'Snack 2': return 'badge badge-meal-snack2';
    default: return 'badge badge-soft-dark';
  }
}


