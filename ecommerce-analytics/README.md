# E-Commerce Sales & Customer Retention Analytics

**Stack:** Python (pandas, NumPy, matplotlib) · SQL (PostgreSQL) · Power BI · Excel
**Dataset:** [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (~100k orders, 2016-2018, currency R$)

## Business problem
An online marketplace wants to understand (1) how sales are performing, (2) who its customers are and
how they buy, (3) why so few customers come back, and (4) whether late deliveries hurt satisfaction.

## Business questions answered
| Area | Questions | Where |
|---|---|---|
| Sales | Revenue, orders, AOV, monthly/yearly trend, top products, top categories | `sql/03_*`, `src/02_*` |
| Customers | Unique customers, new vs returning, top spenders, purchase frequency | `sql/04_*`, `src/02_*` |
| Retention | Repeat rate, monthly cohort retention, RFM segments, win-back list | `sql/05_*`, `src/03_*` |
| Delivery | Avg delivery time, late %, rating vs delay, slowest states, does a bad first delivery reduce repeat purchase? | `sql/06_*`, `src/02_*` |

## Project structure
```
data/raw/            <- put the 5 (+1) Olist CSVs here
data/sample/         <- synthetic test data (generated)
data/processed/      <- cleaned tables (created by step 1)
src/                 <- Python pipeline (steps 0-3)
sql/                 <- PostgreSQL: schema, clean views, 4 analysis files
powerbi/             <- build guide: data model, DAX measures, page layouts
outputs/<real|sample>/charts, powerbi_tables
```

## How to run

```bash
pip install -r requirements.txt

# --- A. Smoke test on synthetic data (no download needed) ---
python src/generate_sample_data.py
python src/01_clean_data.py   --sample
python src/02_analysis_kpis.py --sample
python src/03_rfm_cohort.py   --sample

# --- B. Real project: download Olist from Kaggle into data/raw/, then ---
python src/01_clean_data.py
python src/02_analysis_kpis.py
python src/03_rfm_cohort.py
```

**SQL (PostgreSQL):** create a database, then from the project root:
```bash
createdb olist
psql -d olist -f sql/01_schema_and_load.sql   # creates tables + loads data/raw/*.csv
psql -d olist -f sql/02_clean_views.sql       # vw_order_fact, vw_sales_orders, vw_order_lines
# then run queries from 03-06 in pgAdmin / DBeaver / psql
```
**Power BI:** follow `powerbi/POWERBI_GUIDE.md`.

## Design decisions (be ready to explain these in interviews)
1. **`customer_unique_id`, not `customer_id`.** In Olist, `customer_id` is generated per order, so counting it
   treats every order as a new customer and makes retention look like 0%.
2. **Revenue = delivered orders only, product price only** (freight excluded). Cancelled / unavailable orders are not revenue.
3. **One row per order before joining.** Items and reviews are aggregated first; joining them directly multiplies rows and inflates revenue.
4. **Duplicate reviews:** some orders have several; the latest is kept.
5. **Category names are Portuguese** - translated with `product_category_name_translation.csv`; missing categories become `unknown`.
6. **Olist has no product names**, so "top products" are shown as category + product ID.
7. **RFM frequency is capped at 5 instead of quintiled**, because ~97% of customers buy once and quintiles would be meaningless. Segments are rule-based and documented in `src/03_rfm_cohort.py` / `sql/05_*`.
8. Python and SQL implement the same logic, so you can cross-check numbers between them (tiny differences in RFM score boundaries are possible: NTILE vs rank-quintile).

## Expect this in the real data
Olist is a notoriously **low-repeat** dataset: roughly 3% of customers order twice, and cohort retention after
month 0 is typically well under 1-2%. That is not a bug - it **is** the headline finding. Your story becomes:
*"Retention is the core problem; here is who to win back and whether delivery experience contributes."*

## Findings template (fill in AFTER running on the real data)
| # | Finding | Evidence (your number) | Recommended action |
|---|---|---|---|
| 1 | Top categories drive X% of revenue | `category_sales.csv` | Prioritise inventory / marketing |
| 2 | Repeat purchase rate is X% | `rfm_segment_summary.csv`, SQL 05-Q1 | Launch post-purchase re-engagement |
| 3 | Late orders score X vs Y stars | `delay_vs_review.csv` | Tighten delivery estimates / carriers in slow states |
| 4 | "High-Value At Risk" segment = X% of revenue | `rfm_segment_summary.csv` | Targeted win-back campaign (SQL 05-Q4 list) |
| 5 | First-order lateness vs repeat rate | SQL 06-Q5 | Prioritise on-time delivery for first orders |

## Resume entry (replace the X's with YOUR validated numbers - do not keep placeholders)
**E-Commerce Sales & Customer Retention Analysis** | SQL, Python, Power BI
- Cleaned and modelled ~100K Olist orders across 5 relational tables using Python (pandas) and PostgreSQL, resolving duplicate reviews, missing categories, and invalid delivery records.
- Wrote SQL (CTEs, window functions, cohort and RFM queries) to analyse revenue trends, product performance, and customer behaviour.
- Built a 2-page interactive Power BI dashboard (DAX measures, star-schema model) tracking revenue, AOV, retention, and delivery performance.
- Identified that only X% of customers make a repeat purchase and that late deliveries lower average ratings from X to Y; recommended a win-back campaign targeting the "High-Value At Risk" segment (X% of revenue).

## Interview prep - you should be able to answer
- Why `customer_unique_id` instead of `customer_id`? What happens to retention if you use the wrong one?
- Why aggregate items and reviews before joining? Show the row-multiplication problem.
- Explain `NTILE`, `LAG`, `ROW_NUMBER`, and `FILTER` as used in your queries.
- How is a cohort defined? How do you read the cohort heatmap?
- Why did you cap RFM frequency instead of using quintiles?
- Late delivery correlates with low ratings - does that prove causation? What else could explain it?
- What would you do next? (e.g. seller-level analysis, review-text sentiment, predictive churn model)

## Notes on testing
The Python pipeline was run end-to-end on synthetic data matching the Olist schema. The SQL files are written
for PostgreSQL and were reviewed but **not executed in this environment** - run them on your machine and
cross-check against the Python outputs; any mismatch is worth investigating.
**Numbers from `--sample` runs are synthetic and must never be quoted as findings.**
