import math

import duckdb
import pandas as pd

from app.evidence.investigations import (
    get_category_revenue_change,
    get_monthly_revenue_components,
    get_state_revenue_change,
    investigate_revenue_change,
    resolve_target_month,
)
from app.evidence.models import AnalysisType
from app.evidence.router import route_question


TEST_TABLE_NAME = "test_revenue_investigation"


def create_test_table(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create a small dataset with a known monthly revenue decline.
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
                'jan_1',
                1,
                DATE '2024-01-01',
                'electronics',
                'CA',
                100.00
            ),
            (
                'jan_2',
                1,
                DATE '2024-01-01',
                'electronics',
                'CA',
                100.00
            ),
            (
                'jan_3',
                1,
                DATE '2024-01-01',
                'furniture',
                'TX',
                100.00
            ),
            (
                'feb_1',
                1,
                DATE '2024-02-01',
                'electronics',
                'CA',
                80.00
            ),
            (
                'feb_2',
                1,
                DATE '2024-02-01',
                'furniture',
                'TX',
                100.00
            ),
            (
                'mar_1',
                1,
                DATE '2024-03-01',
                'electronics',
                'CA',
                120.00
            ),
            (
                'mar_2',
                1,
                DATE '2024-03-01',
                'furniture',
                'TX',
                120.00
            )
        """
    )


def test_monthly_revenue_components() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = get_monthly_revenue_components(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=1,
        )

        february = result.iloc[1]

        assert february["item_revenue"] == 180.00
        assert february["order_count"] == 2
        assert february["average_order_value"] == 90.00
        assert february["revenue_change_amount"] == -120.00
        assert february["revenue_change_percentage"] == -40.00

        assert math.isclose(
            february["order_count_change_percentage"],
            -33.33,
            abs_tol=0.01,
        )

        assert february[
            "average_order_value_change_percentage"
        ] == -10.00

    finally:
        connection.close()


def test_target_month_resolution() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        monthly = get_monthly_revenue_components(
            connection,
            TEST_TABLE_NAME,
            minimum_order_count=1,
        )

        assert resolve_target_month(
            "Why did revenue decline in 2024-02?",
            monthly,
        ) == pd.Timestamp("2024-02-01")

        assert resolve_target_month(
            "Why did revenue decline in February 2024?",
            monthly,
        ) == pd.Timestamp("2024-02-01")

        assert resolve_target_month(
            "Why did revenue decline?",
            monthly,
        ) == pd.Timestamp("2024-02-01")

    finally:
        connection.close()


def test_category_and_state_changes() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        category_result = get_category_revenue_change(
            connection,
            current_month=pd.Timestamp("2024-02-01"),
            previous_month=pd.Timestamp("2024-01-01"),
            table_name=TEST_TABLE_NAME,
        )

        state_result = get_state_revenue_change(
            connection,
            current_month=pd.Timestamp("2024-02-01"),
            previous_month=pd.Timestamp("2024-01-01"),
            table_name=TEST_TABLE_NAME,
        )

        assert (
            category_result.iloc[0]["product_category"]
            == "electronics"
        )

        assert (
            category_result.iloc[0]["change_amount"]
            == -120.00
        )

        assert (
            state_result.iloc[0]["customer_state"]
            == "CA"
        )

        assert (
            state_result.iloc[0]["change_amount"]
            == -120.00
        )

    finally:
        connection.close()


def test_complete_revenue_investigation() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        result = investigate_revenue_change(
            connection=connection,
            question="Why did revenue decline in February 2024?",
            table_name=TEST_TABLE_NAME,
            minimum_order_count=1,
            driver_limit=3,
        )

        assert result["current_month"] == pd.Timestamp(
            "2024-02-01"
        )

        assert result["previous_month"] == pd.Timestamp(
            "2024-01-01"
        )

        assert (
            result["current_metrics"][
                "revenue_change_amount"
            ]
            == -120.00
        )

        assert not result["category_changes"].empty
        assert not result["state_changes"].empty

    finally:
        connection.close()


def test_router_selects_revenue_investigation() -> None:
    route = route_question(
        "Why did monthly revenue decline?"
    )

    assert (
        route.analysis_type
        == AnalysisType.REVENUE_CHANGE_INVESTIGATION
    )