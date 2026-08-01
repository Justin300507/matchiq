# MatchIQ Phase 1: Core Prediction Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working, deployable core for MatchIQ: real NBA + top-5-soccer-league data flowing into Postgres, XGBoost models trained on it, a FastAPI backend serving predictions, and a minimal React dashboard displaying them.

**Architecture:** Ingestion clients pull raw data from `balldontlie.io` (NBA) and `football-data.org` (soccer) into sport-specific fetch functions, which get normalized into a shared `matches`/`teams` Postgres schema. A feature-engineering module computes rolling form / home-away splits / head-to-head / rest-days from that shared schema. Per-sport XGBoost classifier+regressor pairs train on those features and must beat a naive "home team always wins" baseline before their artifacts are considered usable. FastAPI loads the latest artifacts and serves predictions computed on-demand for upcoming fixtures. A single-page React dashboard fetches and renders them.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL (SQLite for tests), XGBoost, pandas, scikit-learn, pytest, React 18 + TypeScript + Tailwind (Vite), Vitest + React Testing Library.

## Global Constraints

- Time-based train/test split only — never a random split (spec: avoid future-data leakage).
- Every trained model must be evaluated against a naive home-favorite baseline (accuracy, log-loss, Brier score); an artifact that doesn't beat baseline is not saved as the "latest" artifact.
- No auth, no user accounts, no live/websocket updates, no Redis/Kafka/Kubernetes — all deferred to later phases per the spec.
- Shared `matches`/`teams` schema must not special-case sport in the API or feature layer — sport-specific logic lives only in the ingestion/normalize layer.
- All API responses use Pydantic schemas (no raw ORM objects returned from routes).

---

## File Structure

```
matchiq/
  backend/
    app/
      __init__.py
      config.py
      db.py
      models_db.py
      schemas.py
      routers/
        __init__.py
        predictions.py
        teams.py
      ingestion/
        __init__.py
        normalize.py
        nba_client.py
        soccer_client.py
        backfill.py
        daily_sync.py
      features/
        __init__.py
        build_features.py
      ml/
        __init__.py
        baseline.py
        train.py
        predict.py
      main.py
    tests/
      conftest.py
      test_normalize.py
      test_nba_client.py
      test_soccer_client.py
      test_build_features.py
      test_baseline.py
      test_predict.py
      test_api_predictions.py
      test_api_teams.py
    requirements.txt
    .env.example
  frontend/
    src/
      api.ts
      types.ts
      App.tsx
      main.tsx
      components/
        GameCard.tsx
        GameList.tsx
      __tests__/
        GameCard.test.tsx
        GameList.test.tsx
    package.json
    vite.config.ts
    tailwind.config.js
```

---

### Task 1: Backend scaffold, config, and health endpoint

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/.env.example`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_main.py`

**Interfaces:**
- Produces: `app.config.Settings` (fields: `database_url: str`, `nba_api_key: str`, `football_data_api_key: str`, `artifact_dir: Path`), `get_settings() -> Settings`.
- Produces: `app.main.app` (FastAPI instance), `GET /health` -> `{"status": "ok"}`.

- [ ] **Step 1: Write `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pydantic==2.9.2
pydantic-settings==2.5.2
requests==2.32.3
pandas==2.2.3
scikit-learn==1.5.2
xgboost==2.1.1
joblib==1.4.2
pytest==8.3.3
httpx==0.27.2
python-dotenv==1.0.1
```

- [ ] **Step 2: Write `backend/.env.example`**

```
DATABASE_URL=postgresql://matchiq:matchiq@localhost:5432/matchiq
NBA_API_KEY=
FOOTBALL_DATA_API_KEY=
ARTIFACT_DIR=./artifacts
```

- [ ] **Step 3: Write `backend/app/config.py`**

```python
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./matchiq.db"
    nba_api_key: str = ""
    football_data_api_key: str = ""
    artifact_dir: Path = Path("./artifacts")

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write `backend/app/__init__.py`** (empty file)

- [ ] **Step 5: Write `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="MatchIQ API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: Write `backend/tests/conftest.py`**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 7: Write the failing test `backend/tests/test_main.py`**

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 8: Install deps and run test**

Run: `cd backend && pip install -r requirements.txt && pytest tests/test_main.py -v`
Expected: PASS (test was written after implementation here since this is pure scaffolding — confirm it passes)

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/app/config.py backend/app/__init__.py backend/app/main.py backend/tests/conftest.py backend/tests/test_main.py
git commit -m "feat: backend scaffold with health endpoint"
```

---

### Task 2: Shared database schema (Team, Match)

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models_db.py`
- Test: `backend/tests/test_models_db.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` from Task 1.
- Produces: `app.db.Base`, `app.db.get_engine(database_url: str)`, `app.db.get_session_factory(engine)`.
- Produces: `app.models_db.Team(id, external_id, sport, league, name)`, `app.models_db.Match(id, external_id, sport, league, date, home_team_id, away_team_id, home_score, away_score, status)`.

- [ ] **Step 1: Write `backend/app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str):
    return create_engine(database_url)


def get_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

- [ ] **Step 2: Write `backend/app/models_db.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("sport", "external_id", name="uq_team_sport_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    league: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("sport", "external_id", name="uq_match_sport_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    league: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)

    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id])
```

- [ ] **Step 3: Write the failing test `backend/tests/test_models_db.py`**

```python
from datetime import datetime

from app.db import Base, get_engine, get_session_factory
from app.models_db import Match, Team


def test_can_insert_team_and_match():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = get_session_factory(engine)
    db = Session()

    home = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    away = Team(external_id="2", sport="nba", league="NBA", name="Celtics")
    db.add_all([home, away])
    db.commit()

    match = Match(
        external_id="100",
        sport="nba",
        league="NBA",
        date=datetime(2026, 1, 1),
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=None,
        away_score=None,
        status="scheduled",
    )
    db.add(match)
    db.commit()

    fetched = db.query(Match).one()
    assert fetched.home_team.name == "Lakers"
    assert fetched.away_team.name == "Celtics"
    assert fetched.status == "scheduled"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models_db'` (before Step 1/2) — since steps above are already written, instead run to confirm it now PASSES.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models_db.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db.py backend/app/models_db.py backend/tests/test_models_db.py
git commit -m "feat: shared Team/Match database schema"
```

---

### Task 3: Sport normalization layer

**Files:**
- Create: `backend/app/ingestion/__init__.py`
- Create: `backend/app/ingestion/normalize.py`
- Test: `backend/tests/test_normalize.py`

**Interfaces:**
- Consumes: `app.models_db.Team`, `app.models_db.Match` from Task 2.
- Produces: `app.ingestion.normalize.RawGame` dataclass (fields: `external_id: str, sport: str, league: str, date: datetime, home_team_external_id: str, home_team_name: str, away_team_external_id: str, away_team_name: str, home_score: int | None, away_score: int | None, status: str`).
- Produces: `normalize_nba_game(raw: dict) -> RawGame`, `normalize_soccer_game(raw: dict, league: str) -> RawGame`, `upsert_game(db: Session, game: RawGame) -> Match`.

- [ ] **Step 1: Write `backend/app/ingestion/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test `backend/tests/test_normalize.py`**

```python
from datetime import datetime

from app.db import Base, get_engine, get_session_factory
from app.ingestion.normalize import normalize_nba_game, normalize_soccer_game, upsert_game
from app.models_db import Match, Team


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def test_normalize_nba_game_maps_fields():
    raw = {
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": 110,
        "visitor_team_score": 102,
        "status": "Final",
    }
    game = normalize_nba_game(raw)
    assert game.external_id == "555"
    assert game.sport == "nba"
    assert game.league == "NBA"
    assert game.home_team_name == "Los Angeles Lakers"
    assert game.away_team_name == "Boston Celtics"
    assert game.home_score == 110
    assert game.away_score == 102
    assert game.status == "final"


def test_normalize_soccer_game_maps_fields():
    raw = {
        "id": 777,
        "utcDate": "2026-02-01T15:00:00Z",
        "homeTeam": {"id": 10, "name": "Arsenal"},
        "awayTeam": {"id": 20, "name": "Chelsea"},
        "score": {"fullTime": {"home": 2, "away": 1}},
        "status": "FINISHED",
    }
    game = normalize_soccer_game(raw, league="EPL")
    assert game.external_id == "777"
    assert game.sport == "soccer"
    assert game.league == "EPL"
    assert game.home_team_name == "Arsenal"
    assert game.away_team_name == "Chelsea"
    assert game.home_score == 2
    assert game.away_score == 1
    assert game.status == "final"


def test_upsert_game_creates_teams_and_match():
    db = make_db()
    game = normalize_nba_game({
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": 110,
        "visitor_team_score": 102,
        "status": "Final",
    })

    match = upsert_game(db, game)

    assert db.query(Team).count() == 2
    assert db.query(Match).count() == 1
    assert match.home_score == 110


def test_upsert_game_is_idempotent():
    db = make_db()
    game = normalize_nba_game({
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": None,
        "visitor_team_score": None,
        "status": "Scheduled",
    })
    upsert_game(db, game)

    finished = normalize_nba_game({
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": 110,
        "visitor_team_score": 102,
        "status": "Final",
    })
    upsert_game(db, finished)

    assert db.query(Match).count() == 1
    assert db.query(Team).count() == 2
    assert db.query(Match).one().home_score == 110
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ingestion.normalize'`

- [ ] **Step 4: Write `backend/app/ingestion/normalize.py`**

```python
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models_db import Match, Team

_STATUS_MAP = {
    "final": "final",
    "finished": "final",
    "scheduled": "scheduled",
}


@dataclass
class RawGame:
    external_id: str
    sport: str
    league: str
    date: datetime
    home_team_external_id: str
    home_team_name: str
    away_team_external_id: str
    away_team_name: str
    home_score: int | None
    away_score: int | None
    status: str


def _normalize_status(raw_status: str) -> str:
    return _STATUS_MAP.get(raw_status.strip().lower(), "scheduled")


def normalize_nba_game(raw: dict) -> RawGame:
    return RawGame(
        external_id=str(raw["id"]),
        sport="nba",
        league="NBA",
        date=datetime.fromisoformat(raw["date"].replace("Z", "+00:00")),
        home_team_external_id=str(raw["home_team"]["id"]),
        home_team_name=raw["home_team"]["full_name"],
        away_team_external_id=str(raw["visitor_team"]["id"]),
        away_team_name=raw["visitor_team"]["full_name"],
        home_score=raw["home_team_score"],
        away_score=raw["visitor_team_score"],
        status=_normalize_status(raw["status"]),
    )


def normalize_soccer_game(raw: dict, league: str) -> RawGame:
    full_time = raw["score"]["fullTime"]
    return RawGame(
        external_id=str(raw["id"]),
        sport="soccer",
        league=league,
        date=datetime.fromisoformat(raw["utcDate"].replace("Z", "+00:00")),
        home_team_external_id=str(raw["homeTeam"]["id"]),
        home_team_name=raw["homeTeam"]["name"],
        away_team_external_id=str(raw["awayTeam"]["id"]),
        away_team_name=raw["awayTeam"]["name"],
        home_score=full_time["home"],
        away_score=full_time["away"],
        status=_normalize_status(raw["status"]),
    )


def _get_or_create_team(db: Session, sport: str, league: str, external_id: str, name: str) -> Team:
    team = (
        db.query(Team)
        .filter(Team.sport == sport, Team.external_id == external_id)
        .one_or_none()
    )
    if team is None:
        team = Team(external_id=external_id, sport=sport, league=league, name=name)
        db.add(team)
        db.flush()
    return team


def upsert_game(db: Session, game: RawGame) -> Match:
    home = _get_or_create_team(db, game.sport, game.league, game.home_team_external_id, game.home_team_name)
    away = _get_or_create_team(db, game.sport, game.league, game.away_team_external_id, game.away_team_name)

    match = (
        db.query(Match)
        .filter(Match.sport == game.sport, Match.external_id == game.external_id)
        .one_or_none()
    )
    if match is None:
        match = Match(
            external_id=game.external_id,
            sport=game.sport,
            league=game.league,
            date=game.date,
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=game.home_score,
            away_score=game.away_score,
            status=game.status,
        )
        db.add(match)
    else:
        match.home_score = game.home_score
        match.away_score = game.away_score
        match.status = game.status
    db.commit()
    return match
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_normalize.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingestion/__init__.py backend/app/ingestion/normalize.py backend/tests/test_normalize.py
git commit -m "feat: sport-agnostic game normalization and upsert"
```

---

### Task 4: NBA ingestion client

**Files:**
- Create: `backend/app/ingestion/nba_client.py`
- Test: `backend/tests/test_nba_client.py`

**Interfaces:**
- Consumes: `app.config.Settings.nba_api_key`.
- Produces: `fetch_games(api_key: str, start_date: str, end_date: str, cursor: int | None = None) -> dict` (returns raw JSON with keys `data: list[dict]`, `meta: {"next_cursor": int | None}`), raw dicts shaped for `normalize_nba_game` from Task 3. Retries transient errors (HTTP 429/5xx) up to 3 times with exponential backoff before raising.

- [ ] **Step 1: Write the failing test `backend/tests/test_nba_client.py`**

```python
from unittest.mock import patch

import requests

from app.ingestion.nba_client import fetch_games


@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_sends_auth_header_and_date_range(mock_get):
    mock_get.return_value.json.return_value = {
        "data": [{"id": 1}],
        "meta": {"next_cursor": None},
    }
    mock_get.return_value.raise_for_status.return_value = None

    result = fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02")

    assert result["data"] == [{"id": 1}]
    called_url = mock_get.call_args.args[0]
    called_headers = mock_get.call_args.kwargs["headers"]
    called_params = mock_get.call_args.kwargs["params"]
    assert "balldontlie.io" in called_url
    assert called_headers["Authorization"] == "secret"
    assert called_params["start_date"] == "2026-01-01"
    assert called_params["end_date"] == "2026-01-02"


@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_passes_cursor_when_given(mock_get):
    mock_get.return_value.json.return_value = {"data": [], "meta": {"next_cursor": None}}
    mock_get.return_value.raise_for_status.return_value = None

    fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02", cursor=42)

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["cursor"] == 42


@patch("app.ingestion.nba_client.time.sleep")
@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_retries_on_rate_limit_then_succeeds(mock_get, mock_sleep):
    rate_limited = requests.Response()
    rate_limited.status_code = 429
    ok_response = requests.Response()
    ok_response.status_code = 200
    ok_response.json = lambda: {"data": [], "meta": {"next_cursor": None}}

    def raise_for_rate_limited():
        raise requests.HTTPError(response=rate_limited)

    rate_limited.raise_for_status = raise_for_rate_limited
    ok_response.raise_for_status = lambda: None

    mock_get.side_effect = [rate_limited, ok_response]

    result = fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02")

    assert result == {"data": [], "meta": {"next_cursor": None}}
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("app.ingestion.nba_client.time.sleep")
@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_raises_after_max_retries(mock_get, mock_sleep):
    failing = requests.Response()
    failing.status_code = 500

    def raise_error():
        raise requests.HTTPError(response=failing)

    failing.raise_for_status = raise_error
    mock_get.return_value = failing

    try:
        fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02")
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass

    assert mock_get.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_nba_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ingestion/nba_client.py`**

```python
import time

import requests

BASE_URL = "https://api.balldontlie.io/v1/games"
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_games(api_key: str, start_date: str, end_date: str, cursor: int | None = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date, "per_page": 100}
    if cursor is not None:
        params["cursor"] = cursor

    for attempt in range(MAX_RETRIES):
        response = requests.get(BASE_URL, headers={"Authorization": api_key}, params=params, timeout=30)
        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            status = response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_nba_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/nba_client.py backend/tests/test_nba_client.py
git commit -m "feat: NBA ingestion client (balldontlie.io)"
```

---

### Task 5: Soccer ingestion client

**Files:**
- Create: `backend/app/ingestion/soccer_client.py`
- Test: `backend/tests/test_soccer_client.py`

**Interfaces:**
- Consumes: `app.config.Settings.football_data_api_key`.
- Produces: `LEAGUE_CODES: dict[str, str]` mapping `"EPL" -> "PL"`, `"La Liga" -> "PD"`, `"Serie A" -> "SA"`, `"Bundesliga" -> "BL1"`, `"Ligue 1" -> "FL1"`.
- Produces: `fetch_matches(api_key: str, league: str, season: int) -> dict` (returns raw JSON with key `matches: list[dict]`), raw dicts shaped for `normalize_soccer_game` from Task 3. Retries transient errors (HTTP 429/5xx) up to 3 times with exponential backoff before raising.

- [ ] **Step 1: Write the failing test `backend/tests/test_soccer_client.py`**

```python
from unittest.mock import patch

import requests

from app.ingestion.soccer_client import LEAGUE_CODES, fetch_matches


def test_league_codes_cover_top_5_leagues():
    assert LEAGUE_CODES == {
        "EPL": "PL",
        "La Liga": "PD",
        "Serie A": "SA",
        "Bundesliga": "BL1",
        "Ligue 1": "FL1",
    }


@patch("app.ingestion.soccer_client.requests.get")
def test_fetch_matches_sends_auth_header_and_season(mock_get):
    mock_get.return_value.json.return_value = {"matches": [{"id": 1}]}
    mock_get.return_value.raise_for_status.return_value = None

    result = fetch_matches(api_key="secret", league="EPL", season=2025)

    assert result["matches"] == [{"id": 1}]
    called_url = mock_get.call_args.args[0]
    called_headers = mock_get.call_args.kwargs["headers"]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url.endswith("/competitions/PL/matches")
    assert called_headers["X-Auth-Token"] == "secret"
    assert called_params["season"] == 2025


def test_fetch_matches_rejects_unknown_league():
    try:
        fetch_matches(api_key="secret", league="Not A League", season=2025)
        assert False, "expected ValueError"
    except ValueError:
        pass


@patch("app.ingestion.soccer_client.time.sleep")
@patch("app.ingestion.soccer_client.requests.get")
def test_fetch_matches_retries_on_rate_limit_then_succeeds(mock_get, mock_sleep):
    rate_limited = requests.Response()
    rate_limited.status_code = 429

    def raise_rate_limited():
        raise requests.HTTPError(response=rate_limited)

    rate_limited.raise_for_status = raise_rate_limited

    ok_response = requests.Response()
    ok_response.status_code = 200
    ok_response.json = lambda: {"matches": []}
    ok_response.raise_for_status = lambda: None

    mock_get.side_effect = [rate_limited, ok_response]

    result = fetch_matches(api_key="secret", league="EPL", season=2025)

    assert result == {"matches": []}
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("app.ingestion.soccer_client.time.sleep")
@patch("app.ingestion.soccer_client.requests.get")
def test_fetch_matches_raises_after_max_retries(mock_get, mock_sleep):
    failing = requests.Response()
    failing.status_code = 503

    def raise_error():
        raise requests.HTTPError(response=failing)

    failing.raise_for_status = raise_error
    mock_get.return_value = failing

    try:
        fetch_matches(api_key="secret", league="EPL", season=2025)
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass

    assert mock_get.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_soccer_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ingestion/soccer_client.py`**

```python
import time

import requests

BASE_URL = "https://api.football-data.org/v4"
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

LEAGUE_CODES = {
    "EPL": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
}


def fetch_matches(api_key: str, league: str, season: int) -> dict:
    if league not in LEAGUE_CODES:
        raise ValueError(f"Unknown league: {league}")

    code = LEAGUE_CODES[league]
    url = f"{BASE_URL}/competitions/{code}/matches"

    for attempt in range(MAX_RETRIES):
        response = requests.get(
            url,
            headers={"X-Auth-Token": api_key},
            params={"season": season},
            timeout=30,
        )
        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            status = response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_soccer_client.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/soccer_client.py backend/tests/test_soccer_client.py
git commit -m "feat: soccer ingestion client (football-data.org, top 5 leagues)"
```

---

### Task 6: Historical backfill script

**Files:**
- Create: `backend/app/ingestion/backfill.py`
- Test: `backend/tests/test_backfill.py`

**Interfaces:**
- Consumes: `fetch_games` (Task 4), `fetch_matches` + `LEAGUE_CODES` (Task 5), `normalize_nba_game`, `normalize_soccer_game`, `upsert_game` (Task 3).
- Produces: `backfill_nba(db: Session, api_key: str, seasons: list[str]) -> int` (returns count of games upserted; a game that fails to normalize/upsert is logged and skipped rather than aborting the batch), `backfill_soccer(db: Session, api_key: str, leagues: list[str], seasons: list[int]) -> int` (same skip-and-log behavior), CLI entry point `if __name__ == "__main__":`.

- [ ] **Step 1: Write the failing test `backend/tests/test_backfill.py`**

```python
from unittest.mock import patch

from app.db import Base, get_engine, get_session_factory
from app.ingestion.backfill import backfill_nba, backfill_soccer
from app.models_db import Match


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


@patch("app.ingestion.backfill.fetch_games")
def test_backfill_nba_paginates_until_no_next_cursor(mock_fetch):
    db = make_db()
    mock_fetch.side_effect = [
        {
            "data": [{
                "id": 1, "date": "2026-01-01T00:00:00.000Z",
                "home_team": {"id": 1, "full_name": "Lakers"},
                "visitor_team": {"id": 2, "full_name": "Celtics"},
                "home_team_score": 100, "visitor_team_score": 90, "status": "Final",
            }],
            "meta": {"next_cursor": 5},
        },
        {
            "data": [{
                "id": 2, "date": "2026-01-02T00:00:00.000Z",
                "home_team": {"id": 1, "full_name": "Lakers"},
                "visitor_team": {"id": 3, "full_name": "Nets"},
                "home_team_score": 95, "visitor_team_score": 99, "status": "Final",
            }],
            "meta": {"next_cursor": None},
        },
    ]

    count = backfill_nba(db, api_key="secret", seasons=["2025-2026"])

    assert count == 2
    assert db.query(Match).count() == 2
    assert mock_fetch.call_count == 2


@patch("app.ingestion.backfill.fetch_matches")
def test_backfill_soccer_pulls_each_league_and_season(mock_fetch):
    db = make_db()
    mock_fetch.return_value = {
        "matches": [{
            "id": 1, "utcDate": "2026-02-01T15:00:00Z",
            "homeTeam": {"id": 10, "name": "Arsenal"},
            "awayTeam": {"id": 20, "name": "Chelsea"},
            "score": {"fullTime": {"home": 2, "away": 1}},
            "status": "FINISHED",
        }]
    }

    count = backfill_soccer(db, api_key="secret", leagues=["EPL", "La Liga"], seasons=[2024])

    assert count == 2
    assert mock_fetch.call_count == 2
    assert db.query(Match).count() == 2


@patch("app.ingestion.backfill.fetch_games")
def test_backfill_nba_skips_bad_game_and_keeps_going(mock_fetch):
    db = make_db()
    mock_fetch.return_value = {
        "data": [
            {"id": 1, "date": "not-a-valid-date", "home_team": {"id": 1, "full_name": "Lakers"},
             "visitor_team": {"id": 2, "full_name": "Celtics"}, "home_team_score": 100,
             "visitor_team_score": 90, "status": "Final"},
            {"id": 2, "date": "2026-01-02T00:00:00.000Z", "home_team": {"id": 1, "full_name": "Lakers"},
             "visitor_team": {"id": 3, "full_name": "Nets"}, "home_team_score": 95,
             "visitor_team_score": 99, "status": "Final"},
        ],
        "meta": {"next_cursor": None},
    }

    count = backfill_nba(db, api_key="secret", seasons=["2025-2026"])

    assert count == 1
    assert db.query(Match).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_backfill.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ingestion/backfill.py`**

```python
import argparse
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory
from app.ingestion.nba_client import fetch_games
from app.ingestion.normalize import normalize_nba_game, normalize_soccer_game, upsert_game
from app.ingestion.soccer_client import LEAGUE_CODES, fetch_matches

logger = logging.getLogger(__name__)


def backfill_nba(db: Session, api_key: str, seasons: list[str]) -> int:
    count = 0
    for season in seasons:
        start_date, end_date = f"{season[:4]}-10-01", f"{season[-4:]}-06-30"
        cursor = None
        while True:
            page = fetch_games(api_key, start_date, end_date, cursor=cursor)
            for raw in page["data"]:
                try:
                    upsert_game(db, normalize_nba_game(raw))
                    count += 1
                except Exception:
                    logger.warning("Skipping unparseable NBA game %r", raw.get("id"), exc_info=True)
            cursor = page["meta"]["next_cursor"]
            if cursor is None:
                break
    return count


def backfill_soccer(db: Session, api_key: str, leagues: list[str], seasons: list[int]) -> int:
    count = 0
    for league in leagues:
        for season in seasons:
            page = fetch_matches(api_key, league, season)
            for raw in page["matches"]:
                try:
                    upsert_game(db, normalize_soccer_game(raw, league))
                    count += 1
                except Exception:
                    logger.warning("Skipping unparseable soccer match %r", raw.get("id"), exc_info=True)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nba-seasons", nargs="*", default=["2023-2024", "2024-2025", "2025-2026"])
    parser.add_argument("--soccer-seasons", nargs="*", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()

    settings = get_settings()
    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    nba_count = backfill_nba(db, settings.nba_api_key, args.nba_seasons)
    soccer_count = backfill_soccer(db, settings.football_data_api_key, list(LEAGUE_CODES.keys()), args.soccer_seasons)
    print(f"Backfilled {nba_count} NBA games and {soccer_count} soccer games")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_backfill.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/backfill.py backend/tests/test_backfill.py
git commit -m "feat: historical backfill script for NBA and soccer"
```

- [ ] **Step 6: Manual data pull (not a unit test — run once against real APIs)**

Sign up for free API keys at balldontlie.io and football-data.org, fill in `backend/.env`, then run:
`cd backend && python -m app.ingestion.backfill`
Confirm it prints a non-zero count for both sports and that `SELECT COUNT(*) FROM matches;` in Postgres (or `matchiq.db` via `sqlite3`) shows real rows.

---

### Task 7: Daily sync script

**Files:**
- Create: `backend/app/ingestion/daily_sync.py`
- Test: `backend/tests/test_daily_sync.py`

**Interfaces:**
- Consumes: `fetch_games` (Task 4), `fetch_matches` + `LEAGUE_CODES` (Task 5), `normalize_nba_game`, `normalize_soccer_game`, `upsert_game` (Task 3).
- Produces: `sync_recent(db: Session, nba_api_key: str, football_api_key: str, days_back: int = 3, days_forward: int = 7) -> int` (same skip-and-log behavior as `backfill.py` for unparseable games), CLI entry point.

- [ ] **Step 1: Write the failing test `backend/tests/test_daily_sync.py`**

```python
from unittest.mock import patch

from app.db import Base, get_engine, get_session_factory
from app.ingestion.daily_sync import sync_recent
from app.models_db import Match


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


@patch("app.ingestion.daily_sync.fetch_matches")
@patch("app.ingestion.daily_sync.fetch_games")
def test_sync_recent_pulls_nba_and_all_soccer_leagues(mock_nba, mock_soccer):
    db = make_db()
    mock_nba.return_value = {"data": [], "meta": {"next_cursor": None}}
    mock_soccer.return_value = {"matches": []}

    sync_recent(db, nba_api_key="a", football_api_key="b")

    assert mock_nba.call_count == 1
    assert mock_soccer.call_count == 5  # one call per top-5 league


@patch("app.ingestion.daily_sync.fetch_matches")
@patch("app.ingestion.daily_sync.fetch_games")
def test_sync_recent_upserts_returned_games(mock_nba, mock_soccer):
    db = make_db()
    mock_nba.return_value = {
        "data": [{
            "id": 1, "date": "2026-01-01T00:00:00.000Z",
            "home_team": {"id": 1, "full_name": "Lakers"},
            "visitor_team": {"id": 2, "full_name": "Celtics"},
            "home_team_score": 100, "visitor_team_score": 90, "status": "Final",
        }],
        "meta": {"next_cursor": None},
    }
    mock_soccer.return_value = {"matches": []}

    count = sync_recent(db, nba_api_key="a", football_api_key="b")

    assert count == 1
    assert db.query(Match).count() == 1


@patch("app.ingestion.daily_sync.fetch_matches")
@patch("app.ingestion.daily_sync.fetch_games")
def test_sync_recent_skips_bad_game_and_keeps_going(mock_nba, mock_soccer):
    db = make_db()
    mock_nba.return_value = {
        "data": [
            {"id": 1, "date": "not-a-valid-date", "home_team": {"id": 1, "full_name": "Lakers"},
             "visitor_team": {"id": 2, "full_name": "Celtics"}, "home_team_score": 100,
             "visitor_team_score": 90, "status": "Final"},
            {"id": 2, "date": "2026-01-02T00:00:00.000Z", "home_team": {"id": 1, "full_name": "Lakers"},
             "visitor_team": {"id": 3, "full_name": "Nets"}, "home_team_score": 95,
             "visitor_team_score": 99, "status": "Final"},
        ],
        "meta": {"next_cursor": None},
    }
    mock_soccer.return_value = {"matches": []}

    count = sync_recent(db, nba_api_key="a", football_api_key="b")

    assert count == 1
    assert db.query(Match).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_daily_sync.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ingestion/daily_sync.py`**

```python
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory
from app.ingestion.nba_client import fetch_games
from app.ingestion.normalize import normalize_nba_game, normalize_soccer_game, upsert_game
from app.ingestion.soccer_client import LEAGUE_CODES, fetch_matches

logger = logging.getLogger(__name__)


def sync_recent(db: Session, nba_api_key: str, football_api_key: str, days_back: int = 3, days_forward: int = 7) -> int:
    start = (date.today() - timedelta(days=days_back)).isoformat()
    end = (date.today() + timedelta(days=days_forward)).isoformat()

    count = 0
    nba_page = fetch_games(nba_api_key, start, end)
    for raw in nba_page["data"]:
        try:
            upsert_game(db, normalize_nba_game(raw))
            count += 1
        except Exception:
            logger.warning("Skipping unparseable NBA game %r", raw.get("id"), exc_info=True)

    current_season = date.today().year
    for league in LEAGUE_CODES:
        soccer_page = fetch_matches(football_api_key, league, current_season)
        for raw in soccer_page["matches"]:
            try:
                upsert_game(db, normalize_soccer_game(raw, league))
                count += 1
            except Exception:
                logger.warning("Skipping unparseable soccer match %r", raw.get("id"), exc_info=True)

    return count


if __name__ == "__main__":
    settings = get_settings()
    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()
    total = sync_recent(db, settings.nba_api_key, settings.football_data_api_key)
    print(f"Synced {total} games")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_daily_sync.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/daily_sync.py backend/tests/test_daily_sync.py
git commit -m "feat: daily sync script for recent results and upcoming fixtures"
```

---

### Task 8: Feature engineering

**Files:**
- Create: `backend/app/features/__init__.py`
- Create: `backend/app/features/build_features.py`
- Test: `backend/tests/test_build_features.py`

**Interfaces:**
- Consumes: `app.models_db.Match`, `app.models_db.Team` from Task 2.
- Produces: `MatchFeatures` dataclass (fields: `home_form_last5: float, away_form_last5: float, home_win_rate_home: float, away_win_rate_away: float, h2h_home_win_rate: float, home_rest_days: int, away_rest_days: int`).
- Produces: `compute_features(db: Session, match: Match) -> MatchFeatures`, `build_training_dataframe(db: Session, sport: str) -> pd.DataFrame` (columns: all `MatchFeatures` fields plus `home_score`, `away_score`, `result` where `result` is `"H"`/`"D"`/`"A"`).

- [ ] **Step 1: Write the failing test `backend/tests/test_build_features.py`**

```python
from datetime import datetime, timedelta

from app.db import Base, get_engine, get_session_factory
from app.features.build_features import build_training_dataframe, compute_features
from app.models_db import Match, Team


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def add_team(db, external_id, name, sport="nba", league="NBA"):
    team = Team(external_id=external_id, sport=sport, league=league, name=name)
    db.add(team)
    db.flush()
    return team


def add_match(db, home, away, day_offset, home_score, away_score, sport="nba", league="NBA"):
    match = Match(
        external_id=f"m{day_offset}-{home.id}-{away.id}",
        sport=sport,
        league=league,
        date=datetime(2026, 1, 1) + timedelta(days=day_offset),
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=home_score,
        away_score=away_score,
        status="final",
    )
    db.add(match)
    db.commit()
    return match


def test_compute_features_uses_only_past_matches():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")
    nets = add_team(db, "3", "Nets")

    add_match(db, lakers, nets, day_offset=0, home_score=100, away_score=90)  # Lakers win, home
    add_match(db, celtics, lakers, day_offset=2, home_score=80, away_score=95)  # Lakers win, away

    target = add_match(db, lakers, celtics, day_offset=5, home_score=None, away_score=None)

    features = compute_features(db, target)

    assert features.home_form_last5 == 1.0  # Lakers won both prior games
    assert features.home_rest_days == 3  # last Lakers game was day 2, target is day 5


def test_build_training_dataframe_only_includes_final_matches():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    add_match(db, lakers, celtics, day_offset=0, home_score=100, away_score=90)
    add_match(db, lakers, celtics, day_offset=5, home_score=None, away_score=None)  # scheduled, excluded

    df = build_training_dataframe(db, sport="nba")

    assert len(df) == 1
    assert df.iloc[0]["result"] == "H"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_build_features.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/features/__init__.py`** (empty file)

- [ ] **Step 4: Write `backend/app/features/build_features.py`**

```python
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models_db import Match


@dataclass
class MatchFeatures:
    home_form_last5: float
    away_form_last5: float
    home_win_rate_home: float
    away_win_rate_away: float
    h2h_home_win_rate: float
    home_rest_days: int
    away_rest_days: int


def _did_team_win(match: Match, team_id: int) -> bool:
    if match.home_team_id == team_id:
        return match.home_score > match.away_score
    return match.away_score > match.home_score


def _team_matches_before(db: Session, sport: str, team_id: int, before_date, limit: int | None = None):
    query = (
        db.query(Match)
        .filter(
            Match.sport == sport,
            Match.status == "final",
            Match.date < before_date,
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        )
        .order_by(Match.date.desc())
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def _form(matches: list[Match], team_id: int) -> float:
    if not matches:
        return 0.5
    wins = sum(1 for m in matches if _did_team_win(m, team_id))
    return wins / len(matches)


def _home_away_win_rate(db: Session, sport: str, team_id: int, before_date, is_home: bool) -> float:
    column = Match.home_team_id if is_home else Match.away_team_id
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "final", Match.date < before_date, column == team_id)
        .all()
    )
    return _form(matches, team_id)


def _rest_days(matches: list[Match], target_date) -> int:
    if not matches:
        return 7
    return (target_date - matches[0].date).days


def _h2h_home_win_rate(db: Session, sport: str, home_id: int, away_id: int, before_date) -> float:
    matches = (
        db.query(Match)
        .filter(
            Match.sport == sport,
            Match.status == "final",
            Match.date < before_date,
            or_(
                (Match.home_team_id == home_id) & (Match.away_team_id == away_id),
                (Match.home_team_id == away_id) & (Match.away_team_id == home_id),
            ),
        )
        .all()
    )
    if not matches:
        return 0.5
    home_wins = sum(1 for m in matches if _did_team_win(m, home_id))
    return home_wins / len(matches)


def compute_features(db: Session, match: Match) -> MatchFeatures:
    home_recent = _team_matches_before(db, match.sport, match.home_team_id, match.date, limit=5)
    away_recent = _team_matches_before(db, match.sport, match.away_team_id, match.date, limit=5)

    return MatchFeatures(
        home_form_last5=_form(home_recent, match.home_team_id),
        away_form_last5=_form(away_recent, match.away_team_id),
        home_win_rate_home=_home_away_win_rate(db, match.sport, match.home_team_id, match.date, is_home=True),
        away_win_rate_away=_home_away_win_rate(db, match.sport, match.away_team_id, match.date, is_home=False),
        h2h_home_win_rate=_h2h_home_win_rate(db, match.sport, match.home_team_id, match.away_team_id, match.date),
        home_rest_days=_rest_days(home_recent, match.date),
        away_rest_days=_rest_days(away_recent, match.date),
    )


def _result(match: Match) -> str:
    if match.home_score > match.away_score:
        return "H"
    if match.home_score < match.away_score:
        return "A"
    return "D"


def build_training_dataframe(db: Session, sport: str) -> pd.DataFrame:
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "final")
        .order_by(Match.date.asc())
        .all()
    )

    rows = []
    for match in matches:
        features = compute_features(db, match)
        rows.append({
            **features.__dict__,
            "home_score": match.home_score,
            "away_score": match.away_score,
            "result": _result(match),
            "date": match.date,
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_build_features.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/features/__init__.py backend/app/features/build_features.py backend/tests/test_build_features.py
git commit -m "feat: rolling form, home/away, h2h, and rest-day feature engineering"
```

---

### Task 9: Naive baseline and evaluation metrics

**Files:**
- Create: `backend/app/ml/__init__.py`
- Create: `backend/app/ml/baseline.py`
- Test: `backend/tests/test_baseline.py`

**Interfaces:**
- Consumes: nothing beyond stdlib/pandas/sklearn.
- Produces: `naive_home_favorite_probs(n: int, sport: str) -> list[dict]` (returns constant probability dicts: `{"H": 1.0, "A": 0.0}` for NBA or `{"H": 1.0, "D": 0.0, "A": 0.0}` for soccer, repeated `n` times), `evaluate(y_true: list[str], y_pred_probs: list[dict], labels: list[str]) -> dict` (returns `{"accuracy": float, "log_loss": float, "brier_score": float}`).

- [ ] **Step 1: Write the failing test `backend/tests/test_baseline.py`**

```python
import math

from app.ml.baseline import evaluate, naive_home_favorite_probs


def test_naive_home_favorite_probs_nba():
    probs = naive_home_favorite_probs(3, sport="nba")
    assert probs == [{"H": 1.0, "A": 0.0}] * 3


def test_naive_home_favorite_probs_soccer():
    probs = naive_home_favorite_probs(2, sport="soccer")
    assert probs == [{"H": 1.0, "D": 0.0, "A": 0.0}] * 2


def test_evaluate_perfect_predictions():
    y_true = ["H", "H", "A"]
    y_pred = [{"H": 1.0, "A": 0.0}] * 2 + [{"H": 0.0, "A": 1.0}]

    metrics = evaluate(y_true, y_pred, labels=["H", "A"])

    assert metrics["accuracy"] == 1.0
    assert math.isclose(metrics["log_loss"], 0.0, abs_tol=1e-6)
    assert math.isclose(metrics["brier_score"], 0.0, abs_tol=1e-6)


def test_evaluate_naive_baseline_on_mixed_results():
    y_true = ["H", "A", "H"]
    y_pred = [{"H": 1.0, "A": 0.0}] * 3

    metrics = evaluate(y_true, y_pred, labels=["H", "A"])

    assert math.isclose(metrics["accuracy"], 2 / 3, abs_tol=1e-6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_baseline.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ml/__init__.py`** (empty file)

- [ ] **Step 4: Write `backend/app/ml/baseline.py`**

```python
import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss


def naive_home_favorite_probs(n: int, sport: str) -> list[dict]:
    if sport == "soccer":
        return [{"H": 1.0, "D": 0.0, "A": 0.0} for _ in range(n)]
    return [{"H": 1.0, "A": 0.0} for _ in range(n)]


def evaluate(y_true: list[str], y_pred_probs: list[dict], labels: list[str]) -> dict:
    y_true_idx = [labels.index(label) for label in y_true]
    prob_matrix = np.array([[probs.get(label, 0.0) for label in labels] for probs in y_pred_probs])
    predicted_labels = [labels[np.argmax(row)] for row in prob_matrix]

    accuracy = accuracy_score(y_true, predicted_labels)
    loss = log_loss(y_true_idx, prob_matrix, labels=list(range(len(labels))))

    home_true = np.array([1.0 if label == "H" else 0.0 for label in y_true])
    home_pred = prob_matrix[:, labels.index("H")]
    brier = brier_score_loss(home_true, home_pred)

    return {"accuracy": float(accuracy), "log_loss": float(loss), "brier_score": float(brier)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_baseline.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/ml/__init__.py backend/app/ml/baseline.py backend/tests/test_baseline.py
git commit -m "feat: naive home-favorite baseline and evaluation metrics"
```

---

### Task 10: Model training pipeline

**Files:**
- Create: `backend/app/ml/train.py`
- Test: `backend/tests/test_train.py`

**Interfaces:**
- Consumes: `build_training_dataframe` (Task 8), `naive_home_favorite_probs`, `evaluate` (Task 9).
- Produces: `train_sport_models(db: Session, sport: str, artifact_dir: Path) -> dict` (returns `{"model_metrics": {...}, "baseline_metrics": {...}, "beat_baseline": bool, "artifact_path": str | None}`). Saves a joblib dict `{"classifier": ..., "regressor": ..., "feature_columns": [...], "labels": [...]}` to `artifact_dir/{sport}_latest.joblib` only when `beat_baseline` is True.

- [ ] **Step 1: Write the failing test `backend/tests/test_train.py`**

```python
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.db import Base, get_engine, get_session_factory
from app.ml.train import train_sport_models
from app.models_db import Match, Team


def make_db_with_synthetic_matches(n_teams=6, n_matches=120):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    random.seed(42)
    teams = [Team(external_id=str(i), sport="nba", league="NBA", name=f"Team{i}") for i in range(n_teams)]
    db.add_all(teams)
    db.commit()

    # Team 0 is a "strong" team that wins most home games, giving the model
    # a real signal to learn (unlike pure-random labels, which no model can beat).
    for day in range(n_matches):
        home, away = random.sample(teams, 2)
        home_strong = home.id == teams[0].id
        home_score = random.randint(95, 115) + (10 if home_strong else 0)
        away_score = random.randint(90, 110)
        db.add(Match(
            external_id=f"m{day}",
            sport="nba",
            league="NBA",
            date=datetime(2025, 1, 1) + timedelta(days=day),
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=home_score,
            away_score=away_score,
            status="final",
        ))
    db.commit()
    return db


def test_train_sport_models_saves_artifact_when_it_beats_baseline(tmp_path: Path):
    db = make_db_with_synthetic_matches()

    result = train_sport_models(db, sport="nba", artifact_dir=tmp_path)

    assert "model_metrics" in result
    assert "baseline_metrics" in result
    artifact_path = tmp_path / "nba_latest.joblib"
    if result["beat_baseline"]:
        assert artifact_path.exists()
        assert result["artifact_path"] == str(artifact_path)
    else:
        assert not artifact_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_train.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ml/train.py`**

```python
from pathlib import Path

import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session
from xgboost import XGBClassifier, XGBRegressor

from app.features.build_features import build_training_dataframe
from app.ml.baseline import evaluate, naive_home_favorite_probs

FEATURE_COLUMNS = [
    "home_form_last5",
    "away_form_last5",
    "home_win_rate_home",
    "away_win_rate_away",
    "h2h_home_win_rate",
    "home_rest_days",
    "away_rest_days",
]


def _labels_for_sport(sport: str) -> list[str]:
    return ["H", "D", "A"] if sport == "soccer" else ["H", "A"]


def train_sport_models(db: Session, sport: str, artifact_dir: Path) -> dict:
    df = build_training_dataframe(db, sport)
    df = df.sort_values("date").reset_index(drop=True)
    labels = _labels_for_sport(sport)

    split_idx = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]

    X_train, X_test = train_df[FEATURE_COLUMNS], test_df[FEATURE_COLUMNS]
    y_train = train_df["result"].map({label: i for i, label in enumerate(labels)})
    y_test = test_df["result"]

    classifier = XGBClassifier(n_estimators=100, max_depth=3, eval_metric="mlogloss" if sport == "soccer" else "logloss")
    classifier.fit(X_train, y_train)

    regressor_home = XGBRegressor(n_estimators=100, max_depth=3)
    regressor_home.fit(X_train, train_df["home_score"])
    regressor_away = XGBRegressor(n_estimators=100, max_depth=3)
    regressor_away.fit(X_train, train_df["away_score"])

    proba = classifier.predict_proba(X_test)
    model_probs = [dict(zip(labels, row)) for row in proba]
    model_metrics = evaluate(list(y_test), model_probs, labels)

    baseline_probs = naive_home_favorite_probs(len(y_test), sport)
    baseline_metrics = evaluate(list(y_test), baseline_probs, labels)

    beat_baseline = model_metrics["log_loss"] < baseline_metrics["log_loss"]

    artifact_path = None
    if beat_baseline:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{sport}_latest.joblib"
        joblib.dump(
            {
                "classifier": classifier,
                "regressor_home": regressor_home,
                "regressor_away": regressor_away,
                "feature_columns": FEATURE_COLUMNS,
                "labels": labels,
            },
            artifact_path,
        )

    return {
        "model_metrics": model_metrics,
        "baseline_metrics": baseline_metrics,
        "beat_baseline": beat_baseline,
        "artifact_path": str(artifact_path) if artifact_path else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_train.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ml/train.py backend/tests/test_train.py
git commit -m "feat: XGBoost training pipeline with baseline gate on artifact saving"
```

- [ ] **Step 6: Manual run against real backfilled data**

Run: `cd backend && python -c "from app.config import get_settings; from app.db import get_engine, get_session_factory; from app.ml.train import train_sport_models; s = get_settings(); db = get_session_factory(get_engine(s.database_url))(); print(train_sport_models(db, 'nba', s.artifact_dir)); print(train_sport_models(db, 'soccer', s.artifact_dir))"`
Confirm both sports print `beat_baseline: True` and an `artifact_path`. If either is `False`, that sport's model is not ready to serve — note it and revisit feature engineering before proceeding to Task 11 for that sport (the API in Task 11 must handle a missing artifact with a 503, so this doesn't block the other sport).

---

### Task 11: Prediction service

**Files:**
- Create: `backend/app/ml/predict.py`
- Test: `backend/tests/test_predict.py`

**Interfaces:**
- Consumes: `MatchFeatures`, `compute_features` (Task 8), artifact format from Task 10 (`{"classifier", "regressor_home", "regressor_away", "feature_columns", "labels"}`).
- Produces: `Prediction` dataclass (fields: `home_win_prob: float, draw_prob: float | None, away_win_prob: float, predicted_home_score: float, predicted_away_score: float`).
- Produces: `load_latest_artifact(sport: str, artifact_dir: Path) -> dict | None`, `predict_match(artifact: dict, features: MatchFeatures) -> Prediction`.

- [ ] **Step 1: Write the failing test `backend/tests/test_predict.py`**

```python
from pathlib import Path
from unittest.mock import MagicMock

import joblib
import numpy as np

from app.features.build_features import MatchFeatures
from app.ml.predict import load_latest_artifact, predict_match


def test_load_latest_artifact_returns_none_when_missing(tmp_path: Path):
    assert load_latest_artifact("nba", tmp_path) is None


def test_load_latest_artifact_loads_saved_file(tmp_path: Path):
    joblib.dump({"labels": ["H", "A"]}, tmp_path / "nba_latest.joblib")
    artifact = load_latest_artifact("nba", tmp_path)
    assert artifact["labels"] == ["H", "A"]


def test_predict_match_nba_returns_two_way_probs():
    classifier = MagicMock()
    classifier.predict_proba.return_value = np.array([[0.7, 0.3]])
    regressor_home = MagicMock()
    regressor_home.predict.return_value = np.array([105.0])
    regressor_away = MagicMock()
    regressor_away.predict.return_value = np.array([98.0])

    artifact = {
        "classifier": classifier,
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": ["home_form_last5", "away_form_last5", "home_win_rate_home", "away_win_rate_away", "h2h_home_win_rate", "home_rest_days", "away_rest_days"],
        "labels": ["H", "A"],
    }
    features = MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3)

    prediction = predict_match(artifact, features)

    assert prediction.home_win_prob == 0.7
    assert prediction.away_win_prob == 0.3
    assert prediction.draw_prob is None
    assert prediction.predicted_home_score == 105.0
    assert prediction.predicted_away_score == 98.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_predict.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `backend/app/ml/predict.py`**

```python
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from app.features.build_features import MatchFeatures


@dataclass
class Prediction:
    home_win_prob: float
    draw_prob: float | None
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float


def load_latest_artifact(sport: str, artifact_dir: Path) -> dict | None:
    path = Path(artifact_dir) / f"{sport}_latest.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def predict_match(artifact: dict, features: MatchFeatures) -> Prediction:
    row = pd.DataFrame([features.__dict__])[artifact["feature_columns"]]
    proba = artifact["classifier"].predict_proba(row)[0]
    labels = artifact["labels"]
    probs = dict(zip(labels, proba))

    home_score = float(artifact["regressor_home"].predict(row)[0])
    away_score = float(artifact["regressor_away"].predict(row)[0])

    return Prediction(
        home_win_prob=float(probs["H"]),
        draw_prob=float(probs["D"]) if "D" in probs else None,
        away_win_prob=float(probs["A"]),
        predicted_home_score=home_score,
        predicted_away_score=away_score,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_predict.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ml/predict.py backend/tests/test_predict.py
git commit -m "feat: prediction service loading latest artifact and scoring fixtures"
```

---

### Task 12: API schemas and dependency wiring

**Files:**
- Create: `backend/app/schemas.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `app.models_db.Team`, `app.models_db.Match` (Task 2), `app.ml.predict.Prediction` shape (Task 11).
- Produces: `TeamOut(id, name, league)`, `PredictionOut(game_id, sport, league, date, home_team: TeamOut, away_team: TeamOut, home_win_prob, draw_prob, away_win_prob, predicted_home_score, predicted_away_score)`.
- Produces: `app.main.get_db()` FastAPI dependency yielding a `Session`, `app.main.get_artifact_dir()` dependency returning `Settings.artifact_dir`.

- [ ] **Step 1: Write `backend/app/schemas.py`**

```python
from datetime import datetime

from pydantic import BaseModel


class TeamOut(BaseModel):
    id: int
    name: str
    league: str

    class Config:
        from_attributes = True


class PredictionOut(BaseModel):
    game_id: int
    sport: str
    league: str
    date: datetime
    home_team: TeamOut
    away_team: TeamOut
    home_win_prob: float
    draw_prob: float | None
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
```

- [ ] **Step 2: Modify `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory

app = FastAPI(title="MatchIQ API")

_settings = get_settings()
_engine = get_engine(_settings.database_url)
Base.metadata.create_all(_engine)
_SessionFactory = get_session_factory(_engine)


def get_db():
    db = _SessionFactory()
    try:
        yield db
    finally:
        db.close()


def get_artifact_dir():
    return _settings.artifact_dir


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 3: Run existing tests to confirm nothing broke**

Run: `cd backend && pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas.py backend/app/main.py
git commit -m "feat: API response schemas and shared db/artifact dependencies"
```

---

### Task 13: Predictions and teams API endpoints

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/predictions.py`
- Create: `backend/app/routers/teams.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_predictions.py`
- Test: `backend/tests/test_api_teams.py`

**Interfaces:**
- Consumes: `get_db`, `get_artifact_dir` (Task 12), `load_latest_artifact`, `predict_match` (Task 11), `compute_features` (Task 8), `PredictionOut`, `TeamOut` (Task 12).
- Produces: `GET /predictions/upcoming?sport=nba|soccer` -> `list[PredictionOut]`, `GET /predictions/{game_id}` -> `PredictionOut` (404 if game not found, 503 if no artifact), `GET /teams/{team_id}` -> `TeamOut` (404 if not found).

- [ ] **Step 1: Write the failing test `backend/tests/test_api_predictions.py`**

```python
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_artifact_dir, get_db
from app.ml.predict import Prediction
from app.models_db import Match, Team


@pytest.fixture
def client_with_db(tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = get_session_factory(engine)
    db = SessionFactory()

    home = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    away = Team(external_id="2", sport="nba", league="NBA", name="Celtics")
    db.add_all([home, away])
    db.commit()

    match = Match(
        external_id="100", sport="nba", league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(match)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    yield TestClient(app), match
    app.dependency_overrides.clear()


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.predict_match")
def test_upcoming_returns_predictions_for_sport(mock_predict, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0)

    response = client.get("/predictions/upcoming?sport=nba")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["home_team"]["name"] == "Lakers"
    assert body[0]["home_win_prob"] == 0.65


def test_upcoming_returns_503_when_no_artifact(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/upcoming?sport=nba")
    assert response.status_code == 503


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.predict_match")
def test_get_prediction_by_id(mock_predict, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0)

    response = client.get(f"/predictions/{match.id}")

    assert response.status_code == 200
    assert response.json()["game_id"] == match.id


def test_get_prediction_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999")
    assert response.status_code == 404
```

- [ ] **Step 2: Write the failing test `backend/tests/test_api_teams.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_db
from app.models_db import Team


@pytest.fixture
def client_with_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()
    team = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    db.add(team)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), team
    app.dependency_overrides.clear()


def test_get_team_by_id(client_with_db):
    client, team = client_with_db
    response = client.get(f"/teams/{team.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Lakers"


def test_get_team_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/teams/999999")
    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_api_predictions.py tests/test_api_teams.py -v`
Expected: FAIL with `ImportError` (routers don't exist yet)

- [ ] **Step 4: Write `backend/app/routers/__init__.py`** (empty file)

- [ ] **Step 5: Write `backend/app/routers/predictions.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.features.build_features import compute_features
from app.main import get_artifact_dir, get_db
from app.ml.predict import load_latest_artifact, predict_match
from app.models_db import Match
from app.schemas import PredictionOut

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _to_prediction_out(match: Match, artifact: dict, db: Session) -> PredictionOut:
    features = compute_features(db, match)
    prediction = predict_match(artifact, features)
    return PredictionOut(
        game_id=match.id,
        sport=match.sport,
        league=match.league,
        date=match.date,
        home_team=match.home_team,
        away_team=match.away_team,
        home_win_prob=prediction.home_win_prob,
        draw_prob=prediction.draw_prob,
        away_win_prob=prediction.away_win_prob,
        predicted_home_score=prediction.predicted_home_score,
        predicted_away_score=prediction.predicted_away_score,
    )


@router.get("/upcoming", response_model=list[PredictionOut])
def get_upcoming(sport: str, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={sport}")

    matches = db.query(Match).filter(Match.sport == sport, Match.status == "scheduled").all()
    return [_to_prediction_out(match, artifact, db) for match in matches]


@router.get("/{game_id}", response_model=PredictionOut)
def get_prediction(game_id: int, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    match = db.query(Match).filter(Match.id == game_id).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Game not found")

    artifact = load_latest_artifact(match.sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={match.sport}")

    return _to_prediction_out(match, artifact, db)
```

- [ ] **Step 6: Write `backend/app/routers/teams.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_db
from app.models_db import Team
from app.schemas import TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team
```

- [ ] **Step 7: Modify `backend/app/main.py`** to register routers (add after the `get_artifact_dir` function, before nothing else changes)

```python
from app.routers import predictions, teams

app.include_router(predictions.router)
app.include_router(teams.router)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && pytest tests/ -v`
Expected: PASS (all tests across the whole suite)

- [ ] **Step 9: Commit**

```bash
git add backend/app/routers backend/app/main.py backend/tests/test_api_predictions.py backend/tests/test_api_teams.py
git commit -m "feat: predictions and teams API endpoints"
```

---

### Task 14: Frontend scaffold, API client, and types

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Test: `frontend/src/__tests__/api.test.ts`

**Interfaces:**
- Produces: `PredictionOut` TypeScript type mirroring the backend Pydantic schema (Task 12) exactly (same field names).
- Produces: `fetchUpcomingPredictions(sport: "nba" | "soccer"): Promise<PredictionOut[]>` calling `GET {API_BASE_URL}/predictions/upcoming?sport=...`.

- [ ] **Step 1: Scaffold Vite project**

Run: `cd ~/matchiq && npm create vite@latest frontend -- --template react-ts`
Then: `cd frontend && npm install && npm install -D tailwindcss postcss autoprefixer vitest @testing-library/react @testing-library/jest-dom jsdom && npx tailwindcss init -p`

- [ ] **Step 2: Write `frontend/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 3: Write `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: Write `frontend/src/types.ts`**

```typescript
export interface TeamOut {
  id: number;
  name: string;
  league: string;
}

export interface PredictionOut {
  game_id: number;
  sport: "nba" | "soccer";
  league: string;
  date: string;
  home_team: TeamOut;
  away_team: TeamOut;
  home_win_prob: number;
  draw_prob: number | null;
  away_win_prob: number;
  predicted_home_score: number;
  predicted_away_score: number;
}
```

- [ ] **Step 5: Write the failing test `frontend/src/__tests__/api.test.ts`**

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchUpcomingPredictions } from "../api";
import type { PredictionOut } from "../types";

describe("fetchUpcomingPredictions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the predictions/upcoming endpoint with the sport query param", async () => {
    const mockData: PredictionOut[] = [];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    await fetchUpcomingPredictions("nba");

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/predictions/upcoming?sport=nba"),
    );
  });

  it("throws when the response is not ok", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(fetchUpcomingPredictions("soccer")).rejects.toThrow();
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/api.test.ts`
Expected: FAIL with module not found (`../api`)

- [ ] **Step 7: Write `frontend/src/api.ts`**

```typescript
import type { PredictionOut } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchUpcomingPredictions(sport: "nba" | "soccer"): Promise<PredictionOut[]> {
  const response = await fetch(`${API_BASE_URL}/predictions/upcoming?sport=${sport}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch predictions: ${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/api.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js frontend/src/index.css frontend/src/types.ts frontend/src/api.ts frontend/src/__tests__/api.test.ts
git commit -m "feat: frontend scaffold with typed API client"
```

---

### Task 15: GameCard component

**Files:**
- Create: `frontend/src/components/GameCard.tsx`
- Test: `frontend/src/__tests__/GameCard.test.tsx`

**Interfaces:**
- Consumes: `PredictionOut` type (Task 14).
- Produces: `GameCard({ prediction }: { prediction: PredictionOut }): JSX.Element`, rendering team names, a home-win probability bar, draw probability (soccer only), and predicted score.

- [ ] **Step 1: Write the failing test `frontend/src/__tests__/GameCard.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GameCard } from "../components/GameCard";
import type { PredictionOut } from "../types";

const basePrediction: PredictionOut = {
  game_id: 1,
  sport: "nba",
  league: "NBA",
  date: "2026-02-01T19:00:00Z",
  home_team: { id: 1, name: "Lakers", league: "NBA" },
  away_team: { id: 2, name: "Celtics", league: "NBA" },
  home_win_prob: 0.65,
  draw_prob: null,
  away_win_prob: 0.35,
  predicted_home_score: 108,
  predicted_away_score: 101,
};

describe("GameCard", () => {
  it("renders team names and predicted score", () => {
    render(<GameCard prediction={basePrediction} />);
    expect(screen.getByText("Lakers")).toBeInTheDocument();
    expect(screen.getByText("Celtics")).toBeInTheDocument();
    expect(screen.getByText("108")).toBeInTheDocument();
    expect(screen.getByText("101")).toBeInTheDocument();
  });

  it("renders home win probability as a percentage", () => {
    render(<GameCard prediction={basePrediction} />);
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("renders draw probability only when present", () => {
    render(<GameCard prediction={{ ...basePrediction, sport: "soccer", draw_prob: 0.25, home_win_prob: 0.5, away_win_prob: 0.25 }} />);
    expect(screen.getByText("25%")).toBeInTheDocument();
  });

  it("omits draw probability for nba", () => {
    render(<GameCard prediction={basePrediction} />);
    expect(screen.queryByText("Draw")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/GameCard.test.tsx`
Expected: FAIL with module not found

- [ ] **Step 3: Write `frontend/src/components/GameCard.tsx`**

```tsx
import type { PredictionOut } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function GameCard({ prediction }: { prediction: PredictionOut }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex justify-between text-sm text-gray-500">
        <span>{prediction.league}</span>
        <span>{new Date(prediction.date).toLocaleDateString()}</span>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className="font-semibold">{prediction.home_team.name}</span>
        <span className="text-lg font-bold">{Math.round(prediction.predicted_home_score)}</span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="font-semibold">{prediction.away_team.name}</span>
        <span className="text-lg font-bold">{Math.round(prediction.predicted_away_score)}</span>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded bg-gray-200">
        <div className="h-full bg-blue-500" style={{ width: pct(prediction.home_win_prob) }} />
      </div>
      <div className="mt-1 flex justify-between text-xs text-gray-600">
        <span>Home {pct(prediction.home_win_prob)}</span>
        {prediction.draw_prob !== null && <span>Draw {pct(prediction.draw_prob)}</span>}
        <span>Away {pct(prediction.away_win_prob)}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/GameCard.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/GameCard.tsx frontend/src/__tests__/GameCard.test.tsx
git commit -m "feat: GameCard component with win probability bar"
```

---

### Task 16: GameList page with loading/error states, and App wiring

**Files:**
- Create: `frontend/src/components/GameList.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Test: `frontend/src/__tests__/GameList.test.tsx`

**Interfaces:**
- Consumes: `fetchUpcomingPredictions` (Task 14), `GameCard` (Task 15).
- Produces: `GameList({ sport }: { sport: "nba" | "soccer" }): JSX.Element` handling loading, error, empty, and populated states.

- [ ] **Step 1: Write the failing test `frontend/src/__tests__/GameList.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GameList } from "../components/GameList";
import * as api from "../api";
import type { PredictionOut } from "../types";

describe("GameList", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading state before data arrives", () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockReturnValue(new Promise(() => {}));
    render(<GameList sport="nba" />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders a GameCard per prediction once loaded", async () => {
    const predictions: PredictionOut[] = [{
      game_id: 1, sport: "nba", league: "NBA", date: "2026-02-01T19:00:00Z",
      home_team: { id: 1, name: "Lakers", league: "NBA" },
      away_team: { id: 2, name: "Celtics", league: "NBA" },
      home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4,
      predicted_home_score: 105, predicted_away_score: 99,
    }];
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue(predictions);

    render(<GameList sport="nba" />);

    await waitFor(() => expect(screen.getByText("Lakers")).toBeInTheDocument());
  });

  it("shows an error message when the fetch fails", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockRejectedValue(new Error("boom"));

    render(<GameList sport="nba" />);

    await waitFor(() => expect(screen.getByText(/couldn't load predictions/i)).toBeInTheDocument());
  });

  it("shows an empty-state message when there are no upcoming games", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([]);

    render(<GameList sport="nba" />);

    await waitFor(() => expect(screen.getByText(/no upcoming games/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/GameList.test.tsx`
Expected: FAIL with module not found

- [ ] **Step 3: Write `frontend/src/components/GameList.tsx`**

```tsx
import { useEffect, useState } from "react";
import { fetchUpcomingPredictions } from "../api";
import type { PredictionOut } from "../types";
import { GameCard } from "./GameCard";

export function GameList({ sport }: { sport: "nba" | "soccer" }) {
  const [predictions, setPredictions] = useState<PredictionOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPredictions(null);
    setError(null);
    fetchUpcomingPredictions(sport)
      .then(setPredictions)
      .catch(() => setError("Couldn't load predictions. Please try again later."));
  }, [sport]);

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (predictions === null) {
    return <p className="text-gray-500">Loading predictions...</p>;
  }

  if (predictions.length === 0) {
    return <p className="text-gray-500">No upcoming games right now.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {predictions.map((prediction) => (
        <GameCard key={prediction.game_id} prediction={prediction} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/GameList.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Write `frontend/src/App.tsx`**

```tsx
import { useState } from "react";
import { GameList } from "./components/GameList";

export default function App() {
  const [sport, setSport] = useState<"nba" | "soccer">("nba");

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-bold">MatchIQ</h1>
      <div className="mt-4 flex gap-2">
        <button
          className={`rounded px-3 py-1 ${sport === "nba" ? "bg-blue-600 text-white" : "bg-gray-100"}`}
          onClick={() => setSport("nba")}
        >
          NBA
        </button>
        <button
          className={`rounded px-3 py-1 ${sport === "soccer" ? "bg-blue-600 text-white" : "bg-gray-100"}`}
          onClick={() => setSport("soccer")}
        >
          Soccer
        </button>
      </div>
      <div className="mt-6">
        <GameList sport={sport} />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Write `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 7: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS (all tests)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/GameList.tsx frontend/src/App.tsx frontend/src/main.tsx frontend/src/__tests__/GameList.test.tsx
git commit -m "feat: GameList page with loading/error/empty states and sport toggle"
```

---

### Task 17: Deployment configuration (Railway + Vercel)

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/railway.json`
- Create: `frontend/vercel.json`
- Create: `.gitignore`

**Interfaces:**
- No code interfaces — this task wires the already-tested backend and frontend to hosting, matching the existing Atlas/ForgeAI deployment pattern.

- [ ] **Step 1: Write `.gitignore`**

```
__pycache__/
*.pyc
.env
matchiq.db
artifacts/
node_modules/
dist/
.vite/
```

- [ ] **Step 2: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Write `backend/railway.json`**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": { "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port 8000" }
}
```

- [ ] **Step 4: Write `frontend/vercel.json`**

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore backend/Dockerfile backend/railway.json frontend/vercel.json
git commit -m "chore: deployment config for Railway (backend) and Vercel (frontend)"
```

- [ ] **Step 6: Manual deployment (not automatable from this plan)**

Provision a Railway project (Postgres + backend service pointed at `backend/`) and a Vercel project pointed at `frontend/`, matching the existing Atlas/ForgeAI setup. Set `DATABASE_URL`, `NBA_API_KEY`, `FOOTBALL_DATA_API_KEY` on Railway, and `VITE_API_BASE_URL` (pointing at the Railway backend URL) on Vercel. Re-run the backfill (Task 6, Step 6) and training (Task 10, Step 6) against the production database before considering Phase 1 complete.

---

## Definition of Done for Phase 1

- All backend and frontend automated tests pass (`pytest tests/ -v` and `npx vitest run`).
- Real historical data has been backfilled for NBA and all 5 soccer leagues (Task 6, Step 6).
- Both sports' models beat the naive home-favorite baseline on held-out data, or the gap is explicitly documented if one sport doesn't yet (Task 10, Step 6).
- `/predictions/upcoming`, `/predictions/{game_id}`, `/teams/{team_id}` are live and return real predictions for real upcoming fixtures.
- The dashboard is deployed and shows real predictions for both NBA and soccer without errors in the browser console.
