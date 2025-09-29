CREATE OR REPLACE VIEW `deliveries` AS
SELECT 
    t1.sales_order,
    t1.delivery_note,
    t1.delivery_date as subsciption_delivery_date,
    t1.name AS delivery_stop,
    t1.customer,
    t2.name AS delivery_trip,
    t2.driver AS driver_id,
    DATE(t2.departure_time) as delivery_date,
    t3.full_name AS driver_name,
    t3.cell_number AS driver_number,
    t1.latitude,
    t1.longitude,
    t1.distance,
    t1.estimated_arrival,
    t1.start_time,
    t1.end_time,
    t1.actual_arrival,
    t1.delivery_status,
    t1.delivery_proof,
    t1.failure_reason,
    t1.failure_reason_details
FROM `tabDelivery Stop` AS t1
INNER JOIN `tabDelivery Trip` AS t2 ON t1.parent = t2.name
INNER JOIN `tabDriver` AS t3 ON t2.driver = t3.name
WHERE t2.docstatus = 1;
