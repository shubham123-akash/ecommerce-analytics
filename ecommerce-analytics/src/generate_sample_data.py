"""
Generate a SYNTHETIC dataset with the same schema as the Olist public dataset.

Purpose: lets you test the whole pipeline (Python, SQL, Power BI) before downloading the
real data. Numbers produced from this data are NOT real findings - never put them on a resume.

Usage:  python src/generate_sample_data.py
"""
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = Path(__file__).resolve().parents[1] / "data" / "sample"
OUT.mkdir(parents=True, exist_ok=True)

N_ORDERS = 8000
N_PRODUCTS = 300
N_SELLERS = 60


def hex_ids(n):
    return [uuid.UUID(bytes=rng.bytes(16)).hex for _ in range(n)]


# ---------- customers ----------
n_unique = int(N_ORDERS * 0.96)  # ~4% of orders come from repeat customers
unique_ids = hex_ids(n_unique)
states = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES", "PE", "CE"]
state_p = [.42, .13, .12, .06, .06, .04, .04, .03, .03, .03, .02, .02]
cust_state = dict(zip(unique_ids, rng.choice(states, n_unique, p=state_p)))
cust_zip = dict(zip(unique_ids, rng.integers(1000, 99999, n_unique)))

order_owner = list(unique_ids) + list(rng.choice(unique_ids, N_ORDERS - n_unique))
rng.shuffle(order_owner)

order_ids = hex_ids(N_ORDERS)
customer_ids = hex_ids(N_ORDERS)  # NOTE: customer_id is per ORDER, like in Olist

customers = pd.DataFrame({
    "customer_id": customer_ids,
    "customer_unique_id": order_owner,
    "customer_zip_code_prefix": [cust_zip[u] for u in order_owner],
    "customer_city": [f"city_{cust_zip[u] % 80}" for u in order_owner],
    "customer_state": [cust_state[u] for u in order_owner],
})

# ---------- orders ----------
days = pd.date_range("2017-01-01", "2018-08-31", freq="D")
w = 1 + np.arange(len(days)) / 200.0  # business grows over time
day_pick = rng.choice(len(days), N_ORDERS, p=w / w.sum())
purchase = days[day_pick] + pd.to_timedelta(rng.integers(0, 86400, N_ORDERS), unit="s")

status = rng.choice(["delivered", "shipped", "canceled", "unavailable", "processing", "invoiced"],
                    N_ORDERS, p=[.965, .01, .01, .005, .005, .005])
is_del = status == "delivered"

approved = purchase + pd.to_timedelta(rng.exponential(10, N_ORDERS), unit="h")
carrier = approved + pd.to_timedelta(rng.uniform(1, 3, N_ORDERS), unit="D")

state_arr = np.array([cust_state[u] for u in order_owner])
remote_bonus = np.where(np.isin(state_arr, ["BA", "PE", "CE"]), 4, 0)
transit = rng.gamma(4, 3, N_ORDERS) + remote_bonus
extra_delay = np.where(rng.random(N_ORDERS) < 0.07, rng.gamma(2, 6, N_ORDERS), 0)
delivered_ts = purchase + pd.to_timedelta(transit + extra_delay, unit="D")
estimated = (purchase + pd.to_timedelta(rng.normal(24, 4, N_ORDERS).clip(10), unit="D")).normalize()

orders = pd.DataFrame({
    "order_id": order_ids,
    "customer_id": customer_ids,
    "order_status": status,
    "order_purchase_timestamp": purchase,
    "order_approved_at": approved,
    "order_delivered_carrier_date": carrier,
    "order_delivered_customer_date": delivered_ts,
    "order_estimated_delivery_date": estimated,
})
orders.loc[status == "processing", "order_delivered_carrier_date"] = pd.NaT
orders.loc[~is_del, "order_delivered_customer_date"] = pd.NaT

# ---------- products ----------
cats_pt_en = {
    "cama_mesa_banho": "bed_bath_table", "beleza_saude": "health_beauty",
    "esporte_lazer": "sports_leisure", "informatica_acessorios": "computers_accessories",
    "moveis_decoracao": "furniture_decor", "utilidades_domesticas": "housewares",
    "relogios_presentes": "watches_gifts", "telefonia": "telephony", "automotivo": "auto",
    "brinquedos": "toys", "cool_stuff": "cool_stuff", "perfumaria": "perfumery",
    "bebes": "baby", "eletronicos": "electronics", "papelaria": "stationery",
}
cat_list = list(cats_pt_en)
cat_w = rng.dirichlet(np.ones(len(cat_list)) * 2)
product_ids = hex_ids(N_PRODUCTS)
prod_cat = rng.choice(cat_list, N_PRODUCTS, p=cat_w).astype(object)
prod_cat[rng.random(N_PRODUCTS) < 0.02] = None  # missing categories exist in the real data
base_price = rng.lognormal(4.3, 0.8, N_PRODUCTS).round(2)

products = pd.DataFrame({
    "product_id": product_ids,
    "product_category_name": prod_cat,
    "product_name_lenght": rng.integers(20, 70, N_PRODUCTS),
    "product_description_lenght": rng.integers(100, 2000, N_PRODUCTS),
    "product_photos_qty": rng.integers(1, 8, N_PRODUCTS),
    "product_weight_g": rng.integers(100, 8000, N_PRODUCTS),
    "product_length_cm": rng.integers(10, 60, N_PRODUCTS),
    "product_height_cm": rng.integers(2, 40, N_PRODUCTS),
    "product_width_cm": rng.integers(10, 50, N_PRODUCTS),
})

# ---------- order items ----------
pop = 1 / np.arange(1, N_PRODUCTS + 1) ** 0.8
pop /= pop.sum()
seller_ids = hex_ids(N_SELLERS)
rows = []
for i, oid in enumerate(order_ids):
    if status[i] == "unavailable" and rng.random() < 0.5:
        continue  # some orders have no items in the real data too
    n_items = rng.choice([1, 2, 3, 4], p=[.88, .09, .025, .005])
    for k in range(1, n_items + 1):
        p_idx = rng.choice(N_PRODUCTS, p=pop)
        price = round(float(base_price[p_idx] * rng.uniform(.9, 1.1)), 2)
        rows.append({
            "order_id": oid, "order_item_id": k, "product_id": product_ids[p_idx],
            "seller_id": seller_ids[rng.integers(N_SELLERS)],
            "shipping_limit_date": purchase[i] + pd.Timedelta(days=3),
            "price": price,
            "freight_value": round(max(0.0, 5 + price * 0.1 + float(rng.normal(0, 2))), 2),
        })
items = pd.DataFrame(rows)

# ---------- reviews (late delivery -> worse score) ----------
delay = (orders["order_delivered_customer_date"] - orders["order_estimated_delivery_date"]).dt.total_seconds() / 86400
rev_rows = []
for i, oid in enumerate(order_ids):
    if rng.random() > 0.95:
        continue
    if not is_del[i]:
        p = [.5, .1, .1, .1, .2]
    elif delay.iloc[i] > 7:
        p = [.55, .2, .1, .08, .07]
    elif delay.iloc[i] > 0:
        p = [.35, .2, .15, .15, .15]
    else:
        p = [.04, .02, .08, .2, .66]
    score = int(rng.choice([1, 2, 3, 4, 5], p=p))
    base = orders["order_delivered_customer_date"].iloc[i]
    if pd.isna(base):
        base = purchase[i] + pd.Timedelta(days=10)
    created = base + pd.Timedelta(days=int(rng.integers(0, 3)))
    answered = created + pd.Timedelta(hours=int(rng.integers(1, 72)))
    for _ in range(2 if rng.random() < 0.01 else 1):  # a few duplicate reviews
        rev_rows.append({
            "review_id": uuid.UUID(bytes=rng.bytes(16)).hex, "order_id": oid, "review_score": score,
            "review_comment_title": None, "review_comment_message": None,
            "review_creation_date": created.normalize(), "review_answer_timestamp": answered,
        })
reviews = pd.DataFrame(rev_rows)

translation = pd.DataFrame({"product_category_name": list(cats_pt_en),
                            "product_category_name_english": list(cats_pt_en.values())})

orders.to_csv(OUT / "olist_orders_dataset.csv", index=False)
customers.to_csv(OUT / "olist_customers_dataset.csv", index=False)
items.to_csv(OUT / "olist_order_items_dataset.csv", index=False)
products.to_csv(OUT / "olist_products_dataset.csv", index=False)
reviews.to_csv(OUT / "olist_order_reviews_dataset.csv", index=False)
translation.to_csv(OUT / "product_category_name_translation.csv", index=False)
print(f"Synthetic sample written to {OUT}")
print(f"orders={len(orders):,} items={len(items):,} reviews={len(reviews):,} "
      f"customers(unique)={customers.customer_unique_id.nunique():,}")
