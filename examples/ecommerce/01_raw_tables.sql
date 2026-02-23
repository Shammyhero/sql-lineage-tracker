-- ============================================
-- E-Commerce Pipeline: 01 - Raw Source Tables
-- ============================================
-- These represent raw data landing tables from
-- source systems (typically loaded via EL tools).

CREATE TABLE raw.customers (
    customer_id     BIGINT PRIMARY KEY,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    email           VARCHAR(255),
    phone           VARCHAR(50),
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE raw.orders (
    order_id        BIGINT PRIMARY KEY,
    customer_id     BIGINT REFERENCES raw.customers(customer_id),
    order_date      DATE,
    status          VARCHAR(30),
    total_amount    DECIMAL(12, 2),
    currency        VARCHAR(3) DEFAULT 'USD',
    shipping_address_id BIGINT,
    created_at      TIMESTAMP
);

CREATE TABLE raw.order_items (
    item_id         BIGINT PRIMARY KEY,
    order_id        BIGINT REFERENCES raw.orders(order_id),
    product_id      BIGINT,
    quantity        INT,
    unit_price      DECIMAL(10, 2),
    discount_pct    DECIMAL(5, 2) DEFAULT 0,
    created_at      TIMESTAMP
);

CREATE TABLE raw.products (
    product_id      BIGINT PRIMARY KEY,
    product_name    VARCHAR(255),
    category_id     BIGINT,
    brand           VARCHAR(100),
    sku             VARCHAR(50),
    base_price      DECIMAL(10, 2),
    cost_price      DECIMAL(10, 2),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP
);

CREATE TABLE raw.categories (
    category_id     BIGINT PRIMARY KEY,
    category_name   VARCHAR(100),
    parent_category_id BIGINT,
    created_at      TIMESTAMP
);
