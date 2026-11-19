-- =====================================================================
-- 02_clean_views.sql  (PostgreSQL)
-- SQL equivalent of src/01_clean_data.py. Every analysis query reads from these views.
--
--   vw_order_fact   one row per order (all statuses) with revenue, delivery metrics, review
--   vw_sales_orders one row per VALID sales order + customer order sequence (new / returning)
--   vw_order_lines  one row per order line of a valid sales order, with English category
--
-- Why order-level first? Joining items AND reviews to orders at once multiplies rows
-- (an order with 3 items x 2 reviews = 6 rows) and silently inflates revenue.
-- Aggregating each child table to one row per order BEFORE joining avoids that.
-- =====================================================================

CREATE OR REPLACE VIEW vw_order_fact AS
WITH item_totals AS (
    SELECT order_id,
           COUNT(*)           AS items_count,
           SUM(price)         AS revenue,
           SUM(freight_value) AS freight
    FROM order_items
    GROUP BY order_id
),
latest_review AS (                      -- some orders have several reviews: keep the latest
    SELECT order_id, review_score
    FROM (
        SELECT order_id, review_score,
               ROW_NUMBER() OVER (PARTITION BY order_id
                                  ORDER BY review_answer_timestamp DESC,
                                           review_creation_date DESC) AS rn
        FROM order_reviews
        WHERE review_score BETWEEN 1 AND 5
    ) r
    WHERE rn = 1
)
SELECT o.order_id,
       o.customer_id,
       c.customer_unique_id,
       c.customer_state,
       o.order_status,
       o.order_purchase_timestamp,
       DATE_TRUNC('month', o.order_purchase_timestamp)::date          AS order_month,
       EXTRACT(YEAR FROM o.order_purchase_timestamp)::int             AS order_year,
       o.order_delivered_customer_date,
       o.order_estimated_delivery_date,
       it.items_count,
       it.revenue,
       it.freight,
       lr.review_score,
       ROUND((EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400.0)::numeric, 1)
                                                                      AS delivery_days,
       ROUND((EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_estimated_delivery_date)) / 86400.0)::numeric, 1)
                                                                      AS delay_days,
       CASE WHEN o.order_delivered_customer_date IS NOT NULL
            THEN (o.order_delivered_customer_date > o.order_estimated_delivery_date)::int
       END                                                            AS is_late
FROM orders o
JOIN customers c           ON c.customer_id = o.customer_id
LEFT JOIN item_totals it   ON it.order_id   = o.order_id
LEFT JOIN latest_review lr ON lr.order_id   = o.order_id;


CREATE OR REPLACE VIEW vw_sales_orders AS
SELECT f.*,
       ROW_NUMBER() OVER (PARTITION BY f.customer_unique_id
                          ORDER BY f.order_purchase_timestamp, f.order_id)        AS customer_order_number,
       CASE WHEN ROW_NUMBER() OVER (PARTITION BY f.customer_unique_id
                                    ORDER BY f.order_purchase_timestamp, f.order_id) = 1
            THEN 'New' ELSE 'Returning' END                                       AS customer_type
FROM vw_order_fact f
WHERE f.order_status = 'delivered'
  AND f.revenue IS NOT NULL
  AND f.order_delivered_customer_date IS NOT NULL
  AND f.order_delivered_customer_date >= f.order_purchase_timestamp;


CREATE OR REPLACE VIEW vw_order_lines AS
SELECT oi.order_id,
       oi.order_item_id,
       oi.product_id,
       oi.price,
       oi.freight_value,
       so.customer_unique_id,
       so.order_month,
       COALESCE(ct.product_category_name_english, p.product_category_name, 'unknown') AS category_en
FROM order_items oi
JOIN vw_sales_orders so              ON so.order_id = oi.order_id
LEFT JOIN products p                 ON p.product_id = oi.product_id
LEFT JOIN category_translation ct    ON ct.product_category_name = p.product_category_name;
