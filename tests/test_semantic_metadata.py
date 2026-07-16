from app.analytics.build_metadata import (
    build_semantic_metadata,
)
from app.analytics.semantic import COLUMN_REGISTRY


def test_all_current_columns_have_registered_semantics() -> None:
    metadata = build_semantic_metadata()

    profile_column_names = {column["name"] for column in metadata["columns"]}

    registered_column_names = set(COLUMN_REGISTRY)

    assert profile_column_names == registered_column_names


def test_item_price_is_additive_item_measure() -> None:
    metadata = build_semantic_metadata()

    item_price = next(
        column for column in metadata["columns"] if column["name"] == "item_price"
    )

    assert item_price["semantic_role"] == "measure"
    assert item_price["metric_grain"] == "order_item"
    assert item_price["default_aggregation"] == "sum"
    assert item_price["is_additive"] is True


def test_payment_value_requires_order_level_aggregation() -> None:
    metadata = build_semantic_metadata()

    payment_value = next(
        column
        for column in metadata["columns"]
        if column["name"] == "total_payment_value"
    )

    assert payment_value["metric_grain"] == "order"
    assert payment_value["is_additive"] is False
    assert payment_value["default_aggregation"] == "order_level_sum"
    assert "warning" in payment_value


def test_primary_time_dimension_is_purchase_timestamp() -> None:
    metadata = build_semantic_metadata()

    purchase_timestamp = next(
        column
        for column in metadata["columns"]
        if column["name"] == "purchase_timestamp"
    )

    assert purchase_timestamp["semantic_role"] == "time_dimension"
    assert purchase_timestamp["is_primary_time_dimension"] is True
