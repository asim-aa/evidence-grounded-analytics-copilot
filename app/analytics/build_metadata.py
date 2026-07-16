from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from app.analytics.profiling import profile_table
from app.analytics.semantic import enrich_profile_with_semantics
from app.config import ANALYTICAL_TABLE_NAME, DATABASE_PATH


METADATA_OUTPUT_PATH = Path("data/processed/semantic_metadata.json")


def _json_default(value: Any) -> Any:
    """
    Convert values not natively serializable by json.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if hasattr(value, "item"):
        return value.item()

    return str(value)


def build_semantic_metadata(
    database_path: Path = DATABASE_PATH,
    table_name: str = ANALYTICAL_TABLE_NAME,
) -> dict[str, Any]:
    """
    Profile the analytical table and enrich it with semantic metadata.
    """
    if not database_path.exists():
        raise FileNotFoundError(
            f"DuckDB database not found: {database_path}\n"
            "Run the ingestion pipeline first."
        )

    connection = duckdb.connect(
        str(database_path),
        read_only=True,
    )

    try:
        table_profile = profile_table(
            connection,
            table_name,
        )

        return enrich_profile_with_semantics(table_profile)

    finally:
        connection.close()


def save_semantic_metadata(
    metadata: dict[str, Any],
    output_path: Path = METADATA_OUTPUT_PATH,
) -> None:
    """
    Save semantic metadata as formatted JSON.
    """
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            default=_json_default,
        ),
        encoding="utf-8",
    )


def print_semantic_summary(
    metadata: dict[str, Any],
) -> None:
    """
    Print a concise semantic metadata summary.
    """
    role_counts: dict[str, int] = {}

    for column in metadata["columns"]:
        role = column["semantic_role"]
        role_counts[role] = role_counts.get(role, 0) + 1

    print("Semantic metadata created successfully")
    print(f"Table: {metadata['table_name']}")
    print(f"Rows: {metadata['row_count']:,}")
    print(f"Columns: {metadata['column_count']}")
    print(f"Grain: {metadata['table_grain']['description']}")

    print("\nSemantic roles:")

    for role, count in sorted(role_counts.items()):
        print(f"- {role}: {count}")

    print("\nImportant aggregation warnings:")

    for column in metadata["columns"]:
        warning = column.get("warning")

        if warning:
            print(f"- {column['name']}: {warning}")

    print(f"\nMetadata file: {METADATA_OUTPUT_PATH}")


def main() -> None:
    """
    Build, save, and summarize semantic metadata.
    """
    metadata = build_semantic_metadata()
    save_semantic_metadata(metadata)
    print_semantic_summary(metadata)


if __name__ == "__main__":
    main()
