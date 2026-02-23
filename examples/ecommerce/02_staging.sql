-- ============================================
-- E-Commerce Pipeline: 02 - Staging Layer
-- ============================================
-- Clean and standardize raw data.

CREATE TABLE staging.stg_customers AS
SELECT
    customer_id,
    LOWER(TRIM(first_name)) AS first_name,
    LOWER(TRIM(last_name))  AS last_name,
    LOWER(TRIM(email))      AS email,
    phone,
    created_at,
    updated_at,
    is_active
FROM raw.customers
WHERE customer_id IS NOT NULL;

CREATE TABLE staging.stg_orders AS
SELECT
    order_id,
    customer_id,
    order_date,
    UPPER(status) AS status,
    total_amount,
    currency,
    shipping_address_id,
    created_at
FROM raw.orders
WHERE order_id IS NOT NULL;

CREATE TABLE staging.stg_order_items AS
SELECT
    item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    discount_pct,
    unit_price * quantity * (1 - discount_pct / 100) AS line_total,
    created_at
FROM raw.order_items;

CREATE TABLE staging.stg_products AS
SELECT
    product_id,
    TRIM(product_name) AS product_name,
    category_id,
    brand,
    sku,
    base_price,
    cost_price,
    base_price - cost_price AS profit_margin,
    is_active,
    created_at
FROM raw.products;
