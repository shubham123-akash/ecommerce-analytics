"""Shared paths + CLI flag. Every script accepts --sample to run on the synthetic test data."""
import argparse
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "translation": "product_category_name_translation.csv",
}


def get_paths(description: str = "") -> SimpleNamespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--sample", action="store_true",
                        help="use synthetic data in data/sample instead of real data in data/raw")
    args = parser.parse_args()

    tag = "sample" if args.sample else "real"
    paths = SimpleNamespace(
        sample=args.sample,
        raw=ROOT / "data" / ("sample" if args.sample else "raw"),
        processed=ROOT / "data" / ("processed_sample" if args.sample else "processed"),
        charts=ROOT / "outputs" / tag / "charts",
        powerbi=ROOT / "outputs" / tag / "powerbi_tables",
    )
    for p in (paths.processed, paths.charts, paths.powerbi):
        p.mkdir(parents=True, exist_ok=True)
    return paths
