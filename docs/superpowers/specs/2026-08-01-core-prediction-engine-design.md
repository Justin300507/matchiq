# MatchIQ — Phase 1: Core Prediction Engine

**Date:** 2026-08-01
**Status:** Approved for planning

## Context

MatchIQ is a new flagship portfolio project: an AI sports analytics platform (not a betting app) that predicts match outcomes and explains why. The original pitch bundled ~8 independent subsystems (live prediction updates, explainable AI, player performance AI, news/sentiment analysis, Monte Carlo simulation, public API, full dashboard, MLOps). That's too large for one spec, so the project is decomposed into phases. This document specs **Phase 1 only**.

Later phases (not specced here, will get their own design docs): live in-play prediction updates, explainable AI breakdowns, player performance/fantasy AI, news & sentiment analysis, Monte Carlo simulation engine, public API + Swagger polish, Redis/Kafka, Kubernetes.

## Sport scope

**NBA** and **soccer's top 5 European leagues** (EPL, La Liga, Serie A, Bundesliga, Ligue 1).

Rationale: research shows tennis and NBA are the most predictable sports (favorites win ~65%+ of the time), while soccer is the least predictable major sport. NBA was chosen over tennis because the target feature set (team comparisons, injury risk, fantasy recommendations, player performance AI in later phases) assumes rosters and teams, which tennis doesn't have. Soccer's top 5 leagues were added per explicit user request alongside NBA, despite lower predictability — the two domains together give the platform broader appeal (US audience via NBA, global audience via soccer) and force the pipeline/model architecture to be sport-agnostic from day one instead of NBA-specific.

## Phase 1 goal

A working, deployed core: real historical + upcoming match data → trained ML models → REST API → minimal dashboard showing live predictions. This is the spine every later phase (live updates, explainability, simulation) attaches to.

## Architecture

```
[External APIs] -> [Ingestion jobs] -> [PostgreSQL] -> [Feature pipeline] -> [Model training (offline)]
                                              |                                        |
                                              v                                        v
                                     [FastAPI backend] <----------------------- [Model artifacts]
                                              |
                                              v
                                   [React dashboard (Vercel)]
```

### Components

**1. Data pipeline**
- NBA: `balldontlie.io` free API — teams, games, box scores. No key required for basic tier.
- Soccer: `football-data.org` free tier — covers all 5 target leagues, fixtures, results, standings.
- One-time backfill script pulls 3-5 seasons of historical results per sport for training data.
- A scheduled job (cron, not a message queue — deferred to a later phase) pulls new results and upcoming fixtures daily.
- Raw responses land in Postgres in sport-specific tables; a normalization step maps both sports into a shared `matches` schema (home_team, away_team, date, league/conference, final_score, status) so the API and feature pipeline don't need to special-case sport everywhere.

**2. Feature engineering & models**
- Time-based train/test split (train on past seasons, test on most recent season) — never random split, to avoid leakage from future data.
- Shared feature families computed per sport: rolling team form (last N games), home/away split performance, head-to-head history, rest days between games.
- Sport-specific model pair, same architecture pattern for both:
  - Classifier (XGBoost) for outcome: NBA is binary (win/loss), soccer is 3-class (win/draw/loss).
  - Regressor (XGBoost) for score prediction: NBA final score margin/points, soccer goals per side.
- Baseline comparison: every model is evaluated against a naive baseline (always pick home team) using accuracy, log-loss, and Brier score. The spec's definition of "done" for modeling includes beating this baseline — a model that doesn't beat picking the home team isn't shipped.
- Model artifacts are versioned files (joblib) tagged with training date and metrics; the API loads the latest artifact per sport at startup.

**3. Backend API (FastAPI)**
- `GET /predictions/upcoming?sport=nba|soccer` — upcoming games with outcome probabilities + predicted score.
- `GET /predictions/{game_id}` — single game detail.
- `GET /teams/{team_id}` — basic team info + recent form.
- Auto-generated Swagger docs at `/docs` (free with FastAPI, no extra work).
- No auth in Phase 1 — public read-only endpoints.

**4. Dashboard (React + TypeScript + Tailwind)**
- Single page: upcoming games grouped by sport/league.
- Each game card: teams, win probability bar (and draw for soccer), predicted score.
- No user accounts, no historical prediction log, no team pages — those are later-phase dashboard work.

## Data flow

1. Backfill script populates historical matches → training data for models.
2. Daily job pulls new results (updates historical data) and upcoming fixtures.
3. Training pipeline runs offline (manually triggered in Phase 1, not automated retraining) to produce model artifacts.
4. API loads current artifacts, serves predictions computed on-demand from the latest features for upcoming fixtures.
5. Dashboard polls the API on page load (no live/websocket updates — that's Phase 2).

## Error handling

- Ingestion: retry on API rate-limit/transient errors with backoff; skip and log a game on persistent bad data rather than failing the whole batch.
- API: 404 for unknown game/team IDs; 503 if a sport's model artifact failed to load at startup.
- Dashboard: visible loading and error states on fetch failure, no silent blank screens.

## Testing

- Pytest unit tests for feature engineering transforms and the sport-normalization mapping.
- Model evaluation script asserting each model beats the naive-home-favorite baseline on held-out data (this is a checked requirement, not just a report).
- API integration tests (pytest + httpx) covering the three endpoints, including 404/503 paths.

## Tech stack (Phase 1)

- Backend: FastAPI, Python
- ML: XGBoost, pandas, scikit-learn (LightGBM/PyTorch deferred — not needed until later phases need time-series/deep models)
- DB: PostgreSQL
- Frontend: React + TypeScript + Tailwind
- Deployment: Backend on Railway, frontend on Vercel (matches the existing Atlas/ForgeAI deployment pattern)

Explicitly deferred: Redis, Kafka/RabbitMQ, Kubernetes, Docker orchestration beyond local dev, live/websocket updates, explainable AI, player performance AI, news/sentiment analysis, Monte Carlo simulation, public-facing API product polish.

## Out of scope for Phase 1 (future phases)

- Live prediction updates during matches
- Explainable AI (feature-contribution breakdowns)
- Player performance AI / fantasy recommendations
- News + social sentiment analysis
- Monte Carlo simulation engine
- Public API product (rate limiting, API keys, published docs)
- Mobile-specific frontend polish, team pages, prediction history
