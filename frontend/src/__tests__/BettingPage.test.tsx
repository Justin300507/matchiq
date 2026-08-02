import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BettingPage } from "../pages/BettingPage";
import * as api from "../api";
import type { MarketOddsOut, PredictionOut } from "../types";

const nbaMatch: PredictionOut = {
  game_id: 1, sport: "nba", league: "NBA", date: "2026-02-01T19:00:00Z",
  home_team: { id: 1, name: "Lakers", league: "NBA" },
  away_team: { id: 2, name: "Celtics", league: "NBA" },
  home_win_prob: 0.5, draw_prob: null, away_win_prob: 0.5,
  predicted_home_score: 100, predicted_away_score: 99, model_confidence: "Medium",
};

const unavailableOdds: MarketOddsOut = {
  available: false, source: null, event_title: null, event_url: null,
  home_decimal_odds: null, draw_decimal_odds: null, away_decimal_odds: null,
};

describe("BettingPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the no-fabricated-odds disclaimer", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    vi.spyOn(api, "fetchMarketOdds").mockResolvedValue(unavailableOdds);
    render(<BettingPage />);
    await waitFor(() => expect(screen.getByText(/either fetched live from/i)).toBeInTheDocument());
  });

  it("shows a message when no Polymarket market is found for the selected match", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    vi.spyOn(api, "fetchMarketOdds").mockResolvedValue(unavailableOdds);
    render(<BettingPage />);

    await waitFor(() => expect(screen.getByText(/no live polymarket market found/i)).toBeInTheDocument());
  });

  it("shows fetched Polymarket odds and fills the odds input when used", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    vi.spyOn(api, "fetchMarketOdds").mockResolvedValue({
      available: true, source: "Polymarket", event_title: "Lakers vs. Celtics",
      event_url: "https://polymarket.com/event/lakers-vs-celtics",
      home_decimal_odds: 2.5, draw_decimal_odds: null, away_decimal_odds: 1.8,
    });
    render(<BettingPage />);

    await waitFor(() => expect(screen.getByText(/polymarket: home 2.50/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /view on polymarket/i })).toHaveAttribute(
      "href", "https://polymarket.com/event/lakers-vs-celtics",
    );

    fireEvent.click(screen.getByRole("button", { name: /use these odds for home/i }));

    expect(screen.getByLabelText(/decimal odds/i)).toHaveValue(2.5);
  });

  it("adds a leg and computes edge/EV/Kelly against user-entered odds", async () => {
    vi.spyOn(api, "fetchUpcomingPredictions").mockResolvedValue([nbaMatch]);
    vi.spyOn(api, "fetchMarketOdds").mockResolvedValue(unavailableOdds);
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
    vi.spyOn(api, "fetchMarketOdds").mockResolvedValue(unavailableOdds);
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
    vi.spyOn(api, "fetchMarketOdds").mockResolvedValue(unavailableOdds);
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
