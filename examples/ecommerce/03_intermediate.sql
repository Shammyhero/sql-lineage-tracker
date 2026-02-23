-- ============================================
-- E-Commerce Pipeline: 03 - Intermediate Layer
-- ============================================
-- Business logic, joins, and enrichment.

CREATE TABLE intermediate.int_orders_enriched AS
SELECT
    o.order_id,
    o.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    o.order_date,
    o.status,
    o.total_amount,
    o.currency,
    COUNT(oi.item_id) AS item_count,
    SUM(oi.line_total) AS calculated_total
FROM staging.stg_orders o
JOIN staging.stg_customers c ON o.customer_id = c.customer_id
JOIN staging.stg_order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.customer_id, c.first_name, c.last_name,
         c.email, o.order_date, o.status, o.total_amount, o.currency;

CREATE TABLE intermediate.int_product_performance AS
WITH product_sales AS (
    SELECT
        p.product_id,
        p.product_name,
        p.brand,
        p.category_id,
        p.profit_margin,
        SUM(oi.quantity) AS total_quantity_sold,
        SUM(oi.line_total) AS total_revenue,
        COUNT(DISTINCT oi.order_id) AS order_count
    FROM staging.stg_products p
    JOIN staging.stg_order_items oi ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.product_name, p.brand, p.category_id, p.profit_margin
)
SELECT
    ps.*,
    cat.category_name,
    ps.total_revenue / NULLIF(ps.total_quantity_sold, 0) AS avg_selling_price
FROM product_sales ps
LEFT JOIN raw.categories cat ON ps.category_id = cat.category_id;
