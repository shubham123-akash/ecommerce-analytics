-- =====================================================================
-- 05_retention_rfm_cohort.sql  (PostgreSQL)
-- Business question: Who comes back, who is slipping away, and who is worth keeping?
-- =====================================================================

-- Q1. Repeat purchase rate -----------------------------------------------------------
WITH per_customer AS (
    SELECT customer_unique_id, COUNT(*) AS orders
    FROM vw_sales_orders
    GROUP BY customer_unique_id
)
SELECT COUNT(*)                                                   AS customers,
       COUNT(*) FILTER (WHERE orders >= 2)                        AS repeat_customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE orders >= 2) / COUNT(*), 2) AS repeat_purchase_rate_pct
FROM per_customer;


-- Q2. Monthly cohort retention ----------------------------------------------------------
-- Cohort = month of a customer's first order. Period N = N months after that month.
WITH activity AS (
    SELECT DISTINCT
           customer_unique_id,
           MIN(order_month) OVER (PARTITION BY customer_unique_id) AS cohort_month,
           order_month
    FROM vw_sales_orders
),
indexed AS (
    SELECT customer_unique_id,
           cohort_month,
           (EXTRACT(YEAR  FROM order_month) - EXTRACT(YEAR  FROM cohort_month)) * 12
         + (EXTRACT(MONTH FROM order_month) - EXTRACT(MONTH FROM cohort_month)) AS period
    FROM activity
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM indexed
    WHERE period = 0
    GROUP BY cohort_month
)
SELECT i.cohort_month,
       i.period::int                                              AS months_since_first_order,
       COUNT(DISTINCT i.customer_unique_id)                       AS active_customers,
       s.cohort_size,
       ROUND(100.0 * COUNT(DISTINCT i.customer_unique_id) / s.cohort_size, 2) AS retention_pct
FROM indexed i
JOIN cohort_sizes s USING (cohort_month)
GROUP BY i.cohort_month, i.period, s.cohort_size
ORDER BY i.cohort_month, i.period;


-- Q3. RFM segmentation ---------------------------------------------------------------------
-- R and M: quintile scores via NTILE(5). F: number of orders capped at 5
-- (about 97% of Olist customers order once, so frequency quintiles would be meaningless).
-- Segments are evaluated top to bottom - first match wins.
CREATE OR REPLACE VIEW vw_rfm AS
WITH snapshot AS (
    SELECT (MAX(order_purchase_timestamp)::date + 1) AS snap_date FROM vw_sales_orders
),
base AS (
    SELECT s.customer_unique_id,
           (sn.snap_date - MAX(s.order_purchase_timestamp)::date) AS recency_days,
           COUNT(*)                                               AS frequency,
           ROUND(SUM(s.revenue), 2)                               AS monetary
    FROM vw_sales_orders s
    CROSS JOIN snapshot sn
    GROUP BY s.customer_unique_id, sn.snap_date
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_score,  -- most recent = 5
           LEAST(frequency, 5)                                            AS f_score,
           NTILE(5) OVER (ORDER BY monetary, customer_unique_id)          AS m_score
    FROM base
)
SELECT *,
       CONCAT(r_score, f_score, m_score) AS rfm_score,
       CASE
           WHEN f_score >= 2 AND r_score >= 4                 THEN 'Champions'
           WHEN f_score >= 2 AND r_score <= 3                 THEN 'Loyal Repeat Buyers'
           WHEN f_score = 1  AND r_score >= 4 AND m_score >= 4 THEN 'Recent High Spenders'
           WHEN f_score = 1  AND r_score >= 4                 THEN 'New Customers'
           WHEN f_score = 1  AND r_score <= 3 AND m_score >= 4 THEN 'High-Value At Risk'
           WHEN f_score = 1  AND r_score = 3                  THEN 'Needs Attention'
           WHEN f_score = 1  AND r_score = 2                  THEN 'Hibernating'
           ELSE 'Lost'
       END AS segment
FROM scored;

-- Segment summary: where does the revenue come from?
SELECT segment,
       COUNT(*)                                                  AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)        AS pct_customers,
       ROUND(SUM(monetary), 2)                                   AS revenue,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS pct_revenue,
       ROUND(AVG(recency_days), 0)                               AS avg_recency_days,
       ROUND(AVG(monetary), 2)                                   AS avg_spend
FROM vw_rfm
GROUP BY segment
ORDER BY revenue DESC;


-- Q4. Win-back list: high-value one-time customers who have gone quiet -------------------------
SELECT customer_unique_id, recency_days, monetary, rfm_score
FROM vw_rfm
WHERE segment = 'High-Value At Risk'
ORDER BY monetary DESC
LIMIT 50;
