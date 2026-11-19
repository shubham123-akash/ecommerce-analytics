"""
Step 1 - Clean the raw Olist CSVs and build analysis-ready tables.

Outputs (data/processed/):
  fact_orders_all.csv     one row per order (all statuses) + data-quality flags
  fact_sales_orders.csv   one row per VALID sales order (delivered, has items, sane dates)
  fact_order_items.csv    one row per order line, with English category (valid sales orders only)
  dim_customers.csv       one row per real customer (customer_unique_id)
  dim_products.csv        one row per product
  dim_date.csv            calendar table for Power BI time intelligence
  data_quality_report.txt what was cleaned / dropped, and why

Run:  python src/01_clean_data.py            (real data in data/raw)
      python src/01_clean_data.py --sample   (synthetic data)
"""
import numpy as np
import pandas as pd

from config import FILES, get_paths

P = get_paths("Clean Olist data")
report = []


def log(msg):
    print(msg)
    report.append(msg)


def read(key, **kw):
    path = P.raw / FILES[key]
    if not path.exists():
        raise SystemExit(f"Missing file: {path}\nDownload the Olist dataset or run with --sample.")
    return pd.read_csv(path, **kw)


# ------------------------------------------------------------------ load
order_dates = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
               "order_delivered_customer_date", "order_estimated_delivery_date"]
orders = read("orders", parse_dates=order_dates)
customers = read("customers", dtype={"customer_zip_code_prefix": str})
items = read("items", parse_dates=["shipping_limit_date"])
products = read("products")
reviews = read("reviews", parse_dates=["review_creation_date", "review_answer_timestamp"])
translation = read("translation") if (P.raw / FILES["translation"]).exists() else None

log("== RAW ROW COUNTS ==")
for name, df in [("orders", orders), ("customers", customers), ("order_items", items),
                 ("products", products), ("order_reviews", reviews)]:
    log(f"{name:<14}{len(df):>9,}")

# ------------------------------------------------------------------ de-duplicate
before = len(orders)
orders = orders.drop_duplicates("order_id")
customers = customers.drop_duplicates("customer_id")
items = items.drop_duplicates(["order_id", "order_item_id"])
products = products.drop_duplicates("product_id")
log(f"\nDuplicate orders removed: {before - len(orders)}")

# ------------------------------------------------------------------ products
products = products.rename(columns={"product_name_lenght": "product_name_length",
                                    "product_description_lenght": "product_description_length"})
if translation is not None:
    products = products.merge(translation, on="product_category_name", how="left")
    products["category_en"] = products["product_category_name_english"].fillna(products["product_category_name"])
    products = products.drop(columns="product_category_name_english")
else:
    products["category_en"] = products["product_category_name"]
n_missing_cat = int(products["category_en"].isna().sum())
products["category_en"] = products["category_en"].fillna("unknown")
log(f"Products with missing category -> 'unknown': {n_missing_cat}")

# ------------------------------------------------------------------ reviews: keep latest per order
n_dup_rev = int(reviews.duplicated("order_id").sum())
reviews = reviews[reviews["review_score"].between(1, 5)]
reviews = (reviews.sort_values(["order_id", "review_answer_timestamp", "review_creation_date"])
           .drop_duplicates("order_id", keep="last")[["order_id", "review_score"]])
log(f"Orders with multiple reviews (kept latest only): {n_dup_rev}")

# ------------------------------------------------------------------ order-level facts
item_totals = items.groupby("order_id").agg(
    items_count=("order_item_id", "count"),
    revenue=("price", "sum"),
    freight=("freight_value", "sum"),
).reset_index()

fact = (orders
        .merge(customers[["customer_id", "customer_unique_id", "customer_city", "customer_state"]],
               on="customer_id", how="left")
        .merge(item_totals, on="order_id", how="left")
        .merge(reviews, on="order_id", how="left"))

fact["order_date"] = fact["order_purchase_timestamp"].dt.normalize()
fact["order_month"] = fact["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
fact["order_year"] = fact["order_purchase_timestamp"].dt.year

secs_per_day = 86400.0
delivered_ts = fact["order_delivered_customer_date"]
fact["delivery_days"] = ((delivered_ts - fact["order_purchase_timestamp"]).dt.total_seconds() / secs_per_day).round(1)
fact["delay_days"] = ((delivered_ts - fact["order_estimated_delivery_date"]).dt.total_seconds() / secs_per_day).round(1)
# is_late: 1 / 0 for orders with a delivery date, blank otherwise
fact["is_late"] = np.where(delivered_ts.notna(), (delivered_ts > fact["order_estimated_delivery_date"]).astype(float), np.nan)

# ------------------------------------------------------------------ data-quality flags
fact["flag_no_items"] = fact["revenue"].isna()
fact["flag_delivered_no_date"] = (fact["order_status"] == "delivered") & delivered_ts.isna()
fact["flag_delivered_before_purchase"] = delivered_ts.notna() & (delivered_ts < fact["order_purchase_timestamp"])
fact["is_sales_order"] = (
    (fact["order_status"] == "delivered")
    & fact["revenue"].notna()
    & delivered_ts.notna()
    & (delivered_ts >= fact["order_purchase_timestamp"])
)

log("\n== STATUS BREAKDOWN ==")
log(fact["order_status"].value_counts().to_string())
log("\n== DATA QUALITY FLAGS ==")
log(f"Orders with no items (no revenue):          {int(fact.flag_no_items.sum()):,}")
log(f"Delivered but missing delivery date:        {int(fact.flag_delivered_no_date.sum()):,}")
log(f"Delivered before purchase (invalid dates):  {int(fact.flag_delivered_before_purchase.sum()):,}")
log(f"Orders without a review:                    {int(fact.review_score.isna().sum()):,}")
log(f"\nValid sales orders kept for analysis:       {int(fact.is_sales_order.sum()):,} of {len(fact):,}")

# ------------------------------------------------------------------ customer sequence (new vs returning)
sales = fact[fact["is_sales_order"]].copy()
sales = sales.sort_values(["order_purchase_timestamp", "order_id"])
sales["customer_order_number"] = sales.groupby("customer_unique_id").cumcount() + 1
sales["customer_type"] = np.where(sales["customer_order_number"] == 1, "New", "Returning")
fact = fact.merge(sales[["order_id", "customer_order_number", "customer_type"]], on="order_id", how="left")
sales = fact[fact["is_sales_order"]].copy()

# ------------------------------------------------------------------ order lines (valid sales orders only)
lines = (items.merge(sales[["order_id", "customer_unique_id", "order_date", "order_month", "customer_state"]],
                     on="order_id", how="inner")
         .merge(products[["product_id", "category_en"]], on="product_id", how="left"))
lines["category_en"] = lines["category_en"].fillna("unknown")

# ------------------------------------------------------------------ customer dimension
dim_customers = (sales.groupby("customer_unique_id")
                 .agg(first_order_date=("order_date", "min"),
                      last_order_date=("order_date", "max"),
                      total_orders=("order_id", "nunique"),
                      total_revenue=("revenue", "sum"),
                      avg_order_value=("revenue", "mean"),
                      customer_state=("customer_state", "last"))
                 .reset_index())
dim_customers["is_repeat_customer"] = (dim_customers["total_orders"] >= 2).astype(int)
dim_customers["total_revenue"] = dim_customers["total_revenue"].round(2)
dim_customers["avg_order_value"] = dim_customers["avg_order_value"].round(2)

# ------------------------------------------------------------------ calendar dimension
cal = pd.DataFrame({"date": pd.date_range(fact["order_date"].min().replace(day=1),
                                          fact["order_date"].max() + pd.offsets.MonthEnd(0))})
cal["year"] = cal["date"].dt.year
cal["quarter"] = "Q" + cal["date"].dt.quarter.astype(str)
cal["month_num"] = cal["date"].dt.month
cal["month_name"] = cal["date"].dt.strftime("%b")
cal["year_month"] = cal["date"].dt.strftime("%Y-%m")
cal["weekday"] = cal["date"].dt.strftime("%a")
cal["weekday_num"] = cal["date"].dt.weekday + 1

# ------------------------------------------------------------------ save
out = P.processed
fact.to_csv(out / "fact_orders_all.csv", index=False)
sales.to_csv(out / "fact_sales_orders.csv", index=False)
lines.to_csv(out / "fact_order_items.csv", index=False)
dim_customers.to_csv(out / "dim_customers.csv", index=False)
products.to_csv(out / "dim_products.csv", index=False)
cal.to_csv(out / "dim_date.csv", index=False)
(out / "data_quality_report.txt").write_text("\n".join(report), encoding="utf-8")
log(f"\nSaved cleaned tables to {out}")
