from __future__ import annotations

import re
from typing import Any

import duckdb
import pandas as pd

from app.config import ANALYTICAL_TABLE_NAME


MONTH_NUMBERS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

ALLOWED_CHANGE_DIMENSIONS = {
    "product_category",
    "customer_state",
}


def get_monthly_revenue_components(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 100,
) -> pd.DataFrame:
    """
    Return monthly revenue, order volume, and average order value.

    Only months meeting the minimum-order threshold are included.
    Revenue is calculated from item-level values, while order volume
    uses distinct order identifiers.
    """
    if minimum_order_count <= 0:
        raise ValueError("minimum_order_count must be greater than zero.")

    return connection.execute(
        f"""
        WITH monthly_metrics AS (
            SELECT
                purchase_month_start,
                ROUND(
                    SUM(item_price),
                    2
                ) AS item_revenue,

                COUNT(
                    DISTINCT order_id
                ) AS order_count

            FROM {table_name}

            WHERE purchase_month_start IS NOT NULL

            GROUP BY purchase_month_start

            HAVING COUNT(
                DISTINCT order_id
            ) >= ?
        ),

        monthly_components AS (
            SELECT
                purchase_month_start,
                item_revenue,
                order_count,

                ROUND(
                    item_revenue
                    / NULLIF(order_count, 0),
                    2
                ) AS average_order_value

            FROM monthly_metrics
        ),

        with_previous_period AS (
            SELECT
                purchase_month_start,
                item_revenue,
                order_count,
                average_order_value,

                LAG(item_revenue) OVER (
                    ORDER BY purchase_month_start
                ) AS previous_item_revenue,

                LAG(order_count) OVER (
                    ORDER BY purchase_month_start
                ) AS previous_order_count,

                LAG(average_order_value) OVER (
                    ORDER BY purchase_month_start
                ) AS previous_average_order_value

            FROM monthly_components
        )

        SELECT
            purchase_month_start,
            item_revenue,
            order_count,
            average_order_value,

            previous_item_revenue,
            previous_order_count,
            previous_average_order_value,

            ROUND(
                item_revenue
                - previous_item_revenue,
                2
            ) AS revenue_change_amount,

            ROUND(
                100.0
                * (
                    item_revenue
                    - previous_item_revenue
                )
                / NULLIF(
                    previous_item_revenue,
                    0
                ),
                2
            ) AS revenue_change_percentage,

            order_count
            - previous_order_count
                AS order_count_change,

            ROUND(
                100.0
                * (
                    order_count
                    - previous_order_count
                )
                / NULLIF(
                    previous_order_count,
                    0
                ),
                2
            ) AS order_count_change_percentage,

            ROUND(
                average_order_value
                - previous_average_order_value,
                2
            ) AS average_order_value_change,

            ROUND(
                100.0
                * (
                    average_order_value
                    - previous_average_order_value
                )
                / NULLIF(
                    previous_average_order_value,
                    0
                ),
                2
            ) AS average_order_value_change_percentage

        FROM with_previous_period

        ORDER BY purchase_month_start
        """,
        [minimum_order_count],
    ).fetchdf()


def _find_named_month(
    normalized_question: str,
) -> int | None:
    """
    Find a standalone English month name in a question.

    Word boundaries prevent names such as 'may' from matching words
    like 'maybe'.
    """
    for month_name, month_number in MONTH_NUMBERS.items():
        if re.search(
            rf"\b{month_name}\b",
            normalized_question,
        ):
            return month_number

    return None


def resolve_target_month(
    question: str,
    monthly_components: pd.DataFrame,
) -> pd.Timestamp:
    """
    Resolve the target comparison month from a question.

    Supported forms include:
    - 2018-06
    - June 2018
    - June

    When no specific month is supplied, select the available month
    with the largest percentage revenue decline.
    """
    required_columns = {
        "purchase_month_start",
        "previous_item_revenue",
        "revenue_change_percentage",
    }

    missing_columns = required_columns - set(monthly_components.columns)

    if missing_columns:
        raise ValueError(
            "Monthly components are missing required columns: "
            f"{sorted(missing_columns)}"
        )

    available = monthly_components.dropna(
        subset=[
            "previous_item_revenue",
            "revenue_change_percentage",
        ]
    ).copy()

    if available.empty:
        raise ValueError("At least two complete months are required.")

    available["purchase_month_start"] = pd.to_datetime(
        available["purchase_month_start"]
    )

    normalized = question.strip().lower()

    numeric_match = re.search(
        r"\b(20\d{2})-(0[1-9]|1[0-2])\b",
        normalized,
    )

    if numeric_match is not None:
        target = pd.Timestamp(
            year=int(numeric_match.group(1)),
            month=int(numeric_match.group(2)),
            day=1,
        )

        if not (available["purchase_month_start"] == target).any():
            raise ValueError(
                f"{target:%Y-%m} is not an available complete comparison month."
            )

        return target

    detected_month = _find_named_month(normalized)

    if detected_month is not None:
        candidates = available[
            available["purchase_month_start"].dt.month == detected_month
        ].copy()

        year_match = re.search(
            r"\b(20\d{2})\b",
            normalized,
        )

        if year_match is not None:
            requested_year = int(year_match.group(1))

            candidates = candidates[
                candidates["purchase_month_start"].dt.year == requested_year
            ]

        if candidates.empty:
            raise ValueError(
                "The requested month is not available as a complete comparison period."
            )

        return pd.Timestamp(candidates["purchase_month_start"].max())

    largest_decline_row = available.sort_values(
        "revenue_change_percentage",
        ascending=True,
    ).iloc[0]

    return pd.Timestamp(largest_decline_row["purchase_month_start"])


def _get_dimension_revenue_change(
    connection: duckdb.DuckDBPyConnection,
    dimension: str,
    current_month: pd.Timestamp,
    previous_month: pd.Timestamp,
    table_name: str,
) -> pd.DataFrame:
    """
    Compare revenue between two months for an approved dimension.
    """
    if dimension not in ALLOWED_CHANGE_DIMENSIONS:
        raise ValueError(f"Unsupported revenue-change dimension: {dimension}")

    result = connection.execute(
        f"""
        WITH previous_period AS (
            SELECT
                {dimension} AS dimension_value,

                SUM(item_price)
                    AS previous_revenue

            FROM {table_name}

            WHERE purchase_month_start = ?
              AND {dimension} IS NOT NULL

            GROUP BY {dimension}
        ),

        current_period AS (
            SELECT
                {dimension} AS dimension_value,

                SUM(item_price)
                    AS current_revenue

            FROM {table_name}

            WHERE purchase_month_start = ?
              AND {dimension} IS NOT NULL

            GROUP BY {dimension}
        ),

        changes AS (
            SELECT
                COALESCE(
                    current_period.dimension_value,
                    previous_period.dimension_value
                ) AS dimension_value,

                COALESCE(
                    previous_period.previous_revenue,
                    0
                ) AS previous_revenue,

                COALESCE(
                    current_period.current_revenue,
                    0
                ) AS current_revenue,

                COALESCE(
                    current_period.current_revenue,
                    0
                )
                - COALESCE(
                    previous_period.previous_revenue,
                    0
                ) AS change_amount

            FROM previous_period

            FULL OUTER JOIN current_period
                ON previous_period.dimension_value
                   = current_period.dimension_value
        ),

        with_total_change AS (
            SELECT
                *,
                SUM(change_amount) OVER ()
                    AS total_change
            FROM changes
        )

        SELECT
            dimension_value,

            ROUND(
                previous_revenue,
                2
            ) AS previous_revenue,

            ROUND(
                current_revenue,
                2
            ) AS current_revenue,

            ROUND(
                change_amount,
                2
            ) AS change_amount,

            ROUND(
                100.0
                * change_amount
                / NULLIF(
                    previous_revenue,
                    0
                ),
                2
            ) AS change_percentage,

            ROUND(
                100.0
                * change_amount
                / NULLIF(
                    total_change,
                    0
                ),
                2
            ) AS contribution_to_total_change_percentage

        FROM with_total_change
        """,
        [
            previous_month.to_pydatetime(),
            current_month.to_pydatetime(),
        ],
    ).fetchdf()

    if result.empty:
        return result

    total_change = float(result["change_amount"].sum())

    # For a decline, place the largest negative drivers first.
    # For an increase, place the largest positive drivers first.
    ascending = total_change < 0

    return result.sort_values(
        "change_amount",
        ascending=ascending,
    ).reset_index(drop=True)


def get_category_revenue_change(
    connection: duckdb.DuckDBPyConnection,
    current_month: pd.Timestamp,
    previous_month: pd.Timestamp,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> pd.DataFrame:
    """
    Compare category revenue between two months.
    """
    result = _get_dimension_revenue_change(
        connection=connection,
        dimension="product_category",
        current_month=current_month,
        previous_month=previous_month,
        table_name=table_name,
    )

    return result.rename(
        columns={
            "dimension_value": "product_category",
        }
    )


def get_state_revenue_change(
    connection: duckdb.DuckDBPyConnection,
    current_month: pd.Timestamp,
    previous_month: pd.Timestamp,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> pd.DataFrame:
    """
    Compare state revenue between two months.
    """
    result = _get_dimension_revenue_change(
        connection=connection,
        dimension="customer_state",
        current_month=current_month,
        previous_month=previous_month,
        table_name=table_name,
    )

    return result.rename(
        columns={
            "dimension_value": "customer_state",
        }
    )


def investigate_revenue_change(
    connection: duckdb.DuckDBPyConnection,
    question: str,
    table_name: str = ANALYTICAL_TABLE_NAME,
    minimum_order_count: int = 100,
    driver_limit: int = 5,
) -> dict[str, Any]:
    """
    Investigate one monthly revenue change using deterministic evidence.
    """
    if minimum_order_count <= 0:
        raise ValueError("minimum_order_count must be greater than zero.")

    if driver_limit <= 0:
        raise ValueError("driver_limit must be greater than zero.")

    monthly = get_monthly_revenue_components(
        connection=connection,
        table_name=table_name,
        minimum_order_count=minimum_order_count,
    ).copy()

    monthly["purchase_month_start"] = pd.to_datetime(monthly["purchase_month_start"])

    current_month = resolve_target_month(
        question,
        monthly,
    )

    matching_positions = monthly.index[
        monthly["purchase_month_start"] == current_month
    ].tolist()

    if len(matching_positions) != 1:
        raise ValueError("The target month could not be uniquely resolved.")

    row_label = matching_positions[0]
    current_position = monthly.index.get_loc(row_label)

    if not isinstance(current_position, int):
        raise RuntimeError("The monthly index did not resolve to one position.")

    if current_position == 0:
        raise ValueError("The target month has no previous complete month.")

    current = monthly.iloc[current_position]
    previous = monthly.iloc[current_position - 1]

    previous_month = pd.Timestamp(previous["purchase_month_start"])

    category_changes = get_category_revenue_change(
        connection=connection,
        current_month=current_month,
        previous_month=previous_month,
        table_name=table_name,
    )

    state_changes = get_state_revenue_change(
        connection=connection,
        current_month=current_month,
        previous_month=previous_month,
        table_name=table_name,
    )

    return {
        "current_month": current_month,
        "previous_month": previous_month,
        "current_metrics": current.to_dict(),
        "previous_metrics": previous.to_dict(),
        "category_changes": (
            category_changes.head(driver_limit).reset_index(drop=True)
        ),
        "state_changes": (state_changes.head(driver_limit).reset_index(drop=True)),
        "minimum_order_count": minimum_order_count,
    }
