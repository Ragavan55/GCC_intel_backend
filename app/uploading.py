from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    City,
    CostAssumption,
    Gcc,
    Provider,
    RawItem,
    RealEstateCluster,
    SalaryBenchmark,
    ScoringWeight,
    StateIncentive,
)


@dataclass(frozen=True)
class ColumnSpec:
    kind: str
    required: bool = False
    example: str = ""


@dataclass(frozen=True)
class TableSpec:
    model: type[Any]
    columns: dict[str, ColumnSpec]
    natural_key: tuple[str, ...]
    aliases: tuple[str, ...] = ()


PROVENANCE = {
    "source": ColumnSpec("string", example="manual_upload"),
    "source_url": ColumnSpec("string | null", example="https://example.com/source"),
    "confidence": ColumnSpec("string", example="Medium"),
    "last_verified_at": ColumnSpec("datetime | null", example="2026-10-14T12:00:00Z"),
}

TABLE_SPECS: dict[str, TableSpec] = {
    "cost_assumptions": TableSpec(
        CostAssumption,
        {"key": ColumnSpec("string", True, "annual_overhead_rate"), "value": ColumnSpec("number", True, "0.25"), "unit": ColumnSpec("string", example="fraction"), "description": ColumnSpec("string", example="Annual non-salary overhead rate"), **PROVENANCE},
        ("key",),
    ),
    "gccs": TableSpec(
        Gcc,
        {"company": ColumnSpec("string", True, "Example Financial Services"), "city": ColumnSpec("string", True, "Bengaluru"), "state": ColumnSpec("string", example="Karnataka"), "industry": ColumnSpec("string", example="Financial services"), "functions": ColumnSpec("string", example="Engineering; analytics"), "headcount": ColumnSpec("integer | null", example="1200"), "country": ColumnSpec("string", example="India"), **PROVENANCE},
        ("company", "city"),
    ),
    "providers": TableSpec(
        Provider,
        {"name": ColumnSpec("string", True, "Example Consulting"), "category": ColumnSpec("string", True, "Talent acquisition"), "city": ColumnSpec("string", example="Pune"), "description": ColumnSpec("string", example="Recruiting and workforce planning"), "website": ColumnSpec("string | null", example="https://example.com"), **PROVENANCE},
        ("name", "category", "city"),
    ),
    "real_estate_clusters": TableSpec(
        RealEstateCluster,
        {"city": ColumnSpec("string", True, "Hyderabad"), "cluster": ColumnSpec("string", True, "HITEC City"), "rent_min_inr_sqft": ColumnSpec("number | null", example="55"), "rent_max_inr_sqft": ColumnSpec("number | null", example="90"), "area_per_seat_sqft": ColumnSpec("number | null", example="100"), **PROVENANCE},
        ("city", "cluster"),
        aliases=("rea_estate_cluster",),
    ),
    "salary_benchmarks": TableSpec(
        SalaryBenchmark,
        {"city": ColumnSpec("string", True, "Chennai"), "role": ColumnSpec("string", True, "Data Engineer"), "annual_salary_inr": ColumnSpec("number", True, "1800000"), "currency": ColumnSpec("string", example="INR"), **PROVENANCE},
        ("city", "role"),
    ),
    "scoring_weights": TableSpec(
        ScoringWeight,
        {"criterion": ColumnSpec("string", True, "talent"), "weight": ColumnSpec("number", True, "0.35"), **PROVENANCE},
        ("criterion",),
    ),
    "state_incentives": TableSpec(
        StateIncentive,
        {"state": ColumnSpec("string", True, "Karnataka"), "title": ColumnSpec("string", True, "Employment generation incentive"), "description": ColumnSpec("string", example="Eligibility details"), "industry": ColumnSpec("string", example="IT and ITES"), "benefit": ColumnSpec("string", example="Reimbursement subject to scheme conditions"), **PROVENANCE},
        ("state", "title"),
    ),
    "cities": TableSpec(
        City,
        {"name": ColumnSpec("string", True, "Bengaluru"), "state": ColumnSpec("string", example="Karnataka"), "region": ColumnSpec("string", example="South India"), "country": ColumnSpec("string", example="India"), "population": ColumnSpec("integer | null", example="8400000"), "university_count": ColumnSpec("integer | null", example="35"), "coworking_count": ColumnSpec("integer | null", example="120"), "talent_index": ColumnSpec("number | null", example="82.5"), "cost_index": ColumnSpec("number | null", example="71.0"), **PROVENANCE},
        ("name",),
    ),
    "raw_items": TableSpec(
        RawItem,
        {"external_id": ColumnSpec("string", True, "source-record-001"), "payload_json": ColumnSpec("JSON object or array", True, "{\"title\":\"Example record\"}"), "fetched_at": ColumnSpec("datetime | null", example="2026-10-14T12:00:00Z"), **PROVENANCE},
        ("source", "external_id"),
    ),
}

TABLE_ALIASES = {alias: canonical for canonical, spec in TABLE_SPECS.items() for alias in spec.aliases}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_ROWS = 10_000


def _parse_value(value: str, column: ColumnSpec, field: str, row_number: int) -> Any:
    cleaned = value.strip()
    if not cleaned:
        if column.required:
            raise ValueError(f"Row {row_number}: '{field}' is required")
        return None
    kind = column.kind
    try:
        if kind.startswith("integer"):
            return int(cleaned)
        if kind.startswith("number"):
            parsed = float(cleaned.replace(",", ""))
            if parsed != parsed or parsed in (float("inf"), float("-inf")):
                raise ValueError("must be a finite number")
            return parsed
        if kind == "datetime | null":
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if kind == "JSON object or array":
            parsed_json = json.loads(cleaned)
            if not isinstance(parsed_json, (dict, list)):
                raise ValueError("must be a JSON object or array")
            return json.dumps(parsed_json, ensure_ascii=True, sort_keys=True)
        return cleaned
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Row {row_number}: '{field}' expected {kind}; got {cleaned!r}") from error


def upload_csv(database: Session, requested_table: str, content: bytes) -> dict[str, Any]:
    canonical = TABLE_ALIASES.get(requested_table, requested_table)
    spec = TABLE_SPECS.get(canonical)
    if spec is None:
        raise ValueError("Unknown upload table")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds the 10 MB upload limit")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must use UTF-8 encoding") from error
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row")
    headers = [header.strip() for header in reader.fieldnames]
    if len(headers) != len(set(headers)):
        raise ValueError("CSV contains duplicate column names")
    unknown = sorted(set(headers) - set(spec.columns))
    missing = sorted(name for name, column in spec.columns.items() if column.required and name not in headers)
    if unknown or missing:
        pieces = []
        if missing:
            pieces.append("Missing required headers: " + ", ".join(missing))
        if unknown:
            pieces.append("Unknown headers: " + ", ".join(unknown))
        raise ValueError(". ".join(pieces))

    prepared: list[dict[str, Any]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        if row_number > MAX_UPLOAD_ROWS + 1:
            raise ValueError(f"CSV exceeds the {MAX_UPLOAD_ROWS:,} row limit")
        raw_values = {str(key).strip(): value or "" for key, value in raw_row.items() if key is not None}
        if not any(value.strip() for value in raw_values.values()):
            continue
        values = {
            name: _parse_value(raw_values.get(name, ""), column, name, row_number)
            for name, column in spec.columns.items()
            if name in raw_values
            and not (column.kind == "string" and not column.required and not raw_values.get(name, "").strip())
        }
        for name in spec.natural_key:
            if values.get(name) is None:
                raise ValueError(f"Row {row_number}: natural key '{name}' is required")
        if not values.get("source"):
            values["source"] = "manual_upload"
        if not values.get("confidence"):
            values["confidence"] = "Low"
        if "fetched_at" in spec.columns and values.get("fetched_at") is None:
            values["fetched_at"] = datetime.now(timezone.utc)
        prepared.append(values)
    if not prepared:
        raise ValueError("CSV contains no data rows")

    inserted = updated = 0
    try:
        for values in prepared:
            keys = {name: values[name] for name in spec.natural_key}
            existing = database.scalar(select(spec.model).filter_by(**keys))
            if existing is None:
                database.add(spec.model(**values))
                database.flush()
                inserted += 1
            else:
                for name, value in values.items():
                    setattr(existing, name, value)
                updated += 1
        database.commit()
    except Exception:
        database.rollback()
        raise
    return {"table": canonical, "rows_received": len(prepared), "inserted": inserted, "updated": updated}
