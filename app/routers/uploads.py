from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.uploading import MAX_UPLOAD_BYTES, TABLE_ALIASES, TABLE_SPECS, upload_csv


router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/tables")
def list_upload_tables(
    database: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    for key, spec in TABLE_SPECS.items():
        tables.append({
            "key": key,
            "label": key,
            "aliases": list(spec.aliases),
            "headers": list(spec.columns),
            "natural_key": list(spec.natural_key),
            "columns": [
                {"name": name, "type": column.kind, "required": column.required, "example": column.example}
                for name, column in spec.columns.items()
            ],
            "row_count": database.scalar(select(func.count()).select_from(spec.model)) or 0,
        })
    return {"tables": tables, "aliases": TABLE_ALIASES}


@router.get("/{table_key}/records")
def list_table_records(
    table_key: str,
    database: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    canonical = TABLE_ALIASES.get(table_key, table_key)
    spec = TABLE_SPECS.get(canonical)
    if spec is None:
        raise HTTPException(status_code=404, detail={"detail": "Upload table not found", "code": "table_not_found"})
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(status_code=422, detail={"detail": "Page must be positive and page_size must be between 1 and 200", "code": "invalid_pagination"})
    total = database.scalar(select(func.count()).select_from(spec.model)) or 0
    order_columns = [getattr(spec.model, key) for key in spec.natural_key]
    rows = database.scalars(
        select(spec.model).order_by(*order_columns).offset((page - 1) * page_size).limit(page_size)
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        item = {"id": getattr(row, "id")}
        for column in spec.columns:
            value = getattr(row, column, None)
            item[column] = value.isoformat() if isinstance(value, datetime) else value
        items.append(item)
    return {"table": canonical, "items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{table_key}")
async def upload_table_csv(
    table_key: str,
    database: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
) -> dict[str, Any]:
    if file.filename is None or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail={"detail": "Upload a UTF-8 CSV file", "code": "unsupported_file"})
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"detail": "File exceeds the 10 MB upload limit", "code": "file_too_large"})
    try:
        return upload_csv(database, table_key, content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"detail": str(error), "code": "invalid_upload"}) from error
