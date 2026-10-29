import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Literal

import psycopg
from psycopg import sql

from weather.fmi import Reading

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()

Table = Literal["observation", "forecast"]
Series = dict[str, list[tuple[int, float]]]


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"])


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)


def last_observation(conn: psycopg.Connection, place: str) -> datetime | None:
    row = conn.execute("SELECT max(ts) FROM observation WHERE place = %s", (place,)).fetchone()
    return row[0] if row else None


def upsert(conn: psycopg.Connection, table: Table, place: str, readings: list[Reading]) -> None:
    query = sql.SQL(
        "INSERT INTO {} (place, ts, param, value) VALUES (%s, %s, %s, %s)"
        " ON CONFLICT (place, ts, param) DO UPDATE SET value = EXCLUDED.value"
    ).format(sql.Identifier(table))
    with conn.cursor() as cur:
        cur.executemany(query, [(place, r.ts, r.param, r.value) for r in readings])


def delete_old_forecasts(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM forecast WHERE ts < now() - interval '1 day'")


def series(conn: psycopg.Connection, place: str, hours: int) -> dict[str, Series]:
    out: dict[str, Series] = {}
    for table, where in (
        ("observation", "ts >= now() - make_interval(hours => %s)"),
        ("forecast", "ts >= now() AND ts <= now() + make_interval(hours => %s)"),
    ):
        query = sql.SQL(
            "SELECT param, ts, value FROM {} WHERE place = %s AND " + where + " ORDER BY ts"
        ).format(sql.Identifier(table))
        points: defaultdict[str, list[tuple[int, float]]] = defaultdict(list)
        for param, ts, value in conn.execute(query, (place, hours)):
            points[param].append((int(ts.timestamp() * 1000), value))
        out[table] = dict(points)
    return out
