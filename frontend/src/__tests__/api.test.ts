import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchExplanation, fetchUpcomingPredictions } from "../api";
import type { ExplanationOut, PredictionOut } from "../types";

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
