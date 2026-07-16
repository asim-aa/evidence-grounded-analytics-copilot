from pathlib import Path

import duckdb

from app.config import ANALYTICAL_TABLE_NAME
from app.database.ingestion import (
    create_analytical_table,
    load_raw_olist_tables,
    validate_required_files,
)
from app.database.validation import validate_analytical_table


def test_required_olist_files_exist() -> None:
    file_paths = validate_required_files()

    assert file_paths
    assert all(path.exists() for path in file_paths.values())


def test_analytical_table_has_valid_grain(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_olist.duckdb"

    connection = duckdb.connect(str(database_path))

    try:
        file_paths = validate_required_files()

        load_raw_olist_tables(
            connection,
            file_paths,
        )

        create_analytical_table(connection)

        validation = validate_analytical_table(
            connection,
            ANALYTICAL_TABLE_NAME,
        )

        assert validation["row_count"] > 0
        assert validation["grain_is_valid"] is True
        assert validation["duplicate_order_item_keys"] == 0
        assert validation["invalid_prices"] == 0

    finally:
        connection.close()
