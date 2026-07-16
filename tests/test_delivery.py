import math

import duckdb

from app.analytics.delivery import (
    compare_late_and_on_time_orders,
    get_delivery_performance_by_category,
    get_delivery_performance_by_state,
    get_delivery_review_relationship,
    get_worst_delivery_sellers,
)


TEST_TABLE_NAME = "test_delivery_data"


def create_test_table(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create a deterministic order-item dataset for delivery tests.
    """
    connection.execute(
        f"""
        CREATE TABLE {TEST_TABLE_NAME} (
            order_id VARCHAR,
            order_item_id INTEGER,
            customer_state VARCHAR,
            product_category VARCHAR,
            seller_id VARCHAR,
            delivery_days BIGINT,
            delivery_delay_days BIGINT,
            is_late_delivery BOOLEAN,
            average_review_score DOUBLE
        )
        """
    )

    connection.execute(
        f"""
        INSERT INTO {TEST_TABLE_NAME} VALUES
            (
                'order_1',
                1,
                'CA',
                'electronics',
                'seller_a',
                5,
                -3,
                FALSE,
                5.0
            ),
            (
                'order_1',
                2,
                'CA',
                'accessories',
                'seller_a',
                5,
                -3,
                FALSE,
                5.0
            ),
            (
                'order_2',
                1,
                'CA',
                'electronics',
                'seller_b',
                10,
                2,
                TRUE,
                2.0
            ),
            (
                'order_3',
                1,
                'TX',
                'furniture',
                'seller_b',
                15,
                6,
                TRUE,
                1.0
            ),
            (
                'order_4',
                1,
                'TX',
                'electronics',
                'seller_a',
                7,
                0,
                FALSE,
                4.0
            ),
            (
                'order_5',
                1,
                'NY',
                'furniture',
                'seller_c',
                20,
                10,
                TRUE,
                1.0
            ),
            (
                'order_6',
                1,
                'NY',
                'accessories',
                'seller_c',
                4,
                -10,
                FALSE,
                5.0
            )
        """
    )


def test_delivery_performance_by_state_uses_order_grain() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_delivery_performance_by_state(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=1,
        )

        ca = result[result["customer_state"] == "CA"].iloc[0]

        assert ca["order_count"] == 2

        assert math.isclose(
            ca["average_delivery_days"],
            7.50,
            abs_tol=0.01,
        )

        assert math.isclose(
            ca["late_delivery_rate_percentage"],
            50.00,
            abs_tol=0.01,
        )

        assert math.isclose(
            ca["average_review_score"],
            3.50,
            abs_tol=0.01,
        )

    finally:
        connection.close()


def test_delivery_performance_by_category() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_delivery_performance_by_category(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=1,
        )

        electronics = result[result["product_category"] == "electronics"].iloc[0]

        assert electronics["order_count"] == 3

        assert math.isclose(
            electronics["late_delivery_rate_percentage"],
            33.33,
            abs_tol=0.01,
        )

        assert math.isclose(
            electronics["average_review_score"],
            3.67,
            abs_tol=0.01,
        )

    finally:
        connection.close()


def test_late_and_on_time_order_comparison() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = compare_late_and_on_time_orders(
            connection,
            TEST_TABLE_NAME,
        )

        late = result[result["delivery_status"] == "late"].iloc[0]

        on_time = result[result["delivery_status"] == "on_time"].iloc[0]

        assert late["order_count"] == 3
        assert on_time["order_count"] == 3

        assert math.isclose(
            late["average_review_score"],
            1.33,
            abs_tol=0.01,
        )

        assert math.isclose(
            on_time["average_review_score"],
            4.67,
            abs_tol=0.01,
        )

    finally:
        connection.close()


def test_worst_delivery_sellers_respect_threshold() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_worst_delivery_sellers(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=2,
            limit=2,
        )

        assert list(result["seller_id"]) == [
            "seller_b",
            "seller_c",
        ]

        assert list(result["late_delivery_rate_percentage"]) == [
            100.00,
            50.00,
        ]

    finally:
        connection.close()


def test_delivery_review_relationship_bands() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_delivery_review_relationship(
            connection,
            TEST_TABLE_NAME,
        )

        assert list(result["delivery_delay_band"]) == [
            "more_than_7_days_early",
            "1_to_7_days_early",
            "on_estimated_date",
            "1_to_3_days_late",
            "4_to_7_days_late",
            "more_than_7_days_late",
        ]

        late_over_seven = result[
            result["delivery_delay_band"] == "more_than_7_days_late"
        ].iloc[0]

        assert late_over_seven["order_count"] == 1
        assert late_over_seven["average_review_score"] == 1.00

    finally:
        connection.close()


def test_invalid_delivery_arguments_raise_errors() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        try:
            get_delivery_performance_by_state(
                connection,
                TEST_TABLE_NAME,
                minimum_order_count=0,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for minimum_order_count.")

        try:
            get_worst_delivery_sellers(
                connection,
                TEST_TABLE_NAME,
                minimum_order_count=1,
                limit=0,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for limit.")

    finally:
        connection.close()
