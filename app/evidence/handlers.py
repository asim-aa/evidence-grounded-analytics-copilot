from __future__ import annotations

import json
from typing import Any

import duckdb
import pandas as pd

from app.analytics.delivery import (
    compare_late_and_on_time_orders,
    get_delivery_performance_by_state,
)
from app.analytics.metrics import get_business_kpis
from app.analytics.revenue import (
    get_complete_monthly_revenue,
    get_revenue_by_category,
    get_revenue_by_state,
)
from app.evidence.models import (
    AnalysisType,
    EvidenceResult,
)


def _dataframe_to_records(
    dataframe: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Convert a dataframe into JSON-compatible records.

    Pandas and NumPy scalar values are normalized through JSON.
    """
    if dataframe.empty:
        return []

    serialized = dataframe.to_json(
        orient="records",
        date_format="iso",
    )

    records = json.loads(serialized)

    if not isinstance(records, list):
        raise RuntimeError("Dataframe serialization did not produce a record list.")

    return records


def handle_core_kpis(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Return the principal marketplace KPIs.
    """
    metrics = get_business_kpis(connection)

    summary = (
        f"The marketplace generated "
        f"{metrics['item_revenue']:,.2f} in item revenue "
        f"across {metrics['order_count']:,} orders, with an "
        f"average order value of "
        f"{metrics['average_order_value']:,.2f}."
    )

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.CORE_KPIS,
        summary=summary,
        metrics=metrics,
        supporting_rows=[metrics],
        methodology={
            "table_grain": "one row per purchased order item",
            "revenue_calculation": "SUM(item_price)",
            "order_count_calculation": ("COUNT(DISTINCT order_id)"),
            "order_level_metrics": (
                "Reviews and delivery outcomes are reduced to one row per order."
            ),
        },
        warnings=[
            ("Item revenue excludes freight and does not represent profit."),
            (
                "The dataset does not include product cost, "
                "so margin cannot be calculated."
            ),
        ],
    )


def handle_monthly_revenue_trend(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Return complete-month revenue evidence.
    """
    trend = get_complete_monthly_revenue(
        connection,
        minimum_order_count=100,
    )

    rows = _dataframe_to_records(trend)

    if len(trend) < 2:
        return EvidenceResult(
            question=question,
            analysis_type=AnalysisType.MONTHLY_REVENUE_TREND,
            summary=(
                "There are not enough complete months to "
                "calculate a reliable revenue trend."
            ),
            supporting_rows=rows,
            methodology={
                "minimum_order_count_per_month": 100,
            },
            warnings=["At least two complete months are required."],
        )

    latest = trend.iloc[-1]
    previous = trend.iloc[-2]

    latest_month = pd.Timestamp(latest["purchase_month_start"]).strftime("%Y-%m")

    previous_month = pd.Timestamp(previous["purchase_month_start"]).strftime("%Y-%m")

    growth = latest["month_over_month_growth_percentage"]

    direction = (
        "increased"
        if growth > 0
        else "decreased"
        if growth < 0
        else "remained unchanged"
    )

    summary = (
        f"Item revenue {direction} by "
        f"{abs(float(growth)):.2f}% from "
        f"{previous_month} to {latest_month}. "
        f"The latest complete month generated "
        f"{float(latest['item_revenue']):,.2f} "
        f"across {int(latest['order_count']):,} orders."
    )

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.MONTHLY_REVENUE_TREND,
        summary=summary,
        metrics={
            "latest_complete_month": latest_month,
            "previous_complete_month": previous_month,
            "latest_item_revenue": float(latest["item_revenue"]),
            "previous_item_revenue": float(previous["item_revenue"]),
            "month_over_month_growth_percentage": float(growth),
        },
        supporting_rows=rows,
        methodology={
            "grain": "calendar month",
            "metric": "SUM(item_price)",
            "minimum_order_count_per_month": 100,
            "growth_method": ("(current month - previous month) / previous month"),
        },
        warnings=[
            (
                "Months with fewer than 100 orders are excluded "
                "as clearly incomplete reporting periods."
            ),
            (
                "The minimum-order threshold is a dataset-specific "
                "completeness rule, not a universal standard."
            ),
        ],
    )


def handle_revenue_by_category(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Return top revenue-producing product categories.
    """
    result = get_revenue_by_category(
        connection,
        limit=10,
    )

    rows = _dataframe_to_records(result)

    if result.empty:
        return EvidenceResult(
            question=question,
            analysis_type=AnalysisType.REVENUE_BY_CATEGORY,
            summary="No category revenue evidence was available.",
            supporting_rows=[],
        )

    leader = result.iloc[0]

    summary = (
        f"{leader['product_category']} generated the most "
        f"item revenue at "
        f"{float(leader['item_revenue']):,.2f}, representing "
        f"{float(leader['revenue_share_percentage']):.2f}% "
        f"of total item revenue."
    )

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.REVENUE_BY_CATEGORY,
        summary=summary,
        metrics={
            "leading_category": str(leader["product_category"]),
            "leading_category_revenue": float(leader["item_revenue"]),
            "leading_category_order_count": int(leader["order_count"]),
            "leading_category_revenue_share_percentage": float(
                leader["revenue_share_percentage"]
            ),
        },
        supporting_rows=rows,
        methodology={
            "grain": "order item",
            "grouping_dimension": "product_category",
            "metric": "SUM(item_price)",
            "ranking": "item_revenue descending",
            "returned_categories": 10,
        },
        warnings=[
            ("Revenue does not represent profit because product cost is unavailable.")
        ],
    )


def handle_revenue_by_state(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Return top revenue-producing customer states.
    """
    result = get_revenue_by_state(
        connection,
        limit=10,
    )

    rows = _dataframe_to_records(result)

    if result.empty:
        return EvidenceResult(
            question=question,
            analysis_type=AnalysisType.REVENUE_BY_STATE,
            summary="No state revenue evidence was available.",
            supporting_rows=[],
        )

    leader = result.iloc[0]

    summary = (
        f"{leader['customer_state']} generated the most "
        f"item revenue at "
        f"{float(leader['item_revenue']):,.2f}, representing "
        f"{float(leader['revenue_share_percentage']):.2f}% "
        f"of total item revenue."
    )

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.REVENUE_BY_STATE,
        summary=summary,
        metrics={
            "leading_state": str(leader["customer_state"]),
            "leading_state_revenue": float(leader["item_revenue"]),
            "leading_state_order_count": int(leader["order_count"]),
            "leading_state_revenue_share_percentage": float(
                leader["revenue_share_percentage"]
            ),
        },
        supporting_rows=rows,
        methodology={
            "grain": "order item",
            "grouping_dimension": "customer_state",
            "metric": "SUM(item_price)",
            "ranking": "item_revenue descending",
            "returned_states": 10,
        },
        warnings=[
            (
                "Customer geography is associated with revenue "
                "but does not by itself explain revenue differences."
            )
        ],
    )


def handle_delivery_by_state(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Return states ranked by late-delivery rate.
    """
    result = get_delivery_performance_by_state(
        connection,
        minimum_order_count=100,
    )

    top_result = result.head(10).copy()
    rows = _dataframe_to_records(top_result)

    if result.empty:
        return EvidenceResult(
            question=question,
            analysis_type=AnalysisType.DELIVERY_BY_STATE,
            summary="No state delivery evidence was available.",
            supporting_rows=[],
        )

    worst = result.iloc[0]

    summary = (
        f"{worst['customer_state']} had the highest "
        f"late-delivery rate among states meeting the sample "
        f"threshold: "
        f"{float(worst['late_delivery_rate_percentage']):.2f}% "
        f"across {int(worst['order_count']):,} orders."
    )

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.DELIVERY_BY_STATE,
        summary=summary,
        metrics={
            "highest_late_delivery_state": str(worst["customer_state"]),
            "late_delivery_rate_percentage": float(
                worst["late_delivery_rate_percentage"]
            ),
            "order_count": int(worst["order_count"]),
            "average_delivery_days": float(worst["average_delivery_days"]),
            "median_delivery_days": float(worst["median_delivery_days"]),
            "average_review_score": float(worst["average_review_score"]),
        },
        supporting_rows=rows,
        methodology={
            "grain": "one row per order",
            "grouping_dimension": "customer_state",
            "ranking_metric": ("late_delivery_rate_percentage descending"),
            "minimum_order_count": 100,
        },
        warnings=[
            ("State rankings exclude states with fewer than 100 orders."),
            (
                "Geography is associated with delivery outcomes "
                "but does not prove that geography caused delays."
            ),
        ],
    )


def handle_late_vs_on_time(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Compare reviews and delivery durations for late and on-time orders.
    """
    result = compare_late_and_on_time_orders(connection)
    rows = _dataframe_to_records(result)

    late_rows = result[result["delivery_status"] == "late"]

    on_time_rows = result[result["delivery_status"] == "on_time"]

    if late_rows.empty or on_time_rows.empty:
        return EvidenceResult(
            question=question,
            analysis_type=AnalysisType.LATE_VS_ON_TIME,
            summary=(
                "The dataset does not contain both late and on-time order groups."
            ),
            supporting_rows=rows,
        )

    late = late_rows.iloc[0]
    on_time = on_time_rows.iloc[0]

    review_gap = float(on_time["average_review_score"] - late["average_review_score"])

    summary = (
        f"Late orders averaged a review score of "
        f"{float(late['average_review_score']):.2f}, compared "
        f"with {float(on_time['average_review_score']):.2f} "
        f"for on-time orders. On-time orders scored "
        f"{review_gap:.2f} points higher on average."
    )

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.LATE_VS_ON_TIME,
        summary=summary,
        metrics={
            "late_order_count": int(late["order_count"]),
            "on_time_order_count": int(on_time["order_count"]),
            "late_average_review_score": float(late["average_review_score"]),
            "on_time_average_review_score": float(on_time["average_review_score"]),
            "review_score_gap": review_gap,
            "late_average_delivery_days": float(late["average_delivery_days"]),
            "on_time_average_delivery_days": float(on_time["average_delivery_days"]),
        },
        supporting_rows=rows,
        methodology={
            "grain": "one row per order",
            "comparison_groups": [
                "late",
                "on_time",
            ],
            "review_metric": ("average review score among reviewed orders"),
        },
        warnings=[
            (
                "The observed relationship is an association and "
                "does not prove that delivery lateness caused the "
                "review-score difference."
            ),
            (
                "Average review scores are calculated only for "
                "orders with available reviews."
            ),
        ],
    )


def handle_unsupported_question(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Return an explicit unsupported-question response.
    """
    del connection

    return EvidenceResult(
        question=question,
        analysis_type=AnalysisType.UNSUPPORTED,
        supported=False,
        summary=(
            "This question is not supported by the current "
            "deterministic analytics engine."
        ),
        warnings=[
            (
                "Supported topics currently include core KPIs, "
                "monthly revenue, revenue by category or state, "
                "delivery by state, and late versus on-time reviews."
            )
        ],
    )
