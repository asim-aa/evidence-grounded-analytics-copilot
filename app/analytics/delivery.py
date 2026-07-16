from __future__ import annotations
import duckdb
import pandas as pd
from app.analytics.metrics import open_analytics_connection
from app.config import ANALYTICAL_TABLE_NAME


def _validate_minimum_order_count(
    minimum_order_count: int,
) -> None:
    """Validate a minimum-order threshold."""
    if minimum_order_count <= 0:
        raise ValueError("minimum_order_count must be greater than zero.")


def _validate_limit(
    limit: int,
) -> None:
    """Validate a row limit."""
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")


def get_delivery_performance_by_state(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 100,
) -> pd.DataFrame:
    """
    Return delivery and review performance by customer state.

    Delivery and review values are first reduced to one row per order.
    """
    _validate_minimum_order_count(minimum_order_count)

    return connection.execute(
        f"""
        WITH order_level AS (
            SELECT
                order_id,
                MAX(customer_state) AS customer_state,
                MAX(delivery_days) AS delivery_days,
                MAX(delivery_delay_days) AS delivery_delay_days,
                BOOL_OR(is_late_delivery) AS is_late_delivery,
                MAX(average_review_score) AS review_score
            FROM {table_name}
            GROUP BY order_id
        )

        SELECT
            customer_state,
            COUNT(*) AS order_count,
            COUNT(review_score) AS reviewed_order_count,

            ROUND(
                100.0 * COUNT(review_score)
                / NULLIF(COUNT(*), 0),
                2
            ) AS review_coverage_percentage,

            ROUND(
                AVG(delivery_days),
                2
            ) AS average_delivery_days,

            ROUND(
                MEDIAN(delivery_days),
                2
            ) AS median_delivery_days,

            ROUND(
                100.0 * AVG(
                    CASE
                        WHEN is_late_delivery = TRUE THEN 1
                        WHEN is_late_delivery = FALSE THEN 0
                        ELSE NULL
                    END
                ),
                2
            ) AS late_delivery_rate_percentage,

            ROUND(
                AVG(delivery_delay_days),
                2
            ) AS average_delay_days,

            ROUND(
                AVG(
                    CASE
                        WHEN is_late_delivery = TRUE
                            THEN delivery_delay_days
                        ELSE NULL
                    END
                ),
                2
            ) AS average_late_days_among_late_orders,

            ROUND(
                AVG(review_score),
                2
            ) AS average_review_score

        FROM order_level
        WHERE customer_state IS NOT NULL
        GROUP BY customer_state
        HAVING COUNT(*) >= ?
        ORDER BY
            late_delivery_rate_percentage DESC,
            order_count DESC
        """,
        [minimum_order_count],
    ).fetchdf()


def get_delivery_performance_by_category(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 100,
) -> pd.DataFrame:
    """
    Return delivery and review performance by product category.

    Each order-category pair is reduced to one row before aggregation.
    """
    _validate_minimum_order_count(minimum_order_count)

    return connection.execute(
        f"""
        WITH order_category_level AS (
            SELECT
                order_id,
                product_category,
                MAX(delivery_days) AS delivery_days,
                MAX(delivery_delay_days) AS delivery_delay_days,
                BOOL_OR(is_late_delivery) AS is_late_delivery,
                MAX(average_review_score) AS review_score
            FROM {table_name}
            WHERE product_category IS NOT NULL
            GROUP BY
                order_id,
                product_category
        )

        SELECT
            product_category,
            COUNT(*) AS order_count,
            COUNT(review_score) AS reviewed_order_count,

            ROUND(
                100.0 * COUNT(review_score)
                / NULLIF(COUNT(*), 0),
                2
            ) AS review_coverage_percentage,

            ROUND(
                AVG(delivery_days),
                2
            ) AS average_delivery_days,

            ROUND(
                MEDIAN(delivery_days),
                2
            ) AS median_delivery_days,

            ROUND(
                100.0 * AVG(
                    CASE
                        WHEN is_late_delivery = TRUE THEN 1
                        WHEN is_late_delivery = FALSE THEN 0
                        ELSE NULL
                    END
                ),
                2
            ) AS late_delivery_rate_percentage,

            ROUND(
                AVG(delivery_delay_days),
                2
            ) AS average_delay_days,

            ROUND(
                AVG(
                    CASE
                        WHEN is_late_delivery = TRUE
                            THEN delivery_delay_days
                        ELSE NULL
                    END
                ),
                2
            ) AS average_late_days_among_late_orders,

            ROUND(
                AVG(review_score),
                2
            ) AS average_review_score

        FROM order_category_level
        GROUP BY product_category
        HAVING COUNT(*) >= ?
        ORDER BY
            late_delivery_rate_percentage DESC,
            order_count DESC
        """,
        [minimum_order_count],
    ).fetchdf()


def compare_late_and_on_time_orders(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> pd.DataFrame:
    """
    Compare delivery duration and reviews for late and on-time orders.
    """
    return connection.execute(
        f"""
        WITH order_level AS (
            SELECT
                order_id,
                MAX(delivery_days) AS delivery_days,
                BOOL_OR(is_late_delivery) AS is_late_delivery,
                MAX(average_review_score) AS review_score
            FROM {table_name}
            GROUP BY order_id
        )

        SELECT
            CASE
                WHEN is_late_delivery = TRUE THEN 'late'
                ELSE 'on_time'
            END AS delivery_status,

            COUNT(*) AS order_count,
            COUNT(review_score) AS reviewed_order_count,

            ROUND(
                100.0 * COUNT(review_score)
                / NULLIF(COUNT(*), 0),
                2
            ) AS review_coverage_percentage,

            ROUND(
                AVG(delivery_days),
                2
            ) AS average_delivery_days,

            ROUND(
                MEDIAN(delivery_days),
                2
            ) AS median_delivery_days,

            ROUND(
                AVG(review_score),
                2
            ) AS average_review_score

        FROM order_level
        WHERE is_late_delivery IS NOT NULL
        GROUP BY delivery_status
        ORDER BY delivery_status
        """
    ).fetchdf()


def get_worst_delivery_sellers(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 50,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Return sellers with the highest late-delivery rates.

    Each order-seller pair is reduced to one row. Sellers below the
    minimum-order threshold are excluded.
    """
    _validate_minimum_order_count(minimum_order_count)
    _validate_limit(limit)

    return connection.execute(
        f"""
        WITH order_seller_level AS (
            SELECT
                order_id,
                seller_id,
                MAX(delivery_days) AS delivery_days,
                MAX(delivery_delay_days) AS delivery_delay_days,
                BOOL_OR(is_late_delivery) AS is_late_delivery,
                MAX(average_review_score) AS review_score
            FROM {table_name}
            WHERE seller_id IS NOT NULL
            GROUP BY
                order_id,
                seller_id
        ),

        seller_performance AS (
            SELECT
                seller_id,
                COUNT(*) AS order_count,
                COUNT(review_score) AS reviewed_order_count,

                ROUND(
                    100.0 * COUNT(review_score)
                    / NULLIF(COUNT(*), 0),
                    2
                ) AS review_coverage_percentage,

                ROUND(
                    AVG(delivery_days),
                    2
                ) AS average_delivery_days,

                ROUND(
                    MEDIAN(delivery_days),
                    2
                ) AS median_delivery_days,

                ROUND(
                    100.0 * AVG(
                        CASE
                            WHEN is_late_delivery = TRUE THEN 1
                            WHEN is_late_delivery = FALSE THEN 0
                            ELSE NULL
                        END
                    ),
                    2
                ) AS late_delivery_rate_percentage,

                ROUND(
                    AVG(delivery_delay_days),
                    2
                ) AS average_delay_days,

                ROUND(
                    AVG(
                        CASE
                            WHEN is_late_delivery = TRUE
                                THEN delivery_delay_days
                            ELSE NULL
                        END
                    ),
                    2
                ) AS average_late_days_among_late_orders,

                ROUND(
                    AVG(review_score),
                    2
                ) AS average_review_score

            FROM order_seller_level
            GROUP BY seller_id
            HAVING COUNT(*) >= ?
        )

        SELECT *
        FROM seller_performance
        ORDER BY
            late_delivery_rate_percentage DESC,
            order_count DESC
        LIMIT ?
        """,
        [
            minimum_order_count,
            limit,
        ],
    ).fetchdf()


def get_delivery_review_relationship(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> pd.DataFrame:
    """
    Group orders into delivery-delay bands and compare review outcomes.

    Positive delivery_delay_days values indicate late delivery.
    Negative values indicate early delivery.
    """
    return connection.execute(
        f"""
        WITH order_level AS (
            SELECT
                order_id,
                MAX(delivery_delay_days) AS delivery_delay_days,
                MAX(average_review_score) AS review_score
            FROM {table_name}
            GROUP BY order_id
        ),

        delay_bands AS (
            SELECT
                order_id,
                delivery_delay_days,
                review_score,

                CASE
                    WHEN delivery_delay_days <= -8
                        THEN 'more_than_7_days_early'
                    WHEN delivery_delay_days BETWEEN -7 AND -1
                        THEN '1_to_7_days_early'
                    WHEN delivery_delay_days = 0
                        THEN 'on_estimated_date'
                    WHEN delivery_delay_days BETWEEN 1 AND 3
                        THEN '1_to_3_days_late'
                    WHEN delivery_delay_days BETWEEN 4 AND 7
                        THEN '4_to_7_days_late'
                    WHEN delivery_delay_days >= 8
                        THEN 'more_than_7_days_late'
                    ELSE NULL
                END AS delivery_delay_band,

                CASE
                    WHEN delivery_delay_days <= -8 THEN 1
                    WHEN delivery_delay_days BETWEEN -7 AND -1 THEN 2
                    WHEN delivery_delay_days = 0 THEN 3
                    WHEN delivery_delay_days BETWEEN 1 AND 3 THEN 4
                    WHEN delivery_delay_days BETWEEN 4 AND 7 THEN 5
                    WHEN delivery_delay_days >= 8 THEN 6
                    ELSE NULL
                END AS band_order

            FROM order_level
            WHERE delivery_delay_days IS NOT NULL
        )

        SELECT
            delivery_delay_band,
            COUNT(*) AS order_count,
            COUNT(review_score) AS reviewed_order_count,

            ROUND(
                100.0 * COUNT(review_score)
                / NULLIF(COUNT(*), 0),
                2
            ) AS review_coverage_percentage,

            ROUND(
                AVG(delivery_delay_days),
                2
            ) AS average_delay_days,

            ROUND(
                MEDIAN(delivery_delay_days),
                2
            ) AS median_delay_days,

            ROUND(
                AVG(review_score),
                2
            ) AS average_review_score

        FROM delay_bands
        WHERE delivery_delay_band IS NOT NULL
        GROUP BY
            delivery_delay_band,
            band_order
        ORDER BY band_order
        """
    ).fetchdf()


def _format_delivery_dataframe(
    dataframe: pd.DataFrame,
) -> str:
    """Format delivery analysis output for terminal display."""
    formatters = {}

    integer_columns = {
        "order_count",
        "reviewed_order_count",
    }

    percentage_columns = {
        "review_coverage_percentage",
        "late_delivery_rate_percentage",
    }

    decimal_columns = {
        "average_delivery_days",
        "median_delivery_days",
        "average_delay_days",
        "median_delay_days",
        "average_late_days_among_late_orders",
        "average_review_score",
    }

    for column in dataframe.columns:
        if column in integer_columns:
            formatters[column] = lambda value: f"{value:,}"

        elif column in percentage_columns:
            formatters[column] = lambda value: f"{value:.2f}%"

        elif column in decimal_columns:
            formatters[column] = lambda value: f"{value:.2f}"

    return dataframe.to_string(
        index=False,
        formatters=formatters,
    )


def print_delivery_summary(
    state_performance: pd.DataFrame,
    late_comparison: pd.DataFrame,
    worst_sellers: pd.DataFrame,
    delay_relationship: pd.DataFrame,
) -> None:
    """Print a readable summary of delivery analyses."""
    print("States with highest late-delivery rates:")
    print(_format_delivery_dataframe(state_performance.head(10)))

    print("\nLate versus on-time orders:")
    print(_format_delivery_dataframe(late_comparison))

    print("\nWorst delivery sellers:")
    print(_format_delivery_dataframe(worst_sellers))

    print("\nReview score by delivery-delay band:")
    print(_format_delivery_dataframe(delay_relationship))


def main() -> None:
    """Run the delivery and customer-experience analyses."""
    connection = open_analytics_connection()

    try:
        state_performance = get_delivery_performance_by_state(
            connection,
            minimum_order_count=100,
        )

        late_comparison = compare_late_and_on_time_orders(connection)

        worst_sellers = get_worst_delivery_sellers(
            connection,
            minimum_order_count=50,
            limit=10,
        )

        delay_relationship = get_delivery_review_relationship(connection)

        print_delivery_summary(
            state_performance=state_performance,
            late_comparison=late_comparison,
            worst_sellers=worst_sellers,
            delay_relationship=delay_relationship,
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
