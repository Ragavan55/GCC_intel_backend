from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.database import engine
from app.models import RawItem


logger = logging.getLogger(__name__)
FETCH_ONLY_TABLES = ("api_fetch_logs", "gcc_signals", "macro_indicators")


def migrate_legacy_tables() -> None:
    """Drop fetch-only tables and preserve raw item rows without their source FK."""
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        with connection.begin():
            tables = set(inspect(connection).get_table_names())
            for table_name in FETCH_ONLY_TABLES:
                if table_name in tables:
                    connection.exec_driver_sql(f'DROP TABLE "{table_name}"')

            if "raw_items" in tables:
                columns = {column["name"] for column in inspect(connection).get_columns("raw_items")}
                if "source_id" in columns:
                    has_sources = "data_sources" in tables
                    connection.exec_driver_sql('ALTER TABLE "raw_items" RENAME TO "raw_items_legacy"')
                    RawItem.__table__.create(connection)
                    source_expression = "COALESCE(ds.name, r.source, 'manual_upload')" if has_sources else "COALESCE(r.source, 'manual_upload')"
                    source_join = " LEFT JOIN data_sources ds ON ds.id = r.source_id" if has_sources else ""
                    connection.execute(
                        text(
                            "INSERT INTO raw_items "
                            "(id, external_id, payload_json, fetched_at, source, source_url, confidence, last_verified_at) "
                            "SELECT r.id, r.external_id, r.payload_json, r.fetched_at, " + source_expression + ", "
                            "r.source_url, r.confidence, r.last_verified_at "
                            "FROM raw_items_legacy r" + source_join
                        )
                    )
                    connection.exec_driver_sql('DROP TABLE "raw_items_legacy"')

            if "data_sources" in tables:
                connection.exec_driver_sql('DROP TABLE "data_sources"')
    logger.info("SQLite manual-upload schema migration complete")
