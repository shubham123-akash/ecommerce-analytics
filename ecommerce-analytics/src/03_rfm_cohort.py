"""
Step 3 - Customer retention: repeat rate, monthly cohort analysis, RFM segmentation.

RFM notes
  * Recency   = days since last order (snapshot = last order date + 1 day)
  * Frequency = number of delivered orders
  * Monetary  = total product revenue (excludes freight)
  * R and M are scored 1-5 by rank quintile. F is capped at 5 because in Olist ~97% of
    customers order only once, so frequency quintiles would not be meaningful.
  * Segments are rule-based and evaluated top to bottom (first match wins).

Run:  python src/03_rfm_cohort.py [--sample]
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import get_paths

P = get_paths("RFM + cohort analysis")
sales = pd.read_csv(P.processed / "fact_sales_orders.csv",
                    parse_dates=["order_purchase_timestamp", "order_date", "order_month"])

# ================================================================ RETENTION BASICS
n_cust = sales["customer_unique_id"].nunique()
orders_per_cust = sales.groupby("customer_unique_id")["order_id"].nunique()
repeat_rate = (orders_per_cust >= 2).mean() * 100
print(f"Customers: {n_cust:,} | repeat purchase rate: {repeat_rate:.2f}%")

# ================================================================ COHORT ANALYSIS
act = sales[["customer_unique_id", "order_month"]].drop_duplicates()
first_month = act.groupby("customer_unique_id")["order_month"].transform("min")
act = act.assign(cohort_month=first_month)
act["period"] = ((act["order_month"].dt.year - act["cohort_month"].dt.year) * 12
                 + (act["order_month"].dt.month - act["cohort_month"].dt.month))

cohort = (act.groupby(["cohort_month", "period"])["customer_unique_id"].nunique()
          .rename("active_customers").reset_index())
sizes = cohort[cohort["period"] == 0].set_index("cohort_month")["active_customers"].rename("cohort_size")
cohort = cohort.merge(sizes, on="cohort_month")
cohort["retention_pct"] = (cohort["active_customers"] / cohort["cohort_size"] * 100).round(2)
cohort.to_csv(P.powerbi / "cohort_retention.csv", index=False)

matrix = cohort.pivot(index="cohort_month", columns="period", values="retention_pct")
matrix = matrix.loc[:, matrix.columns <= 12]
print("\nAverage retention by months since first purchase (all cohorts, simple mean):")
print(matrix.mean().round(2).to_string())

fig, ax = plt.subplots(figsize=(11, 6))
vmax = max(1.0, np.nanmax(matrix.iloc[:, 1:].values)) if matrix.shape[1] > 1 else 1
im = ax.imshow(matrix.values, cmap="Blues", aspect="auto", vmin=0, vmax=vmax)
ax.set_xticks(range(matrix.shape[1])); ax.set_xticklabels(matrix.columns)
ax.set_yticks(range(matrix.shape[0])); ax.set_yticklabels(matrix.index.strftime("%Y-%m"))
ax.set(title="Monthly cohort retention (%) - month 0 omitted from colour scale",
       xlabel="Months since first purchase", ylabel="Cohort (first purchase month)")
for i in range(matrix.shape[0]):
    for j in range(1, matrix.shape[1]):
        v = matrix.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7)
fig.colorbar(im, ax=ax, label="Retention %")
fig.tight_layout(); fig.savefig(P.charts / "05_cohort_retention.png"); plt.close(fig)

# ================================================================ RFM
snapshot = sales["order_purchase_timestamp"].max().normalize() + pd.Timedelta(days=1)
rfm = (sales.groupby("customer_unique_id")
       .agg(last_order=("order_purchase_timestamp", "max"),
            frequency=("order_id", "nunique"),
            monetary=("revenue", "sum"))
       .reset_index().sort_values("customer_unique_id").reset_index(drop=True))
rfm["recency_days"] = (snapshot - rfm["last_order"].dt.normalize()).dt.days
rfm["monetary"] = rfm["monetary"].round(2)

rfm["r_score"] = pd.qcut(rfm["recency_days"].rank(method="first", ascending=False), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["f_score"] = rfm["frequency"].clip(upper=5).astype(int)
rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["rfm_score"] = rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)

r, f, m = rfm["r_score"], rfm["f_score"], rfm["m_score"]
conditions = [
    (f >= 2) & (r >= 4),               # repeat buyers who bought recently
    (f >= 2) & (r <= 3),               # repeat buyers who have gone quiet
    (f == 1) & (r >= 4) & (m >= 4),    # recent first-time big spenders
    (f == 1) & (r >= 4),               # recent first-time buyers
    (f == 1) & (r <= 3) & (m >= 4),    # one-time big spenders who haven't come back
    (f == 1) & (r == 3),
    (f == 1) & (r == 2),
]
names = ["Champions", "Loyal Repeat Buyers", "Recent High Spenders", "New Customers",
         "High-Value At Risk", "Needs Attention", "Hibernating"]
rfm["segment"] = np.select(conditions, names, default="Lost")
rfm = rfm.drop(columns="last_order")
rfm.to_csv(P.powerbi / "rfm_customers.csv", index=False)

seg = (rfm.groupby("segment")
       .agg(customers=("customer_unique_id", "count"), revenue=("monetary", "sum"),
            avg_recency_days=("recency_days", "mean"), avg_orders=("frequency", "mean"),
            avg_spend=("monetary", "mean"))
       .reset_index())
seg["pct_customers"] = (seg["customers"] / seg["customers"].sum() * 100).round(2)
seg["pct_revenue"] = (seg["revenue"] / seg["revenue"].sum() * 100).round(2)
seg = seg.round(2).sort_values("revenue", ascending=False)
seg.to_csv(P.powerbi / "rfm_segment_summary.csv", index=False)
print("\nRFM segments:\n", seg.to_string(index=False))

fig, ax = plt.subplots(figsize=(8, 4.5))
s = seg.sort_values("pct_revenue")
ax.barh(s["segment"], s["pct_revenue"], color="#9467bd")
ax.set(title="Share of revenue by RFM segment", xlabel="% of revenue")
for i, v in enumerate(s["pct_revenue"]):
    ax.text(v + .3, i, f"{v:.1f}%", va="center")
fig.tight_layout(); fig.savefig(P.charts / "06_rfm_segments.png"); plt.close(fig)
print(f"\nSaved RFM + cohort outputs to {P.powerbi}")
