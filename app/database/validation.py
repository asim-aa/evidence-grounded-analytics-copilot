from typing import Any

import duckdb

from app.config import ANALYTICAL_TABLE_NAME


def _fetch_scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> Any:
    """
    Execute a query expected to return one row with one value.
    """
    result = connection.execute(query).fetchone()

    if result is None:
        raise RuntimeError("Validation query returned no result.")

    return result[0]


def validate_analytical_table(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> dict[str, Any]:
    """
    Validate row grain, identifiers, numeric ranges, and basic data integrity.

    The analytical table should contain exactly one row per
    (order_id, order_item_id) pair.
    """

    row_count = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            """,
        )
    )

    unique_order_item_keys = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT
                    order_id,
                    order_item_id
                FROM {table_name}
            )
            """,
        )
    )

    duplicate_order_item_keys = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT
                    order_id,
                    order_item_id,
                    COUNT(*) AS key_count
                FROM {table_name}
                GROUP BY
                    order_id,
                    order_item_id
                HAVING COUNT(*) > 1
            )
            """,
        )
    )

    distinct_orders = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(DISTINCT order_id)
            FROM {table_name}
            """,
        )
    )

    item_revenue = float(
        _fetch_scalar(
            connection,
            f"""
            SELECT COALESCE(ROUND(SUM(item_price), 2), 0)
            FROM {table_name}
            """,
        )
    )

    freight_revenue = float(
        _fetch_scalar(
            connection,
            f"""
            SELECT COALESCE(ROUND(SUM(freight_value), 2), 0)
            FROM {table_name}
            """,
        )
    )

    null_order_ids = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE order_id IS NULL
            """,
        )
    )

    null_order_item_ids = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE order_item_id IS NULL
            """,
        )
    )

    null_product_ids = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE product_id IS NULL
            """,
        )
    )

    invalid_prices = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE item_price < 0
               OR freight_value < 0
               OR item_total_value < 0
            """,
        )
    )

    invalid_review_scores = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE average_review_score IS NOT NULL
              AND (
                  average_review_score < 1
                  OR average_review_score > 5
              )
            """,
        )
    )

    invalid_delivery_days = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE delivery_days IS NOT NULL
              AND delivery_days < 0
            """,
        )
    )

    grain_is_valid = (
        row_count == unique_order_item_keys
        and duplicate_order_item_keys == 0
        and null_order_ids == 0
        and null_order_item_ids == 0
    )

    return {
        "row_count": row_count,
        "unique_order_item_keys": unique_order_item_keys,
        "duplicate_order_item_keys": duplicate_order_item_keys,
        "distinct_orders": distinct_orders,
        "item_revenue": item_revenue,
        "freight_revenue": freight_revenue,
        "null_order_ids": null_order_ids,
        "null_order_item_ids": null_order_item_ids,
        "null_product_ids": null_product_ids,
        "invalid_prices": invalid_prices,
        "invalid_review_scores": invalid_review_scores,
        "invalid_delivery_days": invalid_delivery_days,
        "grain_is_valid": grain_is_valid,
    }


def print_validation_report(
    validation: dict[str, Any],
) -> None:
    """
    Print a readable validation summary.
    """

    print("\nValidation report:")
    print(f"- Grain valid: {validation['grain_is_valid']}")
    print(f"- Rows: {validation['row_count']:,}")
    print(f"- Unique order-item keys: {validation['unique_order_item_keys']:,}")
    print(f"- Duplicate order-item keys: {validation['duplicate_order_item_keys']:,}")
    print(f"- Distinct orders: {validation['distinct_orders']:,}")
    print(f"- Item revenue: {validation['item_revenue']:,.2f}")
    print(f"- Freight revenue: {validation['freight_revenue']:,.2f}")
    print(f"- Null order IDs: {validation['null_order_ids']:,}")
    print(f"- Null order-item IDs: {validation['null_order_item_ids']:,}")
    print(f"- Null product IDs: {validation['null_product_ids']:,}")
    print(f"- Invalid prices: {validation['invalid_prices']:,}")
    print(f"- Invalid review scores: {validation['invalid_review_scores']:,}")
    print(f"- Invalid delivery durations: {validation['invalid_delivery_days']:,}")
