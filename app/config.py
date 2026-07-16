from pathlib import Path


RAW_DATA_DIRECTORY = Path("data/raw")
PROCESSED_DATA_DIRECTORY = Path("data/processed")

DATABASE_PATH = PROCESSED_DATA_DIRECTORY / "olist_analytics.duckdb"

ANALYTICAL_TABLE_NAME = "order_items_analytics"


REQUIRED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}
