# Power BI Build Guide (2 pages)

All currency is **Brazilian Real (R$)** - the Olist dataset is Brazilian. Use `R$` in card formats, not ₹.

## 1. Load the data (Home > Get Data > Text/CSV)

| Table | File | Folder |
|---|---|---|
| `fact_sales_orders` | fact_sales_orders.csv | `data/processed/` |
| `fact_order_items`  | fact_order_items.csv  | `data/processed/` |
| `dim_customers`     | dim_customers.csv     | `data/processed/` |
| `dim_date`          | dim_date.csv          | `data/processed/` |
| `rfm_customers`     | rfm_customers.csv     | `outputs/real/powerbi_tables/` |
| `cohort_retention`  | cohort_retention.csv  | `outputs/real/powerbi_tables/` |

In Power Query set types: `order_date`, `order_month`, `dim_date[date]` -> **Date**; `revenue`, `price` -> **Fixed decimal**; `is_late`, `review_score`, `delivery_days`, `delay_days` -> **Decimal**.
Right-click `dim_date` > **Mark as date table** (column `date`).

## 2. Data model (Model view)

```
dim_date[date]                 1 ──► *  fact_sales_orders[order_date]
dim_customers[customer_unique_id] 1 ──► *  fact_sales_orders[customer_unique_id]
fact_sales_orders[order_id]    1 ──► *  fact_order_items[order_id]
dim_customers[customer_unique_id] 1 ◄──► 1 rfm_customers[customer_unique_id]
cohort_retention               (no relationship - used on its own)
```
All single-direction filters except the 1:1 relationship. Hide the key columns from Report view.

## 3. Calculated column (on `fact_sales_orders`)

```DAX
Delivery Bucket =
SWITCH(
    TRUE(),
    fact_sales_orders[delay_days] <= -7, "1. Early 7+ days",
    fact_sales_orders[delay_days] <= 0,  "2. On time (0-7 days early)",
    fact_sales_orders[delay_days] <= 3,  "3. Late 1-3 days",
    fact_sales_orders[delay_days] <= 7,  "4. Late 4-7 days",
    "5. Late 7+ days"
)
```

## 4. Measures (create a table called `_Measures` to hold them)

```DAX
-- Sales
Total Revenue    = SUM ( fact_sales_orders[revenue] )
Total Orders     = DISTINCTCOUNT ( fact_sales_orders[order_id] )
Avg Order Value  = DIVIDE ( [Total Revenue], [Total Orders] )
Unique Customers = DISTINCTCOUNT ( fact_sales_orders[customer_unique_id] )

Revenue Prev Month = CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
Revenue MoM %      = DIVIDE ( [Total Revenue] - [Revenue Prev Month], [Revenue Prev Month] )
Revenue YTD        = TOTALYTD ( [Total Revenue], dim_date[date] )

Category Revenue   = SUM ( fact_order_items[price] )
Category Share %   = DIVIDE ( [Category Revenue], CALCULATE ( [Category Revenue], ALL ( fact_order_items[category_en] ) ) )

-- Customers
New Customers       = CALCULATE ( DISTINCTCOUNT ( fact_sales_orders[customer_unique_id] ), fact_sales_orders[customer_type] = "New" )
Returning Customers = CALCULATE ( DISTINCTCOUNT ( fact_sales_orders[customer_unique_id] ), fact_sales_orders[customer_type] = "Returning" )
Repeat Customers    = CALCULATE ( DISTINCTCOUNT ( dim_customers[customer_unique_id] ), dim_customers[is_repeat_customer] = 1 )
Repeat Purchase Rate = DIVIDE ( [Repeat Customers], DISTINCTCOUNT ( dim_customers[customer_unique_id] ) )

-- Retention (cohort matrix)
Cohort Retention % =
DIVIDE (
    SUM ( cohort_retention[active_customers] ),
    SUMX ( VALUES ( cohort_retention[cohort_month] ), CALCULATE ( MAX ( cohort_retention[cohort_size] ) ) )
)

-- RFM
Segment Customers = DISTINCTCOUNT ( rfm_customers[customer_unique_id] )
Segment Revenue   = SUM ( rfm_customers[monetary] )
Segment Revenue % = DIVIDE ( [Segment Revenue], CALCULATE ( [Segment Revenue], ALL ( rfm_customers[segment] ) ) )

-- Delivery & satisfaction
Avg Delivery Days  = AVERAGE ( fact_sales_orders[delivery_days] )
Late Delivery %    = AVERAGE ( fact_sales_orders[is_late] )
Avg Review Score   = AVERAGE ( fact_sales_orders[review_score] )
```

Format: revenue/AOV as `R$ #,0`; percentages as `0.0%`; scores as `0.00`.

## 5. Page 1 - Sales Overview

| Area | Visual | Fields |
|---|---|---|
| Top row | 4 **Cards** | Total Revenue, Total Orders, Avg Order Value, Unique Customers |
| Left | **Line + column chart** | Axis `dim_date[year_month]`; columns = Total Revenue, line = Revenue MoM % |
| Middle | **Bar chart** (top 10 filter) | `fact_order_items[category_en]` by Category Revenue |
| Right | **Filled map or bar chart** | `customer_state` by Total Revenue |
| Bottom | **Table** (Top N = 10) | `fact_order_items[product_id]`, `category_en`, Category Revenue |
| Slicers | Year, State, Category | `dim_date[year]`, `customer_state`, `category_en` |

## 6. Page 2 - Customer Insights

| Area | Visual | Fields |
|---|---|---|
| Top row | 4 **Cards** | Repeat Purchase Rate, Avg Review Score, Late Delivery %, Avg Delivery Days |
| Left | **Stacked column** | Axis `year_month`; values New Customers, Returning Customers |
| Middle | **Matrix** (cohort heatmap) | Rows `cohort_month`, Columns `period`, Values Cohort Retention %; conditional formatting > Background colour scale |
| Right | **Donut / bar** | `rfm_customers[segment]` by Segment Revenue % |
| Bottom left | **Clustered column** | `Delivery Bucket` by Avg Review Score |
| Bottom right | **Table** | Segment, Segment Customers, Segment Revenue, Segment Revenue % |
| Slicers | Year, State, RFM segment | |

Add a **text box** with 3 findings written from YOUR real results (see README > "Findings template").

## 7. Polish checklist
- One colour palette, consistent fonts, titles that state the insight ("Late deliveries cut ratings by X points") rather than the chart type.
- Turn on tooltips; sync the Year slicer across both pages (View > Sync slicers).
- Hide helper columns/tables. Name pages "Sales Overview" and "Customer Insights".
- Export a 2-page PDF/PNG preview and save it in `/outputs` for your GitHub README.
