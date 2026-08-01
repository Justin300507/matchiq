import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccuracyPage } from "../pages/AccuracyPage";
import * as api from "../api";
import type { BacktestOut } from "../types";

const nbaResult: BacktestOut = {
  sport: "nba", predictions_evaluated: 120, model_accuracy: 0.586, model_log_loss: 0.65,
  model_brier_score: 0.23, baseline_accuracy: 0.53, baseline_log_loss: 15.2, baseline_brier_score: 0.47,
  labels: ["H", "A"], confusion_matrix: [[50, 10], [15, 45]], roc_auc: 0.72,
  reliability_bins: [{ bin_start: 0.8, bin_end: 0.9, avg_confidence: 0.85, observed_accuracy: 0.8, count: 20 }],
};
const soccerResult: BacktestOut = {
  sport: "soccer", predictions_evaluated: 200, model_accuracy: 0.48, model_log_loss: 1.0,
  model_brier_score: 0.22, baseline_accuracy: 0.43, baseline_log_loss: 20.0, baseline_brier_score: 0.59,
  labels: ["H", "D", "A"], confusion_matrix: [], roc_auc: null, reliability_bins: [],
};

describe("AccuracyPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders backtest metrics for both sports once loaded", async () => {
    vi.spyOn(api, "fetchAccuracy").mockImplementation(async (sport) =>
      sport === "nba" ? nbaResult : soccerResult,
    );

    render(<MemoryRouter><AccuracyPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("58.6%")).toBeInTheDocument());
    expect(screen.getByText("48.0%")).toBeInTheDocument();
    expect(screen.getByText("53.0%")).toBeInTheDocument();

    // NBA has a confusion matrix and reliability bin; soccer has neither (roc_auc: null).
    expect(screen.getByText("0.720")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText(/80% actual · n=20/)).toBeInTheDocument();
  });

  it("shows a friendly message for a sport with no trained model", async () => {
    vi.spyOn(api, "fetchAccuracy").mockImplementation(async (sport) => {
      if (sport === "soccer") {
        throw new Error("503");
      }
      return nbaResult;
    });

    render(<MemoryRouter><AccuracyPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText(/no trained model available yet for soccer/i)).toBeInTheDocument());
  });
});
