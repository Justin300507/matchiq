# MatchIQ — AI Sports Copilot (floating chatbot)

**Date:** 2026-08-02
**Status:** Approved for planning

## Context

This is sub-project #1 of a broader "MatchIQ becomes a sports intelligence platform" vision that was pitched as ~10 independent subsystems in one message (Bloomberg-terminal match view, AI copilot, Monte Carlo digital twin, computer vision on live video, sports knowledge graph, multi-agent orchestration, developer SDK/API platform, cross-entity AI memory, autonomous nightly retraining, and the "ForgeAI for Sports" umbrella positioning). That's too large for one spec or one build. The agreed decomposition order is:

1. **AI Sports Copilot** (this spec)
2. Bloomberg Terminal match view (natural-language reasoning bullets + pre-match timeline, reusing this copilot's LLM layer)
3. Digital Twin simulation upgrades (extend the existing Monte Carlo endpoint)
4. Autonomous nightly research/retrain agent (behind a human-approval gate before any new model artifact goes live)
5. Knowledge Graph / cross-entity AI memory — deferred until more entity data (injuries, referees, weather, transfers) is actually ingested; without that data there's nothing real for a graph to reason over.

Explicitly deprioritized for now: computer vision on live broadcast video (this is what Second Spectrum/Stats Perform do with proprietary tracking data and dedicated ML teams — not realistic for a solo project without a fundamentally different data source), the 10-agent multi-agent architecture (most of the proposed agents — news, injury, psychology — have no underlying data feed yet, so there's nothing to orchestrate), and the Developer SDK / Enterprise Dashboard productization (not worth building an external API surface before the product itself is compelling).

## Current state this builds on

MatchIQ already has a chat analyst (`backend/app/ml/analyst.py`, `POST /chat`), but it's narrow: a single-shot question/answer, hard-scoped to one `sport`/`league` passed in by the frontend, with the entire context being a flat list of that scope's upcoming predictions. It explicitly refuses to answer anything about injuries/weather/lineups/odds because none of that existed when it was built — that's now stale, since live Polymarket odds shipped today. The frontend embeds it as a small widget (`ChatPanel.tsx`) on the homepage only, with no conversation memory.

Also relevant: `backend/app/rate_limit.py` (a 20 req/min per-IP in-memory limiter, currently applied to `/chat`), `backend/app/ml/explain.py` (SHAP-based per-prediction factors), `backend/app/ml/team_profile.py` (Elo + form), `backend/app/integrations/polymarket_odds.py` (live market odds, including its `_names_match` fuzzy team-name matching, which this spec reuses the pattern of).

## Goal

Replace the embedded, scope-limited widget with a floating chatbot (bubble, bottom-right, available on every page) that holds a real multi-turn conversation and can answer questions across any sport/league in one conversation — comparisons ("compare Real Madrid with Bayern"), reasoning ("why is Barcelona favored today?"), and general Q&A — grounded only in MatchIQ's real data, using the same "say we don't have it, never fabricate" honesty principle the current analyst already follows.

Explicitly out of scope for this build (confirmed with the user): "biggest probability shifts today" and "why did the odds change" — both require snapshotting predictions/odds over time to diff against, and nothing is stored historically today, only live values. This ships as a fast-follow once the copilot itself is proven, not as part of this build.

## Architecture

Tool-calling replaces the current single-shot prompt. Four read-only tools, each wrapping logic that already exists:

- `get_upcoming_predictions(sport, league=None)` — generalizes today's `_build_match_context`; no longer hard-scoped to a single league per call.
- `get_team_profile(team_name, sport)` — resolves `team_name` to a `Team` row via fuzzy substring matching (same pattern as `polymarket_odds._names_match`, factored out into a new shared `backend/app/utils/name_matching.py` that both `polymarket_odds.py` and the copilot's tools import), then calls the existing `compute_team_profile`. Returns "no team found matching X" as a tool result (not an HTTP error) if unresolved, so the model can tell the user honestly rather than guessing.
- `get_match_explanation(home_team, away_team, sport)` — resolves both names to the nearest upcoming `Match` row (a new shared `find_upcoming_match(db, home_team, away_team, sport)` helper, same fuzzy-matching approach), then calls the existing `explain_prediction`.
- `get_market_odds(home_team, away_team, sport)` — same match resolution, then calls the existing `find_match_odds`.

Flow per user message: send the conversation + tool defs to OpenAI → if it returns tool calls, execute them against the DB (read-only, no user input reaches SQL directly — team/sport names only ever flow into the existing fuzzy-match helpers, never into raw queries) → feed results back as tool messages → repeat, capped at 5 rounds → return the final text answer. The cap bounds worst-case OpenAI cost per request regardless of how many tools the model decides to call. Same model as today (`gpt-4o-mini`, which supports function calling) — no model change needed for this.

The system prompt is rewritten to match reality: it currently tells the model MatchIQ has no odds data, which became false the moment the Polymarket integration shipped. The new prompt says what tools are available and reiterates the same honesty rule in tool-call terms — answer only from tool results, and if a tool comes back "not found" or a question needs data with no corresponding tool (injuries, weather, lineups — still genuinely absent), say so plainly instead of guessing.

`POST /chat` (single `question` + fixed `sport`/`league`) is replaced by `POST /chat/copilot`, which accepts `{ messages: [{role, content}, ...] }` — the full conversation so far, including the new user message. The backend is stateless between requests; conversation memory lives entirely in the frontend's local state, not a server-side session store — no new DB table needed for this.

The existing `rate_limit_chat` dependency (20 req/min/IP) moves to `/chat/copilot`; the 5-round tool-call cap is the real cost control since one HTTP request can now trigger multiple OpenAI calls.

## Frontend

A new `CopilotWidget` component mounted once at the app root (`App.tsx`), not per-page — a floating bubble that expands into a chat window, present on every route. It owns the conversation array in local React state and sends the full history with each new question. The existing embedded `ChatPanel` and its use on `HomePage` are removed — one chat surface instead of two.

## Error handling

Same shape as today's `/chat`: 503 if `OPENAI_API_KEY` isn't configured, 400 on an empty/whitespace question, 502 on OpenAI connection/status errors, 429 from the rate limiter. New: if the model asks for a tool with a team/match it can't resolve, that tool returns a "not found" result *to the model* (never an HTTP error), consistent with the "say we don't have it" principle. If the 5-round tool-call cap is hit without a final answer, return a graceful "couldn't complete that request" message rather than an error.

## Testing

Backend: a unit test per tool (mocked DB) covering both the found and not-found cases; a test for the tool-calling loop itself using a mocked OpenAI client that simulates a tool_call response followed by a final-answer response; endpoint tests for the 503/400/502/429 paths and a happy-path multi-turn request. Frontend: `CopilotWidget` tests for open/close, sending a message, a follow-up message building on prior context, and error states; `ChatPanel.tsx` and its tests are deleted along with the component.
