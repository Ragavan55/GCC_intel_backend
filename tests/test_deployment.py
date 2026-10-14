from __future__ import annotations

from types import SimpleNamespace

from app import migrations
from app.config import Settings


def test_legacy_sqlite_migration_skips_postgresql(monkeypatch) -> None:
    class UnexpectedEngine:
        dialect = SimpleNamespace(name="postgresql")

        def connect(self):
            raise AssertionError("SQLite migration must not connect to PostgreSQL")

    monkeypatch.setattr(migrations, "engine", UnexpectedEngine())

    migrations.migrate_legacy_tables()


def test_render_postgres_urls_use_psycopg_driver() -> None:
    legacy = Settings(database_url="postgres://user:pass@db.example.test/app")
    standard = Settings(database_url="postgresql://user:pass@db.example.test/app")

    assert legacy.effective_database_url == "postgresql+psycopg://user:pass@db.example.test/app"
    assert standard.effective_database_url == "postgresql+psycopg://user:pass@db.example.test/app"