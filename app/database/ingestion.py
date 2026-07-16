from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.config import (
    ANALYTICAL_TABLE_NAME,
    DATABASE_PATH,
    RAW_DATA_DIRECTORY,
    REQUIRED_FILES,
)
from app.database.validation import (
    print_validation_report,
    validate_analytical_table,
)


def validate_required_files(
    raw_data_directory: Path = RAW_DATA_DIRECTORY,
) -> dict[str, Path]:
    """
    Confirm that all required Olist files exist.

    Returns:
        Mapping from logical dataset name to file path.

    Raises:
        FileNotFoundError: If one or more required files are missing.
    """

    file_paths = {
        dataset_name: raw_data_directory / filename
        for dataset_name, filename in REQUIRED_FILES.items()
    }

    missing_files = [
        file_path for file_path in file_paths.values() if not file_path.exists()
    ]

    if missing_files:
        missing_list = "\n".join(f"- {file_path}" for file_path in missing_files)

        raise FileNotFoundError(
            "The following required Olist files are missing:\n"
            f"{missing_list}\n\n"
            "Place the extracted CSV files inside data/raw/."
        )

    return file_paths


def create_database_connection(
    database_path: Path = DATABASE_PATH,
) -> duckdb.DuckDBPyConnection:
    """
    Create a persistent DuckDB connection.
    """

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return duckdb.connect(str(database_path))


def load_raw_olist_tables(
    connection: duckdb.DuckDBPyConnection,
    file_paths: dict[str, Path],
) -> None:
    """
    Load required Olist CSV files into DuckDB staging tables.
    """

    for logical_name, file_path in file_paths.items():
        table_name = f"raw_{logical_name}"

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT *
            FROM read_csv_auto(
                ?,
                header = true,
                sample_size = -1
            )
            """,
            [str(file_path)],
        )


def create_analytical_table(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create one analytical row per order item.

    Payments and reviews are aggregated to the order level before joining.
    This prevents accidental row multiplication.
    """

    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {ANALYTICAL_TABLE_NAME} AS

        WITH payment_summary AS (
            SELECT
                order_id,
                SUM(payment_value) AS total_payment_value,
                MAX(payment_installments) AS max_payment_installments,
                COUNT(*) AS payment_record_count,
                STRING_AGG(
                    DISTINCT payment_type,
                    ', '
                    ORDER BY payment_type
                ) AS payment_types
            FROM raw_payments
            GROUP BY order_id
        ),

        review_summary AS (
            SELECT
                order_id,
                AVG(review_score) AS average_review_score,
                COUNT(*) AS review_count
            FROM raw_reviews
            GROUP BY order_id
        ),

        translated_products AS (
            SELECT
                products.product_id,

                COALESCE(
                    translation.product_category_name_english,
                    products.product_category_name,
                    'unknown'
                ) AS product_category,

                products.product_name_lenght
                    AS product_name_length,

                products.product_description_lenght
                    AS product_description_length,

                products.product_photos_qty
                    AS product_photo_count,

                products.product_weight_g,
                products.product_length_cm,
                products.product_height_cm,
                products.product_width_cm

            FROM raw_products AS products

            LEFT JOIN raw_category_translation AS translation
                ON products.product_category_name =
                   translation.product_category_name
        )

        SELECT
            orders.order_id,
            items.order_item_id,

            orders.customer_id,
            customers.customer_unique_id,
            customers.customer_city,
            customers.customer_state,

            orders.order_status,

            CAST(
                orders.order_purchase_timestamp AS TIMESTAMP
            ) AS purchase_timestamp,

            CAST(
                orders.order_approved_at AS TIMESTAMP
            ) AS approved_timestamp,

            CAST(
                orders.order_delivered_carrier_date AS TIMESTAMP
            ) AS delivered_carrier_timestamp,

            CAST(
                orders.order_delivered_customer_date AS TIMESTAMP
            ) AS delivered_customer_timestamp,

            CAST(
                orders.order_estimated_delivery_date AS TIMESTAMP
            ) AS estimated_delivery_timestamp,

            items.product_id,
            products.product_category,
            items.seller_id,

            CAST(items.price AS DOUBLE)
                AS item_price,

            CAST(items.freight_value AS DOUBLE)
                AS freight_value,

            CAST(
                items.price + items.freight_value
                AS DOUBLE
            ) AS item_total_value,

            payments.total_payment_value,
            payments.max_payment_installments,
            payments.payment_record_count,
            payments.payment_types,

            reviews.average_review_score,
            reviews.review_count,

            DATE_DIFF(
                'day',
                CAST(
                    orders.order_purchase_timestamp
                    AS TIMESTAMP
                ),
                CAST(
                    orders.order_delivered_customer_date
                    AS TIMESTAMP
                )
            ) AS delivery_days,

            DATE_DIFF(
                'day',
                CAST(
                    orders.order_purchase_timestamp
                    AS TIMESTAMP
                ),
                CAST(
                    orders.order_estimated_delivery_date
                    AS TIMESTAMP
                )
            ) AS estimated_delivery_days,

            DATE_DIFF(
                'day',
                CAST(
                    orders.order_estimated_delivery_date
                    AS TIMESTAMP
                ),
                CAST(
                    orders.order_delivered_customer_date
                    AS TIMESTAMP
                )
            ) AS delivery_delay_days,

            CASE
                WHEN orders.order_delivered_customer_date IS NULL
                    THEN NULL

                WHEN CAST(
                    orders.order_delivered_customer_date
                    AS TIMESTAMP
                ) > CAST(
                    orders.order_estimated_delivery_date
                    AS TIMESTAMP
                )
                    THEN TRUE

                ELSE FALSE
            END AS is_late_delivery,

            EXTRACT(
                YEAR
                FROM CAST(
                    orders.order_purchase_timestamp
                    AS TIMESTAMP
                )
            ) AS purchase_year,

            EXTRACT(
                MONTH
                FROM CAST(
                    orders.order_purchase_timestamp
                    AS TIMESTAMP
                )
            ) AS purchase_month,

            DATE_TRUNC(
                'month',
                CAST(
                    orders.order_purchase_timestamp
                    AS TIMESTAMP
                )
            ) AS purchase_month_start

        FROM raw_orders AS orders

        INNER JOIN raw_order_items AS items
            ON orders.order_id = items.order_id

        LEFT JOIN raw_customers AS customers
            ON orders.customer_id = customers.customer_id

        LEFT JOIN translated_products AS products
            ON items.product_id = products.product_id

        LEFT JOIN payment_summary AS payments
            ON orders.order_id = payments.order_id

        LEFT JOIN review_summary AS reviews
            ON orders.order_id = reviews.order_id
        """
    )


def get_table_summary(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> dict[str, Any]:
    """
    Return row count and schema information.
    """

    row_count_result = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        """
    ).fetchone()

    if row_count_result is None:
        raise RuntimeError(f"Could not count rows in table: {table_name}")

    columns = connection.execute(
        f"""
        DESCRIBE {table_name}
        """
    ).fetchdf()

    return {
        "table_name": table_name,
        "row_count": int(row_count_result[0]),
        "column_count": len(columns),
        "columns": columns.to_dict(orient="records"),
    }


def run_sample_analysis(
    connection: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """
    Calculate item revenue and order-level operational metrics by state.

    Revenue is aggregated from item-level rows.
    Reviews and delivery rates are first reduced to one row per order.
    """

    return connection.execute(
        f"""
        WITH state_revenue AS (
            SELECT
                customer_state,
                COUNT(DISTINCT order_id) AS order_count,
                ROUND(SUM(item_price), 2) AS item_revenue,
                ROUND(SUM(freight_value), 2) AS freight_revenue
            FROM {ANALYTICAL_TABLE_NAME}
            GROUP BY customer_state
        ),

        order_level_operations AS (
            SELECT
                order_id,
                customer_state,
                MAX(average_review_score) AS review_score,
                BOOL_OR(is_late_delivery) AS is_late_delivery
            FROM {ANALYTICAL_TABLE_NAME}
            GROUP BY
                order_id,
                customer_state
        ),

        state_operations AS (
            SELECT
                customer_state,

                ROUND(
                    AVG(review_score),
                    2
                ) AS average_review_score,

                ROUND(
                    100.0 * AVG(
                        CASE
                            WHEN is_late_delivery = TRUE
                                THEN 1
                            WHEN is_late_delivery = FALSE
                                THEN 0
                            ELSE NULL
                        END
                    ),
                    2
                ) AS late_delivery_percentage

            FROM order_level_operations
            GROUP BY customer_state
        )

        SELECT
            revenue.customer_state,
            revenue.order_count,
            revenue.item_revenue,
            revenue.freight_revenue,
            operations.average_review_score,
            operations.late_delivery_percentage

        FROM state_revenue AS revenue

        LEFT JOIN state_operations AS operations
            ON revenue.customer_state =
               operations.customer_state

        ORDER BY revenue.item_revenue DESC
        LIMIT 10
        """
    ).fetchdf()


def build_olist_database() -> duckdb.DuckDBPyConnection:
    """
    Run the complete Olist ingestion pipeline.
    """

    file_paths = validate_required_files()
    connection = create_database_connection()

    load_raw_olist_tables(
        connection,
        file_paths,
    )

    create_analytical_table(connection)

    return connection


def print_table_summary(
    summary: dict[str, Any],
) -> None:
    """
    Print table metadata and schema.
    """

    print("Olist analytical database created successfully")
    print(f"Database: {DATABASE_PATH}")
    print(f"Table: {summary['table_name']}")
    print(f"Rows: {summary['row_count']:,}")
    print(f"Columns: {summary['column_count']}")

    print("\nSchema:")

    for column in summary["columns"]:
        print(f"- {column['column_name']}: {column['column_type']}")


def main() -> None:
    """
    Build, validate, and preview the analytical database.
    """

    connection = build_olist_database()

    try:
        summary = get_table_summary(connection)
        validation = validate_analytical_table(connection)
        sample_analysis = run_sample_analysis(connection)

        print_table_summary(summary)
        print_validation_report(validation)

        print("\nSample analysis:")
        print(
            sample_analysis.to_string(
                index=False,
            )
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
