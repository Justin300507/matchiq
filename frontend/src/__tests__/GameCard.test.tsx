import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GameCard } from "../components/GameCard";
import * as api from "../api";
import type { ExplanationOut, PredictionOut } from "../types";

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
  model_confidence: "Medium",
};

describe("GameCard", () => {
  it("renders team names and predicted score", () => {
    render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);
    expect(screen.getByText("Lakers")).toBeInTheDocument();
    expect(screen.getByText("Celtics")).toBeInTheDocument();
    expect(screen.getByText("108")).toBeInTheDocument();
    expect(screen.getByText("101")).toBeInTheDocument();
  });

  it("renders home win probability as a percentage", () => {
    render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("renders draw probability only when present", () => {
    render(<MemoryRouter><GameCard prediction={{ ...basePrediction, sport: "soccer", draw_prob: 0.25, home_win_prob: 0.55, away_win_prob: 0.2 }} /></MemoryRouter>);
    expect(screen.getByText("25%")).toBeInTheDocument();
  });

  it("omits draw probability for nba", () => {
    render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);
    expect(screen.queryByText("Draw")).not.toBeInTheDocument();
  });

  it("renders the model confidence badge from the prediction", () => {
    render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);
    expect(screen.getByText("Medium confidence")).toBeInTheDocument();
  });

  describe("Why? explanation panel", () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    const explanation: ExplanationOut = {
      game_id: 1,
      model_confidence: "High",
      factors: [
        { name: "home_form_last5", label: "Home team's recent form", relative_influence_pct: 42.3 },
        { name: "away_rest_days", label: "Away team's rest advantage", relative_influence_pct: -8.1 },
      ],
    };

    it("does not fetch the explanation until the button is clicked", () => {
      const spy = vi.spyOn(api, "fetchExplanation").mockResolvedValue(explanation);
      render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);
      expect(spy).not.toHaveBeenCalled();
    });

    it("fetches and displays factors when clicked", async () => {
      vi.spyOn(api, "fetchExplanation").mockResolvedValue(explanation);
      render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);

      fireEvent.click(screen.getByRole("button", { name: /why\?/i }));

      await waitFor(() => expect(screen.getByText("Home team's recent form")).toBeInTheDocument());
      expect(screen.getByText("+42.3%")).toBeInTheDocument();
      expect(screen.getByText("-8.1%")).toBeInTheDocument();
    });

    it("does not refetch when toggled closed then open again", async () => {
      const spy = vi.spyOn(api, "fetchExplanation").mockResolvedValue(explanation);
      render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);

      const button = screen.getByRole("button", { name: /why\?/i });
      fireEvent.click(button);
      await waitFor(() => expect(screen.getByText("Home team's recent form")).toBeInTheDocument());

      fireEvent.click(screen.getByRole("button", { name: /hide explanation/i }));
      fireEvent.click(screen.getByRole("button", { name: /why\?/i }));

      await waitFor(() => expect(screen.getByText("Home team's recent form")).toBeInTheDocument());
      expect(spy).toHaveBeenCalledTimes(1);
    });

    it("shows an error message when the explanation fails to load", async () => {
      vi.spyOn(api, "fetchExplanation").mockRejectedValue(new Error("boom"));
      render(<MemoryRouter><GameCard prediction={basePrediction} /></MemoryRouter>);

      fireEvent.click(screen.getByRole("button", { name: /why\?/i }));

      await waitFor(() => expect(screen.getByText(/couldn't load the explanation/i)).toBeInTheDocument());
    });
  });
});
