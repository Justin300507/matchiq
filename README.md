# MatchIQ

An AI sports analytics platform that predicts NBA and top-5 European soccer league
outcomes (win probabilities and score predictions) from historical results. It is
an analytics tool, not a betting product.

## Prerequisites

- Python 3.11+
- Node 18+
- Postgres (production) or SQLite (default for local dev/tests, no setup needed)

## Backend setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and fill in:

- `NBA_API_KEY` — free key from [balldontlie.io](https://www.balldontlie.io/)
- `FOOTBALL_DATA_API_KEY` — free key from [football-data.org](https://www.football-data.org/)

`DATABASE_URL` defaults to a local SQLite file if left as-is; point it at a
Postgres instance for anything beyond quick local testing.

`ALLOWED_ORIGINS` (comma-separated) controls which frontend origins the API's
CORS policy accepts; it defaults to the local Vite dev ports
(`http://localhost:5173,http://localhost:4173`), so when deploying, set it to
include your deployed frontend's actual URL (e.g. `https://your-app.vercel.app`)
in addition to (or instead of) the localhost defaults.

## Getting real predictions (first-run data + training)

The API only serves predictions once a trained model artifact exists for a
sport. Run these once (and again periodically to refresh):

1. **Backfill historical data** for NBA and the top-5 soccer leagues:

   ```bash
   cd backend
   python -m app.ingestion.backfill
   ```

2. **Train both sports' models**, which also evaluates each model against a
   naive home-favorite baseline and only saves an artifact if it beats it:

   ```bash
   python -c "from app.config import get_settings; from app.db import get_engine, get_session_factory; from app.ml.train import train_sport_models; s = get_settings(); db = get_session_factory(get_engine(s.database_url))(); print(train_sport_models(db, 'nba', s.artifact_dir)); print(train_sport_models(db, 'soccer', s.artifact_dir))"
   ```

   Confirm both calls print `beat_baseline: True` with an `artifact_path`. If a
   sport prints `False`, that sport has no usable model yet (see note below) —
   the other sport is unaffected.

## Running the API

```bash
cd backend
uvicorn app.main:app --reload
```

The API listens on `http://localhost:8000` by default. `/health` returns
`{"status": "ok"}` once it's up.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

`VITE_API_BASE_URL` in `.env` should point at the backend (defaults to
`http://localhost:8000`).

## Keeping data fresh

`backend/app/ingestion/daily_sync.py` pulls recent/upcoming games (run it on a
schedule, e.g. a daily cron/Railway job) to keep `/predictions/upcoming`
current without re-running the full backfill.

## Expected first-run behavior: 503 on `/predictions/*`

If you hit `/predictions/upcoming` or `/predictions/{game_id}` before running
backfill + train for a given sport, you'll get **HTTP 503** ("No trained
model available for sport=..."). This is by design — there is no fallback or
stub model — not a bug. Run the backfill and training steps above to resolve
it.

## Tests

```bash
cd backend && pytest tests/ -v
cd frontend && npx vitest run
```
