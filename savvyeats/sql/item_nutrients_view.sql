CREATE OR REPLACE VIEW item_nutrients_view AS
SELECT
    i.name AS item,

    COALESCE(MAX(CASE WHEN n.nutrient = 'Calories'  THEN n.uom  END), 'Gram') AS calories_uom,
    COALESCE(MAX(CASE WHEN n.nutrient = 'Calories'  THEN n.value END), 0)      AS calories_value,

    COALESCE(MAX(CASE WHEN n.nutrient = 'Protein'   THEN n.uom  END), 'Gram') AS protein_uom,
    COALESCE(MAX(CASE WHEN n.nutrient = 'Protein'   THEN n.value END), 0)      AS protein_value,

    COALESCE(MAX(CASE WHEN n.nutrient = 'Fats'      THEN n.uom  END), 'Gram') AS fats_uom,
    COALESCE(MAX(CASE WHEN n.nutrient = 'Fats'      THEN n.value END), 0)      AS fats_value,

    COALESCE(MAX(CASE WHEN n.nutrient = 'Net Carbs' THEN n.uom  END), 'Gram') AS net_carbs_uom,
    COALESCE(MAX(CASE WHEN n.nutrient = 'Net Carbs' THEN n.value END), 0)      AS net_carbs_value,

    COALESCE(MAX(CASE WHEN n.nutrient = 'Fibers'    THEN n.uom  END), 'Gram') AS fibers_uom,
    COALESCE(MAX(CASE WHEN n.nutrient = 'Fibers'    THEN n.value END), 0)      AS fibers_value

FROM `tabItem` i
LEFT JOIN `tabItem Nutrients` n
    ON n.parent = i.name
   AND n.parenttype = 'Item'
   AND n.parentfield = 'nutrients'
GROUP BY i.name
ORDER BY i.name;
