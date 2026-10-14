from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai import database_answer
from app.database import Base
from app.models import City, RawItem


def make_database() -> tuple[object, Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_greeting_is_friendly_and_does_not_dump_city_rows() -> None:
    engine, database = make_database()
    try:
        database.add(City(name="Bengaluru", state="Karnataka"))
        database.commit()
        reply, sources = database_answer(database, "Hi")
        assert reply.startswith("Hi!")
        assert "Bengaluru" not in reply
        assert sources == []
    finally:
        database.close()
        engine.dispose()


def test_city_ranking_returns_only_the_requested_top_rows() -> None:
    engine, database = make_database()
    cities = [
        City(name="Bengaluru", talent_index=95, source="city upload", source_url="https://data.example/cities", confidence="High"),
        City(name="Hyderabad", talent_index=89, source="city upload", source_url="https://data.example/cities", confidence="High"),
        City(name="Delhi NCR", talent_index=88, source="city upload", source_url="https://data.example/cities", confidence="High"),
        City(name="Pune", talent_index=86, source="city upload", source_url="https://data.example/cities", confidence="High"),
    ]
    try:
        database.add_all(cities)
        database.commit()
        reply, sources = database_answer(database, "Rank the top 3 cities by talent index")
        assert reply.index("Bengaluru") < reply.index("Hyderabad") < reply.index("Delhi NCR")
        assert "Pune" not in reply
        assert "Confidence: High" in reply
        assert sources[0]["source"] == "data.example"
    finally:
        database.close()
        engine.dispose()


def test_city_comparison_does_not_attach_unrelated_raw_item_summary() -> None:
    engine, database = make_database()
    try:
        database.add_all([
            City(name="Bengaluru", state="Karnataka", population=13_187_098, source="city upload", confidence="High"),
            City(name="Pune", state="Maharashtra", population=6_817_951, source="city upload", confidence="High"),
            RawItem(
                external_id="survey-1",
                payload_json='{"extract":"Survey of GCC leaders covering AI, talent, cybersecurity, and operating-model trends.","city":"Other city"}',
                source="survey upload",
            ),
        ])
        database.commit()
        reply, _ = database_answer(database, "Compare Bengaluru and Pune")
        assert "13,187,098" in reply
        assert "6,817,951" in reply
        assert "Survey of GCC leaders" not in reply
    finally:
        database.close()
        engine.dispose()


def test_missing_city_population_is_explained_not_omitted() -> None:
    engine, database = make_database()
    try:
        database.add(City(name="Coimbatore", state="Tamil Nadu", population=None, confidence="Medium"))
        database.commit()
        reply, _ = database_answer(database, "What is the population of Coimbatore?")
        assert "don't have a population" in reply
        assert "Coimbatore" in reply
    finally:
        database.close()
        engine.dispose()