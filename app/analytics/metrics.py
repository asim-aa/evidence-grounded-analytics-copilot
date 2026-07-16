from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from app.config import ANALYTICAL_TABLE_NAME, DATABASE_PATH


def open_analytics_connection() -> duckdb.DuckDBPyConnection:
    """
    Open the existing analytical DuckDB database in read-only mode.

    Raises:
        FileNotFoundError: If the analytical database has not been built.
    """
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Analytical database not found: {DATABASE_PATH}\n"
            "Run `uv run python -m app.database.ingestion` first."
        )

    return duckdb.connect(
        str(DATABASE_PATH),
        read_only=True,
    )


def _fetch_scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> Any:
    """
    Execute a query expected to return one scalar value.
    """
    result = connection.execute(query).fetchone()

    if result is None:
        raise RuntimeError("Metric query returned no result.")

    return result[0]


def calculate_item_revenue(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> float:
    """
    Calculate total item revenue, excluding freight.

    item_price exists at the order-item grain and can therefore be
    summed directly across the analytical table.
    """
    value = _fetch_scalar(
        connection,
        f"""
        SELECT
            COALESCE(
                ROUND(SUM(item_price), 2),
                0
            )
        FROM {table_name}
        """,
    )

    return float(value)


def calculate_freight_value(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> float:
    """
    Calculate total freight value.

    freight_value exists at the order-item grain and can therefore be
    summed directly.
    """
    value = _fetch_scalar(
        connection,
        f"""
        SELECT
            COALESCE(
                ROUND(SUM(freight_value), 2),
                0
            )
        FROM {table_name}
        """,
    )

    return float(value)


def calculate_order_count(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> int:
    """
    Count distinct orders in the analytical table.
    """
    value = _fetch_scalar(
        connection,
        f"""
        SELECT COUNT(DISTINCT order_id)
        FROM {table_name}
        """,
    )

    return int(value)


def calculate_average_order_value(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> float:
    """
    Calculate average item revenue per order.

    Revenue is first summed within each order before averaging across
    orders. This prevents multi-item orders from being overweighted.
    """
    value = _fetch_scalar(
        connection,
        f"""
        WITH order_revenue AS (
            SELECT
                order_id,
                SUM(item_price) AS revenue
            FROM {table_name}
            GROUP BY order_id
        )

        SELECT
            COALESCE(
                ROUND(AVG(revenue), 2),
                0
            )
        FROM order_revenue
        """,
    )

    return float(value)


def calculate_late_delivery_rate(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> float:
    """
    Calculate the percentage of delivered orders that arrived late.

    is_late_delivery is repeated across item rows, so the query first
    reduces the table to one row per order.
    """
    value = _fetch_scalar(
        connection,
        f"""
        WITH order_delivery AS (
            SELECT
                order_id,
                BOOL_OR(is_late_delivery) AS is_late_delivery
            FROM {table_name}
            GROUP BY order_id
        )

        SELECT
            COALESCE(
                ROUND(
                    100.0 * AVG(
                        CASE
                            WHEN is_late_delivery = TRUE THEN 1
                            WHEN is_late_delivery = FALSE THEN 0
                            ELSE NULL
                        END
                    ),
                    2
                ),
                0
            )
        FROM order_delivery
        """,
    )

    return float(value)


def calculate_average_review_score(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> float:
    """
    Calculate the average review score across reviewed orders.

    average_review_score is repeated across item rows, so the query
    first reduces the table to one row per order.
    """
    value = _fetch_scalar(
        connection,
        f"""
        WITH order_reviews AS (
            SELECT
                order_id,
                MAX(average_review_score) AS review_score
            FROM {table_name}
            GROUP BY order_id
        )

        SELECT
            COALESCE(
                ROUND(AVG(review_score), 2),
                0
            )
        FROM order_reviews
        WHERE review_score IS NOT NULL
        """,
    )

    return float(value)


def get_monthly_revenue_trend(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> pd.DataFrame:
    """
    Return monthly item revenue, order count, and month-over-month growth.

    Incomplete edge months remain in the output. Later analysis modules
    may choose whether to exclude them from comparisons.
    """
    return connection.execute(
        f"""
        WITH monthly_metrics AS (
            SELECT
                purchase_month_start,
                ROUND(SUM(item_price), 2) AS item_revenue,
                COUNT(DISTINCT order_id) AS order_count
            FROM {table_name}
            WHERE purchase_month_start IS NOT NULL
            GROUP BY purchase_month_start
        ),

        with_previous_month AS (
            SELECT
                purchase_month_start,
                item_revenue,
                order_count,
                LAG(item_revenue) OVER (
                    ORDER BY purchase_month_start
                ) AS previous_month_revenue
            FROM monthly_metrics
        )

        SELECT
            purchase_month_start,
            item_revenue,
            order_count,
            ROUND(
                100.0 * (
                    item_revenue - previous_month_revenue
                ) / NULLIF(previous_month_revenue, 0),
                2
            ) AS month_over_month_growth_percentage
        FROM with_previous_month
        ORDER BY purchase_month_start
        """
    ).fetchdf()


def get_business_kpis(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> dict[str, float | int]:
    """
    Return the core business KPIs in one consistent structure.
    """
    return {
        "item_revenue": calculate_item_revenue(
            connection,
            table_name,
        ),
        "freight_value": calculate_freight_value(
            connection,
            table_name,
        ),
        "order_count": calculate_order_count(
            connection,
            table_name,
        ),
        "average_order_value": calculate_average_order_value(
            connection,
            table_name,
        ),
        "late_delivery_rate_percentage": calculate_late_delivery_rate(
            connection,
            table_name,
        ),
        "average_review_score": calculate_average_review_score(
            connection,
            table_name,
        ),
    }


def print_metrics_summary(
    metrics: dict[str, float | int],
) -> None:
    """
    Print the core business metrics in a readable format.
    """
    print("Core business metrics")
    print(f"- Item revenue: {metrics['item_revenue']:,.2f}")
    print(f"- Freight value: {metrics['freight_value']:,.2f}")
    print(f"- Orders: {metrics['order_count']:,}")
    print(f"- Average order value: {metrics['average_order_value']:,.2f}")
    print(f"- Late delivery rate: {metrics['late_delivery_rate_percentage']:.2f}%")
    print(f"- Average review score: {metrics['average_review_score']:.2f}")


def main() -> None:
    """
    Calculate and print the initial deterministic metrics.
    """
    connection = open_analytics_connection()

    try:
        metrics = get_business_kpis(connection)
        monthly_trend = get_monthly_revenue_trend(connection)

        print_metrics_summary(metrics)

        print("\nMonthly revenue trend:")
        display_trend = monthly_trend.tail(12).copy()

        display_trend["purchase_month_start"] = display_trend[
            "purchase_month_start"
        ].dt.strftime("%Y-%m")

        print(
            display_trend.to_string(
                index=False,
                formatters={
                    "item_revenue": lambda value: f"{value:,.2f}",
                    "order_count": lambda value: f"{value:,}",
                    "month_over_month_growth_percentage": (
                        lambda value: "N/A" if pd.isna(value) else f"{value:.2f}%"
                    ),
                },
            )
        )
    finally:
        connection.close()

if __name__ == "__main__":
    main()
