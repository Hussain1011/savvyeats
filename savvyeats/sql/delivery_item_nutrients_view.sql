CREATE OR REPLACE VIEW delivery_item_nutrients_view AS
SELECT
    d.parent AS delivery_note,
    dn.posting_date,
    dn.customer,
    dn.customer_name,
    dn.subscription,
    d.item_code AS item,
    d.meal,
    d.qty,
    CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END AS qty_multiplier,

    -- UOMs
    inv.calories_uom,
    inv.protein_uom,
    inv.fats_uom,
    inv.net_carbs_uom,
    inv.fibers_uom,

    -- Totals per nutrient
    COALESCE(inv.calories_value, 0)  * CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END AS calories_total,
    COALESCE(inv.protein_value, 0)   * CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END AS protein_total,
    COALESCE(inv.fats_value, 0)      * CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END AS fats_total,
    COALESCE(inv.net_carbs_value, 0) * CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END AS net_carbs_total,
    COALESCE(inv.fibers_value, 0)    * CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END AS fibers_total

FROM `tabDelivery Note Item` d
JOIN `tabDelivery Note` dn
     ON dn.name = d.parent
    AND dn.docstatus = 1
LEFT JOIN item_nutrients_view inv
       ON inv.item = d.item_code;
