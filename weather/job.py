"""The scheduled fetch: shared by the local thread, /api/fetch and the CLI."""

import logging
from datetime import UTC, datetime, timedelta

from weather import db, fmi

PLACES = ("Helsinki", "Espoo", "Vantaa", "Turku", "Tampere", "Oulu")
BACKFILL = timedelta(days=7)  # also FMI's 168 h per-request limit

log = logging.getLogger(__name__)


def run_fetch() -> dict[str, str]:
    """Fetch every place; one failing place is logged and skipped, the next run fills the gap."""
    results = {}
    with db.connect() as conn:
        db.init_schema(conn)
        conn.commit()
        for place in PLACES:
            try:
                floor = datetime.now(UTC) - BACKFILL
                last = db.last_observation(conn, place)
                obs = fmi.fetch_observations(place, max(last, floor) if last else floor)
                forecast = fmi.fetch_forecast(place)
                db.upsert(conn, "observation", place, obs)
                db.upsert(conn, "forecast", place, forecast)
                conn.commit()
                results[place] = f"ok: {len(obs)} observations, {len(forecast)} forecast"
            except Exception as e:
                conn.rollback()
                log.exception("fetch failed for %s", place)
                results[place] = f"error: {e}"
        db.delete_old_forecasts(conn)
        conn.commit()
    log.info("fetch done: %s", results)
    return results
