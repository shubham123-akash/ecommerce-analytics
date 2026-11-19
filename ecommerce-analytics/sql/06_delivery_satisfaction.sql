-- =====================================================================
-- 06_delivery_satisfaction.sql  (PostgreSQL)
-- Business question: Does late delivery hurt customer satisfaction?
-- delay_days = actual delivery - estimated delivery (positive = late).
-- =====================================================================

-- Q1. Delivery & satisfaction KPIs ----------------------------------------------------------
SELECT ROUND(AVG(delivery_days), 1)                        AS avg_delivery_days,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_days))::numeric, 1) AS median_delivery_days,
       ROUND(100.0 * AVG(is_late), 2)                      AS late_delivery_pct,
       ROUND(AVG(review_score), 2)                         AS avg_review_score,
       ROUND(CORR(delay_days, review_score)::numeric, 3)   AS corr_delay_vs_review
FROM vw_sales_orders;


-- Q2. Review score by delivery timeliness ---------------------------------------------------------
WITH bucketed AS (
    SELECT order_id, review_score,
           CASE WHEN delay_days <= -7 THEN '1. Early 7+ days'
                WHEN delay_days <=  0 THEN '2. On time (0-7 days early)'
                WHEN delay_days <=  3 THEN '3. Late 1-3 days'
                WHEN delay_days <=  7 THEN '4. Late 4-7 days'
                ELSE                       '5. Late 7+ days' END AS delivery_bucket
    FROM vw_sales_orders
    WHERE review_score IS NOT NULL
)
SELECT delivery_bucket,
       COUNT(*)                                                     AS orders,
       ROUND(AVG(review_score), 2)                                  AS avg_review,
       ROUND(100.0 * AVG((review_score <= 2)::int), 1)              AS pct_1_2_star
FROM bucketed
GROUP BY delivery_bucket
ORDER BY delivery_bucket;


-- Q3. Monthly trend: late % vs average rating -------------------------------------------------------
SELECT order_month,
       ROUND(AVG(delivery_days), 1)  AS avg_delivery_days,
       ROUND(100.0 * AVG(is_late), 2) AS late_pct,
       ROUND(AVG(review_score), 2)   AS avg_review
FROM vw_sales_orders
GROUP BY order_month
ORDER BY order_month;


-- Q4. States with the slowest delivery (min 100 orders to avoid noisy small samples) ---------------
SELECT customer_state,
       COUNT(*)                        AS orders,
       ROUND(AVG(delivery_days), 1)    AS avg_delivery_days,
       ROUND(100.0 * AVG(is_late), 2)  AS late_pct,
       ROUND(AVG(review_score), 2)     AS avg_review
FROM vw_sales_orders
GROUP BY customer_state
HAVING COUNT(*) >= 100
ORDER BY avg_delivery_days DESC;


-- Q5. Does a bad delivery cost us repeat business? -----------------------------------------------------
-- Compare how often a customer's FIRST order was late vs. whether they ordered again.
WITH first_orders AS (
    SELECT customer_unique_id, is_late, review_score
    FROM vw_sales_orders
    WHERE customer_order_number = 1
),
repeaters AS (
    SELECT DISTINCT customer_unique_id FROM vw_sales_orders WHERE customer_order_number = 2
)
SELECT CASE WHEN f.is_late = 1 THEN 'First order late' ELSE 'First order on time' END AS first_delivery,
       COUNT(*)                                                       AS customers,
       COUNT(r.customer_unique_id)                                    AS came_back,
       ROUND(100.0 * COUNT(r.customer_unique_id) / COUNT(*), 2)       AS repeat_rate_pct
FROM first_orders f
LEFT JOIN repeaters r USING (customer_unique_id)
GROUP BY 1;
