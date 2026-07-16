import duckdb

from app.evidence.engine import (
    answer_question_with_evidence,
)
from app.evidence.models import AnalysisType
from app.evidence.router import route_question


TEST_TABLE_NAME = "order_items_analytics"


def create_test_table(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create a compact dataset supporting every evidence route.
    """
    connection.execute(
        f"""
        CREATE TABLE {TEST_TABLE_NAME} (
            order_id VARCHAR,
            order_item_id INTEGER,
            customer_state VARCHAR,
            product_category VARCHAR,
            purchase_month_start DATE,
            item_price DOUBLE,
            freight_value DOUBLE,
            average_review_score DOUBLE,
            delivery_days BIGINT,
            delivery_delay_days BIGINT,
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
                'CA',
                'electronics',
                DATE '2024-01-01',
                100.00,
                10.00,
                5.00,
                5,
                -3,
                FALSE
            ),
            (
                'order_1',
                2,
                'CA',
                'accessories',
                DATE '2024-01-01',
                50.00,
                5.00,
                5.00,
                5,
                -3,
                FALSE
            ),
            (
                'order_2',
                1,
                'TX',
                'electronics',
                DATE '2024-01-01',
                150.00,
                15.00,
                2.00,
                12,
                3,
                TRUE
            ),
            (
                'order_3',
                1,
                'CA',
                'furniture',
                DATE '2024-02-01',
                300.00,
                20.00,
                4.00,
                7,
                0,
                FALSE
            ),
            (
                'order_4',
                1,
                'TX',
                'electronics',
                DATE '2024-02-01',
                200.00,
                20.00,
                1.00,
                18,
                8,
                TRUE
            )
        """
    )


def test_router_supports_expected_question_types() -> None:
    assert (
        route_question("Show me the main business KPIs.").analysis_type
        == AnalysisType.CORE_KPIS
    )

    assert (
        route_question("How has monthly revenue changed?").analysis_type
        == AnalysisType.MONTHLY_REVENUE_TREND
    )

    assert (
        route_question("Which product categories make the most revenue?").analysis_type
        == AnalysisType.REVENUE_BY_CATEGORY
    )

    assert (
        route_question("Which states generate the most revenue?").analysis_type
        == AnalysisType.REVENUE_BY_STATE
    )

    assert (
        route_question("Which state has the worst delivery performance?").analysis_type
        == AnalysisType.DELIVERY_BY_STATE
    )

    assert (
        route_question("How do late deliveries affect review scores?").analysis_type
        == AnalysisType.LATE_VS_ON_TIME
    )


def test_router_rejects_unsupported_question() -> None:
    route = route_question("What will revenue be next year?")

    assert route.analysis_type == AnalysisType.UNSUPPORTED


def test_revenue_by_category_returns_evidence() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        evidence = answer_question_with_evidence(
            "Which product categories make the most revenue?",
            connection,
        )

        assert evidence.supported is True

        assert evidence.analysis_type == AnalysisType.REVENUE_BY_CATEGORY

        assert evidence.metrics["leading_category"] == "electronics"

        assert evidence.metrics["leading_category_revenue"] == 450.00

        assert evidence.supporting_rows

    finally:
        connection.close()


def test_late_vs_on_time_returns_review_gap() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        evidence = answer_question_with_evidence(
            "How do late deliveries affect review scores?",
            connection,
        )

        assert evidence.analysis_type == AnalysisType.LATE_VS_ON_TIME

        assert evidence.metrics["late_average_review_score"] == 1.50

        assert evidence.metrics["on_time_average_review_score"] == 4.50

        assert evidence.metrics["review_score_gap"] == 3.00

        assert evidence.warnings

    finally:
        connection.close()


def test_unsupported_question_returns_safe_response() -> None:
    connection = duckdb.connect(":memory:")

    try:
        create_test_table(connection)

        evidence = answer_question_with_evidence(
            "Predict customer churn next year.",
            connection,
        )

        assert evidence.supported is False

        assert evidence.analysis_type == AnalysisType.UNSUPPORTED

        assert evidence.supporting_rows == []

    finally:
        connection.close()
