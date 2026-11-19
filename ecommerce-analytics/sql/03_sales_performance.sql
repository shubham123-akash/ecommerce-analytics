-- =====================================================================
-- 03_sales_performance.sql  (PostgreSQL)
-- Business question: How is the company performing, and what drives revenue?
-- Revenue = SUM(price) of delivered orders (freight excluded). Currency: BRL (R$).
-- =====================================================================

-- Q1. Headline KPIs -----------------------------------------------------------
SELECT ROUND(SUM(revenue), 2)                         AS total_revenue,
       COUNT(DISTINCT order_id)                       AS total_orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2) AS avg_order_value,
       COUNT(DISTINCT customer_unique_id)             AS unique_customers
FROM vw_sales_orders;


-- Q2. Monthly revenue trend with month-over-month growth (window function: LAG) ---
WITH monthly AS (
    SELECT order_month,
           SUM(revenue)             AS revenue,
           COUNT(DISTINCT order_id) AS orders
    FROM vw_sales_orders
    GROUP BY order_month
)
SELECT order_month,
       ROUND(revenue, 2) AS revenue,
       orders,
       ROUND(revenue / orders, 2) AS avg_order_value,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
             / NULLIF(LAG(revenue) OVER (ORDER BY order_month), 0), 1) AS revenue_mom_pct
FROM monthly
ORDER BY order_month;


-- Q3. Yearly summary ----------------------------------------------------------
-- Note: Olist data is partial in 2016 and ends in Aug/Sep 2018, so compare years carefully.
SELECT order_year,
       ROUND(SUM(revenue), 2)                            AS revenue,
       COUNT(DISTINCT order_id)                          AS orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2) AS avg_order_value
FROM vw_sales_orders
GROUP BY order_year
ORDER BY order_year;


-- Q4. Top 10 products by revenue ------------------------------------------------
SELECT product_id,
       category_en,
       ROUND(SUM(price), 2) AS revenue,
       COUNT(*)             AS units_sold
FROM vw_order_lines
GROUP BY product_id, category_en
ORDER BY revenue DESC
LIMIT 10;


-- Q5. Category performance with revenue share and cumulative share (Pareto) ------
WITH cat AS (
    SELECT category_en,
           SUM(price)               AS revenue,
           COUNT(*)                 AS units_sold,
           COUNT(DISTINCT order_id) AS orders
    FROM vw_order_lines
    GROUP BY category_en
)
SELECT category_en,
       ROUND(revenue, 2)                                          AS revenue,
       units_sold,
       orders,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2)           AS revenue_share_pct,
       ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC)
             / SUM(revenue) OVER (), 2)                           AS cumulative_share_pct
FROM cat
ORDER BY revenue DESC
LIMIT 15;


-- Q6. Revenue by customer state --------------------------------------------------
SELECT customer_state,
       ROUND(SUM(revenue), 2)             AS revenue,
       COUNT(DISTINCT order_id)           AS orders,
       COUNT(DISTINCT customer_unique_id) AS customers
FROM vw_sales_orders
GROUP BY customer_state
ORDER BY revenue DESC;
