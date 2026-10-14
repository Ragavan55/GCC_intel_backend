from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProvenanceMixin:
    source: Mapped[str] = mapped_column(String(255), default="unknown")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(32), default="Low")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(ProvenanceMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="other")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class City(ProvenanceMixin, Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(120), default="")
    region: Mapped[str] = mapped_column(String(80), default="")
    country: Mapped[str] = mapped_column(String(80), default="India")
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    university_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coworking_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    talent_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_index: Mapped[float | None] = mapped_column(Float, nullable=True)


class StateIncentive(ProvenanceMixin, Base):
    __tablename__ = "state_incentives"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(160), default="")
    benefit: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(255), default="unknown")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(32), default="Low")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Gcc(ProvenanceMixin, Base):
    __tablename__ = "gccs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    city: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(120), default="")
    industry: Mapped[str] = mapped_column(String(160), default="")
    functions: Mapped[str] = mapped_column(Text, default="")
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="India")


class Provider(ProvenanceMixin, Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalaryBenchmark(ProvenanceMixin, Base):
    __tablename__ = "salary_benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(120), index=True)
    role: Mapped[str] = mapped_column(String(160), index=True)
    annual_salary_inr: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")


class RealEstateCluster(ProvenanceMixin, Base):
    __tablename__ = "real_estate_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(120), index=True)
    cluster: Mapped[str] = mapped_column(String(160))
    rent_min_inr_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    rent_max_inr_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_per_seat_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)


class CostAssumption(ProvenanceMixin, Base):
    __tablename__ = "cost_assumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class ScoringWeight(ProvenanceMixin, Base):
    __tablename__ = "scoring_weights"

    id: Mapped[int] = mapped_column(primary_key=True)
    criterion: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    weight: Mapped[float] = mapped_column(Float)


class RawItem(ProvenanceMixin, Base):
    __tablename__ = "raw_items"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_raw_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(500))
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SavedBrief(ProvenanceMixin, Base):
    __tablename__ = "saved_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    inputs_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChatSession(ProvenanceMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChatMessage(ProvenanceMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
    tool_calls_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)



