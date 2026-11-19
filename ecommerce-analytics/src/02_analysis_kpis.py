"""
Step 2 - Sales, customer and delivery/satisfaction analysis.

Prints the headline KPIs, saves charts to outputs/<real|sample>/charts and
saves Power BI-ready summary tables to outputs/<real|sample>/powerbi_tables.

Run:  python src/02_analysis_kpis.py [--sample]
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import get_paths

P = get_paths("Sales / customer / delivery analysis")
sales = pd.read_csv(P.processed / "fact_sales_orders.csv",
                    parse_dates=["order_purchase_timestamp", "order_date", "order_month"])
lines = pd.read_csv(P.processed / "fact_order_items.csv", parse_dates=["order_month"])
cust = pd.read_csv(P.processed / "dim_customers.csv")

plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})


def money(x):
    return f"R$ {x:,.0f}"


# ================================================================ 1. SALES PERFORMANCE
total_revenue = sales["revenue"].sum()
total_orders = sales["order_id"].nunique()
aov = total_revenue / total_orders

monthly = (sales.groupby("order_month")
           .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
                customers=("customer_unique_id", "nunique"))
           .reset_index())
monthly["aov"] = (monthly["revenue"] / monthly["orders"]).round(2)
monthly["revenue_mom_pct"] = (monthly["revenue"].pct_change() * 100).round(1)

yearly = (sales.groupby("order_year")
          .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
          .reset_index())
yearly["aov"] = (yearly["revenue"] / yearly["orders"]).round(2)

# top products: Olist has no product names, so label = category + short id
prod = (lines.groupby(["product_id", "category_en"])
        .agg(revenue=("price", "sum"), units=("order_item_id", "count"))
        .reset_index().sort_values("revenue", ascending=False))
prod["label"] = prod["category_en"] + " · " + prod["product_id"].str[:6]
top_products = prod.head(10)

cat = (lines.groupby("category_en")
       .agg(revenue=("price", "sum"), units=("order_item_id", "count"),
            orders=("order_id", "nunique"))
       .reset_index().sort_values("revenue", ascending=False))
cat["revenue_share_pct"] = (cat["revenue"] / cat["revenue"].sum() * 100).round(2)
cat["cum_share_pct"] = cat["revenue_share_pct"].cumsum().round(2)

state = (sales.groupby("customer_state")
         .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
              customers=("customer_unique_id", "nunique"))
         .reset_index().sort_values("revenue", ascending=False))

# ================================================================ 2. CUSTOMER ANALYTICS
n_customers = cust["customer_unique_id"].nunique()
repeat_customers = int(cust["is_repeat_customer"].sum())
repeat_rate = repeat_customers / n_customers * 100

new_vs_ret = (sales.groupby(["order_month", "customer_type"])
              .agg(orders=("order_id", "nunique"), customers=("customer_unique_id", "nunique"),
                   revenue=("revenue", "sum"))
              .reset_index())

top_customers = cust.sort_values("total_revenue", ascending=False).head(10)

freq = (cust.groupby("total_orders").size().rename("customers").reset_index())
freq["pct_of_customers"] = (freq["customers"] / n_customers * 100).round(2)

# ================================================================ 3. DELIVERY & SATISFACTION
bins = [-np.inf, -7, 0, 3, 7, np.inf]
labels = ["Early 7+ days", "On time (0-7 days early)", "Late 1-3 days", "Late 4-7 days", "Late 7+ days"]
d = sales.dropna(subset=["delay_days"]).copy()
d["delivery_bucket"] = pd.cut(d["delay_days"], bins=bins, labels=labels, right=True)

avg_delivery = d["delivery_days"].mean()
late_pct = d["is_late"].mean() * 100
rev = d.dropna(subset=["review_score"])
avg_review = rev["review_score"].mean()
corr = rev["delay_days"].corr(rev["review_score"])

delay_vs_review = (rev.groupby("delivery_bucket", observed=True)
                   .agg(orders=("order_id", "nunique"), avg_review=("review_score", "mean"),
                        pct_1_2_star=("review_score", lambda s: (s <= 2).mean() * 100))
                   .round(2).reset_index())
delay_vs_review["delivery_bucket"] = delay_vs_review["delivery_bucket"].astype(str)

monthly_delivery = (d.groupby("order_month")
                    .agg(avg_delivery_days=("delivery_days", "mean"), late_pct=("is_late", lambda s: s.mean() * 100),
                         avg_review=("review_score", "mean"))
                    .round(2).reset_index())

state_delivery = (d.groupby("customer_state")
                  .agg(orders=("order_id", "nunique"), avg_delivery_days=("delivery_days", "mean"),
                       late_pct=("is_late", lambda s: s.mean() * 100), avg_review=("review_score", "mean"))
                  .round(2).reset_index().sort_values("avg_delivery_days", ascending=False))

# ================================================================ KPI summary
kpis = {
    "total_revenue_brl": round(total_revenue, 2),
    "total_orders": int(total_orders),
    "avg_order_value_brl": round(aov, 2),
    "unique_customers": int(n_customers),
    "repeat_customers": repeat_customers,
    "repeat_purchase_rate_pct": round(repeat_rate, 2),
    "avg_delivery_days": round(avg_delivery, 1),
    "late_delivery_pct": round(late_pct, 2),
    "avg_review_score": round(avg_review, 2),
    "corr_delay_days_vs_review": round(corr, 3),
    "top_category": cat.iloc[0]["category_en"],
    "top_category_share_pct": float(cat.iloc[0]["revenue_share_pct"]),
    "top5_categories_share_pct": float(cat["revenue_share_pct"].head(5).sum().round(2)),
}
print("\n=========== HEADLINE KPIs ===========")
for k, v in kpis.items():
    print(f"{k:<30}{v}")
print("\nRating by delivery bucket:\n", delay_vs_review.to_string(index=False))
(P.processed / "kpis.json").write_text(json.dumps(kpis, indent=2))

# ================================================================ Power BI summary tables
tables = {"monthly_sales": monthly, "yearly_sales": yearly, "top_products": top_products,
          "category_sales": cat, "state_sales": state, "new_vs_returning": new_vs_ret,
          "purchase_frequency": freq, "delay_vs_review": delay_vs_review,
          "monthly_delivery": monthly_delivery, "state_delivery": state_delivery}
for name, df in tables.items():
    df.to_csv(P.powerbi / f"{name}.csv", index=False)

# ================================================================ charts
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(monthly["order_month"], monthly["revenue"], marker="o", color="#1f77b4")
ax.set(title="Monthly revenue (delivered orders)", ylabel="Revenue (R$)")
ax.yaxis.set_major_formatter(lambda x, _: f"{x/1000:,.0f}k")
fig.tight_layout(); fig.savefig(P.charts / "01_monthly_revenue.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4.5))
top = cat.head(10).iloc[::-1]
ax.barh(top["category_en"], top["revenue"], color="#2ca02c")
ax.set(title="Top 10 categories by revenue", xlabel="Revenue (R$)")
ax.xaxis.set_major_formatter(lambda x, _: f"{x/1000:,.0f}k")
fig.tight_layout(); fig.savefig(P.charts / "02_top_categories.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4))
piv = new_vs_ret.pivot(index="order_month", columns="customer_type", values="orders").fillna(0)
ax.bar(piv.index, piv.get("New", 0), width=20, label="New", color="#1f77b4")
ax.bar(piv.index, piv.get("Returning", 0), width=20, bottom=piv.get("New", 0), label="Returning", color="#ff7f0e")
ax.set(title="Orders: new vs returning customers", ylabel="Orders"); ax.legend()
fig.tight_layout(); fig.savefig(P.charts / "03_new_vs_returning.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(delay_vs_review["delivery_bucket"], delay_vs_review["avg_review"], color="#d62728")
ax.set(title="Average review score by delivery timeliness", ylabel="Avg review (1-5)", ylim=(0, 5))
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
for i, v in enumerate(delay_vs_review["avg_review"]):
    ax.text(i, v + .05, f"{v:.2f}", ha="center")
fig.tight_layout(); fig.savefig(P.charts / "04_delay_vs_review.png"); plt.close(fig)

print(f"\nCharts  -> {P.charts}\nTables  -> {P.powerbi}")
