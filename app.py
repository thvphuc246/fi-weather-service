import hmac
import logging
import os
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse

from weather import db
from weather.job import PLACES, run_fetch

FETCH_INTERVAL = 30 * 60
INDEX = Path(__file__).parent / "static" / "index.html"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _scheduler() -> None:
    while True:
        try:
            run_fetch()
        except Exception:
            log.exception("scheduled fetch failed")
        time.sleep(FETCH_INTERVAL)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if os.environ.get("RUN_SCHEDULER") == "1":
        threading.Thread(target=_scheduler, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(INDEX)


@app.get("/api/places")
def places() -> tuple[str, ...]:
    return PLACES


@app.get("/api/series")
def series(place: str, hours: Annotated[int, Query(ge=1, le=720)] = 24) -> dict[str, db.Series]:
    if place not in PLACES:
        raise HTTPException(404, f"unknown place {place!r}")
    with db.connect() as conn:
        return db.series(conn, place, hours)


@app.get("/api/fetch")
def fetch(authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
    secret = os.environ.get("CRON_SECRET")
    given = (authorization or "").encode()
    if not secret or not hmac.compare_digest(given, f"Bearer {secret}".encode()):
        raise HTTPException(401)
    return run_fetch()
