import math

import duckdb

from app.analytics.revenue import (
    get_bottom_revenue_categories,
    get_complete_monthly_revenue,
    get_largest_monthly_revenue_changes,
    get_revenue_by_category,
    get_revenue_by_state,
    get_top_revenue_categories,
)


TEST_TABLE_NAME = "test_revenue_data"


def create_test_table(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create a deterministic order-item dataset for revenue tests.
    """
    connection.execute(
        f"""
        CREATE TABLE {TEST_TABLE_NAME} (
            order_id VARCHAR,
            order_item_id INTEGER,
            purchase_month_start DATE,
            product_category VARCHAR,
            customer_state VARCHAR,
            item_price DOUBLE
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
                'electronics',
                'CA',
                100.00
            ),
            (
                'order_1',
                2,
                DATE '2024-01-01',
                'accessories',
                'CA',
                50.00
            ),
            (
                'order_2',
                1,
                DATE '2024-01-01',
                'electronics',
                'NY',
                150.00
            ),
            (
                'order_3',
                1,
                DATE '2024-02-01',
                'furniture',
                'CA',
                300.00
            ),
            (
                'order_4',
                1,
                DATE '2024-02-01',
                'electronics',
                'TX',
                100.00
            ),
            (
                'order_5',
                1,
                DATE '2024-03-01',
                'accessories',
                'TX',
                100.00
            )
        """
    )


def test_revenue_by_category() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_revenue_by_category(
            connection,
            TEST_TABLE_NAME,
        )

        assert list(result["product_category"]) == [
            "electronics",
            "furniture",
            "accessories",
        ]

        assert list(result["item_revenue"]) == [
            350.00,
            300.00,
            150.00,
        ]

        assert list(result["order_count"]) == [
            3,
            1,
            2,
        ]

        assert math.isclose(
            result.iloc[0]["revenue_share_percentage"],
            43.75,
            abs_tol=0.01,
        )

    finally:
        connection.close()


def test_revenue_by_state() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_revenue_by_state(
            connection,
            TEST_TABLE_NAME,
        )

        assert list(result["customer_state"]) == [
            "CA",
            "TX",
            "NY",
        ]

        assert list(result["item_revenue"]) == [
            450.00,
            200.00,
            150.00,
        ]

    finally:
        connection.close()


def test_top_and_bottom_categories() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        top = get_top_revenue_categories(
            connection,
            TEST_TABLE_NAME,
            limit=2,
        )

        bottom = get_bottom_revenue_categories(
            connection,
            TEST_TABLE_NAME,
            limit=2,
        )

        assert list(top["product_category"]) == [
            "electronics",
            "furniture",
        ]

        assert list(bottom["product_category"]) == [
            "accessories",
            "furniture",
        ]

    finally:
        connection.close()


def test_complete_month_filtering() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_complete_monthly_revenue(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=2,
        )

        assert len(result) == 2

        january = result.iloc[0]
        february = result.iloc[1]

        assert january["item_revenue"] == 300.00
        assert january["order_count"] == 2
        assert math.isnan(january["month_over_month_growth_percentage"])

        assert february["item_revenue"] == 400.00
        assert february["order_count"] == 2
        assert math.isclose(
            february["month_over_month_growth_percentage"],
            33.33,
            abs_tol=0.01,
        )

    finally:
        connection.close()


def test_largest_monthly_revenue_changes() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_largest_monthly_revenue_changes(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=1,
            limit=2,
        )

        assert len(result) == 2

        assert result.iloc[0]["month_over_month_growth_percentage"] == -75.00

        assert math.isclose(
            result.iloc[1]["month_over_month_growth_percentage"],
            33.33,
            abs_tol=0.01,
        )

    finally:
        connection.close()


def test_invalid_limits_raise_errors() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        try:
            get_revenue_by_category(
                connection,
                TEST_TABLE_NAME,
                limit=0,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for zero limit.")

        try:
            get_complete_monthly_revenue(
                connection,
                TEST_TABLE_NAME,
                minimum_order_count=0,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for invalid minimum order count.")

    finally:
        connection.close()
