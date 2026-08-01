import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MatchPage } from "../pages/MatchPage";
import * as api from "../api";
import type { ExplanationOut, MatchContextOut, PredictionOut } from "../types";

const prediction: PredictionOut = {
  game_id: 42, sport: "nba", league: "NBA", date: "2026-02-01T19:00:00Z",
  home_team: { id: 1, name: "Lakers", league: "NBA" },
  away_team: { id: 2, name: "Celtics", league: "NBA" },
  home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4,
  predicted_home_score: 105, predicted_away_score: 99, model_confidence: "Medium",
};

const context: MatchContextOut = {
  game_id: 42,
  home_recent_form: [{ date: "2026-01-20T00:00:00Z", opponent_name: "Nets", is_home: true, team_score: 110, opponent_score: 90, result: "W" }],
  away_recent_form: [],
  head_to_head: [],
};

const explanation: ExplanationOut = {
  game_id: 42,
  model_confidence: "Medium",
  factors: [{ name: "home_form_last5", label: "Home team's recent form", relative_influence_pct: 20 }],
};

function renderAtMatch(gameId: number) {
  return render(
    <MemoryRouter initialEntries={[`/match/${gameId}`]}>
      <Routes>
        <Route path="/match/:gameId" element={<MatchPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MatchPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading state before the prediction arrives", () => {
    vi.spyOn(api, "fetchPrediction").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "fetchMatchContext").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "fetchExplanation").mockReturnValue(new Promise(() => {}));
    renderAtMatch(42);
    expect(screen.getByText(/loading match/i)).toBeInTheDocument();
  });

  it("renders teams, predicted score, explanation, and recent form", async () => {
    vi.spyOn(api, "fetchPrediction").mockResolvedValue(prediction);
    vi.spyOn(api, "fetchMatchContext").mockResolvedValue(context);
    vi.spyOn(api, "fetchExplanation").mockResolvedValue(explanation);
    vi.spyOn(api, "fetchSimulation").mockResolvedValue({
      game_id: 42, home_win_pct: 60, draw_pct: null, away_win_pct: 40, top_scorelines: [], n_simulations: 10000,
    });

    renderAtMatch(42);

    await waitFor(() => expect(screen.getByText("Lakers")).toBeInTheDocument());
    expect(screen.getByText("Celtics")).toBeInTheDocument();
    expect(screen.getByText("105")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Home team's recent form")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Nets/)).toBeInTheDocument());
  });

  it("shows an error message when the prediction fails to load", async () => {
    vi.spyOn(api, "fetchPrediction").mockRejectedValue(new Error("boom"));
    vi.spyOn(api, "fetchMatchContext").mockResolvedValue(context);
    vi.spyOn(api, "fetchExplanation").mockResolvedValue(explanation);

    renderAtMatch(42);

    await waitFor(() => expect(screen.getByText(/couldn't load this match/i)).toBeInTheDocument());
  });
});
