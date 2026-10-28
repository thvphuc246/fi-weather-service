# Finnish weather data service

Pulls [FMI open data](https://en.ilmatieteenlaitos.fi/open-data) (observations + edited forecast) for Helsinki, Espoo, Vantaa, Turku, Tampere and Oulu every 30 minutes, stores it in Postgres and charts it.

- `weather/fmi.py` – WFS fetch + XML parse
- `weather/db.py`, `weather/schema.sql` – Postgres
- `weather/job.py` – `run_fetch()`, shared by every trigger
- `app.py` – FastAPI: `/` (charts), `/api/series`, `/api/places`, `/api/fetch` (needs `Authorization: Bearer $CRON_SECRET`)

## Local

```sh
docker compose up --build          # Postgres + app, fetches on start then every 30 min
open http://localhost:8000
curl -H "Authorization: Bearer dev-secret" localhost:8000/api/fetch   # fetch now
```

## Checks

```sh
uv sync
uv run mypy
docker compose up -d db
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/weather_test uv run pytest
```

DB tests are skipped without `TEST_DATABASE_URL`. They truncate tables, so never point it at real data.

## Production (Vercel + Neon)

1. `vercel link`, `vercel integration add neon` (sets `DATABASE_URL`), `vercel env add CRON_SECRET production`.
2. Deploy (Git push, or `vercel deploy --prod`).
3. GitHub repo settings: secrets `FETCH_URL` (`https://<app>.vercel.app/api/fetch`) and `CRON_SECRET`; variable `FETCH_ENABLED=true`.

`.github/workflows/fetch.yml` then calls `/api/fetch` every 30 minutes (Vercel Hobby cron only runs daily). GitHub pauses scheduled workflows after 60 days without commits – re-enable from the Actions tab.
