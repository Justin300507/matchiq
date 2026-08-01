import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
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
    render(<MemoryRouter><GameList sport="nba" /></MemoryRouter>);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders a GameCard per prediction once loaded", async () => {
    const predictions: PredictionOut[] = [{
      game_id: 1, sport: "nba", league: "NBA", date: "2026-02-01T19:00:00Z",
      home_team: { id: 1, name: "Lakers", league: "NBA" },
      away_team: { id: 2, name: "Celtics", league: "NBA" },
      home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4,
      predicted_home_score: 105, predicted_away_score: 99,
      model_confidence: "Medium",
    }];
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue(predictions);

    render(<MemoryRouter><GameList sport="nba" /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("Lakers")).toBeInTheDocument());
  });

  it("shows an error message when the fetch fails", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockRejectedValue(new Error("boom"));

    render(<MemoryRouter><GameList sport="nba" /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText(/couldn't load predictions/i)).toBeInTheDocument());
  });

  it("shows an empty-state message when there are no upcoming games", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([]);

    render(<MemoryRouter><GameList sport="nba" /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText(/no upcoming games/i)).toBeInTheDocument());
  });
});
