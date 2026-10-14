from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


database_url = settings.effective_database_url
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
if database_url.startswith("sqlite:") and database_url not in {"sqlite://", "sqlite:///:memory:"}:
    database_path = database_url.removeprefix("sqlite:///")
    if database_path and not database_path.startswith(":memory:"):
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
