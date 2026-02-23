-- ============================================
-- E-Commerce Pipeline: 04 - Mart / Analytics
-- ============================================
-- Final analytics-ready views for dashboards.

CREATE VIEW mart.customer_lifetime_value AS
SELECT
    oe.customer_id,
    oe.first_name,
    oe.last_name,
    oe.email,
    COUNT(DISTINCT oe.order_id) AS total_orders,
    SUM(oe.calculated_total) AS lifetime_value,
    AVG(oe.calculated_total) AS avg_order_value,
    MIN(oe.order_date) AS first_order_date,
    MAX(oe.order_date) AS last_order_date,
    MAX(oe.order_date) - MIN(oe.order_date) AS customer_tenure_days
FROM intermediate.int_orders_enriched oe
WHERE oe.status != 'CANCELLED'
GROUP BY oe.customer_id, oe.first_name, oe.last_name, oe.email;

CREATE VIEW mart.product_dashboard AS
SELECT
    pp.product_name,
    pp.brand,
    pp.category_name,
    pp.total_quantity_sold,
    pp.total_revenue,
    pp.order_count,
    pp.avg_selling_price,
    pp.profit_margin,
    pp.total_revenue * (pp.profit_margin / pp.avg_selling_price) AS estimated_profit
FROM intermediate.int_product_performance pp
WHERE pp.total_quantity_sold > 0;

-- Summary view combining customer + product insights
CREATE VIEW mart.executive_summary AS
WITH customer_stats AS (
    SELECT
        COUNT(*) AS total_customers,
        SUM(lifetime_value) AS total_revenue,
        AVG(lifetime_value) AS avg_clv,
        AVG(total_orders) AS avg_orders_per_customer
    FROM mart.customer_lifetime_value
),
product_stats AS (
    SELECT
        COUNT(*) AS total_products,
        SUM(total_revenue) AS product_revenue,
        AVG(avg_selling_price) AS avg_price
    FROM mart.product_dashboard
)
SELECT
    cs.total_customers,
    cs.total_revenue,
    cs.avg_clv,
    cs.avg_orders_per_customer,
    ps.total_products,
    ps.avg_price
FROM customer_stats cs
CROSS JOIN product_stats ps;
