CREATE OR REPLACE VIEW delivery_daily_nutrients_view AS
SELECT
    dn.posting_date,
    dn.customer,
    dn.customer_name,
    dn.subscription,

    SUM(COALESCE(inv.calories_value, 0)  *
        (CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END)) AS calories_total,

    SUM(COALESCE(inv.protein_value, 0)   *
        (CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END)) AS protein_total,

    SUM(COALESCE(inv.fats_value, 0)      *
        (CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END)) AS fats_total,

    SUM(COALESCE(inv.net_carbs_value, 0) *
        (CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END)) AS net_carbs_total,

    SUM(COALESCE(inv.fibers_value, 0)    *
        (CASE WHEN COALESCE(d.extra_portion, 0) = 1 THEN 1 ELSE d.qty END)) AS fibers_total

FROM `tabDelivery Note Item` d
JOIN `tabDelivery Note` dn
     ON dn.name = d.parent
    AND dn.docstatus = 1
LEFT JOIN item_nutrients_view inv
       ON inv.item = d.item_code
GROUP BY dn.posting_date, dn.customer, dn.customer_name, dn.subscription
ORDER BY dn.posting_date, dn.customer;
