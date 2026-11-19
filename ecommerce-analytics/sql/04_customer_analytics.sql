-- =====================================================================
-- 04_customer_analytics.sql  (PostgreSQL)
-- Business question: Who are our customers and how do they buy?
-- Always use customer_unique_id (a person), never customer_id (one per order).
-- =====================================================================

-- Q1. Customer counts -----------------------------------------------------------
SELECT COUNT(DISTINCT customer_unique_id) AS unique_customers,
       COUNT(DISTINCT customer_id)        AS customer_ids_wrong_to_use   -- shows why the distinction matters
FROM vw_sales_orders;


-- Q2. New vs returning customers per month ----------------------------------------
SELECT order_month,
       COUNT(DISTINCT customer_unique_id) FILTER (WHERE customer_type = 'New')       AS new_customers,
       COUNT(DISTINCT customer_unique_id) FILTER (WHERE customer_type = 'Returning') AS returning_customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE customer_type = 'Returning') / COUNT(*), 2) AS returning_order_pct,
       ROUND(SUM(revenue) FILTER (WHERE customer_type = 'Returning'), 2)             AS returning_revenue
FROM vw_sales_orders
GROUP BY order_month
ORDER BY order_month;


-- Q3. Top 10 customers by lifetime spend ---------------------------------------------
SELECT customer_unique_id,
       COUNT(*)                   AS orders,
       ROUND(SUM(revenue), 2)     AS lifetime_revenue,
       ROUND(AVG(revenue), 2)     AS avg_order_value,
       MIN(order_purchase_timestamp)::date AS first_order,
       MAX(order_purchase_timestamp)::date AS last_order
FROM vw_sales_orders
GROUP BY customer_unique_id
ORDER BY lifetime_revenue DESC
LIMIT 10;


-- Q4. Purchase frequency distribution ---------------------------------------------------
WITH per_customer AS (
    SELECT customer_unique_id, COUNT(*) AS orders
    FROM vw_sales_orders
    GROUP BY customer_unique_id
)
SELECT orders                                                    AS orders_placed,
       COUNT(*)                                                  AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)        AS pct_of_customers
FROM per_customer
GROUP BY orders
ORDER BY orders;


-- Q5. Do repeat customers spend more per order than one-time customers? ---------------------
WITH per_customer AS (
    SELECT customer_unique_id,
           COUNT(*)     AS orders,
           SUM(revenue) AS total_revenue
    FROM vw_sales_orders
    GROUP BY customer_unique_id
)
SELECT CASE WHEN orders >= 2 THEN 'Repeat' ELSE 'One-time' END AS customer_group,
       COUNT(*)                                                AS customers,
       ROUND(SUM(total_revenue), 2)                            AS revenue,
       ROUND(100.0 * SUM(total_revenue) / SUM(SUM(total_revenue)) OVER (), 2) AS revenue_share_pct,
       ROUND(SUM(total_revenue) / SUM(orders), 2)              AS avg_order_value
FROM per_customer
GROUP BY 1;


-- Q6. Median days between first and second purchase (repeat customers only) -----------------
WITH ranked AS (
    SELECT customer_unique_id, order_purchase_timestamp, customer_order_number
    FROM vw_sales_orders
    WHERE customer_order_number <= 2
),
gaps AS (
    SELECT customer_unique_id,
           MAX(order_purchase_timestamp) FILTER (WHERE customer_order_number = 2)
         - MAX(order_purchase_timestamp) FILTER (WHERE customer_order_number = 1) AS gap
    FROM ranked
    GROUP BY customer_unique_id
    HAVING COUNT(*) = 2
)
SELECT COUNT(*) AS repeat_customers,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM gap) / 86400.0))::numeric, 1)
           AS median_days_to_second_order
FROM gaps;
