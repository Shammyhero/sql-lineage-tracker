-- =============================================
-- Inventory & Supply Chain
-- Complex: MERGE, multiple CTEs, window functions
-- NO dependency on other files
-- =============================================

-- Merge latest inventory snapshot with warehouse data
CREATE TABLE current_inventory AS
WITH warehouse_stock AS (
    SELECT
        w.warehouse_id,
        w.warehouse_name,
        w.region,
        i.sku,
        i.quantity_on_hand,
        i.last_counted_at,
        RANK() OVER (PARTITION BY i.sku ORDER BY i.quantity_on_hand DESC) AS stock_rank
    FROM warehouses w
    JOIN inventory_snapshots i ON w.warehouse_id = i.warehouse_id
    WHERE i.snapshot_date = CURRENT_DATE
),
low_stock AS (
    SELECT sku, SUM(quantity_on_hand) AS total_qty
    FROM warehouse_stock
    GROUP BY sku
    HAVING SUM(quantity_on_hand) < 100
)
SELECT
    ws.warehouse_id,
    ws.warehouse_name,
    ws.region,
    ws.sku,
    ws.quantity_on_hand,
    ws.stock_rank,
    CASE WHEN ls.sku IS NOT NULL THEN true ELSE false END AS is_low_stock,
    ls.total_qty AS global_qty
FROM warehouse_stock ws
LEFT JOIN low_stock ls ON ws.sku = ls.sku;

-- Reorder recommendations (depends on current_inventory)
CREATE VIEW reorder_list AS
SELECT
    ci.sku,
    ci.warehouse_name,
    ci.quantity_on_hand,
    ci.global_qty,
    p.supplier_id,
    p.lead_time_days,
    GREATEST(0, 200 - ci.quantity_on_hand) AS reorder_qty
FROM current_inventory ci
JOIN products_catalog p ON ci.sku = p.sku
WHERE ci.is_low_stock = true;
