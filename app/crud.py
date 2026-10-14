from __future__ import annotations

import json
from typing import Any

from sqlalchemy import or_, select
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


def search_gccs(database: Session, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    statement = select(Gcc).order_by(Gcc.company).limit(min(max(limit, 1), 20))
    if query.strip():
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(Gcc.company.ilike(pattern), Gcc.city.ilike(pattern), Gcc.industry.ilike(pattern), Gcc.functions.ilike(pattern))
        )
    return [
        {"company": row.company, "city": row.city, "industry": row.industry, "headcount": row.headcount,
         "source": row.source, "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(statement)
    ]


def get_city_details(database: Session, name: str) -> dict[str, Any] | None:
    city = database.scalar(select(City).where(City.name.ilike(name.strip())))
    if city is None:
        return None
    return {
        "name": city.name, "state": city.state, "region": city.region,
        "population": city.population, "universities_mapped": city.university_count,
        "coworking_spaces_mapped": city.coworking_count,
        "talent_index": city.talent_index, "cost_index": city.cost_index,
        "source": city.source, "source_url": city.source_url,
        "confidence": city.confidence,
        "last_verified_at": city.last_verified_at.isoformat() if city.last_verified_at else None,
    }


def list_cities(database: Session, limit: int = 20) -> list[dict[str, Any]]:
    return [
        {"name": city.name, "state": city.state, "region": city.region,
         "population": city.population, "university_count": city.university_count,
         "coworking_count": city.coworking_count, "talent_index": city.talent_index,
         "cost_index": city.cost_index, "source": city.source,
         "source_url": city.source_url, "confidence": city.confidence,
         "last_verified_at": city.last_verified_at.isoformat() if city.last_verified_at else None}
        for city in database.scalars(select(City).order_by(City.name).limit(min(max(limit, 1), 20)))
    ]


def get_incentives(database: Session, state: str, limit: int = 20) -> list[dict[str, Any]]:
    statement = select(StateIncentive).where(StateIncentive.state.ilike(f"%{state.strip()}%")).limit(min(max(limit, 1), 20))
    return [
        {"state": item.state, "title": item.title, "description": item.description,
         "benefit": item.benefit, "source": item.source, "source_url": item.source_url,
         "confidence": item.confidence}
        for item in database.scalars(statement)
    ]


def find_providers(database: Session, query: str = "", category: str = "", city: str = "", limit: int = 10) -> list[dict[str, Any]]:
    statement = select(Provider).order_by(Provider.name).limit(min(max(limit, 1), 20))
    if category:
        statement = statement.where(Provider.category.ilike(f"%{category.strip()}%"))
    if city:
        statement = statement.where(Provider.city.ilike(f"%{city.strip()}%"))
    if query.strip():
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(Provider.name.ilike(pattern), Provider.category.ilike(pattern), Provider.description.ilike(pattern), Provider.city.ilike(pattern)))
    return [
        {"name": row.name, "category": row.category, "city": row.city, "description": row.description,
         "website": row.website, "source": row.source, "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(statement)
    ]


def get_salary_benchmark(database: Session, role: str = "", city: str = "", limit: int = 10) -> list[dict[str, Any]]:
    statement = select(SalaryBenchmark).order_by(SalaryBenchmark.city, SalaryBenchmark.role).limit(min(max(limit, 1), 20))
    if role:
        statement = statement.where(SalaryBenchmark.role.ilike(f"%{role.strip()}%"))
    if city:
        statement = statement.where(SalaryBenchmark.city.ilike(f"%{city.strip()}%"))
    return [
        {"city": row.city, "role": row.role, "annual_salary_inr": row.annual_salary_inr,
         "currency": row.currency, "source": row.source, "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(statement)
    ]


def get_rent_clusters(database: Session, city: str = "", limit: int = 10) -> list[dict[str, Any]]:
    statement = select(RealEstateCluster).order_by(RealEstateCluster.city, RealEstateCluster.cluster).limit(min(max(limit, 1), 20))
    if city:
        statement = statement.where(RealEstateCluster.city.ilike(f"%{city.strip()}%"))
    return [
        {"city": row.city, "cluster": row.cluster, "rent_min_inr_sqft": row.rent_min_inr_sqft,
         "rent_max_inr_sqft": row.rent_max_inr_sqft, "area_per_seat_sqft": row.area_per_seat_sqft,
         "source": row.source, "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(statement)
    ]


def get_cost_assumptions(database: Session, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    statement = select(CostAssumption).order_by(CostAssumption.key).limit(min(max(limit, 1), 20))
    if query.strip():
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(CostAssumption.key.ilike(pattern), CostAssumption.description.ilike(pattern)))
    return [
        {"key": row.key, "value": row.value, "unit": row.unit, "description": row.description,
         "source": row.source, "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(statement)
    ]


def get_scoring_weights(database: Session, limit: int = 20) -> list[dict[str, Any]]:
    return [
        {"criterion": row.criterion, "weight": row.weight, "source": row.source,
         "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(select(ScoringWeight).order_by(ScoringWeight.criterion).limit(min(max(limit, 1), 20)))
    ]


def search_raw_items(database: Session, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    statement = select(RawItem).order_by(RawItem.fetched_at.desc()).limit(min(max(limit, 1), 20))
    if query.strip():
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(RawItem.external_id.ilike(pattern), RawItem.payload_json.ilike(pattern)))
    return [
        {"external_id": row.external_id, "payload": json.loads(row.payload_json),
         "source": row.source, "source_url": row.source_url, "confidence": row.confidence}
        for row in database.scalars(statement)
    ]
