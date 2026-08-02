# AI Sports Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MatchIQ's single-shot, per-league `/chat` widget with a floating, multi-turn AI copilot (`POST /chat/copilot`) that uses OpenAI tool-calling to ground every answer in MatchIQ's real data (predictions, team profiles, SHAP explanations, live Polymarket odds) across any sport/league in one conversation.

**Architecture:** A new `backend/app/copilot/` package holds four read-only tool functions (each wrapping existing prediction/explanation/team-profile/odds logic via new team/match name-resolution helpers) and a tool-calling loop (`run_copilot_conversation`) that repeatedly calls OpenAI, executes any requested tools, and feeds results back — capped at 5 rounds. `POST /chat/copilot` accepts the full conversation (`messages: [{role, content}]`); the frontend's local React state is the only place conversation history lives. A new `CopilotWidget` floating bubble, mounted once at the app root, replaces the old embedded `ChatPanel`.

**Tech Stack:** FastAPI, SQLAlchemy, OpenAI Python SDK (`openai==2.43.0`, already installed) using `chat.completions.create(tools=..., tool_choice="auto")`; React + TypeScript + Vite + Tailwind on the frontend; pytest / vitest for testing.

## Global Constraints

- Model: reuse `gpt-4o-mini` (same as today's analyst) — no model change.
- Tool-call rounds capped at 5 per request (bounds worst-case OpenAI cost per HTTP request).
- Reuse the existing `rate_limit_chat` dependency (20 req/min/IP) on the new endpoint — do not create a second limiter.
- Never fabricate data: any tool that can't resolve a team/match returns a "not found" string *to the model*, never an HTTP error; if a question needs data with no tool (injuries, weather, lineups, news), the system prompt requires the model to say MatchIQ doesn't have it.
- No server-side conversation storage — conversation state lives only in the frontend's local React state for this build.
- Out of scope for this plan (per the approved spec): "biggest probability shifts today" and "why did odds change" — both need historical snapshotting that doesn't exist yet.

---

## Task 1: Shared name-matching + team/match lookup helpers

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/name_matching.py`
- Modify: `backend/app/integrations/polymarket_odds.py:24-26` (remove private `_names_match`, import shared one) and its call sites at lines ~44-46 and ~109-111
- Create: `backend/app/copilot/__init__.py`
- Create: `backend/app/copilot/lookups.py`
- Test: `backend/tests/test_name_matching.py`
- Test: `backend/tests/test_copilot_lookups.py`

**Interfaces:**
- Produces: `names_match(name: str, candidate: str) -> bool` in `app.utils.name_matching`
- Produces: `find_team_by_name(db: Session, team_name: str, sport: str) -> Team | None` in `app.copilot.lookups`
- Produces: `find_upcoming_match(db: Session, home_team: str, away_team: str, sport: str) -> Match | None` in `app.copilot.lookups`

- [ ] **Step 1: Write the failing test for `names_match`**

Create `backend/tests/test_name_matching.py`:

```python
from app.utils.name_matching import names_match


def test_matches_when_one_name_is_a_substring_of_the_other():
    assert names_match("Arsenal", "Arsenal FC") is True
    assert names_match("Arsenal FC", "Arsenal") is True


def test_matches_case_insensitively():
    assert names_match("arsenal", "ARSENAL FC") is True


def test_does_not_match_unrelated_names():
    assert names_match("Arsenal", "Chelsea") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_name_matching.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.utils'`

- [ ] **Step 3: Create the package and implementation**

Create `backend/app/utils/__init__.py` (empty file).

Create `backend/app/utils/name_matching.py`:

```python
def names_match(name: str, candidate: str) -> bool:
    name, candidate = name.lower(), candidate.lower()
    return name in candidate or candidate in name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_name_matching.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Point `polymarket_odds.py` at the shared helper**

In `backend/app/integrations/polymarket_odds.py`, remove the private function (lines 24-26):

```python
def _names_match(name: str, candidate: str) -> bool:
    name, candidate = name.lower(), candidate.lower()
    return name in candidate or candidate in name
```

Add an import near the top of the file (after the existing imports):

```python
from app.utils.name_matching import names_match
```

Replace every call site of `_names_match(` with `names_match(` in that file (there are 3: inside `_event_matches_teams`, twice).

- [ ] **Step 6: Confirm the existing Polymarket tests still pass**

Run: `cd backend && pytest tests/test_polymarket_odds.py tests/test_polymarket_client.py -v`
Expected: PASS (all previously-passing tests still pass — behavior is unchanged, only the function moved)

- [ ] **Step 7: Write the failing tests for the lookup helpers**

Create `backend/tests/test_copilot_lookups.py`:

```python
from datetime import datetime, timedelta

from app.copilot.lookups import find_team_by_name, find_upcoming_match
from app.db import Base, get_engine, get_session_factory
from app.models_db import Match, Team


def _make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def test_find_team_by_name_matches_a_known_team():
    db = _make_db()
    db.add(Team(external_id="1", sport="nba", league="NBA", name="Los Angeles Lakers"))
    db.commit()

    team = find_team_by_name(db, "Lakers", "nba")

    assert team is not None
    assert team.name == "Los Angeles Lakers"


def test_find_team_by_name_returns_none_when_no_team_matches():
    db = _make_db()
    db.add(Team(external_id="1", sport="nba", league="NBA", name="Los Angeles Lakers"))
    db.commit()

    assert find_team_by_name(db, "Celtics", "nba") is None


def test_find_team_by_name_is_scoped_to_sport():
    db = _make_db()
    db.add(Team(external_id="1", sport="football", league="EPL", name="Arsenal"))
    db.commit()

    assert find_team_by_name(db, "Arsenal", "nba") is None


def _add_upcoming_match(db, home_name="Lakers", away_name="Celtics", sport="nba"):
    home = Team(external_id="h", sport=sport, league="NBA", name=home_name)
    away = Team(external_id="a", sport=sport, league="NBA", name=away_name)
    db.add_all([home, away])
    db.commit()
    match = Match(
        external_id="m1", sport=sport, league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(match)
    db.commit()
    return match


def test_find_upcoming_match_matches_regardless_of_home_away_order():
    db = _make_db()
    _add_upcoming_match(db)

    match = find_upcoming_match(db, "Celtics", "Lakers", "nba")

    assert match is not None
    assert match.home_team.name == "Lakers"


def test_find_upcoming_match_returns_none_when_no_match_found():
    db = _make_db()
    _add_upcoming_match(db)

    assert find_upcoming_match(db, "Warriors", "Nets", "nba") is None
```

- [ ] **Step 8: Run test to verify it fails**

Run: `cd backend && pytest tests/test_copilot_lookups.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.copilot'`

- [ ] **Step 9: Implement the lookup helpers**

Create `backend/app/copilot/__init__.py` (empty file).

Create `backend/app/copilot/lookups.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models_db import Match, Team
from app.utils.name_matching import names_match


def find_team_by_name(db: Session, team_name: str, sport: str) -> Team | None:
    teams = db.query(Team).filter(Team.sport == sport).all()
    for team in teams:
        if names_match(team_name, team.name):
            return team
    return None


def find_upcoming_match(db: Session, home_team: str, away_team: str, sport: str) -> Match | None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "scheduled", Match.date >= now)
        .order_by(Match.date.asc())
        .all()
    )
    for match in matches:
        home_name, away_name = match.home_team.name, match.away_team.name
        if (names_match(home_team, home_name) and names_match(away_team, away_name)) or (
            names_match(home_team, away_name) and names_match(away_team, home_name)
        ):
            return match
    return None
```

- [ ] **Step 10: Run test to verify it passes**

Run: `cd backend && pytest tests/test_copilot_lookups.py -v`
Expected: PASS (5 passed)

- [ ] **Step 11: Commit**

```bash
git add backend/app/utils backend/app/copilot backend/app/integrations/polymarket_odds.py backend/tests/test_name_matching.py backend/tests/test_copilot_lookups.py
git commit -m "feat: add shared team/match name-matching helpers for the copilot"
```

---

## Task 2: Copilot tool functions

**Files:**
- Create: `backend/app/copilot/tools.py`
- Test: `backend/tests/test_copilot_tools.py`
- Modify: `backend/app/features/build_features.py:106` and `:180` (update stale "AI analyst" wording in comments)

**Interfaces:**
- Consumes: `find_team_by_name`, `find_upcoming_match` from `app.copilot.lookups` (Task 1); `compute_features_bulk(db, sport, matches) -> dict[int, MatchFeatures]` from `app.features.build_features`; `load_latest_artifact(sport, artifact_dir) -> dict | None`, `predict_batch(artifact, features_list) -> list[Prediction]`, `predict_match(artifact, features) -> Prediction` from `app.ml.predict`; `explain_prediction(artifact, features) -> Explanation` from `app.ml.explain`; `compute_team_profile(db, team) -> TeamProfile` from `app.ml.team_profile`; `find_match_odds(home_team, away_team, match_date) -> MarketOdds | None` from `app.integrations.polymarket_odds`
- Produces: `get_upcoming_predictions(db, artifact_dir, **kwargs) -> str`, `get_team_profile(db, artifact_dir, **kwargs) -> str`, `get_match_explanation(db, artifact_dir, **kwargs) -> str`, `get_market_odds(db, artifact_dir, **kwargs) -> str`, `TOOL_SCHEMAS: list[dict]`, `TOOL_FUNCTIONS: dict[str, Callable]` — all in `app.copilot.tools` (used by Task 3)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_copilot_tools.py`:

```python
from datetime import datetime, timedelta
from unittest.mock import patch

from app.copilot.tools import (
    get_market_odds,
    get_match_explanation,
    get_team_profile,
    get_upcoming_predictions,
)
from app.db import Base, get_engine, get_session_factory
from app.integrations.polymarket_odds import MarketOdds
from app.ml.explain import Explanation, ExplanationFactor
from app.ml.predict import Prediction
from app.models_db import Match, Team


def _make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def _add_upcoming_match(db, home_name="Lakers", away_name="Celtics", sport="nba"):
    home = Team(external_id="h", sport=sport, league="NBA", name=home_name)
    away = Team(external_id="a", sport=sport, league="NBA", name=away_name)
    db.add_all([home, away])
    db.commit()
    match = Match(
        external_id="m1", sport=sport, league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(match)
    db.commit()
    return match


@patch("app.copilot.tools.predict_batch")
@patch("app.copilot.tools.load_latest_artifact")
def test_get_upcoming_predictions_lists_real_matches(mock_load, mock_predict):
    db = _make_db()
    _add_upcoming_match(db)
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = [Prediction(0.65, None, 0.35, 105.0, 99.0, "High")]

    result = get_upcoming_predictions(db, "/tmp/artifacts", sport="nba")

    assert "Lakers vs Celtics" in result
    assert "home_win_prob=0.65" in result


@patch("app.copilot.tools.load_latest_artifact")
def test_get_upcoming_predictions_reports_no_model(mock_load):
    db = _make_db()
    mock_load.return_value = None

    result = get_upcoming_predictions(db, "/tmp/artifacts", sport="nba")

    assert "No trained prediction model" in result


def test_get_upcoming_predictions_reports_no_matches():
    db = _make_db()

    result = get_upcoming_predictions(db, "/tmp/artifacts", sport="nba")

    assert "no upcoming matches" in result.lower()


def test_get_team_profile_returns_real_stats():
    db = _make_db()
    db.add(Team(external_id="1", sport="nba", league="NBA", name="Los Angeles Lakers"))
    db.commit()

    result = get_team_profile(db, "/tmp/artifacts", team_name="Lakers", sport="nba")

    assert "Los Angeles Lakers" in result
    assert "Elo rating" in result


def test_get_team_profile_reports_team_not_found():
    db = _make_db()

    result = get_team_profile(db, "/tmp/artifacts", team_name="Nonexistent Team", sport="nba")

    assert "No team found" in result


@patch("app.copilot.tools.explain_prediction")
@patch("app.copilot.tools.predict_match")
@patch("app.copilot.tools.load_latest_artifact")
def test_get_match_explanation_returns_factors(mock_load, mock_predict, mock_explain):
    db = _make_db()
    _add_upcoming_match(db)
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0, "High")
    mock_explain.return_value = Explanation(
        factors=[ExplanationFactor(
            name="home_form_last5", label="Home team's recent form", relative_influence_pct=42.0,
        )],
        model_confidence="High",
    )

    result = get_match_explanation(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "Lakers vs Celtics" in result
    assert "Home team's recent form" in result
    assert "42.0" in result


def test_get_match_explanation_reports_match_not_found():
    db = _make_db()

    result = get_match_explanation(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "No upcoming match found" in result


@patch("app.copilot.tools.find_match_odds")
def test_get_market_odds_returns_real_odds(mock_find):
    db = _make_db()
    _add_upcoming_match(db)
    mock_find.return_value = MarketOdds(
        source="Polymarket", event_title="Lakers vs. Celtics",
        event_url="https://polymarket.com/event/lakers-vs-celtics",
        home_decimal_odds=2.5, draw_decimal_odds=None, away_decimal_odds=1.8,
    )

    result = get_market_odds(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "2.5" in result
    assert "polymarket.com" in result


@patch("app.copilot.tools.find_match_odds")
def test_get_market_odds_reports_no_market(mock_find):
    db = _make_db()
    _add_upcoming_match(db)
    mock_find.return_value = None

    result = get_market_odds(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "No live Polymarket market" in result


def test_get_market_odds_reports_match_not_found():
    db = _make_db()

    result = get_market_odds(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "No upcoming match found" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_copilot_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.copilot.tools'`

- [ ] **Step 3: Implement the tools**

Create `backend/app/copilot/tools.py`:

```python
from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from app.copilot.lookups import find_team_by_name, find_upcoming_match
from app.features.build_features import compute_features_bulk
from app.integrations.polymarket_odds import find_match_odds
from app.ml.explain import explain_prediction
from app.ml.predict import load_latest_artifact, predict_batch, predict_match
from app.ml.team_profile import compute_team_profile
from app.models_db import Match

_UPCOMING_LIMIT = 25


# Every tool below takes (db, artifact_dir, **kwargs) even when it doesn't
# need artifact_dir, so the engine's dispatch loop can call any tool the
# same way without per-tool special-casing.


def get_upcoming_predictions(db: Session, artifact_dir, *, sport: str, league: str | None = None) -> str:
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        return f"No trained prediction model is currently available for sport={sport}."

    query = db.query(Match).filter(
        Match.sport == sport,
        Match.status == "scheduled",
        Match.date >= datetime.now(timezone.utc).replace(tzinfo=None),
    )
    if league is not None:
        query = query.filter(Match.league == league)
    matches = query.order_by(Match.date.asc()).limit(_UPCOMING_LIMIT).all()
    if not matches:
        scope = f"sport={sport}" + (f", league={league}" if league else "")
        return f"There are no upcoming matches currently loaded for {scope}."

    features_by_id = compute_features_bulk(db, sport, matches)
    predictions = predict_batch(artifact, [features_by_id[match.id] for match in matches])
    lines = []
    for match, prediction in zip(matches, predictions):
        draw_part = f", draw_win_prob={prediction.draw_prob:.2f}" if prediction.draw_prob is not None else ""
        lines.append(
            f"- {match.date.isoformat()} | {match.league} | "
            f"{match.home_team.name} vs {match.away_team.name} | "
            f"home_win_prob={prediction.home_win_prob:.2f}{draw_part}, "
            f"away_win_prob={prediction.away_win_prob:.2f} | "
            f"predicted_score={prediction.predicted_home_score:.1f}-{prediction.predicted_away_score:.1f} | "
            f"confidence={prediction.confidence}"
        )
    return "\n".join(lines)


def get_team_profile(db: Session, artifact_dir, *, team_name: str, sport: str) -> str:
    team = find_team_by_name(db, team_name, sport)
    if team is None:
        return f"No team found matching '{team_name}' in sport={sport}."

    profile = compute_team_profile(db, team)
    return (
        f"{profile.team_name} ({profile.league}) — Elo rating: {profile.elo_rating:.0f}. "
        f"Record: {profile.wins}W-{profile.draws}D-{profile.losses}L over {profile.matches_played} matches. "
        f"Last 5 form: {profile.last5_form or 'n/a'}. "
        f"Goals for/against per match: {profile.goals_for_avg:.2f}/{profile.goals_against_avg:.2f}. "
        f"Home win rate: {profile.home_win_rate:.0%}, away win rate: {profile.away_win_rate:.0%}."
    )


def get_match_explanation(db: Session, artifact_dir, *, home_team: str, away_team: str, sport: str) -> str:
    match = find_upcoming_match(db, home_team, away_team, sport)
    if match is None:
        return f"No upcoming match found between '{home_team}' and '{away_team}' in sport={sport}."

    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        return f"No trained prediction model is currently available for sport={sport}."

    features = compute_features_bulk(db, sport, [match])[match.id]
    prediction = predict_match(artifact, features)
    explanation = explain_prediction(artifact, features)
    factor_lines = "\n".join(
        f"  - {factor.label}: {factor.relative_influence_pct:+.1f}% relative influence toward the home side"
        for factor in explanation.factors
    )
    draw_part = f", draw_prob={prediction.draw_prob:.2f}" if prediction.draw_prob is not None else ""
    return (
        f"{match.home_team.name} vs {match.away_team.name} ({match.league}, {match.date.isoformat()}):\n"
        f"home_win_prob={prediction.home_win_prob:.2f}{draw_part}, "
        f"away_win_prob={prediction.away_win_prob:.2f}, confidence={prediction.confidence}\n"
        f"Factors behind the prediction:\n{factor_lines}"
    )


def get_market_odds(db: Session, artifact_dir, *, home_team: str, away_team: str, sport: str) -> str:
    match = find_upcoming_match(db, home_team, away_team, sport)
    if match is None:
        return f"No upcoming match found between '{home_team}' and '{away_team}' in sport={sport}."

    try:
        odds = find_match_odds(match.home_team.name, match.away_team.name, match.date)
    except requests.exceptions.RequestException:
        return "Polymarket is temporarily unreachable -- no odds available right now."

    if odds is None:
        return f"No live Polymarket market found for {match.home_team.name} vs {match.away_team.name}."

    draw_part = f", draw_decimal_odds={odds.draw_decimal_odds}" if odds.draw_decimal_odds is not None else ""
    return (
        f"Polymarket odds for {match.home_team.name} vs {match.away_team.name}: "
        f"home_decimal_odds={odds.home_decimal_odds}{draw_part}, away_decimal_odds={odds.away_decimal_odds}. "
        f"Source: {odds.event_url}"
    )


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_predictions",
            "description": "Get MatchIQ's real upcoming-match predictions for a sport, optionally filtered to one league.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                    "league": {
                        "type": "string",
                        "description": "Optional league filter, e.g. 'EPL', 'La Liga'. Omit for all leagues in the sport.",
                    },
                },
                "required": ["sport"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_profile",
            "description": "Get a team's real record, Elo rating, recent form, and goal stats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {"type": "string"},
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                },
                "required": ["team_name", "sport"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_match_explanation",
            "description": (
                "Get the real model prediction and the factors behind it for a specific upcoming "
                "match between two teams."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "home_team": {"type": "string"},
                    "away_team": {"type": "string"},
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                },
                "required": ["home_team", "away_team", "sport"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_odds",
            "description": (
                "Get live Polymarket odds for a specific upcoming match between two teams, if a "
                "market exists for it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "home_team": {"type": "string"},
                    "away_team": {"type": "string"},
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                },
                "required": ["home_team", "away_team", "sport"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_upcoming_predictions": get_upcoming_predictions,
    "get_team_profile": get_team_profile,
    "get_match_explanation": get_match_explanation,
    "get_market_odds": get_market_odds,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_copilot_tools.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Update the stale "AI analyst" wording in `build_features.py`**

In `backend/app/features/build_features.py:106`, change:

```python
    list, the AI analyst's match context, training), use
```

to:

```python
    list, the AI copilot's tool calls, training), use
```

At `backend/app/features/build_features.py:180`, change:

```python
    list, or the AI analyst's match context) against one shared history load,
```

to:

```python
    list, or the AI copilot's tool calls) against one shared history load,
```

- [ ] **Step 6: Run the full backend suite to confirm no regressions**

Run: `cd backend && pytest -q`
Expected: all tests pass (previous count + 11 new)

- [ ] **Step 7: Commit**

```bash
git add backend/app/copilot/tools.py backend/tests/test_copilot_tools.py backend/app/features/build_features.py
git commit -m "feat: add copilot tool functions (predictions, team profile, explanation, odds)"
```

---

## Task 3: Tool-calling conversation engine

**Files:**
- Create: `backend/app/copilot/engine.py`
- Test: `backend/tests/test_copilot_engine.py`

**Interfaces:**
- Consumes: `TOOL_SCHEMAS`, `TOOL_FUNCTIONS` from `app.copilot.tools` (Task 2)
- Produces: `run_copilot_conversation(db: Session, artifact_dir, api_key: str, messages: list[dict]) -> str` in `app.copilot.engine` (used by Task 4)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_copilot_engine.py`:

```python
import json
from types import SimpleNamespace
from unittest.mock import patch

from app.copilot.engine import run_copilot_conversation


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@patch("app.copilot.engine.TOOL_FUNCTIONS", {"get_team_profile": lambda db, artifact_dir, **kw: "Lakers: Elo 1600."})
@patch("app.copilot.engine.OpenAI")
def test_run_copilot_conversation_executes_a_tool_call_then_returns_the_final_answer(mock_openai_cls):
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.side_effect = [
        _response(tool_calls=[_tool_call("call_1", "get_team_profile", {"team_name": "Lakers", "sport": "nba"})]),
        _response(content="The Lakers have a strong Elo rating."),
    ]

    answer = run_copilot_conversation(
        db=None, artifact_dir="/tmp/artifacts", api_key="fake-key",
        messages=[{"role": "user", "content": "Tell me about the Lakers"}],
    )

    assert answer == "The Lakers have a strong Elo rating."
    assert mock_client.chat.completions.create.call_count == 2

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_message = next(m for m in second_call_messages if m["role"] == "tool")
    assert tool_message["content"] == "Lakers: Elo 1600."
    assert tool_message["tool_call_id"] == "call_1"


@patch("app.copilot.engine.OpenAI")
def test_run_copilot_conversation_returns_the_answer_directly_when_no_tool_call_is_needed(mock_openai_cls):
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.return_value = _response(content="MatchIQ covers NBA and 5 soccer leagues.")

    answer = run_copilot_conversation(
        db=None, artifact_dir="/tmp/artifacts", api_key="fake-key",
        messages=[{"role": "user", "content": "What sports do you cover?"}],
    )

    assert answer == "MatchIQ covers NBA and 5 soccer leagues."


@patch("app.copilot.engine.TOOL_FUNCTIONS", {})
@patch("app.copilot.engine.OpenAI")
def test_run_copilot_conversation_stops_after_the_max_tool_rounds(mock_openai_cls):
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.return_value = _response(
        tool_calls=[_tool_call("call_1", "get_team_profile", {"team_name": "Lakers", "sport": "nba"})]
    )

    answer = run_copilot_conversation(
        db=None, artifact_dir="/tmp/artifacts", api_key="fake-key",
        messages=[{"role": "user", "content": "Tell me about the Lakers"}],
    )

    assert "couldn't finish" in answer.lower()
    assert mock_client.chat.completions.create.call_count == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_copilot_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.copilot.engine'`

- [ ] **Step 3: Implement the engine**

Create `backend/app/copilot/engine.py`:

```python
import json

from openai import OpenAI
from sqlalchemy.orm import Session

from app.copilot.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

_MODEL = "gpt-4o-mini"
_MAX_TOOL_ROUNDS = 5

_SYSTEM_PROMPT = (
    "You are MatchIQ's built-in AI copilot. Answer only using the tools provided -- call "
    "get_upcoming_predictions, get_team_profile, get_match_explanation, and get_market_odds as "
    "needed to ground your answer in MatchIQ's real data. Never guess or invent a team, "
    "prediction, or odds value. If a tool reports something wasn't found, or the question needs "
    "data with no corresponding tool (injuries, weather, lineups, news -- MatchIQ doesn't have "
    "any of that), say so plainly instead of guessing. Be concise, and cite specific numbers "
    "from tool results when relevant."
)


def run_copilot_conversation(db: Session, artifact_dir, api_key: str, messages: list[dict]) -> str:
    client = OpenAI(api_key=api_key)
    conversation = [{"role": "system", "content": _SYSTEM_PROMPT}, *messages]

    for _ in range(_MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=_MODEL,
            max_tokens=1024,
            temperature=0.2,
            messages=conversation,
            tools=TOOL_SCHEMAS,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

        conversation.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments},
                }
                for tool_call in message.tool_calls
            ],
        })
        for tool_call in message.tool_calls:
            function = TOOL_FUNCTIONS.get(tool_call.function.name)
            arguments = json.loads(tool_call.function.arguments)
            if function is None:
                result = f"Unknown tool: {tool_call.function.name}"
            else:
                result = function(db, artifact_dir, **arguments)
            conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "I couldn't finish gathering the data needed to answer that -- try asking a more specific question."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_copilot_engine.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/copilot/engine.py backend/tests/test_copilot_engine.py
git commit -m "feat: add the copilot tool-calling conversation engine"
```

---

## Task 4: `/chat/copilot` endpoint, retiring `/chat` and the old analyst

**Files:**
- Modify: `backend/app/schemas.py` (replace `ChatRequest` with `ChatMessageIn` + `CopilotRequest`)
- Modify: `backend/app/routers/chat.py` (full rewrite)
- Delete: `backend/app/ml/analyst.py`
- Delete: `backend/tests/test_analyst.py`
- Modify: `backend/tests/test_chat.py` (full rewrite)

**Interfaces:**
- Consumes: `run_copilot_conversation` from `app.copilot.engine` (Task 3); `rate_limit_chat` from `app.rate_limit`
- Produces: `POST /chat/copilot` — request `{"messages": [{"role": "user"|"assistant", "content": str}]}`, response `{"answer": str}`

- [ ] **Step 1: Update the schemas**

In `backend/app/schemas.py`, add `Literal` to the top import:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
```

Replace the `ChatRequest` class:

```python
class ChatRequest(BaseModel):
    sport: str
    league: str | None = None
    question: str
```

with:

```python
class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CopilotRequest(BaseModel):
    messages: list[ChatMessageIn]
```

(`ChatResponse` right below it is unchanged.)

- [ ] **Step 2: Rewrite the chat router**

Replace the full contents of `backend/app/routers/chat.py`:

```python
import openai
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.copilot.engine import run_copilot_conversation
from app.main import get_artifact_dir, get_db
from app.rate_limit import rate_limit_chat
from app.schemas import ChatResponse, CopilotRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/copilot", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
def post_copilot(
    body: CopilotRequest,
    db: Session = Depends(get_db),
    artifact_dir=Depends(get_artifact_dir),
):
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="AI copilot is not configured — set OPENAI_API_KEY")

    if not body.messages or not body.messages[-1].content.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        answer = run_copilot_conversation(
            db, artifact_dir, settings.openai_api_key,
            [message.model_dump() for message in body.messages],
        )
    except openai.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"AI copilot request failed: {e.message}")
    except openai.APIConnectionError:
        raise HTTPException(status_code=502, detail="AI copilot request failed: connection error")

    return ChatResponse(answer=answer)
```

- [ ] **Step 3: Delete the retired analyst module and its test**

```bash
git rm backend/app/ml/analyst.py backend/tests/test_analyst.py
```

- [ ] **Step 4: Rewrite the chat endpoint tests**

Replace the full contents of `backend/tests/test_chat.py`:

```python
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_artifact_dir, get_db
from app.rate_limit import RateLimiter


@pytest.fixture
def client_with_db(tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_copilot_503_when_no_api_key_configured(client_with_db):
    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(openai_api_key="")):
        response = client_with_db.post("/chat/copilot", json={"messages": [{"role": "user", "content": "Any picks?"}]})

    assert response.status_code == 503


def test_copilot_400_on_empty_question(client_with_db):
    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(openai_api_key="fake-key")):
        response = client_with_db.post("/chat/copilot", json={"messages": [{"role": "user", "content": "   "}]})

    assert response.status_code == 400


def test_copilot_400_when_messages_is_empty(client_with_db):
    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(openai_api_key="fake-key")):
        response = client_with_db.post("/chat/copilot", json={"messages": []})

    assert response.status_code == 400


@patch("app.routers.chat.run_copilot_conversation")
def test_copilot_returns_answer(mock_run, client_with_db):
    mock_run.return_value = "The Lakers are favored tonight."

    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(openai_api_key="fake-key")):
        response = client_with_db.post(
            "/chat/copilot",
            json={"messages": [{"role": "user", "content": "Who is favored tonight?"}]},
        )

    assert response.status_code == 200
    assert response.json() == {"answer": "The Lakers are favored tonight."}
    mock_run.assert_called_once()
    args = mock_run.call_args.args
    assert args[2] == "fake-key"
    assert args[3] == [{"role": "user", "content": "Who is favored tonight?"}]


@patch("app.routers.chat.run_copilot_conversation", return_value="ok")
def test_copilot_429_after_exceeding_the_rate_limit(mock_run, client_with_db):
    with (
        patch("app.rate_limit.chat_rate_limiter", RateLimiter(max_requests=1, window_seconds=60)),
        patch("app.routers.chat.get_settings", return_value=SimpleNamespace(openai_api_key="fake-key")),
    ):
        first = client_with_db.post("/chat/copilot", json={"messages": [{"role": "user", "content": "Q1"}]})
        second = client_with_db.post("/chat/copilot", json={"messages": [{"role": "user", "content": "Q2"}]})

    assert first.status_code == 200
    assert second.status_code == 429
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_chat.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: all tests pass (`test_analyst.py`'s 2 tests are gone, `test_chat.py`'s tests are replaced 3-for-5, net count changes accordingly — no failures)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/chat.py backend/tests/test_chat.py
git commit -m "feat: replace /chat with POST /chat/copilot (multi-turn, tool-calling)"
```

---

## Task 5: Frontend API client and types

**Files:**
- Modify: `frontend/src/types.ts` (add `ChatMessage`)
- Modify: `frontend/src/api.ts` (replace `askAnalyst` with `askCopilot`)
- Modify: `frontend/src/__tests__/api.test.ts` (replace the `askAnalyst` describe block)

**Interfaces:**
- Produces: `ChatMessage { role: "user" | "assistant"; content: string }` in `../types`; `askCopilot(messages: ChatMessage[]): Promise<ChatResponse>` in `../api` (used by Task 6)

- [ ] **Step 1: Add the `ChatMessage` type**

In `frontend/src/types.ts`, add after the existing `ChatResponse` interface:

```typescript
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
```

- [ ] **Step 2: Write the failing test for `askCopilot`**

In `frontend/src/__tests__/api.test.ts`, replace the whole `describe("askAnalyst", ...)` block (currently around line 302) with:

```typescript
describe("askCopilot", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts the conversation and returns the answer", async () => {
    const mockData: ChatResponse = { answer: "Lakers are favored." };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const messages: ChatMessage[] = [{ role: "user", content: "Who is favored?" }];
    const result = await askCopilot(messages);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/chat/copilot"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ messages }),
      }),
    );
    expect(result).toEqual(mockData);
  });

  it("throws an ApiError carrying the status code when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(askCopilot([{ role: "user", content: "Who is favored?" }])).rejects.toMatchObject(
      new ApiError("Failed to get an answer: 503", 503),
    );
  });
});
```

Update the file's top imports: replace `askAnalyst` with `askCopilot` in the named import from `../api`, and add `ChatMessage` to the named import from `../types`.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/api.test.ts`
Expected: FAIL — `askCopilot` is not exported by `../api`

- [ ] **Step 4: Replace `askAnalyst` with `askCopilot` in `api.ts`**

In `frontend/src/api.ts`, add `ChatMessage` to the type import at the top:

```typescript
import type {
  BacktestOut,
  ChatMessage,
  ChatResponse,
  ExplanationOut,
  MarketOddsOut,
  MatchContextOut,
  PredictionOut,
  SimulationOut,
  TeamProfileOut,
  WhatIfOut,
} from "./types";
```

Replace the `askAnalyst` function:

```typescript
export async function askAnalyst(sport: "nba" | "football", league: string | undefined, question: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sport, league: league ?? null, question }),
  });
  if (!response.ok) {
    throw new ApiError(`Failed to get an answer: ${response.status}`, response.status);
  }
  return response.json();
}
```

with:

```typescript
export async function askCopilot(messages: ChatMessage[]): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat/copilot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  if (!response.ok) {
    throw new ApiError(`Failed to get an answer: ${response.status}`, response.status);
  }
  return response.json();
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/api.test.ts`
Expected: PASS (all tests in the file, including the 2 new `askCopilot` tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/__tests__/api.test.ts
git commit -m "feat: replace askAnalyst with askCopilot (multi-turn /chat/copilot client)"
```

---

## Task 6: `CopilotWidget` (floating chatbot), retiring `ChatPanel`

**Files:**
- Create: `frontend/src/components/CopilotWidget.tsx`
- Test: `frontend/src/__tests__/CopilotWidget.test.tsx`
- Modify: `frontend/src/App.tsx` (mount the widget)
- Modify: `frontend/src/pages/HomePage.tsx` (remove `ChatPanel`)
- Delete: `frontend/src/components/ChatPanel.tsx`
- Delete: `frontend/src/__tests__/ChatPanel.test.tsx`

**Interfaces:**
- Consumes: `askCopilot`, `ApiError` from `../api`; `ChatMessage` from `../types` (Task 5)
- Produces: `CopilotWidget` component (default export not used — named export, mounted once in `App.tsx`)

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/__tests__/CopilotWidget.test.tsx`:

```tsx
import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CopilotWidget } from "../components/CopilotWidget";
import * as api from "../api";

describe("CopilotWidget", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is closed by default, showing only the bubble", () => {
    render(<CopilotWidget />);

    expect(screen.getByRole("button", { name: /ask matchiq/i })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/ask a question/i)).not.toBeInTheDocument();
  });

  it("opens the chat window when the bubble is clicked", () => {
    render(<CopilotWidget />);

    fireEvent.click(screen.getByRole("button", { name: /ask matchiq/i }));

    expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument();
  });

  it("sends a question and shows the answer", async () => {
    const spy = vi.spyOn(api, "askCopilot").mockResolvedValue({ answer: "The Lakers are favored tonight." });

    render(<CopilotWidget />);
    fireEvent.click(screen.getByRole("button", { name: /ask matchiq/i }));
    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Who is favored?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText(/lakers are favored tonight/i)).toBeInTheDocument());
    expect(spy).toHaveBeenCalledWith([{ role: "user", content: "Who is favored?" }]);
  });

  it("sends the accumulated conversation on a follow-up question", async () => {
    const spy = vi.spyOn(api, "askCopilot")
      .mockResolvedValueOnce({ answer: "The Lakers are favored tonight." })
      .mockResolvedValueOnce({ answer: "By about 8 points." });

    render(<CopilotWidget />);
    fireEvent.click(screen.getByRole("button", { name: /ask matchiq/i }));

    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Who is favored?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/lakers are favored tonight/i)).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "By how much?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/by about 8 points/i)).toBeInTheDocument());

    expect(spy).toHaveBeenLastCalledWith([
      { role: "user", content: "Who is favored?" },
      { role: "assistant", content: "The Lakers are favored tonight." },
      { role: "user", content: "By how much?" },
    ]);
  });

  it("shows a not-configured message on a 503 response", async () => {
    vi.spyOn(api, "askCopilot").mockRejectedValue(new api.ApiError("Failed to get an answer: 503", 503));

    render(<CopilotWidget />);
    fireEvent.click(screen.getByRole("button", { name: /ask matchiq/i }));
    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Any picks?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText(/isn't configured/i)).toBeInTheDocument());
  });

  it("shows a generic error message on other failures", async () => {
    vi.spyOn(api, "askCopilot").mockRejectedValue(new Error("boom"));

    render(<CopilotWidget />);
    fireEvent.click(screen.getByRole("button", { name: /ask matchiq/i }));
    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Any picks?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText(/couldn't get an answer/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/CopilotWidget.test.tsx`
Expected: FAIL — cannot find module `../components/CopilotWidget`

- [ ] **Step 3: Implement `CopilotWidget`**

Create `frontend/src/components/CopilotWidget.tsx`:

```tsx
import { useState } from "react";
import { ApiError, askCopilot } from "../api";
import type { ChatMessage } from "../types";

export function CopilotWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleSend() {
    if (!question.trim()) {
      setError("Type a question first.");
      return;
    }
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: question }];
    setMessages(nextMessages);
    setQuestion("");
    setError(null);
    setIsLoading(true);

    askCopilot(nextMessages)
      .then((result) => setMessages([...nextMessages, { role: "assistant", content: result.answer }]))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 503) {
          setError("The AI copilot isn't configured on this deployment yet.");
        } else if (err instanceof ApiError && err.status === 429) {
          setError("Too many questions — try again in a minute.");
        } else {
          setError("Couldn't get an answer from the copilot. Please try again later.");
        }
      })
      .finally(() => setIsLoading(false));
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 rounded-full bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-lg hover:bg-blue-700"
      >
        Ask MatchIQ
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 flex h-[28rem] w-80 flex-col rounded border border-gray-200 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-gray-200 p-3">
        <span className="text-sm font-semibold">MatchIQ Copilot</span>
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          className="text-gray-500 hover:text-gray-700"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3 text-sm">
        {messages.length === 0 && (
          <p className="text-xs text-gray-500">
            Ask about predictions, team form, or odds — e.g. "compare Real Madrid with Bayern" or "why is Arsenal
            favored?". I only answer from MatchIQ's real data.
          </p>
        )}
        {messages.map((message, index) => (
          <p key={index} className={message.role === "user" ? "text-right text-blue-700" : "text-left text-gray-800"}>
            {message.content}
          </p>
        ))}
        {isLoading && <p className="text-xs text-gray-400">Thinking...</p>}
      </div>

      {error && <p className="px-3 text-xs text-red-600">{error}</p>}

      <div className="flex items-end gap-2 border-t border-gray-200 p-3">
        <input
          type="text"
          placeholder="Ask a question..."
          className="min-w-0 flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={isLoading}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/CopilotWidget.test.tsx`
Expected: PASS (6 passed)

- [ ] **Step 5: Mount the widget globally in `App.tsx`**

In `frontend/src/App.tsx`, add an import:

```typescript
import { CopilotWidget } from "./components/CopilotWidget";
```

Add `<CopilotWidget />` as the last child inside the outer `<div className="mx-auto max-w-6xl p-6">`, after the closing `</div>` of the `Routes` wrapper:

```tsx
      <div className="mt-6">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/team/:teamId" element={<TeamPage />} />
          <Route path="/match/:gameId" element={<MatchPage />} />
          <Route path="/accuracy" element={<AccuracyPage />} />
          <Route path="/betting" element={<BettingPage />} />
        </Routes>
      </div>

      <CopilotWidget />
    </div>
  );
}
```

- [ ] **Step 6: Remove `ChatPanel` from `HomePage.tsx`**

Replace the full contents of `frontend/src/pages/HomePage.tsx`:

```tsx
import { useState } from "react";
import { GameList } from "../components/GameList";
import { LEAGUE_TABS, type LeagueTab } from "../leagueTabs";

export function HomePage() {
  const [activeTab, setActiveTab] = useState<LeagueTab>(LEAGUE_TABS[0]);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {LEAGUE_TABS.map((tab) => (
          <button
            key={tab.label}
            className={`rounded px-3 py-1 ${activeTab.label === tab.label ? "bg-blue-600 text-white" : "bg-gray-100"}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        <GameList sport={activeTab.sport} league={activeTab.league} />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Delete `ChatPanel` and its test**

```bash
git rm frontend/src/components/ChatPanel.tsx frontend/src/__tests__/ChatPanel.test.tsx
```

- [ ] **Step 8: Run the full frontend suite, typecheck, and lint**

Run: `cd frontend && npx vitest run`
Expected: all tests pass (previous count − `ChatPanel.test.tsx`'s 4 + `CopilotWidget.test.tsx`'s 6 + `api.test.ts`'s net-unchanged 2)

Run: `cd frontend && npm run build`
Expected: `tsc -b` and the Vite build both succeed with no errors

Run: `cd frontend && npm run lint`
Expected: no errors

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/CopilotWidget.tsx frontend/src/__tests__/CopilotWidget.test.tsx frontend/src/App.tsx frontend/src/pages/HomePage.tsx
git rm frontend/src/components/ChatPanel.tsx frontend/src/__tests__/ChatPanel.test.tsx
git commit -m "feat: add floating CopilotWidget mounted globally, retire embedded ChatPanel"
```

---

## Task 7: Full verification and push

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: all tests pass, 0 failures

- [ ] **Step 2: Run the full frontend suite, typecheck, and lint**

Run: `cd frontend && npx vitest run && npm run build && npm run lint`
Expected: all pass, 0 failures/errors

- [ ] **Step 3: Restart the local backend to pick up the code changes**

The backend dev server (if already running from an earlier session) was started without `--reload`, so it's still serving the old code. Stop any process listening on port 8000, then:

Run: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 &` (or however the existing background process is managed)
Expected: `curl -s http://localhost:8000/health` returns `{"status":"ok"}`

- [ ] **Step 4: Manual smoke test in the browser**

With the frontend dev server running (`http://localhost:5173`), open it in a browser and confirm:
- A blue "Ask MatchIQ" bubble is visible in the bottom-right corner on every page (Predictions, Accuracy, Betting Tools).
- Clicking it opens the chat window; the old "Ask the analyst" box on the homepage is gone.
- Asking "Who is favored tonight?" (or similar) returns a real answer grounded in actual upcoming matches (requires `OPENAI_API_KEY` set in `backend/.env`).
- A follow-up question in the same session gets an answer that's consistent with the first (confirms conversation history is being sent).
- Asking about a team not currently loaded (e.g. a team from an unsupported sport) gets an honest "not found" answer, not a fabricated one.

- [ ] **Step 5: Push**

```bash
git push origin phase1-core-prediction-engine
```
