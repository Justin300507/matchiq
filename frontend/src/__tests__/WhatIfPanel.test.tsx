import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WhatIfPanel } from "../components/WhatIfPanel";
import * as api from "../api";
import type { WhatIfOut } from "../types";

describe("WhatIfPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not fetch until Run what-if is clicked", () => {
    const spy = vi.spyOn(api, "fetchWhatIf").mockResolvedValue({
      game_id: 1,
      overrides_applied: {},
      original: { home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4, predicted_home_score: 100, predicted_away_score: 95, model_confidence: "Medium" },
      counterfactual: { home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4, predicted_home_score: 100, predicted_away_score: 95, model_confidence: "Medium" },
    });

    render(<WhatIfPanel gameId={1} />);

    expect(spy).not.toHaveBeenCalled();
  });

  it("runs the simulation and shows original vs counterfactual", async () => {
    const result: WhatIfOut = {
      game_id: 1,
      overrides_applied: { home_form_last5: 0.8 },
      original: { home_win_prob: 0.6, draw_prob: null, away_win_prob: 0.4, predicted_home_score: 100, predicted_away_score: 95, model_confidence: "Medium" },
      counterfactual: { home_win_prob: 0.9, draw_prob: null, away_win_prob: 0.1, predicted_home_score: 108, predicted_away_score: 90, model_confidence: "High" },
    };
    vi.spyOn(api, "fetchWhatIf").mockResolvedValue(result);

    render(<WhatIfPanel gameId={1} />);

    fireEvent.click(screen.getByRole("button", { name: /run what-if/i }));

    await waitFor(() => expect(screen.getByText("Home 90%")).toBeInTheDocument());
    expect(screen.getByText("Home 60%")).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    vi.spyOn(api, "fetchWhatIf").mockRejectedValue(new Error("boom"));

    render(<WhatIfPanel gameId={1} />);

    fireEvent.click(screen.getByRole("button", { name: /run what-if/i }));

    await waitFor(() => expect(screen.getByText(/couldn't run the what-if simulation/i)).toBeInTheDocument());
  });
});
