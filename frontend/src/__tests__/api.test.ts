import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  askAnalyst,
  fetchAccuracy,
  fetchExplanation,
  fetchMarketOdds,
  fetchMatchContext,
  fetchPrediction,
  fetchSimulation,
  fetchTeamProfile,
  fetchUpcomingPredictions,
  fetchWhatIf,
} from "../api";
import type {
  BacktestOut,
  ChatResponse,
  ExplanationOut,
  MarketOddsOut,
  MatchContextOut,
  PredictionOut,
  SimulationOut,
  TeamProfileOut,
  WhatIfOut,
} from "../types";

describe("fetchUpcomingPredictions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the predictions/upcoming endpoint with the sport query param", async () => {
    const mockData: PredictionOut[] = [];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    await fetchUpcomingPredictions("nba");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/predictions/upcoming?sport=nba"),
    );
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(fetchUpcomingPredictions("football")).rejects.toThrow();
  });

  it("includes the league query param when given", async () => {
    const mockData: PredictionOut[] = [];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    await fetchUpcomingPredictions("football", "Bundesliga");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("league=Bundesliga"),
    );
  });
});

describe("fetchPrediction", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  const basePrediction: PredictionOut = {
    game_id: 42, sport: "nba", league: "NBA", date: "2026-02-01T19:00:00Z",
    home_team: { id: 1, name: "Lakers", league: "NBA" },
    away_team: { id: 2, name: "Celtics", league: "NBA" },
    home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4,
    predicted_home_score: 105, predicted_away_score: 99, model_confidence: "Medium",
  };

  it("calls the predictions/{id} endpoint", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => basePrediction,
    }) as unknown as typeof fetch;

    const result = await fetchPrediction(42);

    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/predictions/42"));
    expect(result).toEqual(basePrediction);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as unknown as typeof fetch;

    await expect(fetchPrediction(42)).rejects.toThrow();
  });
});

describe("fetchMatchContext", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the predictions/{id}/context endpoint", async () => {
    const mockData: MatchContextOut = { game_id: 42, home_recent_form: [], away_recent_form: [], head_to_head: [] };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchMatchContext(42);

    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/predictions/42/context"));
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as unknown as typeof fetch;

    await expect(fetchMatchContext(42)).rejects.toThrow();
  });
});

describe("fetchMarketOdds", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the predictions/{id}/market-odds endpoint", async () => {
    const mockData: MarketOddsOut = {
      available: true, source: "Polymarket", event_title: "Arsenal vs. Chelsea",
      event_url: "https://polymarket.com/event/arsenal-vs-chelsea",
      home_decimal_odds: 2.1, draw_decimal_odds: 3.3, away_decimal_odds: 3.8,
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchMarketOdds(42);

    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/predictions/42/market-odds"));
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 }) as unknown as typeof fetch;

    await expect(fetchMarketOdds(42)).rejects.toThrow();
  });
});

describe("fetchExplanation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the predictions/{id}/explain endpoint", async () => {
    const mockData: ExplanationOut = { game_id: 42, factors: [], model_confidence: "High" };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchExplanation(42);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/predictions/42/explain"),
    );
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(fetchExplanation(42)).rejects.toThrow();
  });
});

describe("fetchSimulation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the predictions/{id}/simulate endpoint", async () => {
    const mockData: SimulationOut = {
      game_id: 42, home_win_pct: 60, draw_pct: null, away_win_pct: 40,
      top_scorelines: [], n_simulations: 10000,
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchSimulation(42);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/predictions/42/simulate"),
    );
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(fetchSimulation(42)).rejects.toThrow();
  });
});

describe("fetchTeamProfile", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the teams/{id}/profile endpoint", async () => {
    const mockData: TeamProfileOut = {
      team_id: 7, team_name: "Lakers", league: "NBA", matches_played: 10,
      wins: 6, draws: 0, losses: 4, goals_for_avg: 108.2, goals_against_avg: 104.5,
      home_win_rate: 0.7, away_win_rate: 0.5, last5_form: "WWLWL", elo_rating: 1550.2,
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchTeamProfile(7);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/teams/7/profile"),
    );
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as unknown as typeof fetch;

    await expect(fetchTeamProfile(7)).rejects.toThrow();
  });
});

describe("fetchAccuracy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the accuracy endpoint with the sport query param", async () => {
    const mockData: BacktestOut = {
      sport: "nba", predictions_evaluated: 120, model_accuracy: 0.58, model_log_loss: 0.65,
      model_brier_score: 0.23, baseline_accuracy: 0.53, baseline_log_loss: 15.2, baseline_brier_score: 0.47,
      labels: ["H", "A"], confusion_matrix: [[50, 10], [15, 45]], roc_auc: 0.72, reliability_bins: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchAccuracy("nba");

    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/accuracy?sport=nba"));
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(fetchAccuracy("nba")).rejects.toThrow();
  });
});

describe("fetchWhatIf", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds a query string from the overrides and calls the whatif endpoint", async () => {
    const mockData: WhatIfOut = {
      game_id: 42,
      overrides_applied: { home_form_last5: 0.95 },
      original: { home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4, predicted_home_score: 100, predicted_away_score: 95, model_confidence: "Medium" },
      counterfactual: { home_win_prob: 0.9, draw_prob: null, away_win_prob: 0.1, predicted_home_score: 108, predicted_away_score: 90, model_confidence: "High" },
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await fetchWhatIf(42, { home_form_last5: 0.95 });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/predictions/42/whatif?home_form_last5=0.95"),
    );
    expect(result).toEqual(mockData);
  });

  it("throws when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 400 }) as unknown as typeof fetch;

    await expect(fetchWhatIf(42, { home_form_last5: 2 })).rejects.toThrow();
  });
});

describe("askAnalyst", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts sport, league, and question and returns the answer", async () => {
    const mockData: ChatResponse = { answer: "Lakers are favored." };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    const result = await askAnalyst("nba", undefined, "Who is favored?");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/chat"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ sport: "nba", league: null, question: "Who is favored?" }),
      }),
    );
    expect(result).toEqual(mockData);
  });

  it("throws an ApiError carrying the status code when the response is not ok", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 }) as unknown as typeof fetch;

    await expect(askAnalyst("nba", undefined, "Who is favored?")).rejects.toMatchObject(
      new ApiError("Failed to get an answer: 503", 503),
    );
  });
});
