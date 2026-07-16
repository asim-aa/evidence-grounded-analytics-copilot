from __future__ import annotations

from typing import Any, cast

import duckdb

from app.config import ANALYTICAL_TABLE_NAME


NUMERIC_TYPE_PREFIXES = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
)

TEMPORAL_TYPE_PREFIXES = (
    "DATE",
    "TIMESTAMP",
    "TIME",
)


def _quote_identifier(identifier: str) -> str:
    """
    Safely quote a DuckDB identifier.
    """
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _fetch_scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> Any:
    """
    Execute a query expected to return one row with one value.
    """
    result = connection.execute(query).fetchone()

    if result is None:
        raise RuntimeError("Profiling query returned no result.")

    return result[0]


def _fetch_row(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> tuple[Any, ...]:
    """
    Execute a query expected to return exactly one row.
    """
    result = connection.execute(query).fetchone()

    if result is None:
        raise RuntimeError("Profiling query returned no row.")

    return tuple(result)


def get_table_schema(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> list[dict[str, Any]]:
    """
    Return DuckDB schema metadata for a table.
    """
    schema_records = (
        connection.execute(f"DESCRIBE {table_name}").fetchdf().to_dict(orient="records")
    )

    return cast(
        list[dict[str, Any]],
        schema_records,
    )


def profile_column(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
    column_type: str,
    row_count: int,
) -> dict[str, Any]:
    """
    Build a deterministic profile for one column.
    """
    quoted_column = _quote_identifier(column_name)

    null_count = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE {quoted_column} IS NULL
            """,
        )
    )

    unique_count = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(DISTINCT {quoted_column})
            FROM {table_name}
            """,
        )
    )

    sample_values = (
        connection.execute(
            f"""
            SELECT DISTINCT {quoted_column}
            FROM {table_name}
            WHERE {quoted_column} IS NOT NULL
            LIMIT 5
            """
        )
        .fetchdf()[column_name]
        .tolist()
    )

    profile: dict[str, Any] = {
        "name": column_name,
        "database_type": column_type,
        "null_count": null_count,
        "null_percentage": (
            round(
                (null_count / row_count) * 100,
                2,
            )
            if row_count > 0
            else 0.0
        ),
        "unique_count": unique_count,
        "cardinality_ratio": (
            round(
                unique_count / row_count,
                4,
            )
            if row_count > 0
            else 0.0
        ),
        "sample_values": sample_values,
    }

    if column_type.startswith(NUMERIC_TYPE_PREFIXES):
        minimum, maximum, mean, median = _fetch_row(
            connection,
            f"""
            SELECT
                MIN({quoted_column}),
                MAX({quoted_column}),
                AVG({quoted_column}),
                MEDIAN({quoted_column})
            FROM {table_name}
            """,
        )

        profile["statistics"] = {
            "minimum": minimum,
            "maximum": maximum,
            "mean": mean,
            "median": median,
        }

    elif column_type.startswith(TEMPORAL_TYPE_PREFIXES):
        minimum, maximum = _fetch_row(
            connection,
            f"""
            SELECT
                MIN({quoted_column}),
                MAX({quoted_column})
            FROM {table_name}
            """,
        )

        profile["statistics"] = {
            "minimum": minimum,
            "maximum": maximum,
        }

    else:
        most_common_dataframe = connection.execute(
            f"""
            SELECT
                {quoted_column} AS value,
                COUNT(*) AS frequency
            FROM {table_name}
            WHERE {quoted_column} IS NOT NULL
            GROUP BY {quoted_column}
            ORDER BY frequency DESC
            LIMIT 5
            """
        ).fetchdf()

        most_common_records = most_common_dataframe.to_dict(orient="records")

        profile["most_common_values"] = cast(
            list[dict[str, Any]],
            most_common_records,
        )

    return profile


def profile_table(
    connection: duckdb.DuckDBPyConnection,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> dict[str, Any]:
    """
    Generate a deterministic profile for an analytical table.
    """
    row_count = int(
        _fetch_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            """,
        )
    )

    schema = get_table_schema(
        connection,
        table_name,
    )

    columns = [
        profile_column(
            connection=connection,
            table_name=table_name,
            column_name=str(column["column_name"]),
            column_type=str(column["column_type"]),
            row_count=row_count,
        )
        for column in schema
    ]

    return {
        "table_name": table_name,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
    }
