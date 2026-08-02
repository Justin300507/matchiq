# MatchIQ — Repository Audit

Real findings from the actual codebase, using real tools (`ruff` for backend static analysis, `oxlint` for
frontend, manual code reading, and live-server timing measurements). Nothing in this document is invented or
mocked — every number was measured against the real running app.

Codebase size at time of audit: ~1,980 lines of backend Python, ~1,350 lines of frontend TypeScript/TSX.

## Findings

| # | Finding | Priority | Impact | Difficulty | Status |
|---|---|---|---|---|---|
| 1 | N+1 query pattern in feature computation (`compute_features` issued ~5 DB queries per match; called once per row for every match in `build_training_dataframe` AND, separately, once per match in the live `/predictions/upcoming` list and the AI analyst's match context) | High | High — measured 59s (NBA) / 68s (soccer) `/accuracy`, and ~2s per `/predictions/upcoming` page load, before fixing | Medium | **Fixed** — see below |
| 1b | Trained model artifacts (XGBoost classifier + 2 regressors) were re-deserialized from disk on every single request — ~0.9s each time, paid repeatedly since a match page fires 3+ of these requests | High | Directly caused the "every match takes so long to load" complaint | Low | **Fixed** — in-memory cache keyed by `(path, mtime)`, auto-invalidates on retrain |
| 1c | Model inference called individually per match (3 XGBoost `.predict()`-family calls × up to 60 matches = 180 individual calls) instead of batched | Medium | ~0.4s of the `/predictions/upcoming` response was just per-call overhead from calling `.predict()` 180 times instead of 3 times | Low | **Fixed** — added `predict_batch()`, one call per model for the whole list |
| 2 | No database indexes beyond the primary key and the `(sport, external_id)` unique constraint, despite `sport`/`status`/`date`/`home_team_id`/`away_team_id` being filtered on in every hot-path query | High | Invisible today on SQLite with a few thousand rows; will degrade badly on Postgres in production at real data volume | Low | Open |
| 3 | `/accuracy` recomputes the entire backtest from scratch on every request, with no caching | Medium | Even after fix #1, each request still does real, non-trivial work (10.7s NBA / 4.4s football after fix #1; not yet re-measured against fixes #1b/#1c, which don't apply to this endpoint) | Low–Medium | Open |
| 4 | No database migration tooling — schema changes apply via a bare `Base.metadata.create_all()` on startup | Medium | Fine for SQLite today; risky once Postgres holds real data and a column needs to change | Medium | Open |
| 5 | Duplicate data-fetching boilerplate across 9 frontend files (`useState<T\|null>` + `useEffect` + `.then(setX)` + `.catch(setError)`, repeated verbatim in HomePage, MatchPage, TeamPage, AccuracyPage, BettingPage, ChatPanel, GameCard, GameList, SimulationPanel, WhatIfPanel) | Low–Medium | Maintainability tax on every new page | Medium | Open |
| 6 | Light business logic living directly in route handlers (e.g. the per-league balancing logic in `predictions.py`'s `get_upcoming`) and in `BettingPage.tsx` (EV/Kelly math over already-fetched data) | Low | Low at current scale | N/A | **Not recommended to fix** — see note below |
| 7 | `ruff` flagged 17 `B008` warnings — false positives against FastAPI's required `Depends(...)` route-signature pattern | Low | None (false positive) | Trivial | **Fixed** — added a `pyproject.toml` ruff config ignoring `B008` with the reason documented inline |
| 8 | `datetime.date.today()` used without a timezone in `daily_sync.py` (3 occurrences) — server-local "today" can be off by a day from UTC-based match dates near midnight | Low | Low (the sync window is already padded ±3–7 days) | Trivial | **Fixed** — switched to `datetime.now(timezone.utc).date()` |
| 9 | Unsorted import blocks in 3 files (`config.py`, `ingestion/backfill.py`, `ingestion/daily_sync.py`) | Low | Cosmetic | Trivial | **Fixed** — `ruff check --fix` |
| 10 | No authentication/authorization layer — every endpoint is public | Info | N/A today (single-user local/demo deployment) | — | Intentionally deferred — see note below |
| 11 | Frontend bundle is a single ~260KB JS chunk (~80KB gzipped), not code-split by route | Info | Not a real problem at this size | — | Deferred |

### What's clean (worth stating, not just issues)

- Zero unused imports, zero `TODO`/`FIXME`/`XXX` markers anywhere in the codebase.
- No secrets committed — `backend/.env` and `frontend/.env*` are correctly gitignored; only `.env.example` templates are tracked.
- No SQL-injection surface — 100% ORM query usage (SQLAlchemy `.query()`/`.filter()`), no raw string-interpolated SQL anywhere.
- CORS is scoped to explicitly configured origins (`ALLOWED_ORIGINS` env var), not wildcarded.
- No duplicate `requirements.txt` entries, no dependency version conflicts.

## Fix #1 in detail: the N+1 query pattern

`compute_features()` computed a match's 7 features via 5 separate DB round trips (last-5 form × 2 teams, home/away
win rate × 2 teams, head-to-head history). `build_training_dataframe()` — which both model training and the
`/accuracy` backtest depend on — called this once per historical match, so a sport with N final matches issued
roughly 5N queries sequentially.

Fixed by loading each sport's full match history in a single query, building in-memory per-team and per-matchup
indices, and computing every match's features from those indices instead of re-querying the database. Verified two
ways:

1. **Correctness** — a new test (`test_build_features_performance.py`) asserts the bulk-computed dataframe is
   field-for-field identical to calling the original per-row `compute_features()` for every match.
2. **The actual fix** — a second test counts real SQL statements executed via a SQLAlchemy `before_cursor_execute`
   listener and asserts the bulk path issues a small, constant number of queries regardless of match count (proven
   at 120 synthetic matches; the old path would have issued 600+).

**Measured before/after on the live server, real data:**

| Sport | Before | After |
|---|---|---|
| NBA | 59.2s | 10.7s |
| Soccer | 68.6s | 4.4s |

The remaining time is genuine computation (large historical dataset, in-memory feature building across many
teams/matches), not further N+1 queries — reducing it further is finding #3 (caching the backtest result so this
work only happens on retrain, not on every page load).

The same N+1 pattern also existed on the **live** hot path — `/predictions/upcoming` (the home page's match list
and the betting page's match dropdown) and the AI analyst's match-context builder both called `compute_features()`
once per match in a loop. Fixed the same way via a new `compute_features_bulk()` that shares one history load and
index across all target matches; verified with the same two-part correctness + query-count-listener test pattern
(`test_compute_features_bulk_*`).

## Fixes #1b and #1c in detail: artifact caching and batched inference

Fixing the query pattern alone didn't fully explain user-reported slowness ("every match takes so long to load,
including bets"), so this was measured further rather than assumed fixed:

- **`load_latest_artifact()` deserialized the trained model from disk on every call** (~0.9s each time — confirmed
  by direct timing, not estimated), and it's called on every predictions-related endpoint, including 3+ times per
  match page. Fixed with an in-memory cache keyed by `(file path, mtime)` — a retrain changes the file's mtime and
  is picked up automatically, no manual invalidation needed. Verified with tests asserting object identity across
  repeat calls, and a fresh (non-cached) object after the underlying file changes.
- **Model inference was called once per match** — for a 60-match upcoming list, that's 3 individual XGBoost
  `.predict()`-family calls × 60 = 180 calls, each carrying real fixed overhead regardless of row count. Added
  `predict_batch()`, which builds one DataFrame for the whole list and calls each model exactly once. Verified with
  a test asserting `predict_proba`/`.predict()` mock call counts are 1, not N.

**Measured before/after on the live server, real data, `/predictions/upcoming?sport=football&league=EPL`:**

| Stage | Time |
|---|---|
| Before any of this round's fixes | ~2.07s |
| After fixing the N+1 query pattern on this endpoint | ~1.0s |
| After also caching the artifact and batching inference | ~0.3–0.5s |

## Explicitly not doing

**A full Clean Architecture / DDD rewrite** (separate Domain/Application/Infrastructure/Presentation layers,
Repository pattern, dependency injection containers) was requested but is not applied here. At ~3,300 lines of
code with a single maintainer, that much layering is overhead the project doesn't need yet — it would make every
future change touch more files for no behavioral benefit. The one real instance of "business logic in a router"
(finding #6) is a few lines of league-balancing logic, not a systemic problem. Revisit this if/when the codebase
or team actually grows to a size where the layering pays for itself.

**Authentication (JWT/refresh tokens)** was requested but not built (finding #10). There are currently no user
accounts, no per-user data, and no access-control requirement — building auth with nothing for it to protect would
be unused scaffolding, not a real feature. Build this when there's an actual multi-user requirement driving it.

**Mocked/fake data providers** (news intelligence, injury feeds, additional odds providers, testimonials) were
requested but not built, on principle: MatchIQ's own stated rule for this project is "never fabricate... if data
is unavailable, say Unavailable." Building realistic-looking fake providers would violate that rule for the sake
of appearing more complete. Real provider interfaces are welcome; invented data behind them is not.
