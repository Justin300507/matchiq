import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SimulationPanel } from "../components/SimulationPanel";
import * as api from "../api";
import type { SimulationOut } from "../types";

describe("SimulationPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading state before data arrives", () => {
    vi.spyOn(api, "fetchSimulation").mockReturnValue(new Promise(() => {}));
    render(<SimulationPanel gameId={1} />);
    expect(screen.getByText(/running/i)).toBeInTheDocument();
  });

  it("renders outcome percentages and top scorelines once loaded", async () => {
    const simulation: SimulationOut = {
      game_id: 1,
      home_win_pct: 58.3,
      draw_pct: 24.1,
      away_win_pct: 17.6,
      top_scorelines: [{ home_score: 2, away_score: 1, frequency_pct: 8.4 }],
      n_simulations: 10000,
    };
    vi.spyOn(api, "fetchSimulation").mockResolvedValue(simulation);

    render(<SimulationPanel gameId={1} />);

    await waitFor(() => expect(screen.getByText("58.3%")).toBeInTheDocument());
    expect(screen.getByText("24.1%")).toBeInTheDocument();
    expect(screen.getByText("17.6%")).toBeInTheDocument();
    expect(screen.getByText("2 - 1")).toBeInTheDocument();
  });

  it("omits the draw row when draw_pct is null", async () => {
    const simulation: SimulationOut = {
      game_id: 1, home_win_pct: 60, draw_pct: null, away_win_pct: 40,
      top_scorelines: [], n_simulations: 10000,
    };
    vi.spyOn(api, "fetchSimulation").mockResolvedValue(simulation);

    render(<SimulationPanel gameId={1} />);

    await waitFor(() => expect(screen.getByText("60.0%")).toBeInTheDocument());
    expect(screen.queryByText(/draw/i)).not.toBeInTheDocument();
  });

  it("shows an error message when the simulation fails to load", async () => {
    vi.spyOn(api, "fetchSimulation").mockRejectedValue(new Error("boom"));

    render(<SimulationPanel gameId={1} />);

    await waitFor(() => expect(screen.getByText(/couldn't run the simulation/i)).toBeInTheDocument());
  });
});
