from __future__ import annotations

import duckdb
import pandas as pd

from app.analytics.metrics import open_analytics_connection
from app.config import ANALYTICAL_TABLE_NAME


def get_revenue_by_category(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Return item revenue, order count, and revenue contribution by category.

    item_price is an item-level additive measure and may be summed directly.
    """
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than zero.")

    query = f"""
        WITH category_revenue AS (
            SELECT
                product_category,
                ROUND(SUM(item_price), 2) AS item_revenue,
                COUNT(DISTINCT order_id) AS order_count
            FROM {table_name}
            WHERE product_category IS NOT NULL
            GROUP BY product_category
        ),

        category_with_share AS (
            SELECT
                product_category,
                item_revenue,
                order_count,
                ROUND(
                    100.0 * item_revenue
                    / NULLIF(SUM(item_revenue) OVER (), 0),
                    2
                ) AS revenue_share_percentage
            FROM category_revenue
        )

        SELECT
            product_category,
            item_revenue,
            order_count,
            revenue_share_percentage
        FROM category_with_share
        ORDER BY item_revenue DESC
    """

    if limit is not None:
        query += f"\nLIMIT {limit}"

    return connection.execute(query).fetchdf()


def get_revenue_by_state(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Return item revenue, order count, and revenue contribution by state.
    """
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than zero.")

    query = f"""
        WITH state_revenue AS (
            SELECT
                customer_state,
                ROUND(SUM(item_price), 2) AS item_revenue,
                COUNT(DISTINCT order_id) AS order_count
            FROM {table_name}
            WHERE customer_state IS NOT NULL
            GROUP BY customer_state
        ),

        state_with_share AS (
            SELECT
                customer_state,
                item_revenue,
                order_count,
                ROUND(
                    100.0 * item_revenue
                    / NULLIF(SUM(item_revenue) OVER (), 0),
                    2
                ) AS revenue_share_percentage
            FROM state_revenue
        )

        SELECT
            customer_state,
            item_revenue,
            order_count,
            revenue_share_percentage
        FROM state_with_share
        ORDER BY item_revenue DESC
    """

    if limit is not None:
        query += f"\nLIMIT {limit}"

    return connection.execute(query).fetchdf()


def get_complete_monthly_revenue(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 100,
) -> pd.DataFrame:
    """
    Return monthly revenue while excluding clearly incomplete months.

    A month is considered complete enough for comparison when its order
    count is at least minimum_order_count.

    This is a practical completeness rule for the current dataset, not a
    universal calendar-completeness guarantee.
    """
    if minimum_order_count <= 0:
        raise ValueError("minimum_order_count must be greater than zero.")

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

        complete_months AS (
            SELECT
                purchase_month_start,
                item_revenue,
                order_count
            FROM monthly_metrics
            WHERE order_count >= ?
        ),

        with_previous_month AS (
            SELECT
                purchase_month_start,
                item_revenue,
                order_count,
                LAG(item_revenue) OVER (
                    ORDER BY purchase_month_start
                ) AS previous_month_revenue
            FROM complete_months
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
        """,
        [minimum_order_count],
    ).fetchdf()


def get_top_revenue_categories(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Return the highest-revenue product categories.
    """
    return get_revenue_by_category(
        connection=connection,
        table_name=table_name,
        limit=limit,
    )


def get_bottom_revenue_categories(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Return the lowest-revenue product categories.

    Categories with zero or missing revenue are excluded.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    return connection.execute(
        f"""
        WITH category_revenue AS (
            SELECT
                product_category,
                ROUND(SUM(item_price), 2) AS item_revenue,
                COUNT(DISTINCT order_id) AS order_count
            FROM {table_name}
            WHERE product_category IS NOT NULL
            GROUP BY product_category
        ),

        category_with_share AS (
            SELECT
                product_category,
                item_revenue,
                order_count,
                ROUND(
                    100.0 * item_revenue
                    / NULLIF(SUM(item_revenue) OVER (), 0),
                    2
                ) AS revenue_share_percentage
            FROM category_revenue
            WHERE item_revenue > 0
        )

        SELECT
            product_category,
            item_revenue,
            order_count,
            revenue_share_percentage
        FROM category_with_share
        ORDER BY item_revenue ASC
        LIMIT ?
        """,
        [limit],
    ).fetchdf()


def get_largest_monthly_revenue_changes(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 100,
    limit: int = 5,
) -> pd.DataFrame:
    """
    Return months with the largest absolute month-over-month changes.

    Clearly incomplete months are excluded first.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    monthly_revenue = get_complete_monthly_revenue(
        connection=connection,
        table_name=table_name,
        minimum_order_count=minimum_order_count,
    ).copy()

    monthly_revenue = monthly_revenue.dropna(
        subset=["month_over_month_growth_percentage"]
    )

    monthly_revenue["absolute_growth_percentage"] = monthly_revenue[
        "month_over_month_growth_percentage"
    ].abs()

    return (
        monthly_revenue.sort_values(
            "absolute_growth_percentage",
            ascending=False,
        )
        .head(limit)
        .drop(columns=["absolute_growth_percentage"])
        .reset_index(drop=True)
    )


def print_revenue_summary(
    categories: pd.DataFrame,
    states: pd.DataFrame,
    monthly_revenue: pd.DataFrame,
) -> None:
    """
    Print a readable summary of core revenue analyses.
    """
    print("Top revenue categories:")
    print(
        categories.to_string(
            index=False,
            formatters={
                "item_revenue": lambda value: f"{value:,.2f}",
                "order_count": lambda value: f"{value:,}",
                "revenue_share_percentage": (lambda value: f"{value:.2f}%"),
            },
        )
    )

    print("\nTop revenue states:")
    print(
        states.to_string(
            index=False,
            formatters={
                "item_revenue": lambda value: f"{value:,.2f}",
                "order_count": lambda value: f"{value:,}",
                "revenue_share_percentage": (lambda value: f"{value:.2f}%"),
            },
        )
    )

    display_months = monthly_revenue.tail(12).copy()

    display_months["purchase_month_start"] = display_months[
        "purchase_month_start"
    ].dt.strftime("%Y-%m")

    print("\nComplete monthly revenue trend:")
    print(
        display_months.to_string(
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


def main() -> None:
    """
    Run and print the initial revenue analyses.
    """
    connection = open_analytics_connection()

    try:
        top_categories = get_top_revenue_categories(
            connection,
            limit=10,
        )

        top_states = get_revenue_by_state(
            connection,
            limit=10,
        )

        monthly_revenue = get_complete_monthly_revenue(
            connection,
            minimum_order_count=100,
        )

        print_revenue_summary(
            categories=top_categories,
            states=top_states,
            monthly_revenue=monthly_revenue,
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
