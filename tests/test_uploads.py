from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, SessionLocal
from app.main import app
from app.models import ChatMessage, Gcc, RawItem


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def signup(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Upload Tester",
            "email": f"upload-{uuid.uuid4().hex}@example.com",
            "password": "strong-upload-password",
            "role": "other",
        },
    )
    assert response.status_code == 201


def test_upload_catalog_exposes_typed_columns_and_natural_keys(client: TestClient) -> None:
    signup(client)
    response = client.get("/api/uploads/tables")

    assert response.status_code == 200
    catalog = {table["key"]: table for table in response.json()["tables"]}
    assert set(catalog) == {
        "cost_assumptions", "gccs", "providers", "real_estate_clusters", "salary_benchmarks",
        "scoring_weights", "state_incentives", "cities", "raw_items",
    }
    assert "rea_estate_cluster" in catalog["real_estate_clusters"]["aliases"]
    assert catalog["gccs"]["natural_key"] == ["company", "city"]
    assert next(column for column in catalog["gccs"]["columns"] if column["name"] == "headcount")["type"] == "integer | null"


def test_empty_table_is_not_not_found_and_unknown_table_is(client: TestClient) -> None:
    signup(client)
    empty_or_populated = client.get("/api/uploads/cost_assumptions/records")
    unknown = client.get("/api/uploads/not_a_table/records")

    assert empty_or_populated.status_code == 200
    assert isinstance(empty_or_populated.json()["items"], list)
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "table_not_found"


def test_csv_upload_inserts_then_updates_natural_key(client: TestClient) -> None:
    signup(client)
    company = f"Example Test Company {uuid.uuid4().hex}"
    headers = "company,city,state,industry,functions,headcount,country,source,source_url,confidence,last_verified_at"
    first_row = f"{company},Pune,Maharashtra,Technology,Engineering,30,India,User upload,,High,"
    first = client.post(
        "/api/uploads/gccs",
        files={"file": ("gcc.csv", f"{headers}\n{first_row}\n".encode(), "text/csv")},
    )
    updated_row = f"{company},Pune,Maharashtra,Technology,Engineering,45,India,Refreshed upload,,High,"
    updated = client.post(
        "/api/uploads/gccs",
        files={"file": ("gcc.csv", f"{headers}\n{updated_row}\n".encode(), "text/csv")},
    )

    assert first.status_code == 200
    assert first.json()["inserted"] == 1
    assert first.json()["updated"] == 0
    assert updated.status_code == 200
    assert updated.json()["inserted"] == 0
    assert updated.json()["updated"] == 1
    with SessionLocal() as database:
        rows = list(database.scalars(select(Gcc).where(Gcc.company == company, Gcc.city == "Pune")))
    assert len(rows) == 1
    assert rows[0].headcount == 45
    assert rows[0].source == "Refreshed upload"


def test_upload_rejects_bad_headers_and_values_without_partial_writes(client: TestClient) -> None:
    signup(client)
    invalid_company = f"Invalid Upload {uuid.uuid4().hex}"
    wrong_headers = client.post(
        "/api/uploads/gccs",
        files={"file": ("wrong.csv", f"company,city,headcount,unexpected\n{invalid_company},Pune,12,extra\n".encode(), "text/csv")},
    )
    bad_value = client.post(
        "/api/uploads/gccs",
        files={"file": ("bad.csv", f"company,city,headcount\n{invalid_company},Pune,not-a-number\n".encode(), "text/csv")},
    )

    assert wrong_headers.status_code == 422
    assert "unexpected" in wrong_headers.json()["detail"]
    assert bad_value.status_code == 422
    assert "headcount" in bad_value.json()["detail"]
    with SessionLocal() as database:
        assert database.scalar(select(func.count()).select_from(Gcc).where(Gcc.company == invalid_company)) == 0


def test_real_estate_alias_uploads_to_canonical_table(client: TestClient) -> None:
    signup(client)
    cluster = f"HITEC City {uuid.uuid4().hex}"
    response = client.post(
        "/api/uploads/rea_estate_cluster",
        files={
            "file": (
                "rent.csv",
                f"city,cluster,rent_min_inr_sqft,rent_max_inr_sqft\nHyderabad,{cluster},55,90\n".encode(),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["table"] == "real_estate_clusters"
    assert response.json()["inserted"] == 1


def test_chat_reads_uploaded_gcc_records_and_persists_messages(client: TestClient) -> None:
    signup(client)
    company = f"Chat Test Company {uuid.uuid4().hex}"
    upload = client.post(
        "/api/uploads/gccs",
        files={
            "file": (
                "gcc.csv",
                f"company,city,state,industry,headcount,source,confidence\n{company},Chennai,Tamil Nadu,Fintech,70,Manual research,High\n".encode(),
                "text/csv",
            )
        },
    )
    response = client.post("/api/chat", json={"message": f"Find {company} in the GCC records"})

    assert upload.status_code == 200
    assert response.status_code == 200
    assert company in response.json()["reply"]
    assert "Manual research" in response.json()["reply"]
    with SessionLocal() as database:
        messages = list(database.scalars(select(ChatMessage).order_by(ChatMessage.id.desc()).limit(2)))
    assert {message.role for message in messages} == {"user", "assistant"}


def test_database_only_chat_reads_cost_rent_provider_and_salary_tables() -> None:
    from app.ai import _dispatch_tool

    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(test_engine)
    try:
        with Session(test_engine) as database:
            from app.models import CostAssumption, Provider, RealEstateCluster, SalaryBenchmark

            database.add_all([
                CostAssumption(key="overhead", value=0.2, unit="fraction", source="uploaded"),
                Provider(name="Sample Talent Co", category="Recruiting", city="Pune", source="uploaded"),
                RealEstateCluster(city="Pune", cluster="Hinjawadi", rent_min_inr_sqft=40, rent_max_inr_sqft=70, source="uploaded"),
                SalaryBenchmark(city="Pune", role="Analyst", annual_salary_inr=900000, source="uploaded"),
            ])
            database.commit()
            outputs = {
                name: _dispatch_tool(database, name, arguments)
                for name, arguments in (
                    ("get_cost_assumptions", '{"query":"overhead"}'),
                    ("find_providers", '{"query":"Sample Talent Co"}'),
                    ("get_rent_clusters", '{"city":"Pune"}'),
                    ("get_salary_benchmarks", '{"city":"Pune","role":"Analyst"}'),
                )
            }
        assert outputs["get_cost_assumptions"][0]["value"] == 0.2
        assert outputs["find_providers"][0]["name"] == "Sample Talent Co"
        assert outputs["get_rent_clusters"][0]["cluster"] == "Hinjawadi"
        assert outputs["get_salary_benchmarks"][0]["annual_salary_inr"] == 900000
    finally:
        test_engine.dispose()


def test_legacy_migration_preserves_raw_items_and_drops_fetch_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import migrations

    legacy_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE data_sources (id INTEGER PRIMARY KEY, name TEXT)")
        connection.exec_driver_sql("INSERT INTO data_sources (id, name) VALUES (1, 'GDELT News')")
        connection.exec_driver_sql("CREATE TABLE raw_items (id INTEGER PRIMARY KEY, source_id INTEGER, external_id TEXT, payload_json TEXT, fetched_at DATETIME, source TEXT, source_url TEXT, confidence TEXT, last_verified_at DATETIME)")
        connection.exec_driver_sql("INSERT INTO raw_items VALUES (1, 1, 'legacy-item', '{\"title\":\"Kept\"}', '2026-10-14 00:00:00', 'unknown', 'https://example.test', 'Medium', NULL)")
        connection.exec_driver_sql("CREATE TABLE api_fetch_logs (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE gcc_signals (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE macro_indicators (id INTEGER PRIMARY KEY)")
    monkeypatch.setattr(migrations, "engine", legacy_engine)

    try:
        migrations.migrate_legacy_tables()
        with legacy_engine.connect() as connection:
            row = connection.exec_driver_sql("SELECT external_id, payload_json, source FROM raw_items").one()
            tables = set(connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars())
        assert row == ("legacy-item", '{"title":"Kept"}', "GDELT News")
        assert {"api_fetch_logs", "gcc_signals", "macro_indicators", "data_sources"}.isdisjoint(tables)
        assert "raw_items" in tables
    finally:
        legacy_engine.dispose()
