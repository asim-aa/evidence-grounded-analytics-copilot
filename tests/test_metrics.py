import math

import duckdb

from app.analytics.metrics import (
    calculate_average_order_value,
    calculate_average_review_score,
    calculate_freight_value,
    calculate_item_revenue,
    calculate_late_delivery_rate,
    calculate_order_count,
    get_business_kpis,
    get_monthly_revenue_trend,
)


TEST_TABLE_NAME = "test_order_items"


def create_test_table(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create a small table with known item-level and order-level values.
    """
    connection.execute(
        f"""
        CREATE TABLE {TEST_TABLE_NAME} (
            order_id VARCHAR,
            order_item_id INTEGER,
            purchase_month_start DATE,
            item_price DOUBLE,
            freight_value DOUBLE,
            average_review_score DOUBLE,
            is_late_delivery BOOLEAN
        )
        """
    )

    connection.execute(
        f"""
        INSERT INTO {TEST_TABLE_NAME} VALUES
            (
                'order_1',
                1,
                DATE '2024-01-01',
                40.00,
                5.00,
                5.00,
                FALSE
            ),
            (
                'order_1',
                2,
                DATE '2024-01-01',
                60.00,
                7.00,
                5.00,
                FALSE
            ),
            (
                'order_2',
                1,
                DATE '2024-01-01',
                50.00,
                6.00,
                1.00,
                TRUE
            ),
            (
                'order_3',
                1,
                DATE '2024-02-01',
                150.00,
                10.00,
                NULL,
                FALSE
            )
        """
    )


def test_item_level_metrics() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        assert (
            calculate_item_revenue(
                connection,
                TEST_TABLE_NAME,
            )
            == 300.00
        )

        assert (
            calculate_freight_value(
                connection,
                TEST_TABLE_NAME,
            )
            == 28.00
        )

        assert (
            calculate_order_count(
                connection,
                TEST_TABLE_NAME,
            )
            == 3
        )

    finally:
        connection.close()


def test_average_order_value_uses_order_grain() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        average_order_value = calculate_average_order_value(
            connection,
            TEST_TABLE_NAME,
        )

        # Order revenues are 100, 50, and 150.
        assert average_order_value == 100.00

    finally:
        connection.close()


def test_order_level_metrics_do_not_overweight_multi_item_orders() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        late_delivery_rate = calculate_late_delivery_rate(
            connection,
            TEST_TABLE_NAME,
        )

        average_review_score = calculate_average_review_score(
            connection,
            TEST_TABLE_NAME,
        )

        # One of three orders was late.
        assert math.isclose(
            late_delivery_rate,
            33.33,
            abs_tol=0.01,
        )

        # Only reviewed orders count: scores 5 and 1.
        assert average_review_score == 3.00

    finally:
        connection.close()


def test_monthly_revenue_trend() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        trend = get_monthly_revenue_trend(
            connection,
            TEST_TABLE_NAME,
        )

        assert len(trend) == 2

        january = trend.iloc[0]
        february = trend.iloc[1]

        assert january["item_revenue"] == 150.00
        assert january["order_count"] == 2
        assert math.isnan(january["month_over_month_growth_percentage"])

        assert february["item_revenue"] == 150.00
        assert february["order_count"] == 1
        assert february["month_over_month_growth_percentage"] == 0.00

    finally:
        connection.close()


def test_business_kpis_have_consistent_output() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        metrics = get_business_kpis(
            connection,
            TEST_TABLE_NAME,
        )

        assert metrics == {
            "item_revenue": 300.00,
            "freight_value": 28.00,
            "order_count": 3,
            "average_order_value": 100.00,
            "late_delivery_rate_percentage": 33.33,
            "average_review_score": 3.00,
        }

    finally:
        connection.close()
