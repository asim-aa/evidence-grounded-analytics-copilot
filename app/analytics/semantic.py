from __future__ import annotations

from copy import deepcopy
from typing import Any


COLUMN_REGISTRY: dict[str, dict[str, Any]] = {
    "order_id": {
        "semantic_role": "identifier",
        "entity": "order",
        "business_meaning": "Unique identifier for an order.",
        "metric_grain": "order",
        "allowed_aggregations": ["count_distinct"],
        "default_aggregation": "count_distinct",
        "is_additive": False,
    },
    "order_item_id": {
        "semantic_role": "identifier",
        "entity": "order_item",
        "business_meaning": ("Sequence number identifying an item within an order."),
        "metric_grain": "order_item",
        "allowed_aggregations": ["count"],
        "default_aggregation": "count",
        "is_additive": False,
    },
    "customer_id": {
        "semantic_role": "identifier",
        "entity": "customer_order_record",
        "business_meaning": ("Customer identifier associated with a specific order."),
        "metric_grain": "order",
        "allowed_aggregations": ["count_distinct"],
        "default_aggregation": "count_distinct",
        "is_additive": False,
    },
    "customer_unique_id": {
        "semantic_role": "identifier",
        "entity": "customer",
        "business_meaning": (
            "Stable identifier representing the same customer across multiple orders."
        ),
        "metric_grain": "customer",
        "allowed_aggregations": ["count_distinct"],
        "default_aggregation": "count_distinct",
        "is_additive": False,
    },
    "customer_city": {
        "semantic_role": "dimension",
        "entity": "geography",
        "business_meaning": "Customer city.",
        "metric_grain": "order",
        "allowed_aggregations": ["group_by", "count_distinct"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "customer_state": {
        "semantic_role": "dimension",
        "entity": "geography",
        "business_meaning": "Customer state abbreviation.",
        "metric_grain": "order",
        "allowed_aggregations": ["group_by", "count_distinct"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "order_status": {
        "semantic_role": "dimension",
        "entity": "order",
        "business_meaning": "Current or final status of the order.",
        "metric_grain": "order",
        "allowed_aggregations": ["group_by", "count_distinct"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "purchase_timestamp": {
        "semantic_role": "time_dimension",
        "entity": "order",
        "business_meaning": ("Timestamp when the customer placed the order."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "group_by_day",
            "group_by_week",
            "group_by_month",
            "group_by_year",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "group_by_month",
        "is_additive": False,
        "is_primary_time_dimension": True,
    },
    "approved_timestamp": {
        "semantic_role": "time_dimension",
        "entity": "order",
        "business_meaning": ("Timestamp when the order payment was approved."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "group_by_day",
            "group_by_month",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "group_by_month",
        "is_additive": False,
    },
    "delivered_carrier_timestamp": {
        "semantic_role": "time_dimension",
        "entity": "delivery",
        "business_meaning": ("Timestamp when the order was handed to the carrier."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "group_by_day",
            "group_by_month",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "group_by_month",
        "is_additive": False,
    },
    "delivered_customer_timestamp": {
        "semantic_role": "time_dimension",
        "entity": "delivery",
        "business_meaning": ("Timestamp when the order reached the customer."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "group_by_day",
            "group_by_month",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "group_by_month",
        "is_additive": False,
    },
    "estimated_delivery_timestamp": {
        "semantic_role": "time_dimension",
        "entity": "delivery",
        "business_meaning": ("Delivery date originally estimated for the customer."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "group_by_day",
            "group_by_month",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "group_by_month",
        "is_additive": False,
    },
    "product_id": {
        "semantic_role": "identifier",
        "entity": "product",
        "business_meaning": "Unique identifier for a product.",
        "metric_grain": "product",
        "allowed_aggregations": ["count_distinct"],
        "default_aggregation": "count_distinct",
        "is_additive": False,
    },
    "product_category": {
        "semantic_role": "dimension",
        "entity": "product",
        "business_meaning": ("English-language category assigned to the product."),
        "metric_grain": "product",
        "allowed_aggregations": ["group_by", "count_distinct"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "seller_id": {
        "semantic_role": "identifier",
        "entity": "seller",
        "business_meaning": "Unique identifier for a marketplace seller.",
        "metric_grain": "seller",
        "allowed_aggregations": ["count_distinct"],
        "default_aggregation": "count_distinct",
        "is_additive": False,
    },
    "item_price": {
        "semantic_role": "measure",
        "entity": "order_item",
        "business_meaning": (
            "Price charged for one purchased item, excluding freight."
        ),
        "metric_grain": "order_item",
        "allowed_aggregations": [
            "sum",
            "average",
            "minimum",
            "maximum",
            "median",
        ],
        "default_aggregation": "sum",
        "is_additive": True,
        "format": "currency",
    },
    "freight_value": {
        "semantic_role": "measure",
        "entity": "order_item",
        "business_meaning": ("Freight charge allocated to one purchased item."),
        "metric_grain": "order_item",
        "allowed_aggregations": [
            "sum",
            "average",
            "minimum",
            "maximum",
            "median",
        ],
        "default_aggregation": "sum",
        "is_additive": True,
        "format": "currency",
    },
    "item_total_value": {
        "semantic_role": "measure",
        "entity": "order_item",
        "business_meaning": ("Item price plus freight value for one purchased item."),
        "metric_grain": "order_item",
        "allowed_aggregations": [
            "sum",
            "average",
            "minimum",
            "maximum",
            "median",
        ],
        "default_aggregation": "sum",
        "is_additive": True,
        "format": "currency",
    },
    "total_payment_value": {
        "semantic_role": "measure",
        "entity": "order",
        "business_meaning": ("Total customer payment value for the complete order."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_sum",
            "order_level_average",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "order_level_sum",
        "is_additive": False,
        "format": "currency",
        "warning": (
            "This order-level value is repeated across item rows. "
            "Deduplicate by order_id before summing or averaging."
        ),
    },
    "max_payment_installments": {
        "semantic_role": "measure",
        "entity": "order",
        "business_meaning": ("Maximum number of installments used for an order."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_average",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "warning": ("This order-level value is repeated across item rows."),
    },
    "payment_record_count": {
        "semantic_role": "measure",
        "entity": "order",
        "business_meaning": ("Number of payment records associated with an order."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_sum",
            "order_level_average",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "warning": ("This order-level value is repeated across item rows."),
    },
    "payment_types": {
        "semantic_role": "dimension",
        "entity": "payment",
        "business_meaning": ("Distinct payment methods used for an order."),
        "metric_grain": "order",
        "allowed_aggregations": ["group_by", "count_distinct"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "average_review_score": {
        "semantic_role": "measure",
        "entity": "order",
        "business_meaning": ("Average customer review score associated with an order."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_average",
            "minimum",
            "maximum",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "format": "rating_1_to_5",
        "warning": (
            "This order-level score is repeated across item rows. "
            "Reduce to one row per order before calculating averages."
        ),
    },
    "review_count": {
        "semantic_role": "measure",
        "entity": "order",
        "business_meaning": ("Number of review records associated with an order."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_sum",
            "order_level_average",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "warning": ("This order-level value is repeated across item rows."),
    },
    "delivery_days": {
        "semantic_role": "measure",
        "entity": "delivery",
        "business_meaning": ("Number of days from purchase to customer delivery."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_average",
            "minimum",
            "maximum",
            "median",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "format": "days",
        "warning": ("This order-level value is repeated across item rows."),
    },
    "estimated_delivery_days": {
        "semantic_role": "measure",
        "entity": "delivery",
        "business_meaning": ("Number of days between purchase and estimated delivery."),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_average",
            "minimum",
            "maximum",
            "median",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "format": "days",
        "warning": ("This order-level value is repeated across item rows."),
    },
    "delivery_delay_days": {
        "semantic_role": "measure",
        "entity": "delivery",
        "business_meaning": (
            "Difference in days between actual and estimated delivery. "
            "Positive values represent late delivery."
        ),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_average",
            "minimum",
            "maximum",
            "median",
        ],
        "default_aggregation": "order_level_average",
        "is_additive": False,
        "format": "days",
        "warning": ("This order-level value is repeated across item rows."),
    },
    "is_late_delivery": {
        "semantic_role": "boolean_measure",
        "entity": "delivery",
        "business_meaning": (
            "Whether the customer received the order after the estimated delivery date."
        ),
        "metric_grain": "order",
        "allowed_aggregations": [
            "order_level_percentage_true",
            "count_true",
        ],
        "default_aggregation": "order_level_percentage_true",
        "is_additive": False,
        "warning": ("This order-level flag is repeated across item rows."),
    },
    "purchase_year": {
        "semantic_role": "time_dimension",
        "entity": "order",
        "business_meaning": "Calendar year of purchase.",
        "metric_grain": "order",
        "allowed_aggregations": ["group_by"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "purchase_month": {
        "semantic_role": "time_dimension",
        "entity": "order",
        "business_meaning": ("Calendar month number of purchase, from 1 through 12."),
        "metric_grain": "order",
        "allowed_aggregations": ["group_by"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
    "purchase_month_start": {
        "semantic_role": "time_dimension",
        "entity": "order",
        "business_meaning": (
            "First day of the month in which the order was purchased."
        ),
        "metric_grain": "order",
        "allowed_aggregations": ["group_by"],
        "default_aggregation": "group_by",
        "is_additive": False,
    },
}


def infer_fallback_semantics(
    column_profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Infer basic semantic metadata for an unregistered column.
    """
    column_name = column_profile["name"]
    database_type = column_profile["database_type"]
    cardinality_ratio = column_profile["cardinality_ratio"]

    if column_name.endswith("_id"):
        role = "identifier"
        default_aggregation = "count_distinct"
        allowed_aggregations = ["count_distinct"]
    elif database_type.startswith(("DATE", "TIMESTAMP", "TIME")):
        role = "time_dimension"
        default_aggregation = "group_by"
        allowed_aggregations = ["group_by", "minimum", "maximum"]
    elif database_type == "BOOLEAN":
        role = "boolean_measure"
        default_aggregation = "percentage_true"
        allowed_aggregations = ["percentage_true", "count_true"]
    elif database_type.startswith(
        (
            "TINYINT",
            "SMALLINT",
            "INTEGER",
            "BIGINT",
            "FLOAT",
            "DOUBLE",
            "DECIMAL",
        )
    ):
        role = "measure"
        default_aggregation = "average"
        allowed_aggregations = [
            "average",
            "minimum",
            "maximum",
            "median",
        ]
    elif cardinality_ratio < 0.20:
        role = "dimension"
        default_aggregation = "group_by"
        allowed_aggregations = ["group_by", "count_distinct"]
    else:
        role = "attribute"
        default_aggregation = "none"
        allowed_aggregations = ["count_distinct"]

    return {
        "semantic_role": role,
        "entity": "unknown",
        "business_meaning": (f"Automatically inferred metadata for {column_name}."),
        "metric_grain": "unknown",
        "allowed_aggregations": allowed_aggregations,
        "default_aggregation": default_aggregation,
        "is_additive": False,
        "inference_source": "heuristic",
    }


def enrich_profile_with_semantics(
    table_profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Add semantic metadata to every profiled column.
    """
    enriched_columns: list[dict[str, Any]] = []

    for column_profile in table_profile["columns"]:
        column_name = column_profile["name"]

        semantic_metadata = deepcopy(
            COLUMN_REGISTRY.get(
                column_name,
                infer_fallback_semantics(column_profile),
            )
        )

        semantic_metadata.setdefault(
            "inference_source",
            "business_registry",
        )

        enriched_columns.append(
            {
                **column_profile,
                **semantic_metadata,
            }
        )

    return {
        **table_profile,
        "table_grain": {
            "description": ("One row represents one purchased item within an order."),
            "key_columns": [
                "order_id",
                "order_item_id",
            ],
        },
        "important_rules": [
            (
                "Item-level measures such as item_price and freight_value "
                "may be summed directly."
            ),
            (
                "Order-level measures repeated across item rows must be "
                "reduced to one row per order before aggregation."
            ),
            (
                "Revenue is available, but product cost and profit are "
                "not present in the dataset."
            ),
        ],
        "columns": enriched_columns,
    }
