import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GameCard } from "../components/GameCard";
import type { PredictionOut } from "../types";

const basePrediction: PredictionOut = {
  game_id: 1,
  sport: "nba",
  league: "NBA",
  date: "2026-02-01T19:00:00Z",
  home_team: { id: 1, name: "Lakers", league: "NBA" },
  away_team: { id: 2, name: "Celtics", league: "NBA" },
  home_win_prob: 0.65,
  draw_prob: null,
  away_win_prob: 0.35,
  predicted_home_score: 108,
  predicted_away_score: 101,
};

describe("GameCard", () => {
  it("renders team names and predicted score", () => {
    render(<GameCard prediction={basePrediction} />);
    expect(screen.getByText("Lakers")).toBeInTheDocument();
    expect(screen.getByText("Celtics")).toBeInTheDocument();
    expect(screen.getByText("108")).toBeInTheDocument();
    expect(screen.getByText("101")).toBeInTheDocument();
  });

  it("renders home win probability as a percentage", () => {
    render(<GameCard prediction={basePrediction} />);
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("renders draw probability only when present", () => {
    render(<GameCard prediction={{ ...basePrediction, sport: "soccer", draw_prob: 0.25, home_win_prob: 0.55, away_win_prob: 0.2 }} />);
    expect(screen.getByText("25%")).toBeInTheDocument();
  });

  it("omits draw probability for nba", () => {
    render(<GameCard prediction={basePrediction} />);
    expect(screen.queryByText("Draw")).not.toBeInTheDocument();
  });
});
