import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchExplanation, fetchSimulation, fetchTeamProfile, fetchUpcomingPredictions } from "../api";
import type { ExplanationOut, PredictionOut, SimulationOut, TeamProfileOut } from "../types";

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

    await expect(fetchUpcomingPredictions("soccer")).rejects.toThrow();
  });

  it("includes the league query param when given", async () => {
    const mockData: PredictionOut[] = [];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    }) as unknown as typeof fetch;

    await fetchUpcomingPredictions("soccer", "Bundesliga");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("league=Bundesliga"),
    );
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
