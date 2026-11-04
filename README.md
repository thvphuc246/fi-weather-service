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

`master` is the source of truth and never deploys. `prod` is what's live.

### Deploying

Actions → **Promote** → Run workflow on `master`. It runs the checks, fast-forwards `prod` to that commit, then runs `vercel deploy --prod`. Nothing else deploys: Git deploys are off in `vercel.json`.

### Rollback

Vercel dashboard → Deployments → Instant Rollback, then revert on `master` and Promote again.

### Scheduled fetch

cron-job.org calls `GET /api/fetch` every 30 minutes with `Authorization: Bearer $CRON_SECRET`. A 502 means at least one place failed, and the body says which.

### One-time setup

1. `vercel link`. Don't connect the Git repo.
2. `vercel integration add neon`, choosing region `aws-eu-central-1`. It sets `DATABASE_URL`.
3. `vercel env add CRON_SECRET production`.
4. GitHub secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID`. The two IDs are in `.vercel/project.json`.
5. Branch protection on `master` and `prod`: required check `check`, no deletion, no force pushes.
6. A cron-job.org job: every 30 min, with the Bearer header, and an email after 3 failures in a row.
