-- =====================================================================
-- 01_schema_and_load.sql  (PostgreSQL)
-- Creates the 6 raw tables and loads the Olist CSVs.
-- Run in psql from the folder that contains the CSV files, e.g.:
--   psql -d olist -f sql/01_schema_and_load.sql
-- (\copy reads files on YOUR machine, so it works without superuser rights.
--  Edit the file paths below to wherever you saved the CSVs.)
-- =====================================================================

DROP TABLE IF EXISTS order_reviews, order_items, orders, products, customers, category_translation CASCADE;

CREATE TABLE customers (
    customer_id               VARCHAR(32) PRIMARY KEY,   -- one per ORDER, not per person
    customer_unique_id        VARCHAR(32) NOT NULL,      -- the real customer: use this for retention
    customer_zip_code_prefix  VARCHAR(10),
    customer_city             VARCHAR(100),
    customer_state            CHAR(2)
);

CREATE TABLE orders (
    order_id                       VARCHAR(32) PRIMARY KEY,
    customer_id                    VARCHAR(32) REFERENCES customers(customer_id),
    order_status                   VARCHAR(20),
    order_purchase_timestamp       TIMESTAMP,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP
);

CREATE TABLE products (
    product_id                   VARCHAR(32) PRIMARY KEY,
    product_category_name        VARCHAR(100),
    product_name_lenght          INT,      -- (sic) spelling matches the original CSV header
    product_description_lenght   INT,
    product_photos_qty           INT,
    product_weight_g             INT,
    product_length_cm            INT,
    product_height_cm            INT,
    product_width_cm             INT
);

CREATE TABLE order_items (
    order_id             VARCHAR(32) REFERENCES orders(order_id),
    order_item_id        INT,
    product_id           VARCHAR(32),
    seller_id            VARCHAR(32),
    shipping_limit_date  TIMESTAMP,
    price                NUMERIC(10,2),
    freight_value        NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_reviews (          -- no primary key: review_id is NOT unique in the real data
    review_id                VARCHAR(32),
    order_id                 VARCHAR(32),
    review_score             SMALLINT,
    review_comment_title     TEXT,
    review_comment_message   TEXT,
    review_creation_date     TIMESTAMP,
    review_answer_timestamp  TIMESTAMP
);

CREATE TABLE category_translation (
    product_category_name          VARCHAR(100) PRIMARY KEY,
    product_category_name_english  VARCHAR(100)
);

-- Load order matters because of the foreign keys.
\copy customers            FROM 'data/raw/olist_customers_dataset.csv'      WITH (FORMAT csv, HEADER true)
\copy orders               FROM 'data/raw/olist_orders_dataset.csv'         WITH (FORMAT csv, HEADER true)
\copy products             FROM 'data/raw/olist_products_dataset.csv'       WITH (FORMAT csv, HEADER true)
\copy order_items          FROM 'data/raw/olist_order_items_dataset.csv'    WITH (FORMAT csv, HEADER true)
\copy order_reviews        FROM 'data/raw/olist_order_reviews_dataset.csv'  WITH (FORMAT csv, HEADER true)
\copy category_translation FROM 'data/raw/product_category_name_translation.csv' WITH (FORMAT csv, HEADER true)

-- Helpful indexes for the joins used later
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_purchase ON orders(order_purchase_timestamp);
CREATE INDEX idx_items_product   ON order_items(product_id);
CREATE INDEX idx_reviews_order   ON order_reviews(order_id);
CREATE INDEX idx_customers_uid   ON customers(customer_unique_id);

-- Row-count sanity check (real data: ~99k orders, ~99k customers, ~112k items, ~33k products)
SELECT 'customers' AS tbl, COUNT(*) FROM customers
UNION ALL SELECT 'orders',      COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'products',    COUNT(*) FROM products
UNION ALL SELECT 'reviews',     COUNT(*) FROM order_reviews;
