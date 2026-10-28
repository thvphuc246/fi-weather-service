"""Runs against a real Postgres. Uses TEST_DATABASE_URL (never DATABASE_URL) because it wipes tables."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app
from weather import db, fmi, job

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")
FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer test-secret"}


@pytest.fixture
def starts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[datetime]]:
    """Fresh DB, FMI replaced by fixtures; yields the obs start times requested."""
    monkeypatch.setenv("DATABASE_URL", TEST_DB or "")
    monkeypatch.setenv("CRON_SECRET", "test-secret")
    with db.connect() as conn:
        db.init_schema(conn)
        conn.execute("TRUNCATE observation, forecast")
    requested: list[datetime] = []

    def fake_obs(place: str, start: datetime) -> list[fmi.Reading]:
        requested.append(start)
        return fmi.parse((FIXTURES / "observations.xml").read_bytes(), fmi.OBSERVATION_PARAMS)

    def fake_forecast(place: str) -> list[fmi.Reading]:
        return fmi.parse((FIXTURES / "forecast.xml").read_bytes(), fmi.FORECAST_PARAMS)

    monkeypatch.setattr(fmi, "fetch_observations", fake_obs)
    monkeypatch.setattr(fmi, "fetch_forecast", fake_forecast)
    yield requested


def count(table: str) -> int:
    with db.connect() as conn:
        row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
        assert row
        return int(row[0])


def test_fetch_requires_secret(starts: list[datetime]) -> None:
    client = TestClient(app)
    assert client.get("/api/fetch").status_code == 401
    assert client.get("/api/fetch", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_fetch_is_idempotent(starts: list[datetime]) -> None:
    client = TestClient(app)
    for _ in range(2):
        resp = client.get("/api/fetch", headers=AUTH)
        assert resp.status_code == 200
        assert all(v.startswith("ok") for v in resp.json().values())
    assert count("observation") == 25 * len(job.PLACES)
    assert count("forecast") == 15 * len(job.PLACES)


def test_fetch_backfills_then_resumes_from_last(starts: list[datetime]) -> None:
    job.run_fetch()
    assert abs(starts[0] - (datetime.now(UTC) - job.BACKFILL)) < timedelta(minutes=1)
    # newer than anything in the fixture, so it must become the resume point
    recent = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)
    with db.connect() as conn:
        db.upsert(conn, "observation", "Helsinki", [fmi.Reading(recent, "temperature", 1.0)])
    starts.clear()
    job.run_fetch()
    assert starts[0] == recent  # Helsinki comes first in PLACES


def test_one_failing_place_does_not_stop_others(starts: list[datetime], monkeypatch: pytest.MonkeyPatch) -> None:
    real = fmi.fetch_forecast

    def flaky(place: str) -> list[fmi.Reading]:
        if place == "Espoo":
            raise OSError("FMI down")
        return real(place)

    monkeypatch.setattr(fmi, "fetch_forecast", flaky)
    results = job.run_fetch()
    assert results["Espoo"].startswith("error")
    assert results["Oulu"].startswith("ok")


def test_series(starts: list[datetime]) -> None:
    now = datetime.now(UTC)
    with db.connect() as conn:
        db.upsert(conn, "observation", "Oulu", [fmi.Reading(now - timedelta(hours=2), "temperature", -3.5)])
        db.upsert(conn, "forecast", "Oulu", [fmi.Reading(now + timedelta(hours=2), "temperature", -4.0)])
    client = TestClient(app)
    data = client.get("/api/series", params={"place": "Oulu", "hours": 24}).json()
    assert [p[1] for p in data["observation"]["temperature"]] == [-3.5]
    assert [p[1] for p in data["forecast"]["temperature"]] == [-4.0]
    assert client.get("/api/series", params={"place": "Nowhere"}).status_code == 404
