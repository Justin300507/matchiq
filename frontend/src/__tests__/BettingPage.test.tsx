import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BettingPage } from "../pages/BettingPage";
import * as api from "../api";
import type { PredictionOut } from "../types";

const nbaMatch: PredictionOut = {
  game_id: 1, sport: "nba", league: "NBA", date: "2026-02-01T19:00:00Z",
  home_team: { id: 1, name: "Lakers", league: "NBA" },
  away_team: { id: 2, name: "Celtics", league: "NBA" },
  home_win_prob: 0.5, draw_prob: null, away_win_prob: 0.5,
  predicted_home_score: 100, predicted_away_score: 99, model_confidence: "Medium",
};

describe("BettingPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the no-fabricated-odds disclaimer", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    render(<BettingPage />);
    await waitFor(() => expect(screen.getByText(/doesn't fetch, store, or invent/i)).toBeInTheDocument());
  });

  it("adds a leg and computes edge/EV/Kelly against user-entered odds", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    render(<BettingPage />);

    await waitFor(() => expect(screen.getByText("Lakers vs Celtics")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/decimal odds/i), { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: /add to bet slip/i }));

    await waitFor(() => expect(screen.getByText(/bet slip \(1 leg\)/i)).toBeInTheDocument());
    expect(screen.getByText("10.0 pts")).toBeInTheDocument(); // edge: 50% model vs 40% implied
    expect(screen.getByText("25.0%")).toBeInTheDocument(); // EV
  });

  it("rejects invalid odds", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    render(<BettingPage />);

    await waitFor(() => expect(screen.getByText("Lakers vs Celtics")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/decimal odds/i), { target: { value: "0.5" } });
    fireEvent.click(screen.getByRole("button", { name: /add to bet slip/i }));

    expect(screen.getByText(/enter decimal odds greater than 1.00/i)).toBeInTheDocument();
  });

  it("labels multiple legs as a parlay and shows the independence caveat", async () => {
    const secondMatch: PredictionOut = {
      ...nbaMatch, game_id: 2,
      home_team: { id: 3, name: "Warriors", league: "NBA" },
      away_team: { id: 4, name: "Suns", league: "NBA" },
    };
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch, secondMatch]);
    render(<BettingPage />);

    await waitFor(() => expect(screen.getByText("Lakers vs Celtics")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/decimal odds/i), { target: { value: "2.0" } });
    fireEvent.click(screen.getByRole("button", { name: /add to bet slip/i }));

    fireEvent.change(screen.getByLabelText(/^match$/i), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /add to bet slip/i }));

    await waitFor(() => expect(screen.getByText(/bet slip \(2 legs — parlay\)/i)).toBeInTheDocument());
    expect(screen.getByText(/assumes the selected matches are statistically independent/i)).toBeInTheDocument();
  });
});
